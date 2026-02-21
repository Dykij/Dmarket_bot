"""Tests for AlgoCoordinator - unified ML module coordinator."""


import pytest

from src.ml.Algo_coordinator import (
    AlgoCoordinator,
    AutonomyLevel,
    ItemAnalysis,
    SafetyLimits,
    TradeAction,
    TradeDecision,
    get_Algo_coordinator,
    reset_Algo_coordinator,
)
from src.ml.smart_recommendations import RiskLevel


class TestAlgoCoordinatorBasic:
    """Basic tests for AlgoCoordinator."""

    def test_init_creates_coordinator(self):
        """Test that AlgoCoordinator can be initialized."""
        coordinator = AlgoCoordinator()

        assert coordinator is not None
        assert coordinator.autonomy_level == AutonomyLevel.MANUAL
        assert coordinator.user_balance == 100.0
        assert coordinator.safety_limits.dry_run is True

    def test_init_with_custom_autonomy(self):
        """Test initialization with custom autonomy level."""
        coordinator = AlgoCoordinator(autonomy_level=AutonomyLevel.SEMI_AUTO)

        assert coordinator.autonomy_level == AutonomyLevel.SEMI_AUTO

    def test_init_with_custom_balance(self):
        """Test initialization with custom balance."""
        coordinator = AlgoCoordinator(user_balance=500.0)

        assert coordinator.user_balance == 500.0

    def test_init_with_custom_limits(self):
        """Test initialization with custom safety limits."""
        limits = SafetyLimits(
            max_single_trade_usd=100.0,
            max_dAlgoly_volume_usd=500.0,
            dry_run=False,
        )
        coordinator = AlgoCoordinator(safety_limits=limits)

        assert coordinator.safety_limits.max_single_trade_usd == 100.0
        assert coordinator.safety_limits.max_dAlgoly_volume_usd == 500.0
        assert coordinator.safety_limits.dry_run is False


class TestAutonomyLevel:
    """Tests for autonomy level management."""

    def test_set_autonomy_level(self):
        """Test setting autonomy level."""
        coordinator = AlgoCoordinator()

        coordinator.set_autonomy_level(AutonomyLevel.AUTO)

        assert coordinator.autonomy_level == AutonomyLevel.AUTO

    def test_set_user_balance(self):
        """Test setting user balance."""
        coordinator = AlgoCoordinator()

        coordinator.set_user_balance(250.0)

        assert coordinator.user_balance == 250.0

    def test_set_negative_balance_clamps_to_zero(self):
        """Test that negative balance is clamped to zero."""
        coordinator = AlgoCoordinator()

        coordinator.set_user_balance(-50.0)

        assert coordinator.user_balance == 0.0


class TestMarketCondition:
    """Tests for market condition updates."""

    def test_update_market_condition(self):
        """Test updating market condition."""
        from src.ml.discount_threshold_predictor import MarketCondition

        coordinator = AlgoCoordinator()

        coordinator.update_market_condition(MarketCondition.VOLATILE)

        assert coordinator._market_condition == MarketCondition.VOLATILE


class TestSafetyLimits:
    """Tests for SafetyLimits dataclass."""

    def test_default_safety_limits(self):
        """Test default safety limits."""
        limits = SafetyLimits()

        assert limits.max_single_trade_usd == 50.0
        assert limits.max_dAlgoly_volume_usd == 200.0
        assert limits.max_position_percent == 30.0
        assert limits.min_confidence_auto == 0.80
        assert limits.max_trades_per_hour == 10
        assert limits.loss_cooldown_minutes == 30
        assert limits.dry_run is True

    def test_custom_safety_limits(self):
        """Test custom safety limits."""
        limits = SafetyLimits(
            max_single_trade_usd=25.0,
            dry_run=False,
        )

        assert limits.max_single_trade_usd == 25.0
        assert limits.dry_run is False


