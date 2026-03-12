"""
Technical Indicators Library for KiteAlgo.
Pure-Python implementations — no numpy/pandas required for core calcs.
"""
import math
from typing import List, Dict, Any, Optional, Tuple


def ema(data: List[float], period: int) -> List[float]:
    """Exponential Moving Average."""
    if not data or period < 1:
        return []
    result = [0.0] * len(data)
    k = 2.0 / (period + 1)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = data[i] * k + result[i - 1] * (1 - k)
    return result


def sma(data: List[float], period: int) -> List[float]:
    """Simple Moving Average."""
    if not data or period < 1:
        return []
    result = [0.0] * len(data)
    for i in range(len(data)):
        start = max(0, i - period + 1)
        window = data[start:i + 1]
        result[i] = sum(window) / len(window)
    return result


def rsi(closes: List[float], period: int = 14) -> List[float]:
    """Relative Strength Index using Wilder's smoothing."""
    if len(closes) < period + 1:
        return [50.0] * len(closes)
    result = [50.0] * len(closes)
    gains = []
    losses = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    if len(gains) < period:
        return result
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        idx = i + 1  # offset for result
        if avg_loss == 0:
            result[idx] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[idx] = 100.0 - (100.0 / (1.0 + rs))
        if i < len(gains):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    return result


def macd(closes: List[float], fast: int = 12, slow: int = 26, signal_period: int = 9) -> Dict[str, List[float]]:
    """MACD: line, signal, histogram."""
    fast_ema = ema(closes, fast)
    slow_ema = ema(closes, slow)
    macd_line = [f - s for f, s in zip(fast_ema, slow_ema)]
    signal_line = ema(macd_line, signal_period)
    histogram = [m - s for m, s in zip(macd_line, signal_line)]
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    """Average True Range."""
    if len(highs) < 2:
        return [0.0] * len(highs)
    tr = [highs[0] - lows[0]]
    for i in range(1, len(highs)):
        tr.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        ))
    return ema(tr, period)


def supertrend(highs: List[float], lows: List[float], closes: List[float],
               period: int = 10, multiplier: float = 3.0) -> Dict[str, List[Any]]:
    """Supertrend indicator. Returns trend direction (+1 bull, -1 bear) and line values."""
    n = len(closes)
    atr_vals = atr(highs, lows, closes, period)
    upper_band = [0.0] * n
    lower_band = [0.0] * n
    supertrend_line = [0.0] * n
    direction = [1] * n  # +1 = bullish, -1 = bearish

    for i in range(n):
        mid = (highs[i] + lows[i]) / 2
        upper_band[i] = mid + multiplier * atr_vals[i]
        lower_band[i] = mid - multiplier * atr_vals[i]

    for i in range(1, n):
        # Carry forward bands
        if lower_band[i] > lower_band[i - 1] or closes[i - 1] < lower_band[i - 1]:
            pass
        else:
            lower_band[i] = lower_band[i - 1]
        if upper_band[i] < upper_band[i - 1] or closes[i - 1] > upper_band[i - 1]:
            pass
        else:
            upper_band[i] = upper_band[i - 1]

        # Determine direction
        if direction[i - 1] == 1:
            if closes[i] < lower_band[i]:
                direction[i] = -1
            else:
                direction[i] = 1
        else:
            if closes[i] > upper_band[i]:
                direction[i] = 1
            else:
                direction[i] = -1

        supertrend_line[i] = lower_band[i] if direction[i] == 1 else upper_band[i]

    return {"line": supertrend_line, "direction": direction, "upper": upper_band, "lower": lower_band}


def bollinger_bands(closes: List[float], period: int = 20, std_mult: float = 2.0) -> Dict[str, List[float]]:
    """Bollinger Bands: middle, upper, lower."""
    middle = sma(closes, period)
    upper = [0.0] * len(closes)
    lower = [0.0] * len(closes)
    for i in range(len(closes)):
        start = max(0, i - period + 1)
        window = closes[start:i + 1]
        if len(window) >= 2:
            mean = sum(window) / len(window)
            variance = sum((x - mean) ** 2 for x in window) / len(window)
            std = math.sqrt(variance)
            upper[i] = middle[i] + std_mult * std
            lower[i] = middle[i] - std_mult * std
        else:
            upper[i] = middle[i]
            lower[i] = middle[i]
    return {"middle": middle, "upper": upper, "lower": lower}


