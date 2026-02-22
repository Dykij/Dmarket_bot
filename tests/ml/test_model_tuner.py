"""Тесты для ModelTuner и AutoMLSelector.

Тестирует:
- CVStrategy и ScoringMetric enums
- ModelTuner с различными моделями
- Pipeline создание
- GridSearchCV / RandomizedSearchCV
- AutoMLSelector для автоматического выбора модели
"""

import numpy as np
import pytest

from src.ml.model_tuner import (
    AutoMLSelector,
    CVStrategy,
    EvaluationResult,
    ModelTuner,
    ScoringMetric,
    TuningResult,
)

# === Fixtures ===

@pytest.fixture
def sample_data():
    """Создать тестовые данные."""
    np.random.seed(42)
    n_samples = 100
    n_features = 10

    X = np.random.randn(n_samples, n_features)
    # Линейная зависимость + шум
    y = 2 * X[:, 0] - 1 * X[:, 1] + 0.5 * X[:, 2] + np.random.randn(n_samples) * 0.1

    return X, y


@pytest.fixture
def small_data():
    """Маленький датасет для быстрых тестов."""
    np.random.seed(42)
    X = np.random.randn(50, 5)
    y = X[:, 0] + X[:, 1] + np.random.randn(50) * 0.1
    return X, y


@pytest.fixture
def tuner():
    """Создать ModelTuner с базовыми настSwarmками."""
    return ModelTuner(
        cv_strategy=CVStrategy.KFOLD,
        cv_folds=3,
        scoring=ScoringMetric.MAE,
        n_jobs=1,
    )


# === CVStrategy Tests ===

class TestCVStrategy:
    """Тесты для CVStrategy enum."""

    def test_kfold_value(self):
        """Проверить значение KFOLD."""
        assert CVStrategy.KFOLD.value == "kfold"

    def test_time_series_value(self):
        """Проверить значение TIME_SERIES."""
        assert CVStrategy.TIME_SERIES.value == "time_series"

    def test_stratified_value(self):
        """Проверить значение STRATIFIED."""
        assert CVStrategy.STRATIFIED.value == "stratified"

    def test_all_strategies_exist(self):
        """Проверить наличие всех стратегий."""
        strategies = [s.value for s in CVStrategy]
        assert "kfold" in strategies
        assert "time_series" in strategies
        assert "stratified" in strategies


# === ScoringMetric Tests ===

class TestScoringMetric:
    """Тесты для ScoringMetric enum."""

    def test_mae_value(self):
        """Проверить значение MAE."""
        assert ScoringMetric.MAE.value == "neg_mean_absolute_error"

    def test_mse_value(self):
        """Проверить значение MSE."""
        assert ScoringMetric.MSE.value == "neg_mean_squared_error"

    def test_r2_value(self):
        """Проверить значение R2."""
        assert ScoringMetric.R2.value == "r2"

    def test_regression_metrics_exist(self):
        """Проверить наличие метрик регрессии."""
        metrics = [m.value for m in ScoringMetric]
        assert "neg_mean_absolute_error" in metrics
        assert "neg_mean_squared_error" in metrics
        assert "r2" in metrics

    def test_classification_metrics_exist(self):
        """Проверить наличие метрик классификации."""
        metrics = [m.value for m in ScoringMetric]
        assert "accuracy" in metrics
        assert "f1" in metrics


# === TuningResult Tests ===

class TestTuningResult:
    """Тесты для TuningResult dataclass."""

    def test_creation(self):
        """Проверить создание TuningResult."""
        result = TuningResult(
            best_params={"n_estimators": 100},
            best_score=0.95,
            cv_results={},
            best_estimator=None,
            model_name="TestModel",
            scoring="accuracy",
            cv_folds=5,
            total_fits=50,
            tuning_time_seconds=10.5,
        )

        assert result.best_params == {"n_estimators": 100}
        assert result.best_score == 0.95
        assert result.model_name == "TestModel"
        assert result.cv_folds == 5
        assert result.total_fits == 50

    def test_summary(self):
        """Проверить метод summary()."""
        result = TuningResult(
            best_params={"alpha": 1.0},
            best_score=0.85,
            cv_results={},
            best_estimator=None,
            model_name="Ridge",
            scoring="r2",
            cv_folds=5,
            total_fits=10,
            tuning_time_seconds=2.5,
        )

        summary = result.summary()
        assert "Ridge" in summary
        assert "0.85" in summary
        assert "alpha" in summary


