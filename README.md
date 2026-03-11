# KiteAlgo - Algorithmic Trading Bot for Indian Markets

A production-style, end-to-end algo trading system for Indian markets using **Zerodha Kite Connect APIs**. Features a complete Python trading bot core with a professional-grade React web dashboard for monitoring, backtesting, strategy optimization, and risk management.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Dashboard Pages](#dashboard-pages)
- [Trading Bot Core](#trading-bot-core)
- [Strategies](#strategies)
- [Backtesting](#backtesting)
- [Strategy Optimizer](#strategy-optimizer)
- [Risk Controls](#risk-controls)
- [Broker Integration](#broker-integration)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Paper Trading Walkthrough](#paper-trading-walkthrough)
- [Paper-to-Live Migration Checklist](#paper-to-live-migration-checklist)
- [Production Hardening Checklist](#production-hardening-checklist)
- [Troubleshooting](#troubleshooting)
- [Strategy Development Guide](#strategy-development-guide)
- [Future Roadmap](#future-roadmap)

---

## Overview

KiteAlgo is built with a core philosophy: **full ownership of strategy, execution, logging, risk controls, and deployment**. No third-party bot platforms, no SaaS lock-in, no no-code tools.

**Key principles:**
- Paper trading by default. Live trading requires explicit opt-in.
- Strategy logic is fully decoupled from broker logic.
- Every critical action is logged as a structured event.
- Risk controls are enforced before every order placement.
- Kill switch provides instant emergency stop.

**Primary use cases:**
- Intraday and positional strategy experimentation
- Safe paper-trading with realistic simulated fills
- Backtesting strategies against historical data
- Parameter optimization with visual heatmaps

---

## Architecture

```
+-----------------------------------------------------------+
|                    React Dashboard                         |
|  Dashboard | Trades | Backtest | Strategies | Risk | Opt  |
+-----------------------------------------------------------+
         |  HTTP/REST (REACT_APP_BACKEND_URL/api)
+-----------------------------------------------------------+
|                   FastAPI Backend                          |
|  server.py - API endpoints, bot control, data serving     |
+-----------------------------------------------------------+
         |                    |                    |
+----------------+  +------------------+  +---------------+
| Trading Bot    |  | MongoDB          |  | Paper Broker  |
| Core Modules   |  | (Persistent      |  | (Simulated    |
|                |  |  Storage)        |  |  Fills)       |
| - Strategies   |  |                  |  |               |
| - Risk Manager |  | Collections:     |  | - Slippage    |
| - Execution    |  | - signals        |  | - Fees        |
| - Backtest     |  | - orders         |  | - Position    |
| - Models       |  | - trades         |  |   Tracking    |
| - Config       |  | - positions      |  |               |
+----------------+  | - backtest_results|  +---------------+
                    | - risk_config    |
                    | - settings       |         |
                    | - instruments    |  +---------------+
                    | - optimizer_results| Zerodha Kite  |
                    | - bot_runs       |  | Connect SDK  |
                    +------------------+  | (When creds  |
                                          |  configured) |
                                          +---------------+
```

### Data Flow

1. **Signal Generation**: Strategy processes candles/ticks and emits normalized `Signal` objects
2. **Risk Validation**: `RiskManager` runs 11+ pre-trade checks (kill switch, daily loss, position limits, etc.)
3. **Order Execution**: `OrderManager` converts approved signals into broker orders
4. **Trade Tracking**: `TradeEngine` tracks lifecycle from entry to exit with P&L calculation
5. **Storage**: All signals, orders, trades, and positions persisted to MongoDB
6. **Dashboard**: React frontend polls API for real-time updates

---

## Features

### Dashboard & Monitoring
- Real-time dashboard with daily P&L, equity curve, open positions, signal count
- Interactive equity curve chart (area chart with gradient)
- Daily P&L bar chart
- Recent signals and trades tables with color-coded BUY/SELL indicators
- Bot start/stop control from the dashboard
- Kill switch status badge

### Trade Monitor
- Four-tab view: Orders, Trades, Positions, Signals
- Status filtering (Complete, Open, Pending, Cancelled, Closed)
- Color-coded P&L (green = profit, red = loss)
- Detailed order lifecycle tracking with broker IDs

### Backtest Lab
- Run strategies against historical data with configurable parameters
- Equity curve visualization with dynamic coloring (green for profit, red for loss)
- Comprehensive metrics: Return %, CAGR, Win Rate, Max Drawdown, Sharpe Ratio, Profit Factor, Expectancy
- Detailed trade-by-trade breakdown table
- Previous backtests stored and reloadable

### Strategy Optimizer
- Grid search across parameter ranges (e.g., fast_period 5-20, slow_period 15-50)
- Interactive color-coded heatmap (green = best, red = worst)
- Switchable heatmap metric: Return %, Sharpe Ratio, Win Rate, Max Drawdown
- Hover tooltips with full details per cell
- Best parameter combination highlighted with golden ring
- Full results table sortable by any metric column
- Add/remove custom parameters dynamically
- Previous optimizations saved and reloadable
- Safety limit: max 2500 combinations per run

### Strategy Editor
- Configure strategy parameters (SMA periods, breakout settings, etc.)
- Enable/disable strategies
- Set instruments per strategy (comma-separated symbols)
- Set quantity per trade
- Reset to default parameters

### Risk Controls
- Visual kill switch with glowing activation effect
- Loss limits: max daily loss (INR + %), max consecutive losses, max slippage
- Position limits: max position size, max position value, max open positions, max orders/day
- Safety controls: cooldown after exit, circuit breaker, no-trade windows
- Symbol whitelist/blacklist

### Settings
- Zerodha Kite Connect credential management (API Key, Secret, Access Token)
- Trading mode toggle (Paper/Live) with live mode warning
- Capital configuration
- Telegram bot alert configuration
- Webhook URL configuration
- System health monitoring (API, Database, Market, Bot status)
- Initialize database and sync instruments actions
- Instruments table with all configured symbols

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | Python 3.11+, FastAPI, Pydantic v2 |
| **Frontend** | React 18, Tailwind CSS, Shadcn/UI |
| **Database** | MongoDB (Motor async driver) |
| **Charts** | Recharts (area, bar charts), Custom CSS heatmap |
| **Broker SDK** | Zerodha KiteConnect Python SDK |
| **Trading Fees** | Indian NSE equity intraday fee model (STT, GST, SEBI, stamp duty) |
| **Timezone** | Asia/Kolkata (IST) with pytz |

---

## Project Structure

```
app/
+-- backend/
|   +-- server.py                    # FastAPI application (all API endpoints)
|   +-- .env                         # Environment variables (MONGO_URL, DB_NAME)
|   +-- requirements.txt             # Python dependencies
|   +-- trading_bot/                 # Core trading bot modules
|       +-- __init__.py
|       +-- models.py                # Pydantic models (Signal, Order, Trade, Position, etc.)
|       +-- enums.py                 # Enumerations (Side, OrderType, TradingMode, etc.)
|       +-- config.py                # Market hours, fees, default instruments, IST timezone
|       +-- broker_base.py           # Abstract broker interface (BrokerBase ABC)
|       +-- broker_paper.py          # Paper trading broker (simulated fills, slippage, fees)
|       +-- broker_zerodha.py        # Zerodha Kite Connect broker implementation
|       +-- strategies.py            # Strategy base + SMA Crossover + ORB strategies
|       +-- risk.py                  # Risk manager (11+ checks), kill switch, position sizing
|       +-- execution.py             # Order manager, trade engine, P&L tracking
|       +-- backtest.py              # Backtesting engine with comprehensive metrics
+-- frontend/
|   +-- .env                         # REACT_APP_BACKEND_URL
|   +-- package.json
|   +-- src/
|       +-- App.js                   # React router with 7 pages
|       +-- App.css                  # Terminal-style component classes
|       +-- index.css                # Dark theme, fonts (IBM Plex Sans + JetBrains Mono)
|       +-- pages/
|       |   +-- Dashboard.js         # Overview with metrics, charts, recent activity
|       |   +-- TradeMonitor.js      # Orders, trades, positions, signals tabs
|       |   +-- BacktestLab.js       # Backtesting configuration and results
|       |   +-- Optimizer.js         # Parameter optimization with heatmap
|       |   +-- StrategyEditor.js    # Strategy parameter configuration
|       |   +-- RiskControls.js      # Risk limits and kill switch
|       |   +-- Settings.js          # Credentials, trading config, system health
|       +-- components/
|           +-- Sidebar.js           # Navigation sidebar
|           +-- ui/                  # Shadcn/UI components
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- MongoDB (running locally or remote)
- Yarn package manager

### 1. Clone and Install

```bash
# Clone the repository
git clone <your-repo-url>
cd kitealgo

# Backend setup
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Frontend setup
cd ../frontend
yarn install
```

### 2. Configure Environment

**Backend** (`backend/.env`):
```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=kitealgo
```

**Frontend** (`frontend/.env`):
```env
REACT_APP_BACKEND_URL=http://localhost:8001
```

### 3. Start Services

```bash
# Terminal 1: Start MongoDB
mongod

# Terminal 2: Start Backend
cd backend
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Terminal 3: Start Frontend
cd frontend
yarn start
```

### 4. Initialize

Open the dashboard at `http://localhost:3000` and:
1. Go to **Settings** > **System** > Click **Initialize DB**
2. Click **Sync Instruments** to load default instruments
3. Go to **Dashboard** > Click **Start Bot** to generate demo data
4. Go to **Backtest Lab** to run your first backtest
5. Go to **Optimizer** to find optimal strategy parameters

---

## Dashboard Pages

### 1. Dashboard (/)
The main overview page showing:
- **Metric Cards**: Daily P&L, Total P&L, Open Positions, Trades Today, Signals Today, Win Rate
- **Equity Curve**: Area chart showing portfolio equity over time
- **Daily P&L**: Bar chart of daily profit/loss
- **Recent Signals**: Last 8 signals with symbol, side, strategy, confidence
- **Recent Trades**: Last 8 trades with entry price and P&L
- **Bot Controls**: Start/Stop bot in paper mode

### 2. Trade Monitor (/trades)
Detailed view with four tabs:
- **Orders**: All orders with ID, symbol, side, quantity, type, fill price, status, timestamp
- **Trades**: Completed trades with entry/exit prices, P&L, net P&L, fees
- **Positions**: Open/closed positions with avg price, current price, unrealized/realized P&L
- **Signals**: Generated signals with confidence %, reason, stop loss, take profit

### 3. Backtest Lab (/backtest)
Configure and run backtests:
- Select strategy (SMA Crossover / Opening Range Breakout)
- Select symbol, date range, initial capital, quantity
- Metrics grid: Return %, Net P&L, Trades, Win Rate, Max DD, Sharpe, Profit Factor, Expectancy
- Equity curve chart with dynamic coloring
- Trade-by-trade results table
- Previous backtests history

### 4. Strategy Optimizer (/optimizer)
Parameter grid search with visualization:
- Configure parameter ranges (min/max/step for each parameter)
- Add/remove custom parameters
- Live combination counter
- **Heatmap**: 2D color-coded grid showing metric values across parameter space
- **Metric Selector**: Switch between Return %, Sharpe Ratio, Win Rate, Max Drawdown
- **Best Parameters Banner**: Highlights optimal combination
- **Full Results Table**: All combinations sortable by any column
- Previous optimization history

### 5. Strategy Editor (/strategies)
Configure strategy parameters:
- Tab per strategy with info, parameters, and instrument configuration
- Enable/disable toggle
- Quantity per trade
- Custom symbol lists (comma-separated)
- Save/reset functionality

### 6. Risk Controls (/risk)
Safety guardrails:
- **Kill Switch**: Large toggle with glowing red activation effect
- **Loss Limits**: Max daily loss (INR), max daily loss (%), max consecutive losses, max slippage
- **Position Limits**: Max position size, max position value, max open positions, max orders/day
- **Safety Controls**: Cooldown timer, circuit breaker toggle, no-trade windows
- **Symbol Filters**: Whitelist and blacklist

### 7. Settings (/settings)
System configuration:
- **Credentials**: Zerodha API Key, Secret, Access Token, Redirect URL
- **Trading**: Mode (Paper/Live), Capital, Exchange, Auto square-off time, Live ticks toggle
- **System**: Health status, Initialize DB, Sync Instruments, Instruments table
- **Alerts**: Telegram bot token/chat ID, Webhook URL

---

## Trading Bot Core

### Models (`trading_bot/models.py`)

All data structures use **Pydantic v2 models** with type hints:

| Model | Description |
|-------|-------------|
| `Signal` | Normalized trading signal (symbol, side, confidence, stop_loss, take_profit, strategy_name) |
| `Order` | Broker order (symbol, side, quantity, order_type, price, status, broker_order_id) |
| `Trade` | Executed trade (entry_price, exit_price, pnl, fees, net_pnl, duration) |
| `Position` | Open/closed position (avg_price, current_price, unrealized_pnl) |
| `Instrument` | Tradeable instrument (tradingsymbol, exchange, lot_size, tick_size) |
| `BacktestResult` | Full backtest output (metrics, equity_curve, trades, parameters) |
| `RiskConfig` | Risk control settings (max_daily_loss, kill_switch, limits) |
| `StrategyConfig` | Strategy configuration (parameters, symbols, enabled) |
| `AppSettings` | Application settings (trading_mode, credentials, capital) |

### Enums (`trading_bot/enums.py`)

```python
TradingMode: PAPER | LIVE
Side: BUY | SELL
OrderType: MARKET | LIMIT | SL | SL_M
OrderStatus: PENDING | OPEN | COMPLETE | CANCELLED | REJECTED
ProductType: MIS (Intraday) | CNC (Delivery) | NRML (F&O)
Exchange: NSE | BSE | NFO | MCX | CDS
BotStatus: IDLE | RUNNING | STOPPED | ERROR
Timeframe: 1m | 3m | 5m | 15m | 30m | 60m | day | week | month
```

### Configuration (`trading_bot/config.py`)

- **Market Hours**: 09:15 - 15:30 IST (with pre-open 09:00 - 09:08)
- **Default Instruments**: RELIANCE, INFY, TCS, HDFCBANK, NIFTY 50, BANKNIFTY, SBIN, ITC
- **Fee Calculation**: Brokerage (Rs.20 flat), STT (0.025% sell), Transaction charges, GST (18%), SEBI charges, Stamp duty
- **Slippage**: Default 5 basis points

---

## Strategies

### Strategy Interface

All strategies extend `StrategyBase` and implement:

```python
class StrategyBase(ABC):
    def warmup(self, candles: List[Dict]) -> None:
        """Feed historical candles for indicator warmup."""

    @abstractmethod
    def on_candle(self, candle: Dict) -> Optional[Signal]:
        """Process a new candle. Return Signal if conditions met."""

    def on_tick(self, tick: Dict) -> Optional[Signal]:
        """Process a live tick. Override if needed."""

    def parameters(self) -> Dict[str, Any]:
        """Return current parameter values."""

    def reset(self) -> None:
        """Reset internal state for fresh run."""
```

### SMA Crossover (`sma_crossover`)

**Logic**: Generates BUY when fast SMA crosses above slow SMA, SELL when it crosses below.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `fast_period` | 9 | Fast SMA lookback period |
| `slow_period` | 21 | Slow SMA lookback period |
| `signal_threshold` | 0.0 | Minimum SMA difference threshold |
| `volume_filter` | false | Enable volume confirmation |
| `min_volume_multiplier` | 1.5 | Minimum volume vs 20-period average |

**Signal output**:
- Side: BUY or SELL
- Confidence: Scaled by SMA divergence magnitude (0.5 to 0.95)
- Stop Loss: 2% from entry (BUY), 2% above (SELL)
- Take Profit: 4% from entry (BUY), 4% below (SELL)
- Prevents duplicate signals (no consecutive same-side signals)

### Opening Range Breakout (`opening_range_breakout`)

**Logic**: Defines a price range in the first N minutes of market open. BUY on breakout above range high, SELL on breakdown below range low.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `opening_range_minutes` | 15 | Number of candles to form the opening range |
| `breakout_buffer_pct` | 0.1 | Buffer percentage above/below range for confirmation |
| `volume_confirmation` | true | Require volume confirmation |
| `min_range_pct` | 0.3 | Minimum range size (skip if too narrow) |
| `max_range_pct` | 2.0 | Maximum range size (skip if too wide) |

**Signal output**:
- Stop Loss: Range low (for BUY), Range high (for SELL)
- Take Profit: Symmetric to stop loss distance
- One signal per day maximum

---

## Backtesting

### How It Works

1. **Data Generation**: Paper broker generates synthetic OHLCV candles with trend + noise
2. **Warmup**: First N candles feed indicator warmup (e.g., 23 candles for SMA(21))
3. **Candle Processing**: Each subsequent candle runs through the strategy's `on_candle()`
4. **Fill Simulation**: Signals get simulated fills with slippage (5 bps) and realistic fees
5. **Position Tracking**: Open positions tracked; opposite signals close existing positions
6. **End of Test**: Any remaining open position force-closed at last candle price
7. **Metrics**: Comprehensive performance metrics calculated

### Backtest Metrics

| Metric | Description |
|--------|-------------|
| **Total Return** | Absolute P&L in INR |
| **Total Return %** | Percentage return on initial capital |
| **CAGR** | Compound Annual Growth Rate |
| **Win Rate** | Percentage of profitable trades |
| **Max Drawdown** | Largest peak-to-trough decline (%) |
| **Sharpe Ratio** | Risk-adjusted return (annualized, simplified) |
| **Profit Factor** | Gross profit / Gross loss |
| **Expectancy** | Average P&L per trade |
| **Avg Win / Avg Loss** | Average winning and losing trade P&L |
| **Total Trades** | Number of completed trades |
| **Avg Trade Duration** | Mean trade holding time |

### Sample Backtest (via API)

```bash
curl -X POST http://localhost:8001/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "sma_crossover",
    "symbol": "RELIANCE",
    "start_date": "2024-01-01",
    "end_date": "2025-06-01",
    "initial_capital": 100000,
    "quantity": 10
  }'
```

---

## Strategy Optimizer

The optimizer runs a **grid search** across parameter ranges, executing backtests for every combination and producing a heatmap visualization.

### How It Works

1. **Define Ranges**: Set min/max/step for each parameter (e.g., fast_period: 5-20 step 1)
2. **Generate Grid**: All parameter combinations enumerated (up to 2500 max)
3. **Batch Backtest**: Each combination runs a full backtest on the same candle data
4. **Rank Results**: Results sorted by selected metric (return %, Sharpe, etc.)
5. **Heatmap**: First two parameters form X/Y axes, cells colored by performance

### Sample Optimization (via API)

```bash
curl -X POST http://localhost:8001/api/optimizer/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "sma_crossover",
    "symbol": "RELIANCE",
    "start_date": "2024-01-01",
    "end_date": "2025-06-01",
    "initial_capital": 100000,
    "quantity": 10,
    "param_ranges": {
      "fast_period": {"min": 5, "max": 20, "step": 1},
      "slow_period": {"min": 15, "max": 50, "step": 5}
    }
  }'
```

**Response includes**:
- `best_params`: Winning parameter combination
- `best_return_pct`: Best return achieved
- `heatmap`: 2D grid with x/y values and metric values per cell
- `results`: All combinations sorted by return descending

### Heatmap Metrics

The heatmap can be viewed with different metrics:
- **Return %**: Total return percentage (default)
- **Sharpe Ratio**: Risk-adjusted return
- **Win Rate %**: Percentage of winning trades
- **Max Drawdown %**: Largest decline (inverted coloring - lower = greener)

---

## Risk Controls

### Pre-Trade Checks (11 Rules)

Every signal must pass **all** checks before order placement:

| # | Check | Description |
|---|-------|-------------|
| 1 | Kill Switch | Hard stop - blocks all trading when active |
| 2 | Daily Loss (INR) | Blocks if daily P&L exceeds max_daily_loss |
| 3 | Daily Loss (%) | Blocks if daily loss exceeds % of capital |
| 4 | Max Orders/Day | Blocks if daily order count exceeded |
| 5 | Max Open Positions | Blocks if too many positions open |
| 6 | Position Size | Blocks if quantity exceeds max_position_size |
| 7 | Position Value | Blocks if qty * price exceeds max_position_value |
| 8 | Symbol Allowed | Blocks blacklisted symbols / non-whitelisted symbols |
| 9 | No-Trade Window | Blocks during configured time windows |
| 10 | Cooldown | Blocks if too soon after last exit |
| 11 | Consecutive Losses | Blocks after N consecutive losing trades |
| 12 | Duplicate Signal | Blocks repeated same-direction signals |

### Position Sizing Helpers

```python
# Fixed quantity
size_fixed_quantity(10)  # Always 10 shares

# Fixed capital per trade
size_fixed_capital(50000, price=2450)  # 50k / 2450 = 20 shares

# Percent of capital
size_percent_of_capital(100000, pct=5, price=2450)  # 5% of 100k = 2 shares

# Risk per trade
size_risk_per_trade(100000, risk_pct=1, entry_price=2450, stop_loss=2400)
# 1% of 100k = 1000 risk, 2450-2400 = 50 per share, 1000/50 = 20 shares
```

### Kill Switch

The kill switch provides an **instant emergency stop**:
- Activatable from dashboard UI, API, or CLI
- Blocks ALL signal processing and order placement
- Persisted to database (survives restarts)
- Visual indicator on dashboard (pulsing red badge)

```bash
# Activate kill switch
curl -X POST "http://localhost:8001/api/risk/kill-switch?active=true&reason=Market+crash"

# Deactivate kill switch
curl -X POST "http://localhost:8001/api/risk/kill-switch?active=false"
```

---

## Broker Integration

### Paper Broker (Default)

The `PaperBroker` provides realistic simulation:
- **Simulated fills**: Instant market order fills, limit order price matching
- **Slippage**: Configurable basis points (default: 5 bps)
- **Fee calculation**: Full Indian NSE fee structure (brokerage, STT, GST, SEBI, stamp)
- **Position tracking**: Maintains internal position state with P&L
- **Price simulation**: Small random jitter on each price query
- **Historical data**: Generates synthetic OHLCV candles with trend + noise

### Zerodha Kite Connect (Live)

The `ZerodhaBroker` wraps the official KiteConnect Python SDK:

**Setup Steps:**
1. Register at [kite.trade](https://kite.trade) (Kite Connect Developer Portal)
2. Create an app to get API Key and API Secret
3. Set credentials in Settings > Credentials page
4. Complete the login flow to generate an Access Token
5. Token refreshes daily (Zerodha invalidates at ~6 AM IST)

**Supported operations:**
- `authenticate()` - Verify credentials and set access token
- `get_profile()` - Fetch user account details
- `get_instruments(exchange)` - Fetch all tradeable instruments
- `get_ltp(symbols)` - Get last traded prices
- `get_historical_data()` - Fetch OHLCV candles
- `place_order()` - Place market/limit/SL/SL-M orders
- `modify_order()` / `cancel_order()` - Order management
- `get_orders()` / `get_positions()` / `get_holdings()` - Portfolio queries
- `generate_session(request_token)` - Generate access token from login redirect

---

## API Reference

All endpoints are prefixed with `/api`.

### Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/summary` | Dashboard overview metrics |
| GET | `/api/health` | System health check |

### Bot Control
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/bot/start` | Start the trading bot |
| POST | `/api/bot/stop` | Stop the trading bot |
| GET | `/api/bot/status` | Current bot status |
| GET | `/api/bot/runs` | Historical bot run records |

### Signals
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/signals` | List signals (filter by strategy, symbol, status) |
| POST | `/api/signals/generate` | Manually generate signals for testing |

### Orders
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/orders` | List orders (filter by status) |
| POST | `/api/orders/place` | Manually place an order |

### Trades & Positions
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/trades` | List trades (filter by status) |
| GET | `/api/positions` | List positions (filter by status) |

### Strategies
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/strategies` | List all strategies with configs |
| PUT | `/api/strategies/{name}` | Update strategy configuration |

### Risk
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/risk/config` | Get risk configuration |
| PUT | `/api/risk/config` | Update risk configuration |
| POST | `/api/risk/kill-switch` | Toggle kill switch (active, reason) |

### Backtesting
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/backtest/run` | Run a backtest |
| GET | `/api/backtest/results` | List past backtest results |
| GET | `/api/backtest/results/{id}` | Get specific backtest detail |

### Optimizer
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/optimizer/run` | Run parameter optimization grid search |
| GET | `/api/optimizer/results` | List past optimization results |
| GET | `/api/optimizer/results/{id}` | Get specific optimization detail with heatmap |

### Settings & Instruments
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings` | Get application settings |
| PUT | `/api/settings` | Update application settings |
| GET | `/api/instruments` | List instruments |
| POST | `/api/instruments/sync` | Sync instruments from broker |
| POST | `/api/init` | Initialize database with defaults |

### Metrics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/metrics/equity-curve` | Equity curve from trade history |
| GET | `/api/metrics/daily-pnl` | Daily P&L aggregation |

---

## Configuration

### Environment Variables

| Variable | Location | Description | Default |
|----------|----------|-------------|---------|
| `MONGO_URL` | backend/.env | MongoDB connection string | - |
| `DB_NAME` | backend/.env | Database name | - |
| `REACT_APP_BACKEND_URL` | frontend/.env | Backend API base URL | - |

### Application Settings (via Dashboard or API)

| Setting | Default | Description |
|---------|---------|-------------|
| `trading_mode` | `paper` | paper or live |
| `kite_api_key` | `` | Zerodha API key |
| `kite_api_secret` | `` | Zerodha API secret |
| `kite_access_token` | `` | Zerodha access token |
| `default_exchange` | `NSE` | Default exchange |
| `capital` | `100000` | Trading capital (INR) |
| `timezone` | `Asia/Kolkata` | Trading timezone |
| `enable_ticks` | `false` | Enable live tick streaming |
| `auto_square_off_time` | `15:15` | Auto square-off time |
| `telegram_bot_token` | `` | Telegram alert bot token |
| `telegram_chat_id` | `` | Telegram alert chat ID |
| `webhook_url` | `` | Webhook alert URL |

### Risk Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `max_daily_loss` | `5000` | Max daily loss in INR |
| `max_daily_loss_pct` | `5.0` | Max daily loss as % of capital |
| `max_position_size` | `100` | Max shares per position |
| `max_position_value` | `50000` | Max position value in INR |
| `max_open_positions` | `5` | Max concurrent open positions |
| `max_orders_per_day` | `50` | Max orders per trading day |
| `cooldown_seconds` | `60` | Cooldown after trade exit |
| `max_consecutive_losses` | `5` | Stop after N consecutive losses |
| `max_slippage_pct` | `1.0` | Circuit breaker slippage threshold |
| `kill_switch_active` | `false` | Emergency kill switch |

---

## Paper Trading Walkthrough

### Step 1: Start the Bot
Navigate to the Dashboard and click **Start Bot**. This will:
- Initialize the paper broker
- Run the SMA Crossover strategy on RELIANCE and INFY
- Generate signals from synthetic historical data
- Execute signals through the paper broker with simulated fills
- Record all signals, orders, trades, and positions to the database

### Step 2: Monitor Activity
- **Dashboard**: Watch metrics update (P&L, trades, signals)
- **Trade Monitor > Orders**: See filled paper orders with simulated prices
- **Trade Monitor > Trades**: See completed trades with P&L
- **Trade Monitor > Signals**: See generated BUY/SELL signals with reasons

### Step 3: Run a Backtest
Go to **Backtest Lab**:
1. Select "SMA Crossover" strategy
2. Select "RELIANCE" symbol
3. Set date range: 2024-01-01 to 2025-06-01
4. Capital: 100,000 INR, Quantity: 10
5. Click **Run Backtest**
6. Review equity curve, metrics, and trade table

### Step 4: Optimize Parameters
Go to **Optimizer**:
1. Set fast_period range: 5 to 20, step 1
2. Set slow_period range: 15 to 50, step 5
3. Click **Run Optimizer** (128 combinations)
4. Review heatmap to identify sweet spots
5. Note the best parameters from the green banner
6. Apply those parameters in the Strategy Editor

### Step 5: Configure Risk
Go to **Risk Controls**:
1. Set max daily loss to your comfort level
2. Set position limits
3. Verify kill switch is OFF
4. Save changes

---

## Paper-to-Live Migration Checklist

Before enabling live trading, verify every item:

- [ ] **Credentials**: Zerodha API Key, Secret, and Access Token configured in Settings
- [ ] **Token Refresh**: Understand that access tokens expire daily (~6 AM IST)
- [ ] **Paper Results**: Strategy has been paper-traded for at least 2 weeks
- [ ] **Backtest Verified**: Strategy shows positive metrics across multiple time periods
- [ ] **Risk Config**: All risk limits set to conservative values
- [ ] **Kill Switch**: Kill switch is OFF but ready (you know how to activate it)
- [ ] **Capital**: Capital set to actual trading capital (start small)
- [ ] **Instruments**: Instruments synced from Zerodha (not just defaults)
- [ ] **Market Hours**: Bot configured to respect NSE market hours (09:15-15:30)
- [ ] **Auto Square-Off**: Auto square-off time set before 15:30
- [ ] **Slippage**: Understand that live slippage may differ from paper simulation
- [ ] **Monitoring**: Dashboard open and monitoring during live trading
- [ ] **Telegram Alerts**: Configured for trade notifications (recommended)
- [ ] **Emergency Plan**: Know how to activate kill switch and manually cancel orders
- [ ] **Start Small**: Begin with 1-2 instruments and minimal quantity

---

## Production Hardening Checklist

- [ ] Set `LOG_LEVEL=WARNING` for production
- [ ] Enable MongoDB authentication and SSL
- [ ] Set up MongoDB backups
- [ ] Configure rate limiting on API endpoints
- [ ] Set up HTTPS/TLS for the dashboard
- [ ] Implement access token auto-refresh logic
- [ ] Add server-side session management
- [ ] Set up monitoring/alerting (Prometheus, Grafana, or similar)
- [ ] Add retry logic for broker API calls (network issues)
- [ ] Implement WebSocket reconnection handling
- [ ] Add database indexes for query performance
- [ ] Set up log rotation and archival
- [ ] Test failover scenarios (database down, broker API down)
- [ ] Implement audit logging for all configuration changes
- [ ] Set CORS to specific origins (not wildcard)

---

## Troubleshooting

### Authentication Issues

**"No access token set"**
- Access tokens expire daily. Re-generate via the Zerodha login flow.
- Check Settings > Credentials for correct API Key and Secret.

**"kiteconnect not installed"**
- Run: `pip install kiteconnect`

### Session/Token Issues

**Token expired at 6 AM**
- Zerodha invalidates tokens around 6 AM IST daily.
- Implement a cron job or startup check to re-authenticate.

### Order Placement Issues

**"Max orders/day reached"**
- Increase `max_orders_per_day` in Risk Controls.
- Or wait for daily reset.

**"Kill switch is ACTIVE"**
- Go to Risk Controls and deactivate the kill switch.

**"Symbol blacklisted"**
- Check the symbol blacklist in Risk Controls.

### Database Issues

**"MongoDB connection failed"**
- Verify `MONGO_URL` in backend/.env
- Check that MongoDB is running

### Frontend Issues

**Dashboard shows "Loading..."**
- Check backend is running on port 8001
- Verify `REACT_APP_BACKEND_URL` in frontend/.env
- Check browser console for CORS errors

---

## Strategy Development Guide

### Creating a New Strategy

1. Create your strategy class extending `StrategyBase`:

```python
# In trading_bot/strategies.py

class MyStrategy(StrategyBase):
    name = "my_strategy"
    display_name = "My Custom Strategy"
    description = "Description of what it does."
    default_params = {
        "lookback": 20,
        "threshold": 0.5,
    }

    def __init__(self, params=None):
        super().__init__(params)
        self._warmup_period = self.params["lookback"] + 5

    def on_candle(self, candle):
        self._candle_buffer.append(candle)
        if len(self._candle_buffer) < self._warmup_period:
            return None

        # Your signal logic here
        # Return Signal(...) when conditions met
        # Return None otherwise
        return None
```

2. Register it in `STRATEGY_REGISTRY`:

```python
STRATEGY_REGISTRY["my_strategy"] = MyStrategy
```

3. The strategy will automatically appear in:
   - Strategy Editor page
   - Backtest Lab dropdown
   - Optimizer dropdown
   - Bot start options

### Strategy Rules
- **Never import broker modules** - strategies must be broker-agnostic
- **Always return Signal objects** - normalized output format
- **Manage your own buffer** - trim old candles to prevent memory growth
- **Use warmup period** - ensure enough data before generating signals
- **Set stop_loss and take_profit** on every signal
- **Include a reason string** - for auditability

---

## Future Roadmap

### P1 - High Priority
- [ ] **Live Tick Integration**: WebSocket consumer with queue-based design for real-time data
- [ ] **Zerodha Auth Flow**: OAuth redirect flow for automated session generation
- [ ] **Trade Journal Export**: CSV/PDF export of trade history
- [ ] **Telegram Alerts**: Send trade notifications when bot token configured
- [ ] **Real Historical Data**: Fetch candles from Zerodha API instead of synthetic data

### P2 - Medium Priority
- [ ] **Walk-Forward Optimization**: Train/test split to reduce overfitting
- [ ] **CLI Interface**: Typer-based CLI (init-db, backtest, paper-trade, kill-switch)
- [ ] **Multi-Symbol Strategy**: Run strategies across multiple symbols simultaneously
- [ ] **Candlestick Charts**: Interactive price charts with indicator overlays
- [ ] **3D Surface Plot**: 3+ parameter optimization visualization
- [ ] **Optimization Export**: CSV/JSON export of optimization results

### P3 - Nice to Have
- [ ] **ML Signal Module**: TensorFlow/PyTorch hooks for ML-based signal generation
- [ ] **Options Strategies**: Support for F&O instruments
- [ ] **Portfolio-Level Risk**: Cross-strategy risk management
- [ ] **Additional Brokers**: Abstract broker interface for Upstox, Angel, etc.
- [ ] **Real-Time Dashboard**: WebSocket push instead of polling
- [ ] **Mobile Dashboard**: Responsive mobile-optimized views
- [ ] **Strategy Marketplace**: Share/import community strategies

---

## License

This project is for personal use and educational purposes. Use at your own risk. Trading in financial markets involves substantial risk of loss.

---

## Disclaimer

**This software is for educational and experimental purposes only.** It is not financial advice. Trading in financial markets involves significant risk of loss. The authors are not responsible for any financial losses incurred through the use of this software. Always paper-trade thoroughly before considering live trading, and never trade with money you cannot afford to lose.
