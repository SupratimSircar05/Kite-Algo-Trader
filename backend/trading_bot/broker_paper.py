import random
import logging
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from .broker_base import BrokerBase
from .models import Order, Position, Instrument, gen_id, now_utc
from .enums import OrderStatus, Side, OrderType, PositionStatus
from .config import DEFAULT_SLIPPAGE_BPS, calculate_fees, DEFAULT_INSTRUMENTS

logger = logging.getLogger("paper_broker")


class PaperBroker(BrokerBase):
    """Simulated broker for paper trading with realistic fills, slippage, and fees."""

    def __init__(self):
        self._authenticated = False
        self._orders: List[Dict[str, Any]] = []
        self._positions: Dict[str, Dict[str, Any]] = {}
        self._holdings: List[Dict[str, Any]] = []
        self._prices: Dict[str, float] = {}
        self._order_counter = 0
        self._initialize_prices()

    def _initialize_prices(self):
        """Set initial simulated prices for default instruments."""
        price_map = {
            "RELIANCE": 2450.0, "INFY": 1520.0, "TCS": 3680.0,
            "HDFCBANK": 1620.0, "SBIN": 780.0, "ITC": 430.0,
            "NIFTY 50": 22500.0, "BANKNIFTY": 48000.0,
        }
        self._prices = price_map

    def _simulate_price(self, symbol: str, base_price: Optional[float] = None) -> float:
        """Get simulated current price with small random movement."""
        if base_price:
            self._prices[symbol] = base_price
        price = self._prices.get(symbol, 1000.0)
        jitter = price * random.uniform(-0.002, 0.002)
        new_price = round(price + jitter, 2)
        self._prices[symbol] = new_price
        return new_price

    def _apply_slippage(self, price: float, side: str) -> float:
        """Apply realistic slippage based on side."""
        slippage_pct = DEFAULT_SLIPPAGE_BPS / 10000
        if side == Side.BUY:
            return round(price * (1 + slippage_pct), 2)
        return round(price * (1 - slippage_pct), 2)

    async def authenticate(self) -> bool:
        self._authenticated = True
        logger.info("Paper broker authenticated (no credentials needed)")
        return True

    async def get_profile(self) -> Dict[str, Any]:
        return {
            "user_id": "PAPER001",
            "user_name": "Paper Trader",
            "email": "paper@kitealgo.local",
            "broker": "paper",
            "exchanges": ["NSE", "BSE", "NFO"],
        }

    async def get_instruments(self, exchange: str = "NSE") -> List[Instrument]:
        instruments = []
        for inst in DEFAULT_INSTRUMENTS:
            if inst["exchange"] == exchange:
                instruments.append(Instrument(**inst))
        return instruments

    async def get_ltp(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, float]:
        result = {}
        for sym in symbols:
            result[sym] = self._simulate_price(sym)
        return result

    async def get_historical_data(
        self, symbol: str, exchange: str, timeframe: str,
        from_date: str, to_date: str
    ) -> List[Dict[str, Any]]:
        """Generate deterministic synthetic historical data for paper trading."""
        from datetime import timedelta, time as dt_time
        import math

        candles = []
        base_price = self._prices.get(symbol, 1000.0)
        start = datetime.fromisoformat(from_date.replace("Z", "+00:00")) if "T" in from_date else datetime.strptime(from_date, "%Y-%m-%d")
        end = datetime.fromisoformat(to_date.replace("Z", "+00:00")) if "T" in to_date else datetime.strptime(to_date, "%Y-%m-%d")

        is_intraday = timeframe.endswith("m")
        step_minutes = int(timeframe.replace("m", "")) if is_intraday else None
        delta = timedelta(days=1) if timeframe == "day" else timedelta(minutes=step_minutes) if is_intraday else timedelta(days=1)
        session_open = dt_time(9, 15)
        session_close = dt_time(15, 30)
        seed_key = f"{symbol}:{exchange}:{timeframe}:{from_date}:{to_date}".encode()
        rng = random.Random(int(hashlib.sha256(seed_key).hexdigest()[:12], 16))

        current = start.replace(hour=9, minute=15, second=0, microsecond=0) if is_intraday else start
        price = base_price
        day_count = 0
        while current <= end:
            in_session = True
            if is_intraday:
                in_session = session_open <= current.time() <= session_close
            if current.weekday() < 5 and in_session:
                intraday_factor = 1.0
                if is_intraday:
                    session_minutes = ((current.hour * 60 + current.minute) - (9 * 60 + 15))
                    intraday_factor = 0.4 + abs(math.sin(session_minutes / 375 * math.pi))
                trend = math.sin(day_count * 0.1) * 0.005
                cyclical = math.sin(day_count * 0.03 + (step_minutes or 1440) / 60) * 0.0025
                noise = rng.gauss(0, 0.01 * intraday_factor)
                change = trend + noise
                o = round(price, 2)
                c = round(max(1.0, price * (1 + change + cyclical)), 2)
                range_noise = max(0.002, abs(rng.gauss(0, 0.006 * intraday_factor)))
                h = round(max(o, c) * (1 + range_noise), 2)
                l = round(min(o, c) * (1 - range_noise), 2)
                if h < max(o, c):
                    h = max(o, c) + round(rng.uniform(0.5, 3.0), 2)
                if l > min(o, c):
                    l = min(o, c) - round(rng.uniform(0.5, 3.0), 2)
                vol = int(rng.gauss(500000 * intraday_factor, 120000 * intraday_factor))
                candles.append({
                    "timestamp": current.isoformat(),
                    "open": o, "high": h, "low": l, "close": c,
                    "volume": max(vol, 10000),
                })
                price = c
                day_count += 1
            if is_intraday and current.time() >= session_close:
                next_day = current + timedelta(days=1)
                current = next_day.replace(hour=9, minute=15, second=0, microsecond=0)
                continue
            current += delta
        return candles

    async def place_order(self, order: Order) -> str:
        """Simulate order placement with instant fill for MARKET orders."""
        self._order_counter += 1
        broker_id = f"PAPER-{self._order_counter:06d}"

        current_price = self._simulate_price(order.symbol)
        fill_price = current_price

        if order.order_type == OrderType.MARKET:
            fill_price = self._apply_slippage(current_price, order.side)
            status = OrderStatus.COMPLETE
        elif order.order_type == OrderType.LIMIT:
            if order.price is not None:
                if (order.side == Side.BUY and order.price >= current_price) or \
                   (order.side == Side.SELL and order.price <= current_price):
                    fill_price = order.price
                    status = OrderStatus.COMPLETE
                else:
                    status = OrderStatus.OPEN
                    fill_price = None
            else:
                fill_price = self._apply_slippage(current_price, order.side)
                status = OrderStatus.COMPLETE
        else:
            fill_price = self._apply_slippage(current_price, order.side)
            status = OrderStatus.COMPLETE

        fees = calculate_fees(fill_price * order.quantity, order.side) if fill_price else 0

        order_record = {
            "broker_order_id": broker_id,
            "order_id": order.id,
            "signal_id": order.signal_id,
            "symbol": order.symbol,
            "exchange": order.exchange,
            "side": order.side,
            "quantity": order.quantity,
            "order_type": order.order_type,
            "product": order.product,
            "price": order.price,
            "trigger_price": order.trigger_price,
            "status": status,
            "filled_quantity": order.quantity if status == OrderStatus.COMPLETE else 0,
            "filled_price": fill_price,
            "fees": fees,
            "created_at": now_utc(),
            "filled_at": now_utc() if status == OrderStatus.COMPLETE else None,
        }
        self._orders.append(order_record)

        if status == OrderStatus.COMPLETE and fill_price:
            self._update_position(order.symbol, order.exchange, order.side, order.quantity, fill_price)

        logger.info(f"Paper order placed: {broker_id} {order.side} {order.quantity}x {order.symbol} @ {fill_price} [{status}]")
        return broker_id

    def _update_position(self, symbol: str, exchange: str, side: str, qty: int, price: float):
        """Update internal position tracking after a fill."""
        key = f"{exchange}:{symbol}"
        if key in self._positions:
            pos = self._positions[key]
            if pos["side"] == side:
                total_qty = pos["quantity"] + qty
                pos["avg_price"] = round(((pos["avg_price"] * pos["quantity"]) + (price * qty)) / total_qty, 2)
                pos["quantity"] = total_qty
            else:
                remaining = pos["quantity"] - qty
                if remaining > 0:
                    pos["quantity"] = remaining
                elif remaining == 0:
                    pos["status"] = PositionStatus.CLOSED
                    pos["closed_at"] = now_utc()
                else:
                    pos["side"] = side
                    pos["quantity"] = abs(remaining)
                    pos["avg_price"] = price
        else:
            self._positions[key] = {
                "symbol": symbol, "exchange": exchange, "side": side,
                "quantity": qty, "avg_price": price, "current_price": price,
                "unrealized_pnl": 0.0, "status": PositionStatus.OPEN,
                "opened_at": now_utc(), "closed_at": None,
            }

    async def modify_order(self, broker_order_id: str, changes: Dict[str, Any]) -> bool:
        for o in self._orders:
            if o["broker_order_id"] == broker_order_id and o["status"] == OrderStatus.OPEN:
                o.update(changes)
                logger.info(f"Paper order modified: {broker_order_id}")
                return True
        return False

    async def cancel_order(self, broker_order_id: str) -> bool:
        for o in self._orders:
            if o["broker_order_id"] == broker_order_id and o["status"] in [OrderStatus.OPEN, OrderStatus.PENDING]:
                o["status"] = OrderStatus.CANCELLED
                logger.info(f"Paper order cancelled: {broker_order_id}")
                return True
        return False

    async def get_orders(self) -> List[Dict[str, Any]]:
        return self._orders.copy()

    async def get_positions(self) -> List[Dict[str, Any]]:
        positions = []
        for key, pos in self._positions.items():
            current = self._simulate_price(pos["symbol"])
            pos["current_price"] = current
            if pos["status"] == PositionStatus.OPEN:
                if pos["side"] == Side.BUY:
                    pos["unrealized_pnl"] = round((current - pos["avg_price"]) * pos["quantity"], 2)
                else:
                    pos["unrealized_pnl"] = round((pos["avg_price"] - current) * pos["quantity"], 2)
            positions.append(pos.copy())
        return positions

    async def get_holdings(self) -> List[Dict[str, Any]]:
        return self._holdings.copy()

    def set_price(self, symbol: str, price: float):
        """Manually set a price for testing."""
        self._prices[symbol] = price

    def get_price(self, symbol: str) -> float:
        return self._prices.get(symbol, 0.0)