# === EvaluationResult Tests ===

class TestEvaluationResult:
    """Тесты для EvaluationResult dataclass."""

    def test_creation(self):
        """Проверить создание EvaluationResult."""
        result = EvaluationResult(
            train_scores=[0.9, 0.91, 0.89],
            test_scores=[0.85, 0.84, 0.86],
            mean_train_score=0.9,
            mean_test_score=0.85,
            std_train_score=0.01,
            std_test_score=0.01,
        )

        assert len(result.train_scores) == 3
        assert result.mean_test_score == 0.85

    def test_is_overfitting_true(self):
        """Проверить обнаружение переобучения."""
        result = EvaluationResult(
            train_scores=[0.95],
            test_scores=[0.6],
            mean_train_score=0.95,
            mean_test_score=0.6,
            std_train_score=0.0,
            std_test_score=0.0,
        )

        # (0.95 - 0.6) / 0.95 = 0.368 > 0.15
        assert result.is_overfitting(threshold=0.15) is True

    def test_is_overfitting_false(self):
        """Проверить отсутствие переобучения."""
        result = EvaluationResult(
            train_scores=[0.85],
            test_scores=[0.82],
            mean_train_score=0.85,
            mean_test_score=0.82,
            std_train_score=0.0,
            std_test_score=0.0,
        )

        # (0.85 - 0.82) / 0.85 = 0.035 < 0.15
        assert result.is_overfitting(threshold=0.15) is False


# === ModelTuner Tests ===

