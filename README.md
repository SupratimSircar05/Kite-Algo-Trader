# KiteAlgo - Algorithmic Trading Platform for Indian Markets

A production-grade, end-to-end algo trading system for Indian markets using **Zerodha Kite Connect APIs**. Features a modular Python trading bot core with a professional React dashboard for monitoring, backtesting, strategy optimization, ML-powered signal generation, and risk management.

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
- [Walk-Forward Optimization](#walk-forward-optimization)
- [ML Signal Module](#ml-signal-module)
- [Risk Controls](#risk-controls)
- [Alerts & Notifications](#alerts--notifications)
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
- ML-powered regime filtering for smarter signal generation.

**Primary use cases:**
- Intraday and positional strategy experimentation
- Safe paper-trading with realistic simulated fills
- Backtesting strategies against historical data
- Parameter optimization with visual heatmaps
- Walk-forward analysis to reduce overfitting
- ML-enhanced directional prediction

---

## Architecture

```
+-----------------------------------------------------------+
|                    React Dashboard                         |
|  Dashboard | Trades | Backtest | Strategies | Risk | Opt  |
|  Charts | Walk-Forward | Trade Journal | Settings          |
+-----------------------------------------------------------+
         |  HTTP/REST (REACT_APP_BACKEND_URL/api)
+-----------------------------------------------------------+
|                   FastAPI Backend                          |
|  server.py - API endpoints, bot control, data serving     |
+-----------------------------------------------------------+
   |            |              |              |
+--------+  +----------+  +-----------+  +----------+
| Trading|  | MongoDB  |  | Paper     |  | Zerodha  |
| Bot    |  | (Motor   |  | Broker    |  | Kite     |
| Core   |  |  async)  |  | (Sim)     |  | Connect  |
|        |  |          |  |           |  | (Live)   |
| Strats |  | signals  |  | Slippage  |  |          |
| Risk   |  | orders   |  | Fees      |  | OAuth    |
| ML     |  | trades   |  | Position  |  | Orders   |
| Backtest| | positions|  | Tracking  |  | Data     |
| WalkFwd|  | results  |  |           |  |          |
| JobQueue| | jobs     |  |           |  |          |
+--------+  +----------+  +-----------+  +----------+
```

### Data Flow

1. **Signal Generation**: Strategy processes candles and emits normalized `Signal` objects
2. **ML Filtering** (optional): RandomForest regime filter confirms or rejects signals
3. **Risk Validation**: `RiskManager` runs 11+ pre-trade checks
4. **Order Execution**: `OrderManager` converts approved signals into broker orders
5. **Trade Tracking**: `TradeEngine` tracks lifecycle from entry to exit with P&L
6. **Storage**: All signals, orders, trades, and positions persisted to MongoDB
7. **Dashboard**: React frontend polls API for real-time updates

---

## Features

### Core Trading
- Paper & live trading modes with realistic simulation
- Multi-symbol bot execution
- 3 built-in strategies (SMA Crossover, Opening Range Breakout, TrendShift)
- ML-powered regime filtering (RandomForest)
- Kill switch for emergency stop
- Comprehensive risk controls (11+ pre-trade checks)

### Backtesting & Optimization
- Full backtesting engine with slippage modeling and fee simulation
- **Lightweight mode** for memory-efficient optimizer runs
- Parameter grid search optimizer with heatmap visualization
- Walk-forward optimization with train/test window splits
- Job queue system for long-running analysis tasks
- Save optimized parameters as strategy defaults

### ML Integration
- RandomForest-based market direction prediction
- Integrated as regime filter in TrendShift strategy
- Toggle ML on/off from the UI per backtest/optimization run
- Cached predictions for performance

### Dashboard & Monitoring
- Real-time metrics (P&L, equity curve, win rate, positions)
- Interactive candlestick charts with indicator overlays
- Trade journal with CSV/JSON export
- Demand/supply zone visualization
- TrendShift signal markers on charts

### Alerts (Configurable)
- Telegram bot notifications
- Webhook alerts
- Bot status and kill switch alerts

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, Motor (async MongoDB) |
| **Frontend** | React 18, Tailwind CSS, Shadcn/UI, Recharts |
| **Charts** | Recharts (equity/P&L), lightweight-charts (candlestick) |
| **Database** | MongoDB |
| **ML** | scikit-learn (RandomForest) |
| **Broker SDK** | Zerodha KiteConnect Python SDK |
| **Job Queue** | Custom async job queue with MongoDB persistence |
| **Fees** | Indian NSE equity intraday fee model (STT, GST, SEBI, stamp duty) |

---

## Project Structure

```
app/
├── backend/
│   ├── server.py                    # FastAPI application (all API endpoints)
│   ├── .env                         # Environment variables (MONGO_URL, DB_NAME)
│   ├── requirements.txt             # Python dependencies
│   └── trading_bot/                 # Core trading bot modules
│       ├── __init__.py
│       ├── models.py                # Pydantic models (Signal, Order, Trade, etc.)
│       ├── enums.py                 # Enumerations (Side, OrderType, TradingMode)
│       ├── config.py                # Market hours, fees, instruments, IST timezone
│       ├── broker_base.py           # Abstract broker interface
│       ├── broker_paper.py          # Paper trading broker (simulated fills)
│       ├── broker_zerodha.py        # Zerodha Kite Connect implementation
│       ├── strategies.py            # Strategy base + SMA Crossover + ORB
│       ├── trendshift.py            # TrendShift strategy (ML-enhanced)
│       ├── indicators.py            # Technical indicators (EMA, RSI, MACD, ATR, etc.)
│       ├── ml_signals.py            # ML signal service (RandomForest)
│       ├── risk.py                  # Risk manager (11+ checks), kill switch
│       ├── execution.py             # Order manager, trade engine, P&L tracking
│       ├── backtest.py              # Backtesting engine (full + lightweight modes)
│       ├── walk_forward.py          # Walk-forward optimization engine
│       ├── job_queue.py             # Async job queue for long-running tasks
│       ├── alerts.py                # Telegram + webhook alert manager
│       ├── live_ticks.py            # Live tick WebSocket consumer
│       └── portfolio_risk.py        # Portfolio-level risk analysis
├── frontend/
│   ├── .env                         # REACT_APP_BACKEND_URL
│   ├── package.json
│   └── src/
│       ├── App.js                   # React router with all pages
│       ├── pages/
│       │   ├── Dashboard.js         # Overview with metrics, charts, activity
│       │   ├── TradeMonitor.js      # Orders, trades, positions, signals tabs
│       │   ├── BacktestLab.js       # Backtesting with ML toggle
│       │   ├── Optimizer.js         # Parameter optimization with heatmap
│       │   ├── StrategyEditor.js    # Strategy parameter configuration
│       │   ├── RiskControls.js      # Risk limits and kill switch
│       │   ├── MarketCharts.js      # Candlestick charts with indicators
│       │   ├── TradeJournal.js      # Trade history with export
│       │   └── Settings.js          # Credentials, alerts, system config
│       └── components/
│           ├── Sidebar.js           # Navigation sidebar
│           ├── CandlestickChart.js  # lightweight-charts wrapper
│           └── ui/                  # Shadcn/UI components
└── memory/
    └── PRD.md                       # Product requirements document
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
git clone <your-repo-url>
cd kitealgo

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
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
# Terminal 1: MongoDB
mongod

# Terminal 2: Backend
cd backend
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Terminal 3: Frontend
cd frontend
yarn start
```

### 4. First Steps

Open `http://localhost:3000`:
1. **Settings** > Initialize DB and Sync Instruments
2. **Dashboard** > Start Bot (generates demo data)
3. **Backtest Lab** > Run your first TrendShift backtest
4. **Optimizer** > Find optimal parameters with heatmap
5. **Charts** > View candlestick charts with indicators

---

## Dashboard Pages

### 1. Dashboard (`/`)
Main overview: Daily P&L, Total P&L, Open Positions, Trades Today, Win Rate. Equity curve chart, Daily P&L bar chart, recent signals and trades tables, bot start/stop control.

### 2. Trade Monitor (`/trades`)
Four-tab view: Orders, Trades, Positions, Signals. Status filtering, color-coded P&L, detailed lifecycle tracking.

### 3. Backtest Lab (`/backtest`)
Run backtests with configurable parameters. **ML Regime Filter toggle** for TrendShift. Equity curve visualization, comprehensive metrics, trade-by-trade breakdown. Job queue for long backtests.

### 4. Strategy Optimizer (`/optimizer`)
Grid search with interactive heatmap. TrendShift presets (Safe/Balanced/Deep). **ML toggle**. Combination cap at 2000. Save best parameters as defaults. Job queue for large optimizations.

### 5. Strategy Editor (`/strategies`)
Configure parameters, enable/disable strategies, set instruments and quantity per strategy.

### 6. Risk Controls (`/risk`)
Kill switch with glowing activation. Loss limits, position limits, cooldown, circuit breaker, symbol whitelist/blacklist.

### 7. Market Charts (`/charts`)
Candlestick charts using lightweight-charts. EMA ribbon, RSI, MACD, Supertrend overlays. Demand/supply zones. TrendShift signal markers.

### 8. Trade Journal (`/journal`)
Trade history with summary statistics. CSV and JSON export. Filter by symbol, strategy, status, side.

### 9. Settings (`/settings`)
Zerodha credentials, trading mode, capital, Telegram alerts, webhook URL, system health, instruments.

---

## Trading Bot Core

### Models (`trading_bot/models.py`)

| Model | Description |
|-------|-------------|
| `Signal` | Trading signal (symbol, side, confidence, stop_loss, take_profit, strategy_name, metadata) |
| `Order` | Broker order (symbol, side, quantity, order_type, price, status) |
| `Trade` | Executed trade (entry/exit price, pnl, fees, net_pnl, duration) |
| `Position` | Open/closed position (avg_price, current_price, unrealized_pnl) |
| `BacktestResult` | Full backtest output (metrics, equity_curve, trades, parameters) |
| `RiskConfig` | Risk control settings |
| `AppSettings` | Application settings |

### Enums (`trading_bot/enums.py`)

```
TradingMode: PAPER | LIVE
Side: BUY | SELL
OrderType: MARKET | LIMIT | SL | SL_M
OrderStatus: PENDING | OPEN | COMPLETE | CANCELLED | REJECTED
BotStatus: IDLE | RUNNING | STOPPED | ERROR
```

---

## Strategies

### SMA Crossover (`sma_crossover`)
BUY when fast SMA crosses above slow SMA, SELL on cross below. Configurable periods, optional volume filter.

### Opening Range Breakout (`opening_range_breakout`)
Defines price range in first N minutes. BUY on breakout above range high, SELL on breakdown below range low.

### TrendShift (`trendshift`)
**Advanced multi-indicator strategy with ML regime confirmation:**

| Component | Details |
|-----------|---------|
| **EMA Ribbon** | Fast (8), Mid (21), Slow (55) - trend direction + spread |
| **RSI** | Momentum strength/weakness (14-period) |
| **MACD** | Histogram expansion for momentum confirmation |
| **Supertrend** | Trend flip detection (direction changes) |
| **Bollinger Bands** | Volatility assessment |
| **Volume** | Relative volume spike detection |
| **Demand/Supply Zones** | Swing-based zone confluence |
| **ML Regime Filter** | RandomForest directional prediction |
| **Slippage Estimation** | ATR + volume + gap-based expected slippage |

**Key parameters:**
- `min_confidence` (0.62): Minimum score to trigger signal
- `signal_edge` (0.06): Required edge over opposing signal
- `use_ml_filter` (true): Enable/disable ML predictions
- `ml_min_confidence` (0.57): ML prediction confidence threshold
- `ml_weight` (0.16): Weight of ML score in final signal

---

## Backtesting

### How It Works
1. Paper broker generates synthetic OHLCV candles with trend + noise
2. Strategy warms up on initial candles
3. Each candle runs through `on_candle()` or `batch_generate_signals()`
4. Fills simulated with realistic slippage and NSE fee structure
5. Comprehensive metrics computed at end

### Lightweight Mode
For optimizer and walk-forward runs, the engine uses `lightweight=True`:
- Skips equity curve and trade list storage
- Tracks only summary metrics (win/loss counts, P&L, Sharpe returns)
- ~90% memory reduction per backtest iteration
- Enables running 1000+ combinations without memory exhaustion

### Metrics
Total Return %, CAGR, Win Rate, Max Drawdown, Sharpe Ratio, Profit Factor, Expectancy, Avg Win/Loss, Avg Slippage BPS.

---

## Strategy Optimizer

Grid search across parameter ranges with **max 2000 combinations**:
1. Define ranges (min/max/step per parameter)
2. TrendShift presets: Safe, Balanced, Deep search
3. Heatmap visualization (Return %, Sharpe, Win Rate, Drawdown, Objective Score)
4. Save best parameters as strategy defaults
5. Jobs auto-queue for reliable processing

```bash
curl -X POST http://localhost:8001/api/optimizer/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "trendshift",
    "symbol": "RELIANCE",
    "start_date": "2024-01-01",
    "end_date": "2025-06-01",
    "param_ranges": {
      "min_confidence": {"min": 0.55, "max": 0.75, "step": 0.05},
      "sl_atr_mult": {"min": 1.0, "max": 2.0, "step": 0.25}
    },
    "fixed_params": {"use_ml_filter": true},
    "objective": "balanced"
  }'
```

---

## Walk-Forward Optimization

Splits data into N windows with train/test splits to detect overfitting:
1. Each window optimizes parameters on training data
2. Validates with best params on out-of-sample test data
3. Reports consistency score and overfit ratio per window
4. Identifies most robust parameters across all windows

---

## ML Signal Module

### RandomForest Regime Filter
- Trains on historical candle features (RSI, MACD, EMA cross, volume, ATR, BB position)
- Predicts market direction (BUY/SELL/HOLD) with confidence scores
- Cached predictions avoid re-training on same dataset
- Integrated into TrendShift strategy as optional filter
- Toggleable from BacktestLab and Optimizer UI

### Features Used
`rsi`, `macd_histogram`, `ema_cross`, `volume_relative`, `atr_pct`, `bb_position`, `ribbon_spread`, `gap_pct`

---

## Risk Controls

### Pre-Trade Checks (11 Rules)
| # | Check | Description |
|---|-------|-------------|
| 1 | Kill Switch | Hard stop - blocks all trading |
| 2 | Daily Loss (INR) | Max daily loss limit |
| 3 | Daily Loss (%) | Max daily loss percentage |
| 4 | Max Orders/Day | Daily order count limit |
| 5 | Max Open Positions | Concurrent position limit |
| 6 | Position Size | Max shares per position |
| 7 | Position Value | Max position value |
| 8 | Symbol Allowed | Blacklist/whitelist check |
| 9 | No-Trade Window | Time-based restrictions |
| 10 | Cooldown | Post-exit cooldown period |
| 11 | Consecutive Losses | Stop after N losses |

---

## Alerts & Notifications

- **Telegram**: Configure bot token and chat ID in Settings. Sends trade alerts, bot status, kill switch notifications.
- **Webhook**: Configure URL for HTTP POST notifications.
- Both are optional and configurable.

---

## Broker Integration

### Paper Broker (Default)
Realistic simulation with slippage (5 bps), NSE fee structure, position tracking, and deterministic synthetic data generation.

### Zerodha Kite Connect (Live)
OAuth flow implemented. Supports: authenticate, get_profile, get_instruments, get_ltp, get_historical_data, place_order, modify_order, cancel_order.

**Setup:** Register at [kite.trade](https://kite.trade), create app, configure credentials in Settings, complete OAuth login flow.

---

## API Reference

All endpoints prefixed with `/api`.

### Dashboard & Bot
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/summary` | Dashboard overview |
| POST | `/api/bot/start` | Start trading bot |
| POST | `/api/bot/stop` | Stop trading bot |
| POST | `/api/bot/start-multi` | Start multi-symbol bot |

### Backtesting
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/backtest/run` | Run backtest (queues if large) |
| GET | `/api/backtest/results` | List past results |
| GET | `/api/backtest/results/{id}` | Get detailed result |

### Optimizer
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/optimizer/run` | Run optimization (max 2000 combos) |
| GET | `/api/optimizer/results` | List past results |
| GET | `/api/optimizer/results/{id}` | Get detailed result with heatmap |
| POST | `/api/optimizer/results/{id}/apply-defaults` | Save best params as defaults |

### Walk-Forward
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/walkforward/run` | Run walk-forward optimization |
| GET | `/api/walkforward/results` | List past results |

### Charts & Data
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/chart/candles` | Candlestick data with indicators |
| GET | `/api/candles/{symbol}` | Symbol candle data |

### Trade Journal
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/journal` | Trade journal with summary |
| GET | `/api/journal/export` | Export CSV/JSON |

### ML
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ml/models` | List ML models |
| POST | `/api/ml/predict` | Get ML prediction |

### Job Queue
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/jobs` | List analysis jobs |
| GET | `/api/jobs/{id}` | Get job status/progress |

### Signals, Orders, Trades, Positions
| GET | `/api/signals` | `/api/orders` | `/api/trades` | `/api/positions` |

### Strategies, Risk, Settings
| GET/PUT | `/api/strategies` | `/api/risk/config` | `/api/settings` |
| POST | `/api/risk/kill-switch` | Toggle kill switch |

### Alerts
| POST | `/api/alerts/test` | Send test alert |
| POST | `/api/alerts/notify` | Send custom alert |
| GET | `/api/alerts/status` | Alert channel status |

### Auth (Zerodha)
| GET | `/api/auth/zerodha/start` | Get login URL |
| GET | `/api/auth/zerodha/callback` | OAuth callback |
| GET | `/api/auth/zerodha/status` | Auth status |

---

## Configuration

### Environment Variables

| Variable | Location | Description |
|----------|----------|-------------|
| `MONGO_URL` | backend/.env | MongoDB connection string |
| `DB_NAME` | backend/.env | Database name |
| `REACT_APP_BACKEND_URL` | frontend/.env | Backend API base URL |

### Application Settings (via Dashboard)

| Setting | Default | Description |
|---------|---------|-------------|
| `trading_mode` | `paper` | Paper or live |
| `capital` | `100000` | Trading capital (INR) |
| `kite_api_key` | - | Zerodha API key |
| `kite_api_secret` | - | Zerodha API secret |
| `telegram_bot_token` | - | Telegram alert bot token |
| `telegram_chat_id` | - | Telegram alert chat ID |
| `webhook_url` | - | Webhook alert URL |

---

## Paper Trading Walkthrough

1. **Start Bot**: Dashboard > Start Bot > generates demo signals/trades
2. **Monitor**: Watch metrics, equity curve, signals, trades update
3. **Backtest**: Backtest Lab > Select TrendShift > Run with ML filter on
4. **Optimize**: Optimizer > TrendShift with Balanced preset > Save best params
5. **Walk-Forward**: Validate that optimized params aren't overfit
6. **Charts**: View candlestick charts with TrendShift signals
7. **Risk**: Configure risk limits before going live

---

## Paper-to-Live Migration Checklist

- [ ] Zerodha credentials configured and OAuth flow completed
- [ ] Paper-traded for 2+ weeks with positive results
- [ ] Backtested across multiple time periods
- [ ] Walk-forward validation shows consistency
- [ ] Risk limits set conservatively
- [ ] Kill switch ready (know how to activate)
- [ ] Telegram alerts configured
- [ ] Start with minimal capital and 1-2 instruments
- [ ] Market hours and auto square-off configured

---

## Production Hardening Checklist

- [ ] MongoDB authentication and SSL enabled
- [ ] Database backups configured
- [ ] CORS restricted to specific origins
- [ ] Rate limiting on API endpoints
- [ ] HTTPS/TLS for dashboard
- [ ] Log rotation and monitoring
- [ ] Access token auto-refresh for Zerodha
- [ ] Retry logic for broker API calls

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Dashboard shows "Loading..." | Check backend is running, verify REACT_APP_BACKEND_URL |
| "Kill switch is ACTIVE" | Deactivate in Risk Controls |
| Token expired | Re-authenticate via Zerodha OAuth flow |
| Optimizer memory issues | Reduce combinations (max 2000), use lightweight mode |
| MongoDB connection failed | Check MONGO_URL in backend/.env |

---

## Strategy Development Guide

```python
from trading_bot.strategies import StrategyBase
from trading_bot.models import Signal

class MyStrategy(StrategyBase):
    name = "my_strategy"
    display_name = "My Strategy"
    description = "Custom strategy description"
    default_params = {"lookback": 20, "threshold": 0.5}

    def __init__(self, params=None):
        super().__init__(params)
        self._warmup_period = self.params["lookback"] + 5

    def on_candle(self, candle):
        self._candle_buffer.append(candle)
        if len(self._candle_buffer) < self._warmup_period:
            return None
        # Your signal logic here
        return None  # or Signal(...)

# Register in server.py:
STRATEGY_REGISTRY["my_strategy"] = MyStrategy
```

---

## Future Roadmap

### P1 - Next
- [ ] Telegram alerts integration (configurable)
- [ ] Live tick WebSocket integration
- [ ] CLI interface (typer-based)

### P2 - Medium Priority
- [ ] Portfolio-level risk management
- [ ] Deeper ML enhancements
- [ ] Real historical data from Zerodha API

### P3 - Future
- [ ] Options strategies support
- [ ] Multi-broker support (Upstox, Angel)
- [ ] Real-time WebSocket dashboard updates
- [ ] Strategy marketplace

---

## License

This project is for personal use and educational purposes. Use at your own risk.

## Disclaimer

**This software is for educational and experimental purposes only.** It is not financial advice. Trading in financial markets involves significant risk of loss. The authors are not responsible for any financial losses incurred through the use of this software. Always paper-trade thoroughly before considering live trading, and never trade with money you cannot afford to lose.
