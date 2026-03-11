from fastapi import FastAPI, APIRouter, HTTPException, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
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
bot_status = BotStatus.IDLE
bot_run_id: Optional[str] = None
bot_start_time: Optional[datetime] = None


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
            warmup_size = getattr(strategy, '_warmup_period', 20)
            if len(candles) > warmup_size:
                strategy.warmup(candles[:warmup_size])
                for candle in candles[warmup_size:]:
                    candle["symbol"] = symbol
                    candle["exchange"] = "NSE"
                    signal = strategy.on_candle(candle)
                    if signal:
                        sig_doc = signal.model_dump()
                        await db.signals.insert_one(sig_doc)

                        # Execute through paper broker
                        result = await order_manager.execute_signal(signal)
                        if result.get("success"):
                            order_doc = result["order"]
                            await db.orders.insert_one(order_doc)

                            fill_price = order_doc.get("filled_price") or signal.price or candle["close"]
                            if fill_price is None:
                                fill_price = candle["close"]
                            trade = trade_engine.open_trade(
                                Order(**order_doc), fill_price, strategy_name
                            )
                            # Close trade with small profit/loss for demo
                            import random
                            exit_mult = 1 + random.uniform(-0.02, 0.03)
                            exit_price = round(fill_price * exit_mult, 2)
                            closed = trade_engine.close_trade(trade.id, exit_price)
                            if closed:
                                await db.trades.insert_one(closed.model_dump())
                                # Create position record
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
    return {"kill_switch_active": active, "reason": reason if active else None}


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

@api_router.post("/backtest/run")
async def run_backtest(req: BacktestRequest):
    try:
        params = req.parameters or None
        strategy = get_strategy(req.strategy_name, params)
        candles = await paper_broker.get_historical_data(
            req.symbol, "NSE", req.timeframe, req.start_date, req.end_date
        )
        if not candles:
            raise HTTPException(400, "No candle data generated")

        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=req.initial_capital,
            quantity=req.quantity,
        )
        result = engine.run(candles, symbol=req.symbol, exchange="NSE")
        result_doc = result.model_dump()
        await db.backtest_results.insert_one(result_doc.copy())
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
    return result


# ==================== SETTINGS ====================
@api_router.get("/settings")
async def get_settings():
    doc = await db.settings.find_one({}, {"_id": 0})
    if not doc:
        default = AppSettings()
        doc = default.model_dump()
        await db.settings.insert_one(doc)
    return doc


@api_router.put("/settings")
async def update_settings(settings: Dict[str, Any]):
    settings["updated_at"] = now_utc()
    await db.settings.update_one({}, {"$set": settings}, upsert=True)
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
    client.close()
