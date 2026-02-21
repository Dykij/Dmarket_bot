"""Тесты для ML модулей прогнозирования цен."""

from datetime import UTC, datetime, timedelta

import numpy as np


class TestPriceFeatures:
    """Тесты для PriceFeatures."""

    def test_to_array_returns_correct_shape(self):
        """Тест преобразования в массив."""
        from src.ml.feature_extractor import PriceFeatures

        features = PriceFeatures(current_price=10.0)
        array = features.to_array()

        assert isinstance(array, np.ndarray)
        assert array.dtype == np.float64
        assert len(array) == 18  # 18 признаков

    def test_to_array_contAlgons_current_price(self):
        """Тест что массив содержит текущую цену."""
        from src.ml.feature_extractor import PriceFeatures

        features = PriceFeatures(current_price=25.50)
        array = features.to_array()

        assert array[0] == 25.50

    def test_feature_names_returns_list(self):
        """Тест получения названий признаков."""
        from src.ml.feature_extractor import PriceFeatures

        names = PriceFeatures.feature_names()

        assert isinstance(names, list)
        assert len(names) == 18
        assert "current_price" in names
        assert "rsi" in names
        assert "volatility" in names


class TestMarketFeatureExtractor:
    """Тесты для MarketFeatureExtractor."""

    def test_extract_features_basic(self):
        """Тест базового извлечения признаков."""
        from src.ml.feature_extractor import MarketFeatureExtractor, PriceFeatures

        extractor = MarketFeatureExtractor()
        features = extractor.extract_features(
            item_name="AK-47 | Redline",
            current_price=10.0,
        )

        assert isinstance(features, PriceFeatures)
        assert features.current_price == 10.0
        assert 0 <= features.hour_of_day <= 23
        assert 0 <= features.day_of_week <= 6

    def test_extract_features_with_price_history(self):
        """Тест извлечения признаков с историей цен."""
        from src.ml.feature_extractor import MarketFeatureExtractor

        extractor = MarketFeatureExtractor()
        now = datetime.now(UTC)

        price_history = [
            (now - timedelta(days=6), 9.0),
            (now - timedelta(days=4), 9.5),
            (now - timedelta(days=2), 10.0),
            (now - timedelta(hours=12), 10.5),
            (now - timedelta(hours=1), 11.0),
        ]

        features = extractor.extract_features(
            item_name="Test Item",
            current_price=11.0,
            price_history=price_history,
        )

        assert features.price_mean_7d > 0
        assert features.price_std_7d >= 0
        assert features.price_change_7d != 0

    def test_rsi_calculation(self):
        """Тест расчёта RSI."""
        from src.ml.feature_extractor import MarketFeatureExtractor

        extractor = MarketFeatureExtractor()

        # Растущие цены - RSI должен быть высоким
        rising_prices = list(range(50, 70))
        rsi = extractor._calculate_rsi(rising_prices)
        assert rsi > 50

        # Падающие цены - RSI должен быть низким
        falling_prices = list(range(70, 50, -1))
        rsi = extractor._calculate_rsi(falling_prices)
        assert rsi < 50

    def test_momentum_calculation(self):
        """Тест расчёта momentum."""
        from src.ml.feature_extractor import MarketFeatureExtractor

        extractor = MarketFeatureExtractor()

        # Растущие цены - положительный momentum
        rising_prices = [10, 11, 12, 13, 14, 15]
        momentum = extractor._calculate_momentum(rising_prices)
        assert momentum > 0

        # Падающие цены - отрицательный momentum
        falling_prices = [15, 14, 13, 12, 11, 10]
        momentum = extractor._calculate_momentum(falling_prices)
        assert momentum < 0

    def test_trend_direction_detection(self):
        """Тест определения направления тренда."""
        from src.ml.feature_extractor import MarketFeatureExtractor, TrendDirection

        extractor = MarketFeatureExtractor()

        # Сильный рост
        trend = extractor._determine_trend(price_change_7d=10.0, volatility=0.05)
        assert trend == TrendDirection.UP

        # Сильное падение
        trend = extractor._determine_trend(price_change_7d=-10.0, volatility=0.05)
        assert trend == TrendDirection.DOWN

        # Высокая волатильность
        trend = extractor._determine_trend(price_change_7d=3.0, volatility=0.2)
        assert trend == TrendDirection.VOLATILE

        # Стабильный
        trend = extractor._determine_trend(price_change_7d=2.0, volatility=0.05)
        assert trend == TrendDirection.STABLE