def volume_profile(volumes: List[float], period: int = 20) -> Dict[str, List[float]]:
    """Volume analysis: moving average and relative volume."""
    vol_ma = sma(volumes, period)
    relative = [0.0] * len(volumes)
    for i in range(len(volumes)):
        if vol_ma[i] > 0:
            relative[i] = round(volumes[i] / vol_ma[i], 2)
    return {"ma": vol_ma, "relative": relative}


def swing_highs_lows(highs: List[float], lows: List[float], lookback: int = 5) -> Dict[str, List[Optional[float]]]:
    """Detect swing high and swing low points."""
    n = len(highs)
    swing_high = [None] * n
    swing_low = [None] * n
    for i in range(lookback, n - lookback):
        is_high = all(highs[i] >= highs[i - j] and highs[i] >= highs[i + j] for j in range(1, lookback + 1))
        is_low = all(lows[i] <= lows[i - j] and lows[i] <= lows[i + j] for j in range(1, lookback + 1))
        if is_high:
            swing_high[i] = highs[i]
        if is_low:
            swing_low[i] = lows[i]
    return {"highs": swing_high, "lows": swing_low}


def demand_supply_zones(
    highs: List[float], lows: List[float], closes: List[float],
    atr_vals: List[float], lookback: int = 5
) -> Dict[str, List[Dict[str, float]]]:
    """Identify demand (buy) and supply (sell) zones based on swing points + ATR."""
    swings = swing_highs_lows(highs, lows, lookback)
    demand_zones = []
    supply_zones = []
    for i in range(len(highs)):
        if swings["lows"][i] is not None:
            zone_width = atr_vals[i] * 0.5 if i < len(atr_vals) else 0
            demand_zones.append({
                "index": i, "low": round(swings["lows"][i] - zone_width, 2),
                "high": round(swings["lows"][i] + zone_width * 0.3, 2),
                "center": swings["lows"][i],
            })
        if swings["highs"][i] is not None:
            zone_width = atr_vals[i] * 0.5 if i < len(atr_vals) else 0
            supply_zones.append({
                "index": i, "low": round(swings["highs"][i] - zone_width * 0.3, 2),
                "high": round(swings["highs"][i] + zone_width, 2),
                "center": swings["highs"][i],
            })
    return {"demand": demand_zones, "supply": supply_zones}


def compute_all_indicators(candles: List[Dict[str, Any]], params: Optional[Dict] = None) -> Dict[str, Any]:
    """Compute all indicators for a candle series. Used by candlestick chart endpoint."""
    p = params or {}
    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    volumes = [c.get("volume", 0) for c in candles]

    ema8 = ema(closes, p.get("ema_fast", 8))
    ema21 = ema(closes, p.get("ema_mid", 21))
    ema55 = ema(closes, p.get("ema_slow", 55))
    rsi_vals = rsi(closes, p.get("rsi_period", 14))
    macd_data = macd(closes, p.get("macd_fast", 12), p.get("macd_slow", 26), p.get("macd_signal", 9))
    atr_vals = atr(highs, lows, closes, p.get("atr_period", 10))
    st = supertrend(highs, lows, closes, p.get("st_period", 10), p.get("st_mult", 3.0))
    bb = bollinger_bands(closes, p.get("bb_period", 20), p.get("bb_std", 2.0))
    vol = volume_profile(volumes, p.get("vol_period", 20))
    zones = demand_supply_zones(highs, lows, closes, atr_vals, p.get("swing_lookback", 5))

    return {
        "ema8": ema8, "ema21": ema21, "ema55": ema55,
        "rsi": rsi_vals,
        "macd_line": macd_data["macd"], "macd_signal": macd_data["signal"], "macd_histogram": macd_data["histogram"],
        "atr": atr_vals,
        "supertrend_line": st["line"], "supertrend_direction": st["direction"],
        "bb_upper": bb["upper"], "bb_middle": bb["middle"], "bb_lower": bb["lower"],
        "volume_relative": vol["relative"],
        "demand_zones": zones["demand"], "supply_zones": zones["supply"],
    }
