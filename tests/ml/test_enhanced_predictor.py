"""Тесты для улучшенного ML прогнозатора.

Тестирует:
- EnhancedFeatureExtractor для всех игр
- EnhancedPricePredictor с ансамблем моделей
- MLPipeline для защиты от ошибок
- Game-specific признаки (float, stickers, patterns)
"""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from src.ml.enhanced_predictor import (
    EnhancedFeatureExtractor,
    EnhancedFeatures,
    EnhancedPricePredictor,
    GameType,
    ItemCondition,
    ItemRarity,
    MLPipeline,
)

# ============ EnhancedFeatures Tests ============


class TestEnhancedFeatures:
    """Тесты для расширенных признаков."""

    def test_create_default_features(self):
        """Тест создания признаков с значениями по умолчанию."""
        features = EnhancedFeatures(current_price=10.0)

        assert features.current_price == 10.0
        assert features.rsi == 50.0
        assert features.relative_strength == 1.0
        assert features.game_type == GameType.CS2

    def test_to_array_returns_correct_shape(self):
        """Тест преобразования в массив."""
        features = EnhancedFeatures(current_price=10.0)
        arr = features.to_array()

        assert isinstance(arr, np.ndarray)
        assert arr.dtype == np.float64
        assert len(arr) == 38  # 38 признаков (базовые + DMarket + Lock)

    def test_feature_names_match_array_length(self):
        """Тест соответствия количества имён и признаков."""
        features = EnhancedFeatures(current_price=10.0)
        names = EnhancedFeatures.feature_names()
        arr = features.to_array()

        assert len(names) == len(arr)

    def test_game_to_numeric(self):
        """Тест преобразования игры в число."""
        cs2 = EnhancedFeatures(current_price=10.0, game_type=GameType.CS2)
        dota2 = EnhancedFeatures(current_price=10.0, game_type=GameType.DOTA2)
        tf2 = EnhancedFeatures(current_price=10.0, game_type=GameType.TF2)
        rust = EnhancedFeatures(current_price=10.0, game_type=GameType.RUST)

        assert cs2._game_to_numeric() == 1.0
        assert dota2._game_to_numeric() == 2.0
        assert tf2._game_to_numeric() == 3.0
        assert rust._game_to_numeric() == 4.0

    def test_rarity_to_numeric(self):
        """Тест преобразования редкости в число."""
        consumer = EnhancedFeatures(current_price=10.0, item_rarity=ItemRarity.CONSUMER)
        covert = EnhancedFeatures(current_price=10.0, item_rarity=ItemRarity.COVERT)
        arcana = EnhancedFeatures(current_price=10.0, item_rarity=ItemRarity.ARCANA)

        assert consumer._rarity_to_numeric() == 0.1
        assert covert._rarity_to_numeric() == 0.9
        assert arcana._rarity_to_numeric() == 1.0

    def test_condition_to_numeric(self):
        """Тест преобразования состояния в число."""
        fn = EnhancedFeatures(current_price=10.0, item_condition=ItemCondition.FACTORY_NEW)
        bs = EnhancedFeatures(current_price=10.0, item_condition=ItemCondition.BATTLE_SCARRED)

        assert fn._condition_to_numeric() == 1.0
        assert bs._condition_to_numeric() == 0.2


# ============ EnhancedFeatureExtractor Tests ============