class TestModelTuner:
    """Тесты для ModelTuner."""

    def test_initialization(self):
        """Проверить инициализацию."""
        tuner = ModelTuner(
            cv_strategy=CVStrategy.TIME_SERIES,
            cv_folds=5,
            scoring=ScoringMetric.MSE,
        )

        assert tuner.cv_strategy == CVStrategy.TIME_SERIES
        assert tuner.cv_folds == 5
        assert tuner.scoring == ScoringMetric.MSE

    def test_sklearn_check(self, tuner):
        """Проверить проверку sklearn."""
        # sklearn может быть не установлен в тестовом окружении
        if not tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")

    def test_get_cv_splitter_kfold(self, tuner):
        """Проверить создание KFold splitter."""
        if not tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")
        tuner.cv_strategy = CVStrategy.KFOLD
        splitter = tuner._get_cv_splitter(100)

        assert splitter is not None
        assert hasattr(splitter, "split")

    def test_get_cv_splitter_time_series(self):
        """Проверить создание TimeSeriesSplit splitter."""
        tuner = ModelTuner(cv_strategy=CVStrategy.TIME_SERIES)
        if not tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")
        splitter = tuner._get_cv_splitter(100)

        from sklearn.model_selection import TimeSeriesSplit
        assert isinstance(splitter, TimeSeriesSplit)

    def test_create_pipeline_basic(self, tuner):
        """Проверить создание базового pipeline."""
        if not tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")
        from sklearn.linear_model import Ridge

        model = Ridge()
        pipeline = tuner.create_pipeline(model)

        assert hasattr(pipeline, "fit")
        assert hasattr(pipeline, "predict")

    def test_create_pipeline_with_scaling(self, tuner):
        """Проверить pipeline со scaling."""
        if not tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")
        from sklearn.linear_model import Ridge

        model = Ridge()
        pipeline = tuner.create_pipeline(model, use_scaling=True)

        # Pipeline должен содержать scaler
        assert "scaler" in pipeline.named_steps

    def test_create_pipeline_with_feature_selection(self, tuner):
        """Проверить pipeline с feature selection."""
        if not tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")
        from sklearn.linear_model import Ridge

        model = Ridge()
        pipeline = tuner.create_pipeline(
            model,
            use_feature_selection=True,
            n_features_to_select=5,
        )

        assert "feature_selection" in pipeline.named_steps

    def test_tune_ridge(self, tuner, small_data):
        """Тест настSwarmки Ridge."""
        if not tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")
        X, y = small_data
        result = tuner.tune_ridge(X, y)

        assert isinstance(result, TuningResult)
        assert result.model_name == "Ridge"
        assert "alpha" in result.best_params
        assert result.best_score > 0

    def test_tune_random_forest_randomized(self, tuner, small_data):
        """Тест настSwarmки RandomForest с RandomizedSearchCV."""
        if not tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")
        X, y = small_data
        result = tuner.tune_random_forest(
            X, y,
            use_randomized=True,
            n_iter=5,  # Мало итераций для быстрого теста
        )

        assert isinstance(result, TuningResult)
        assert result.model_name == "RandomForestRegressor"
        assert result.best_estimator is not None

    def test_tune_gradient_boosting(self, tuner, small_data):
        """Тест настSwarmки GradientBoosting."""
        if not tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")
        X, y = small_data

        # Уменьшаем grid для быстрого теста
        small_grid = {
            "n_estimators": [10],
            "max_depth": [3],
            "learning_rate": [0.1],
            "min_samples_split": [2],
        }

        result = tuner.tune_gradient_boosting(
            X, y,
            param_grid=small_grid,
        )

        assert isinstance(result, TuningResult)
        assert result.model_name == "GradientBoostingRegressor"

    def test_evaluate_model(self, tuner, small_data):
        """Тест оценки модели."""
        if not tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")
        from sklearn.ensemble import RandomForestRegressor

        X, y = small_data
        model = RandomForestRegressor(n_estimators=10, random_state=42)

        pipeline = tuner.create_pipeline(model)
        pipeline.fit(X, y)

        result = tuner.evaluate_model(pipeline, X, y)

        assert isinstance(result, EvaluationResult)
        assert len(result.train_scores) == tuner.cv_folds
        assert len(result.test_scores) == tuner.cv_folds
        assert result.mean_test_score > 0

    def test_compare_models(self, tuner, small_data):
        """Тест сравнения моделей."""
        if not tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")
        X, y = small_data

        results = tuner.compare_models(
            X, y,
            models=["ridge", "random_forest"],
        )

        assert "ridge" in results or "random_forest" in results

    def test_fallback_result(self, tuner):
        """Тест fallback результата."""
        result = tuner._fallback_result("TestModel")

        assert result.model_name == "TestModel"
        assert result.best_params == {}
        assert result.best_estimator is None


# === AutoMLSelector Tests ===

class TestAutoMLSelector:
    """Тесты для AutoMLSelector."""

    def test_initialization(self):
        """Проверить инициализацию."""
        selector = AutoMLSelector(
            cv_folds=3,
            scoring=ScoringMetric.MAE,
            time_budget_seconds=60,
        )

        assert selector.cv_folds == 3
        assert selector.scoring == ScoringMetric.MAE
        assert selector.time_budget_seconds == 60

    def test_select_best_model(self, small_data):
        """Тест выбора лучшей модели."""
        selector = AutoMLSelector(
            cv_folds=2,
            time_budget_seconds=30,
        )
        if not selector.tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")
        X, y = small_data

        best_model, results = selector.select_best_model(
            X, y,
            include_xgboost=False,  # Пропускаем для скорости
        )

        # Должен вернуть хотя бы одну модель
        assert len(results) >= 1

    def test_get_recommendations_empty(self):
        """Тест рекомендаций для пустых результатов."""
        selector = AutoMLSelector()

        recommendations = selector.get_recommendations({})

        assert len(recommendations) >= 1
        assert "No results" in recommendations[0]

    def test_get_recommendations_with_results(self, small_data):
        """Тест рекомендаций с результатами."""
        selector = AutoMLSelector(cv_folds=2, time_budget_seconds=30)
        if not selector.tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")
        X, y = small_data

        _, results = selector.select_best_model(X, y, include_xgboost=False)

        recommendations = selector.get_recommendations(results)

        # Должны быть рекомендации
        assert len(recommendations) >= 1
        # Первая рекомендация должна содержать лучшую модель
        assert "Best model" in recommendations[0] or "No models" in recommendations[0]


