import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from .models import Signal, Order, Trade, Position, gen_id, now_utc
from .enums import (
    Side, OrderType, OrderStatus, TradeStatus, PositionStatus,
    ProductType, Validity, TradingMode, SignalStatus
)
from .broker_base import BrokerBase
from .risk import RiskManager
from .config import calculate_fees

logger = logging.getLogger("execution")


class OrderManager:
    """Converts approved signals into validated broker orders."""

    def __init__(self, broker: BrokerBase, risk_manager: RiskManager, trading_mode: TradingMode = TradingMode.PAPER):
        self.broker = broker
        self.risk = risk_manager
        self.trading_mode = trading_mode
        self._pending_orders: Dict[str, Order] = {}

    def validate_order_payload(self, order: Order) -> tuple[bool, str]:
        """Validate order fields before sending to broker."""
        if not order.symbol:
            return False, "Symbol is required"
        if order.quantity <= 0:
            return False, "Quantity must be positive"
        if order.order_type == OrderType.LIMIT and order.price is None:
            return False, "Limit orders require a price"
        if order.order_type in [OrderType.SL, OrderType.SL_M] and order.trigger_price is None:
            return False, "Stop-loss orders require a trigger price"
        if order.order_type == OrderType.SL and order.price is None:
            return False, "SL orders require both price and trigger_price"
        return True, "OK"

    def signal_to_order(
        self, signal: Signal,
        order_type: OrderType = OrderType.MARKET,
        product: ProductType = ProductType.MIS,
        quantity: Optional[int] = None,
    ) -> Order:
        """Convert a signal into an order."""
        return Order(
            signal_id=signal.id,
            symbol=signal.symbol,
            exchange=signal.exchange,
            side=signal.side,
            quantity=quantity or signal.quantity,
            order_type=order_type,
            product=product,
            price=signal.price if order_type == OrderType.LIMIT else None,
            trigger_price=signal.stop_loss if order_type in [OrderType.SL, OrderType.SL_M] else None,
            tag=f"{signal.strategy_name[:10]}_{signal.id[:6]}",
            trading_mode=self.trading_mode,
        )

    async def execute_signal(
        self, signal: Signal, capital: float = 100000.0,
        order_type: OrderType = OrderType.MARKET,
        product: ProductType = ProductType.MIS,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Full pipeline: validate signal -> create order -> place with broker."""
        # Risk check
        approved, failures = self.risk.validate_signal(signal, capital)
        if not approved:
            logger.warning(f"Signal rejected by risk: {failures}")
            return {"success": False, "reason": "risk_rejected", "failures": failures, "signal_id": signal.id}

        # Create order
        order = self.signal_to_order(signal, order_type, product)

        # Validate payload
        valid, reason = self.validate_order_payload(order)
        if not valid:
            logger.warning(f"Order validation failed: {reason}")
            return {"success": False, "reason": "validation_failed", "message": reason, "signal_id": signal.id}

        # Dry run
        if dry_run:
            logger.info(f"DRY RUN: Would place {order.side} {order.quantity}x {order.symbol} @ {order.order_type}")
            return {
                "success": True, "dry_run": True,
                "order": order.model_dump(),
                "signal_id": signal.id,
            }

        # Place order
        try:
            broker_order_id = await self.broker.place_order(order)
            order.broker_order_id = broker_order_id
            order.status = OrderStatus.COMPLETE  # For market orders via paper broker
            order.updated_at = now_utc()
            self._pending_orders[order.id] = order
            self.risk.record_order()

            logger.info(f"Order executed: {broker_order_id} for signal {signal.id}")
            return {
                "success": True,
                "order_id": order.id,
                "broker_order_id": broker_order_id,
                "signal_id": signal.id,
                "order": order.model_dump(),
            }
        except Exception as e:
            logger.error(f"Order execution failed: {e}")
            return {"success": False, "reason": "broker_error", "message": str(e), "signal_id": signal.id}


class TradeEngine:
    """Tracks trades from signal to exit, manages PnL calculation."""

    def __init__(self):
        self._open_trades: Dict[str, Trade] = {}
        self._closed_trades: List[Trade] = []
        self._total_pnl: float = 0.0

    def open_trade(self, order: Order, fill_price: float, strategy_name: str = "") -> Trade:
        """Create a new trade from a filled order."""
        trade = Trade(
            order_id=order.id,
            signal_id=order.signal_id,
            symbol=order.symbol,
            exchange=order.exchange,
            side=order.side,
            quantity=order.quantity,
            entry_price=fill_price,
            strategy_name=strategy_name,
            trading_mode=order.trading_mode,
        )
        self._open_trades[trade.id] = trade
        logger.info(f"Trade opened: {trade.id} {trade.side} {trade.quantity}x {trade.symbol} @ {fill_price}")
        return trade

    def close_trade(self, trade_id: str, exit_price: float, fees: float = 0.0) -> Optional[Trade]:
        """Close an open trade and calculate PnL."""
        trade = self._open_trades.pop(trade_id, None)
        if not trade:
            logger.warning(f"Trade {trade_id} not found in open trades")
            return None

        if trade.side == Side.BUY:
            trade.pnl = round((exit_price - trade.entry_price) * trade.quantity, 2)
        else:
            trade.pnl = round((trade.entry_price - exit_price) * trade.quantity, 2)

        trade.exit_price = exit_price
        trade.fees = fees or calculate_fees(exit_price * trade.quantity, "SELL")
        entry_fees = calculate_fees(trade.entry_price * trade.quantity, "BUY")
        trade.net_pnl = round(trade.pnl - trade.fees - entry_fees, 2)
        trade.pnl_percent = round((trade.pnl / (trade.entry_price * trade.quantity)) * 100, 2) if trade.entry_price > 0 else 0
        trade.status = TradeStatus.CLOSED
        trade.exit_time = now_utc()

        entry_dt = datetime.fromisoformat(trade.entry_time)
        exit_dt = datetime.fromisoformat(trade.exit_time)
        trade.duration_seconds = int((exit_dt - entry_dt).total_seconds())

        self._closed_trades.append(trade)
        self._total_pnl += trade.net_pnl
        logger.info(f"Trade closed: {trade.id} PnL={trade.pnl:.2f} Net={trade.net_pnl:.2f}")
        return trade

    def get_open_trades(self) -> List[Trade]:
        return list(self._open_trades.values())

    def get_closed_trades(self) -> List[Trade]:
        return self._closed_trades.copy()

    def get_total_pnl(self) -> float:
        return self._total_pnl

    def get_metrics(self) -> Dict[str, Any]:
        closed = self._closed_trades
        if not closed:
            return {"total_trades": 0, "win_rate": 0, "total_pnl": 0}

        wins = [t for t in closed if t.net_pnl > 0]
        losses = [t for t in closed if t.net_pnl <= 0]
        avg_win = sum(t.net_pnl for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.net_pnl for t in losses) / len(losses) if losses else 0

        return {
            "total_trades": len(closed),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(len(wins) / len(closed) * 100, 2),
            "total_pnl": round(self._total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(abs(sum(t.net_pnl for t in wins)) / abs(sum(t.net_pnl for t in losses)), 2) if losses and sum(t.net_pnl for t in losses) != 0 else 0,
            "expectancy": round(self._total_pnl / len(closed), 2),
        }