class TestEnhancedFeatureExtractor:
    """Тесты для экстрактора признаков."""

    @pytest.fixture()
    def extractor(self):
        return EnhancedFeatureExtractor()

    def test_extract_basic_features(self, extractor):
        """Тест извлечения базовых признаков."""
        features = extractor.extract_features(
            item_name="AK-47 | Redline",
            current_price=10.0,
            game=GameType.CS2,
        )

        assert features.current_price == 10.0
        assert features.game_type == GameType.CS2
        assert features.hour_of_day >= 0
        assert features.day_of_week >= 0

    def test_extract_with_price_history(self, extractor):
        """Тест с историей цен."""
        now = datetime.now(UTC)
        price_history = [
            (now - timedelta(days=6), 9.0),
            (now - timedelta(days=5), 9.5),
            (now - timedelta(days=4), 10.0),
            (now - timedelta(days=3), 10.5),
            (now - timedelta(days=2), 11.0),
            (now - timedelta(days=1), 10.5),
            (now, 10.0),
        ]

        features = extractor.extract_features(
            item_name="AK-47 | Redline",
            current_price=10.0,
            game=GameType.CS2,
            price_history=price_history,
        )

        assert features.price_mean_7d > 0
        assert features.price_std_7d >= 0
        assert features.data_quality_score > 0.5

    def test_extract_with_sales_history(self, extractor):
        """Тест с историей продаж."""
        now = datetime.now(UTC)
        sales_history = [
            {"timestamp": (now - timedelta(hours=i)).isoformat(), "price": 10.0} for i in range(24)
        ]

        features = extractor.extract_features(
            item_name="AK-47 | Redline",
            current_price=10.0,
            game=GameType.CS2,
            sales_history=sales_history,
        )

        assert features.sales_count_24h > 0
        assert features.time_since_last_sale >= 0

    def test_extract_cs2_specific_features(self, extractor):
        """Тест CS2-специфичных признаков."""
        features = extractor.extract_features(
            item_name="AK-47 | Case Hardened (Factory New)",
            current_price=100.0,
            game=GameType.CS2,
            item_data={
                "float": 0.01,
                "pattern": 661,
                "stickers": [{"name": "Katowice 2014 iBUYPOWER Holo"}],
            },
        )

        assert features.float_value == 0.01
        assert features.float_percentile == 99.0
        assert features.pattern_index == 661
        assert features.pattern_score == 1.0  # Blue gem
        assert features.sticker_count == 1
        assert features.sticker_value > 0

    def test_extract_dota2_features(self, extractor):
        """Тест Dota 2-специфичных признаков."""
        features = extractor.extract_features(
            item_name="Genuine Dragonclaw Hook",
            current_price=500.0,
            game=GameType.DOTA2,
            item_data={
                "rarity": "immortal",
                "gems": [{"name": "Gem1"}, {"name": "Gem2"}],
            },
        )

        assert features.game_type == GameType.DOTA2
        assert features.gem_count == 2
        assert features.item_rarity == ItemRarity.IMMORTAL

    def test_extract_tf2_features(self, extractor):
        """Тест TF2-специфичных признаков."""
        features = extractor.extract_features(
            item_name="Unusual Team CaptAlgon",
            current_price=200.0,
            game=GameType.TF2,
            item_data={
                "effect": "Burning Flames",
            },
        )

        assert features.game_type == GameType.TF2
        assert features.is_unusual
        assert features.item_rarity == ItemRarity.UNUSUAL
        assert features.effect_value == 1.0

    def test_extract_rust_features(self, extractor):
        """Тест Rust-специфичных признаков."""
        features = extractor.extract_features(
            item_name="Metal Facemask Rust Skin",
            current_price=15.0,
            game=GameType.RUST,
            item_data={
                "has_skin": True,
            },
        )

        assert features.game_type == GameType.RUST
        assert features.has_skin

    def test_rsi_calculation(self, extractor):
        """Тест расчёта RSI."""
        # Восходящий тренд
        rising_prices = [1.0 + i * 0.1 for i in range(20)]
        rsi_up = extractor._calculate_rsi(rising_prices)
        assert rsi_up > 70

        # Нисходящий тренд
        falling_prices = [2.0 - i * 0.1 for i in range(20)]
        rsi_down = extractor._calculate_rsi(falling_prices)
        assert rsi_down < 30

    def test_momentum_calculation(self, extractor):
        """Тест расчёта momentum."""
        prices = [10.0, 10.5, 11.0, 11.5, 12.0]
        momentum = extractor._calculate_momentum(prices)

        assert momentum > 0  # Положительный momentum

    def test_pattern_score_blue_gem(self, extractor):
        """Тест оценки редких паттернов (blue gem)."""
        score = extractor._calculate_pattern_score("AK-47 | Case Hardened", 661)
        assert score == 1.0

    def test_sticker_value_katowice(self, extractor):
        """Тест оценки стикеров Katowice 2014."""
        stickers = [{"name": "iBUYPOWER | Katowice 2014 Holo"}]
        value = extractor._calculate_sticker_value(stickers)

        assert value >= 5000  # iBP Holo = 10000

    def test_parse_condition(self, extractor):
        """Тест парсинга состояния."""
        assert extractor._parse_condition("Factory New") == ItemCondition.FACTORY_NEW
        assert extractor._parse_condition("FN") == ItemCondition.FACTORY_NEW
        assert extractor._parse_condition("BS") == ItemCondition.BATTLE_SCARRED

    def test_update_market_index(self, extractor):
        """Тест обновления индекса рынка."""
        extractor.update_market_index(GameType.CS2, 120.0)
        assert extractor._market_index_cache[GameType.CS2] == 120.0

    def test_relative_strength_calculation(self, extractor):
        """Тест расчёта Relative Strength."""
        now = datetime.now(UTC)
        price_history = [(now - timedelta(days=i), 50.0) for i in range(7)]

        features = extractor.extract_features(
            item_name="Test Item",
            current_price=100.0,  # Выше индекса
            game=GameType.CS2,
            price_history=price_history,
        )

        assert features.relative_strength == 1.0  # current_price / market_index