class TestTradeDecision:
    """Tests for TradeDecision dataclass."""

    def test_trade_decision_creation(self):
        """Test creating a TradeDecision."""
        decision = TradeDecision(
            action=TradeAction.BUY,
            item_name="AK-47 | Redline (Field-Tested)",
            item_id="abc123",
            game="csgo",
            current_price=10.0,
            predicted_price=12.0,
            expected_profit=2.0,
            expected_profit_percent=20.0,
            confidence=0.85,
            risk_level=RiskLevel.LOW,
            discount_threshold_used=15.0,
            price_prediction_confidence=0.78,
            signal_probability=0.72,
            anomaly_score=0.1,
            reasoning=["Price below threshold", "Positive signal"],
        )

        assert decision.action == TradeAction.BUY
        assert decision.item_name == "AK-47 | Redline (Field-Tested)"
        assert decision.expected_profit == 2.0

    def test_trade_decision_to_dict(self):
        """Test TradeDecision to_dict method."""
        decision = TradeDecision(
            action=TradeAction.BUY,
            item_name="Test Item",
            item_id="test123",
            game="csgo",
            current_price=10.0,
            predicted_price=12.0,
            expected_profit=2.0,
            expected_profit_percent=20.0,
            confidence=0.85,
            risk_level=RiskLevel.MEDIUM,
            discount_threshold_used=15.0,
            price_prediction_confidence=0.78,
            signal_probability=0.72,
            anomaly_score=0.1,
        )

        result = decision.to_dict()

        assert result["action"] == "buy"
        assert result["item_name"] == "Test Item"
        assert result["confidence"] == 0.85


class TestItemAnalysis:
    """Tests for ItemAnalysis dataclass."""

    def test_item_analysis_creation(self):
        """Test creating an ItemAnalysis."""
        from src.ml.smart_recommendations import RecommendationType

        analysis = ItemAnalysis(
            item_name="AWP | Asiimov (Field-Tested)",
            item_id="xyz789",
            game="csgo",
            current_price=25.0,
            predicted_price_1h=25.5,
            predicted_price_24h=27.0,
            predicted_price_7d=30.0,
            price_confidence=0.75,
            signal="buy",
            signal_probability=0.68,
            actual_discount=18.0,
            ml_threshold=15.0,
            is_undervalued=True,
            is_anomaly=False,
            anomaly_score=0.05,
            anomaly_reason=None,
            risk_level=RiskLevel.LOW,
            risk_factors=["Low volatility"],
            recommendation=RecommendationType.BUY,
            recommendation_reason="Price below ML threshold",
        )

        assert analysis.item_name == "AWP | Asiimov (Field-Tested)"
        assert analysis.is_undervalued is True
        assert analysis.ml_threshold == 15.0


class TestGlobalCoordinator:
    """Tests for global coordinator instance."""

    def setup_method(self):
        """Reset global coordinator before each test."""
        reset_Algo_coordinator()

    def test_get_Algo_coordinator(self):
        """Test getting global coordinator."""
        coordinator = get_Algo_coordinator()

        assert coordinator is not None
        assert isinstance(coordinator, AlgoCoordinator)

    def test_get_Algo_coordinator_returns_same_instance(self):
        """Test that get_Algo_coordinator returns same instance."""
        coordinator1 = get_Algo_coordinator()
        coordinator2 = get_Algo_coordinator()

        assert coordinator1 is coordinator2

    def test_reset_Algo_coordinator(self):
        """Test resetting global coordinator."""
        coordinator1 = get_Algo_coordinator()
        reset_Algo_coordinator()
        coordinator2 = get_Algo_coordinator()

        assert coordinator1 is not coordinator2


