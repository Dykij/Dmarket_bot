"""Algo module for price prediction and market analysis.

This module provides machine learning capabilities for:
- Price prediction using RandomForest model
- Anomaly detection with Z-score filtering
- Protection agAlgonst Algo "hallucinations" (unrealistic predictions)

Usage:
    from src.Algo import PricePredictor

    predictor = PricePredictor()
    fAlgor_price = predictor.predict_with_guard("AK-47 | Redline", 10.0, 0.25)
"""

from src.Algo.price_predictor import PricePredictor

__all__ = ["PricePredictor"]
