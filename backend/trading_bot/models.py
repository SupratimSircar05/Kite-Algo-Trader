from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid

from .enums import (
    Side, OrderType, OrderStatus, PositionStatus, TradeStatus,
    SignalStatus, Exchange, ProductType, Validity, TradingMode,
    BotStatus, Timeframe
)


def gen_id() -> str:
    return str(uuid.uuid4())[:12]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class Signal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=gen_id)
    symbol: str
    exchange: str = "NSE"
    side: Side
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    reason: str = ""
    timestamp: str = Field(default_factory=now_utc)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy_name: str = ""
    status: SignalStatus = SignalStatus.GENERATED
    quantity: int = 1
    price: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Order(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=gen_id)
    signal_id: Optional[str] = None
    correlation_id: str = Field(default_factory=gen_id)
    symbol: str
    exchange: str = "NSE"
    side: Side
    quantity: int
    order_type: OrderType = OrderType.MARKET
    product: ProductType = ProductType.MIS
    validity: Validity = Validity.DAY
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    broker_order_id: Optional[str] = None
    filled_quantity: int = 0
    filled_price: Optional[float] = None
    created_at: str = Field(default_factory=now_utc)
    updated_at: str = Field(default_factory=now_utc)
    filled_at: Optional[str] = None
    tag: str = ""
    rejection_reason: Optional[str] = None
    trading_mode: TradingMode = TradingMode.PAPER


class Trade(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=gen_id)
    order_id: str
    signal_id: Optional[str] = None
    symbol: str
    exchange: str = "NSE"
    side: Side
    quantity: int
    entry_price: float
    exit_price: Optional[float] = None
    pnl: float = 0.0
    pnl_percent: float = 0.0
    fees: float = 0.0
    net_pnl: float = 0.0
    status: TradeStatus = TradeStatus.OPEN
    strategy_name: str = ""
    entry_time: str = Field(default_factory=now_utc)
    exit_time: Optional[str] = None
    duration_seconds: int = 0
    slippage: float = 0.0
    trading_mode: TradingMode = TradingMode.PAPER


class Position(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=gen_id)
    symbol: str
    exchange: str = "NSE"
    side: Side
    quantity: int
    avg_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    status: PositionStatus = PositionStatus.OPEN
    product: ProductType = ProductType.MIS
    strategy_name: str = ""
    opened_at: str = Field(default_factory=now_utc)
    closed_at: Optional[str] = None
    trading_mode: TradingMode = TradingMode.PAPER


class Instrument(BaseModel):
    model_config = ConfigDict(extra="ignore")
    instrument_token: int = 0
    exchange_token: int = 0
    tradingsymbol: str
    name: str = ""
    exchange: str = "NSE"
    segment: str = ""
    instrument_type: str = "EQ"
    tick_size: float = 0.05
    lot_size: int = 1
    last_price: float = 0.0
    expiry: Optional[str] = None


class Candle(BaseModel):
    model_config = ConfigDict(extra="ignore")
    symbol: str
    exchange: str = "NSE"
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    timeframe: str = "day"


class BacktestResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=gen_id)
    strategy_name: str
    symbol: str
    exchange: str = "NSE"
    timeframe: str = "day"
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    final_capital: float = 100000.0
    total_return: float = 0.0
    total_return_pct: float = 0.0
    cagr: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    expectancy: float = 0.0
    avg_trade_duration: float = 0.0
    avg_slippage_bps: float = 0.0
    slippage_cost_total: float = 0.0
    equity_curve: List[Dict[str, Any]] = Field(default_factory=list)
    trades: List[Dict[str, Any]] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_utc)


class RiskConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    max_daily_loss: float = 5000.0
    max_daily_loss_pct: float = 5.0
    max_position_size: int = 100
    max_position_value: float = 50000.0
    max_open_positions: int = 5
    max_orders_per_day: int = 50
    kill_switch_active: bool = False
    kill_switch_reason: Optional[str] = None
    symbol_whitelist: List[str] = Field(default_factory=list)
    symbol_blacklist: List[str] = Field(default_factory=list)
    no_trade_start: Optional[str] = None  # "09:15"
    no_trade_end: Optional[str] = None    # "09:30"
    cooldown_seconds: int = 60
    max_consecutive_losses: int = 5
    max_slippage_pct: float = 1.0
    enable_circuit_breaker: bool = True
    updated_at: str = Field(default_factory=now_utc)


class StrategyConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    display_name: str = ""
    description: str = ""
    enabled: bool = True
    symbols: List[str] = Field(default_factory=lambda: ["RELIANCE", "INFY", "TCS", "HDFCBANK"])
    exchange: str = "NSE"
    timeframe: str = "5m"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    product: ProductType = ProductType.MIS
    quantity: int = 1
    updated_at: str = Field(default_factory=now_utc)


class BotRunRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=gen_id)
    mode: TradingMode = TradingMode.PAPER
    strategy_name: str = ""
    status: BotStatus = BotStatus.IDLE
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    signals_generated: int = 0
    orders_placed: int = 0
    trades_executed: int = 0
    total_pnl: float = 0.0
    error_message: Optional[str] = None


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    trading_mode: TradingMode = TradingMode.PAPER
    kite_api_key: str = ""
    kite_api_secret: str = ""
    kite_access_token: str = ""
    kite_redirect_url: str = "http://localhost:8001/api/kite/callback"
    default_exchange: str = "NSE"
    capital: float = 100000.0
    timezone: str = "Asia/Kolkata"
    enable_ticks: bool = False
    log_level: str = "INFO"
    auto_square_off_time: str = "15:15"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    webhook_url: str = ""
    updated_at: str = Field(default_factory=now_utc)


class DashboardSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    bot_status: BotStatus = BotStatus.IDLE
    trading_mode: TradingMode = TradingMode.PAPER
    capital: float = 100000.0
    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0
    total_pnl: float = 0.0
    open_positions: int = 0
    total_trades_today: int = 0
    total_signals_today: int = 0
    win_rate: float = 0.0
    active_strategy: str = "None"
    kill_switch_active: bool = False
    market_status: str = "CLOSED"
    last_signal_time: Optional[str] = None
    uptime_seconds: int = 0


class EquityPoint(BaseModel):
    timestamp: str
    equity: float
    pnl: float


class DailyPnL(BaseModel):
    date: str
    pnl: float
    trades: int
    win_rate: float
