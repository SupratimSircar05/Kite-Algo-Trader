# Changelog

All notable changes to KiteAlgo are documented here.

## [2026-03-12] - Memory Optimization & ML Integration

### Fixed
- **P0: Memory Exhaustion** - Optimizer and walk-forward runs no longer crash due to memory limits
  - Added `lightweight` mode to BacktestEngine (skips equity_curve and trades storage)
  - Added periodic `gc.collect()` every 25 iterations in optimizer/walk-forward loops
  - Hard-capped optimizer at 2000 maximum combinations with clear error messages
  - Cancelled stuck legacy optimizer job (227K combinations)

### Added
- **ML Regime Filter UI Toggle** - Checkbox in BacktestLab and Optimizer pages to enable/disable ML predictions for TrendShift strategy
- `lightweight` parameter on BacktestEngine for memory-efficient batch runs
- Combination limit validation on optimizer API

### Changed
- Optimizer auto-queues at lower thresholds (80 combos or 1200 candles) for reliability
- Walk-forward engine uses lightweight backtests and caps combos at 300
- BacktestEngine tracks win/loss metrics incrementally (no post-hoc list scanning)

## [2026-03-11] - Feature Expansion

### Added
- **TrendShift Strategy** - Advanced multi-indicator strategy with EMA ribbon, RSI, MACD, Supertrend, Bollinger Bands, demand/supply zones, and ML regime filter
- **ML Signal Module** - RandomForest-based market direction prediction with caching
- **Walk-Forward Optimization** - Train/test split approach to reduce overfitting
- **Job Queue System** - Async job processing for long-running backtests and optimizations
- **Candlestick Charts** - Interactive charts using lightweight-charts with indicator overlays
- **Trade Journal** - Trade history with summary statistics and CSV/JSON export
- **Zerodha OAuth Flow** - Complete authentication endpoints for Kite Connect
- **Settings Page** - Zerodha credentials, alert configuration, system health
- **Market Charts Page** - Candlestick visualization with TrendShift signals
- **Save Best Parameters** - Apply optimizer results as strategy defaults
- **TrendShift Presets** - Safe, Balanced, Deep optimization presets
- **Multi-Symbol Bot** - Run strategies across multiple symbols simultaneously
- **Portfolio Risk** - Basic portfolio-level risk analysis endpoint
- **Alert System** - Telegram and webhook notification framework

### Changed
- Backtest results chunked for MongoDB storage efficiency
- Optimizer results chunked for MongoDB storage efficiency
- Slippage modeling enhanced with ATR, volume, and gap-based estimation

## [2026-03-10] - Initial Release

### Added
- FastAPI backend with complete REST API
- React frontend with dark terminal-style theme
- MongoDB integration with Motor async driver
- Paper trading broker with realistic simulation
- SMA Crossover strategy
- Opening Range Breakout strategy
- Backtesting engine with comprehensive metrics
- Strategy Optimizer with heatmap visualization
- Risk management with kill switch
- Dashboard with equity curve and P&L charts
- Trade Monitor with orders, trades, positions, signals
- Strategy Editor for parameter configuration
- Indian NSE fee model (STT, GST, SEBI, stamp duty)