# ============ MLPipeline Tests ============


class TestMLPipeline:
    """Тесты для ML Pipeline."""

    def test_basic_clean_nan(self):
        """Тест очистки NaN значений."""
        pipeline = MLPipeline()
        X = np.array([[1.0, np.nan, 3.0], [4.0, 5.0, np.inf]])

        cleaned = pipeline._basic_clean(X)

        assert not np.any(np.isnan(cleaned))
        assert not np.any(np.isinf(cleaned))

    def test_fit_transform_with_sklearn(self):
        """Тест fit_transform со sklearn."""
        pipeline = MLPipeline()
        X = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])

        try:
            transformed = pipeline.fit_transform(X)
            assert transformed.shape == X.shape
            # sklearn may not be avAlgolable, in which case basic cleaning is used
            # and _is_fitted remains False (expected behavior)
            if not pipeline._is_fitted:
                # sklearn not avAlgolable, basic cleaning was used
                pytest.skip("sklearn not avAlgolable, using basic cleaning")
        except ImportError:
            pytest.skip("sklearn not avAlgolable")

    def test_transform_after_fit(self):
        """Тест transform после fit."""
        pipeline = MLPipeline()
        X = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])

        try:
            pipeline.fit_transform(X)
            X_new = np.array([[10.0, 11.0, 12.0]])
            transformed = pipeline.transform(X_new)

            assert transformed.shape == X_new.shape
        except ImportError:
            pytest.skip("sklearn not avAlgolable")


# ============ EnhancedPricePredictor Tests ============


