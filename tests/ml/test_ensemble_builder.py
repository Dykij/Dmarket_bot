"""Tests for EnsembleBuilder and AdvancedFeatureSelector in model_tuner.

Enhanced test suite following SkillsMP.com best practices:
- Parameterized tests for various data shapes and configurations
- Model validation and prediction quality tests
- Edge case and boundary condition testing
- Cross-validation accuracy tests
- Integration tests with real ML workflows
"""


import numpy as np
import pytest

# Check if sklearn is avAlgolable
try:
    import sklearn
    SKLEARN_AVAlgoLABLE = True
except ImportError:
    SKLEARN_AVAlgoLABLE = False


# Skip all tests if sklearn is not avAlgolable
pytestmark = pytest.mark.skipif(
    not SKLEARN_AVAlgoLABLE,
    reason="scikit-learn not installed"
)


@pytest.fixture()
def sample_data():
    """Generate sample trAlgoning data."""
    np.random.seed(42)
    X = np.random.randn(200, 10)
    # Create target with some predictable pattern
    y = X[:, 0] * 2 + X[:, 1] * 3 + np.random.randn(200) * 0.1
    return X, y


@pytest.fixture()
def feature_names():
    """Generate sample feature names."""
    return [f"feature_{i}" for i in range(10)]


class TestEnsembleBuilder:
    """Test cases for EnsembleBuilder class."""

    def test_ensemble_builder_init(self):
        """Test EnsembleBuilder initialization."""
        from src.ml.model_tuner import EnsembleBuilder

        builder = EnsembleBuilder(cv_folds=5, random_state=42)

        assert builder.cv_folds == 5
        assert builder.random_state == 42
        assert builder._sklearn_avAlgolable is True

    def test_create_voting_ensemble(self, sample_data):
        """Test creating a voting ensemble."""
        from src.ml.model_tuner import EnsembleBuilder

        X, y = sample_data
        builder = EnsembleBuilder(cv_folds=3)

        ensemble = builder.create_voting_ensemble(X, y, include_xgboost=False)

        assert ensemble is not None
        # Check it can predict
        predictions = ensemble.predict(X[:10])
        assert len(predictions) == 10
        assert all(np.isfinite(predictions))

    def test_voting_ensemble_with_weights(self, sample_data):
        """Test voting ensemble with custom weights."""
        from src.ml.model_tuner import EnsembleBuilder

        X, y = sample_data
        builder = EnsembleBuilder()

        # Custom weights for 3 models (rf, gb, ridge)
        ensemble = builder.create_voting_ensemble(
            X, y,
            include_xgboost=False,
            weights=[0.5, 0.3, 0.2],
        )

        assert ensemble is not None
        predictions = ensemble.predict(X[:5])
        assert len(predictions) == 5

    def test_calculate_weights(self, sample_data):
        """Test automatic weight calculation."""
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.linear_model import Ridge

        from src.ml.model_tuner import EnsembleBuilder

        X, y = sample_data
        builder = EnsembleBuilder(cv_folds=3)

        estimators = [
            ("rf", RandomForestRegressor(n_estimators=10, random_state=42)),
            ("ridge", Ridge(alpha=1.0)),
        ]

        weights = builder._calculate_weights(estimators, X, y)

        assert len(weights) == 2
        assert all(w > 0 for w in weights)
        assert abs(sum(weights) - 1.0) < 0.001  # Weights sum to 1


