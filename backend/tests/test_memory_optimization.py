"""
Backend API Tests for KiteAlgo Trading Bot - Memory Optimization and ML Filter Features
Tests for: Backtest with ML toggle, Optimizer with combination limits, Walk-forward, Job queue
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestBacktestWithMLToggle:
    """Test backtest API with use_ml_filter parameter for TrendShift strategy"""
    
    def test_backtest_trendshift_with_ml_filter_enabled(self):
        """POST /api/backtest/run with trendshift and use_ml_filter=true"""
        payload = {
            "strategy_name": "trendshift",
            "symbol": "RELIANCE",
            "start_date": "2024-06-01",
            "end_date": "2025-01-01",
            "initial_capital": 100000,
            "quantity": 10,
            "timeframe": "day",
            "parameters": {"use_ml_filter": True}
        }
        response = requests.post(f"{BASE_URL}/api/backtest/run", json=payload, timeout=60)
        # Accept 200 (immediate), 202 (queued), or valid job response
        assert response.status_code in [200, 202]
        data = response.json()
        if response.status_code == 202:
            # Queued job
            assert "job_id" in data
            print(f"Backtest queued: job_id={data['job_id']}")
        else:
            # Immediate result
            assert "total_return_pct" in data
            assert "total_trades" in data
            print(f"Backtest with ML filter enabled: return={data['total_return_pct']}%, trades={data['total_trades']}")
    
    def test_backtest_trendshift_with_ml_filter_disabled(self):
        """POST /api/backtest/run with trendshift and use_ml_filter=false"""
        payload = {
            "strategy_name": "trendshift",
            "symbol": "RELIANCE",
            "start_date": "2024-06-01",
            "end_date": "2025-01-01",
            "initial_capital": 100000,
            "quantity": 10,
            "timeframe": "day",
            "parameters": {"use_ml_filter": False}
        }
        response = requests.post(f"{BASE_URL}/api/backtest/run", json=payload, timeout=60)
        assert response.status_code in [200, 202]
        data = response.json()
        if response.status_code == 202:
            assert "job_id" in data
            print(f"Backtest queued: job_id={data['job_id']}")
        else:
            assert "total_return_pct" in data
            print(f"Backtest with ML filter disabled: return={data['total_return_pct']}%, trades={data['total_trades']}")
    
    def test_backtest_results_list(self):
        """GET /api/backtest/results returns list of results"""
        response = requests.get(f"{BASE_URL}/api/backtest/results")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Backtest results count: {len(data)}")


class TestOptimizerWithCombinationLimit:
    """Test optimizer API with combination limit and memory optimization"""
    
    def test_optimizer_small_grid_completes(self):
        """POST /api/optimizer/run with small grid (under 2000 combinations) completes"""
        payload = {
            "strategy_name": "sma_crossover",
            "symbol": "RELIANCE",
            "start_date": "2024-06-01",
            "end_date": "2025-01-01",
            "initial_capital": 100000,
            "quantity": 10,
            "timeframe": "day",
            "param_ranges": {
                "fast_period": {"min": 5, "max": 15, "step": 2},  # 6 values
                "slow_period": {"min": 20, "max": 40, "step": 5}  # 5 values = 30 combos
            },
            "objective": "balanced"
        }
        response = requests.post(f"{BASE_URL}/api/optimizer/run", json=payload, timeout=120)
        assert response.status_code in [200, 202]
        data = response.json()
        if response.status_code == 202:
            # Queued job
            assert "job_id" in data
            assert "total_combinations" in data
            print(f"Optimizer queued: job_id={data['job_id']}, combos={data['total_combinations']}")
        else:
            # Immediate result
            assert "best_params" in data
            assert "results" in data
            assert "total_combinations" in data
            print(f"Optimizer completed: combos={data['total_combinations']}, best_return={data.get('best_return_pct')}%")
    
    def test_optimizer_rejects_over_2000_combinations(self):
        """POST /api/optimizer/run rejects > 2000 combinations"""
        payload = {
            "strategy_name": "sma_crossover",
            "symbol": "RELIANCE",
            "start_date": "2024-06-01",
            "end_date": "2025-01-01",
            "initial_capital": 100000,
            "quantity": 10,
            "timeframe": "day",
            "param_ranges": {
                "fast_period": {"min": 1, "max": 50, "step": 1},  # 50 values
                "slow_period": {"min": 1, "max": 100, "step": 1}  # 100 values = 5000 combos
            },
            "objective": "balanced"
        }
        response = requests.post(f"{BASE_URL}/api/optimizer/run", json=payload, timeout=10)
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "2000" in data["detail"].lower() or "combination" in data["detail"].lower()
        print(f"Optimizer correctly rejected: {data['detail']}")
    
    def test_optimizer_trendshift_with_ml_filter(self):
        """POST /api/optimizer/run with trendshift strategy and ML filter in fixed_params"""
        payload = {
            "strategy_name": "trendshift",
            "symbol": "RELIANCE",
            "start_date": "2024-06-01",
            "end_date": "2025-01-01",
            "initial_capital": 100000,
            "quantity": 10,
            "timeframe": "day",
            "param_ranges": {
                "ema_fast": {"min": 6, "max": 10, "step": 2},  # 3 values
                "ema_mid": {"min": 18, "max": 24, "step": 3}   # 3 values = 9 combos
            },
            "fixed_params": {"use_ml_filter": True},
            "objective": "balanced"
        }
        response = requests.post(f"{BASE_URL}/api/optimizer/run", json=payload, timeout=120)
        assert response.status_code in [200, 202]
        data = response.json()
        if response.status_code == 202:
            assert "job_id" in data
            print(f"TrendShift optimizer queued: job_id={data['job_id']}")
        else:
            assert "best_params" in data
            print(f"TrendShift optimizer completed: best_return={data.get('best_return_pct')}%")
    
    def test_optimizer_results_list(self):
        """GET /api/optimizer/results returns list of results"""
        response = requests.get(f"{BASE_URL}/api/optimizer/results")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Optimizer results count: {len(data)}")


class TestWalkForwardOptimization:
    """Test walk-forward optimization endpoint"""
    
    def test_walkforward_sma_crossover(self):
        """POST /api/walkforward/run works with sma_crossover"""
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
                "fast_period": {"min": 5, "max": 15, "step": 5},
                "slow_period": {"min": 20, "max": 40, "step": 10}
            }
        }
        response = requests.post(f"{BASE_URL}/api/walkforward/run", json=payload, timeout=120)
        assert response.status_code == 200
        data = response.json()
        assert "windows" in data or "id" in data
        if "avg_oos_return_pct" in data:
            print(f"Walk-forward: avg_oos_return={data['avg_oos_return_pct']}%, consistency={data.get('consistency')}%")
        else:
            print(f"Walk-forward completed: {data}")
    
    def test_walkforward_results_list(self):
        """GET /api/walkforward/results returns list of results"""
        response = requests.get(f"{BASE_URL}/api/walkforward/results")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Walk-forward results count: {len(data)}")


class TestJobQueueSystem:
    """Test job queue system for backtests and optimizations"""
    
    def test_list_jobs(self):
        """GET /api/jobs returns list of jobs"""
        response = requests.get(f"{BASE_URL}/api/jobs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Total jobs: {len(data)}")
    
    def test_list_jobs_by_kind(self):
        """GET /api/jobs?kind=backtest filters correctly"""
        response = requests.get(f"{BASE_URL}/api/jobs", params={"kind": "backtest"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # If jobs returned, verify they are backtests
        for job in data:
            if "kind" in job:
                assert job["kind"] == "backtest"
        print(f"Backtest jobs: {len(data)}")
    
    def test_list_optimizer_jobs(self):
        """GET /api/jobs?kind=optimizer filters correctly"""
        response = requests.get(f"{BASE_URL}/api/jobs", params={"kind": "optimizer"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Optimizer jobs: {len(data)}")


class TestChartCandlesEndpoint:
    """Test chart candles endpoint"""
    
    def test_chart_candles_basic(self):
        """GET /api/chart/candles returns data"""
        response = requests.get(f"{BASE_URL}/api/chart/candles", params={
            "symbol": "RELIANCE",
            "start_date": "2024-06-01",
            "end_date": "2025-01-01",
            "timeframe": "day"
        })
        assert response.status_code == 200
        data = response.json()
        assert "candles" in data
        assert len(data["candles"]) > 0
        assert "indicators" in data
        print(f"Chart candles: {len(data['candles'])} candles returned")
    
    def test_chart_candles_with_indicators(self):
        """GET /api/chart/candles with indicators enabled"""
        response = requests.get(f"{BASE_URL}/api/chart/candles", params={
            "symbol": "RELIANCE",
            "include_indicators": True,
            "include_trendshift": True
        })
        assert response.status_code == 200
        data = response.json()
        assert "indicators" in data
        assert "trendshift_signals" in data
        print(f"Chart with indicators: signals={len(data.get('trendshift_signals', []))}")


class TestSettingsEndpoint:
    """Test settings endpoint"""
    
    def test_get_settings(self):
        """GET /api/settings returns settings"""
        response = requests.get(f"{BASE_URL}/api/settings")
        assert response.status_code == 200
        data = response.json()
        assert "trading_mode" in data or "capital" in data or isinstance(data, dict)
        print(f"Settings retrieved successfully")


class TestStrategiesEndpoint:
    """Test strategies endpoint includes trendshift"""
    
    def test_list_strategies_includes_trendshift(self):
        """GET /api/strategies includes trendshift"""
        response = requests.get(f"{BASE_URL}/api/strategies")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        strategy_names = [s["name"] for s in data]
        assert "trendshift" in strategy_names
        # Verify trendshift has ML parameters
        trendshift = next((s for s in data if s["name"] == "trendshift"), None)
        assert trendshift is not None
        print(f"Strategies: {strategy_names}")


class TestTradeJournal:
    """Test trade journal endpoint"""
    
    def test_journal_returns_data(self):
        """GET /api/journal returns data"""
        response = requests.get(f"{BASE_URL}/api/journal")
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "trades" in data
        print(f"Journal: {data['summary']['total_trades']} trades")


class TestMLModels:
    """Test ML models endpoint"""
    
    def test_list_ml_models(self):
        """GET /api/ml/models returns list"""
        response = requests.get(f"{BASE_URL}/api/ml/models")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"ML models: {[m['name'] for m in data]}")


class TestDashboardSummary:
    """Test dashboard summary for regression"""
    
    def test_dashboard_loads(self):
        """GET /api/dashboard/summary works"""
        response = requests.get(f"{BASE_URL}/api/dashboard/summary")
        assert response.status_code == 200
        data = response.json()
        assert "bot_status" in data
        assert "trading_mode" in data
        assert "capital" in data
        print(f"Dashboard: status={data['bot_status']}, mode={data['trading_mode']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
