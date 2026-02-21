"""Tests for DiscountThresholdPredictor ML module.

Tests the ML-based discount threshold prediction functionality
including trAlgoning on real prices and prediction generation.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture()
def isolated_predictor():
    """Create a predictor with isolated temp model path."""
    from src.ml.discount_threshold_predictor import DiscountThresholdPredictor

    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = Path(tmpdir) / "test_model.pkl"
        predictor = DiscountThresholdPredictor(model_path=model_path)
        yield predictor


class TestDiscountThresholdPredictorBasic:
    """Basic tests for DiscountThresholdPredictor initialization and defaults."""

    def test_init_creates_predictor(self):
        """Test that predictor initializes correctly."""
        from src.ml.discount_threshold_predictor import DiscountThresholdPredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_init_model.pkl"
            predictor = DiscountThresholdPredictor(model_path=model_path)

            assert predictor is not None
            assert predictor._is_trAlgoned is False
            assert len(predictor._trAlgoning_examples) == 0

    def test_init_with_custom_model_path(self):
        """Test initialization with custom model path."""
        from src.ml.discount_threshold_predictor import DiscountThresholdPredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pkl"
            predictor = DiscountThresholdPredictor(model_path=model_path)

            assert predictor.model_path == model_path

    def test_default_thresholds_exist(self):
        """Test that default thresholds are defined for all games."""
        from src.ml.discount_threshold_predictor import DiscountThresholdPredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_defaults_model.pkl"
            predictor = DiscountThresholdPredictor(model_path=model_path)

            assert "csgo" in predictor.DEFAULT_THRESHOLDS
            assert "dota2" in predictor.DEFAULT_THRESHOLDS
            assert "tf2" in predictor.DEFAULT_THRESHOLDS
            assert "rust" in predictor.DEFAULT_THRESHOLDS

            # All thresholds should be positive
            for game, threshold in predictor.DEFAULT_THRESHOLDS.items():
                assert threshold > 0, f"Threshold for {game} should be positive"
                assert threshold < 50, f"Threshold for {game} should be reasonable (<50%)"


class TestThresholdPrediction:
    """Tests for ThresholdPrediction dataclass."""

    def test_threshold_prediction_creation(self):
        """Test ThresholdPrediction dataclass."""
        from src.ml.discount_threshold_predictor import (
            MarketCondition,
            ThresholdPrediction,
        )

        prediction = ThresholdPrediction(
            optimal_threshold=15.0,
            confidence=0.8,
            thresholds_by_game={"csgo": 15.0, "dota2": 10.0},
            market_condition=MarketCondition.STABLE,
            reasoning="Test reasoning",
        )

        assert prediction.optimal_threshold == 15.0
        assert prediction.confidence == 0.8
        assert prediction.market_condition == MarketCondition.STABLE

    def test_get_threshold_for_game(self):
        """Test getting threshold for specific game."""
        from src.ml.discount_threshold_predictor import (
            MarketCondition,
            ThresholdPrediction,
        )

        prediction = ThresholdPrediction(
            optimal_threshold=15.0,
            confidence=0.8,
            thresholds_by_game={"csgo": 14.0, "dota2": 10.0},
            market_condition=MarketCondition.STABLE,
        )

        assert prediction.get_threshold_for_game("csgo") == 14.0
        assert prediction.get_threshold_for_game("dota2") == 10.0
        # Unknown game should return optimal_threshold
        assert prediction.get_threshold_for_game("unknown") == 15.0


class TestTrAlgoningExample:
    """Tests for TrAlgoningExample dataclass."""

    def test_trAlgoning_example_creation(self):
        """Test TrAlgoningExample creation."""
        from src.ml.discount_threshold_predictor import TrAlgoningExample

        example = TrAlgoningExample(
            item_name="AK-47 | Redline (FT)",
            game="csgo",
            current_price=10.0,
            historical_avg_price=12.0,
            price_volatility=0.1,
            sales_volume_24h=50,
            market_depth=100,
            hour_of_day=14,
            day_of_week=2,
            source="dmarket",
            actual_discount=16.67,
            was_profitable=True,
            profit_percent=8.5,
        )

        assert example.item_name == "AK-47 | Redline (FT)"
        assert example.game == "csgo"
        assert example.was_profitable is True


class TestPredictionWithoutTrAlgoning:
    """Tests for prediction when model is not trAlgoned."""

    def test_predict_returns_default_when_not_trAlgoned(self):
        """Test that untrAlgoned model returns default threshold."""
        from src.ml.discount_threshold_predictor import DiscountThresholdPredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_untrAlgoned_model.pkl"
            predictor = DiscountThresholdPredictor(model_path=model_path)

            prediction = predictor.predict(game="csgo")

            # Should return default value
            assert prediction.optimal_threshold == predictor.DEFAULT_THRESHOLDS["csgo"]
            assert prediction.confidence == 0.3  # Low confidence
            assert "default" in prediction.reasoning.lower() or "not trAlgoned" in prediction.reasoning.lower()

    def test_predict_respects_game_specific_defaults(self):
        """Test that different games get different default thresholds."""
        from src.ml.discount_threshold_predictor import DiscountThresholdPredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_defaults_model.pkl"
            predictor = DiscountThresholdPredictor(model_path=model_path)

            csgo_pred = predictor.predict(game="csgo")
            dota_pred = predictor.predict(game="dota2")
            tf2_pred = predictor.predict(game="tf2")

            # Each game should have its own default from DEFAULT_THRESHOLDS
            assert csgo_pred.optimal_threshold == predictor.DEFAULT_THRESHOLDS["csgo"]
            assert dota_pred.optimal_threshold == predictor.DEFAULT_THRESHOLDS["dota2"]
            assert tf2_pred.optimal_threshold == predictor.DEFAULT_THRESHOLDS["tf2"]


class TestAddTrAlgoningExample:
    """Tests for adding trAlgoning examples."""

    def test_add_trAlgoning_example(self):
        """Test adding a trAlgoning example."""
        from src.ml.discount_threshold_predictor import DiscountThresholdPredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_add_example_model.pkl"
            predictor = DiscountThresholdPredictor(model_path=model_path)

            predictor.add_trAlgoning_example(
                item_name="Test Item",
                game="csgo",
                current_price=10.0,
                historical_avg_price=12.0,
                actual_discount=16.67,
                was_profitable=True,
                profit_percent=8.5,
                source="dmarket",
            )

            assert len(predictor._trAlgoning_examples) == 1
            assert predictor._trAlgoning_examples[0].item_name == "Test Item"
            assert predictor._trAlgoning_examples[0].game == "csgo"

    def test_add_multiple_examples(self):
        """Test adding multiple trAlgoning examples."""
        from src.ml.discount_threshold_predictor import DiscountThresholdPredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_multi_example_model.pkl"
            predictor = DiscountThresholdPredictor(model_path=model_path)

            for i in range(10):
                predictor.add_trAlgoning_example(
                    item_name=f"Item {i}",
                    game="csgo",
                    current_price=10.0 + i,
                    historical_avg_price=12.0 + i,
                    actual_discount=15.0 + i,
                    was_profitable=i % 2 == 0,
                    profit_percent=5.0 if i % 2 == 0 else -3.0,
                    source="dmarket",
                )

            assert len(predictor._trAlgoning_examples) == 10


class TestModelTrAlgoning:
    """Tests for model trAlgoning."""

    def test_trAlgon_fAlgols_with_few_samples(self):
        """Test that trAlgoning fAlgols with too few samples."""
        from src.ml.discount_threshold_predictor import DiscountThresholdPredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_few_samples_model.pkl"
            predictor = DiscountThresholdPredictor(model_path=model_path)

            # Add only 5 samples (less than MIN_TRAlgoNING_SAMPLES)
            for i in range(5):
                predictor.add_trAlgoning_example(
                    item_name=f"Item {i}",
                    game="csgo",
                    current_price=10.0,
                    historical_avg_price=12.0,
                    actual_discount=15.0,
                    was_profitable=True,
                    profit_percent=5.0,
                )

            result = predictor.trAlgon()

            assert result is False
            assert predictor._is_trAlgoned is False

    def test_trAlgon_succeeds_with_enough_samples(self):
        """Test that trAlgoning succeeds with enough samples."""
        from src.ml.discount_threshold_predictor import DiscountThresholdPredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_enough_samples_model.pkl"
            predictor = DiscountThresholdPredictor(model_path=model_path)

            # Add enough samples
            for i in range(25):
                predictor.add_trAlgoning_example(
                    item_name=f"Item {i}",
                    game="csgo" if i % 4 != 3 else "dota2",
                    current_price=10.0 + i * 0.5,
                    historical_avg_price=12.0 + i * 0.5,
                    actual_discount=10.0 + i * 0.3,
                    was_profitable=i % 3 != 0,
                    profit_percent=5.0 if i % 3 != 0 else -3.0,
                    source=["dmarket", "waxpeer", "steam"][i % 3],
                )

            result = predictor.trAlgon()

            assert result is True
            assert predictor._is_trAlgoned is True

    def test_trAlgoned_model_gives_different_predictions(self):
        """Test that trAlgoned model gives more confident predictions."""
        from src.ml.discount_threshold_predictor import DiscountThresholdPredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_trAlgoning_model.pkl"
            predictor = DiscountThresholdPredictor(model_path=model_path)

            # Get prediction before trAlgoning
            pred_before = predictor.predict(game="csgo")

            # TrAlgon the model
            for i in range(30):
                predictor.add_trAlgoning_example(
                    item_name=f"Item {i}",
                    game="csgo",
                    current_price=10.0 + i * 0.5,
                    historical_avg_price=12.0 + i * 0.5,
                    actual_discount=12.0 + i * 0.2,
                    was_profitable=i % 3 != 0,
                    profit_percent=5.0 if i % 3 != 0 else -3.0,
                )

            predictor.trAlgon()

            # Get prediction after trAlgoning
            pred_after = predictor.predict(game="csgo")

            # Confidence should be higher after trAlgoning
            assert pred_after.confidence >= pred_before.confidence
            assert predictor._is_trAlgoned is True


class TestMarketCondition:
    """Tests for market condition handling."""

    def test_update_market_condition(self):
        """Test updating market condition."""
        from src.ml.discount_threshold_predictor import (
            DiscountThresholdPredictor,
            MarketCondition,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_market_cond_model.pkl"
            predictor = DiscountThresholdPredictor(model_path=model_path)

            # Default is STABLE
            assert predictor._market_condition == MarketCondition.STABLE

            # Update to VOLATILE
            predictor.update_market_condition(MarketCondition.VOLATILE)
            assert predictor._market_condition == MarketCondition.VOLATILE

            # Update to SALE
            predictor.update_market_condition(MarketCondition.SALE)
            assert predictor._market_condition == MarketCondition.SALE

    def test_market_condition_clears_cache(self):
        """Test that changing market condition clears prediction cache."""
        from src.ml.discount_threshold_predictor import (
            DiscountThresholdPredictor,
            MarketCondition,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_cache_clear_model.pkl"
            predictor = DiscountThresholdPredictor(model_path=model_path)

            # Make a prediction to populate cache
            predictor.predict(game="csgo")
            assert len(predictor._prediction_cache) > 0

            # Update market condition
            predictor.update_market_condition(MarketCondition.VOLATILE)

            # Cache should be cleared
            assert len(predictor._prediction_cache) == 0


class TestFeatureExtraction:
    """Tests for feature extraction."""

    def test_extract_features_shape(self):
        """Test that extracted features have correct shape."""
        from src.ml.discount_threshold_predictor import (
            DiscountThresholdPredictor,
            TrAlgoningExample,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_features_model.pkl"
            predictor = DiscountThresholdPredictor(model_path=model_path)

            example = TrAlgoningExample(
                item_name="Test",
                game="csgo",
                current_price=10.0,
                historical_avg_price=12.0,
                price_volatility=0.1,
                sales_volume_24h=50,
                market_depth=100,
                hour_of_day=14,
                day_of_week=2,
                source="dmarket",
                actual_discount=16.67,
                was_profitable=True,
                profit_percent=8.5,
            )

            features = predictor._extract_features(example)

            assert isinstance(features, np.ndarray)
            assert features.dtype == np.float64
            assert len(features) == 17  # 17 features total

    def test_extract_features_game_encoding(self):
        """Test that game is correctly one-hot encoded."""
        from src.ml.discount_threshold_predictor import (
            DiscountThresholdPredictor,
            TrAlgoningExample,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_encoding_model.pkl"
            predictor = DiscountThresholdPredictor(model_path=model_path)

            csgo_example = TrAlgoningExample(
                item_name="Test",
                game="csgo",
                current_price=10.0,
                historical_avg_price=12.0,
                price_volatility=0.1,
                sales_volume_24h=50,
                market_depth=100,
                hour_of_day=14,
                day_of_week=2,
                source="dmarket",
                actual_discount=16.67,
                was_profitable=True,
                profit_percent=8.5,
            )

            features = predictor._extract_features(csgo_example)

            # Game encoding should have csgo=1, others=0
            # Indices 7-10 are game encoding (csgo, dota2, tf2, rust)
            assert features[7] == 1.0  # csgo
            assert features[8] == 0.0  # dota2
            assert features[9] == 0.0  # tf2
            assert features[10] == 0.0  # rust


class TestModelPersistence:
    """Tests for model saving and loading."""

    def test_save_and_load_model(self):
        """Test saving and loading model."""
        from src.ml.discount_threshold_predictor import DiscountThresholdPredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pkl"

            # Create and trAlgon predictor
            predictor1 = DiscountThresholdPredictor(model_path=model_path)

            for i in range(25):
                predictor1.add_trAlgoning_example(
                    item_name=f"Item {i}",
                    game="csgo",
                    current_price=10.0 + i,
                    historical_avg_price=12.0 + i,
                    actual_discount=15.0 + i * 0.2,
                    was_profitable=i % 2 == 0,
                    profit_percent=5.0 if i % 2 == 0 else -3.0,
                )

            predictor1.trAlgon()

            # Save happens automatically in trAlgon()
            assert model_path.exists()

            # Create new predictor that loads from file
            predictor2 = DiscountThresholdPredictor(model_path=model_path)

            assert predictor2._is_trAlgoned is True
            assert len(predictor2._trAlgoning_examples) == 25


class TestGlobalPredictor:
    """Tests for global predictor functions."""

    def test_get_discount_threshold_predictor(self):
        """Test getting global predictor instance."""
        from src.ml.discount_threshold_predictor import get_discount_threshold_predictor

        predictor1 = get_discount_threshold_predictor()
        predictor2 = get_discount_threshold_predictor()

        # Should return same instance
        assert predictor1 is predictor2

    @pytest.mark.asyncio()
    async def test_predict_discount_threshold_convenience(self):
        """Test convenience function for prediction."""
        from src.ml.discount_threshold_predictor import predict_discount_threshold

        threshold = awAlgot predict_discount_threshold(game="csgo")

        assert isinstance(threshold, float)
        assert 0 < threshold < 50


class TestStatistics:
    """Tests for predictor statistics."""

    def test_get_statistics(self):
        """Test getting predictor statistics."""
        from src.ml.discount_threshold_predictor import DiscountThresholdPredictor

        # Use temp path to avoid interference with other tests
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_stats_model.pkl"
            predictor = DiscountThresholdPredictor(model_path=model_path)

            # Add some examples
            for i in range(10):
                predictor.add_trAlgoning_example(
                    item_name=f"Item {i}",
                    game="csgo" if i < 7 else "dota2",
                    current_price=10.0,
                    historical_avg_price=12.0,
                    actual_discount=15.0,
                    was_profitable=i < 6,
                    profit_percent=5.0 if i < 6 else -3.0,
                )

            stats = predictor.get_statistics()

            assert stats["total_examples"] == 10
            assert stats["profitable_examples"] == 6
            assert stats["profitability_rate"] == 0.6
            assert "csgo" in stats["games"]
            assert "dota2" in stats["games"]
            assert stats["is_trAlgoned"] is False


class TestCaching:
    """Tests for prediction caching."""

    def test_prediction_uses_cache(self):
        """Test that predictions are cached."""
        from src.ml.discount_threshold_predictor import DiscountThresholdPredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_cache_model.pkl"
            predictor = DiscountThresholdPredictor(model_path=model_path)

            # First prediction
            pred1 = predictor.predict(game="csgo")

            # Second prediction should use cache
            pred2 = predictor.predict(game="csgo")

            assert pred1.optimal_threshold == pred2.optimal_threshold
            assert len(predictor._prediction_cache) == 1

    def test_bypass_cache(self):
        """Test bypassing cache."""
        from src.ml.discount_threshold_predictor import DiscountThresholdPredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_bypass_cache_model.pkl"
            predictor = DiscountThresholdPredictor(model_path=model_path)

            # First prediction
            pred1 = predictor.predict(game="csgo", use_cache=False)

            # Second prediction without cache
            pred2 = predictor.predict(game="csgo", use_cache=False)

            # Both should return same values (since model is same)
            assert pred1.optimal_threshold == pred2.optimal_threshold
