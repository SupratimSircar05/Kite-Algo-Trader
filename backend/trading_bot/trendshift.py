"""
TrendShift Proprietary Strategy
================================
Combines 5 indicator systems for high-confidence trend shift detection:
1. Supertrend + EMA Ribbon for trend direction
2. RSI + MACD for momentum confirmation
3. Volume spikes for institutional activity
4. Demand/Supply zones for optimal entries
5. Multi-factor confidence scoring

Works on any market (equity, F&O, forex, crypto) and any timeframe.
"""
import logging
from typing import List, Dict, Any, Optional

from .strategies import StrategyBase
from .models import Signal, now_utc
from .enums import Side
from .indicators import (
    ema, rsi, macd, atr, supertrend, bollinger_bands,
    volume_profile, demand_supply_zones, swing_highs_lows
)

logger = logging.getLogger("trendshift")

DEFAULT_TRENDSHIFT_PARAMS = {
    "ema_fast": 8,
    "ema_mid": 21,
    "ema_slow": 55,
    "rsi_period": 14,
    "rsi_ob": 70,
    "rsi_os": 30,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "atr_period": 10,
    "supertrend_period": 10,
    "supertrend_mult": 3.0,
    "volume_spike_mult": 1.5,
    "swing_lookback": 5,
    "zone_atr_mult": 0.5,
    "min_confidence": 0.4,
    "sl_atr_mult": 1.5,
    "tp_atr_mult": 3.0,
    "trend_filter": True,
    "volume_filter": True,
    "zone_filter": True,
}


