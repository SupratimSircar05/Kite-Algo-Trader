import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, List

class AlgoTradingAPITester:
    def __init__(self, base_url="https://kite-trade-engine.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        self.session = requests.Session()

    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {test_name}: PASSED")
        else:
            self.failed_tests.append({"test": test_name, "details": details})
            print(f"❌ {test_name}: FAILED - {details}")
        return success

    def test_api_call(self, name: str, method: str, endpoint: str, expected_status: int = 200, 
                     data: Dict[str, Any] = None, params: Dict[str, Any] = None) -> tuple[bool, Dict]:
        """Make API call and test response"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, headers=headers, params=params, timeout=30)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, headers=headers, params=params, timeout=30)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data, headers=headers, timeout=30)
            else:
                return self.log_result(name, False, f"Unsupported method: {method}"), {}

            success = response.status_code == expected_status
            response_data = {}
            
            try:
                response_data = response.json() if response.content else {}
            except:
                response_data = {"raw_response": response.text}

            if not success:
                self.log_result(name, False, f"Expected {expected_status}, got {response.status_code}. Response: {response.text[:200]}")
                return False, response_data
            
            self.log_result(name, True)
            return True, response_data

        except requests.exceptions.RequestException as e:
            self.log_result(name, False, f"Request error: {str(e)}")
            return False, {}
        except Exception as e:
            self.log_result(name, False, f"Unexpected error: {str(e)}")
            return False, {}

    def test_health_endpoint(self):
        """Test health check endpoint"""
        print("\n🔍 Testing Health Check...")
        success, data = self.test_api_call("Health Check", "GET", "health")
        if success and data:
            print(f"   Database: {data.get('database', 'unknown')}")
            print(f"   Bot Status: {data.get('bot_status', 'unknown')}")
            print(f"   Market Open: {data.get('market_open', 'unknown')}")
        return success

    def test_dashboard_endpoints(self):
        """Test dashboard related endpoints"""
        print("\n🔍 Testing Dashboard Endpoints...")
        
        # Dashboard summary
        success1, summary = self.test_api_call("Dashboard Summary", "GET", "dashboard/summary")
        if success1 and summary:
            print(f"   Trading Mode: {summary.get('trading_mode', 'unknown')}")
            print(f"   Bot Status: {summary.get('bot_status', 'unknown')}")
            print(f"   Daily P&L: {summary.get('daily_pnl', 'unknown')}")

        # Equity curve
        success2, _ = self.test_api_call("Equity Curve", "GET", "metrics/equity-curve")
        
        # Daily P&L 
        success3, _ = self.test_api_call("Daily P&L Metrics", "GET", "metrics/daily-pnl")
        
        return success1 and success2 and success3

    def test_bot_control(self):
        """Test bot start/stop functionality"""
        print("\n🔍 Testing Bot Control...")
        
        # Get bot status first
        success1, status = self.test_api_call("Bot Status", "GET", "bot/status")
        
        # Start bot
        bot_config = {
            "strategy_name": "sma_crossover",
            "symbols": ["RELIANCE", "INFY"],
            "mode": "paper"
        }
        success2, start_result = self.test_api_call("Start Bot", "POST", "bot/start", 200, bot_config)
        if success2 and start_result:
            print(f"   Bot started with run_id: {start_result.get('run_id', 'unknown')}")

        # Wait briefly for bot to start
        import time
        time.sleep(2)

        # Stop bot
        stop_config = {"reason": "Test stop"}
        success3, _ = self.test_api_call("Stop Bot", "POST", "bot/stop", 200, stop_config)
        
        return success1 and success2 and success3

    def test_data_endpoints(self):
        """Test data retrieval endpoints"""
        print("\n🔍 Testing Data Endpoints...")
        
        # Get signals
        success1, signals = self.test_api_call("Get Signals", "GET", "signals", params={"limit": 10})
        if success1 and isinstance(signals, list):
            print(f"   Retrieved {len(signals)} signals")

        # Get orders  
        success2, orders = self.test_api_call("Get Orders", "GET", "orders", params={"limit": 10})
        if success2 and isinstance(orders, list):
            print(f"   Retrieved {len(orders)} orders")

        # Get trades
        success3, trades = self.test_api_call("Get Trades", "GET", "trades", params={"limit": 10})
        if success3 and isinstance(trades, list):
            print(f"   Retrieved {len(trades)} trades")

        # Get positions
        success4, positions = self.test_api_call("Get Positions", "GET", "positions")
        if success4 and isinstance(positions, list):
            print(f"   Retrieved {len(positions)} positions")

        return success1 and success2 and success3 and success4

    def test_strategies(self):
        """Test strategy endpoints"""
        print("\n🔍 Testing Strategy Management...")
        
        # List strategies
        success1, strategies = self.test_api_call("List Strategies", "GET", "strategies")
        if success1 and isinstance(strategies, list):
            print(f"   Found {len(strategies)} strategies")
            for strat in strategies[:2]:  # Show first 2
                print(f"     - {strat.get('name', 'unknown')}: {strat.get('display_name', 'unknown')}")
        
        # Update strategy config (if strategies exist)
        success2 = True
        if success1 and strategies and len(strategies) > 0:
            strat_name = strategies[0].get('name')
            if strat_name:
                config_update = {
                    "enabled": True,
                    "symbols": ["RELIANCE", "INFY", "TCS"],
                    "quantity": 5,
                    "parameters": {"fast_period": 10, "slow_period": 20}
                }
                success2, _ = self.test_api_call(f"Update Strategy {strat_name}", "PUT", f"strategies/{strat_name}", 200, config_update)

        return success1 and success2

    def test_risk_controls(self):
        """Test risk management endpoints"""
        print("\n🔍 Testing Risk Controls...")
        
        # Get risk config
        success1, config = self.test_api_call("Get Risk Config", "GET", "risk/config")
        if success1 and config:
            print(f"   Kill Switch Active: {config.get('kill_switch_active', 'unknown')}")
            print(f"   Max Daily Loss: {config.get('max_daily_loss', 'unknown')}")

        # Update risk config
        risk_update = {
            "max_daily_loss": 5000,
            "max_daily_loss_pct": 5.0,
            "max_position_size": 100,
            "kill_switch_active": False
        }
        success2, _ = self.test_api_call("Update Risk Config", "PUT", "risk/config", 200, risk_update)

        # Test kill switch toggle
        success3, _ = self.test_api_call("Toggle Kill Switch", "POST", "risk/kill-switch", params={"active": "false", "reason": "Test"})

        return success1 and success2 and success3

    def test_backtest(self):
        """Test backtest functionality"""
        print("\n🔍 Testing Backtest Engine...")
        
        # Get previous results first
        success1, results = self.test_api_call("Get Backtest Results", "GET", "backtest/results", params={"limit": 5})
        if success1 and isinstance(results, list):
            print(f"   Found {len(results)} previous backtest results")

        # Run a backtest
        backtest_config = {
            "strategy_name": "sma_crossover",
            "symbol": "RELIANCE", 
            "start_date": "2024-01-01",
            "end_date": "2025-06-01",
            "initial_capital": 100000,
            "quantity": 10,
            "timeframe": "day",
            "parameters": {"fast_period": 10, "slow_period": 20}
        }
        
        success2, result = self.test_api_call("Run Backtest", "POST", "backtest/run", 200, backtest_config)
        if success2 and result:
            print(f"   Backtest completed with {result.get('total_trades', 0)} trades")
            print(f"   Total Return: {result.get('total_return_pct', 0):.2f}%")

        return success1 and success2

    def test_settings_and_instruments(self):
        """Test settings and instruments"""
        print("\n🔍 Testing Settings & Instruments...")
        
        # Get settings
        success1, settings = self.test_api_call("Get Settings", "GET", "settings")
        if success1 and settings:
            print(f"   Trading Mode: {settings.get('trading_mode', 'unknown')}")
            print(f"   Capital: {settings.get('capital', 'unknown')}")

        # Update settings
        settings_update = {
            "trading_mode": "paper",
            "capital": 100000,
            "default_exchange": "NSE"
        }
        success2, _ = self.test_api_call("Update Settings", "PUT", "settings", 200, settings_update)

        # Get instruments
        success3, instruments = self.test_api_call("Get Instruments", "GET", "instruments")
        if success3 and isinstance(instruments, list):
            print(f"   Found {len(instruments)} instruments")

        # Initialize database
        success4, _ = self.test_api_call("Initialize Database", "POST", "init")

        return success1 and success2 and success3 and success4

    def test_manual_signal_generation(self):
        """Test manual signal generation"""
        print("\n🔍 Testing Manual Signal Generation...")
        
        success, result = self.test_api_call(
            "Generate Manual Signals", 
            "POST", 
            "signals/generate", 
            params={"strategy_name": "sma_crossover", "symbol": "RELIANCE"}
        )
        
        if success and result:
            print(f"   Generated {result.get('count', 0)} signals")
            
        return success

    def test_optimizer(self):
        """Test optimizer functionality"""
        print("\n🔍 Testing Optimizer Functionality...")
        
        # Test getting past optimizer results first
        success1, past_results = self.test_api_call("Get Optimizer Results", "GET", "optimizer/results", params={"limit": 5})
        if success1 and isinstance(past_results, list):
            print(f"   Found {len(past_results)} previous optimizer results")

        # Test running optimizer with small parameter grid
        optimizer_config = {
            "strategy_name": "sma_crossover",
            "symbol": "RELIANCE",
            "start_date": "2024-01-01", 
            "end_date": "2025-06-01",
            "initial_capital": 100000,
            "quantity": 10,
            "timeframe": "day",
            "param_ranges": {
                "fast_period": {"min": 5, "max": 10, "step": 1},
                "slow_period": {"min": 15, "max": 20, "step": 2}
            },
            "fixed_params": {}
        }
        
        print("   Running optimizer with small grid (18 combinations)...")
        success2, result = self.test_api_call("Run Optimizer", "POST", "optimizer/run", 200, optimizer_config)
        
        optimizer_result_id = None
        if success2 and result:
            print(f"   Optimization completed with {result.get('total_combinations', 0)} combinations")
            print(f"   Best return: {result.get('best_return_pct', 0):.2f}%")
            print(f"   Best params: {result.get('best_params', {})}")
            
            # Check heatmap data structure
            heatmap = result.get('heatmap')
            if heatmap:
                print(f"   Heatmap: {heatmap.get('x_param')} vs {heatmap.get('y_param')}")
                print(f"   Grid size: {len(heatmap.get('x_values', []))} x {len(heatmap.get('y_values', []))}")
            else:
                print("   No heatmap data (expected for 1D optimization)")
            
            optimizer_result_id = result.get('id')
            
        # Test getting specific optimizer result if we have an ID
        success3 = True
        if optimizer_result_id:
            success3, detail = self.test_api_call(f"Get Optimizer Detail", "GET", f"optimizer/results/{optimizer_result_id}")
            if success3 and detail:
                print(f"   Retrieved optimizer detail with {len(detail.get('results', []))} result entries")

        # Test invalid optimizer request (too many combinations)
        large_config = {
            "strategy_name": "sma_crossover",
            "symbol": "RELIANCE", 
            "start_date": "2024-01-01",
            "end_date": "2025-06-01",
            "initial_capital": 100000,
            "quantity": 10,
            "param_ranges": {
                "fast_period": {"min": 1, "max": 100, "step": 1},
                "slow_period": {"min": 1, "max": 100, "step": 1}
            }
        }
        
        success4, _ = self.test_api_call("Large Grid Rejection", "POST", "optimizer/run", 400, large_config)
        if success4:
            print("   Large grid correctly rejected (10000 combinations > 2500 limit)")

        return success1 and success2 and success3 and success4

    def run_all_tests(self):
        """Run all test suites"""
        print("🚀 Starting Algo Trading Bot API Tests")
        print(f"📡 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Core functionality tests
        health_ok = self.test_health_endpoint()
        dashboard_ok = self.test_dashboard_endpoints() 
        bot_control_ok = self.test_bot_control()
        data_ok = self.test_data_endpoints()
        strategies_ok = self.test_strategies()
        risk_ok = self.test_risk_controls()
        backtest_ok = self.test_backtest()
        settings_ok = self.test_settings_and_instruments()
        signals_ok = self.test_manual_signal_generation()
        optimizer_ok = self.test_optimizer()
        
        # Print final results
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {len(self.failed_tests)}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.failed_tests:
            print("\n❌ FAILED TESTS:")
            for failed in self.failed_tests:
                print(f"   • {failed['test']}: {failed['details']}")
        
        # Return categorized results
        results = {
            "health": health_ok,
            "dashboard": dashboard_ok, 
            "bot_control": bot_control_ok,
            "data_retrieval": data_ok,
            "strategies": strategies_ok,
            "risk_controls": risk_ok,
            "backtest": backtest_ok,
            "settings": settings_ok,
            "signals": signals_ok,
            "optimizer": optimizer_ok
        }
        
        critical_failed = not (health_ok and dashboard_ok and bot_control_ok)
        
        return {
            "total_tests": self.tests_run,
            "passed_tests": self.tests_passed,
            "failed_tests": self.failed_tests,
            "success_rate": self.tests_passed/self.tests_run*100 if self.tests_run > 0 else 0,
            "critical_systems_working": not critical_failed,
            "detailed_results": results
        }

def main():
    """Main test execution"""
    tester = AlgoTradingAPITester()
    results = tester.run_all_tests()
    
    # Exit with appropriate code
    if results["success_rate"] < 70:
        print("\n🚨 CRITICAL: Less than 70% tests passed!")
        return 1
    elif results["success_rate"] < 90:
        print(f"\n⚠️  WARNING: {results['success_rate']:.1f}% tests passed")
        return 0
    else:
        print(f"\n✅ EXCELLENT: {results['success_rate']:.1f}% tests passed")
        return 0

if __name__ == "__main__":
    sys.exit(main())