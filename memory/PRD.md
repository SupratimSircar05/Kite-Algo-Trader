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

### FastAPI API Endpoints
- Dashboard summary, bot start/stop, signals, orders, trades, positions
- Strategy CRUD, risk config, kill switch toggle
- Backtest run/results, settings management
- Instruments, equity curve, daily PnL, health check

### React Dashboard (6 pages)
- Dashboard Overview (metrics, equity curve, daily PnL, recent signals/trades)
- Trade Monitor (orders, trades, positions, signals tabs with filtering)
- Backtest Lab (configurable backtests with equity curves and trade tables)
- Strategy Editor (parameter config, instruments, enable/disable)
- Risk Controls (kill switch, loss limits, position limits, safety controls)
- Settings (Zerodha credentials, trading mode, alerts config, instruments)

## Test Results
- Backend: 95.7% -> 100% after ObjectId fix
- Frontend: 100%
- Overall: 97.8% -> 100%

## Prioritized Backlog
### P0 (Critical)
- [x] Paper trading broker
- [x] Dashboard with real data
- [x] Backtest engine
- [x] Risk controls with kill switch
- [x] Strategy editor

### P1 (Important)
- [ ] Live trading flow with Zerodha auth redirect
- [ ] WebSocket live tick integration
- [ ] Real-time position updates
- [ ] Trade journal export (CSV/PDF)
- [ ] Telegram alerts when bot token configured

### P2 (Nice to Have)
- [ ] ML signal module hooks
- [ ] Options strategies support
- [ ] Portfolio-level risk management
- [ ] Additional broker abstractions
- [ ] Strategy parameter optimization
- [ ] Multi-timeframe analysis
- [ ] Candlestick chart with indicators

## Next Tasks
1. Implement Zerodha login flow (redirect auth)
2. Add WebSocket live tick integration
3. Trade journal with export functionality
4. Performance optimization for large datasets
5. CLI commands (init-db, sync-instruments, etc.)

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
