"""
Backend API Tests for KiteAlgo Trading Bot
Tests for: journal, chart, auth, backtest, alerts, signals, and bot control endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthCheck:
    """Test API health check"""
    
    def test_health_endpoint(self):
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "database" in data
        assert "bot_status" in data
        print(f"Health check passed: {data}")


class TestJournalAPI:
    """Test Trade Journal endpoints - /api/journal"""
    
    def test_get_journal_summary(self):
        """GET /api/journal returns summary + filtered trade ledger data"""
        response = requests.get(f"{BASE_URL}/api/journal")
        assert response.status_code == 200
        data = response.json()
        # Validate response structure
        assert "summary" in data
        assert "trades" in data
        assert "filters" in data
        # Validate summary fields
        summary = data["summary"]
        assert "total_trades" in summary
        assert "net_pnl" in summary
        assert "win_rate" in summary
        assert "strategy_breakdown" in summary
        print(f"Journal summary: total_trades={summary['total_trades']}, net_pnl={summary['net_pnl']}")
    
    def test_get_journal_with_filters(self):
        """GET /api/journal with filter params"""
        response = requests.get(f"{BASE_URL}/api/journal", params={
            "symbol": "RELIANCE",
            "limit": 50
        })
        assert response.status_code == 200
        data = response.json()
        assert "trades" in data
        # If trades returned, verify they match filter
        if data["trades"]:
            for trade in data["trades"]:
                assert trade.get("symbol") == "RELIANCE"
        print(f"Filtered journal: {len(data['trades'])} trades for RELIANCE")
    
    def test_export_journal_csv(self):
        """GET /api/journal/export?format=csv works"""
        response = requests.get(f"{BASE_URL}/api/journal/export", params={"format": "csv"})
        # Could be 200 with CSV content or 404 if no trades
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            assert "text/csv" in response.headers.get("Content-Type", "")
            print("CSV export successful")
        else:
            print("No trades to export (404)")
    
    def test_export_journal_json(self):
        """GET /api/journal/export?format=json works"""
        response = requests.get(f"{BASE_URL}/api/journal/export", params={"format": "json"})
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "summary" in data
            assert "trades" in data
            print(f"JSON export successful with {len(data['trades'])} trades")


class TestChartAPI:
    """Test Chart/Candles endpoints - /api/chart/candles"""
    
    def test_get_chart_candles(self):
        """GET /api/chart/candles returns candles, indicators, zones, trendshift signals"""
        response = requests.get(f"{BASE_URL}/api/chart/candles", params={
            "symbol": "RELIANCE",
            "start_date": "2024-06-01",
            "end_date": "2025-06-01",
            "timeframe": "day",
            "include_indicators": True,
            "include_trendshift": True,
            "limit": 60
        })
        assert response.status_code == 200
        data = response.json()
        # Validate structure
        assert "candles" in data
        assert "indicators" in data
        assert "trendshift_signals" in data
        assert "zones" in data
        assert "indicator_summary" in data
        # Validate candle data
        assert len(data["candles"]) > 0
        candle = data["candles"][0]
        assert "open" in candle
        assert "high" in candle
        assert "low" in candle
        assert "close" in candle
        assert "timestamp" in candle
        # Validate zones structure
        assert "demand" in data["zones"]
        assert "supply" in data["zones"]
        print(f"Chart data: {len(data['candles'])} candles, {len(data['trendshift_signals'])} signals")
    
    def test_chart_with_different_timeframe(self):
        """GET /api/chart/candles with different timeframe"""
        response = requests.get(f"{BASE_URL}/api/chart/candles", params={
            "symbol": "INFY",
            "timeframe": "day"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "INFY"
        assert len(data["candles"]) > 0
        print(f"Got {len(data['candles'])} candles for INFY")


class TestZerodhaAuthAPI:
    """Test Zerodha auth endpoints - safe handling when credentials absent"""
    
    def test_zerodha_auth_start_no_credentials(self):
        """GET /api/auth/zerodha/start returns configured:false when credentials absent"""
        response = requests.get(f"{BASE_URL}/api/auth/zerodha/start")
        assert response.status_code == 200
        data = response.json()
        # Should return safe response when no credentials
        assert "configured" in data
        # If not configured, should have reason
        if not data["configured"]:
            assert "reason" in data or data.get("login_url") is None
        print(f"Auth start response: configured={data['configured']}")
    
    def test_zerodha_auth_status(self):
        """GET /api/auth/zerodha/status returns auth readiness without crashing"""
        response = requests.get(f"{BASE_URL}/api/auth/zerodha/status")
        assert response.status_code == 200
        data = response.json()
        # Validate structure
        assert "api_key_configured" in data
        assert "api_secret_configured" in data
        assert "access_token_configured" in data
        print(f"Auth status: api_key={data['api_key_configured']}, token={data['access_token_configured']}")


class TestBacktestAPI:
    """Test Backtest and Walk-Forward endpoints"""
    
    def test_walk_forward_backtest(self):
        """POST /api/backtest/walk_forward runs successfully"""
        payload = {
            "strategy_name": "sma_crossover",
            "symbol": "RELIANCE",
            "start_date": "2024-01-01",
            "end_date": "2025-06-01",
            "initial_capital": 100000,
            "quantity": 10,
            "n_windows": 3,
            "train_pct": 0.7,
            "param_ranges": {
                "fast_period": {"min": 5, "max": 10, "step": 5},
                "slow_period": {"min": 20, "max": 30, "step": 10}
            }
        }
        response = requests.post(f"{BASE_URL}/api/backtest/walk_forward", json=payload)
        assert response.status_code == 200
        data = response.json()
        # Validate walk-forward result structure
        assert "windows" in data or "id" in data
        print(f"Walk-forward completed")
    
    def test_backtest_run(self):
        """POST /api/backtest/run basic test"""
        payload = {
            "strategy_name": "sma_crossover",
            "symbol": "RELIANCE",
            "start_date": "2024-01-01",
            "end_date": "2025-06-01",
            "initial_capital": 100000,
            "quantity": 10
        }
        response = requests.post(f"{BASE_URL}/api/backtest/run", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "total_return_pct" in data
        print(f"Backtest result: return={data['total_return_pct']}%")


class TestAlertsAPI:
    """Test Alert endpoints - safe handling when credentials absent"""
    
    def test_alerts_status(self):
        """GET /api/alerts/status returns channel status"""
        response = requests.get(f"{BASE_URL}/api/alerts/status")
        assert response.status_code == 200
        data = response.json()
        assert "telegram_configured" in data
        assert "webhook_configured" in data
        print(f"Alerts status: telegram={data['telegram_configured']}, webhook={data['webhook_configured']}")
    
    def test_alerts_test_no_credentials(self):
        """POST /api/alerts/test safely skips when credentials absent"""
        response = requests.post(f"{BASE_URL}/api/alerts/test")
        assert response.status_code == 200
        data = response.json()
        # Should either skip or send based on configuration
        assert "status" in data
        assert data["status"] in ["skipped", "sent"]
        if data["status"] == "skipped":
            assert "reason" in data
        print(f"Test alert: status={data['status']}")


class TestSignalsAPI:
    """Test Signal generation endpoints"""
    
    def test_generate_signals_trendshift(self):
        """POST /api/signals/generate works for trendshift"""
        response = requests.post(
            f"{BASE_URL}/api/signals/generate",
            params={"strategy_name": "trendshift", "symbol": "RELIANCE"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "signals" in data
        print(f"Trendshift signals generated: count={data['count']}")
    
    def test_generate_signals_sma(self):
        """POST /api/signals/generate with sma_crossover"""
        response = requests.post(
            f"{BASE_URL}/api/signals/generate",
            params={"strategy_name": "sma_crossover", "symbol": "INFY"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        print(f"SMA signals generated: count={data['count']}")


class TestBotControlAPI:
    """Test Bot start/stop in paper mode"""
    
    def test_bot_start_multi_paper(self):
        """POST /api/bot/start-multi works in paper mode"""
        payload = {
            "strategy_name": "trendshift",
            "symbols": ["RELIANCE", "INFY"],
            "mode": "paper"
        }
        response = requests.post(f"{BASE_URL}/api/bot/start-multi", json=payload)
        assert response.status_code in [200, 400]  # 400 if already running
        data = response.json()
        if response.status_code == 200:
            assert data["status"] == "started"
            assert "run_id" in data
            print(f"Bot started: run_id={data['run_id']}")
        else:
            print(f"Bot already running or error: {data}")
    
    def test_bot_stop(self):
        """POST /api/bot/stop works"""
        payload = {"reason": "Test stop"}
        response = requests.post(f"{BASE_URL}/api/bot/stop", json=payload)
        assert response.status_code in [200, 400]  # 400 if not running
        data = response.json()
        if response.status_code == 200:
            assert data["status"] == "stopped"
            print("Bot stopped successfully")
        else:
            print(f"Bot was not running: {data}")
    
    def test_bot_status(self):
        """GET /api/bot/status returns current status"""
        response = requests.get(f"{BASE_URL}/api/bot/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        print(f"Bot status: {data['status']}")


class TestDashboardAPI:
    """Test dashboard summary for regression"""
    
    def test_dashboard_summary(self):
        """GET /api/dashboard/summary still works after new routes"""
        response = requests.get(f"{BASE_URL}/api/dashboard/summary")
        assert response.status_code == 200
        data = response.json()
        assert "bot_status" in data
        assert "trading_mode" in data
        assert "capital" in data
        assert "daily_pnl" in data
        print(f"Dashboard: mode={data['trading_mode']}, capital={data['capital']}")


class TestStrategiesAPI:
    """Test strategies API for regression"""
    
    def test_list_strategies(self):
        """GET /api/strategies returns list"""
        response = requests.get(f"{BASE_URL}/api/strategies")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Check trendshift is registered
        strategy_names = [s["name"] for s in data]
        assert "trendshift" in strategy_names
        print(f"Strategies: {strategy_names}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