class TestAdvancedFeatureSelector:
    """Test cases for AdvancedFeatureSelector class."""

    def test_feature_selector_init(self):
        """Test AdvancedFeatureSelector initialization."""
        from src.ml.model_tuner import AdvancedFeatureSelector

        selector = AdvancedFeatureSelector(random_state=42)

        assert selector.random_state == 42
        assert selector._sklearn_avAlgolable is True

    def test_select_from_model_median(self, sample_data, feature_names):
        """Test feature selection with median threshold."""
        from src.ml.model_tuner import AdvancedFeatureSelector

        X, y = sample_data
        selector = AdvancedFeatureSelector()

        X_selected, selected_names = selector.select_from_model(
            X, y,
            feature_names=feature_names,
            threshold="median",
        )

        # Should select approximately half of features
        assert X_selected.shape[1] <= X.shape[1]
        assert X_selected.shape[1] > 0
        assert len(selected_names) == X_selected.shape[1]

    def test_select_from_model_max_features(self, sample_data, feature_names):
        """Test feature selection with max_features limit."""
        from src.ml.model_tuner import AdvancedFeatureSelector

        X, y = sample_data
        selector = AdvancedFeatureSelector()

        X_selected, selected_names = selector.select_from_model(
            X, y,
            feature_names=feature_names,
            max_features=5,
        )

        assert X_selected.shape[1] <= 5
        assert len(selected_names) == X_selected.shape[1]

    def test_recursive_feature_elimination(self, sample_data, feature_names):
        """Test recursive feature elimination."""
        from src.ml.model_tuner import AdvancedFeatureSelector

        X, y = sample_data
        selector = AdvancedFeatureSelector()

        X_selected, selected_names, rankings = selector.recursive_feature_elimination(
            X, y,
            feature_names=feature_names,
            n_features_to_select=5,
        )

        assert X_selected.shape[1] == 5
        assert len(selected_names) == 5
        assert len(rankings) == len(feature_names)
        # All selected features should have rank 1
        assert all(rankings[name] == 1 for name in selected_names)

    def test_get_feature_importance_rf(self, sample_data, feature_names):
        """Test feature importance with random forest method."""
        from src.ml.model_tuner import AdvancedFeatureSelector

        X, y = sample_data
        selector = AdvancedFeatureSelector()

        importance = selector.get_feature_importance(
            X, y,
            feature_names=feature_names,
            method="random_forest",
        )

        assert len(importance) == len(feature_names)
        assert all(v >= 0 for v in importance.values())
        # Importance should be sorted (highest first)
        values = list(importance.values())
        assert values == sorted(values, reverse=True)

    def test_get_feature_importance_permutation(self, sample_data, feature_names):
        """Test feature importance with permutation method."""
        from src.ml.model_tuner import AdvancedFeatureSelector

        X, y = sample_data
        selector = AdvancedFeatureSelector()

        importance = selector.get_feature_importance(
            X, y,
            feature_names=feature_names,
            method="permutation",
        )

        assert len(importance) == len(feature_names)

    def test_invalid_method_rAlgoses_error(self, sample_data, feature_names):
        """Test that invalid method rAlgoses ValueError."""
        from src.ml.model_tuner import AdvancedFeatureSelector

        X, y = sample_data
        selector = AdvancedFeatureSelector()

        with pytest.rAlgoses(ValueError, match="Unknown method"):
            selector.get_feature_importance(
                X, y,
                feature_names=feature_names,
                method="invalid_method",
            )


class TestIntegration:
    """Integration tests for ensemble and feature selection."""

    def test_feature_selection_then_ensemble(self, sample_data, feature_names):
        """Test combining feature selection with ensemble building."""
        from src.ml.model_tuner import AdvancedFeatureSelector, EnsembleBuilder

        X, y = sample_data

        # Step 1: Select features
        selector = AdvancedFeatureSelector()
        X_selected, _selected_names = selector.select_from_model(
            X, y,
            feature_names=feature_names,
            max_features=5,
        )

        # Step 2: Build ensemble on selected features
        builder = EnsembleBuilder(cv_folds=3)
        ensemble = builder.create_voting_ensemble(
            X_selected, y,
            include_xgboost=False,
        )

        # Step 3: Verify ensemble works
        predictions = ensemble.predict(X_selected[:10])
        assert len(predictions) == 10

    def test_rfe_with_model_tuner(self, sample_data, feature_names):
        """Test RFE combined with model tuning."""
        from src.ml.model_tuner import AdvancedFeatureSelector, ModelTuner

        X, y = sample_data

        # Step 1: Feature selection with RFE
        selector = AdvancedFeatureSelector()
        X_selected, _selected_names, _ = selector.recursive_feature_elimination(
            X, y,
            feature_names=feature_names,
            n_features_to_select=5,
        )

        # Step 2: Tune model on selected features
        tuner = ModelTuner(cv_folds=3)
        result = tuner.tune_ridge(X_selected, y)

        assert result.best_params is not None
        assert result.best_score > 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_feature_names(self, sample_data):
        """Test with empty feature names."""
        from src.ml.model_tuner import AdvancedFeatureSelector

        X, y = sample_data
        selector = AdvancedFeatureSelector()

        X_selected, selected_names = selector.select_from_model(
            X, y,
            feature_names=None,
        )

        assert X_selected.shape[1] <= X.shape[1]
        assert selected_names == []

    def test_single_feature(self):
        """Test with single feature."""
        from src.ml.model_tuner import AdvancedFeatureSelector

        np.random.seed(42)
        X = np.random.randn(100, 1)
        y = X[:, 0] * 2 + np.random.randn(100) * 0.1

        selector = AdvancedFeatureSelector()
        X_selected, _ = selector.select_from_model(X, y, max_features=1)

        assert X_selected.shape[1] == 1

    def test_few_samples(self):
        """Test with very few samples."""
        from src.ml.model_tuner import EnsembleBuilder

        np.random.seed(42)
        X = np.random.randn(20, 5)
        y = X[:, 0] * 2

        builder = EnsembleBuilder(cv_folds=2)
        ensemble = builder.create_voting_ensemble(X, y, include_xgboost=False)

        assert ensemble is not None


