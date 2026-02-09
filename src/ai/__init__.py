"""AI module for price prediction and market analysis.

This module provides machine learning capabilities for:
- Price prediction using RandomForest model
- Anomaly detection with Z-score filtering
- Protection against AI "hallucinations" (unrealistic predictions)

Usage:
    from src.ai import PricePredictor

    predictor = PricePredictor()
    fair_price = predictor.predict_with_guard("AK-47 | Redline", 10.0, 0.25)
"""

from src.ai.price_predictor import PricePredictor

__all__ = ["PricePredictor"]