class TestAdaptivePricePredictor:
    """Тесты для AdaptivePricePredictor."""

    def test_initialization(self):
        """Тест инициализации."""
        from src.ml.price_predictor import AdaptivePricePredictor

        predictor = AdaptivePricePredictor(user_balance=100.0)

        assert predictor.user_balance == 100.0
        assert predictor.MODEL_VERSION == "1.1.0"

    def test_set_user_balance(self):
        """Тест установки баланса."""
        from src.ml.price_predictor import AdaptivePricePredictor

        predictor = AdaptivePricePredictor(user_balance=50.0)
        predictor.set_user_balance(200.0)

        assert predictor.user_balance == 200.0

    def test_predict_returns_prediction(self):
        """Тест что predict возвращает PricePrediction."""
        from src.ml.price_predictor import AdaptivePricePredictor, PricePrediction

        predictor = AdaptivePricePredictor(user_balance=100.0)
        prediction = predictor.predict(
            item_name="Test Item",
            current_price=10.0,
        )

        assert isinstance(prediction, PricePrediction)
        assert prediction.item_name == "Test Item"
        assert prediction.current_price == 10.0
        assert prediction.predicted_price_1h > 0
        assert prediction.predicted_price_24h > 0
        assert prediction.predicted_price_7d > 0

    def test_predict_with_price_history(self):
        """Тест прогноза с историей цен."""
        from src.ml.price_predictor import AdaptivePricePredictor

        predictor = AdaptivePricePredictor(user_balance=100.0)
        now = datetime.now(UTC)

        price_history = [
            (now - timedelta(days=7), 8.0),
            (now - timedelta(days=5), 9.0),
            (now - timedelta(days=3), 10.0),
            (now - timedelta(days=1), 11.0),
        ]

        prediction = predictor.predict(
            item_name="Test Item",
            current_price=12.0,
            price_history=price_history,
        )

        # При растущем тренде прогноз должен быть выше текущей цены
        assert prediction.predicted_price_24h >= prediction.current_price * 0.9

    def test_expected_profit_percent(self):
        """Тест расчёта ожидаемой прибыли."""
        from src.ml.price_predictor import AdaptivePricePredictor

        predictor = AdaptivePricePredictor(user_balance=100.0)
        prediction = predictor.predict(
            item_name="Test Item",
            current_price=10.0,
        )

        profit = prediction.expected_profit_percent("24h")
        # Прибыль должна быть числом
        assert isinstance(profit, float)

    def test_confidence_levels(self):
        """Тест уровней уверенности."""
        from src.ml.price_predictor import AdaptivePricePredictor, PredictionConfidence

        predictor = AdaptivePricePredictor(user_balance=100.0)
        prediction = predictor.predict(
            item_name="Test Item",
            current_price=10.0,
        )

        assert prediction.confidence in PredictionConfidence
        assert 0 <= prediction.confidence_score <= 1

    def test_balance_factor_affects_recommendations(self):
        """Тест влияния баланса на рекомендации."""
        from src.ml.price_predictor import AdaptivePricePredictor

        # Маленький баланс
        small_predictor = AdaptivePricePredictor(user_balance=20.0)
        small_factor = small_predictor._get_balance_factor()

        # Большой баланс
        large_predictor = AdaptivePricePredictor(user_balance=1000.0)
        large_factor = large_predictor._get_balance_factor()

        # Маленький баланс должен давать более консервативный фактор
        assert small_factor > large_factor

    def test_cache_works(self):
        """Тест работы кэша."""
        from src.ml.price_predictor import AdaptivePricePredictor

        predictor = AdaptivePricePredictor(user_balance=100.0)

        # Первый вызов
        pred1 = predictor.predict(
            item_name="Test Item",
            current_price=10.0,
            use_cache=True,
        )

        # ВтоSwarm вызов с тем же ключом
        pred2 = predictor.predict(
            item_name="Test Item",
            current_price=10.0,
            use_cache=True,
        )

        # Должны получить тот же объект из кэша
        assert pred1.prediction_timestamp == pred2.prediction_timestamp


