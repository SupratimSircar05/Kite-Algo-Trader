import logging
from typing import List, Dict, Any

from .broker_base import BrokerBase
from .models import Order, Instrument
from .enums import OrderStatus

logger = logging.getLogger("zerodha_broker")


class ZerodhaBroker(BrokerBase):
    """
    Zerodha Kite Connect broker implementation.
    Requires kiteconnect SDK and valid API credentials.

    Setup:
    1. Get API key/secret from https://kite.trade
    2. Set KITE_API_KEY, KITE_API_SECRET in settings
    3. Generate access token via login flow
    4. Set KITE_ACCESS_TOKEN in settings
    """

    def __init__(self, api_key: str = "", api_secret: str = "", access_token: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.kite = None
        self._authenticated = False

    def _ensure_kite(self):
        """Lazy-initialize kiteconnect client."""
        if self.kite is None:
            try:
                from kiteconnect import KiteConnect
                self.kite = KiteConnect(api_key=self.api_key)
                if self.access_token:
                    self.kite.set_access_token(self.access_token)
            except ImportError:
                logger.error("kiteconnect package not installed. Run: pip install kiteconnect")
                raise RuntimeError("kiteconnect not installed")
            except Exception as e:
                logger.error(f"Failed to initialize KiteConnect: {e}")
                raise

    async def authenticate(self) -> bool:
        """Authenticate using access token. For initial login, use the redirect flow."""
        try:
            self._ensure_kite()
            if not self.access_token:
                logger.warning("No access token set. Use login flow to generate one.")
                logger.info(f"Login URL: {self.kite.login_url()}")
                return False
            profile = self.kite.profile()
            self._authenticated = True
            logger.info(f"Zerodha authenticated: {profile.get('user_id', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Zerodha authentication failed: {e}")
            self._authenticated = False
            return False

    async def get_profile(self) -> Dict[str, Any]:
        self._ensure_kite()
        try:
            return self.kite.profile()
        except Exception as e:
            logger.error(f"Get profile failed: {e}")
            return {"error": str(e)}

    async def get_instruments(self, exchange: str = "NSE") -> List[Instrument]:
        self._ensure_kite()
        try:
            raw = self.kite.instruments(exchange)
            instruments = []
            for item in raw:
                instruments.append(Instrument(
                    instrument_token=item.get("instrument_token", 0),
                    exchange_token=item.get("exchange_token", 0),
                    tradingsymbol=item.get("tradingsymbol", ""),
                    name=item.get("name", ""),
                    exchange=exchange,
                    segment=item.get("segment", ""),
                    instrument_type=item.get("instrument_type", "EQ"),
                    tick_size=item.get("tick_size", 0.05),
                    lot_size=item.get("lot_size", 1),
                    last_price=item.get("last_price", 0.0),
                    expiry=str(item["expiry"]) if item.get("expiry") else None,
                ))
            return instruments
        except Exception as e:
            logger.error(f"Get instruments failed: {e}")
            return []

    async def get_ltp(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, float]:
        self._ensure_kite()
        try:
            instrument_keys = [f"{exchange}:{sym}" for sym in symbols]
            data = self.kite.ltp(instrument_keys)
            result = {}
            for key, val in data.items():
                sym = key.split(":")[1] if ":" in key else key
                result[sym] = val.get("last_price", 0.0)
            return result
        except Exception as e:
            logger.error(f"Get LTP failed: {e}")
            return {}

    async def get_historical_data(
        self, symbol: str, exchange: str, timeframe: str,
        from_date: str, to_date: str
    ) -> List[Dict[str, Any]]:
        self._ensure_kite()
        try:
            tf_map = {"1m": "minute", "3m": "3minute", "5m": "5minute", "15m": "15minute",
                       "30m": "30minute", "60m": "60minute", "day": "day", "week": "week", "month": "month"}
            kite_interval = tf_map.get(timeframe, "day")
            # Need instrument_token - would come from instrument store
            # This is a simplified version
            data = self.kite.historical_data(
                instrument_token=0,  # Must be resolved from instrument store
                from_date=from_date,
                to_date=to_date,
                interval=kite_interval,
            )
            candles = []
            for row in data:
                candles.append({
                    "timestamp": str(row["date"]),
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                })
            return candles
        except Exception as e:
            logger.error(f"Get historical data failed: {e}")
            return []

    async def place_order(self, order: Order) -> str:
        self._ensure_kite()
        try:
            order_id = self.kite.place_order(
                variety="regular",
                exchange=order.exchange,
                tradingsymbol=order.symbol,
                transaction_type=order.side,
                quantity=order.quantity,
                product=order.product,
                order_type=order.order_type,
                price=order.price,
                trigger_price=order.trigger_price,
                validity=order.validity,
                tag=order.tag[:20] if order.tag else "",
            )
            logger.info(f"Zerodha order placed: {order_id}")
            return str(order_id)
        except Exception as e:
            logger.error(f"Place order failed: {e}")
            raise

    async def modify_order(self, broker_order_id: str, changes: Dict[str, Any]) -> bool:
        self._ensure_kite()
        try:
            self.kite.modify_order(
                variety="regular",
                order_id=broker_order_id,
                **changes,
            )
            return True
        except Exception as e:
            logger.error(f"Modify order failed: {e}")
            return False

    async def cancel_order(self, broker_order_id: str) -> bool:
        self._ensure_kite()
        try:
            self.kite.cancel_order(variety="regular", order_id=broker_order_id)
            return True
        except Exception as e:
            logger.error(f"Cancel order failed: {e}")
            return False

    async def get_orders(self) -> List[Dict[str, Any]]:
        self._ensure_kite()
        try:
            return self.kite.orders()
        except Exception as e:
            logger.error(f"Get orders failed: {e}")
            return []

    async def get_positions(self) -> List[Dict[str, Any]]:
        self._ensure_kite()
        try:
            pos = self.kite.positions()
            return pos.get("net", [])
        except Exception as e:
            logger.error(f"Get positions failed: {e}")
            return []

    async def get_holdings(self) -> List[Dict[str, Any]]:
        self._ensure_kite()
        try:
            return self.kite.holdings()
        except Exception as e:
            logger.error(f"Get holdings failed: {e}")
            return []

    def get_login_url(self) -> str:
        """Get Zerodha login URL for initial authentication."""
        self._ensure_kite()
        return self.kite.login_url()

    async def generate_session(self, request_token: str) -> Dict[str, Any]:
        """Generate access token from request token after login redirect."""
        self._ensure_kite()
        try:
            data = self.kite.generate_session(request_token, api_secret=self.api_secret)
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)
            self._authenticated = True
            return data
        except Exception as e:
            logger.error(f"Generate session failed: {e}")
            raise