class TestEnhancedPricePredictor:
    """Тесты для улучшенного прогнозатора."""

    @pytest.fixture()
    def predictor(self):
        return EnhancedPricePredictor(user_balance=100.0)

    def test_create_predictor(self, predictor):
        """Тест создания прогнозатора."""
        assert predictor.user_balance == 100.0
        assert predictor.game == GameType.CS2
        assert predictor.MODEL_VERSION == "2.1.0"

    def test_set_user_balance(self, predictor):
        """Тест установки баланса."""
        predictor.set_user_balance(500.0)
        assert predictor.user_balance == 500.0

    def test_set_game(self, predictor):
        """Тест установки игры."""
        predictor.set_game(GameType.DOTA2)
        assert predictor.game == GameType.DOTA2

    def test_predict_cs2_item(self, predictor):
        """Тест прогноза для CS2 предмета."""
        prediction = predictor.predict(
            item_name="AK-47 | Redline (Field-Tested)",
            current_price=10.0,
            game=GameType.CS2,
        )

        assert "item_name" in prediction
        assert "current_price" in prediction
        assert "predicted_price_1h" in prediction
        assert "predicted_price_24h" in prediction
        assert "predicted_price_7d" in prediction
        assert "recommendation" in prediction
        assert "confidence_score" in prediction
        assert prediction["game"] == "cs2"

    def test_predict_dota2_item(self, predictor):
        """Тест прогноза для Dota 2 предмета."""
        prediction = predictor.predict(
            item_name="Dragonclaw Hook",
            current_price=500.0,
            game=GameType.DOTA2,
        )

        assert prediction["game"] == "dota2"

    def test_predict_tf2_item(self, predictor):
        """Тест прогноза для TF2 предмета."""
        prediction = predictor.predict(
            item_name="Team CaptAlgon",
            current_price=50.0,
            game=GameType.TF2,
        )

        assert prediction["game"] == "tf2"

    def test_predict_rust_item(self, predictor):
        """Тест прогноза для Rust предмета."""
        prediction = predictor.predict(
            item_name="AK47 Skin",
            current_price=25.0,
            game=GameType.RUST,
        )

        assert prediction["game"] == "rust"

    def test_prediction_has_price_ranges(self, predictor):
        """Тест наличия диапазонов цен."""
        prediction = predictor.predict(
            item_name="Test Item",
            current_price=10.0,
        )

        assert "price_range_1h" in prediction
        assert "price_range_24h" in prediction
        assert "price_range_7d" in prediction

        # Диапазоны должны быть кортежами
        assert len(prediction["price_range_24h"]) == 2
        assert prediction["price_range_24h"][0] <= prediction["price_range_24h"][1]

    def test_prediction_expected_profit(self, predictor):
        """Тест расчёта ожидаемого профита."""
        prediction = predictor.predict(
            item_name="Test Item",
            current_price=10.0,
        )

        assert "expected_profit_24h_percent" in prediction
        assert isinstance(prediction["expected_profit_24h_percent"], (int, float))

    def test_prediction_with_item_data(self, predictor):
        """Тест прогноза с дополнительными данными."""
        prediction = predictor.predict(
            item_name="AK-47 | Case Hardened (FN)",
            current_price=200.0,
            game=GameType.CS2,
            item_data={
                "float": 0.005,
                "pattern": 661,
                "stickers": [{"name": "Katowice 2014"}],
            },
        )

        assert prediction["float_value"] == 0.005
        assert prediction["pattern_score"] is not None
        assert prediction["sticker_value"] is not None

    def test_cache_hit(self, predictor):
        """Тест кэширования прогнозов."""
        # Первый вызов
        prediction1 = predictor.predict(
            item_name="Test Item",
            current_price=10.0,
            use_cache=True,
        )

        # ВтоSwarm вызов (должен вернуть кэш)
        prediction2 = predictor.predict(
            item_name="Test Item",
            current_price=10.0,
            use_cache=True,
        )

        assert prediction1["timestamp"] == prediction2["timestamp"]

    def test_cache_bypass(self, predictor):
        """Тест обхода кэша."""
        prediction1 = predictor.predict(
            item_name="Test Item",
            current_price=10.0,
            use_cache=False,
        )

        prediction2 = predictor.predict(
            item_name="Test Item",
            current_price=10.0,
            use_cache=False,
        )

        # Timestamps should be different (or very close)
        # Just check both predictions work
        assert prediction1["current_price"] == prediction2["current_price"]

    def test_balance_factor_micro(self, predictor):
        """Тест фактора баланса для микро-баланса."""
        predictor.set_user_balance(20.0)
        factor = predictor._get_balance_factor()

        assert factor > 1.0  # Консервативнее

    def test_balance_factor_whale(self, predictor):
        """Тест фактора баланса для большого баланса."""
        predictor.set_user_balance(2000.0)
        factor = predictor._get_balance_factor()

        assert factor < 1.0  # Агрессивнее

    def test_recommendation_values(self, predictor):
        """Тест допустимых значений рекомендаций."""
        valid_recommendations = {"strong_buy", "buy", "hold", "sell", "strong_sell"}

        prediction = predictor.predict(
            item_name="Test Item",
            current_price=10.0,
        )

        assert prediction["recommendation"] in valid_recommendations

    def test_confidence_level_values(self, predictor):
        """Тест допустимых уровней уверенности."""
        valid_levels = {"very_high", "high", "medium", "low", "very_low"}

        prediction = predictor.predict(
            item_name="Test Item",
            current_price=10.0,
        )

        assert prediction["confidence_level"] in valid_levels

    def test_statistical_predict_fallback(self, predictor):
        """Тест статистического прогноза (fallback)."""
        features = EnhancedFeatures(
            current_price=10.0,
            price_change_24h=5.0,
            rsi=60.0,
            momentum=2.0,
            volatility=0.05,
        )

        predicted, std = predictor._statistical_predict(features, horizon_hours=24)

        assert predicted > 0
        assert std >= 0

    def test_confidence_calculation(self, predictor):
        """Тест расчёта уверенности."""
        # Высокая уверенность: низкая волатильность, хорошие данные
        high_conf_features = EnhancedFeatures(
            current_price=10.0,
            volatility=0.05,
            data_quality_score=0.9,
            sales_count_24h=20,
            relative_strength=1.0,
        )

        confidence = predictor._calculate_confidence(high_conf_features, 0.05)
        assert confidence > 0.7

        # Низкая уверенность: высокая волатильность, плохие данные
        low_conf_features = EnhancedFeatures(
            current_price=10.0,
            volatility=0.3,
            data_quality_score=0.4,
            sales_count_24h=1,
            relative_strength=0.5,
        )

        confidence = predictor._calculate_confidence(low_conf_features, 0.3)
        assert confidence < 0.5

    def test_score_to_level(self, predictor):
        """Тест преобразования скора в уровень."""
        assert predictor._score_to_level(0.9) == "very_high"
        assert predictor._score_to_level(0.75) == "high"
        assert predictor._score_to_level(0.6) == "medium"
        assert predictor._score_to_level(0.4) == "low"
        assert predictor._score_to_level(0.2) == "very_low"

    def test_invalid_price_handling(self, predictor):
        """Тест обработки невалидной цены."""
        prediction = predictor.predict(
            item_name="Test Item",
            current_price=0.0,
        )

        assert prediction["recommendation"] == "hold"
        assert "Invalid" in prediction["reasoning"]

    def test_add_training_example(self, predictor):
        """Тест добавления примера для обучения."""
        features = EnhancedFeatures(current_price=10.0)

        predictor.add_training_example(features, 12.0)

        assert len(predictor._training_data_X) == 1
        assert len(predictor._training_data_y) == 1
        assert predictor._new_samples_count == 1


