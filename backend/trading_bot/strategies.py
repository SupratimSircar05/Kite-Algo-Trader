import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from .models import Signal, gen_id, now_utc
from .enums import Side, SignalStatus
from .config import DEFAULT_SMA_PARAMS, DEFAULT_BREAKOUT_PARAMS

logger = logging.getLogger("strategies")


class StrategyBase(ABC):
    """Base class for all trading strategies."""

    name: str = "base"
    display_name: str = "Base Strategy"
    description: str = ""
    default_params: Dict[str, Any] = {}

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        self.params = {**self.default_params, **(params or {})}
        self._warmup_complete = False
        self._candle_buffer: List[Dict[str, Any]] = []
        self._warmup_period = 0

    @abstractmethod
    def on_candle(self, candle: Dict[str, Any]) -> Optional[Signal]:
        """Process a new candle. Return a Signal if conditions met, else None."""
        ...

    def warmup(self, candles: List[Dict[str, Any]]):
        """Feed historical candles for indicator warmup."""
        for c in candles:
            self._candle_buffer.append(c)
        if len(self._candle_buffer) >= self._warmup_period:
            self._warmup_complete = True
        logger.info(f"{self.name}: warmed up with {len(candles)} candles (buffer={len(self._candle_buffer)})")

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Signal]:
        """Process a live tick. Override if needed. Default: no-op."""
        return None

    def parameters(self) -> Dict[str, Any]:
        return self.params.copy()

    def reset(self):
        self._candle_buffer.clear()
        self._warmup_complete = False


class SMACrossoverStrategy(StrategyBase):
    """
    Simple Moving Average Crossover Strategy.
    Generates BUY when fast SMA crosses above slow SMA.
    Generates SELL when fast SMA crosses below slow SMA.
    """

    name = "sma_crossover"
    display_name = "SMA Crossover"
    description = "Buy when fast SMA crosses above slow SMA, sell on cross below."
    default_params = DEFAULT_SMA_PARAMS

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        super().__init__(params)
        self._warmup_period = self.params["slow_period"] + 2
        self._last_signal_side: Optional[str] = None

    def _calc_sma(self, period: int) -> Optional[float]:
        if len(self._candle_buffer) < period:
            return None
        closes = [c["close"] for c in self._candle_buffer[-period:]]
        return sum(closes) / period

    def on_candle(self, candle: Dict[str, Any]) -> Optional[Signal]:
        self._candle_buffer.append(candle)
        if len(self._candle_buffer) > self._warmup_period + 50:
            self._candle_buffer = self._candle_buffer[-(self._warmup_period + 50):]

        fast = self.params["fast_period"]
        slow = self.params["slow_period"]

        if len(self._candle_buffer) < slow + 2:
            return None

        fast_sma_now = self._calc_sma(fast)
        slow_sma_now = self._calc_sma(slow)

        prev_buffer = self._candle_buffer[:-1]
        fast_prev = sum(c["close"] for c in prev_buffer[-fast:]) / fast
        slow_prev = sum(c["close"] for c in prev_buffer[-slow:]) / slow

        if fast_sma_now is None or slow_sma_now is None:
            return None

        # Volume filter
        if self.params.get("volume_filter") and candle.get("volume"):
            avg_vol = sum(c.get("volume", 0) for c in self._candle_buffer[-20:]) / 20
            if candle["volume"] < avg_vol * self.params.get("min_volume_multiplier", 1.5):
                return None

        signal = None
        # Bullish crossover
        if fast_prev <= slow_prev and fast_sma_now > slow_sma_now:
            if self._last_signal_side != Side.BUY:
                close = candle["close"]
                signal = Signal(
                    symbol=candle.get("symbol", ""),
                    exchange=candle.get("exchange", "NSE"),
                    side=Side.BUY,
                    confidence=min(0.5 + abs(fast_sma_now - slow_sma_now) / slow_sma_now * 10, 0.95),
                    reason=f"Fast SMA({fast})={fast_sma_now:.2f} crossed above Slow SMA({slow})={slow_sma_now:.2f}",
                    timestamp=candle.get("timestamp", now_utc()),
                    stop_loss=round(close * 0.98, 2),
                    take_profit=round(close * 1.04, 2),
                    strategy_name=self.name,
                    price=close,
                )
                self._last_signal_side = Side.BUY

        # Bearish crossover
        elif fast_prev >= slow_prev and fast_sma_now < slow_sma_now:
            if self._last_signal_side != Side.SELL:
                close = candle["close"]
                signal = Signal(
                    symbol=candle.get("symbol", ""),
                    exchange=candle.get("exchange", "NSE"),
                    side=Side.SELL,
                    confidence=min(0.5 + abs(fast_sma_now - slow_sma_now) / slow_sma_now * 10, 0.95),
                    reason=f"Fast SMA({fast})={fast_sma_now:.2f} crossed below Slow SMA({slow})={slow_sma_now:.2f}",
                    timestamp=candle.get("timestamp", now_utc()),
                    stop_loss=round(close * 1.02, 2),
                    take_profit=round(close * 0.96, 2),
                    strategy_name=self.name,
                    price=close,
                )
                self._last_signal_side = Side.SELL

        return signal


