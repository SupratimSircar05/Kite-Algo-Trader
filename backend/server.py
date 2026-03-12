from fastapi import FastAPI, APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import os
import gc
import logging
import csv
import io
import itertools
import math
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from trading_bot.models import (
    Signal, Order, Trade, Position, Instrument, BacktestResult,
    RiskConfig, StrategyConfig, AppSettings, DashboardSummary,
    BotRunRecord, Candle, gen_id, now_utc
)
from trading_bot.enums import (
    TradingMode, Side, OrderType, OrderStatus, BotStatus,
    SignalStatus, TradeStatus, PositionStatus, ProductType
)
from trading_bot.strategies import get_strategy, list_strategies, STRATEGY_REGISTRY
from trading_bot.risk import RiskManager
from trading_bot.execution import OrderManager, TradeEngine
from trading_bot.broker_paper import PaperBroker
from trading_bot.backtest import BacktestEngine
from trading_bot.config import is_market_open, DEFAULT_INSTRUMENTS, DEFAULT_SMA_PARAMS, DEFAULT_BREAKOUT_PARAMS
from trading_bot.trendshift import TrendShiftStrategy
from trading_bot.indicators import compute_all_indicators
from trading_bot.alerts import alert_manager
from trading_bot.walk_forward import WalkForwardEngine
from trading_bot.live_ticks import live_tick_manager
from trading_bot.ml_signals import ml_service
from trading_bot.job_queue import JobQueueManager
from trading_bot.portfolio_risk import portfolio_risk_manager

# Register TrendShift strategy
STRATEGY_REGISTRY["trendshift"] = TrendShiftStrategy

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="KiteAlgo Trading Bot API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global state
paper_broker = PaperBroker()
risk_config = RiskConfig()
risk_manager = RiskManager(risk_config)
trade_engine = TradeEngine()
order_manager = OrderManager(paper_broker, risk_manager, TradingMode.PAPER)
job_queue = JobQueueManager(db)
bot_status = BotStatus.IDLE
bot_run_id: Optional[str] = None
bot_start_time: Optional[datetime] = None


def _chunk_items(items: List[Dict[str, Any]], chunk_size: int) -> List[List[Dict[str, Any]]]:
    return [items[index:index + chunk_size] for index in range(0, len(items), chunk_size)]


async def _store_chunked_items(collection_name: str, parent_field: str, parent_id: str, kind: str, items: List[Dict[str, Any]], chunk_size: int):
    await db[collection_name].delete_many({parent_field: parent_id, "kind": kind})
    if not items:
        return
    docs = [
        {
            parent_field: parent_id,
            "kind": kind,
            "chunk_index": chunk_index,
            "items": chunk,
            "created_at": now_utc(),
        }
        for chunk_index, chunk in enumerate(_chunk_items(items, chunk_size))
    ]
    await db[collection_name].insert_many(docs)


async def _load_chunked_items(collection_name: str, parent_field: str, parent_id: str, kind: str) -> List[Dict[str, Any]]:
    chunks = await db[collection_name].find(
        {parent_field: parent_id, "kind": kind},
        {"_id": 0, "items": 1},
    ).sort("chunk_index", 1).to_list(5000)
    items: List[Dict[str, Any]] = []
    for chunk in chunks:
        items.extend(chunk.get("items", []))
    return items


async def _store_backtest_result_doc(result_doc: Dict[str, Any]):
    summary_doc = {k: v for k, v in result_doc.items() if k not in {"equity_curve", "trades"}}
    summary_doc.update({
        "has_chunked_details": True,
        "equity_curve_points": len(result_doc.get("equity_curve", [])),
        "trade_rows": len(result_doc.get("trades", [])),
    })
    await db.backtest_results.update_one({"id": summary_doc["id"]}, {"$set": summary_doc}, upsert=True)
    await _store_chunked_items("backtest_result_chunks", "result_id", summary_doc["id"], "equity_curve", result_doc.get("equity_curve", []), 400)
    await _store_chunked_items("backtest_result_chunks", "result_id", summary_doc["id"], "trades", result_doc.get("trades", []), 250)


async def _load_backtest_result_doc(result_doc: Dict[str, Any]) -> Dict[str, Any]:
    if not result_doc:
        return result_doc
    if result_doc.get("has_chunked_details"):
        detail = result_doc.copy()
        detail["equity_curve"] = await _load_chunked_items("backtest_result_chunks", "result_id", result_doc["id"], "equity_curve")
        detail["trades"] = await _load_chunked_items("backtest_result_chunks", "result_id", result_doc["id"], "trades")
        return detail
    return result_doc


async def _store_optimizer_result_doc(result_doc: Dict[str, Any]):
    summary_doc = {k: v for k, v in result_doc.items() if k not in {"results"}}
    summary_doc.update({
        "has_chunked_rows": True,
        "result_rows_count": len(result_doc.get("results", [])),
    })
    await db.optimizer_results.update_one({"id": summary_doc["id"]}, {"$set": summary_doc}, upsert=True)
    await _store_chunked_items("optimizer_result_chunks", "result_id", summary_doc["id"], "results", result_doc.get("results", []), 250)


async def _load_optimizer_result_doc(result_doc: Dict[str, Any]) -> Dict[str, Any]:
    if not result_doc:
        return result_doc
    if result_doc.get("has_chunked_rows"):
        detail = result_doc.copy()
        detail["results"] = await _load_chunked_items("optimizer_result_chunks", "result_id", result_doc["id"], "results")
        return detail
    return result_doc


async def _resolve_strategy_runtime_params(strategy_name: str, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    strategy_doc = await db.strategy_configs.find_one({"name": strategy_name}, {"_id": 0, "parameters": 1})
    saved_params = (strategy_doc or {}).get("parameters", {})
    return {**saved_params, **(overrides or {})}


def _estimate_candle_count(start_date: str, end_date: str, timeframe: str) -> int:
    try:
        start = datetime.fromisoformat(start_date.replace("Z", "+00:00")) if "T" in start_date else datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00")) if "T" in end_date else datetime.strptime(end_date, "%Y-%m-%d")
        total_seconds = max((end - start).total_seconds(), 1)
        if timeframe == "day":
            step_seconds = 24 * 60 * 60
        elif timeframe.endswith("m"):
            step_seconds = max(int(timeframe.replace("m", "")), 1) * 60
        else:
            step_seconds = 24 * 60 * 60
        return max(int(total_seconds / step_seconds), 1)
    except Exception:
        return 1


def _make_progress_callback(async_progress):
    loop = asyncio.get_running_loop()

    def callback(progress_pct: float, message: str, extra_fields: Optional[Dict[str, Any]] = None):
        asyncio.run_coroutine_threadsafe(async_progress(progress_pct, message, extra_fields), loop)

    return callback


def _build_param_axes(param_ranges: Dict[str, Dict[str, float]]) -> Dict[str, List[float]]:
    axes: Dict[str, List[float]] = {}
    for name, rng in param_ranges.items():
        mn, mx, step = rng["min"], rng["max"], rng["step"]
        if step <= 0:
            axes[name] = [mn]
            continue
        values = []
        cursor = mn
        while cursor <= mx + 1e-9:
            values.append(round(cursor, 6))
            cursor += step
        axes[name] = values
    return axes


def _iter_param_grid(axes: Dict[str, List[float]]):
    keys = list(axes.keys())
    for combo in itertools.product(*(axes[key] for key in keys)):
        yield dict(zip(keys, combo))


def _param_grid_size(axes: Dict[str, List[float]]) -> int:
    if not axes:
        return 0
    return math.prod(len(values) for values in axes.values())


def _valid_combo(strategy_name: str, params: Dict[str, Any]) -> bool:
    if strategy_name == "trendshift":
        ema_fast = params.get("ema_fast")
        ema_mid = params.get("ema_mid")
        ema_slow = params.get("ema_slow")
        if ema_fast is not None and ema_mid is not None and ema_slow is not None and not (ema_fast < ema_mid < ema_slow):
            return False
        if params.get("min_confidence") and not (0.35 <= params["min_confidence"] <= 0.95):
            return False
        if params.get("ml_min_confidence") and not (0.35 <= params["ml_min_confidence"] <= 0.95):
            return False
    return True


def _score_optimizer_entry(entry: Dict[str, Any], objective: str) -> float:
    total_return = entry.get("total_return_pct", 0)
    win_rate = entry.get("win_rate", 0)
    drawdown = entry.get("max_drawdown_pct", 0)
    sharpe = entry.get("sharpe_ratio", 0)
    profit_factor = entry.get("profit_factor", 0)
    expectancy = entry.get("expectancy", 0)
    avg_slippage_bps = entry.get("avg_slippage_bps", 0)

    if objective == "win_rate":
        return win_rate * 1.4 + sharpe * 8 + total_return * 0.3 - drawdown * 0.8 - avg_slippage_bps * 0.5
    if objective == "profit":
        return total_return * 1.1 + sharpe * 6 + expectancy * 0.04 - drawdown * 0.45 - avg_slippage_bps * 0.25
    if objective == "low_slippage":
        return total_return * 0.5 + win_rate * 0.7 + sharpe * 6 - drawdown * 0.8 - avg_slippage_bps * 1.2
    return total_return * 0.7 + win_rate * 0.6 + sharpe * 8 + profit_factor * 4 + expectancy * 0.03 - drawdown * 0.75 - avg_slippage_bps * 0.45


def _run_backtest_sync(req: "BacktestRequest", candles: List[Dict[str, Any]], params: Dict[str, Any], progress_callback=None) -> Dict[str, Any]:
    strategy = get_strategy(req.strategy_name, params or None)
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=req.initial_capital,
        quantity=req.quantity,
        progress_callback=progress_callback,
    )
    result = engine.run(candles, symbol=req.symbol, exchange="NSE", timeframe=req.timeframe)
    return result.model_dump()


