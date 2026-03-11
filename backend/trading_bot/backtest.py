import logging
import math
from typing import List, Dict, Any, Optional
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
    ):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.slippage_bps = slippage_bps
        self.quantity = quantity
        self._capital = initial_capital
        self._position: Optional[Dict[str, Any]] = None
        self._trades: List[Dict[str, Any]] = []
        self._equity_curve: List[Dict[str, Any]] = []
        self._peak_equity = initial_capital
        self._max_drawdown = 0.0

    def _apply_slippage(self, price: float, side: str) -> float:
        slip = price * (self.slippage_bps / 10000)
        return round(price + slip if side == "BUY" else price - slip, 2)

    def run(self, candles: List[Dict[str, Any]], symbol: str = "", exchange: str = "NSE") -> BacktestResult:
        """Run backtest on a list of OHLCV candles."""
        logger.info(f"Starting backtest: {self.strategy.name} on {symbol} ({len(candles)} candles)")

        self.strategy.reset()
        self._capital = self.initial_capital
        self._position = None
        self._trades.clear()
        self._equity_curve.clear()
        self._peak_equity = self.initial_capital
        self._max_drawdown = 0.0

        # Warmup
        warmup_size = getattr(self.strategy, '_warmup_period', 30)
        if len(candles) > warmup_size:
            self.strategy.warmup(candles[:warmup_size])
            process_candles = candles[warmup_size:]
        else:
            process_candles = candles

        for candle in process_candles:
            candle["symbol"] = symbol
            candle["exchange"] = exchange
            signal = self.strategy.on_candle(candle)

            if signal:
                self._process_signal(signal, candle)

            # Update equity
            equity = self._capital
            if self._position:
                unrealized = (candle["close"] - self._position["entry_price"]) * self._position["quantity"]
                if self._position["side"] == "SELL":
                    unrealized = -unrealized
                equity += unrealized

            self._equity_curve.append({
                "timestamp": candle.get("timestamp", ""),
                "equity": round(equity, 2),
                "pnl": round(equity - self.initial_capital, 2),
            })

            if equity > self._peak_equity:
                self._peak_equity = equity
            dd = (self._peak_equity - equity) / self._peak_equity * 100 if self._peak_equity > 0 else 0
            if dd > self._max_drawdown:
                self._max_drawdown = dd

        # Close any open position at end
        if self._position and process_candles:
            last_candle = process_candles[-1]
            self._close_position(last_candle["close"], last_candle.get("timestamp", ""), "end_of_backtest")

        return self._compute_results(symbol, exchange, candles)

    def _process_signal(self, signal, candle: Dict[str, Any]):
        """Process a strategy signal during backtest."""
        # Close existing position if opposite signal
        if self._position:
            if self._position["side"] != signal.side:
                self._close_position(candle["close"], candle.get("timestamp", ""), "signal_reversal")
            else:
                return  # Already in same direction

        # Open new position
        fill_price = self._apply_slippage(candle["close"], signal.side)
        fees = calculate_fees(fill_price * self.quantity, signal.side)
        self._capital -= fees

        self._position = {
            "side": signal.side,
            "entry_price": fill_price,
            "quantity": self.quantity,
            "entry_time": candle.get("timestamp", ""),
            "signal_reason": signal.reason,
            "entry_fees": fees,
        }

    def _close_position(self, price: float, timestamp: str, reason: str):
        """Close current position."""
        if not self._position:
            return

        fill_price = self._apply_slippage(price, "SELL" if self._position["side"] == "BUY" else "BUY")
        exit_fees = calculate_fees(fill_price * self._position["quantity"], "SELL")

        if self._position["side"] == "BUY":
            pnl = (fill_price - self._position["entry_price"]) * self._position["quantity"]
        else:
            pnl = (self._position["entry_price"] - fill_price) * self._position["quantity"]

        net_pnl = pnl - self._position["entry_fees"] - exit_fees
        self._capital += net_pnl

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
        })
        self._position = None

    def _compute_results(self, symbol: str, exchange: str, candles: List[Dict[str, Any]]) -> BacktestResult:
        """Compute all backtest metrics."""
        trades = self._trades
        total_trades = len(trades)
        wins = [t for t in trades if t["net_pnl"] > 0]
        losses = [t for t in trades if t["net_pnl"] <= 0]

        total_return = self._capital - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100 if self.initial_capital > 0 else 0

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

        # Win/loss averages
        avg_win = sum(t["net_pnl"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["net_pnl"] for t in losses) / len(losses) if losses else 0
        win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0

        # Profit factor
        gross_profit = sum(t["net_pnl"] for t in wins) if wins else 0
        gross_loss = abs(sum(t["net_pnl"] for t in losses)) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Sharpe-like ratio (simplified)
        sharpe = 0.0
        if len(self._equity_curve) > 1:
            returns = []
            for i in range(1, len(self._equity_curve)):
                prev_eq = self._equity_curve[i - 1]["equity"]
                curr_eq = self._equity_curve[i]["equity"]
                if prev_eq > 0:
                    returns.append((curr_eq - prev_eq) / prev_eq)
            if returns:
                mean_ret = sum(returns) / len(returns)
                std_ret = (sum((r - mean_ret) ** 2 for r in returns) / len(returns)) ** 0.5
                if std_ret > 0:
                    sharpe = round((mean_ret / std_ret) * math.sqrt(252), 2)

        # Expectancy
        expectancy = total_return / total_trades if total_trades > 0 else 0

        # Average trade duration
        avg_duration = 0.0
        for t in trades:
            try:
                entry = datetime.fromisoformat(t["entry_time"].replace("Z", "+00:00"))
                exit_ = datetime.fromisoformat(t["exit_time"].replace("Z", "+00:00"))
                avg_duration += (exit_ - entry).total_seconds()
            except (ValueError, TypeError):
                pass
        avg_duration = avg_duration / total_trades if total_trades > 0 else 0

        # Subsample equity curve for large datasets
        eq_curve = self._equity_curve
        if len(eq_curve) > 500:
            step = len(eq_curve) // 500
            eq_curve = eq_curve[::step]

        start_date = candles[0].get("timestamp", "") if candles else ""
        end_date = candles[-1].get("timestamp", "") if candles else ""

        return BacktestResult(
            strategy_name=self.strategy.name,
            symbol=symbol,
            exchange=exchange,
            timeframe="day",
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
            winning_trades=len(wins),
            losing_trades=len(losses),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            profit_factor=round(profit_factor, 2),
            sharpe_ratio=sharpe,
            expectancy=round(expectancy, 2),
            avg_trade_duration=round(avg_duration, 2),
            equity_curve=eq_curve,
            trades=trades,
            parameters=self.strategy.parameters(),
        )