class BreakoutStrategy(StrategyBase):
    """
    Opening Range Breakout Strategy.
    Defines a range in the first N minutes of market open.
    BUY on breakout above range high, SELL on breakdown below range low.
    """

    name = "opening_range_breakout"
    display_name = "Opening Range Breakout"
    description = "Trade breakouts from the opening range (first N minutes of market)."
    default_params = DEFAULT_BREAKOUT_PARAMS

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        super().__init__(params)
        self._warmup_period = 5
        self._range_high: Optional[float] = None
        self._range_low: Optional[float] = None
        self._range_set = False
        self._range_candle_count = 0
        self._signal_given_today = False

    def reset_daily(self):
        """Reset for new trading day."""
        self._range_high = None
        self._range_low = None
        self._range_set = False
        self._range_candle_count = 0
        self._signal_given_today = False

    def on_candle(self, candle: Dict[str, Any]) -> Optional[Signal]:
        self._candle_buffer.append(candle)
        if len(self._candle_buffer) > 200:
            self._candle_buffer = self._candle_buffer[-200:]

        range_minutes = self.params.get("opening_range_minutes", 15)
        buffer_pct = self.params.get("breakout_buffer_pct", 0.1) / 100

        # Build opening range
        if not self._range_set:
            self._range_candle_count += 1
            if self._range_high is None:
                self._range_high = candle["high"]
                self._range_low = candle["low"]
            else:
                self._range_high = max(self._range_high, candle["high"])
                self._range_low = min(self._range_low, candle["low"])

            # Assume 1-minute candles, so range_minutes candles = opening range
            if self._range_candle_count >= range_minutes:
                self._range_set = True
                range_pct = ((self._range_high - self._range_low) / self._range_low) * 100 if self._range_low > 0 else 0
                min_range = self.params.get("min_range_pct", 0.3)
                max_range = self.params.get("max_range_pct", 2.0)
                if range_pct < min_range or range_pct > max_range:
                    logger.info(f"ORB: Range {range_pct:.2f}% outside bounds [{min_range}, {max_range}]. Skipping.")
                    self._signal_given_today = True  # Prevent signals
                else:
                    logger.info(f"ORB: Range set H={self._range_high} L={self._range_low} ({range_pct:.2f}%)")
            return None

        if self._signal_given_today:
            return None

        close = candle["close"]
        breakout_level = self._range_high * (1 + buffer_pct)
        breakdown_level = self._range_low * (1 - buffer_pct)

        signal = None
        if close > breakout_level:
            signal = Signal(
                symbol=candle.get("symbol", ""),
                exchange=candle.get("exchange", "NSE"),
                side=Side.BUY,
                confidence=0.65,
                reason=f"Breakout above ORB high {self._range_high:.2f} (close={close:.2f})",
                timestamp=candle.get("timestamp", now_utc()),
                stop_loss=round(self._range_low, 2),
                take_profit=round(close + (close - self._range_low), 2),
                strategy_name=self.name,
                price=close,
            )
            self._signal_given_today = True

        elif close < breakdown_level:
            signal = Signal(
                symbol=candle.get("symbol", ""),
                exchange=candle.get("exchange", "NSE"),
                side=Side.SELL,
                confidence=0.65,
                reason=f"Breakdown below ORB low {self._range_low:.2f} (close={close:.2f})",
                timestamp=candle.get("timestamp", now_utc()),
                stop_loss=round(self._range_high, 2),
                take_profit=round(close - (self._range_high - close), 2),
                strategy_name=self.name,
                price=close,
            )
            self._signal_given_today = True

        return signal


# Strategy registry
STRATEGY_REGISTRY: Dict[str, type] = {
    "sma_crossover": SMACrossoverStrategy,
    "opening_range_breakout": BreakoutStrategy,
}


def get_strategy(name: str, params: Optional[Dict[str, Any]] = None) -> StrategyBase:
    """Get a strategy instance by name."""
    cls = STRATEGY_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown strategy: {name}. Available: {list(STRATEGY_REGISTRY.keys())}")
    return cls(params=params)


def list_strategies() -> List[Dict[str, Any]]:
    """List all available strategies with metadata."""
    result = []
    for name, cls in STRATEGY_REGISTRY.items():
        instance = cls()
        result.append({
            "name": cls.name,
            "display_name": cls.display_name,
            "description": cls.description,
            "default_params": cls.default_params,
            "current_params": instance.parameters(),
        })
    return result
