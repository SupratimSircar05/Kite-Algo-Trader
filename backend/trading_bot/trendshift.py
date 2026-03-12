"""Advanced TrendShift strategy with cached indicators and ML regime filter."""
import logging
from typing import Any, Dict, List, Optional

from .enums import Side
from .indicators import compute_all_indicators
from .ml_signals import ml_service
from .models import Signal, now_utc
from .strategies import StrategyBase

logger = logging.getLogger("trendshift")

DEFAULT_TRENDSHIFT_PARAMS = {
    "ema_fast": 8,
    "ema_mid": 21,
    "ema_slow": 55,
    "rsi_period": 14,
    "rsi_ob": 72,
    "rsi_os": 28,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "atr_period": 14,
    "supertrend_period": 10,
    "supertrend_mult": 2.6,
    "volume_spike_mult": 1.15,
    "min_volume_relative": 0.95,
    "swing_lookback": 5,
    "min_confidence": 0.62,
    "signal_edge": 0.06,
    "sl_atr_mult": 1.25,
    "tp_atr_mult": 2.8,
    "min_reward_risk": 1.8,
    "signal_cooldown": 5,
    "pullback_atr_tolerance": 0.55,
    "zone_tolerance_atr": 0.35,
    "zone_memory_bars": 60,
    "min_ribbon_spread": 0.0035,
    "min_atr_pct": 0.18,
    "max_atr_pct": 5.5,
    "max_gap_pct": 1.1,
    "trend_filter": True,
    "volume_filter": True,
    "zone_filter": True,
    "use_ml_filter": True,
    "ml_horizon": 5,
    "ml_min_confidence": 0.57,
    "ml_weight": 0.16,
}