def _run_optimizer_sync(
    req: "OptimizerRequest",
    candles: List[Dict[str, Any]],
    base_params: Dict[str, Any],
    total_combinations: int,
    progress_callback=None,
) -> Dict[str, Any]:
    axes = _build_param_axes(req.param_ranges)
    results: List[Dict[str, Any]] = []
    best_result: Optional[Dict[str, Any]] = None
    best_score = -float("inf")
    processed = 0

    for combo in _iter_param_grid(axes):
        params = {**base_params, **combo}
        for key, value in list(params.items()):
            if isinstance(value, float) and value == int(value):
                params[key] = int(value)
        if not _valid_combo(req.strategy_name, params):
            continue

        processed += 1
        strategy = get_strategy(req.strategy_name, params)
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=req.initial_capital,
            quantity=req.quantity,
            lightweight=True,
        )
        result = engine.run(candles, symbol=req.symbol, exchange="NSE", timeframe=req.timeframe)
        entry = {
            "params": combo,
            "total_return_pct": result.total_return_pct,
            "total_return": result.total_return,
            "total_trades": result.total_trades,
            "win_rate": result.win_rate,
            "max_drawdown_pct": result.max_drawdown_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "profit_factor": result.profit_factor,
            "expectancy": result.expectancy,
            "final_capital": result.final_capital,
            "avg_slippage_bps": result.avg_slippage_bps,
            "slippage_cost_total": result.slippage_cost_total,
        }
        entry["objective_score"] = round(_score_optimizer_entry(entry, req.objective), 4)
        results.append(entry)
        if entry["objective_score"] > best_score:
            best_score = entry["objective_score"]
            best_result = entry

        # Release references and run GC periodically
        del engine, strategy, result
        if processed % 25 == 0:
            gc.collect()

        if progress_callback and (processed == 1 or processed % max(1, total_combinations // 100) == 0 or processed == total_combinations):
            progress_callback(
                100 * processed / max(total_combinations, 1),
                f"Processed {processed}/{total_combinations} combinations",
                {"processed_items": processed, "total_items": total_combinations},
            )

    gc.collect()

    param_names = list(req.param_ranges.keys())
    heatmap = None
    if len(param_names) >= 2 and results:
        x_param, y_param = param_names[0], param_names[1]
        x_vals = sorted(set(r["params"][x_param] for r in results))
        y_vals = sorted(set(r["params"][y_param] for r in results))
        lookup = {(r["params"][x_param], r["params"][y_param]): r for r in results}
        heatmap = {
            "x_param": x_param,
            "y_param": y_param,
            "x_values": x_vals,
            "y_values": y_vals,
            "grid": [
                [
                    {
                        "x": x,
                        "y": y,
                        "return_pct": lookup.get((x, y), {}).get("total_return_pct", 0),
                        "sharpe": lookup.get((x, y), {}).get("sharpe_ratio", 0),
                        "trades": lookup.get((x, y), {}).get("total_trades", 0),
                        "win_rate": lookup.get((x, y), {}).get("win_rate", 0),
                        "drawdown": lookup.get((x, y), {}).get("max_drawdown_pct", 0),
                        "objective_score": lookup.get((x, y), {}).get("objective_score", 0),
                    }
                    for x in x_vals
                ]
                for y in y_vals
            ],
        }

    results.sort(key=lambda row: row.get("objective_score", row.get("total_return_pct", 0)), reverse=True)
    return {
        "id": gen_id(),
        "strategy_name": req.strategy_name,
        "symbol": req.symbol,
        "start_date": req.start_date,
        "end_date": req.end_date,
        "initial_capital": req.initial_capital,
        "quantity": req.quantity,
        "timeframe": req.timeframe,
        "param_ranges": req.param_ranges,
        "fixed_params": req.fixed_params,
        "objective": req.objective,
        "total_combinations": total_combinations,
        "best_params": best_result["params"] if best_result else {},
        "best_return_pct": best_result.get("total_return_pct", 0) if best_result else 0,
        "best_result": best_result,
        "best_objective_score": best_score if best_result else 0,
        "heatmap": heatmap,
        "results": results,
        "created_at": now_utc(),
    }


async def _process_backtest_job(job_id: str, payload: Dict[str, Any], progress):
    req = BacktestRequest(**payload)
    params = await _resolve_strategy_runtime_params(req.strategy_name, req.parameters)
    candles = await paper_broker.get_historical_data(req.symbol, "NSE", req.timeframe, req.start_date, req.end_date)
    progress_callback = _make_progress_callback(progress)
    result_doc = await asyncio.to_thread(_run_backtest_sync, req, candles, params, progress_callback)
    await _store_backtest_result_doc(result_doc)
    return {
        "kind": "backtest",
        "result_id": result_doc["id"],
        "summary": {
            "strategy_name": result_doc["strategy_name"],
            "symbol": result_doc["symbol"],
            "total_return_pct": result_doc["total_return_pct"],
            "win_rate": result_doc["win_rate"],
            "total_trades": result_doc["total_trades"],
        },
    }


async def _process_optimizer_job(job_id: str, payload: Dict[str, Any], progress):
    req = OptimizerRequest(**payload)
    axes = _build_param_axes(req.param_ranges)
    total_combinations = sum(1 for combo in _iter_param_grid(axes) if _valid_combo(req.strategy_name, {**req.fixed_params, **combo}))
    base_params = await _resolve_strategy_runtime_params(req.strategy_name, req.fixed_params)
    candles = await paper_broker.get_historical_data(req.symbol, "NSE", req.timeframe, req.start_date, req.end_date)
    progress_callback = _make_progress_callback(progress)
    result_doc = await asyncio.to_thread(_run_optimizer_sync, req, candles, base_params, total_combinations, progress_callback)
    await _store_optimizer_result_doc(result_doc)
    return {
        "kind": "optimizer",
        "result_id": result_doc["id"],
        "summary": {
            "strategy_name": result_doc["strategy_name"],
            "symbol": result_doc["symbol"],
            "best_return_pct": result_doc["best_return_pct"],
            "objective": result_doc["objective"],
            "best_objective_score": result_doc.get("best_objective_score", 0),
        },
    }


async def _get_settings_doc() -> Dict[str, Any]:
    settings_doc = await db.settings.find_one({}, {"_id": 0})
    if settings_doc:
        return settings_doc
    default_doc = AppSettings().model_dump()
    await db.settings.insert_one(default_doc.copy())
    return default_doc


async def _configure_alert_channels() -> Dict[str, bool]:
    settings_doc = await _get_settings_doc()
    alert_manager.update_config(
        telegram_token=settings_doc.get("telegram_bot_token", ""),
        telegram_chat_id=settings_doc.get("telegram_chat_id", ""),
        webhook_url=settings_doc.get("webhook_url", ""),
    )
    return {
        "telegram_configured": alert_manager.telegram_configured,
        "webhook_configured": alert_manager.webhook_configured,
    }


def _build_trade_query(
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    status: Optional[str] = None,
    side: Optional[str] = None,
) -> Dict[str, Any]:
    query: Dict[str, Any] = {}
    if symbol:
        query["symbol"] = symbol
    if strategy:
        query["strategy_name"] = strategy
    if status:
        query["status"] = status
    if side:
        query["side"] = side
    return query


async def _get_trade_journal_payload(
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    status: Optional[str] = None,
    side: Optional[str] = None,
    limit: int = 250,
) -> Dict[str, Any]:
    query = _build_trade_query(symbol=symbol, strategy=strategy, status=status, side=side)
    trades = await db.trades.find(query, {"_id": 0}).sort("entry_time", -1).to_list(limit)

    total_trades = len(trades)
    closed_trades = [trade for trade in trades if trade.get("status") == TradeStatus.CLOSED]
    winning_trades = [trade for trade in closed_trades if trade.get("net_pnl", 0) > 0]
    net_pnl = round(sum(trade.get("net_pnl", 0) for trade in trades), 2)
    gross_pnl = round(sum(trade.get("pnl", 0) for trade in trades), 2)
    total_fees = round(sum(trade.get("fees", 0) for trade in trades), 2)
    win_rate = round((len(winning_trades) / len(closed_trades) * 100), 2) if closed_trades else 0
    avg_net_pnl = round((net_pnl / total_trades), 2) if total_trades else 0

    strategy_breakdown: Dict[str, int] = {}
    for trade in trades:
        strategy_name = trade.get("strategy_name") or "manual"
        strategy_breakdown[strategy_name] = strategy_breakdown.get(strategy_name, 0) + 1
    best_strategy = max(strategy_breakdown, key=strategy_breakdown.get) if strategy_breakdown else None

    best_trade = max(trades, key=lambda trade: trade.get("net_pnl", 0), default=None)
    worst_trade = min(trades, key=lambda trade: trade.get("net_pnl", 0), default=None)

    return {
        "summary": {
            "total_trades": total_trades,
            "closed_trades": len(closed_trades),
            "win_rate": win_rate,
            "net_pnl": net_pnl,
            "gross_pnl": gross_pnl,
            "total_fees": total_fees,
            "avg_net_pnl": avg_net_pnl,
            "best_strategy": best_strategy,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "strategy_breakdown": strategy_breakdown,
        },
        "filters": {
            "symbol": symbol,
            "strategy": strategy,
            "status": status,
            "side": side,
            "limit": limit,
        },
        "trades": trades,
    }


def _serialize_chart_indicators(indicators: Dict[str, Any], max_points: int = 180) -> Dict[str, Any]:
    serialized: Dict[str, Any] = {}
    for key, value in indicators.items():
        if isinstance(value, list) and value and not isinstance(value[0], dict):
            serialized[key] = value[-max_points:]
        elif isinstance(value, list):
            serialized[key] = value[-10:]
        else:
            serialized[key] = value
    return serialized


def _generate_trendshift_signals(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    strategy = TrendShiftStrategy()
    signal_map = strategy.batch_generate_signals(candles, symbol=candles[-1].get("symbol", "") if candles else "", exchange="NSE")
    signals: List[Dict[str, Any]] = []
    for index, signal in signal_map.items():
        signals.append({**signal.model_dump(), "index": index})
    return signals[-12:]


async def _get_chart_payload(
    symbol: str,
    start_date: str,
    end_date: str,
    timeframe: str,
    include_indicators: bool,
    include_trendshift: bool,
    limit: int,
) -> Dict[str, Any]:
    candles = await paper_broker.get_historical_data(symbol, "NSE", timeframe, start_date, end_date)
    if not candles:
        raise HTTPException(404, "No candle data available")

    max_points = min(max(limit, 30), 240)
    trimmed_candles = candles[-max_points:]
    chart_candles = []
    for index, candle in enumerate(trimmed_candles):
        chart_candles.append({**candle, "symbol": symbol, "exchange": "NSE", "index": index})

    indicators: Dict[str, Any] = {}
    if include_indicators and len(chart_candles) > 10:
        indicators = _serialize_chart_indicators(
            compute_all_indicators(chart_candles, TrendShiftStrategy.default_params),
            max_points=max_points,
        )

    trendshift_signals = _generate_trendshift_signals(chart_candles) if include_trendshift else []
    last_close = chart_candles[-1]["close"]

    return {
        "symbol": symbol,
        "exchange": "NSE",
        "timeframe": timeframe,
        "count": len(chart_candles),
        "candles": chart_candles,
        "indicators": indicators,
        "trendshift_signals": trendshift_signals,
        "zones": {
            "demand": indicators.get("demand_zones", [])[-4:] if indicators else [],
            "supply": indicators.get("supply_zones", [])[-4:] if indicators else [],
        },
        "indicator_summary": {
            "last_close": last_close,
            "rsi": round(indicators.get("rsi", [50])[-1], 2) if indicators else None,
            "supertrend_direction": indicators.get("supertrend_direction", [1])[-1] if indicators else None,
            "volume_relative": round(indicators.get("volume_relative", [1])[-1], 2) if indicators else None,
            "signal_count": len(trendshift_signals),
        },
    }


async def _process_zerodha_callback(request_token: str, status: str = "success") -> Dict[str, Any]:
    if status != "success":
        raise HTTPException(400, "Login was not successful")

    settings_doc = await _get_settings_doc()
    api_key = settings_doc.get("kite_api_key", "")
    api_secret = settings_doc.get("kite_api_secret", "")
    if not api_key or not api_secret:
        raise HTTPException(400, "API Key and Secret must be set in Settings")

    try:
        from trading_bot.broker_zerodha import ZerodhaBroker

        broker = ZerodhaBroker(api_key=api_key, api_secret=api_secret)
        session_data = await broker.generate_session(request_token)
        access_token = session_data.get("access_token", "")
        await db.settings.update_one(
            {},
            {"$set": {"kite_access_token": access_token, "updated_at": now_utc()}},
            upsert=True,
        )
        return {
            "status": "success",
            "access_token_set": bool(access_token),
            "user_id": session_data.get("user_id", ""),
            "user_name": session_data.get("user_name", ""),
            "login_time": session_data.get("login_time", ""),
        }
    except Exception as e:
        raise HTTPException(500, f"Session generation failed: {str(e)}")


# ==================== DASHBOARD ====================
@api_router.get("/dashboard/summary")
async def get_dashboard_summary():
    settings_doc = await db.settings.find_one({}, {"_id": 0})
    settings = AppSettings(**(settings_doc or {}))
    risk_doc = await db.risk_config.find_one({}, {"_id": 0})
    risk_cfg = RiskConfig(**(risk_doc or {}))

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()
    today_trades = await db.trades.count_documents({"entry_time": {"$gte": today_start}})
    today_signals = await db.signals.count_documents({"timestamp": {"$gte": today_start}})
    open_positions = await db.positions.count_documents({"status": PositionStatus.OPEN})

    # Calculate daily PnL from today's closed trades
    pipeline = [
        {"$match": {"exit_time": {"$gte": today_start}, "status": TradeStatus.CLOSED}},
        {"$group": {"_id": None, "total_pnl": {"$sum": "$net_pnl"}, "count": {"$sum": 1},
                     "wins": {"$sum": {"$cond": [{"$gt": ["$net_pnl", 0]}, 1, 0]}}}}
    ]
    pnl_result = await db.trades.aggregate(pipeline).to_list(1)
    daily_pnl = pnl_result[0]["total_pnl"] if pnl_result else 0
    win_count = pnl_result[0]["wins"] if pnl_result else 0
    trade_count = pnl_result[0]["count"] if pnl_result else 0
    win_rate = (win_count / trade_count * 100) if trade_count > 0 else 0

    # Total PnL
    total_pipeline = [
        {"$match": {"status": TradeStatus.CLOSED}},
        {"$group": {"_id": None, "total_pnl": {"$sum": "$net_pnl"}}}
    ]
    total_result = await db.trades.aggregate(total_pipeline).to_list(1)
    total_pnl = total_result[0]["total_pnl"] if total_result else 0

    last_signal = await db.signals.find_one({}, {"_id": 0}, sort=[("timestamp", -1)])

    uptime = 0
    if bot_start_time:
        uptime = int((datetime.now(timezone.utc) - bot_start_time).total_seconds())

    # Get active strategy
    active_strat = await db.strategy_configs.find_one({"enabled": True}, {"_id": 0})

    return DashboardSummary(
        bot_status=bot_status,
        trading_mode=settings.trading_mode,
        capital=settings.capital,
        daily_pnl=round(daily_pnl, 2),
        daily_pnl_pct=round(daily_pnl / settings.capital * 100, 2) if settings.capital > 0 else 0,
        total_pnl=round(total_pnl, 2),
        open_positions=open_positions,
        total_trades_today=today_trades,
        total_signals_today=today_signals,
        win_rate=round(win_rate, 2),
        active_strategy=active_strat["name"] if active_strat else "None",
        kill_switch_active=risk_cfg.kill_switch_active,
        market_status="OPEN" if is_market_open() else "CLOSED",
        last_signal_time=last_signal["timestamp"] if last_signal else None,
        uptime_seconds=uptime,
    ).model_dump()


# ==================== BOT CONTROL ====================
class BotStartRequest(BaseModel):
    strategy_name: str = "sma_crossover"
    symbols: List[str] = Field(default_factory=lambda: ["RELIANCE", "INFY"])
    mode: TradingMode = TradingMode.PAPER

class BotStopRequest(BaseModel):
    reason: str = "Manual stop"

@api_router.post("/bot/start")
async def start_bot(req: BotStartRequest):
    global bot_status, bot_run_id, bot_start_time

    if bot_status == BotStatus.RUNNING:
        raise HTTPException(400, "Bot is already running")

    if req.mode == TradingMode.LIVE:
        settings_doc = await db.settings.find_one({}, {"_id": 0})
        if not settings_doc or not settings_doc.get("kite_api_key"):
            raise HTTPException(400, "Live trading requires Kite API credentials. Configure in Settings.")

    bot_run_id = gen_id()
    bot_start_time = datetime.now(timezone.utc)
    bot_status = BotStatus.RUNNING

    run_record = BotRunRecord(
        id=bot_run_id, mode=req.mode, strategy_name=req.strategy_name,
        status=BotStatus.RUNNING, started_at=now_utc()
    ).model_dump()
    await db.bot_runs.insert_one(run_record)

    # Generate initial signals for demonstration
    await _generate_demo_signals(req.strategy_name, req.symbols)
    await _configure_alert_channels()
    await alert_manager.send_bot_status_alert("started", req.strategy_name, req.mode.value)

    return {"status": "started", "run_id": bot_run_id, "mode": req.mode, "strategy": req.strategy_name}


@api_router.post("/bot/stop")
async def stop_bot(req: BotStopRequest):
    global bot_status, bot_run_id, bot_start_time

    if bot_status != BotStatus.RUNNING:
        raise HTTPException(400, "Bot is not running")

    bot_status = BotStatus.STOPPED
    if bot_run_id:
        await db.bot_runs.update_one(
            {"id": bot_run_id},
            {"$set": {"status": BotStatus.STOPPED, "stopped_at": now_utc()}}
        )
    await _configure_alert_channels()
    await alert_manager.send_bot_status_alert("stopped", "", "paper")
    bot_run_id = None
    bot_start_time = None
    return {"status": "stopped", "reason": req.reason}


@api_router.get("/bot/status")
async def get_bot_status():
    return {"status": bot_status, "run_id": bot_run_id,
            "uptime": int((datetime.now(timezone.utc) - bot_start_time).total_seconds()) if bot_start_time else 0}


async def _generate_demo_signals(strategy_name: str, symbols: List[str]):
    """Generate demo signals by running strategy on paper broker's synthetic data."""
    try:
        strategy = get_strategy(strategy_name)
        for symbol in symbols:
            candles = await paper_broker.get_historical_data(symbol, "NSE", "day", "2025-01-01", "2025-06-01")
            if not candles:
                continue
            strategy.reset()
            batch_generator = getattr(strategy, "batch_generate_signals", None)
            if callable(batch_generator):
                signal_map = batch_generator(candles, symbol=symbol, exchange="NSE")
                generated_signals = [(candles[index], signal) for index, signal in signal_map.items()]
            else:
                warmup_size = getattr(strategy, '_warmup_period', 20)
                generated_signals = []
                if len(candles) > warmup_size:
                    strategy.warmup(candles[:warmup_size])
                    for candle in candles[warmup_size:]:
                        candle["symbol"] = symbol
                        candle["exchange"] = "NSE"
                        signal = strategy.on_candle(candle)
                        if signal:
                            generated_signals.append((candle, signal))
            for candle, signal in generated_signals:
                sig_doc = signal.model_dump()
                await db.signals.insert_one(sig_doc)

                result = await order_manager.execute_signal(signal)
                if result.get("success"):
                    order_doc = result["order"]
                    await db.orders.insert_one(order_doc)

                    fill_price = order_doc.get("filled_price") or signal.price or candle["close"]
                    if fill_price is None:
                        fill_price = candle["close"]
                    trade = trade_engine.open_trade(Order(**order_doc), fill_price, strategy_name)
                    import random
                    exit_mult = 1 + random.uniform(-0.02, 0.03)
                    exit_price = round(fill_price * exit_mult, 2)
                    closed = trade_engine.close_trade(trade.id, exit_price)
                    if closed:
                        await db.trades.insert_one(closed.model_dump())
                        pos = Position(
                            symbol=symbol, exchange="NSE", side=signal.side,
                            quantity=signal.quantity, avg_price=fill_price,
                            current_price=exit_price,
                            realized_pnl=closed.net_pnl,
                            status=PositionStatus.CLOSED,
                            strategy_name=strategy_name,
                            trading_mode=TradingMode.PAPER,
                        )
                        await db.positions.insert_one(pos.model_dump())
        logger.info(f"Demo signals generated for {symbols}")
    except Exception as e:
        logger.error(f"Error generating demo signals: {e}")


# ==================== SIGNALS ====================
@api_router.get("/signals")
async def get_signals(
    limit: int = Query(50, le=200),
    strategy: Optional[str] = None,
    symbol: Optional[str] = None,
    status: Optional[str] = None,
):
    query = {}
    if strategy:
        query["strategy_name"] = strategy
    if symbol:
        query["symbol"] = symbol
    if status:
        query["status"] = status
    signals = await db.signals.find(query, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return signals


@api_router.post("/signals/generate")
async def generate_signals_manual(strategy_name: str = "sma_crossover", symbol: str = "RELIANCE"):
    """Manually trigger signal generation for testing."""
    try:
        strategy = get_strategy(strategy_name)
        candles = await paper_broker.get_historical_data(symbol, "NSE", "day", "2025-01-01", "2025-12-01")
        strategy.reset()
        signals_generated = []
        batch_generator = getattr(strategy, "batch_generate_signals", None)
        if callable(batch_generator):
            signal_map = batch_generator(candles, symbol=symbol, exchange="NSE")
            for _, signal in signal_map.items():
                sig_doc = signal.model_dump()
                signals_generated.append(sig_doc.copy())
                await db.signals.insert_one(sig_doc)
        else:
            warmup_size = getattr(strategy, '_warmup_period', 20)
            if len(candles) > warmup_size:
                strategy.warmup(candles[:warmup_size])
                for candle in candles[warmup_size:]:
                    candle["symbol"] = symbol
                    candle["exchange"] = "NSE"
                    signal = strategy.on_candle(candle)
                    if signal:
                        sig_doc = signal.model_dump()
                        signals_generated.append(sig_doc.copy())
                        await db.signals.insert_one(sig_doc)
        return {"count": len(signals_generated), "signals": signals_generated[:10]}
    except Exception as e:
        raise HTTPException(500, str(e))


# ==================== ORDERS ====================
@api_router.get("/orders")
async def get_orders(limit: int = Query(50, le=200), status: Optional[str] = None):
    query = {}
    if status:
        query["status"] = status
    orders = await db.orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return orders


class PlaceOrderRequest(BaseModel):
    symbol: str
    side: Side
    quantity: int = 1
    order_type: OrderType = OrderType.MARKET
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    product: ProductType = ProductType.MIS

@api_router.post("/orders/place")
async def place_order_manual(req: PlaceOrderRequest):
    """Manually place an order through the paper broker."""
    signal = Signal(
        symbol=req.symbol, side=req.side, quantity=req.quantity,
        price=req.price, strategy_name="manual",
    )
    result = await order_manager.execute_signal(
        signal, order_type=req.order_type, product=req.product
    )
    if result.get("success"):
        await db.orders.insert_one(result["order"].copy())
        await db.signals.insert_one(signal.model_dump())
    return result


# ==================== TRADES ====================
@api_router.get("/trades")
async def get_trades(limit: int = Query(50, le=200), status: Optional[str] = None):
    query = {}
    if status:
        query["status"] = status
    trades = await db.trades.find(query, {"_id": 0}).sort("entry_time", -1).to_list(limit)
    return trades


# ==================== POSITIONS ====================
@api_router.get("/positions")
async def get_positions(status: Optional[str] = None):
    query = {}
    if status:
        query["status"] = status
    positions = await db.positions.find(query, {"_id": 0}).sort("opened_at", -1).to_list(100)
    return positions


# ==================== STRATEGIES ====================
@api_router.get("/strategies")
async def get_strategies_list():
    """List all available strategies with their current configs."""
    available = list_strategies()
    configs = await db.strategy_configs.find({}, {"_id": 0}).to_list(100)
    config_map = {c["name"]: c for c in configs}
    result = []
    for strat in available:
        saved = config_map.get(strat["name"], {})
        result.append({
            **strat,
            "enabled": saved.get("enabled", False),
            "symbols": saved.get("symbols", ["RELIANCE", "INFY", "TCS", "HDFCBANK"]),
            "timeframe": saved.get("timeframe", "5m"),
            "quantity": saved.get("quantity", 1),
            "saved_params": saved.get("parameters", strat["default_params"]),
        })
    return result


@api_router.put("/strategies/{name}")
async def update_strategy_config(name: str, config: Dict[str, Any]):
    """Update strategy configuration."""
    if name not in STRATEGY_REGISTRY:
        raise HTTPException(404, f"Strategy '{name}' not found")
    config["name"] = name
    config["updated_at"] = now_utc()
    await db.strategy_configs.update_one(
        {"name": name}, {"$set": config}, upsert=True
    )
    return {"status": "updated", "name": name}


@api_router.post("/strategies/{name}/defaults")
async def save_strategy_defaults(name: str, payload: Dict[str, Any]):
    if name not in STRATEGY_REGISTRY:
        raise HTTPException(404, f"Strategy '{name}' not found")
    parameters = payload.get("parameters") or {}
    existing = await db.strategy_configs.find_one({"name": name}, {"_id": 0})
    merged = {
        **(existing or {}),
        "name": name,
        "parameters": parameters,
        "updated_at": now_utc(),
    }
    await db.strategy_configs.update_one({"name": name}, {"$set": merged}, upsert=True)
    return {"status": "updated", "name": name, "parameters": parameters}


@api_router.get("/jobs")
async def list_analysis_jobs(kind: Optional[str] = None, limit: int = Query(20, le=100)):
    return await job_queue.list_jobs(kind=kind, limit=limit)


@api_router.get("/jobs/{job_id}")
async def get_analysis_job(job_id: str):
    job = await job_queue.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


# ==================== RISK CONTROLS ====================
@api_router.get("/risk/config")
async def get_risk_config():
    doc = await db.risk_config.find_one({}, {"_id": 0})
    if not doc:
        default = RiskConfig()
        doc = default.model_dump()
        await db.risk_config.insert_one(doc)
    return doc


@api_router.put("/risk/config")
async def update_risk_config(config: Dict[str, Any]):
    config["updated_at"] = now_utc()
    await db.risk_config.update_one({}, {"$set": config}, upsert=True)
    # Update in-memory risk manager
    global risk_config, risk_manager
    doc = await db.risk_config.find_one({}, {"_id": 0})
    risk_config = RiskConfig(**(doc or {}))
    risk_manager = RiskManager(risk_config)
    return {"status": "updated"}


@api_router.post("/risk/kill-switch")
async def toggle_kill_switch(active: bool, reason: str = "Manual toggle"):
    await db.risk_config.update_one(
        {}, {"$set": {"kill_switch_active": active, "kill_switch_reason": reason if active else None, "updated_at": now_utc()}},
        upsert=True
    )
    global risk_config, risk_manager
    risk_config.kill_switch_active = active
    risk_config.kill_switch_reason = reason if active else None
    if active:
        risk_manager.activate_kill_switch(reason)
    else:
        risk_manager.deactivate_kill_switch()
    await _configure_alert_channels()
    await alert_manager.send_kill_switch_alert(active, reason)
    return {"kill_switch_active": active, "reason": reason if active else None}


# ==================== TRADE JOURNAL EXPORT ====================
@api_router.get("/journal")
async def get_trade_journal(
    limit: int = Query(250, le=1000),
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    status: Optional[str] = None,
    side: Optional[str] = None,
):
    return await _get_trade_journal_payload(
        symbol=symbol,
        strategy=strategy,
        status=status,
        side=side,
        limit=limit,
    )


@api_router.get("/journal/export")
async def export_trade_journal(
    format: str = Query("csv", pattern="^(csv|json)$"),
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    status: Optional[str] = None,
    side: Optional[str] = None,
):
    payload = await _get_trade_journal_payload(
        symbol=symbol,
        strategy=strategy,
        status=status,
        side=side,
        limit=10000,
    )
    trades = payload["trades"]
    if not trades:
        raise HTTPException(404, "No trades to export")

    if format == "json":
        return payload

    output = io.StringIO()
    fields = [
        "id", "symbol", "exchange", "side", "quantity", "entry_price", "exit_price",
        "pnl", "net_pnl", "fees", "pnl_percent", "status", "strategy_name",
        "entry_time", "exit_time", "duration_seconds", "trading_mode",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for trade in trades:
        writer.writerow(trade)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trade_journal.csv"},
    )


@api_router.get("/export/trades/csv")
async def export_trades_csv():
    """Export all trades as CSV."""
    return await export_trade_journal(format="csv")


@api_router.get("/export/trades/json")
async def export_trades_json():
    """Export all trades as JSON."""
    payload = await _get_trade_journal_payload(limit=10000)
    return payload["trades"]


@api_router.get("/export/optimizer/csv/{result_id}")
async def export_optimizer_csv(result_id: str):
    """Export optimizer results as CSV."""
    result = await db.optimizer_results.find_one({"id": result_id}, {"_id": 0})
    if not result:
        raise HTTPException(404, "Optimizer result not found")
    result = await _load_optimizer_result_doc(result)
    output = io.StringIO()
    rows = result.get("results", [])
    if not rows:
        raise HTTPException(404, "No results to export")
    all_param_keys = list(rows[0].get("params", {}).keys())
    fields = all_param_keys + ["total_return_pct", "total_trades", "win_rate",
                                "max_drawdown_pct", "sharpe_ratio", "profit_factor", "expectancy"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        row = {**r.get("params", {}), **{k: r.get(k) for k in fields if k not in all_param_keys}}
        writer.writerow(row)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=optimizer_{result_id}.csv"}
    )


# ==================== TELEGRAM ALERTS ====================
@api_router.post("/alerts/test")
async def test_alert():
    """Send a test alert to configured channels."""
    channel_status = await _configure_alert_channels()
    if not alert_manager.telegram_configured and not alert_manager.webhook_configured:
        return {"status": "skipped", "reason": "No alert channels configured. Set Telegram token or webhook URL in Settings."}
    await alert_manager.send_custom("Test Alert", "KiteAlgo alert system is working.")
    return {"status": "sent", **channel_status}


class AlertNotifyRequest(BaseModel):
    title: str = "KiteAlgo Alert"
    message: str
    level: str = "info"
    metadata: Dict[str, Any] = Field(default_factory=dict)


@api_router.post("/alerts/notify")
async def notify_alert(req: AlertNotifyRequest):
    channel_status = await _configure_alert_channels()
    if not alert_manager.telegram_configured and not alert_manager.webhook_configured:
        return {
            "status": "skipped",
            "reason": "No alert channels configured. Add Telegram or webhook settings first.",
            **channel_status,
        }
    await alert_manager.send_custom(req.title, req.message, {"level": req.level, **req.metadata})
    return {"status": "sent", **channel_status}

@api_router.get("/alerts/status")
async def alerts_status():
    return await _configure_alert_channels()


# ==================== ZERODHA AUTH FLOW ====================
@api_router.get("/auth/zerodha/start")
async def start_zerodha_auth():
    settings_doc = await _get_settings_doc()
    api_key = settings_doc.get("kite_api_key", "")
    redirect_url = settings_doc.get("kite_redirect_url", "")
    if not api_key:
        return {
            "configured": False,
            "login_url": None,
            "redirect_url": redirect_url,
            "reason": "Add your Zerodha API key in Settings to enable the login flow.",
        }
    login_url = f"https://kite.zerodha.com/connect/login?v=3&api_key={api_key}"
    return {
        "configured": True,
        "login_url": login_url,
        "redirect_url": redirect_url,
        "has_access_token": bool(settings_doc.get("kite_access_token")),
    }


@api_router.get("/auth/zerodha/status")
async def get_zerodha_auth_status():
    settings_doc = await _get_settings_doc()
    status_payload = {
        "api_key_configured": bool(settings_doc.get("kite_api_key")),
        "api_secret_configured": bool(settings_doc.get("kite_api_secret")),
        "access_token_configured": bool(settings_doc.get("kite_access_token")),
        "redirect_url": settings_doc.get("kite_redirect_url", ""),
        "profile": None,
    }

    if status_payload["api_key_configured"] and status_payload["access_token_configured"]:
        try:
            from trading_bot.broker_zerodha import ZerodhaBroker

            broker = ZerodhaBroker(
                api_key=settings_doc.get("kite_api_key", ""),
                api_secret=settings_doc.get("kite_api_secret", ""),
                access_token=settings_doc.get("kite_access_token", ""),
            )
            if await broker.authenticate():
                profile = await broker.get_profile()
                status_payload["profile"] = {
                    "user_id": profile.get("user_id", ""),
                    "user_name": profile.get("user_name", ""),
                    "email": profile.get("email", ""),
                }
        except Exception as exc:
            status_payload["profile_error"] = str(exc)

    return status_payload


@api_router.get("/kite/login-url")
async def get_kite_login_url():
    """Get Zerodha login URL for OAuth redirect."""
    response = await start_zerodha_auth()
    if not response["configured"]:
        raise HTTPException(400, response["reason"])
    return {"login_url": response["login_url"], "api_key": (await _get_settings_doc()).get("kite_api_key", "")}


@api_router.get("/kite/callback")
async def kite_callback(request_token: str = Query(...), action: str = Query("login"), status: str = Query("success")):
    """Handle Zerodha OAuth callback. Generates session from request_token."""
    return await _process_zerodha_callback(request_token=request_token, status=status)


@api_router.get("/auth/zerodha/callback")
async def zerodha_auth_callback(request_token: str = Query(...), action: str = Query("login"), status: str = Query("success")):
    return await _process_zerodha_callback(request_token=request_token, status=status)


# ==================== WALK-FORWARD OPTIMIZATION ====================
class WalkForwardRequest(BaseModel):
    strategy_name: str = "sma_crossover"
    symbol: str = "RELIANCE"
    start_date: str = "2024-01-01"
    end_date: str = "2025-06-01"
    initial_capital: float = 100000.0
    quantity: int = 10
    n_windows: int = 5
    train_pct: float = 0.7
    param_ranges: Dict[str, Dict[str, float]] = Field(
        default_factory=lambda: {"fast_period": {"min": 5, "max": 20, "step": 2}, "slow_period": {"min": 15, "max": 50, "step": 5}}
    )

@api_router.post("/walkforward/run")
async def run_walk_forward(req: WalkForwardRequest):
    """Run walk-forward optimization with train/test splits."""
    try:
        candles = await paper_broker.get_historical_data(req.symbol, "NSE", "day", req.start_date, req.end_date)
        if not candles or len(candles) < 50:
            raise HTTPException(400, "Insufficient data for walk-forward analysis")
        engine = WalkForwardEngine(req.strategy_name, req.param_ranges, req.initial_capital, req.quantity)
        result = engine.run(candles, symbol=req.symbol, n_windows=req.n_windows, train_pct=req.train_pct)
        await db.walkforward_results.insert_one(result.copy())
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Walk-forward failed: {e}")
        raise HTTPException(500, str(e))

@api_router.get("/walkforward/results")
async def get_walkforward_results(limit: int = Query(20, le=50)):
    return await db.walkforward_results.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)


@api_router.post("/backtest/walk_forward")
async def run_walk_forward_backtest(req: WalkForwardRequest):
    return await run_walk_forward(req)


@api_router.get("/backtest/walk_forward/results")
async def get_walkforward_backtest_results(limit: int = Query(20, le=50)):
    return await get_walkforward_results(limit)


# ==================== CANDLESTICK DATA + INDICATORS ====================
@api_router.get("/chart/candles")
async def get_chart_candles(
    symbol: str = Query("RELIANCE"),
    start_date: str = Query("2024-06-01"),
    end_date: str = Query("2025-06-01"),
    timeframe: str = Query("day"),
    include_indicators: bool = Query(True),
    include_trendshift: bool = Query(True),
    limit: int = Query(120, ge=30, le=240),
):
    return await _get_chart_payload(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
        include_indicators=include_indicators,
        include_trendshift=include_trendshift,
        limit=limit,
    )


@api_router.get("/candles/{symbol}")
async def get_candle_data(symbol: str, start_date: str = "2024-06-01", end_date: str = "2025-06-01",
                          timeframe: str = "day", include_indicators: bool = True):
    """Get OHLCV candle data with optional indicator overlays."""
    return await _get_chart_payload(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
        include_indicators=include_indicators,
        include_trendshift=True,
        limit=180,
    )


# ==================== LIVE TICKS ====================
@api_router.get("/ticks/status")
async def get_tick_status():
    return live_tick_manager.get_status()

@api_router.post("/ticks/start")
async def start_ticks(tokens: List[int] = [256265]):
    settings_doc = await db.settings.find_one({}, {"_id": 0})
    api_key = (settings_doc or {}).get("kite_api_key", "")
    access_token = (settings_doc or {}).get("kite_access_token", "")
    if not api_key or not access_token:
        return {"status": "skipped", "reason": "Kite credentials not configured. Live ticks require API Key + Access Token."}
    live_tick_manager.start(api_key, access_token, tokens)
    return {"status": "started", "tokens": len(tokens)}

@api_router.post("/ticks/stop")
async def stop_ticks():
    live_tick_manager.stop()
    return {"status": "stopped"}


# ==================== ML SIGNALS ====================
@api_router.get("/ml/models")
async def list_ml_models():
    return ml_service.list_models()

@api_router.post("/ml/predict")
async def ml_predict(model_name: str = "sklearn_rf", symbol: str = "RELIANCE"):
    candles = await paper_broker.get_historical_data(symbol, "NSE", "day", "2024-01-01", "2025-06-01")
    if not candles or len(candles) < 30:
        raise HTTPException(400, "Insufficient data")
    signal = ml_service.generate_signal_from_candles(model_name, candles, symbol)
    if signal:
        return signal.model_dump()
    return {"status": "no_signal", "reason": "Model did not generate a signal (confidence too low or not trained)"}


# ==================== PORTFOLIO RISK ====================
@api_router.get("/portfolio/risk")
async def get_portfolio_risk():
    positions = await db.positions.find({}, {"_id": 0}).to_list(500)
    settings_doc = await db.settings.find_one({}, {"_id": 0})
    capital = (settings_doc or {}).get("capital", 100000)
    portfolio_risk_manager.capital = capital
    return portfolio_risk_manager.analyze_positions(positions)


# ==================== MULTI-SYMBOL BOT ====================
class MultiBotStartRequest(BaseModel):
    strategy_name: str = "trendshift"
    symbols: List[str] = Field(default_factory=lambda: ["RELIANCE", "INFY", "TCS", "HDFCBANK", "SBIN", "ITC"])
    mode: TradingMode = TradingMode.PAPER


@api_router.post("/bot/start-multi")
async def start_multi_symbol_bot(req: MultiBotStartRequest):
    """Start bot across multiple symbols simultaneously."""
    global bot_status, bot_run_id, bot_start_time
    if bot_status == BotStatus.RUNNING:
        raise HTTPException(400, "Bot is already running")
    if req.mode == TradingMode.LIVE:
        settings_doc = await _get_settings_doc()
        if not settings_doc.get("kite_api_key"):
            raise HTTPException(400, "Live trading requires Kite API credentials. Configure in Settings.")
    bot_run_id = gen_id()
    bot_start_time = datetime.now(timezone.utc)
    bot_status = BotStatus.RUNNING
    run_record = BotRunRecord(
        id=bot_run_id, mode=req.mode, strategy_name=req.strategy_name,
        status=BotStatus.RUNNING, started_at=now_utc()
    ).model_dump()
    await db.bot_runs.insert_one(run_record)
    # Generate signals for all symbols
    await _generate_demo_signals(req.strategy_name, req.symbols)
    # Send alert
    await _configure_alert_channels()
    await alert_manager.send_bot_status_alert("started", req.strategy_name, req.mode.value)
    return {"status": "started", "run_id": bot_run_id, "symbols": req.symbols, "strategy": req.strategy_name}


# ==================== BACKTEST ====================
class BacktestRequest(BaseModel):
    strategy_name: str = "sma_crossover"
    symbol: str = "RELIANCE"
    start_date: str = "2024-01-01"
    end_date: str = "2025-06-01"
    initial_capital: float = 100000.0
    quantity: int = 10
    timeframe: str = "day"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    execution_mode: str = "auto"

@api_router.post("/backtest/run")
async def run_backtest(req: BacktestRequest):
    try:
        candles = await paper_broker.get_historical_data(
            req.symbol, "NSE", req.timeframe, req.start_date, req.end_date
        )
        if not candles:
            raise HTTPException(400, "No candle data generated")

        estimated_candles = len(candles)
        should_queue = req.execution_mode == "queue" or (
            req.execution_mode == "auto" and (estimated_candles > 1500 or req.timeframe != "day")
        )
        if should_queue:
            job = await job_queue.enqueue(
                "backtest",
                req.model_dump(),
                meta={"symbol": req.symbol, "strategy_name": req.strategy_name, "estimated_candles": estimated_candles},
            )
            return JSONResponse(
                {
                    "status": "queued",
                    "job_id": job["id"],
                    "estimated_candles": estimated_candles,
                    "message": "Backtest queued for reliable processing",
                },
                status_code=202,
            )

        params = await _resolve_strategy_runtime_params(req.strategy_name, req.parameters)
        result_doc = await asyncio.to_thread(_run_backtest_sync, req, candles, params)
        await _store_backtest_result_doc(result_doc)
        return result_doc
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        raise HTTPException(500, str(e))


@api_router.get("/backtest/results")
async def get_backtest_results(limit: int = Query(20, le=50)):
    results = await db.backtest_results.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return results


@api_router.get("/backtest/results/{result_id}")
async def get_backtest_detail(result_id: str):
    result = await db.backtest_results.find_one({"id": result_id}, {"_id": 0})
    if not result:
        raise HTTPException(404, "Backtest result not found")
    return await _load_backtest_result_doc(result)


# ==================== OPTIMIZER ====================
class ParamRange(BaseModel):
    min: float
    max: float
    step: float

class OptimizerRequest(BaseModel):
    strategy_name: str = "sma_crossover"
    symbol: str = "RELIANCE"
    start_date: str = "2024-01-01"
    end_date: str = "2025-06-01"
    initial_capital: float = 100000.0
    quantity: int = 10
    timeframe: str = "day"
    param_ranges: Dict[str, Dict[str, float]] = Field(
        default_factory=lambda: {
            "fast_period": {"min": 5, "max": 20, "step": 1},
            "slow_period": {"min": 15, "max": 50, "step": 5},
        }
    )
    fixed_params: Dict[str, Any] = Field(default_factory=dict)
    objective: str = "balanced"
    execution_mode: str = "auto"

@api_router.post("/optimizer/run")
async def run_optimizer(req: OptimizerRequest):
    """Run backtest grid search across parameter ranges."""
    try:
        if req.strategy_name not in STRATEGY_REGISTRY:
            raise HTTPException(400, f"Unknown strategy: {req.strategy_name}")

        axes = _build_param_axes(req.param_ranges)
        total_combinations = _param_grid_size(axes)
        if total_combinations == 0:
            raise HTTPException(400, "No parameter combinations generated. Check ranges.")
        if total_combinations > 2000:
            raise HTTPException(400, f"Too many parameter combinations ({total_combinations}). Max is 2000. Narrow your ranges or increase step size.")

        candles = await paper_broker.get_historical_data(
            req.symbol, "NSE", req.timeframe, req.start_date, req.end_date
        )
        if not candles or len(candles) < 30:
            raise HTTPException(400, "Insufficient candle data for optimization")

        valid_combinations = sum(1 for combo in _iter_param_grid(axes) if _valid_combo(req.strategy_name, {**req.fixed_params, **combo}))
        if valid_combinations > 2000:
            raise HTTPException(400, f"Too many valid combinations ({valid_combinations}). Max is 2000. Narrow your ranges or increase step size.")

        should_queue = req.execution_mode == "queue" or (
            req.execution_mode == "auto" and (valid_combinations > 80 or len(candles) > 1200 or valid_combinations * len(candles) > 100000)
        )
        if should_queue:
            job = await job_queue.enqueue(
                "optimizer",
                req.model_dump(),
                meta={"symbol": req.symbol, "strategy_name": req.strategy_name, "total_combinations": valid_combinations, "objective": req.objective},
            )
            return JSONResponse(
                {
                    "status": "queued",
                    "job_id": job["id"],
                    "total_combinations": valid_combinations,
                    "message": "Optimizer queued for reliable processing",
                },
                status_code=202,
            )

        base_params = await _resolve_strategy_runtime_params(req.strategy_name, req.fixed_params)
        opt_result = await asyncio.to_thread(_run_optimizer_sync, req, candles, base_params, valid_combinations)
        await _store_optimizer_result_doc(opt_result)
        return opt_result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Optimizer failed: {e}")
        raise HTTPException(500, str(e))


@api_router.get("/optimizer/results")
async def get_optimizer_results(limit: int = Query(20, le=50)):
    results = await db.optimizer_results.find(
        {}, {"_id": 0, "results": 0}
    ).sort("created_at", -1).to_list(limit)
    return results


@api_router.get("/optimizer/results/{result_id}")
async def get_optimizer_detail(result_id: str):
    result = await db.optimizer_results.find_one({"id": result_id}, {"_id": 0})
    if not result:
        raise HTTPException(404, "Optimizer result not found")
    return await _load_optimizer_result_doc(result)


@api_router.post("/optimizer/results/{result_id}/apply-defaults")
async def apply_optimizer_result_defaults(result_id: str):
    result = await db.optimizer_results.find_one({"id": result_id}, {"_id": 0, "strategy_name": 1, "best_params": 1})
    if not result:
        raise HTTPException(404, "Optimizer result not found")
    if not result.get("best_params"):
        raise HTTPException(400, "Optimizer result does not contain best params")
    return await save_strategy_defaults(result["strategy_name"], {"parameters": result["best_params"]})


# ==================== SETTINGS ====================
@api_router.get("/settings")
async def get_settings():
    return await _get_settings_doc()


@api_router.put("/settings")
async def update_settings(settings: Dict[str, Any]):
    settings["updated_at"] = now_utc()
    await db.settings.update_one({}, {"$set": settings}, upsert=True)
    await _configure_alert_channels()
    return {"status": "updated"}


# ==================== INSTRUMENTS ====================
@api_router.get("/instruments")
async def get_instruments():
    instruments = await db.instruments.find({}, {"_id": 0}).to_list(500)
    if not instruments:
        for inst in DEFAULT_INSTRUMENTS:
            await db.instruments.insert_one(inst)
        instruments = await db.instruments.find({}, {"_id": 0}).to_list(500)
    return instruments


@api_router.post("/instruments/sync")
async def sync_instruments():
    """Sync instruments from broker or defaults."""
    broker_instruments = await paper_broker.get_instruments("NSE")
    count = 0
    for inst in broker_instruments:
        doc = inst.model_dump()
        await db.instruments.update_one(
            {"tradingsymbol": doc["tradingsymbol"], "exchange": doc["exchange"]},
            {"$set": doc}, upsert=True
        )
        count += 1
    return {"synced": count}


# ==================== METRICS ====================
@api_router.get("/metrics/equity-curve")
async def get_equity_curve(days: int = Query(30, le=365)):
    """Get equity curve from recent trades."""
    trades = await db.trades.find(
        {"status": TradeStatus.CLOSED}, {"_id": 0}
    ).sort("exit_time", 1).to_list(1000)

    settings_doc = await db.settings.find_one({}, {"_id": 0})
    capital = (settings_doc or {}).get("capital", 100000)
    equity = capital
    curve = [{"timestamp": now_utc(), "equity": capital, "pnl": 0}]

    for t in trades:
        equity += t.get("net_pnl", 0)
        curve.append({
            "timestamp": t.get("exit_time", ""),
            "equity": round(equity, 2),
            "pnl": round(equity - capital, 2),
        })
    return curve


@api_router.get("/metrics/daily-pnl")
async def get_daily_pnl():
    """Aggregate PnL by day."""
    pipeline = [
        {"$match": {"status": TradeStatus.CLOSED}},
        {"$addFields": {"date": {"$substr": ["$exit_time", 0, 10]}}},
        {"$group": {
            "_id": "$date",
            "pnl": {"$sum": "$net_pnl"},
            "trades": {"$sum": 1},
            "wins": {"$sum": {"$cond": [{"$gt": ["$net_pnl", 0]}, 1, 0]}},
        }},
        {"$sort": {"_id": 1}},
        {"$project": {
            "_id": 0, "date": "$_id", "pnl": {"$round": ["$pnl", 2]},
            "trades": 1, "win_rate": {
                "$cond": [{"$gt": ["$trades", 0]},
                          {"$round": [{"$multiply": [{"$divide": ["$wins", "$trades"]}, 100]}, 2]}, 0]
            },
        }}
    ]
    result = await db.trades.aggregate(pipeline).to_list(365)
    return result


# ==================== BOT RUNS ====================
@api_router.get("/bot/runs")
async def get_bot_runs(limit: int = Query(20, le=50)):
    runs = await db.bot_runs.find({}, {"_id": 0}).sort("started_at", -1).to_list(limit)
    return runs


# ==================== HEALTH ====================
@api_router.get("/health")
async def healthcheck():
    try:
        await db.command("ping")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    return {
        "status": "healthy",
        "database": db_status,
        "bot_status": bot_status,
        "market_open": is_market_open(),
        "timestamp": now_utc(),
    }


# ==================== INIT ====================
@api_router.post("/init")
async def initialize_database():
    """Initialize default configs in the database."""
    # Settings
    existing = await db.settings.find_one({})
    if not existing:
        await db.settings.insert_one(AppSettings().model_dump())

    # Risk config
    existing = await db.risk_config.find_one({})
    if not existing:
        await db.risk_config.insert_one(RiskConfig().model_dump())

    # Strategy configs
    for strat_info in list_strategies():
        existing = await db.strategy_configs.find_one({"name": strat_info["name"]})
        if not existing:
            config = StrategyConfig(
                name=strat_info["name"],
                display_name=strat_info["display_name"],
                description=strat_info["description"],
                parameters=strat_info["default_params"],
            ).model_dump()
            await db.strategy_configs.insert_one(config)

    # Instruments
    count = await db.instruments.count_documents({})
    if count == 0:
        for inst in DEFAULT_INSTRUMENTS:
            await db.instruments.insert_one(inst)

    return {"status": "initialized"}


# Include router and middleware
app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    try:
        await db.command("ping")
        logger.info("MongoDB connected")
        job_queue.register_processor("backtest", _process_backtest_job)
        job_queue.register_processor("optimizer", _process_optimizer_job)
        await job_queue.start()
        # Auto-init if empty
        count = await db.settings.count_documents({})
        if count == 0:
            await db.settings.insert_one(AppSettings().model_dump())
            await db.risk_config.insert_one(RiskConfig().model_dump())
            for inst in DEFAULT_INSTRUMENTS:
                await db.instruments.insert_one(inst)
            for strat_info in list_strategies():
                config = StrategyConfig(
                    name=strat_info["name"],
                    display_name=strat_info["display_name"],
                    description=strat_info["description"],
                    parameters=strat_info["default_params"],
                ).model_dump()
                await db.strategy_configs.insert_one(config)
            logger.info("Database initialized with defaults")
    except Exception as e:
        logger.error(f"Startup error: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    await job_queue.shutdown()
    client.close()
