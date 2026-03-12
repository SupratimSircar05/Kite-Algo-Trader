"""
Walk-Forward Optimization: Train/test split approach to reduce overfitting.
Splits data into windows, optimizes on train set, validates on test set.
"""
import gc
import logging
from typing import List, Dict, Any, Optional
import itertools

from .backtest import BacktestEngine
from .strategies import get_strategy, STRATEGY_REGISTRY
from .models import gen_id, now_utc

logger = logging.getLogger("walk_forward")


class WalkForwardEngine:
    """
    Walk-forward optimization:
    1. Split candle data into N windows (train_pct / test_pct)
    2. Optimize parameters on each train set
    3. Validate with best params on each test set
    4. Report aggregate out-of-sample performance
    """

    def __init__(self, strategy_name: str, param_ranges: Dict[str, Dict[str, float]],
                 initial_capital: float = 100000, quantity: int = 10):
        self.strategy_name = strategy_name
        self.param_ranges = param_ranges
        self.initial_capital = initial_capital
        self.quantity = quantity

    def _gen_combos(self) -> List[Dict[str, Any]]:
        axes = {}
        for name, rng in self.param_ranges.items():
            vals = []
            v = rng["min"]
            while v <= rng["max"] + 1e-9:
                vals.append(round(v, 6))
                v += rng["step"]
            axes[name] = vals
        keys = list(axes.keys())
        combos = list(itertools.product(*(axes[k] for k in keys)))
        return [dict(zip(keys, c)) for c in combos]

    def _run_bt(self, candles: List[Dict], params: Dict, symbol: str) -> Dict[str, Any]:
        for k, v in params.items():
            if isinstance(v, float) and v == int(v):
                params[k] = int(v)
        strategy = get_strategy(self.strategy_name, params)
        engine = BacktestEngine(strategy, self.initial_capital, quantity=self.quantity, lightweight=True)
        result = engine.run(candles, symbol=symbol)
        return {
            "params": params,
            "total_return_pct": result.total_return_pct,
            "total_trades": result.total_trades,
            "win_rate": result.win_rate,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown_pct": result.max_drawdown_pct,
            "profit_factor": result.profit_factor,
        }

    def run(self, candles: List[Dict[str, Any]], symbol: str = "",
            n_windows: int = 5, train_pct: float = 0.7) -> Dict[str, Any]:
        """Run walk-forward optimization."""
        n = len(candles)
        window_size = n // n_windows
        if window_size < 30:
            return {"error": "Insufficient data for walk-forward analysis", "windows": 0}

        combos = self._gen_combos()
        if len(combos) > 300:
            import random
            combos = random.sample(combos, 300)

        windows = []
        oos_results = []  # Out-of-sample results

        for w in range(n_windows):
            start = w * window_size
            end = min(start + window_size, n)
            window_candles = candles[start:end]

            train_end = int(len(window_candles) * train_pct)
            train_data = window_candles[:train_end]
            test_data = window_candles[train_end:]

            if len(train_data) < 20 or len(test_data) < 10:
                continue

            # Optimize on train
            best_params = None
            best_return = -float("inf")
            for idx, combo in enumerate(combos):
                try:
                    result = self._run_bt(train_data, dict(combo), symbol)
                    if result["total_return_pct"] > best_return:
                        best_return = result["total_return_pct"]
                        best_params = dict(combo)
                except Exception:
                    continue
                if idx % 25 == 0:
                    gc.collect()

            if best_params is None:
                continue

            # Validate on test
            try:
                oos = self._run_bt(test_data, dict(best_params), symbol)
            except Exception:
                oos = {"total_return_pct": 0, "total_trades": 0, "win_rate": 0, "sharpe_ratio": 0, "max_drawdown_pct": 0, "profit_factor": 0, "params": best_params}

            window_result = {
                "window": w + 1,
                "train_size": len(train_data),
                "test_size": len(test_data),
                "best_train_params": best_params,
                "train_return_pct": round(best_return, 2),
                "test_return_pct": round(oos["total_return_pct"], 2),
                "test_trades": oos.get("total_trades", 0),
                "test_win_rate": round(oos.get("win_rate", 0), 2),
                "test_sharpe": round(oos.get("sharpe_ratio", 0), 2),
                "test_drawdown": round(oos.get("max_drawdown_pct", 0), 2),
                "overfit_ratio": round(oos["total_return_pct"] / best_return, 2) if best_return != 0 else 0,
            }
            windows.append(window_result)
            oos_results.append(oos["total_return_pct"])

        # Aggregate
        avg_oos = sum(oos_results) / len(oos_results) if oos_results else 0
        consistency = sum(1 for r in oos_results if r > 0) / len(oos_results) if oos_results else 0

        # Find most robust params (appears most often as winner)
        param_freq = {}
        for w in windows:
            key = str(sorted(w["best_train_params"].items()))
            param_freq[key] = param_freq.get(key, 0) + 1
        most_robust = max(param_freq, key=param_freq.get) if param_freq else ""

        return {
            "id": gen_id(),
            "strategy_name": self.strategy_name,
            "symbol": symbol,
            "n_windows": n_windows,
            "train_pct": train_pct,
            "total_combinations": len(combos),
            "avg_oos_return_pct": round(avg_oos, 2),
            "consistency": round(consistency * 100, 2),
            "windows": windows,
            "most_robust_params": most_robust,
            "created_at": now_utc(),
        }
