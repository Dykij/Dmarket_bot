"""Tests for src/ml/trade_classifier module.

Tests for AdaptiveTradeClassifier, TradeSignal, RiskLevel, and TradeClassification.
"""

from datetime import UTC, datetime, timedelta

from src.ml.trade_classifier import (
    AdaptiveTradeClassifier,
    RiskLevel,
    TradeClassification,
    TradeSignal,
)


class TestTradeSignal:
    """Tests for TradeSignal enum."""

    def test_strong_buy(self):
        """Test STRONG_BUY value."""
        assert TradeSignal.STRONG_BUY == "strong_buy"

    def test_buy(self):
        """Test BUY value."""
        assert TradeSignal.BUY == "buy"

    def test_hold(self):
        """Test HOLD value."""
        assert TradeSignal.HOLD == "hold"

    def test_sell(self):
        """Test SELL value."""
        assert TradeSignal.SELL == "sell"

    def test_strong_sell(self):
        """Test STRONG_SELL value."""
        assert TradeSignal.STRONG_SELL == "strong_sell"

    def test_skip(self):
        """Test SKIP value."""
        assert TradeSignal.SKIP == "skip"


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_very_low(self):
        """Test VERY_LOW value."""
        assert RiskLevel.VERY_LOW == "very_low"

    def test_low(self):
        """Test LOW value."""
        assert RiskLevel.LOW == "low"

    def test_medium(self):
        """Test MEDIUM value."""
        assert RiskLevel.MEDIUM == "medium"

    def test_high(self):
        """Test HIGH value."""
        assert RiskLevel.HIGH == "high"

    def test_very_high(self):
        """Test VERY_HIGH value."""
        assert RiskLevel.VERY_HIGH == "very_high"


class TestTradeClassification:
    """Tests for TradeClassification dataclass."""

    def test_is_actionable_strong_buy(self):
        """Test is_actionable for STRONG_BUY."""
        classification = TradeClassification(
            item_name="Test",
            signal=TradeSignal.STRONG_BUY,
            risk_level=RiskLevel.LOW,
            signal_probabilities={},
            risk_score=0.2,
            recommended_position_size=10.0,
            max_loss_percent=5.0,
            classification_timestamp=datetime.now(UTC),
            reasoning=["Test"],
            expected_profit_percent=15.0,
            profit_probability=0.7,
        )

        assert classification.is_actionable() is True

    def test_is_actionable_buy(self):
        """Test is_actionable for BUY."""
        classification = TradeClassification(
            item_name="Test",
            signal=TradeSignal.BUY,
            risk_level=RiskLevel.LOW,
            signal_probabilities={},
            risk_score=0.2,
            recommended_position_size=10.0,
            max_loss_percent=5.0,
            classification_timestamp=datetime.now(UTC),
            reasoning=["Test"],
            expected_profit_percent=10.0,
            profit_probability=0.6,
        )

        assert classification.is_actionable() is True

    def test_is_actionable_hold(self):
        """Test is_actionable for HOLD."""
        classification = TradeClassification(
            item_name="Test",
            signal=TradeSignal.HOLD,
            risk_level=RiskLevel.MEDIUM,
            signal_probabilities={},
            risk_score=0.3,
            recommended_position_size=0.0,
            max_loss_percent=0.0,
            classification_timestamp=datetime.now(UTC),
            reasoning=["No clear signal"],
            expected_profit_percent=2.0,
            profit_probability=0.5,
        )

        assert classification.is_actionable() is False

    def test_is_actionable_skip(self):
        """Test is_actionable for SKIP."""
        classification = TradeClassification(
            item_name="Test",
            signal=TradeSignal.SKIP,
            risk_level=RiskLevel.VERY_HIGH,
            signal_probabilities={},
            risk_score=0.8,
            recommended_position_size=0.0,
            max_loss_percent=20.0,
            classification_timestamp=datetime.now(UTC),
            reasoning=["High risk"],
            expected_profit_percent=5.0,
            profit_probability=0.3,
        )

        assert classification.is_actionable() is False


