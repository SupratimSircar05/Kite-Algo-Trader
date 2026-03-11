import os
from datetime import datetime, time
import pytz

IST = pytz.timezone("Asia/Kolkata")

# Default instruments for strategies
DEFAULT_INSTRUMENTS = [
    {"tradingsymbol": "RELIANCE", "exchange": "NSE", "instrument_token": 738561, "name": "Reliance Industries", "lot_size": 1, "tick_size": 0.05},
    {"tradingsymbol": "INFY", "exchange": "NSE", "instrument_token": 408065, "name": "Infosys", "lot_size": 1, "tick_size": 0.05},
    {"tradingsymbol": "TCS", "exchange": "NSE", "instrument_token": 2953217, "name": "Tata Consultancy", "lot_size": 1, "tick_size": 0.05},
    {"tradingsymbol": "HDFCBANK", "exchange": "NSE", "instrument_token": 341249, "name": "HDFC Bank", "lot_size": 1, "tick_size": 0.05},
    {"tradingsymbol": "NIFTY 50", "exchange": "NSE", "instrument_token": 256265, "name": "Nifty 50 Index", "lot_size": 50, "tick_size": 0.05},
    {"tradingsymbol": "BANKNIFTY", "exchange": "NSE", "instrument_token": 260105, "name": "Bank Nifty Index", "lot_size": 25, "tick_size": 0.05},
    {"tradingsymbol": "SBIN", "exchange": "NSE", "instrument_token": 779521, "name": "State Bank of India", "lot_size": 1, "tick_size": 0.05},
    {"tradingsymbol": "ITC", "exchange": "NSE", "instrument_token": 424961, "name": "ITC Limited", "lot_size": 1, "tick_size": 0.05},
]

# Market hours (IST)
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)
PRE_OPEN_START = time(9, 0)
PRE_OPEN_END = time(9, 8)

# Trading fees (approximate for NSE equity intraday)
BROKERAGE_PER_ORDER = 20.0  # Zerodha flat fee
STT_RATE = 0.00025  # 0.025% on sell side
TRANSACTION_CHARGES_RATE = 0.0000345
GST_RATE = 0.18
SEBI_CHARGES_RATE = 0.000001
STAMP_DUTY_RATE = 0.00003

# Default strategy parameters
DEFAULT_SMA_PARAMS = {
    "fast_period": 9,
    "slow_period": 21,
    "signal_threshold": 0.0,
    "volume_filter": False,
    "min_volume_multiplier": 1.5,
}

DEFAULT_BREAKOUT_PARAMS = {
    "opening_range_minutes": 15,
    "breakout_buffer_pct": 0.1,
    "volume_confirmation": True,
    "min_range_pct": 0.3,
    "max_range_pct": 2.0,
}

# Slippage simulation
DEFAULT_SLIPPAGE_BPS = 5  # 5 basis points


def is_market_open() -> bool:
    now_ist = datetime.now(IST)
    current_time = now_ist.time()
    weekday = now_ist.weekday()
    if weekday >= 5:  # Saturday/Sunday
        return False
    return MARKET_OPEN <= current_time <= MARKET_CLOSE


def get_ist_now() -> datetime:
    return datetime.now(IST)


def calculate_fees(turnover: float, side: str = "BUY") -> float:
    brokerage = BROKERAGE_PER_ORDER
    stt = turnover * STT_RATE if side == "SELL" else 0
    txn = turnover * TRANSACTION_CHARGES_RATE
    gst = (brokerage + txn) * GST_RATE
    sebi = turnover * SEBI_CHARGES_RATE
    stamp = turnover * STAMP_DUTY_RATE if side == "BUY" else 0
    return round(brokerage + stt + txn + gst + sebi + stamp, 2)
