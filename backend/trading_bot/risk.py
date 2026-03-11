import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from .models import Signal, Order, RiskConfig, now_utc
from .enums import Side

logger = logging.getLogger("risk")


class RiskManager:
    """
    Enforces pre-trade risk controls and position sizing.
    All checks return (approved: bool, reason: str).
    """

    def __init__(self, config: RiskConfig):
        self.config = config
        self._daily_pnl: float = 0.0
        self._daily_order_count: int = 0
        self._open_position_count: int = 0
        self._consecutive_losses: int = 0
        self._last_exit_time: Optional[str] = None
        self._recent_signals: List[str] = []  # signal hashes for dedup

    def check_kill_switch(self) -> tuple[bool, str]:
        if self.config.kill_switch_active:
            return False, f"Kill switch is ACTIVE: {self.config.kill_switch_reason or 'Manual activation'}"
        return True, "OK"

    def check_daily_loss(self) -> tuple[bool, str]:
        if abs(self._daily_pnl) >= self.config.max_daily_loss and self._daily_pnl < 0:
            return False, f"Max daily loss reached: {self._daily_pnl:.2f} >= {self.config.max_daily_loss}"
        return True, "OK"

    def check_daily_loss_pct(self, capital: float) -> tuple[bool, str]:
        if capital <= 0:
            return True, "OK"
        loss_pct = abs(self._daily_pnl) / capital * 100
        if self._daily_pnl < 0 and loss_pct >= self.config.max_daily_loss_pct:
            return False, f"Max daily loss % reached: {loss_pct:.2f}% >= {self.config.max_daily_loss_pct}%"
        return True, "OK"

    def check_max_orders(self) -> tuple[bool, str]:
        if self._daily_order_count >= self.config.max_orders_per_day:
            return False, f"Max orders/day reached: {self._daily_order_count} >= {self.config.max_orders_per_day}"
        return True, "OK"

    def check_max_positions(self) -> tuple[bool, str]:
        if self._open_position_count >= self.config.max_open_positions:
            return False, f"Max open positions reached: {self._open_position_count} >= {self.config.max_open_positions}"
        return True, "OK"

    def check_position_size(self, quantity: int) -> tuple[bool, str]:
        if quantity > self.config.max_position_size:
            return False, f"Position size {quantity} exceeds max {self.config.max_position_size}"
        return True, "OK"

    def check_position_value(self, quantity: int, price: float) -> tuple[bool, str]:
        value = quantity * price
        if value > self.config.max_position_value:
            return False, f"Position value {value:.2f} exceeds max {self.config.max_position_value:.2f}"
        return True, "OK"

    def check_symbol_allowed(self, symbol: str) -> tuple[bool, str]:
        if self.config.symbol_blacklist and symbol in self.config.symbol_blacklist:
            return False, f"Symbol {symbol} is blacklisted"
        if self.config.symbol_whitelist and symbol not in self.config.symbol_whitelist:
            return False, f"Symbol {symbol} not in whitelist"
        return True, "OK"

    def check_no_trade_window(self) -> tuple[bool, str]:
        if not self.config.no_trade_start or not self.config.no_trade_end:
            return True, "OK"
        import pytz
        now_ist = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%H:%M")
        if self.config.no_trade_start <= now_ist <= self.config.no_trade_end:
            return False, f"No-trade window active: {self.config.no_trade_start}-{self.config.no_trade_end}"
        return True, "OK"

    def check_cooldown(self) -> tuple[bool, str]:
        if not self._last_exit_time:
            return True, "OK"
        try:
            exit_dt = datetime.fromisoformat(self._last_exit_time)
            now = datetime.now(timezone.utc)
            elapsed = (now - exit_dt).total_seconds()
            if elapsed < self.config.cooldown_seconds:
                return False, f"Cooldown active: {self.config.cooldown_seconds - elapsed:.0f}s remaining"
        except (ValueError, TypeError):
            pass
        return True, "OK"

    def check_consecutive_losses(self) -> tuple[bool, str]:
        if self._consecutive_losses >= self.config.max_consecutive_losses:
            return False, f"Consecutive losses: {self._consecutive_losses} >= {self.config.max_consecutive_losses}"
        return True, "OK"

    def check_duplicate_signal(self, signal: Signal) -> tuple[bool, str]:
        sig_hash = f"{signal.symbol}:{signal.side}:{signal.strategy_name}"
        if sig_hash in self._recent_signals:
            return False, f"Duplicate signal: {sig_hash}"
        return True, "OK"

    def validate_signal(self, signal: Signal, capital: float = 100000.0) -> tuple[bool, List[str]]:
        """Run all risk checks on a signal. Returns (approved, list of failure reasons)."""
        failures = []
        checks = [
            self.check_kill_switch(),
            self.check_daily_loss(),
            self.check_daily_loss_pct(capital),
            self.check_max_orders(),
            self.check_max_positions(),
            self.check_position_size(signal.quantity),
            self.check_symbol_allowed(signal.symbol),
            self.check_no_trade_window(),
            self.check_cooldown(),
            self.check_consecutive_losses(),
            self.check_duplicate_signal(signal),
        ]
        if signal.price:
            checks.append(self.check_position_value(signal.quantity, signal.price))

        for ok, reason in checks:
            if not ok:
                failures.append(reason)

        approved = len(failures) == 0
        if approved:
            sig_hash = f"{signal.symbol}:{signal.side}:{signal.strategy_name}"
            self._recent_signals.append(sig_hash)
            if len(self._recent_signals) > 100:
                self._recent_signals = self._recent_signals[-50:]

        return approved, failures

    def record_order(self):
        self._daily_order_count += 1

    def record_trade_result(self, pnl: float):
        self._daily_pnl += pnl
        if pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

    def record_exit(self):
        self._last_exit_time = now_utc()

    def update_positions(self, count: int):
        self._open_position_count = count

    def reset_daily(self):
        self._daily_pnl = 0.0
        self._daily_order_count = 0
        self._consecutive_losses = 0
        self._recent_signals.clear()
        self._last_exit_time = None

    def activate_kill_switch(self, reason: str = "Manual"):
        self.config.kill_switch_active = True
        self.config.kill_switch_reason = reason
        logger.warning(f"KILL SWITCH ACTIVATED: {reason}")

    def deactivate_kill_switch(self):
        self.config.kill_switch_active = False
        self.config.kill_switch_reason = None
        logger.info("Kill switch deactivated")


# Position sizing helpers
def size_fixed_quantity(quantity: int) -> int:
    return max(1, quantity)


def size_fixed_capital(capital_per_trade: float, price: float) -> int:
    if price <= 0:
        return 1
    return max(1, int(capital_per_trade / price))


def size_percent_of_capital(total_capital: float, pct: float, price: float) -> int:
    if price <= 0:
        return 1
    alloc = total_capital * (pct / 100)
    return max(1, int(alloc / price))


def size_risk_per_trade(
    total_capital: float, risk_pct: float,
    entry_price: float, stop_loss: float
) -> int:
    risk_amount = total_capital * (risk_pct / 100)
    risk_per_share = abs(entry_price - stop_loss)
    if risk_per_share <= 0:
        return 1
    return max(1, int(risk_amount / risk_per_share))
