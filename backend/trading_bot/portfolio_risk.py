"""
Portfolio-Level Risk Management.
Cross-strategy correlation, sector exposure, and aggregate risk metrics.
"""
import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict

logger = logging.getLogger("portfolio_risk")

# Simplified sector mapping for NSE
SECTOR_MAP = {
    "RELIANCE": "Energy", "ONGC": "Energy", "IOC": "Energy", "BPCL": "Energy",
    "INFY": "IT", "TCS": "IT", "WIPRO": "IT", "HCLTECH": "IT", "TECHM": "IT",
    "HDFCBANK": "Banking", "ICICIBANK": "Banking", "SBIN": "Banking", "KOTAKBANK": "Banking", "AXISBANK": "Banking",
    "ITC": "FMCG", "HINDUNILVR": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG",
    "TATASTEEL": "Metals", "JSWSTEEL": "Metals", "HINDALCO": "Metals",
    "TATAMOTORS": "Auto", "MARUTI": "Auto", "M&M": "Auto", "BAJAJ-AUTO": "Auto",
    "SUNPHARMA": "Pharma", "DRREDDY": "Pharma", "CIPLA": "Pharma",
    "LT": "Infra", "ULTRACEMCO": "Cement", "ASIANPAINT": "Consumer",
}


class PortfolioRiskManager:
    """Tracks and enforces portfolio-level risk across all strategies."""

    def __init__(self, max_sector_exposure_pct: float = 40, max_correlation_exposure: int = 3,
                 max_portfolio_drawdown_pct: float = 10, capital: float = 100000):
        self.max_sector_exposure_pct = max_sector_exposure_pct
        self.max_correlation_exposure = max_correlation_exposure
        self.max_portfolio_drawdown_pct = max_portfolio_drawdown_pct
        self.capital = capital

    def analyze_positions(self, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze current portfolio for risk metrics."""
        open_positions = [p for p in positions if p.get("status") == "OPEN"]

        # Sector exposure
        sector_exposure = defaultdict(float)
        total_exposure = 0
        for pos in open_positions:
            symbol = pos.get("symbol", "")
            value = abs(pos.get("quantity", 0) * pos.get("avg_price", 0))
            sector = SECTOR_MAP.get(symbol, "Other")
            sector_exposure[sector] += value
            total_exposure += value

        sector_pct = {}
        for sector, val in sector_exposure.items():
            sector_pct[sector] = round(val / self.capital * 100, 2) if self.capital > 0 else 0

        # Strategy exposure
        strategy_exposure = defaultdict(int)
        for pos in open_positions:
            strategy_exposure[pos.get("strategy_name", "unknown")] += 1

        # Concentration risk
        symbol_values = defaultdict(float)
        for pos in open_positions:
            symbol_values[pos.get("symbol", "")] += abs(pos.get("quantity", 0) * pos.get("avg_price", 0))
        top_concentration = sorted(symbol_values.items(), key=lambda x: x[1], reverse=True)[:5]

        # Direction bias
        long_count = sum(1 for p in open_positions if p.get("side") == "BUY")
        short_count = sum(1 for p in open_positions if p.get("side") == "SELL")

        # Unrealized P&L
        total_unrealized = sum(p.get("unrealized_pnl", 0) for p in open_positions)

        # Risk alerts
        alerts = []
        for sector, pct in sector_pct.items():
            if pct > self.max_sector_exposure_pct:
                alerts.append(f"Sector '{sector}' exposure at {pct}% exceeds {self.max_sector_exposure_pct}% limit")

        if len(open_positions) > 0 and (long_count == 0 or short_count == 0):
            direction = "LONG" if long_count > 0 else "SHORT"
            alerts.append(f"Portfolio is 100% {direction} biased ({long_count}L/{short_count}S)")

        portfolio_pnl_pct = (total_unrealized / self.capital * 100) if self.capital > 0 else 0
        if portfolio_pnl_pct < -self.max_portfolio_drawdown_pct:
            alerts.append(f"Portfolio drawdown at {portfolio_pnl_pct:.2f}% exceeds {self.max_portfolio_drawdown_pct}% limit")

        return {
            "open_positions": len(open_positions),
            "total_exposure": round(total_exposure, 2),
            "exposure_pct": round(total_exposure / self.capital * 100, 2) if self.capital > 0 else 0,
            "sector_exposure": dict(sector_pct),
            "strategy_exposure": dict(strategy_exposure),
            "top_concentration": [{"symbol": s, "value": round(v, 2)} for s, v in top_concentration],
            "long_count": long_count,
            "short_count": short_count,
            "direction_bias": "NEUTRAL" if long_count > 0 and short_count > 0 else ("LONG" if long_count > 0 else "SHORT" if short_count > 0 else "FLAT"),
            "total_unrealized_pnl": round(total_unrealized, 2),
            "portfolio_pnl_pct": round(portfolio_pnl_pct, 2),
            "risk_alerts": alerts,
            "risk_score": min(10, len(alerts) * 2 + (1 if portfolio_pnl_pct < -3 else 0) * 3),
        }

    def check_new_position(self, symbol: str, side: str, value: float,
                           current_positions: List[Dict[str, Any]]) -> tuple[bool, str]:
        """Check if a new position is allowed under portfolio risk rules."""
        sector = SECTOR_MAP.get(symbol, "Other")
        sector_value = value
        for pos in current_positions:
            if pos.get("status") == "OPEN" and SECTOR_MAP.get(pos.get("symbol", ""), "Other") == sector:
                sector_value += abs(pos.get("quantity", 0) * pos.get("avg_price", 0))

        sector_pct = sector_value / self.capital * 100 if self.capital > 0 else 0
        if sector_pct > self.max_sector_exposure_pct:
            return False, f"Adding {symbol} would push {sector} sector exposure to {sector_pct:.1f}% (max {self.max_sector_exposure_pct}%)"

        same_sector_count = sum(1 for p in current_positions
                                if p.get("status") == "OPEN" and SECTOR_MAP.get(p.get("symbol", ""), "Other") == sector)
        if same_sector_count >= self.max_correlation_exposure:
            return False, f"Already {same_sector_count} positions in {sector} sector (max {self.max_correlation_exposure})"

        return True, "OK"


portfolio_risk_manager = PortfolioRiskManager()
