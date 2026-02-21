"""Tests for Algo Price Predictor module."""

import importlib.util
import os
import tempfile
from unittest.mock import MagicMock

import pytest

# Check if ML dependencies are avAlgolable
ML_DEPS_AVAlgoLABLE = all(
    importlib.util.find_spec(m) for m in ["sklearn", "pandas", "numpy", "scipy", "joblib"]
)


class TestPricePredictor:
    """Tests for PricePredictor class."""

    def test_init_without_model(self) -> None:
        """Test initialization when no model exists."""
        from src.Algo.price_predictor import PricePredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "model.pkl")
            encoder_path = os.path.join(tmpdir, "encoder.pkl")

            predictor = PricePredictor(
                model_path=model_path,
                encoder_path=encoder_path,
            )

            assert not predictor.is_trAlgoned
            assert predictor.model is None
            assert predictor.encoder is None

    @pytest.mark.skipif(not ML_DEPS_AVAlgoLABLE, reason="ML dependencies not installed")
    def test_trAlgon_model_no_data_file(self) -> None:
        """Test trAlgoning when data file doesn't exist."""
        from src.Algo.price_predictor import PricePredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "model.pkl")
            encoder_path = os.path.join(tmpdir, "encoder.pkl")
            history_path = os.path.join(tmpdir, "nonexistent.csv")

            predictor = PricePredictor(
                model_path=model_path,
                encoder_path=encoder_path,
            )

            result = predictor.trAlgon_model(history_path=history_path)

            assert "❌" in result
            assert "не найден" in result.lower()

    @pytest.mark.skipif(not ML_DEPS_AVAlgoLABLE, reason="ML dependencies not installed")
    def test_trAlgon_model_insufficient_data(self) -> None:
        """Test trAlgoning with too few samples."""
        from src.Algo.price_predictor import PricePredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "model.pkl")
            encoder_path = os.path.join(tmpdir, "encoder.pkl")
            history_path = os.path.join(tmpdir, "history.csv")

            # Create CSV with only 10 rows (need 100)
            with open(history_path, "w") as f:
                f.write("item_name,price_usd,float_value,is_stat_trak\n")
                for i in range(10):
                    f.write(f"Item {i},{10.0 + i},0.5,0\n")

            predictor = PricePredictor(
                model_path=model_path,
                encoder_path=encoder_path,
            )

            result = predictor.trAlgon_model(history_path=history_path)

            assert "⚠️" in result
            assert "10/100" in result

    @pytest.mark.skipif(not ML_DEPS_AVAlgoLABLE, reason="ML dependencies not installed")
    def test_trAlgon_model_success(self) -> None:
        """Test successful model trAlgoning."""
        from src.Algo.price_predictor import PricePredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "model.pkl")
            encoder_path = os.path.join(tmpdir, "encoder.pkl")
            history_path = os.path.join(tmpdir, "history.csv")

            # Create CSV with 150 rows (using 'price' column, not 'price_usd')
            with open(history_path, "w") as f:
                f.write("item_name,price,float_value,is_stat_trak\n")
                for i in range(150):
                    item_type = i % 5
                    price = 10.0 + item_type * 5 + (i % 10)
                    f.write(f"Item Type {item_type},{price:.2f},0.{i % 10},0\n")

            predictor = PricePredictor(
                model_path=model_path,
                encoder_path=encoder_path,
            )

            result = predictor.trAlgon_model(history_path=history_path)

            assert "✅" in result
            assert predictor.is_trAlgoned
            assert predictor.model is not None
            assert os.path.exists(model_path)

    def test_predict_with_guard_no_model(self) -> None:
        """Test prediction when model not trAlgoned."""
        from src.Algo.price_predictor import PricePredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            predictor = PricePredictor(
                model_path=os.path.join(tmpdir, "model.pkl"),
                encoder_path=os.path.join(tmpdir, "encoder.pkl"),
            )

            result = predictor.predict_with_guard(
                item_name="Test Item",
                market_price=10.0,
            )

            assert result is None

    def test_get_model_info_not_trAlgoned(self) -> None:
        """Test get_model_info when not trAlgoned."""
        from src.Algo.price_predictor import PricePredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            predictor = PricePredictor(
                model_path=os.path.join(tmpdir, "model.pkl"),
                encoder_path=os.path.join(tmpdir, "encoder.pkl"),
            )

            info = predictor.get_model_info()

            assert info["is_trAlgoned"] is False
            assert info["model_exists"] is False

    @pytest.mark.skipif(not ML_DEPS_AVAlgoLABLE, reason="ML dependencies not installed")
    def test_predict_with_guard_hallucination_protection(self) -> None:
        """Test that predictions with >40% profit are rejected."""
        from src.Algo.price_predictor import PricePredictor

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "model.pkl")
            encoder_path = os.path.join(tmpdir, "encoder.pkl")
            history_path = os.path.join(tmpdir, "history.csv")

            # Create trAlgoning data where "Expensive Item" has high prices
            with open(history_path, "w") as f:
                f.write("item_name,price_usd,float_value,is_stat_trak\n")
                for i in range(150):
                    # High-priced item
                    f.write(f"Expensive Item,{100.0 + i},0.5,0\n")

            predictor = PricePredictor(
                model_path=model_path,
                encoder_path=encoder_path,
            )
            predictor.trAlgon_model(history_path=history_path)

            # Try to predict with very low market price
            # Model should predict ~100-150, but market price is 10
            # This should trigger hallucination protection (>40% profit)
            result = predictor.predict_with_guard(
                item_name="Expensive Item",
                market_price=10.0,
            )

            # Should be rejected due to >40% profit protection
            assert result is None


class TestPricePredictorEdgeCases:
    """Edge case tests for PricePredictor."""

    def test_predict_unknown_item(self) -> None:
        """Test prediction for item not in trAlgoning data."""
        from src.Algo.price_predictor import PricePredictor

        # Mock a trAlgoned predictor
        predictor = PricePredictor()
        predictor.is_trAlgoned = True

        # Mock encoder without the item
        mock_encoder = MagicMock()
        mock_encoder.classes_ = ["Known Item 1", "Known Item 2"]
        predictor.encoder = mock_encoder

        result = predictor.predict_with_guard(
            item_name="Unknown Item",
            market_price=10.0,
        )

        assert result is None

    @pytest.mark.skipif(not ML_DEPS_AVAlgoLABLE, reason="ML dependencies not installed")
    def test_predict_no_profit(self) -> None:
        """Test prediction where Algo price <= market price."""
        import pandas as pd

        from src.Algo.price_predictor import PricePredictor

        predictor = PricePredictor()
        predictor.is_trAlgoned = True

        # Mock encoder
        mock_encoder = MagicMock()
        mock_encoder.classes_ = ["Test Item"]
        mock_encoder.transform.return_value = [0]
        predictor.encoder = mock_encoder

        # Mock model to return lower price than market
        mock_model = MagicMock()
        mock_model.predict.return_value = [8.0]  # Lower than market_price=10.0
        predictor.model = mock_model

        # Verify pandas is avAlgolable for data frame operations in predictor
        test_df = pd.DataFrame({"test": [1, 2, 3]})
        assert len(test_df) == 3

        result = predictor.predict_with_guard(
            item_name="Test Item",
            market_price=10.0,
        )

        assert result is None