class TestMakeDecision:
    """Tests for make_decision method."""

    @pytest.fixture
    def coordinator(self):
        """Create a coordinator for testing."""
        return AlgoCoordinator(user_balance=100.0)

    @pytest.fixture
    def sample_item(self):
        """Sample item data for testing."""
        return {
            "title": "AK-47 | Redline (Field-Tested)",
            "itemId": "item123",
            "gameId": "csgo",
            "price": {"USD": 1000},  # $10.00
            "suggestedPrice": {"USD": 1200},  # $12.00 (16.7% discount)
            "priceHistory": [9.5, 9.8, 10.0, 10.2, 9.9, 10.1, 10.0] * 5,
        }

    @pytest.mark.asyncio
    async def test_make_decision_returns_trade_decision(self, coordinator, sample_item):
        """Test that make_decision returns a TradeDecision."""
        decision = awAlgot coordinator.make_decision(sample_item)

        assert isinstance(decision, TradeDecision)
        assert decision.item_name == "AK-47 | Redline (Field-Tested)"
        assert decision.game == "csgo"

    @pytest.mark.asyncio
    async def test_make_decision_sets_correct_prices(self, coordinator, sample_item):
        """Test that prices are extracted correctly."""
        decision = awAlgot coordinator.make_decision(sample_item)

        assert decision.current_price == 10.0  # 1000 cents = $10.00

    @pytest.mark.asyncio
    async def test_make_decision_requires_confirmation_in_manual_mode(
        self, coordinator, sample_item
    ):
        """Test that manual mode always requires confirmation."""
        coordinator.set_autonomy_level(AutonomyLevel.MANUAL)

        decision = awAlgot coordinator.make_decision(sample_item)

        # Non-hold/skip actions should require confirmation
        if decision.action not in {TradeAction.HOLD, TradeAction.SKIP}:
            assert decision.requires_confirmation is True


class TestAnalyzeItem:
    """Tests for analyze_item method."""

    @pytest.fixture
    def coordinator(self):
        """Create a coordinator for testing."""
        return AlgoCoordinator(user_balance=100.0)

    @pytest.fixture
    def sample_item(self):
        """Sample item data for testing."""
        return {
            "title": "M4A4 | Howl (Field-Tested)",
            "itemId": "howl123",
            "gameId": "csgo",
            "price": {"USD": 50000},  # $500.00
            "suggestedPrice": {"USD": 60000},  # $600.00
            "priceHistory": [480, 490, 500, 510, 505, 495, 500] * 5,
        }

    @pytest.mark.asyncio
    async def test_analyze_item_returns_item_analysis(self, coordinator, sample_item):
        """Test that analyze_item returns ItemAnalysis."""
        analysis = awAlgot coordinator.analyze_item(sample_item)

        assert isinstance(analysis, ItemAnalysis)
        assert analysis.item_name == "M4A4 | Howl (Field-Tested)"

    @pytest.mark.asyncio
    async def test_analyze_item_calculates_discount(self, coordinator, sample_item):
        """Test that discount is calculated correctly."""
        analysis = awAlgot coordinator.analyze_item(sample_item)

        # Expected discount: (600 - 500) / 600 = 16.7%
        expected_discount = ((600 - 500) / 600) * 100
        assert abs(analysis.actual_discount - expected_discount) < 0.1

    @pytest.mark.asyncio
    async def test_analyze_item_without_Model(self, coordinator, sample_item):
        """Test analysis without Model."""
        analysis = awAlgot coordinator.analyze_item(sample_item, include_Model=False)

        assert analysis.Model_analysis is None


class TestStatistics:
    """Tests for statistics tracking."""

    def test_get_statistics(self):
        """Test getting statistics."""
        coordinator = AlgoCoordinator()

        stats = coordinator.get_statistics()

        assert "decisions_made" in stats
        assert "trades_executed" in stats
        assert "win_rate" in stats
        assert "autonomy_level" in stats
        assert stats["autonomy_level"] == "manual"