class TrendShiftStrategy(StrategyBase):
    name = "trendshift"
    display_name = "TrendShift"
    description = "Adaptive trend-shift strategy with zone confluence, slippage-aware filters, and ML regime confirmation."
    default_params = DEFAULT_TRENDSHIFT_PARAMS

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        super().__init__(params)
        self._warmup_period = max(
            int(self.params["ema_slow"]),
            int(self.params["macd_slow"] + self.params["macd_signal"]),
            int(self.params["supertrend_period"] * 2),
        ) + 10

    def _zone_state(self, index: int, price: float, atr_value: float, zones: List[Dict[str, float]]) -> tuple[bool, Optional[Dict[str, float]]]:
        tolerance = atr_value * self.params["zone_tolerance_atr"]
        recent_limit = int(self.params["zone_memory_bars"])
        for zone in reversed(zones):
            zone_index = zone.get("index", 0)
            if index - zone_index > recent_limit:
                continue
            if zone["low"] - tolerance <= price <= zone["high"] + tolerance:
                return True, zone
        return False, None

    def _expected_slippage_bps(self, atr_pct: float, volume_relative: float, gap_pct: float) -> float:
        base = 5.0
        score = base
        score += max(0.0, atr_pct - 1.4) * 2.2
        score += max(0.0, 1.0 - volume_relative) * 7.5
        score += max(0.0, gap_pct - 0.3) * 8.0
        return round(min(max(score, 2.0), 35.0), 2)

    def _build_signal(
        self,
        candle: Dict[str, Any],
        side: Side,
        confidence: float,
        reasons: List[str],
        current_price: float,
        stop_loss: float,
        take_profit: float,
        metadata: Dict[str, Any],
    ) -> Signal:
        return Signal(
            symbol=candle.get("symbol", ""),
            exchange=candle.get("exchange", "NSE"),
            side=side,
            confidence=min(confidence, 0.99),
            reason=" | ".join(reasons),
            timestamp=candle.get("timestamp", now_utc()),
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            strategy_name=self.name,
            price=current_price,
            metadata=metadata,
        )

    def batch_generate_signals(
        self,
        candles: List[Dict[str, Any]],
        symbol: str = "",
        exchange: str = "NSE",
    ) -> Dict[int, Signal]:
        if len(candles) < self._warmup_period:
            return {}

        p = self.params
        for candle in candles:
            candle.setdefault("symbol", symbol)
            candle.setdefault("exchange", exchange)

        indicators = compute_all_indicators(candles, {
            **p,
            "st_period": p["supertrend_period"],
            "st_mult": p["supertrend_mult"],
        })
        ml_predictions = (
            ml_service.get_market_direction_predictions(candles, symbol or candles[-1].get("symbol", ""), int(p["ml_horizon"]))
            if p.get("use_ml_filter") else
            [{"side": None, "confidence": 0.0}] * len(candles)
        )

        closes = [c["close"] for c in candles]
        opens = [c.get("open", c["close"]) for c in candles]
        ema_fast = indicators["ema8"]
        ema_mid = indicators["ema21"]
        ema_slow = indicators["ema55"]
        rsi_vals = indicators["rsi"]
        macd_hist = indicators["macd_histogram"]
        atr_vals = indicators["atr"]
        trend_dir = indicators["supertrend_direction"]
        volume_relative = indicators["volume_relative"]
        bb_upper = indicators["bb_upper"]
        bb_lower = indicators["bb_lower"]
        demand_zones = indicators["demand_zones"]
        supply_zones = indicators["supply_zones"]

        signal_map: Dict[int, Signal] = {}
        last_signal_side: Optional[Side] = None
        cooldown = 0

        for i in range(self._warmup_period, len(candles)):
            if cooldown > 0:
                cooldown -= 1
                continue

            current_price = closes[i]
            if current_price <= 0:
                continue

            atr_now = max(atr_vals[i], current_price * 0.001)
            atr_pct = atr_now / current_price * 100
            prev_close = closes[i - 1] if i > 0 else current_price
            gap_pct = abs(opens[i] - prev_close) / prev_close * 100 if prev_close else 0
            if gap_pct > p["max_gap_pct"] or not (p["min_atr_pct"] <= atr_pct <= p["max_atr_pct"]):
                continue

            current_trend = trend_dir[i]
            prev_trend = trend_dir[i - 1]
            trend_shifted = current_trend != prev_trend
            ema_bullish = ema_fast[i] > ema_mid[i] > ema_slow[i]
            ema_bearish = ema_fast[i] < ema_mid[i] < ema_slow[i]
            ribbon_spread = abs(ema_fast[i] - ema_slow[i]) / current_price
            if ribbon_spread < p["min_ribbon_spread"]:
                continue

            rsi_now = rsi_vals[i]
            rsi_prev = rsi_vals[i - 1]
            macd_now = macd_hist[i]
            macd_prev = macd_hist[i - 1]
            volume_now = volume_relative[i]
            ml_now = ml_predictions[i]
            bb_width = (bb_upper[i] - bb_lower[i]) / current_price * 100 if current_price else 0

            in_demand_zone, demand_zone = self._zone_state(i, current_price, atr_now, demand_zones)
            in_supply_zone, supply_zone = self._zone_state(i, current_price, atr_now, supply_zones)
            buy_pullback = current_price <= ema_fast[i] + atr_now * p["pullback_atr_tolerance"] and current_price >= ema_mid[i] - atr_now * p["pullback_atr_tolerance"]
            sell_pullback = current_price >= ema_fast[i] - atr_now * p["pullback_atr_tolerance"] and current_price <= ema_mid[i] + atr_now * p["pullback_atr_tolerance"]

            buy_score = 0.0
            sell_score = 0.0
            buy_reasons: List[str] = []
            sell_reasons: List[str] = []

            if trend_shifted and current_trend == 1:
                buy_score += 0.20
                buy_reasons.append("Supertrend flipped bullish")
            elif trend_shifted and current_trend == -1:
                sell_score += 0.20
                sell_reasons.append("Supertrend flipped bearish")

            if ema_bullish:
                buy_score += 0.14
                buy_reasons.append("EMA ribbon aligned bullish")
            if ema_bearish:
                sell_score += 0.14
                sell_reasons.append("EMA ribbon aligned bearish")

            if rsi_now > 52 and rsi_now >= rsi_prev and rsi_now < p["rsi_ob"]:
                buy_score += 0.10
                buy_reasons.append(f"RSI strengthening ({rsi_now:.1f})")
            if rsi_now < 48 and rsi_now <= rsi_prev and rsi_now > p["rsi_os"]:
                sell_score += 0.10
                sell_reasons.append(f"RSI weakening ({rsi_now:.1f})")

            if macd_now > 0 and macd_now >= macd_prev:
                buy_score += 0.10
                buy_reasons.append("MACD histogram expanding positive")
            if macd_now < 0 and macd_now <= macd_prev:
                sell_score += 0.10
                sell_reasons.append("MACD histogram expanding negative")

            if volume_now >= p["min_volume_relative"]:
                buy_score += 0.07
                sell_score += 0.07
                if volume_now >= p["volume_spike_mult"]:
                    buy_reasons.append(f"Relative volume spike ({volume_now:.2f}x)")
                    sell_reasons.append(f"Relative volume spike ({volume_now:.2f}x)")

            if in_demand_zone:
                buy_score += 0.10
                buy_reasons.append("Price reclaimed demand zone")
            if in_supply_zone:
                sell_score += 0.10
                sell_reasons.append("Price tapped supply zone")

            if buy_pullback:
                buy_score += 0.08
                buy_reasons.append("Controlled pullback near fast EMA")
            if sell_pullback:
                sell_score += 0.08
                sell_reasons.append("Controlled pullback near fast EMA")

            if bb_width >= atr_pct * 0.8:
                if current_trend == 1:
                    buy_score += 0.05
                else:
                    sell_score += 0.05

            ml_side = ml_now.get("side")
            ml_conf = ml_now.get("confidence", 0.0)
            if p.get("use_ml_filter") and ml_conf >= p["ml_min_confidence"]:
                if ml_side == Side.BUY:
                    buy_score += p["ml_weight"]
                    buy_reasons.append(f"ML regime confirms BUY ({ml_conf:.2f})")
                    sell_score -= p["ml_weight"] * 0.55
                elif ml_side == Side.SELL:
                    sell_score += p["ml_weight"]
                    sell_reasons.append(f"ML regime confirms SELL ({ml_conf:.2f})")
                    buy_score -= p["ml_weight"] * 0.55

            expected_slippage_bps = self._expected_slippage_bps(atr_pct, volume_now, gap_pct)
            if expected_slippage_bps <= 8:
                buy_score += 0.04
                sell_score += 0.04

            min_conf = p["min_confidence"]
            score_edge = p["signal_edge"]

            if buy_score >= min_conf and buy_score >= sell_score + score_edge and last_signal_side != Side.BUY:
                zone_floor = demand_zone["low"] if demand_zone else current_price - atr_now * p["sl_atr_mult"]
                stop_loss = min(current_price - atr_now * p["sl_atr_mult"], zone_floor)
                risk = max(current_price - stop_loss, atr_now * 0.8)
                take_profit = current_price + max(risk * p["min_reward_risk"], atr_now * p["tp_atr_mult"])
                metadata = {
                    "supertrend_dir": current_trend,
                    "rsi": round(rsi_now, 2),
                    "macd_hist": round(macd_now, 4),
                    "volume_relative": round(volume_now, 2),
                    "in_demand_zone": in_demand_zone,
                    "trend_shifted": trend_shifted,
                    "atr": round(atr_now, 2),
                    "atr_pct": round(atr_pct, 3),
                    "bb_width_pct": round(bb_width, 3),
                    "ml_confidence": round(ml_conf, 3),
                    "expected_slippage_bps": expected_slippage_bps,
                    "gap_pct": round(gap_pct, 3),
                    "ribbon_spread": round(ribbon_spread, 5),
                }
                signal_map[i] = self._build_signal(candles[i], Side.BUY, buy_score, buy_reasons, current_price, stop_loss, take_profit, metadata)
                last_signal_side = Side.BUY
                cooldown = int(p["signal_cooldown"])
                continue

            if sell_score >= min_conf and sell_score >= buy_score + score_edge and last_signal_side != Side.SELL:
                zone_ceiling = supply_zone["high"] if supply_zone else current_price + atr_now * p["sl_atr_mult"]
                stop_loss = max(current_price + atr_now * p["sl_atr_mult"], zone_ceiling)
                risk = max(stop_loss - current_price, atr_now * 0.8)
                take_profit = current_price - max(risk * p["min_reward_risk"], atr_now * p["tp_atr_mult"])
                metadata = {
                    "supertrend_dir": current_trend,
                    "rsi": round(rsi_now, 2),
                    "macd_hist": round(macd_now, 4),
                    "volume_relative": round(volume_now, 2),
                    "in_supply_zone": in_supply_zone,
                    "trend_shifted": trend_shifted,
                    "atr": round(atr_now, 2),
                    "atr_pct": round(atr_pct, 3),
                    "bb_width_pct": round(bb_width, 3),
                    "ml_confidence": round(ml_conf, 3),
                    "expected_slippage_bps": expected_slippage_bps,
                    "gap_pct": round(gap_pct, 3),
                    "ribbon_spread": round(ribbon_spread, 5),
                }
                signal_map[i] = self._build_signal(candles[i], Side.SELL, sell_score, sell_reasons, current_price, stop_loss, take_profit, metadata)
                last_signal_side = Side.SELL
                cooldown = int(p["signal_cooldown"])

        return signal_map

    def on_candle(self, candle: Dict[str, Any]) -> Optional[Signal]:
        self._candle_buffer.append(candle)
        buf_max = self._warmup_period + 220
        if len(self._candle_buffer) > buf_max:
            self._candle_buffer = self._candle_buffer[-buf_max:]
        signal_map = self.batch_generate_signals(
            self._candle_buffer,
            symbol=candle.get("symbol", ""),
            exchange=candle.get("exchange", "NSE"),
        )
        return signal_map.get(len(self._candle_buffer) - 1)
