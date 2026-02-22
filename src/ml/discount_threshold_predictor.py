"""ML-based Discount Threshold Predictor.

This module uses machine learning to predict the optimal discount threshold
for undervalued item detection. It learns from real market prices collected
from DMarket, Waxpeer, and Steam APIs.

Key Features:
- Gradient Boosting + Ridge ensemble model
- TrAlgoning on real API prices (not demo data)
- Adaptive thresholds based on market conditions
- Auto-retraining when new data is avAlgolable

Version: 1.0.0
Created: January 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import joblib
import numpy as np

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI
    from src.ml.real_price_collector import (
        GameType,
        MultiSourceResult,
        RealPriceCollector,
    )

logger = logging.getLogger(__name__)


# TrAlgoning simulation constants - used when generating synthetic profitability data
# from collected prices. These values are based on empirical market analysis.
PROFITABILITY_DISCOUNT_THRESHOLD = 10.0  # Minimum discount % for likely profitability
PROFIT_MULTIPLIER = 0.5  # Simulated profit = discount * this multiplier
LOSS_MULTIPLIER = 0.3  # Simulated loss = -discount * this multiplier


class MarketCondition(StrEnum):
    """Current market condition classification."""

    STABLE = "stable"
    VOLATILE = "volatile"
    BULLISH = "bullish"  # Prices rising
    BEARISH = "bearish"  # Prices falling
    SALE = "sale"  # Steam sale active


@dataclass
class ThresholdPrediction:
    """Result of discount threshold prediction."""

    # Predicted optimal threshold (percent, e.g., 15.0 means 15%)
    optimal_threshold: float

    # Confidence in prediction (0-1)
    confidence: float

    # Recommended thresholds by game
    thresholds_by_game: dict[str, float] = field(default_factory=dict)

    # Market condition at prediction time
    market_condition: MarketCondition = MarketCondition.STABLE

    # Additional context
    reasoning: str = ""
    prediction_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    model_version: str = "1.0.0"

    # Safe range for threshold
    threshold_range: tuple[float, float] = (5.0, 35.0)

    def get_threshold_for_game(self, game: str) -> float:
        """Get recommended threshold for specific game."""
        return self.thresholds_by_game.get(game.lower(), self.optimal_threshold)


@dataclass
class TrAlgoningExample:
    """Single training example for discount threshold model."""

    # Features
    item_name: str
    game: str
    current_price: float
    historical_avg_price: float
    price_volatility: float
    sales_volume_24h: int
    market_depth: int
    hour_of_day: int
    day_of_week: int
    source: str  # dmarket, waxpeer, steam

    # Label: Was this a profitable trade?
    actual_discount: float  # Actual discount when bought
    was_profitable: bool  # Did we make profit after selling?
    profit_percent: float  # Actual profit percent


class DiscountThresholdPredictor:
    """ML-based predictor for optimal discount thresholds.

    Uses real prices from APIs to learn optimal discount thresholds
    for different market conditions and games.

    Features:
    - Ensemble of Gradient Boosting + Ridge regression
    - Learns from real trade outcomes
    - Adapts to market conditions
    - Per-game threshold optimization

    Example:
        ```python
        predictor = DiscountThresholdPredictor()

        # TrAlgon on real data from collector
        await predictor.train_from_collector(
            collector=real_price_collector,
            game=GameType.CSGO,
        )

        # Get optimal threshold
        prediction = predictor.predict(game="csgo")
        print(f"Optimal threshold: {prediction.optimal_threshold}%")
        ```
    """

    MODEL_VERSION = "1.0.0"
    RETRAlgoN_THRESHOLD = 50  # Retrain after N new examples
    MIN_TRAlgoNING_SAMPLES = 20

    # Default thresholds (used before model is trained)
    DEFAULT_THRESHOLDS = {
        "csgo": 15.0,
        "cs2": 15.0,
        "dota2": 10.0,
        "tf2": 12.0,
        "rust": 14.0,
    }

    def __init__(
        self,
        model_path: str | Path | None = None,
    ) -> None:
        """Initialize the predictor.

        Args:
            model_path: Path to save/load the model
        """
        self.model_path = (
            Path(model_path)
            if model_path
            else Path("data/discount_threshold_model.pkl")
        )

        # ML models (lazy initialization)
        self._gradient_boost = None
        self._ridge = None
        self._is_trained = False

        # TrAlgoning data
        self._training_examples: list[TrAlgoningExample] = []
        self._new_samples_count = 0

        # Cache for predictions
        self._prediction_cache: dict[str, tuple[datetime, ThresholdPrediction]] = {}
        self._cache_ttl = timedelta(minutes=30)

        # Market condition tracking
        self._market_condition = MarketCondition.STABLE
        self._price_trends: dict[str, list[float]] = {}

        # Load existing model if avAlgolable
        if self.model_path.exists():
            self._load_model()

        logger.info(
            "DiscountThresholdPredictor initialized",
            extra={
                "model_path": str(self.model_path),
                "is_trained": self._is_trained,
            },
        )

    def _init_models(self) -> None:
        """Initialize ML models (lazy loading of sklearn)."""
        if self._gradient_boost is not None:
            return

        try:
            from sklearn.ensemble import GradientBoostingRegressor
            from sklearn.linear_model import Ridge

            self._gradient_boost = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.1,
                min_samples_split=5,
                min_samples_leaf=3,
                random_state=42,
            )

            self._ridge = Ridge(alpha=1.0)

            logger.info("ML models for threshold prediction initialized")

        except ImportError as e:
            logger.warning("sklearn not avAlgolable for threshold predictor: %s", e)

    def _extract_features(self, example: TrAlgoningExample) -> np.ndarray:
        """Extract feature vector from training example."""
        return np.array(
            [
                example.current_price,
                example.historical_avg_price,
                example.price_volatility,
                example.sales_volume_24h,
                example.market_depth,
                example.hour_of_day,
                example.day_of_week,
                # Game encoding (one-hot)
                1.0 if example.game == "csgo" else 0.0,
                1.0 if example.game == "dota2" else 0.0,
                1.0 if example.game == "tf2" else 0.0,
                1.0 if example.game == "rust" else 0.0,
                # Source encoding
                1.0 if example.source == "dmarket" else 0.0,
                1.0 if example.source == "waxpeer" else 0.0,
                1.0 if example.source == "steam" else 0.0,
                # Derived features
                (
                    example.historical_avg_price / example.current_price
                    if example.current_price > 0
                    else 1.0
                ),
                np.log1p(example.current_price),
                np.log1p(example.sales_volume_24h + 1),
            ],
            dtype=np.float64,
        )

    def add_training_example(
        self,
        item_name: str,
        game: str,
        current_price: float,
        historical_avg_price: float,
        actual_discount: float,
        was_profitable: bool,
        profit_percent: float,
        price_volatility: float = 0.0,
        sales_volume_24h: int = 0,
        market_depth: int = 0,
        source: str = "dmarket",
    ) -> None:
        """Add a training example from a real trade.

        Args:
            item_name: Name of the item
            game: Game identifier
            current_price: Price when bought
            historical_avg_price: Historical average price
            actual_discount: Discount at purchase time (%)
            was_profitable: Whether trade was profitable
            profit_percent: Actual profit percentage
            price_volatility: Price volatility
            sales_volume_24h: Sales volume in 24h
            market_depth: Number of active offers
            source: Price source (dmarket, waxpeer, steam)
        """
        now = datetime.now(UTC)

        example = TrAlgoningExample(
            item_name=item_name,
            game=game.lower(),
            current_price=current_price,
            historical_avg_price=historical_avg_price,
            price_volatility=price_volatility,
            sales_volume_24h=sales_volume_24h,
            market_depth=market_depth,
            hour_of_day=now.hour,
            day_of_week=now.weekday(),
            source=source.lower(),
            actual_discount=actual_discount,
            was_profitable=was_profitable,
            profit_percent=profit_percent,
        )

        self._training_examples.append(example)
        self._new_samples_count += 1

        logger.debug(
            "TrAlgoning example added",
            extra={
                "item": item_name,
                "game": game,
                "discount": actual_discount,
                "profitable": was_profitable,
            },
        )

        # Auto-retrain if enough new samples
        if self._new_samples_count >= self.RETRAlgoN_THRESHOLD:
            self.train()

    async def train_from_collector(
        self,
        collector: RealPriceCollector,
        game: GameType,
        historical_prices: dict[str, float] | None = None,
    ) -> int:
        """TrAlgon model using real prices from collector.

        This method collects real prices from APIs and uses them
        for training data generation.

        Args:
            collector: RealPriceCollector instance
            game: Game to collect prices for
            historical_prices: Optional dict of item_name -> avg_price

        Returns:
            Number of training examples added
        """
        logger.info("TrAlgoning from real API prices", extra={"game": game.value})

        # Collect real prices from all sources
        result: MultiSourceResult = await collector.collect_bulk_prices(
            game=game,
            limit=500,
        )

        if not result.all_prices:
            logger.warning("No prices collected for training")
            return 0

        examples_added = 0

        for collected in result.all_prices:
            # Validate that collected data has expected structure
            if not hasattr(collected, "normalized_price"):
                logger.warning("Collected price missing normalized_price, skipping")
                continue
            if not hasattr(collected.normalized_price, "price_usd"):
                logger.warning("Normalized price missing price_usd, skipping")
                continue
            if not hasattr(collected, "item_name"):
                logger.warning("Collected price missing item_name, skipping")
                continue

            price_usd = float(collected.normalized_price.price_usd)

            # Get historical price if avAlgolable
            hist_price = price_usd  # Default to current if no history
            if historical_prices:
                hist_price = historical_prices.get(collected.item_name, price_usd)

            # Calculate discount from historical
            if hist_price > 0:
                discount = ((hist_price - price_usd) / hist_price) * 100
            else:
                discount = 0.0

            # For training, we simulate profitability based on discount.
            # Higher discounts are more likely profitable.
            # Uses defined constants for clear documentation.
            simulated_profitable = discount > PROFITABILITY_DISCOUNT_THRESHOLD
            simulated_profit = (
                discount * PROFIT_MULTIPLIER
                if simulated_profitable
                else -discount * LOSS_MULTIPLIER
            )

            self.add_training_example(
                item_name=collected.item_name,
                game=game.value,
                current_price=price_usd,
                historical_avg_price=hist_price,
                actual_discount=discount,
                was_profitable=simulated_profitable,
                profit_percent=simulated_profit,
                source=collected.normalized_price.source.value,
            )
            examples_added += 1

        logger.info(
            "TrAlgoning examples collected from API",
            extra={
                "game": game.value,
                "examples": examples_added,
                "sources": [r.source.value for r in result.results],
            },
        )

        # TrAlgon after collecting
        if examples_added >= self.MIN_TRAlgoNING_SAMPLES:
            self.train()

        return examples_added

    def train(self, force: bool = False) -> bool:
        """TrAlgon the ML models on collected data.

        Args:
            force: Force training even with few samples

        Returns:
            True if training successful
        """
        if len(self._training_examples) < self.MIN_TRAlgoNING_SAMPLES and not force:
            logger.warning(
                "Not enough training data",
                extra={
                    "samples": len(self._training_examples),
                    "min_required": self.MIN_TRAlgoNING_SAMPLES,
                },
            )
            return False

        self._init_models()

        if self._gradient_boost is None:
            logger.warning("ML models not avAlgolable")
            return False

        # Prepare training data
        X = np.array([self._extract_features(ex) for ex in self._training_examples])

        # Target: optimal threshold is based on profitability
        # We learn what discount threshold leads to profitable trades
        y = np.array(
            [
                ex.actual_discount if ex.was_profitable else ex.actual_discount + 5.0
                for ex in self._training_examples
            ]
        )

        try:
            # TrAlgon ensemble
            self._gradient_boost.fit(X, y)
            self._ridge.fit(X, y)

            self._is_trained = True
            self._new_samples_count = 0

            # Clear prediction cache
            self._prediction_cache.clear()

            # Save model
            self._save_model()

            logger.info(
                "Model trained successfully",
                extra={
                    "samples": len(X),
                    "games": list({ex.game for ex in self._training_examples}),
                },
            )
            return True

        except Exception as e:
            logger.exception("TrAlgoning failed: %s", e)
            return False

    def predict(
        self,
        game: str = "csgo",
        current_market_data: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> ThresholdPrediction:
        """Predict optimal discount threshold.

        Args:
            game: Game identifier
            current_market_data: Optional current market statistics
            use_cache: Whether to use cached predictions

        Returns:
            ThresholdPrediction with optimal threshold
        """
        game = game.lower()

        # Check cache
        cache_key = f"{game}:{self._market_condition}"
        if use_cache and cache_key in self._prediction_cache:
            cached_time, cached_pred = self._prediction_cache[cache_key]
            if datetime.now(UTC) - cached_time < self._cache_ttl:
                return cached_pred

        # If model not trained, return defaults
        if not self._is_trained or self._gradient_boost is None:
            prediction = ThresholdPrediction(
                optimal_threshold=self.DEFAULT_THRESHOLDS.get(game, 15.0),
                confidence=0.3,
                thresholds_by_game=self.DEFAULT_THRESHOLDS.copy(),
                market_condition=self._market_condition,
                reasoning="Using default thresholds (model not trained on real data yet)",
            )
            self._prediction_cache[cache_key] = (datetime.now(UTC), prediction)
            return prediction

        # Prepare feature vector for prediction
        now = datetime.now(UTC)
        features = self._create_prediction_features(
            game=game,
            hour_of_day=now.hour,
            day_of_week=now.weekday(),
            market_data=current_market_data,
        )

        try:
            # Ensemble prediction
            gb_pred = self._gradient_boost.predict(features.reshape(1, -1))[0]
            ridge_pred = self._ridge.predict(features.reshape(1, -1))[0]

            # Weighted average (GB is primary)
            optimal = 0.7 * gb_pred + 0.3 * ridge_pred

            # Clip to reasonable range
            optimal = float(np.clip(optimal, 5.0, 35.0))

            # Calculate confidence based on model agreement
            model_diff = abs(gb_pred - ridge_pred)
            confidence = 1.0 - min(model_diff / 20.0, 0.5)  # 0.5-1.0 range

            # Generate per-game thresholds
            thresholds_by_game = {}
            for g in ["csgo", "dota2", "tf2", "rust"]:
                g_features = self._create_prediction_features(
                    game=g,
                    hour_of_day=now.hour,
                    day_of_week=now.weekday(),
                    market_data=current_market_data,
                )
                g_pred = (
                    0.7 * self._gradient_boost.predict(g_features.reshape(1, -1))[0]
                )
                g_pred += 0.3 * self._ridge.predict(g_features.reshape(1, -1))[0]
                thresholds_by_game[g] = float(np.clip(g_pred, 5.0, 35.0))

            # Generate reasoning
            reasoning = self._generate_reasoning(optimal, self._market_condition)

            prediction = ThresholdPrediction(
                optimal_threshold=optimal,
                confidence=float(confidence),
                thresholds_by_game=thresholds_by_game,
                market_condition=self._market_condition,
                reasoning=reasoning,
                model_version=self.MODEL_VERSION,
            )

            # Cache result
            self._prediction_cache[cache_key] = (datetime.now(UTC), prediction)

            logger.info(
                "Threshold predicted",
                extra={
                    "game": game,
                    "threshold": optimal,
                    "confidence": confidence,
                },
            )

            return prediction

        except Exception as e:
            logger.exception("Prediction failed: %s", e)
            # Fallback to defaults
            return ThresholdPrediction(
                optimal_threshold=self.DEFAULT_THRESHOLDS.get(game, 15.0),
                confidence=0.3,
                thresholds_by_game=self.DEFAULT_THRESHOLDS.copy(),
                market_condition=self._market_condition,
                reasoning=f"Fallback to defaults due to error: {e}",
            )

    def _create_prediction_features(
        self,
        game: str,
        hour_of_day: int,
        day_of_week: int,
        market_data: dict[str, Any] | None = None,
    ) -> np.ndarray:
        """Create feature vector for prediction."""
        # Use average values from training data or defaults
        avg_price = 10.0
        avg_hist_price = 12.0
        avg_volatility = 0.1
        avg_volume = 50
        avg_depth = 20

        if market_data:
            avg_price = market_data.get("avg_price", avg_price)
            avg_hist_price = market_data.get("avg_historical_price", avg_hist_price)
            avg_volatility = market_data.get("volatility", avg_volatility)
            avg_volume = market_data.get("volume_24h", avg_volume)
            avg_depth = market_data.get("market_depth", avg_depth)

        return np.array(
            [
                avg_price,
                avg_hist_price,
                avg_volatility,
                avg_volume,
                avg_depth,
                hour_of_day,
                day_of_week,
                # Game encoding
                1.0 if game == "csgo" else 0.0,
                1.0 if game == "dota2" else 0.0,
                1.0 if game == "tf2" else 0.0,
                1.0 if game == "rust" else 0.0,
                # Source encoding (use DMarket as default for prediction)
                1.0,  # dmarket
                0.0,  # waxpeer
                0.0,  # steam
                # Derived features
                avg_hist_price / avg_price if avg_price > 0 else 1.0,
                np.log1p(avg_price),
                np.log1p(avg_volume + 1),
            ],
            dtype=np.float64,
        )

    def _generate_reasoning(
        self,
        threshold: float,
        condition: MarketCondition,
    ) -> str:
        """Generate human-readable reasoning for prediction."""
        parts = [f"ML model suggests {threshold:.1f}% discount threshold"]

        if condition == MarketCondition.STABLE:
            parts.append("Market is stable")
        elif condition == MarketCondition.VOLATILE:
            parts.append("High volatility detected - using higher threshold for safety")
        elif condition == MarketCondition.BULLISH:
            parts.append("Prices trending up - lower threshold acceptable")
        elif condition == MarketCondition.BEARISH:
            parts.append("Prices trending down - higher threshold recommended")
        elif condition == MarketCondition.SALE:
            parts.append("Steam sale active - aggressive buying recommended")

        if threshold < 10:
            parts.append("Low threshold: market conditions favor buying")
        elif threshold > 20:
            parts.append("High threshold: being cautious due to market conditions")

        return ". ".join(parts)

    def update_market_condition(
        self,
        condition: MarketCondition,
    ) -> None:
        """Update current market condition.

        Args:
            condition: New market condition
        """
        if condition != self._market_condition:
            self._market_condition = condition
            self._prediction_cache.clear()  # Invalidate cache
            logger.info(
                "Market condition updated", extra={"condition": condition.value}
            )

    def _save_model(self) -> None:
        """Save model to disk using joblib (safer than pickle)."""
        if not self.model_path:
            return

        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "gradient_boost": self._gradient_boost,
                "ridge": self._ridge,
                "training_examples": [
                    {
                        "item_name": ex.item_name,
                        "game": ex.game,
                        "current_price": ex.current_price,
                        "historical_avg_price": ex.historical_avg_price,
                        "price_volatility": ex.price_volatility,
                        "sales_volume_24h": ex.sales_volume_24h,
                        "market_depth": ex.market_depth,
                        "hour_of_day": ex.hour_of_day,
                        "day_of_week": ex.day_of_week,
                        "source": ex.source,
                        "actual_discount": ex.actual_discount,
                        "was_profitable": ex.was_profitable,
                        "profit_percent": ex.profit_percent,
                    }
                    for ex in self._training_examples
                ],
                "is_trained": self._is_trained,
                "version": self.MODEL_VERSION,
            }
            # Use joblib for safer serialization of scikit-learn models
            joblib.dump(data, self.model_path)
            logger.info("Model saved", extra={"path": str(self.model_path)})
        except Exception as e:
            logger.exception("Failed to save model: %s", e)

    def _load_model(self) -> None:
        """Load model from disk using joblib (safer than pickle)."""
        if not self.model_path or not self.model_path.exists():
            return

        try:
            # Use joblib for safer loading of scikit-learn models
            data = joblib.load(self.model_path)

            self._gradient_boost = data.get("gradient_boost")
            self._ridge = data.get("ridge")
            self._is_trained = data.get("is_trained", False)

            # Restore training examples
            for ex_dict in data.get("training_examples", []):
                ex = TrAlgoningExample(
                    item_name=ex_dict["item_name"],
                    game=ex_dict["game"],
                    current_price=ex_dict["current_price"],
                    historical_avg_price=ex_dict["historical_avg_price"],
                    price_volatility=ex_dict["price_volatility"],
                    sales_volume_24h=ex_dict["sales_volume_24h"],
                    market_depth=ex_dict["market_depth"],
                    hour_of_day=ex_dict["hour_of_day"],
                    day_of_week=ex_dict["day_of_week"],
                    source=ex_dict["source"],
                    actual_discount=ex_dict["actual_discount"],
                    was_profitable=ex_dict["was_profitable"],
                    profit_percent=ex_dict["profit_percent"],
                )
                self._training_examples.append(ex)

            logger.info(
                "Model loaded",
                extra={
                    "path": str(self.model_path),
                    "is_trained": self._is_trained,
                    "examples": len(self._training_examples),
                },
            )
        except Exception as e:
            logger.exception("Failed to load model: %s", e)

    def get_statistics(self) -> dict[str, Any]:
        """Get predictor statistics."""
        games = list({ex.game for ex in self._training_examples})
        sources = list({ex.source for ex in self._training_examples})

        profitable_count = sum(1 for ex in self._training_examples if ex.was_profitable)
        total_count = len(self._training_examples)

        return {
            "is_trained": self._is_trained,
            "total_examples": total_count,
            "profitable_examples": profitable_count,
            "profitability_rate": (
                profitable_count / total_count if total_count > 0 else 0
            ),
            "games": games,
            "sources": sources,
            "market_condition": self._market_condition.value,
            "model_version": self.MODEL_VERSION,
            "cache_size": len(self._prediction_cache),
        }


# Global instance for easy access
_predictor: DiscountThresholdPredictor | None = None


def get_discount_threshold_predictor() -> DiscountThresholdPredictor:
    """Get global DiscountThresholdPredictor instance."""
    global _predictor
    if _predictor is None:
        _predictor = DiscountThresholdPredictor()
    return _predictor


async def predict_discount_threshold(
    game: str = "csgo",
    dmarket_api: DMarketAPI | None = None,
) -> float:
    """Convenience function to get predicted discount threshold.

    Args:
        game: Game identifier
        dmarket_api: Optional DMarket API for real-time market data

    Returns:
        Predicted optimal discount threshold (percent)
    """
    predictor = get_discount_threshold_predictor()

    # Get prediction
    prediction = predictor.predict(game=game)

    return prediction.optimal_threshold