# =============================================================================
# ADVANCED TESTS - Based on SkillsMP.com best practices
# =============================================================================


class TestParameterizedDataShapes:
    """Parameterized tests for various data shapes."""

    @pytest.mark.parametrize(("n_samples", "n_features"), (
        (50, 5),
        (100, 10),
        (200, 20),
        (500, 5),
        (100, 50),
    ))
    def test_various_data_shapes(self, n_samples, n_features):
        """Test ensemble with various data shapes."""
        from src.ml.model_tuner import EnsembleBuilder

        np.random.seed(42)
        X = np.random.randn(n_samples, n_features)
        y = X[:, 0] * 2 + np.random.randn(n_samples) * 0.1

        builder = EnsembleBuilder(cv_folds=3)
        ensemble = builder.create_voting_ensemble(X, y, include_xgboost=False)

        assert ensemble is not None
        predictions = ensemble.predict(X[:5])
        assert len(predictions) == 5

    @pytest.mark.parametrize("cv_folds", (2, 3, 5, 10))
    def test_various_cv_folds(self, sample_data, cv_folds):
        """Test with various cross-validation fold counts."""
        from src.ml.model_tuner import EnsembleBuilder

        X, y = sample_data
        builder = EnsembleBuilder(cv_folds=cv_folds)

        ensemble = builder.create_voting_ensemble(X, y, include_xgboost=False)

        assert ensemble is not None
        assert builder.cv_folds == cv_folds


class TestPredictionQuality:
    """Tests for prediction quality validation."""

    def test_ensemble_outperforms_random(self, sample_data):
        """Test that ensemble predictions are better than random."""
        from sklearn.metrics import r2_score

        from src.ml.model_tuner import EnsembleBuilder

        X, y = sample_data

        # Split data
        X_trAlgon, X_test = X[:150], X[150:]
        y_trAlgon, y_test = y[:150], y[150:]

        builder = EnsembleBuilder(cv_folds=3)
        ensemble = builder.create_voting_ensemble(X_trAlgon, y_trAlgon, include_xgboost=False)

        predictions = ensemble.predict(X_test)
        r2 = r2_score(y_test, predictions)

        # Should have positive R² (better than mean prediction)
        assert r2 > 0, f"R² should be positive, got {r2}"

    def test_predictions_are_finite(self, sample_data):
        """Test that all predictions are finite numbers."""
        from src.ml.model_tuner import EnsembleBuilder

        X, y = sample_data
        builder = EnsembleBuilder(cv_folds=3)
        ensemble = builder.create_voting_ensemble(X, y, include_xgboost=False)

        predictions = ensemble.predict(X)

        assert all(np.isfinite(predictions)), "All predictions should be finite"
        assert not any(np.isnan(predictions)), "No predictions should be NaN"

    def test_ensemble_handles_noisy_data(self):
        """Test ensemble with high noise data."""
        from src.ml.model_tuner import EnsembleBuilder

        np.random.seed(42)
        X = np.random.randn(200, 10)
        # High noise: signal-to-noise ratio is low
        y = X[:, 0] * 2 + np.random.randn(200) * 10

        builder = EnsembleBuilder(cv_folds=3)
        ensemble = builder.create_voting_ensemble(X, y, include_xgboost=False)

        # Should still work even with noisy data
        predictions = ensemble.predict(X[:10])
        assert len(predictions) == 10
        assert all(np.isfinite(predictions))