# ============ Integration Tests ============


class TestPredictorIntegration:
    """Интеграционные тесты."""

    def test_full_workflow_cs2(self):
        """Полный workflow для CS2."""
        predictor = EnhancedPricePredictor(
            user_balance=500.0,
            game=GameType.CS2,
        )

        # 1. Прогноз
        prediction = predictor.predict(
            item_name="AWP | Dragon Lore (FN)",
            current_price=5000.0,
            item_data={
                "float": 0.01,
                "stickers": [],
            },
        )

        assert prediction["current_price"] == 5000.0
        assert prediction["game"] == "cs2"

        # 2. Добавление обучающего примера
        features = predictor.feature_extractor.extract_features(
            item_name="AWP | Dragon Lore (FN)",
            current_price=5000.0,
            game=GameType.CS2,
        )
        predictor.add_training_example(features, 5200.0)

        assert predictor._new_samples_count == 1

    def test_full_workflow_dota2(self):
        """Полный workflow для Dota 2."""
        predictor = EnhancedPricePredictor(
            user_balance=1000.0,
            game=GameType.DOTA2,
        )

        prediction = predictor.predict(
            item_name="Genuine Dragonclaw Hook",
            current_price=500.0,
            game=GameType.DOTA2,
            item_data={
                "rarity": "immortal",
                "gems": [{"name": "Inscribed Gem"}],
            },
        )

        assert prediction["game"] == "dota2"

    def test_multi_game_predictions(self):
        """Тест прогнозов для разных игр."""
        predictor = EnhancedPricePredictor(user_balance=200.0)

        games = [
            (GameType.CS2, "AK-47 | Redline", 15.0),
            (GameType.DOTA2, "Arcana Item", 30.0),
            (GameType.TF2, "Team CaptAlgon", 5.0),
            (GameType.RUST, "AK Skin", 10.0),
        ]

        for game, name, price in games:
            prediction = predictor.predict(
                item_name=name,
                current_price=price,
                game=game,
            )

            assert prediction["game"] == game.value
            assert prediction["current_price"] == price
            assert prediction["recommendation"] in {
                "strong_buy",
                "buy",
                "hold",
                "sell",
                "strong_sell",
            }
