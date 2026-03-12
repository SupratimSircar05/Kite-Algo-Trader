"""
ML Signal Module: Hooks for machine learning-based signal generation.
Provides a clean interface for sklearn/PyTorch/TensorFlow models.
"""
import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

from .models import Signal, now_utc
from .enums import Side

logger = logging.getLogger("ml_signals")


class MLModelBase(ABC):
    """Abstract interface for ML signal models."""

    name: str = "base_ml"
    features_required: List[str] = []

    @abstractmethod
    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Predict signal from features. Returns {side, confidence, reason}."""
        ...

    @abstractmethod
    def train(self, data: List[Dict[str, Any]], labels: List[int]) -> Dict[str, Any]:
        """Train the model. Returns training metrics."""
        ...

    def save(self, path: str):
        """Save model to disk."""
        raise NotImplementedError

    def load(self, path: str):
        """Load model from disk."""
        raise NotImplementedError


class SklearnSignalModel(MLModelBase):
    """Sklearn-based signal model (Random Forest classifier)."""

    name = "sklearn_rf"
    features_required = ["rsi", "macd_hist", "ema_cross", "volume_relative", "atr_pct", "bb_position"]

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
                "confidence": round(confidence, 3),
                "reason": f"ML prediction (class={pred}, conf={confidence:.2f})",
            }
        except Exception as e:
            logger.error(f"ML prediction error: {e}")
            return {"side": None, "confidence": 0, "reason": f"Prediction error: {e}"}

    def train(self, data: List[Dict[str, Any]], labels: List[int]) -> Dict[str, Any]:
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import cross_val_score
            X = [self._extract_features(d) for d in data]
            self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
            scores = cross_val_score(self.model, X, labels, cv=min(5, len(X) // 3 or 2))
            self.model.fit(X, labels)
            self._trained = True
            return {
                "status": "trained",
                "samples": len(X),
                "cv_accuracy": round(scores.mean(), 4),
                "cv_std": round(scores.std(), 4),
                "features": self.features_required,
            }
        except ImportError:
            return {"status": "error", "message": "scikit-learn not installed. Run: pip install scikit-learn"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class MLSignalService:
    """Service layer for ML model management."""

    def __init__(self):
        self._models: Dict[str, MLModelBase] = {}
        self._register_defaults()

    def _register_defaults(self):
        self._models["sklearn_rf"] = SklearnSignalModel()

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {"name": m.name, "features": m.features_required, "type": type(m).__name__}
            for m in self._models.values()
        ]

    def predict(self, model_name: str, features: Dict[str, Any]) -> Dict[str, Any]:
        model = self._models.get(model_name)
        if not model:
            return {"error": f"Model '{model_name}' not found"}
        return model.predict(features)

    def train(self, model_name: str, data: List[Dict], labels: List[int]) -> Dict[str, Any]:
        model = self._models.get(model_name)
        if not model:
            return {"error": f"Model '{model_name}' not found"}
        return model.train(data, labels)

    def generate_signal_from_candles(self, model_name: str, candles: List[Dict],
                                      symbol: str, exchange: str = "NSE") -> Optional[Signal]:
        """Generate a signal from candle data using ML model."""
        if len(candles) < 30:
            return None
        from .indicators import rsi, macd, ema, atr, volume_profile, bollinger_bands
        closes = [c["close"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        volumes = [c.get("volume", 1) for c in candles]

        rsi_vals = rsi(closes, 14)
        macd_data = macd(closes)
        ema8 = ema(closes, 8)
        ema21 = ema(closes, 21)
        atr_vals = atr(highs, lows, closes, 14)
        vol = volume_profile(volumes, 20)
        bb = bollinger_bands(closes, 20)

        features = {
            "rsi": rsi_vals[-1],
            "macd_hist": macd_data["histogram"][-1],
            "ema_cross": ema8[-1] > ema21[-1],
            "volume_relative": vol["relative"][-1],
            "atr_pct": (atr_vals[-1] / closes[-1] * 100) if closes[-1] > 0 else 0,
            "bb_position": (closes[-1] - bb["lower"][-1]) / (bb["upper"][-1] - bb["lower"][-1]) if (bb["upper"][-1] - bb["lower"][-1]) > 0 else 0.5,
        }

        result = self.predict(model_name, features)
        if result.get("side") and result.get("confidence", 0) > 0.6:
            return Signal(
                symbol=symbol, exchange=exchange,
                side=result["side"], confidence=result["confidence"],
                reason=result.get("reason", "ML signal"),
                strategy_name=f"ml_{model_name}",
                price=closes[-1],
            )
        return None


ml_service = MLSignalService()