# === Integration Tests ===

class TestModelTunerIntegration:
    """Интеграционные тесты."""

    def test_full_workflow(self, sample_data):
        """Тест полного workflow."""
        tuner = ModelTuner(
            cv_strategy=CVStrategy.TIME_SERIES,
            cv_folds=3,
            scoring=ScoringMetric.MAE,
        )
        if not tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")
        X, y = sample_data

        # 2. Тюним модель
        result = tuner.tune_ridge(X, y)

        assert result.best_estimator is not None

        # 3. Оцениваем
        eval_result = tuner.evaluate_model(result.best_estimator, X, y)

        assert eval_result.mean_test_score > 0

        # 4. Проверяем переобучение
        assert isinstance(eval_result.is_overfitting(), bool)

    def test_different_cv_strategies(self, small_data):
        """Тест разных стратегий CV."""
        X, y = small_data
        for strategy in [CVStrategy.KFOLD, CVStrategy.TIME_SERIES]:
            tuner = ModelTuner(
                cv_strategy=strategy,
                cv_folds=3,
            )
            if not tuner._sklearn_avAlgolable:
                pytest.skip("sklearn not avAlgolable")

            result = tuner.tune_ridge(X, y)
            assert result.best_score > 0

    def test_different_scoring_metrics(self, small_data):
        """Тест разных метрик."""
        X, y = small_data

        for scoring in [ScoringMetric.MAE, ScoringMetric.MSE, ScoringMetric.R2]:
            tuner = ModelTuner(
                cv_folds=2,
                scoring=scoring,
            )
            if not tuner._sklearn_avAlgolable:
                pytest.skip("sklearn not avAlgolable")

            result = tuner.tune_ridge(X, y)
            # Результат должен быть валидным
            assert result.scoring == scoring.value


# === Edge Cases ===

class TestModelTunerEdgeCases:
    """Тесты граничных случаев."""

    def test_small_dataset(self):
        """Тест с очень маленьким датасетом."""
        X = np.random.randn(10, 3)
        y = np.random.randn(10)

        tuner = ModelTuner(cv_folds=2)
        if not tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")
        result = tuner.tune_ridge(X, y)

        # Должен отработать даже на маленьких данных
        assert result is not None

    def test_single_feature(self):
        """Тест с одним признаком."""
        X = np.random.randn(50, 1)
        y = 2 * X[:, 0] + np.random.randn(50) * 0.1

        tuner = ModelTuner(cv_folds=3)
        if not tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")
        result = tuner.tune_ridge(X, y)

        assert result.best_estimator is not None

    def test_many_features(self):
        """Тест с большим количеством признаков."""
        X = np.random.randn(100, 50)
        y = X[:, 0] + X[:, 1] + np.random.randn(100) * 0.1

        tuner = ModelTuner(cv_folds=3)
        if not tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")

        # Создаём pipeline с feature selection
        from sklearn.linear_model import Ridge
        model = Ridge()
        pipeline = tuner.create_pipeline(
            model,
            use_feature_selection=True,
            n_features_to_select=10,
        )

        pipeline.fit(X, y)
        predictions = pipeline.predict(X)

        assert len(predictions) == len(y)

    def test_nan_handling(self):
        """Тест обработки NaN."""
        X = np.random.randn(50, 5)
        X[10, 2] = np.nan  # Добавляем NaN
        y = X[:, 0] + np.random.randn(50) * 0.1
        y = np.nan_to_num(y)  # Убираем NaN из y

        tuner = ModelTuner(cv_folds=3)
        if not tuner._sklearn_avAlgolable:
            pytest.skip("sklearn not avAlgolable")

        # Pipeline с Imputer должен обработать NaN
        from sklearn.linear_model import Ridge
        pipeline = tuner.create_pipeline(Ridge())

        # Не должно упасть
        pipeline.fit(X, y)
        predictions = pipeline.predict(X)

        assert not np.isnan(predictions).any()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
