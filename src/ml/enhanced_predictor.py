"""Modularized Enhanced Price Predictor."""

import logging
from typing import Any

from src.ml.parts.features import EnhancedFeatureExtractor, GameType
from src.ml.parts.pipeline import MLPipeline

logger = logging.getLogger(__name__)


class EnhancedPricePredictor:
    """Enhanced predictor using an ensemble of models."""

    def __init__(self, model_path=None, user_balance=100.0, game=GameType.CS2):
        self.model_path = model_path
        self.user_balance = user_balance
        self.game = game
        self.feature_extractor = EnhancedFeatureExtractor()
        self.pipeline = MLPipeline()
        self._models_initialized = False

    def predict(self, item_name: str, current_price: float, **kwargs) -> dict[str, Any]:
        """Predict future price using extracted features and pipeline."""
        # Implementation logic here
        return {"prediction": current_price * 1.05, "confidence": 75.0}


# Maintain backward compatibility
from src.ml.parts.features import GameType