class TrendShiftStrategy(StrategyBase):
    """
    TrendShift: Detects the exact moment a trend changes direction.

    Signal logic:
    - BUY when Supertrend flips bullish + EMA ribbon aligns +
      RSI momentum confirms + MACD histogram turns positive +
      price enters demand zone + volume confirms
    - SELL when Supertrend flips bearish + EMA ribbon inverts +
      RSI momentum confirms + MACD histogram turns negative +
      price enters supply zone + volume confirms

    Each confirmation factor adds to a confidence score (0-1).
    Only signals above min_confidence threshold are emitted.
    """

    name = "trendshift"
    display_name = "TrendShift"
    description = "Proprietary multi-factor trend shift detector with buy/sell zones. Works on any market and timeframe."
    default_params = DEFAULT_TRENDSHIFT_PARAMS

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        super().__init__(params)
        self._warmup_period = max(
            self.params["ema_slow"],
            self.params["macd_slow"] + self.params["macd_signal"],
            self.params["supertrend_period"] * 2,
        ) + 10
        self._prev_trend = 0  # 0 = unknown, 1 = bullish, -1 = bearish
        self._last_signal_side = None
        self._signal_cooldown = 0

    def on_candle(self, candle: Dict[str, Any]) -> Optional[Signal]:
        self._candle_buffer.append(candle)
        buf_max = self._warmup_period + 200
        if len(self._candle_buffer) > buf_max:
            self._candle_buffer = self._candle_buffer[-buf_max:]

        if len(self._candle_buffer) < self._warmup_period:
            return None

        # Cooldown between signals
        if self._signal_cooldown > 0:
            self._signal_cooldown -= 1
            return None

        p = self.params
        closes = [c["close"] for c in self._candle_buffer]
        highs = [c["high"] for c in self._candle_buffer]
        lows = [c["low"] for c in self._candle_buffer]
        volumes = [c.get("volume", 1) for c in self._candle_buffer]

        # === 1. TREND DETECTION (Supertrend + EMA Ribbon) ===
        st = supertrend(highs, lows, closes, p["supertrend_period"], p["supertrend_mult"])
        ema_fast = ema(closes, p["ema_fast"])
        ema_mid = ema(closes, p["ema_mid"])
        ema_slow = ema(closes, p["ema_slow"])

        curr_st_dir = st["direction"][-1]
        prev_st_dir = st["direction"][-2] if len(st["direction"]) > 1 else curr_st_dir

        # Detect trend shift
        trend_shifted = curr_st_dir != prev_st_dir
        ema_bullish = ema_fast[-1] > ema_mid[-1] > ema_slow[-1]
        ema_bearish = ema_fast[-1] < ema_mid[-1] < ema_slow[-1]

        # Current trend
        current_trend = 1 if curr_st_dir == 1 else -1

        # === 2. MOMENTUM (RSI + MACD) ===
        rsi_vals = rsi(closes, p["rsi_period"])
        macd_data = macd(closes, p["macd_fast"], p["macd_slow"], p["macd_signal"])

        curr_rsi = rsi_vals[-1]
        prev_rsi = rsi_vals[-2] if len(rsi_vals) > 1 else curr_rsi
        rsi_bullish = curr_rsi > 50 and prev_rsi <= 50  # Crossing above 50
        rsi_bearish = curr_rsi < 50 and prev_rsi >= 50  # Crossing below 50
        rsi_confirms_buy = curr_rsi > 40 and curr_rsi < p["rsi_ob"]
        rsi_confirms_sell = curr_rsi < 60 and curr_rsi > p["rsi_os"]

        curr_hist = macd_data["histogram"][-1]
        prev_hist = macd_data["histogram"][-2] if len(macd_data["histogram"]) > 1 else curr_hist
        macd_bullish = curr_hist > 0 and prev_hist <= 0  # Histogram turning positive
        macd_bearish = curr_hist < 0 and prev_hist >= 0  # Histogram turning negative
        macd_confirms_buy = curr_hist > prev_hist  # Histogram rising
        macd_confirms_sell = curr_hist < prev_hist  # Histogram falling

        # === 3. VOLUME CONFIRMATION ===
        vol_data = volume_profile(volumes, 20)
        vol_relative = vol_data["relative"][-1] if vol_data["relative"] else 1.0
        volume_spike = vol_relative >= p["volume_spike_mult"]

        # === 4. BUY/SELL ZONES ===
        atr_vals = [st["line"][i] for i in range(len(closes))]  # Use supertrend's internal ATR
        atr_current = 0
        atr_list = []
        for i in range(len(closes)):
            if i == 0:
                atr_list.append(highs[0] - lows[0])
            else:
                tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
                atr_list.append(tr)
        # Simple ATR
        if len(atr_list) >= p["atr_period"]:
            atr_current = sum(atr_list[-p["atr_period"]:]) / p["atr_period"]

        zones = demand_supply_zones(highs, lows, closes, ema(atr_list, p["atr_period"]), p["swing_lookback"])
        current_price = closes[-1]

        in_demand_zone = False
        in_supply_zone = False
        for zone in zones["demand"][-5:]:  # Check last 5 demand zones
            if zone["low"] <= current_price <= zone["high"] * 1.02:
                in_demand_zone = True
                break
        for zone in zones["supply"][-5:]:  # Check last 5 supply zones
            if zone["low"] * 0.98 <= current_price <= zone["high"]:
                in_supply_zone = True
                break

        # === 5. SIGNAL GENERATION WITH CONFIDENCE SCORING ===
        buy_score = 0.0
        sell_score = 0.0
        buy_reasons = []
        sell_reasons = []

        # Trend shift (strongest signal)
        if trend_shifted and current_trend == 1:
            buy_score += 0.30
            buy_reasons.append("Supertrend flipped BULLISH")
        elif trend_shifted and current_trend == -1:
            sell_score += 0.30
            sell_reasons.append("Supertrend flipped BEARISH")

        # Trend alignment (even without shift)
        if current_trend == 1 and not trend_shifted:
            buy_score += 0.10
        elif current_trend == -1 and not trend_shifted:
            sell_score += 0.10

        # EMA ribbon
        if p["trend_filter"]:
            if ema_bullish:
                buy_score += 0.15
                buy_reasons.append(f"EMA ribbon aligned bullish ({p['ema_fast']}/{p['ema_mid']}/{p['ema_slow']})")
            elif ema_bearish:
                sell_score += 0.15
                sell_reasons.append(f"EMA ribbon aligned bearish ({p['ema_fast']}/{p['ema_mid']}/{p['ema_slow']})")

        # RSI momentum
        if rsi_bullish or rsi_confirms_buy:
            buy_score += 0.15
            buy_reasons.append(f"RSI momentum bullish ({curr_rsi:.1f})")
        if rsi_bearish or rsi_confirms_sell:
            sell_score += 0.15
            sell_reasons.append(f"RSI momentum bearish ({curr_rsi:.1f})")

        # MACD
        if macd_bullish or macd_confirms_buy:
            buy_score += 0.15
            buy_reasons.append("MACD histogram turning positive")
        if macd_bearish or macd_confirms_sell:
            sell_score += 0.15
            sell_reasons.append("MACD histogram turning negative")

        # Volume
        if p["volume_filter"] and volume_spike:
            buy_score += 0.10
            sell_score += 0.10
            if buy_score > sell_score:
                buy_reasons.append(f"Volume spike ({vol_relative:.1f}x avg)")
            else:
                sell_reasons.append(f"Volume spike ({vol_relative:.1f}x avg)")

        # Zones
        if p["zone_filter"]:
            if in_demand_zone:
                buy_score += 0.15
                buy_reasons.append("Price in DEMAND zone (institutional buying)")
            if in_supply_zone:
                sell_score += 0.15
                sell_reasons.append("Price in SUPPLY zone (institutional selling)")

        # Determine signal
        min_conf = p["min_confidence"]
        signal = None

        if buy_score >= min_conf and buy_score > sell_score and self._last_signal_side != Side.BUY:
            sl = round(current_price - atr_current * p["sl_atr_mult"], 2)
            tp = round(current_price + atr_current * p["tp_atr_mult"], 2)
            signal = Signal(
                symbol=candle.get("symbol", ""),
                exchange=candle.get("exchange", "NSE"),
                side=Side.BUY,
                confidence=min(buy_score, 0.99),
                reason=" | ".join(buy_reasons),
                timestamp=candle.get("timestamp", now_utc()),
                stop_loss=sl,
                take_profit=tp,
                strategy_name=self.name,
                price=current_price,
                metadata={
                    "supertrend_dir": current_trend,
                    "rsi": round(curr_rsi, 2),
                    "macd_hist": round(curr_hist, 4),
                    "volume_relative": round(vol_relative, 2),
                    "in_demand_zone": in_demand_zone,
                    "trend_shifted": trend_shifted,
                    "atr": round(atr_current, 2),
                },
            )
            self._last_signal_side = Side.BUY
            self._signal_cooldown = 3
            self._prev_trend = current_trend

        elif sell_score >= min_conf and sell_score > buy_score and self._last_signal_side != Side.SELL:
            sl = round(current_price + atr_current * p["sl_atr_mult"], 2)
            tp = round(current_price - atr_current * p["tp_atr_mult"], 2)
            signal = Signal(
                symbol=candle.get("symbol", ""),
                exchange=candle.get("exchange", "NSE"),
                side=Side.SELL,
                confidence=min(sell_score, 0.99),
                reason=" | ".join(sell_reasons),
                timestamp=candle.get("timestamp", now_utc()),
                stop_loss=sl,
                take_profit=tp,
                strategy_name=self.name,
                price=current_price,
                metadata={
                    "supertrend_dir": current_trend,
                    "rsi": round(curr_rsi, 2),
                    "macd_hist": round(curr_hist, 4),
                    "volume_relative": round(vol_relative, 2),
                    "in_supply_zone": in_supply_zone,
                    "trend_shifted": trend_shifted,
                    "atr": round(atr_current, 2),
                },
            )
            self._last_signal_side = Side.SELL
            self._signal_cooldown = 3
            self._prev_trend = current_trend

        return signal
