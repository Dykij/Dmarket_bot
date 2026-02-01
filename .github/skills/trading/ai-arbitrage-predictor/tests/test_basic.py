"""Tests for AI Arbitrage Predictor.

Tests Phase 2 implementation of AI-powered arbitrage prediction.
"""

import pytest

from src.dmarket.ai_arbitrage_predictor import (
    AIArbitragePredictor,
    ArbitrageOpportunity,
    create_ai_arbitrage_predictor,
)


class TestAIArbitragePredictor:
    """Tests for AIArbitragePredictor class."""

    def test_initialization(self):
        """Test predictor initialization."""
        predictor = AIArbitragePredictor()

        assert predictor is not None
        assert predictor.predictor is not None
        assert predictor.feature_extractor is not None

    def test_factory_function(self):
        """Test factory function creates valid predictor."""
        predictor = create_ai_arbitrage_predictor()

        assert isinstance(predictor, AIArbitragePredictor)

    @pytest.mark.asyncio
    async def test_predict_best_opportunities_empty_list(self):
        """Test prediction with empty item list."""
        predictor = AIArbitragePredictor()

        opportunities = await predictor.predict_best_opportunities(
            items=[],
            current_balance=100.0,
            risk_level="medium",
        )

        assert opportunities == []

    @pytest.mark.asyncio
    async def test_predict_best_opportunities_with_valid_items(self):
        """Test prediction with valid arbitrage items."""
        predictor = AIArbitragePredictor()

        # Mock items with arbitrage opportunity
        items = [
            {
                "title": "AK-47 | Redline (FT)",
                "itemId": "item_123",
                "gameId": "csgo",
                "price": {"USD": 1000},  # $10.00
                "suggestedPrice": {"USD": 1500},  # $15.00 (good arbitrage)
            },
            {
                "title": "AWP | Dragon Lore (FN)",
                "itemId": "item_456",
                "gameId": "csgo",
                "price": {"USD": 10000},  # $100.00 (too expensive)
                "suggestedPrice": {"USD": 12000},
            },
        ]

        opportunities = await predictor.predict_best_opportunities(
            items=items,
            current_balance=50.0,  # Can only afford first item
            risk_level="medium",
        )

        # Should find 1 opportunity (first item affordable)
        assert len(opportunities) == 1
        assert opportunities[0].title == "AK-47 | Redline (FT)"
        assert opportunities[0].current_price == 10.0
        assert opportunities[0].predicted_profit > 0

    @pytest.mark.asyncio
    async def test_predict_with_invalid_risk_level(self):
        """Test prediction with invalid risk level raises error."""
        predictor = AIArbitragePredictor()

        with pytest.raises(ValueError, match="Invalid risk_level"):
            await predictor.predict_best_opportunities(
                items=[],
                current_balance=100.0,
                risk_level="invalid",
            )

    @pytest.mark.asyncio
    async def test_predict_filters_unprofitable_items(self):
        """Test that unprofitable items are filtered out."""
        predictor = AIArbitragePredictor()

        # Item with no profit (suggested <= current)
        items = [
            {
                "title": "Bad Item",
                "itemId": "item_bad",
                "gameId": "csgo",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 900},  # Lower than current!
            }
        ]

        opportunities = await predictor.predict_best_opportunities(
            items=items,
            current_balance=100.0,
            risk_level="medium",
        )

        assert len(opportunities) == 0

    @pytest.mark.asyncio
    async def test_risk_levels_affect_filtering(self):
        """Test that different risk levels filter differently."""
        predictor = AIArbitragePredictor()

        # Item with moderate confidence
        items = [
            {
                "title": "Moderate Item",
                "itemId": "item_mod",
                "gameId": "csgo",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1100},  # Small margin
            }
        ]

        # Low risk should filter more aggressively
        low_risk_opps = await predictor.predict_best_opportunities(
            items=items,
            current_balance=100.0,
            risk_level="low",
        )

        # High risk should be more permissive
        high_risk_opps = await predictor.predict_best_opportunities(
            items=items,
            current_balance=100.0,
            risk_level="high",
        )

        # High risk should find same or more opportunities
        assert len(high_risk_opps) >= len(low_risk_opps)

    def test_get_price_usd_converts_cents(self):
        """Test price conversion from cents to USD."""
        predictor = AIArbitragePredictor()

        item = {"price": {"USD": 1234}}

        price_usd = predictor._get_price_usd(item)

        assert price_usd == 12.34

    def test_get_price_usd_handles_missing_data(self):
        """Test price conversion with missing data."""
        predictor = AIArbitragePredictor()

        item = {}

        price_usd = predictor._get_price_usd(item)

        assert price_usd == 0.0

    def test_calculate_risk_returns_valid_range(self):
        """Test risk calculation returns 0-100."""
        predictor = AIArbitragePredictor()

        item = {"title": "Test"}

        # Test with different confidences
        low_confidence_risk = predictor._calculate_risk(item, 0.3, "medium")
        high_confidence_risk = predictor._calculate_risk(item, 0.9, "medium")

        # Risk should be in valid range
        assert 0 <= low_confidence_risk <= 100
        assert 0 <= high_confidence_risk <= 100

        # Lower confidence should have higher risk
        assert low_confidence_risk > high_confidence_risk

    def test_map_game_id_handles_all_games(self):
        """Test game ID mapping for all supported games."""
        predictor = AIArbitragePredictor()

        from src.ml import GameType

        assert predictor._map_game_id("csgo") == GameType.CS2
        assert predictor._map_game_id("cs2") == GameType.CS2
        assert predictor._map_game_id("dota2") == GameType.DOTA2
        assert predictor._map_game_id("tf2") == GameType.TF2
        assert predictor._map_game_id("rust") == GameType.RUST

    def test_get_min_confidence_for_risk_levels(self):
        """Test minimum confidence thresholds for risk levels."""
        predictor = AIArbitragePredictor()

        low_threshold = predictor._get_min_confidence("low")
        medium_threshold = predictor._get_min_confidence("medium")
        high_threshold = predictor._get_min_confidence("high")

        # Low risk should have highest threshold
        assert low_threshold > medium_threshold > high_threshold

        # All should be between 0 and 1
        assert 0 < low_threshold < 1
        assert 0 < medium_threshold < 1
        assert 0 < high_threshold < 1


class TestArbitrageOpportunity:
    """Tests for ArbitrageOpportunity dataclass."""

    def test_opportunity_creation(self):
        """Test creating arbitrage opportunity."""
        opp = ArbitrageOpportunity(
            title="Test Item",
            item_id="123",
            game_id="csgo",
            current_price=10.0,
            suggested_price=15.0,
            predicted_profit=4.0,
            confidence=0.85,
            risk_score=25.0,
            roi_percent=40.0,
            features={"volatility": 0.1},
        )

        assert opp.title == "Test Item"
        assert opp.confidence == 0.85
        assert opp.predicted_profit == 4.0