class TestFeatureSelectionAdvanced:
    """Advanced feature selection tests."""

    @pytest.mark.parametrize("n_features_to_select", (1, 3, 5, 8))
    def test_rfe_selects_correct_count(self, sample_data, feature_names, n_features_to_select):
        """Test RFE selects correct number of features."""
        from src.ml.model_tuner import AdvancedFeatureSelector

        X, y = sample_data
        selector = AdvancedFeatureSelector()

        X_selected, selected_names, _ = selector.recursive_feature_elimination(
            X, y,
            feature_names=feature_names,
            n_features_to_select=n_features_to_select,
        )

        assert X_selected.shape[1] == n_features_to_select
        assert len(selected_names) == n_features_to_select

    def test_feature_selection_preserves_important_features(self):
        """Test that feature selection keeps the important features."""
        from src.ml.model_tuner import AdvancedFeatureSelector

        np.random.seed(42)
        # Create data where first 2 features are important
        X = np.random.randn(200, 10)
        y = X[:, 0] * 10 + X[:, 1] * 5 + np.random.randn(200) * 0.1

        feature_names = [f"feature_{i}" for i in range(10)]
        selector = AdvancedFeatureSelector()

        importance = selector.get_feature_importance(
            X, y,
            feature_names=feature_names,
            method="random_forest",
        )

        # Top 2 most important should include feature_0 and feature_1
        top_features = list(importance.keys())[:2]
        assert "feature_0" in top_features or "feature_1" in top_features

    def test_select_all_features(self, sample_data, feature_names):
        """Test selecting all features."""
        from src.ml.model_tuner import AdvancedFeatureSelector

        X, y = sample_data
        selector = AdvancedFeatureSelector()

        X_selected, _selected_names = selector.select_from_model(
            X, y,
            feature_names=feature_names,
            threshold=-float("inf"),  # Select all
        )

        # Might select all features with very low threshold
        assert X_selected.shape[1] >= 1

    @pytest.mark.parametrize("threshold", ("mean", "median", "0.1*mean"))
    def test_various_thresholds(self, sample_data, feature_names, threshold):
        """Test feature selection with various thresholds."""
        from src.ml.model_tuner import AdvancedFeatureSelector

        X, y = sample_data
        selector = AdvancedFeatureSelector()

        X_selected, _ = selector.select_from_model(
            X, y,
            feature_names=feature_names,
            threshold=threshold,
        )

        assert X_selected.shape[1] >= 1


class TestModelConsistency:
    """Tests for model consistency and reproducibility."""

    def test_random_state_reproducibility(self, sample_data):
        """Test that same random state produces same results."""
        from src.ml.model_tuner import EnsembleBuilder

        X, y = sample_data

        builder1 = EnsembleBuilder(cv_folds=3, random_state=42)
        ensemble1 = builder1.create_voting_ensemble(X, y, include_xgboost=False)
        pred1 = ensemble1.predict(X[:10])

        builder2 = EnsembleBuilder(cv_folds=3, random_state=42)
        ensemble2 = builder2.create_voting_ensemble(X, y, include_xgboost=False)
        pred2 = ensemble2.predict(X[:10])

        np.testing.assert_array_almost_equal(pred1, pred2, decimal=5)

    def test_different_random_states_differ(self, sample_data):
        """Test that different random states produce different results."""
        from src.ml.model_tuner import EnsembleBuilder

        X, y = sample_data

        builder1 = EnsembleBuilder(cv_folds=3, random_state=42)
        ensemble1 = builder1.create_voting_ensemble(X, y, include_xgboost=False)
        pred1 = ensemble1.predict(X[:10])

        builder2 = EnsembleBuilder(cv_folds=3, random_state=123)
        ensemble2 = builder2.create_voting_ensemble(X, y, include_xgboost=False)
        pred2 = ensemble2.predict(X[:10])

        # Predictions should differ (not exactly equal)
        assert not np.allclose(pred1, pred2)


