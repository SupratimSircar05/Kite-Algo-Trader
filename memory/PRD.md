# KiteAlgo - Algo Trading Bot PRD

## Original Problem Statement
Build a production-style, end-to-end Python algo trading bot for Indian markets using Zerodha Kite Connect APIs with a web-based monitoring dashboard.

## Architecture
- **Backend**: FastAPI + MongoDB + Trading Bot Core Modules
- **Frontend**: React + Shadcn/UI + Recharts + Dark Theme Dashboard
- **Trading Bot**: Paper Broker, SMA Crossover Strategy, ORB Strategy, Risk Controls, Backtest Engine

## User Personas
- Quantitative traders experimenting with algo strategies
- Indian market participants wanting full control over trading systems
- Developers building custom trading strategies

## Core Requirements (Static)
1. Paper trading mode by default (NEVER auto-live)
2. Strategy logic decoupled from broker logic
3. Strong risk controls with kill switch
4. Backtesting with equity curves and metrics
5. Web dashboard for monitoring and control
6. Easy configuration for Zerodha credentials later

## What's Been Implemented (March 2026)
### Backend Trading Bot Modules
- `/app/backend/trading_bot/` - Complete trading bot core
  - `models.py` - All Pydantic models (Signal, Order, Trade, Position, Backtest, Risk, etc.)
  - `enums.py` - Trading enumerations (Side, OrderType, Status, etc.)
  - `config.py` - IST timezone, market hours, fees calculation, default instruments
  - `broker_base.py` - Abstract broker interface
  - `broker_paper.py` - Full paper trading broker with simulated fills, slippage, fees
  - `broker_zerodha.py` - Zerodha Kite Connect broker (ready for credentials)
  - `strategies.py` - SMA Crossover + Opening Range Breakout strategies
  - `risk.py` - Risk manager with 11+ checks, kill switch, position sizing helpers
  - `execution.py` - Order manager, trade engine with PnL tracking
  - `backtest.py` - Backtesting engine with Sharpe, CAGR, drawdown, equity curve
  - `trendshift.py` - Proprietary multi-factor TrendShift strategy with demand/supply zones
  - `alerts.py` - Telegram/webhook alert manager with graceful safe-skip behavior
  - `walk_forward.py` - Walk-forward optimization engine for out-of-sample testing
  - `live_ticks.py` - Zerodha ticker buffer/consumer foundation for live streaming
  - `ml_signals.py` - ML signal service hooks for future sklearn-based predictions
  - `portfolio_risk.py` - Portfolio-level exposure and sector risk analyzer

### FastAPI API Endpoints
- Dashboard summary, bot start/stop, signals, orders, trades, positions
- Strategy CRUD, risk config, kill switch toggle
- Backtest run/results, settings management
- Instruments, equity curve, daily PnL, health check
- Trade Journal APIs: `/api/journal`, `/api/journal/export`
- Chart APIs: `/api/chart/candles` with indicators, zones, TrendShift signal overlays
- Zerodha auth readiness APIs: `/api/auth/zerodha/start`, `/api/auth/zerodha/status`, `/api/auth/zerodha/callback`
- Walk-forward API alias: `/api/backtest/walk_forward`
- Alerts APIs: `/api/alerts/status`, `/api/alerts/test`, `/api/alerts/notify`
- Multi-symbol control: `/api/bot/start-multi`

### React Dashboard (8 pages)
- Dashboard Overview (metrics, equity curve, daily PnL, recent signals/trades)
- Trade Monitor (orders, trades, positions, signals tabs with filtering)
- Backtest Lab (configurable backtests with equity curves and trade tables)
- Strategy Editor (parameter config, instruments, enable/disable)
- Risk Controls (kill switch, loss limits, position limits, safety controls)
- Settings (Zerodha credentials, trading mode, alerts config, instruments)
- Trade Journal (filters, summary metrics, CSV/JSON export actions)
- Candlestick Lab (SVG candlestick chart, EMA/Supertrend overlays, TrendShift signal tape, demand/supply zones)

### Current Integration Status
- Zerodha auth flow is wired for safe start/status/callback handling, but real login/session validation still depends on user-provided credentials.
- Telegram/webhook alerts are wired with test/status endpoints and safe skips when credentials are absent.
- Paper broker remains the default execution path for all self-tests and UI verification.

## Test Results
- Iteration 1: Backend 95.7%, Frontend 100% after initial platform build
- Iteration 2: Backend 100%, Frontend 100% for optimizer feature
- Iteration 3: Backend 100%, Frontend 100% for journal/chart/auth/alert/walk-forward additions

## Prioritized Backlog
### P0 (Critical)
- [x] Paper trading broker
- [x] Dashboard with real data
- [x] Backtest engine
- [x] Risk controls with kill switch
- [x] Strategy editor

### P1 (Important)
- [x] Trade journal export (CSV/JSON)
- [x] Zerodha auth readiness flow (status/start/callback endpoints with safe handling)
- [x] Candlestick chart with indicators and TrendShift overlays
- [x] Alert configuration UI with safe Telegram/webhook test flow
- [ ] Live trading with validated real Zerodha credentials
- [ ] WebSocket live tick integration wired end-to-end to UI
- [ ] Real-time position updates
- [ ] Telegram live delivery validation with real credentials

### P2 (Nice to Have)
- [ ] ML signal module hooks
- [ ] Options strategies support
- [ ] Portfolio-level risk management
- [ ] Additional broker abstractions
- [x] Strategy parameter optimization
- [ ] Walk-forward optimization UI
- [ ] Multi-timeframe analysis
- [x] Candlestick chart with indicators

## Next Tasks
1. Validate Zerodha OAuth callback with real credentials and persist working access token lifecycle
2. Wire live tick streaming into dashboard/chart refresh flows
3. Add a dedicated walk-forward frontend lab page and result visualizations
4. Extend alerts from test/manual mode to trade/risk event delivery with real credentials
5. Build CLI commands (init-db, sync-instruments, backtest, paper-trade)

## Latest Update (March 12, 2026)
- Completed the in-progress feature batch from the previous fork by finishing the missing backend API layer and adding matching UI routes.
- Added Trade Journal and Candlestick Lab pages, TrendShift chart overlays, Zerodha auth readiness UX, alert testing UX, and walk-forward API coverage.
- Verified via self-tests plus testing agent iteration 3 (backend 100%, frontend 100%).

## Feature: Strategy Parameter Optimizer (March 2026)
### What was built
- Backend POST /api/optimizer/run: Grid search across parameter ranges, returns heatmap data + sorted results
- Backend GET /api/optimizer/results: List past optimizations
- Backend GET /api/optimizer/results/{id}: Load full optimization with heatmap
- Frontend /optimizer page: Config panel, heatmap visualization, sortable results table
- Dynamic parameter range editor (min/max/step per parameter)
- Add/remove custom parameters
- Metric selector (Return %, Sharpe Ratio, Win Rate, Max Drawdown)
- Color-coded heatmap with best cell highlighted
- Previous optimizations table with load functionality
- Max 2500 combinations safety limit
### Test Results: 100% pass rate (backend + frontend)
