from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from .models import Order, Position, Instrument


class BrokerBase(ABC):
    """Abstract broker interface. All broker implementations must extend this."""

    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the broker. Returns True on success."""
        ...

    @abstractmethod
    async def get_profile(self) -> Dict[str, Any]:
        """Get user/account profile."""
        ...

    @abstractmethod
    async def get_instruments(self, exchange: str = "NSE") -> List[Instrument]:
        """Fetch all tradeable instruments for an exchange."""
        ...

    @abstractmethod
    async def get_ltp(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, float]:
        """Get last traded price for given symbols."""
        ...

    @abstractmethod
    async def get_historical_data(
        self, symbol: str, exchange: str, timeframe: str,
        from_date: str, to_date: str
    ) -> List[Dict[str, Any]]:
        """Fetch historical OHLCV candles."""
        ...

    @abstractmethod
    async def place_order(self, order: Order) -> str:
        """Place an order. Returns broker_order_id."""
        ...

    @abstractmethod
    async def modify_order(self, broker_order_id: str, changes: Dict[str, Any]) -> bool:
        """Modify an existing order."""
        ...

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel an order."""
        ...

    @abstractmethod
    async def get_orders(self) -> List[Dict[str, Any]]:
        """Get all orders for the day."""
        ...

    @abstractmethod
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        ...

    @abstractmethod
    async def get_holdings(self) -> List[Dict[str, Any]]:
        """Get holdings (delivery positions)."""
        ...