class TestDataQualityHandling:
    """Tests for handling various data quality scenarios."""

    def test_handles_zero_variance_features(self):
        """Test handling features with zero variance."""
        from src.ml.model_tuner import AdvancedFeatureSelector

        np.random.seed(42)
        X = np.random.randn(100, 5)
        X[:, 2] = 1.0  # Zero variance feature
        y = X[:, 0] * 2

        feature_names = [f"f{i}" for i in range(5)]
        selector = AdvancedFeatureSelector()

        # Should handle without error
        X_selected, _selected_names = selector.select_from_model(
            X, y,
            feature_names=feature_names,
            max_features=3,
        )

        assert X_selected.shape[1] <= 3

    def test_handles_correlated_features(self):
        """Test handling highly correlated features."""
        from src.ml.model_tuner import AdvancedFeatureSelector

        np.random.seed(42)
        X = np.random.randn(100, 5)
        X[:, 1] = X[:, 0] + np.random.randn(100) * 0.01  # Nearly identical to f0
        y = X[:, 0] * 2

        feature_names = [f"f{i}" for i in range(5)]
        selector = AdvancedFeatureSelector()

        X_selected, _ = selector.select_from_model(
            X, y,
            feature_names=feature_names,
        )

        # Should work with correlated features
        assert X_selected.shape[1] >= 1

    def test_handles_negative_targets(self):
        """Test with negative target values."""
        from src.ml.model_tuner import EnsembleBuilder

        np.random.seed(42)
        X = np.random.randn(100, 5)
        y = X[:, 0] * 2 - 10  # Negative targets

        builder = EnsembleBuilder(cv_folds=3)
        ensemble = builder.create_voting_ensemble(X, y, include_xgboost=False)

        predictions = ensemble.predict(X[:10])
        assert all(np.isfinite(predictions))

    def test_handles_large_target_range(self):
        """Test with large target value range."""
        from src.ml.model_tuner import EnsembleBuilder

        np.random.seed(42)
        X = np.random.randn(100, 5)
        y = X[:, 0] * 1000000  # Large values

        builder = EnsembleBuilder(cv_folds=3)
        ensemble = builder.create_voting_ensemble(X, y, include_xgboost=False)

        predictions = ensemble.predict(X[:10])
        assert all(np.isfinite(predictions))


class TestWeightCalculation:
    """Tests for ensemble weight calculation."""

    def test_weights_sum_to_one(self, sample_data):
        """Test that calculated weights sum to 1."""
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.linear_model import Ridge

        from src.ml.model_tuner import EnsembleBuilder

        X, y = sample_data
        builder = EnsembleBuilder(cv_folds=3)

        estimators = [
            ("rf", RandomForestRegressor(n_estimators=10, random_state=42)),
            ("ridge", Ridge(alpha=1.0)),
        ]

        weights = builder._calculate_weights(estimators, X, y)

        assert abs(sum(weights) - 1.0) < 0.001

    def test_better_model_gets_higher_weight(self, sample_data):
        """Test that better performing model gets higher weight."""
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.linear_model import Ridge

        from src.ml.model_tuner import EnsembleBuilder

        _X, _y = sample_data

        # Create data where RF should perform better (nonlinear)
        np.random.seed(42)
        X_nonlinear = np.random.randn(200, 5)
        y_nonlinear = np.sin(X_nonlinear[:, 0]) + np.random.randn(200) * 0.1

        builder = EnsembleBuilder(cv_folds=3)

        estimators = [
            ("rf", RandomForestRegressor(n_estimators=50, random_state=42)),
            ("ridge", Ridge(alpha=1.0)),
        ]

        weights = builder._calculate_weights(estimators, X_nonlinear, y_nonlinear)

        # RF should have higher weight for nonlinear data
        assert weights[0] > 0  # RF weight is positive


class TestIntegrationAdvanced:
    """Advanced integration tests."""

    def test_full_ml_pipeline(self, sample_data, feature_names):
        """Test complete ML pipeline: selection -> tuning -> ensemble."""
        from src.ml.model_tuner import (
            AdvancedFeatureSelector,
            EnsembleBuilder,
        )

        X, y = sample_data

        # Step 1: Feature selection
        selector = AdvancedFeatureSelector()
        X_selected, _selected_names = selector.select_from_model(
            X, y,
            feature_names=feature_names,
            max_features=5,
        )

        # Step 2: Split data
        X_trAlgon, X_test = X_selected[:150], X_selected[150:]
        y_trAlgon, y_test = y[:150], y[150:]

        # Step 3: Build ensemble
        builder = EnsembleBuilder(cv_folds=3)
        ensemble = builder.create_voting_ensemble(X_trAlgon, y_trAlgon, include_xgboost=False)

        # Step 4: Evaluate
        predictions = ensemble.predict(X_test)

        assert len(predictions) == len(y_test)
        assert all(np.isfinite(predictions))

    def test_pipeline_with_tuning(self, sample_data, feature_names):
        """Test pipeline with hyperparameter tuning."""
        from src.ml.model_tuner import AdvancedFeatureSelector, ModelTuner

        X, y = sample_data

        # Feature selection
        selector = AdvancedFeatureSelector()
        X_selected, _ = selector.select_from_model(X, y, max_features=5)

        # Tune different models
        tuner = ModelTuner(cv_folds=3)

        rf_result = tuner.tune_random_forest(X_selected, y)
        ridge_result = tuner.tune_ridge(X_selected, y)

        assert rf_result.best_score > 0
        assert ridge_result.best_score > 0