class TestTradeClassifier:
    """Тесты для AdaptiveTradeClassifier."""

    def test_initialization(self):
        """Тест инициализации."""
        from src.ml.trade_classifier import AdaptiveTradeClassifier

        classifier = AdaptiveTradeClassifier(
            user_balance=100.0,
            risk_tolerance="moderate",
        )

        assert classifier.user_balance == 100.0
        assert classifier.risk_tolerance == "moderate"

    def test_classify_returns_classification(self):
        """Тест что classify возвращает TradeClassification."""
        from src.ml.trade_classifier import AdaptiveTradeClassifier, TradeClassification

        classifier = AdaptiveTradeClassifier(user_balance=100.0)
        result = classifier.classify(
            item_name="Test Item",
            current_price=10.0,
            expected_price=12.0,
        )

        assert isinstance(result, TradeClassification)
        assert result.item_name == "Test Item"

    def test_risk_levels(self):
        """Тест уровней риска."""
        from src.ml.trade_classifier import AdaptiveTradeClassifier, RiskLevel

        classifier = AdaptiveTradeClassifier(user_balance=100.0)
        result = classifier.classify(
            item_name="Test Item",
            current_price=10.0,
            expected_price=11.0,
        )

        assert result.risk_level in RiskLevel
        assert 0 <= result.risk_score <= 1

    def test_trade_signals(self):
        """Тест торговых сигналов."""
        from src.ml.trade_classifier import AdaptiveTradeClassifier, TradeSignal

        classifier = AdaptiveTradeClassifier(user_balance=100.0)

        # Высокая ожидаемая прибыль - может быть сигнал покупки или SKIP
        # (SKIP возможен при отсутствии данных о ликвидности)
        result = classifier.classify(
            item_name="Test Item",
            current_price=10.0,
            expected_price=15.0,  # +50%
        )
        # Без данных о ликвидности может быть любой сигнал
        assert result.signal in (
            TradeSignal.STRONG_BUY,
            TradeSignal.BUY,
            TradeSignal.HOLD,
            TradeSignal.SKIP,
        )

        # Ожидаемое падение - сигнал продажи
        result = classifier.classify(
            item_name="Test Item",
            current_price=10.0,
            expected_price=7.0,  # -30%
        )
        # При падении должен быть SELL, STRONG_SELL, HOLD или SKIP
        assert result.signal in (
            TradeSignal.STRONG_SELL,
            TradeSignal.SELL,
            TradeSignal.HOLD,
            TradeSignal.SKIP,
        )

    def test_risk_tolerance_affects_thresholds(self):
        """Тест влияния толерантности к риску на пороги."""
        from src.ml.trade_classifier import AdaptiveTradeClassifier

        conservative = AdaptiveTradeClassifier(
            user_balance=100.0,
            risk_tolerance="conservative",
        )
        aggressive = AdaptiveTradeClassifier(
            user_balance=100.0,
            risk_tolerance="aggressive",
        )

        # Консервативный должен иметь более высокие пороги прибыли
        assert conservative.thresholds["buy_profit"] > aggressive.thresholds["buy_profit"]


