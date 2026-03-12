# KiteAlgo - Algorithmic Trading Platform PRD

## Original Problem Statement
Build a production-style, end-to-end Python algorithmic trading bot for Indian markets using the Zerodha Kite Connect API. Self-controlled, modular, auditable, and testable codebase with a lightweight dashboard.

## Core Requirements
- **Broker:** Zerodha Kite Connect (paper + live modes)
- **Language:** Python 3.11+ / React frontend
- **Database:** MongoDB
- **Interface:** Web dashboard + future CLI

## Architecture
- **Frontend:** React + TailwindCSS + Shadcn/UI + Recharts + lightweight-charts
- **Backend:** FastAPI + Pydantic + motor (async MongoDB)
- **Key modules:** backtest, trendshift, ml_signals, walk_forward, job_queue, indicators, broker_paper, broker_zerodha, alerts, portfolio_risk

## What's Been Implemented

### Core Backend
- Dashboard summary API with real-time metrics
- Bot start/stop with paper trading
- Signal generation, order execution, trade tracking
- Position management
- Risk controls with kill switch
- Instrument management

### Backtesting & Optimization
- BacktestEngine with full equity curve, trade tracking, slippage modeling
- **Lightweight mode** for optimizer/walk-forward (memory-efficient, metrics-only)
- Parameter grid search optimizer with objective scoring
- Walk-forward optimization with train/test windows
- Job queue system for long-running analysis tasks
- Chunked result storage in MongoDB

### TrendShift Strategy
- Multi-indicator strategy: EMA ribbon, RSI, MACD, Supertrend, Bollinger Bands
- Demand/supply zone detection
- **ML Regime Filter** (RandomForest-based market direction prediction)
- Slippage-aware signal generation
- Configurable via UI with presets (Safe/Balanced/Deep)

### ML Integration
- SklearnSignalModel with RandomForest classifier
- Market direction predictions with caching
- Integrated into TrendShift via `use_ml_filter` parameter
- UI toggle in BacktestLab and Optimizer pages

### Zerodha Integration
- OAuth flow endpoints (start, callback, status)
- Skeleton ZerodhaBroker (needs live credentials)

### Alerts
- Telegram alerts module (configurable, not yet connected to live bot)
- Webhook support

### Frontend Pages
- Dashboard (metrics, equity curve, daily P&L, signals, trades)
- Trade Monitor
- Backtest Lab (with ML toggle, job queue integration)
- Strategy Editor
- Risk Controls
- Optimizer (heatmap, results table, presets, ML toggle, save defaults)
- Trade Journal (with CSV/JSON export)
- Market Charts (candlestick with indicators)
- Settings (Zerodha config, alerts config)

## P0 Issues (Resolved)
- **Memory Exhaustion** - Fixed with:
  - Lightweight BacktestEngine mode (skips equity_curve/trades storage)
  - gc.collect() every 25 iterations in optimizer/walk-forward
  - Hard cap of 2000 optimizer combinations
  - Cancelled old 227K-combination stuck job

## Prioritized Backlog

### P1 - Next
- Telegram Alerts integration (keep configurable)
- Live Tick Integration (WebSocket consumer)
- CLI Development (typer-based)
- End-to-end testing of Zerodha Auth flow (needs credentials)

### P2 - Future
- Portfolio risk management module integration
- Deeper ML signal enhancements
- Options strategies support
- Multi-broker support
- Walk-Forward Lab page improvements

### P3 - Backlog
- Refactor optimization logic into separate service module
- Add comprehensive pytest test suite
- Performance profiling under load

## Documentation
- README.md: Comprehensive project documentation (updated 2026-03-12)
- CHANGELOG.md: Version history and changes
- .gitignore: Clean gitignore for GitHub push
