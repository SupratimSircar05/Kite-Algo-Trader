"""
ML Signal Module: cached sklearn-based helpers for directional regime filtering.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .enums import Side
from .models import Signal

logger = logging.getLogger("ml_signals")


class MLModelBase(ABC):
    name: str = "base_ml"
    features_required: List[str] = []

    @abstractmethod
    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def train(self, data: List[Dict[str, Any]], labels: List[int]) -> Dict[str, Any]:
        ...

    def save(self, path: str):
        raise NotImplementedError

    def load(self, path: str):
        raise NotImplementedError


class SklearnSignalModel(MLModelBase):
    name = "sklearn_rf"
    features_required = [
        "rsi", "macd_hist", "ema_cross", "volume_relative",
        "atr_pct", "bb_position", "ribbon_spread", "gap_pct",
    ]

    def __init__(self):
        self.model = None
        self._trained = False

    def _extract_features(self, feat: Dict[str, Any]) -> List[float]:
        return [
            feat.get("rsi", 50) / 100,
            feat.get("macd_hist", 0),
            1.0 if feat.get("ema_cross", False) else 0.0,
            feat.get("volume_relative", 1.0),
            feat.get("atr_pct", 0),
            feat.get("bb_position", 0.5),
            feat.get("ribbon_spread", 0),
            feat.get("gap_pct", 0),
        ]

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        if not self._trained or self.model is None:
            return {"side": None, "confidence": 0, "reason": "Model not trained"}
        try:
            X = [self._extract_features(features)]
            pred = self.model.predict(X)[0]
            proba = self.model.predict_proba(X)[0]
            confidence = max(proba)
            side = Side.BUY if pred == 1 else Side.SELL if pred == -1 else None
            return {
                "side": side,
                "confidence": round(float(confidence), 3),
                "reason": f"ML prediction (class={pred}, conf={confidence:.2f})",
            }
        except Exception as e:
            logger.error("ML prediction error: %s", e)
            return {"side": None, "confidence": 0, "reason": f"Prediction error: {e}"}

    def train(self, data: List[Dict[str, Any]], labels: List[int]) -> Dict[str, Any]:
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import cross_val_score

            X = [self._extract_features(d) for d in data]
            self.model = RandomForestClassifier(
                n_estimators=160,
                max_depth=6,
                min_samples_leaf=6,
                random_state=42,
                class_weight="balanced_subsample",
                n_jobs=1,
            )
            cv = max(2, min(5, len(X) // 20))
            scores = cross_val_score(self.model, X, labels, cv=cv)
            self.model.fit(X, labels)
            self._trained = True
            return {
                "status": "trained",
                "samples": len(X),
                "cv_accuracy": round(float(scores.mean()), 4),
                "cv_std": round(float(scores.std()), 4),
                "features": self.features_required,
            }
        except ImportError:
            return {"status": "error", "message": "scikit-learn not installed. Run: pip install scikit-learn"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class MLSignalService:
    def __init__(self):
        self._models: Dict[str, MLModelBase] = {}
        self._dataset_prediction_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._max_cache_candles = 12000
        self._max_train_samples = 20000
        self._register_defaults()

    def _register_defaults(self):
        self._models["sklearn_rf"] = SklearnSignalModel()

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {"name": model.name, "features": model.features_required, "type": type(model).__name__}
            for model in self._models.values()
        ]

    def predict(self, model_name: str, features: Dict[str, Any]) -> Dict[str, Any]:
        model = self._models.get(model_name)
        if not model:
            return {"error": f"Model '{model_name}' not found"}
        return model.predict(features)

    def train(self, model_name: str, data: List[Dict[str, Any]], labels: List[int]) -> Dict[str, Any]:
        model = self._models.get(model_name)
        if not model:
            return {"error": f"Model '{model_name}' not found"}
        return model.train(data, labels)

    def _dataset_cache_key(self, candles: List[Dict[str, Any]], symbol: str, horizon: int) -> str:
        if not candles:
            return f"{symbol}:empty:{horizon}"
        return f"{symbol}:{len(candles)}:{candles[0].get('timestamp','')}:{candles[-1].get('timestamp','')}:{horizon}"

    def _remember_prediction_cache(self, key: str, predictions: List[Dict[str, Any]], size: int):
        if size > self._max_cache_candles:
            return
        self._dataset_prediction_cache[key] = predictions
        if len(self._dataset_prediction_cache) > 8:
            oldest_key = next(iter(self._dataset_prediction_cache))
            self._dataset_prediction_cache.pop(oldest_key, None)

    def _neutral_predictions(self, size: int) -> List[Dict[str, Any]]:
        return [
            {
                "side": None,
                "confidence": 0.0,
                "prob_buy": 0.0,
                "prob_sell": 0.0,
                "prob_hold": 1.0,
                "label": 0,
                "reason": "Neutral ML regime",
            }
            for _ in range(size)
        ]

    def _build_market_dataset(self, candles: List[Dict[str, Any]], horizon: int) -> tuple[List[int], List[List[float]], List[int]]:
        from .indicators import atr, bollinger_bands, ema, macd, rsi, volume_profile

        closes = [c["close"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        volumes = [c.get("volume", 1) for c in candles]

        ema_fast = ema(closes, 8)
        ema_mid = ema(closes, 21)
        ema_slow = ema(closes, 55)
        rsi_vals = rsi(closes, 14)
        macd_data = macd(closes, 12, 26, 9)
        atr_vals = atr(highs, lows, closes, 14)
        vol_data = volume_profile(volumes, 20)
        bb = bollinger_bands(closes, 20, 2.0)

        start_index = max(60, horizon + 5)
        indexes: List[int] = []
        features: List[List[float]] = []
        labels: List[int] = []

        for i in range(start_index, len(candles) - horizon):
            close = closes[i]
            if close <= 0:
                continue
            future_close = closes[i + horizon]
            future_return_pct = ((future_close - close) / close) * 100
            atr_pct = (atr_vals[i] / close * 100) if atr_vals[i] else 0
            gap_pct = abs(candles[i].get("open", close) - closes[i - 1]) / closes[i - 1] * 100 if i > 0 and closes[i - 1] else 0
            bb_range = bb["upper"][i] - bb["lower"][i]
            bb_position = (close - bb["lower"][i]) / bb_range if bb_range > 0 else 0.5
            ribbon_spread = abs(ema_fast[i] - ema_slow[i]) / close
            threshold = max(0.25, atr_pct * 0.55)

            label = 0
            if future_return_pct > threshold:
                label = 1
            elif future_return_pct < -threshold:
                label = -1

            indexes.append(i)
            features.append([
                rsi_vals[i] / 100,
                macd_data["histogram"][i],
                1.0 if ema_fast[i] > ema_mid[i] else 0.0,
                vol_data["relative"][i],
                atr_pct,
                bb_position,
                ribbon_spread,
                gap_pct,
            ])
            labels.append(label)

        return indexes, features, labels

    def get_market_direction_predictions(
        self,
        candles: List[Dict[str, Any]],
        symbol: str,
        horizon: int = 5,
    ) -> List[Dict[str, Any]]:
        cache_key = self._dataset_cache_key(candles, symbol, horizon)
        if cache_key in self._dataset_prediction_cache:
            return self._dataset_prediction_cache[cache_key]

        predictions = self._neutral_predictions(len(candles))
        try:
            from sklearn.ensemble import RandomForestClassifier

            indexes, features, labels = self._build_market_dataset(candles, horizon)
            if len(features) < 80 or len(set(labels)) < 2:
                self._remember_prediction_cache(cache_key, predictions, len(candles))
                return predictions

            split_index = max(int(len(features) * 0.7), 60)
            train_x = features[:split_index]
            train_y = labels[:split_index]
            if len(train_x) > self._max_train_samples:
                step = max(1, len(train_x) // self._max_train_samples)
                train_x = train_x[::step]
                train_y = train_y[::step]
            model = RandomForestClassifier(
                n_estimators=180,
                max_depth=7,
                min_samples_leaf=8,
                random_state=42,
                class_weight="balanced_subsample",
                n_jobs=1,
            )
            model.fit(train_x, train_y)
            class_index = {cls: idx for idx, cls in enumerate(model.classes_)}

            chunk_size = 5000
            for offset in range(0, len(features), chunk_size):
                chunk = features[offset:offset + chunk_size]
                probabilities = model.predict_proba(chunk)
                for local_idx, probs in enumerate(probabilities):
                    candle_index = indexes[offset + local_idx]
                    prob_buy = float(probs[class_index.get(1, 0)]) if 1 in class_index else 0.0
                    prob_sell = float(probs[class_index.get(-1, 0)]) if -1 in class_index else 0.0
                    prob_hold = float(probs[class_index.get(0, 0)]) if 0 in class_index else 0.0
                    if prob_buy > prob_sell and prob_buy > prob_hold:
                        side = Side.BUY
                        confidence = prob_buy
                        label = 1
                    elif prob_sell > prob_buy and prob_sell > prob_hold:
                        side = Side.SELL
                        confidence = prob_sell
                        label = -1
                    else:
                        side = None
                        confidence = prob_hold
                        label = 0

                    predictions[candle_index] = {
                        "side": side,
                        "confidence": round(confidence, 4),
                        "prob_buy": round(prob_buy, 4),
                        "prob_sell": round(prob_sell, 4),
                        "prob_hold": round(prob_hold, 4),
                        "label": label,
                        "reason": f"RF horizon={horizon} candles",
                    }

            self._remember_prediction_cache(cache_key, predictions, len(candles))
            return predictions
        except Exception as exc:
            logger.warning("Market direction prediction fallback to neutral: %s", exc)
            self._remember_prediction_cache(cache_key, predictions, len(candles))
            return predictions

    def generate_signal_from_candles(
        self,
        model_name: str,
        candles: List[Dict[str, Any]],
        symbol: str,
        exchange: str = "NSE",
    ) -> Optional[Signal]:
        if len(candles) < 30:
            return None

        predictions = self.get_market_direction_predictions(candles, symbol, horizon=5)
        latest = predictions[-1]
        if latest.get("side") and latest.get("confidence", 0) > 0.6:
            return Signal(
                symbol=symbol,
                exchange=exchange,
                side=latest["side"],
                confidence=latest["confidence"],
                reason=latest.get("reason", "ML signal"),
                strategy_name=f"ml_{model_name}",
                price=candles[-1]["close"],
                metadata={
                    "prob_buy": latest.get("prob_buy", 0),
                    "prob_sell": latest.get("prob_sell", 0),
                    "prob_hold": latest.get("prob_hold", 0),
                },
            )
        return None


ml_service = MLSignalService()