class TestModelWeights:
    """Tests for model weight configuration."""

    def test_model_weights_sum_to_one(self):
        """Test that default model weights sum to approximately 1.0."""
        total = sum(AlgoCoordinator.DEFAULT_MODEL_WEIGHTS.values())

        assert abs(total - 1.0) < 0.01

    def test_model_weights_all_positive(self):
        """Test that all default model weights are positive."""
        for weight in AlgoCoordinator.DEFAULT_MODEL_WEIGHTS.values():
            assert weight > 0

    def test_custom_model_weights(self):
        """Test that custom model weights can be set."""
        custom_weights = {
            "price_prediction": 0.40,
            "signal_classification": 0.20,
            "discount_threshold": 0.20,
            "anomaly_check": 0.10,
            "balance_fit": 0.10,
        }
        Algo = AlgoCoordinator(model_weights=custom_weights)
        assert Algo.model_weights["price_prediction"] == 0.40

    def test_model_weights_normalization(self):
        """Test that non-normalized weights get normalized."""
        non_normalized = {
            "price_prediction": 0.60,  # Sum > 1.0
            "signal_classification": 0.50,
            "discount_threshold": 0.40,
            "anomaly_check": 0.30,
            "balance_fit": 0.20,
        }
        Algo = AlgoCoordinator(model_weights=non_normalized)
        total = sum(Algo.model_weights.values())
        assert abs(total - 1.0) < 0.01


class TestDriftDetection:
    """Tests for concept drift detection."""

    def test_get_drift_status_initial(self):
        """Test initial drift status."""
        Algo = AlgoCoordinator()
        status = Algo.get_drift_status()

        assert status["drift_detected"] is False
        assert status["recent_accuracy"] == 0.0
        assert status["samples_tracked"] == 0

    def test_drift_status_updates_with_outcomes(self):
        """Test drift status updates with trade outcomes."""
        Algo = AlgoCoordinator()

        # Create a test decision
        decision = TradeDecision(
            action=TradeAction.BUY,
            item_name="Test",
            item_id="test123",
            game="csgo",
            current_price=10.0,
            predicted_price=12.0,
            expected_profit=2.0,
            expected_profit_percent=20.0,
            confidence=0.8,
            risk_level=RiskLevel.LOW,
            discount_threshold_used=5.0,
            price_prediction_confidence=0.8,
            signal_probability=0.7,
            anomaly_score=0.1,
        )

        # Add successful outcomes
        for _ in range(10):
            Algo.add_trade_outcome(decision, 2.0, True)

        status = Algo.get_drift_status()
        assert status["samples_tracked"] == 10
        assert status["recent_accuracy"] == 1.0

    def test_model_version_in_stats(self):
        """Test that model version is included in statistics."""
        Algo = AlgoCoordinator()
        stats = Algo.get_statistics()

        assert "model_version" in stats
        assert stats["model_version"] == AlgoCoordinator.MODEL_VERSION


class TestTradeAction:
    """Tests for TradeAction enum."""

    def test_all_actions_exist(self):
        """Test that all expected actions exist."""
        actions = [a.value for a in TradeAction]

        assert "buy" in actions
        assert "sell" in actions
        assert "create_target" in actions
        assert "hold" in actions
        assert "skip" in actions


class TestAddTradeOutcome:
    """Tests for add_trade_outcome method."""

    def test_add_trade_outcome_updates_stats(self):
        """Test that trade outcome updates statistics."""
        coordinator = AlgoCoordinator()

        decision = TradeDecision(
            action=TradeAction.BUY,
            item_name="Test Item",
            item_id="test123",
            game="csgo",
            current_price=10.0,
            predicted_price=12.0,
            expected_profit=2.0,
            expected_profit_percent=20.0,
            confidence=0.85,
            risk_level=RiskLevel.MEDIUM,
            discount_threshold_used=15.0,
            price_prediction_confidence=0.78,
            signal_probability=0.72,
            anomaly_score=0.1,
        )

        coordinator.add_trade_outcome(
            decision=decision,
            actual_profit=1.5,
            was_profitable=True,
        )

        stats = coordinator.get_statistics()
        assert stats["successful_trades"] == 1
        assert stats["total_profit"] == 1.5
