import logging
import math
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime

from .models import BacktestResult, gen_id, now_utc
from .strategies import StrategyBase, get_strategy
from .config import calculate_fees, DEFAULT_SLIPPAGE_BPS

logger = logging.getLogger("backtest")


class BacktestEngine:
    """
    Simple but correct backtesting engine.
    Processes candles sequentially, applies strategy signals,
    simulates fills with slippage and fees, tracks equity curve.
    """

    def __init__(
        self,
        strategy: StrategyBase,
        initial_capital: float = 100000.0,
        slippage_bps: int = DEFAULT_SLIPPAGE_BPS,
        quantity: int = 1,
        progress_callback: Optional[Callable[[float, str, Optional[Dict[str, Any]]], None]] = None,
        lightweight: bool = False,
    ):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.slippage_bps = slippage_bps
        self.quantity = quantity
        self.progress_callback = progress_callback
        self.lightweight = lightweight
        self._capital = initial_capital
        self._position: Optional[Dict[str, Any]] = None
        self._trades: List[Dict[str, Any]] = []
        self._trade_count = 0
        self._win_count = 0
        self._loss_count = 0
        self._gross_profit = 0.0
        self._gross_loss = 0.0
        self._total_net_pnl = 0.0
        self._equity_curve: List[Dict[str, Any]] = []
        self._returns_for_sharpe: List[float] = []
        self._prev_equity = initial_capital
        self._peak_equity = initial_capital
        self._max_drawdown = 0.0
        self._slippage_cost_total = 0.0
        self._slippage_bps_total = 0.0
        self._slippage_events = 0
        self._last_progress_bucket = -1
        self._total_duration_seconds = 0.0

    def _apply_slippage(self, price: float, side: str, slippage_bps: Optional[float] = None) -> float:
        effective_bps = slippage_bps if slippage_bps is not None else self.slippage_bps
        slip = price * (effective_bps / 10000)
        return round(price + slip if side == "BUY" else price - slip, 2)

    def _report_progress(self, processed: int, total: int, message: str = "Running backtest"):
        if not self.progress_callback or total <= 0:
            return
        pct = round((processed / total) * 100, 2)
        bucket = int(pct)
        if bucket <= self._last_progress_bucket and processed < total:
            return
        self._last_progress_bucket = bucket
        self.progress_callback(pct, message, {"processed_items": processed, "total_items": total})

    def _estimate_slippage_bps(self, candle: Dict[str, Any], signal: Optional[Any] = None) -> float:
        metadata = getattr(signal, "metadata", {}) if signal is not None else {}
        price = candle.get("close", 0) or 0
        atr_value = metadata.get("atr", 0)
        atr_pct = metadata.get("atr_pct") or ((atr_value / price * 100) if price and atr_value else 0)
        volume_relative = metadata.get("volume_relative", 1.0)
        prev_close = self._equity_curve[-1]["close"] if self._equity_curve and "close" in self._equity_curve[-1] else None
        gap_pct = 0.0
        if prev_close:
            gap_pct = abs(candle.get("open", price) - prev_close) / prev_close * 100
        expected = metadata.get("expected_slippage_bps")
        if expected is not None:
            return float(expected)
        score = float(self.slippage_bps)
        score += max(0.0, atr_pct - 1.5) * 2.0
        score += max(0.0, 1.0 - volume_relative) * 7.0
        score += max(0.0, gap_pct - 0.25) * 8.0
        return round(min(max(score, 2.0), 35.0), 2)

    def run(self, candles: List[Dict[str, Any]], symbol: str = "", exchange: str = "NSE", timeframe: str = "day") -> BacktestResult:
        """Run backtest on a list of OHLCV candles."""
        if not self.lightweight:
            logger.info(f"Starting backtest: {self.strategy.name} on {symbol} ({len(candles)} candles)")

        self.strategy.reset()
        self._capital = self.initial_capital
        self._position = None
        self._trades.clear()
        self._equity_curve.clear()
        self._trade_count = 0
        self._win_count = 0
        self._loss_count = 0
        self._gross_profit = 0.0
        self._gross_loss = 0.0
        self._total_net_pnl = 0.0
        self._returns_for_sharpe.clear()
        self._prev_equity = self.initial_capital
        self._peak_equity = self.initial_capital
        self._max_drawdown = 0.0
        self._slippage_cost_total = 0.0
        self._slippage_bps_total = 0.0
        self._slippage_events = 0
        self._last_progress_bucket = -1
        self._total_duration_seconds = 0.0

        # Warmup
        warmup_size = getattr(self.strategy, '_warmup_period', 30)
        if len(candles) > warmup_size:
            self.strategy.warmup(candles[:warmup_size])
            process_candles = candles[warmup_size:]
        else:
            process_candles = candles

        signal_map = None
        batch_generator = getattr(self.strategy, "batch_generate_signals", None)
        if callable(batch_generator):
            signal_map = batch_generator(candles, symbol=symbol, exchange=exchange)

        total_process = max(len(process_candles), 1)
        for idx, candle in enumerate(process_candles, start=warmup_size):
            candle["symbol"] = symbol
            candle["exchange"] = exchange

            if self._position and self._process_position_exits(candle):
                if not self.lightweight:
                    equity = self._capital
                    self._equity_curve.append({
                        "timestamp": candle.get("timestamp", ""),
                        "equity": round(equity, 2),
                        "pnl": round(equity - self.initial_capital, 2),
                        "close": candle.get("close", 0),
                    })
                self._report_progress(idx - warmup_size + 1, total_process)
                continue

            signal = signal_map.get(idx) if signal_map is not None else self.strategy.on_candle(candle)

            if signal:
                self._process_signal(signal, candle)

            # Update equity
            equity = self._capital
            if self._position:
                unrealized = (candle["close"] - self._position["entry_price"]) * self._position["quantity"]
                if self._position["side"] == "SELL":
                    unrealized = -unrealized
                equity += unrealized

            # Track Sharpe returns (always needed for metrics)
            if self._prev_equity > 0:
                self._returns_for_sharpe.append((equity - self._prev_equity) / self._prev_equity)
            self._prev_equity = equity

            if not self.lightweight:
                self._equity_curve.append({
                    "timestamp": candle.get("timestamp", ""),
                    "equity": round(equity, 2),
                    "pnl": round(equity - self.initial_capital, 2),
                    "close": candle.get("close", 0),
                })

            if equity > self._peak_equity:
                self._peak_equity = equity
            dd = (self._peak_equity - equity) / self._peak_equity * 100 if self._peak_equity > 0 else 0
            if dd > self._max_drawdown:
                self._max_drawdown = dd
            self._report_progress(idx - warmup_size + 1, total_process)

        # Close any open position at end
        if self._position and process_candles:
            last_candle = process_candles[-1]
            self._close_position(last_candle["close"], last_candle.get("timestamp", ""), "end_of_backtest")

        if not self.lightweight:
            self._report_progress(total_process, total_process, "Backtest completed")
        return self._compute_results(symbol, exchange, candles, timeframe)

    def _process_signal(self, signal, candle: Dict[str, Any]):
        """Process a strategy signal during backtest."""
        # Close existing position if opposite signal
        if self._position:
            if self._position["side"] != signal.side:
                self._close_position(candle["close"], candle.get("timestamp", ""), "signal_reversal")
            else:
                return  # Already in same direction

        # Open new position
        signal_slippage_bps = self._estimate_slippage_bps(candle, signal)
        fill_price = self._apply_slippage(candle["close"], signal.side, signal_slippage_bps)
        fees = calculate_fees(fill_price * self.quantity, signal.side)
        self._capital -= fees
        self._slippage_cost_total += abs(fill_price - candle["close"]) * self.quantity
        self._slippage_bps_total += signal_slippage_bps
        self._slippage_events += 1

        self._position = {
            "side": signal.side,
            "entry_price": fill_price,
            "quantity": self.quantity,
            "entry_time": candle.get("timestamp", ""),
            "signal_reason": signal.reason,
            "entry_fees": fees,
            "entry_reference_price": candle["close"],
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "signal_metadata": getattr(signal, "metadata", {}) or {},
            "entry_slippage_bps": signal_slippage_bps,
        }

    def _process_position_exits(self, candle: Dict[str, Any]) -> bool:
        if not self._position:
            return False
        stop_loss = self._position.get("stop_loss")
        take_profit = self._position.get("take_profit")
        side = self._position["side"]
        low = candle.get("low", candle.get("close", 0))
        high = candle.get("high", candle.get("close", 0))

        if side == "BUY":
            if stop_loss is not None and low <= stop_loss:
                self._close_position(stop_loss, candle.get("timestamp", ""), "stop_loss")
                return True
            if take_profit is not None and high >= take_profit:
                self._close_position(take_profit, candle.get("timestamp", ""), "take_profit")
                return True
        else:
            if stop_loss is not None and high >= stop_loss:
                self._close_position(stop_loss, candle.get("timestamp", ""), "stop_loss")
                return True
            if take_profit is not None and low <= take_profit:
                self._close_position(take_profit, candle.get("timestamp", ""), "take_profit")
                return True
        return False

    def _close_position(self, price: float, timestamp: str, reason: str):
        """Close current position."""
        if not self._position:
            return

        exit_side = "SELL" if self._position["side"] == "BUY" else "BUY"
        exit_slippage_bps = self._estimate_slippage_bps(
            {"close": price, "open": price, "high": price, "low": price},
            type("SigMeta", (), {"metadata": self._position.get("signal_metadata", {})})(),
        )
        fill_price = self._apply_slippage(price, exit_side, exit_slippage_bps)
        exit_fees = calculate_fees(fill_price * self._position["quantity"], "SELL")
        self._slippage_cost_total += abs(fill_price - price) * self._position["quantity"]
        self._slippage_bps_total += exit_slippage_bps
        self._slippage_events += 1

        if self._position["side"] == "BUY":
            pnl = (fill_price - self._position["entry_price"]) * self._position["quantity"]
        else:
            pnl = (self._position["entry_price"] - fill_price) * self._position["quantity"]

        net_pnl = pnl - self._position["entry_fees"] - exit_fees
        self._capital += net_pnl

        # Track lightweight metrics
        self._trade_count += 1
        self._total_net_pnl += net_pnl
        if net_pnl > 0:
            self._win_count += 1
            self._gross_profit += net_pnl
        else:
            self._loss_count += 1
            self._gross_loss += abs(net_pnl)

        # Track duration
        try:
            entry_dt = datetime.fromisoformat(self._position["entry_time"].replace("Z", "+00:00"))
            exit_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            self._total_duration_seconds += (exit_dt - entry_dt).total_seconds()
        except (ValueError, TypeError):
            pass

        if not self.lightweight:
            self._trades.append({
                "side": self._position["side"],
                "entry_price": self._position["entry_price"],
                "exit_price": fill_price,
                "quantity": self._position["quantity"],
                "pnl": round(pnl, 2),
                "net_pnl": round(net_pnl, 2),
                "fees": round(self._position["entry_fees"] + exit_fees, 2),
                "entry_time": self._position["entry_time"],
                "exit_time": timestamp,
                "reason": reason,
                "entry_slippage_bps": round(self._position.get("entry_slippage_bps", 0), 2),
                "exit_slippage_bps": round(exit_slippage_bps, 2),
                "avg_slippage_bps": round((self._position.get("entry_slippage_bps", 0) + exit_slippage_bps) / 2, 2),
                "stop_loss": self._position.get("stop_loss"),
                "take_profit": self._position.get("take_profit"),
            })
        self._position = None

    def _compute_results(self, symbol: str, exchange: str, candles: List[Dict[str, Any]], timeframe: str) -> BacktestResult:
        """Compute all backtest metrics."""
        total_trades = self._trade_count
        total_return = self._capital - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100 if self.initial_capital > 0 else 0

        win_rate = (self._win_count / total_trades * 100) if total_trades > 0 else 0
        avg_win = (self._gross_profit / self._win_count) if self._win_count > 0 else 0
        avg_loss = -(self._gross_loss / self._loss_count) if self._loss_count > 0 else 0
        profit_factor = self._gross_profit / self._gross_loss if self._gross_loss > 0 else 0
        expectancy = total_return / total_trades if total_trades > 0 else 0
        avg_duration = self._total_duration_seconds / total_trades if total_trades > 0 else 0

        # CAGR
        cagr = 0.0
        if candles and len(candles) > 1:
            try:
                start_str = candles[0].get("timestamp", "")
                end_str = candles[-1].get("timestamp", "")
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00")) if start_str else None
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00")) if end_str else None
                if start_dt and end_dt:
                    years = (end_dt - start_dt).days / 365.25
                    if years > 0 and self._capital > 0:
                        cagr = (pow(self._capital / self.initial_capital, 1 / years) - 1) * 100
            except (ValueError, TypeError):
                pass

        # Sharpe ratio from tracked returns
        sharpe = 0.0
        returns = self._returns_for_sharpe
        if len(returns) > 1:
            mean_ret = sum(returns) / len(returns)
            std_ret = (sum((r - mean_ret) ** 2 for r in returns) / len(returns)) ** 0.5
            if std_ret > 0:
                sharpe = round((mean_ret / std_ret) * math.sqrt(252), 2)

        # Subsample equity curve for large datasets
        eq_curve = self._equity_curve
        if len(eq_curve) > 500:
            step = len(eq_curve) // 500
            eq_curve = eq_curve[::step]

        avg_slippage_bps = self._slippage_bps_total / self._slippage_events if self._slippage_events else 0

        start_date = candles[0].get("timestamp", "") if candles else ""
        end_date = candles[-1].get("timestamp", "") if candles else ""

        return BacktestResult(
            strategy_name=self.strategy.name,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=round(self._capital, 2),
            total_return=round(total_return, 2),
            total_return_pct=round(total_return_pct, 2),
            cagr=round(cagr, 2),
            max_drawdown=round(self._max_drawdown * self._peak_equity / 100, 2) if self._peak_equity > 0 else 0,
            max_drawdown_pct=round(self._max_drawdown, 2),
            win_rate=round(win_rate, 2),
            total_trades=total_trades,
            winning_trades=self._win_count,
            losing_trades=self._loss_count,
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            profit_factor=round(profit_factor, 2),
            sharpe_ratio=sharpe,
            expectancy=round(expectancy, 2),
            avg_trade_duration=round(avg_duration, 2),
            avg_slippage_bps=round(avg_slippage_bps, 2),
            slippage_cost_total=round(self._slippage_cost_total, 2),
            equity_curve=eq_curve,
            trades=self._trades,
            parameters=self.strategy.parameters(),
        )