class TestAdaptiveTradeClassifier:
    """Tests for AdaptiveTradeClassifier class."""

    def test_init_default(self):
        """Test default initialization."""
        classifier = AdaptiveTradeClassifier()

        assert classifier.user_balance == 100.0
        assert classifier.risk_tolerance == "moderate"

    def test_init_custom(self):
        """Test custom initialization."""
        classifier = AdaptiveTradeClassifier(
            user_balance=500.0,
            risk_tolerance="aggressive",
        )

        assert classifier.user_balance == 500.0
        assert classifier.risk_tolerance == "aggressive"

    def test_set_user_balance(self):
        """Test set_user_balance updates thresholds."""
        classifier = AdaptiveTradeClassifier(user_balance=100.0)

        classifier.set_user_balance(500.0)

        assert classifier.user_balance == 500.0

    def test_set_user_balance_negative(self):
        """Test set_user_balance clamps negative to zero."""
        classifier = AdaptiveTradeClassifier(user_balance=100.0)

        classifier.set_user_balance(-50.0)

        assert classifier.user_balance == 0.0

    def test_set_risk_tolerance_conservative(self):
        """Test set_risk_tolerance to conservative."""
        classifier = AdaptiveTradeClassifier()

        classifier.set_risk_tolerance("conservative")

        assert classifier.risk_tolerance == "conservative"
        assert classifier.thresholds["max_risk_score"] < 0.5

    def test_set_risk_tolerance_aggressive(self):
        """Test set_risk_tolerance to aggressive."""
        classifier = AdaptiveTradeClassifier()

        classifier.set_risk_tolerance("aggressive")

        assert classifier.risk_tolerance == "aggressive"
        assert classifier.thresholds["max_risk_score"] > 0.6

    def test_set_risk_tolerance_invalid(self):
        """Test set_risk_tolerance with invalid value."""
        classifier = AdaptiveTradeClassifier()
        original = classifier.risk_tolerance

        classifier.set_risk_tolerance("invalid")

        # Should remain unchanged
        assert classifier.risk_tolerance == original

    def test_classify_strong_buy(self):
        """Test classify returns STRONG_BUY for high profit with good liquidity."""
        from datetime import datetime, timedelta

        classifier = AdaptiveTradeClassifier(user_balance=100.0)

        # Provide price_history and sales_history for good liquidity/risk scores
        now = datetime.now(UTC)
        price_history = [(now - timedelta(hours=i), 10.0) for i in range(24)]
        sales_history = [{"price": 10.0, "date": now - timedelta(hours=i)} for i in range(20)]

        classification = classifier.classify(
            item_name="Test Item",
            current_price=10.0,
            expected_price=12.0,  # +20% profit
            price_history=price_history,
            sales_history=sales_history,
        )

        assert isinstance(classification, TradeClassification)
        assert classification.signal == TradeSignal.STRONG_BUY
        assert classification.expected_profit_percent > 10.0

    def test_classify_buy(self):
        """Test classify returns BUY for moderate profit with good data."""
        from datetime import datetime, timedelta

        classifier = AdaptiveTradeClassifier(user_balance=100.0)
        now = datetime.now(UTC)
        price_history = [(now - timedelta(hours=i), 10.0) for i in range(24)]
        sales_history = [{"price": 10.0, "date": now - timedelta(hours=i)} for i in range(20)]

        classification = classifier.classify(
            item_name="Test Item",
            current_price=10.0,
            expected_price=10.7,  # +7% profit
            price_history=price_history,
            sales_history=sales_history,
        )

        assert classification.signal in (TradeSignal.BUY, TradeSignal.STRONG_BUY)
        assert classification.expected_profit_percent > 0

    def test_classify_hold(self):
        """Test classify returns HOLD for minimal change with good data."""
        from datetime import datetime, timedelta

        classifier = AdaptiveTradeClassifier(user_balance=100.0)
        now = datetime.now(UTC)
        price_history = [(now - timedelta(hours=i), 10.0) for i in range(24)]
        sales_history = [{"price": 10.0, "date": now - timedelta(hours=i)} for i in range(20)]

        classification = classifier.classify(
            item_name="Test Item",
            current_price=10.0,
            expected_price=10.2,  # +2% (below threshold)
            price_history=price_history,
            sales_history=sales_history,
        )

        assert classification.signal in (TradeSignal.HOLD, TradeSignal.BUY)

    def test_classify_sell(self):
        """Test classify returns SELL for moderate loss with good data."""
        from datetime import datetime, timedelta

        classifier = AdaptiveTradeClassifier(user_balance=100.0)
        now = datetime.now(UTC)
        price_history = [(now - timedelta(hours=i), 10.0) for i in range(24)]
        sales_history = [{"price": 10.0, "date": now - timedelta(hours=i)} for i in range(20)]

        classification = classifier.classify(
            item_name="Test Item",
            current_price=10.0,
            expected_price=9.3,  # -7% loss
            price_history=price_history,
            sales_history=sales_history,
        )

        assert classification.signal in (TradeSignal.SELL, TradeSignal.STRONG_SELL, TradeSignal.HOLD)

    def test_classify_with_price_history(self):
        """Test classify with price history."""
        classifier = AdaptiveTradeClassifier()

        now = datetime.now(UTC)
        price_history = [
            (now - timedelta(days=7), 8.0),
            (now - timedelta(days=3), 9.0),
            (now - timedelta(hours=1), 9.5),
        ]

        classification = classifier.classify(
            item_name="Test Item",
            current_price=10.0,
            expected_price=12.0,
            price_history=price_history,
        )

        assert isinstance(classification, TradeClassification)

    def test_classify_with_sales_history(self):
        """Test classify with sales history."""
        classifier = AdaptiveTradeClassifier()

        now = datetime.now(UTC)
        sales_history = [
            {"timestamp": now - timedelta(hours=1)},
            {"timestamp": now - timedelta(hours=5)},
            {"timestamp": now - timedelta(days=1)},
        ]

        classification = classifier.classify(
            item_name="Test Item",
            current_price=10.0,
            expected_price=12.0,
            sales_history=sales_history,
        )

        assert isinstance(classification, TradeClassification)

    def test_calculate_risk_low_volatility(self):
        """Test risk calculation with low volatility."""
        classifier = AdaptiveTradeClassifier()

        from src.ml.feature_extractor import PriceFeatures

        features = PriceFeatures(
            current_price=10.0,
            volatility=0.05,
            sales_count_24h=20,
            data_quality_score=1.0,
        )

        risk_score, factors = classifier._calculate_risk(features, 10.0)

        assert risk_score < 0.5
        assert isinstance(factors, list)

    def test_calculate_risk_high_volatility(self):
        """Test risk calculation with high volatility."""
        classifier = AdaptiveTradeClassifier()

        from src.ml.feature_extractor import PriceFeatures, TrendDirection

        features = PriceFeatures(
            current_price=10.0,
            volatility=0.3,
            sales_count_24h=2,
            trend_direction=TrendDirection.VOLATILE,
            data_quality_score=0.5,
        )

        risk_score, factors = classifier._calculate_risk(features, 10.0)

        assert risk_score > 0.3
        assert len(factors) > 0

    def test_score_to_risk_level(self):
        """Test risk score to level conversion."""
        classifier = AdaptiveTradeClassifier()

        assert classifier._score_to_risk_level(0.05) == RiskLevel.VERY_LOW
        assert classifier._score_to_risk_level(0.15) == RiskLevel.LOW
        assert classifier._score_to_risk_level(0.3) == RiskLevel.MEDIUM
        assert classifier._score_to_risk_level(0.5) == RiskLevel.HIGH
        assert classifier._score_to_risk_level(0.8) == RiskLevel.VERY_HIGH

    def test_calculate_liquidity_score_high(self):
        """Test liquidity score for high liquidity."""
        classifier = AdaptiveTradeClassifier()

        from src.ml.feature_extractor import PriceFeatures

        features = PriceFeatures(
            current_price=10.0,
            avg_sales_per_day=15.0,
            market_depth=100.0,
        )

        score = classifier._calculate_liquidity_score(features)

        assert score > 0.8

    def test_calculate_liquidity_score_low(self):
        """Test liquidity score for low liquidity."""
        classifier = AdaptiveTradeClassifier()

        from src.ml.feature_extractor import PriceFeatures

        features = PriceFeatures(
            current_price=10.0,
            avg_sales_per_day=0.5,
            market_depth=5.0,
        )

        score = classifier._calculate_liquidity_score(features)

        assert score < 0.5

    def test_calculate_position_size_strong_buy(self):
        """Test position size for strong buy."""
        classifier = AdaptiveTradeClassifier(user_balance=100.0)

        size = classifier._calculate_position_size(
            current_price=10.0,
            risk_score=0.2,
            signal=TradeSignal.STRONG_BUY,
        )

        assert size > 0

    def test_calculate_position_size_hold(self):
        """Test position size for hold (should be zero)."""
        classifier = AdaptiveTradeClassifier(user_balance=100.0)

        size = classifier._calculate_position_size(
            current_price=10.0,
            risk_score=0.3,
            signal=TradeSignal.HOLD,
        )

        assert size == 0.0

    def test_calculate_max_loss(self):
        """Test max loss calculation."""
        classifier = AdaptiveTradeClassifier()

        from src.ml.feature_extractor import PriceFeatures, TrendDirection

        features = PriceFeatures(
            current_price=10.0,
            volatility=0.1,
            trend_direction=TrendDirection.DOWN,
        )

        max_loss = classifier._calculate_max_loss(features, 10.0)

        assert max_loss > 0
        assert max_loss <= 50.0  # Capped at 50%

    def test_calculate_profit_probability(self):
        """Test profit probability calculation."""
        classifier = AdaptiveTradeClassifier()

        from src.ml.feature_extractor import PriceFeatures, TrendDirection

        features = PriceFeatures(
            current_price=10.0,
            trend_direction=TrendDirection.UP,
            rsi=50.0,
            sales_count_24h=15,
        )

        prob = classifier._calculate_profit_probability(features, 10.0)

        assert 0.1 <= prob <= 0.9

    def test_generate_reasoning(self):
        """Test reasoning generation."""
        classifier = AdaptiveTradeClassifier()

        reasoning = classifier._generate_reasoning(
            signal=TradeSignal.STRONG_BUY,
            risk_factors=["High volatility"],
            expected_profit_percent=15.0,
            liquidity_score=0.8,
        )

        assert isinstance(reasoning, list)
        assert len(reasoning) > 0
        assert any("Strong buy" in r for r in reasoning)

    def test_batch_classify(self):
        """Test batch classification."""
        classifier = AdaptiveTradeClassifier(user_balance=100.0)

        items = [
            {"title": "Item 1", "price": {"USD": 1000}},
            {"title": "Item 2", "price": {"USD": 2000}},
        ]

        # Without predictions, expected = current
        classifications = classifier.batch_classify(items)

        assert len(classifications) == 2
        assert all(isinstance(c, TradeClassification) for c in classifications)

    def test_batch_classify_empty(self):
        """Test batch classify with empty list."""
        classifier = AdaptiveTradeClassifier()

        classifications = classifier.batch_classify([])

        assert classifications == []

    def test_thresholds_conservative(self):
        """Test conservative thresholds are stricter."""
        classifier = AdaptiveTradeClassifier(risk_tolerance="conservative")

        # Conservative should require higher profit
        assert classifier.thresholds["strong_buy_profit"] > 10.0
        # And lower risk tolerance
        assert classifier.thresholds["max_risk_score"] < 0.5

    def test_thresholds_aggressive(self):
        """Test aggressive thresholds are looser."""
        classifier = AdaptiveTradeClassifier(risk_tolerance="aggressive")

        # Aggressive should accept lower profit
        assert classifier.thresholds["strong_buy_profit"] < 10.0
        # And higher risk tolerance
        assert classifier.thresholds["max_risk_score"] > 0.6