class TestBalanceAdaptiveStrategy:
    """Тесты для BalanceAdaptiveStrategy."""

    def test_initialization(self):
        """Тест инициализации."""
        from src.ml.balance_adapter import BalanceAdaptiveStrategy

        strategy = BalanceAdaptiveStrategy(user_balance=100.0)

        assert strategy.user_balance == 100.0

    def test_balance_categories(self):
        """Тест категорий баланса."""
        from src.ml.balance_adapter import BalanceAdaptiveStrategy, BalanceCategory

        # Micro: < $20
        strategy = BalanceAdaptiveStrategy(user_balance=10.0)
        assert strategy.category == BalanceCategory.MICRO

        # Small: $20-100
        strategy = BalanceAdaptiveStrategy(user_balance=50.0)
        assert strategy.category == BalanceCategory.SMALL

        # Medium: $100-500
        strategy = BalanceAdaptiveStrategy(user_balance=200.0)
        assert strategy.category == BalanceCategory.MEDIUM

        # Large: $500-2000
        strategy = BalanceAdaptiveStrategy(user_balance=1000.0)
        assert strategy.category == BalanceCategory.LARGE

        # Whale: > $2000
        strategy = BalanceAdaptiveStrategy(user_balance=5000.0)
        assert strategy.category == BalanceCategory.WHALE

    def test_get_recommendation(self):
        """Тест получения рекомендаций."""
        from src.ml.balance_adapter import BalanceAdaptiveStrategy, StrategyRecommendation

        strategy = BalanceAdaptiveStrategy(user_balance=100.0)
        rec = strategy.get_recommendation()

        assert isinstance(rec, StrategyRecommendation)
        assert rec.balance_usd == 100.0
        assert rec.max_position_percent > 0
        assert rec.min_profit_threshold > 0

    def test_position_size_scales_with_balance(self):
        """Тест что размер позиции масштабируется с балансом."""
        from src.ml.balance_adapter import BalanceAdaptiveStrategy

        small_strategy = BalanceAdaptiveStrategy(user_balance=50.0)
        large_strategy = BalanceAdaptiveStrategy(user_balance=500.0)

        small_max = small_strategy.get_max_position_value()
        large_max = large_strategy.get_max_position_value()

        # Большой баланс должен давать бОльшую максимальную позицию
        assert large_max > small_max

    def test_should_buy_checks(self):
        """Тест проверок should_buy."""
        from src.ml.balance_adapter import BalanceAdaptiveStrategy

        strategy = BalanceAdaptiveStrategy(user_balance=100.0)

        # Должен разрешить покупку
        should_buy, reason = strategy.should_buy(
            item_price=20.0,
            expected_profit_percent=15.0,
            risk_score=0.3,
            current_positions=0,
        )
        assert should_buy

        # Цена слишком высокая
        should_buy, reason = strategy.should_buy(
            item_price=50.0,  # >30% от баланса
            expected_profit_percent=15.0,
            risk_score=0.3,
            current_positions=0,
        )
        assert not should_buy
        assert "exceeds" in reason.lower()

        # Прибыль слишком низкая
        should_buy, reason = strategy.should_buy(
            item_price=20.0,
            expected_profit_percent=3.0,  # Ниже порога
            risk_score=0.3,
            current_positions=0,
        )
        assert not should_buy
        assert "threshold" in reason.lower()

    def test_adapt_to_market_conditions(self):
        """Тест адаптации к рыночным условиям."""
        from src.ml.balance_adapter import BalanceAdaptiveStrategy

        strategy = BalanceAdaptiveStrategy(user_balance=100.0)

        # Базовые параметры
        base_params = strategy.CATEGORY_PARAMS[strategy.category]

        # Высокая волатильность
        adapted = strategy.adapt_to_market_conditions(volatility=0.3)
        assert adapted["min_profit_threshold"] > base_params["min_profit_threshold"]

        # Распродажа Steam
        adapted = strategy.adapt_to_market_conditions(
            volatility=0.1,
            is_sale_period=True,
        )
        assert adapted["max_position_percent"] < base_params["max_position_percent"]


class TestPortfolioAllocator:
    """Тесты для AdaptivePortfolioAllocator."""

    def test_allocate_empty_list(self):
        """Тест с пустым списком."""
        from src.ml.balance_adapter import AdaptivePortfolioAllocator, BalanceAdaptiveStrategy

        strategy = BalanceAdaptiveStrategy(user_balance=100.0)
        allocator = AdaptivePortfolioAllocator(strategy)

        result = allocator.allocate([])
        assert result == []

    def test_allocate_returns_allocations(self):
        """Тест что allocate возвращает распределения."""
        from src.ml.balance_adapter import AdaptivePortfolioAllocator, BalanceAdaptiveStrategy

        strategy = BalanceAdaptiveStrategy(user_balance=100.0)
        allocator = AdaptivePortfolioAllocator(strategy)

        opportunities = [
            {
                "item_name": "Item 1",
                "price": 10.0,
                "expected_profit": 15.0,
                "risk_score": 0.3,
                "confidence": 0.7,
            },
            {
                "item_name": "Item 2",
                "price": 20.0,
                "expected_profit": 10.0,
                "risk_score": 0.4,
                "confidence": 0.6,
            },
        ]

        result = allocator.allocate(opportunities)

        assert len(result) == 2
        assert all("allocation" in item for item in result)
        assert all("allocation_reason" in item for item in result)

    def test_allocate_respects_max_positions(self):
        """Тест соблюдения максимума позиций."""
        from src.ml.balance_adapter import AdaptivePortfolioAllocator, BalanceAdaptiveStrategy

        strategy = BalanceAdaptiveStrategy(user_balance=100.0)
        allocator = AdaptivePortfolioAllocator(strategy)

        max_positions = strategy.get_max_concurrent_positions()

        # Создаём больше возможностей чем max_positions
        opportunities = [
            {
                "item_name": f"Item {i}",
                "price": 5.0,
                "expected_profit": 20.0,
                "risk_score": 0.2,
                "confidence": 0.8,
            }
            for i in range(max_positions + 3)
        ]

        result = allocator.allocate(opportunities)

        # Количество ненулевых аллокаций <= max_positions
        allocated_count = sum(1 for item in result if item["allocation"] > 0)
        assert allocated_count <= max_positions
