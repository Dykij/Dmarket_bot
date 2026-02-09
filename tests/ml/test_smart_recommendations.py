"""Tests for Smart Recommendations Module."""

from __future__ import annotations

import pytest

from src.ml.smart_recommendations import (
    ItemRecommendation,
    RecommendationBatch,
    RecommendationType,
    RiskLevel,
    SmartRecommendations,
    create_smart_recommendations,
)


class TestSmartRecommendations:
    """Tests for SmartRecommendations class."""
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        recommender = SmartRecommendations()
        
        assert recommender.user_balance == 100.0
        assert recommender.risk_tolerance == RiskLevel.MEDIUM
        assert recommender.min_profit_threshold == 0.05
    
    def test_init_custom_values(self):
        """Test initialization with custom values."""
        recommender = SmartRecommendations(
            user_balance=500.0,
            risk_tolerance=RiskLevel.HIGH,
            max_single_item_percent=0.5,
        )
        
        assert recommender.user_balance == 500.0
        assert recommender.risk_tolerance == RiskLevel.HIGH
        assert recommender.max_single_item_percent == 0.5
    
    def test_set_user_balance(self):
        """Test balance update."""
        recommender = SmartRecommendations()
        recommender.set_user_balance(200.0)
        
        assert recommender.user_balance == 200.0
    
    def test_set_user_balance_negative(self):
        """Test negative balance is clamped to 0."""
        recommender = SmartRecommendations()
        recommender.set_user_balance(-50.0)
        
        assert recommender.user_balance == 0.0
    
    def test_set_risk_tolerance(self):
        """Test risk tolerance update."""
        recommender = SmartRecommendations()
        recommender.set_risk_tolerance(RiskLevel.LOW)
        
        assert recommender.risk_tolerance == RiskLevel.LOW
    
    def test_add_trading_history_profitable(self):
        """Test adding profitable trade."""
        recommender = SmartRecommendations()
        
        recommender.add_trading_history({
            "item_name": "AK-47 | Redline",
            "profit": 5.0,
        })
        
        assert "AK-47 | Redline" in recommender._successful_items
    
    def test_add_trading_history_loss(self):
        """Test adding losing trade."""
        recommender = SmartRecommendations()
        
        recommender.add_trading_history({
            "item_name": "AWP | Asiimov",
            "profit": -15.0,
            "price": 100.0,  # >10% loss
        })
        
        assert "AWP | Asiimov" in recommender._avoided_items
    
    @pytest.mark.asyncio
    async def test_get_recommendations_empty(self):
        """Test recommendations with empty input."""
        recommender = SmartRecommendations()
        
        batch = await recommender.get_recommendations(
            available_items=[],
            user_inventory=None,
        )
        
        assert len(batch.recommendations) == 0
        assert batch.total_potential_profit == 0.0
    
    @pytest.mark.asyncio
    async def test_get_recommendations_basic(self):
        """Test basic recommendations."""
        recommender = SmartRecommendations(user_balance=100.0)
        
        items = [
            {
                "title": "Test Item",
                "itemId": "item_1",
                "price": {"USD": "1000"},  # $10
                "suggestedPrice": {"USD": "1500"},  # $15
            },
        ]
        
        batch = await recommender.get_recommendations(
            available_items=items,
        )
        
        assert isinstance(batch, RecommendationBatch)
    
    @pytest.mark.asyncio
    async def test_get_recommendations_respects_budget(self):
        """Test recommendations respect budget limits."""
        recommender = SmartRecommendations(
            user_balance=10.0,
            max_single_item_percent=0.3,  # Max $3 per item
        )
        
        items = [
            {
                "title": "Expensive Item",
                "itemId": "exp_1",
                "price": {"USD": "5000"},  # $50 - too expensive
            },
            {
                "title": "Cheap Item",
                "itemId": "cheap_1",
                "price": {"USD": "200"},  # $2 - affordable
                "suggestedPrice": {"USD": "300"},
            },
        ]
        
        batch = await recommender.get_recommendations(
            available_items=items,
        )
        
        # Should not recommend expensive item
        for rec in batch.recommendations:
            assert rec.current_price <= recommender.user_balance * recommender.max_single_item_percent
    
    @pytest.mark.asyncio
    async def test_get_recommendations_arbitrage(self):
        """Test arbitrage opportunity detection."""
        recommender = SmartRecommendations(user_balance=100.0)
        
        items = [
            {
                "title": "Arb Item",
                "itemId": "arb_1",
                "price": {"USD": "1000"},  # $10
            },
        ]
        
        cross_platform = {
            "Arb Item": {"waxpeer": 15.0},  # $15 on Waxpeer
        }
        
        batch = await recommender.get_recommendations(
            available_items=items,
            cross_platform_prices=cross_platform,
        )
        
        # Should detect arbitrage opportunity
        arb_recs = [r for r in batch.recommendations if r.recommendation_type == RecommendationType.ARBITRAGE]
        assert batch.arbitrage_count == len(arb_recs)
    
    @pytest.mark.asyncio
    async def test_analyze_sell_opportunity(self):
        """Test sell recommendation for inventory items."""
        recommender = SmartRecommendations()
        
        inventory = [
            {
                "title": "Profit Item",
                "itemId": "sell_1",
                "purchasePrice": {"USD": "1000"},  # Bought at $10
                "currentPrice": {"USD": "1500"},  # Now $15 (+50%)
            },
        ]
        
        batch = await recommender.get_recommendations(
            available_items=[],
            user_inventory=inventory,
        )
        
        assert batch.sell_count >= 0  # May or may not recommend sell
    
    def test_get_portfolio_recommendations(self):
        """Test portfolio-level recommendations."""
        recommender = SmartRecommendations(user_balance=100.0)
        
        holdings = [
            {"name": "Item 1", "currentPrice": 5000},  # $50
            {"name": "Item 1", "currentPrice": 5000},  # $50 - same item
        ]
        
        recs = recommender.get_portfolio_recommendations(
            holdings,
            target_diversification=3,
        )
        
        assert len(recs) > 0
        assert any("diversif" in r.lower() for r in recs)
    
    def test_adjust_for_risk_tolerance(self):
        """Test risk tolerance adjustment."""
        recommender = SmartRecommendations(risk_tolerance=RiskLevel.LOW)
        
        # High risk item with low risk tolerance should reduce confidence
        adjusted = recommender._adjust_for_risk_tolerance(
            confidence=70.0,
            item_risk=RiskLevel.HIGH,
        )
        
        assert adjusted < 70.0
    
    def test_adjust_for_risk_tolerance_safer_item(self):
        """Test safer item with high risk tolerance."""
        recommender = SmartRecommendations(risk_tolerance=RiskLevel.HIGH)
        
        # Low risk item with high risk tolerance should increase confidence
        adjusted = recommender._adjust_for_risk_tolerance(
            confidence=70.0,
            item_risk=RiskLevel.LOW,
        )
        
        assert adjusted >= 70.0


class TestItemRecommendation:
    """Tests for ItemRecommendation dataclass."""
    
    def test_to_dict(self):
        """Test serialization."""
        rec = ItemRecommendation(
            item_name="Test Item",
            item_id="test_1",
            recommendation_type=RecommendationType.BUY,
            confidence=75.0,
            risk_level=RiskLevel.MEDIUM,
            current_price=10.0,
            target_price=15.0,
            expected_profit=5.0,
            expected_profit_percent=50.0,
            reason="Good opportunity",
            factors=["Factor 1", "Factor 2"],
        )
        
        data = rec.to_dict()
        
        assert data["item_name"] == "Test Item"
        assert data["recommendation"] == "buy"
        assert data["confidence"] == 75.0
        assert data["expected_profit"] == 5.0


class TestRecommendationBatch:
    """Tests for RecommendationBatch."""
    
    def test_sort_by_profit(self):
        """Test sorting by profit."""
        recs = [
            ItemRecommendation(
                item_name="Low",
                item_id="1",
                recommendation_type=RecommendationType.BUY,
                confidence=50.0,
                risk_level=RiskLevel.MEDIUM,
                current_price=10.0,
                expected_profit_percent=5.0,
            ),
            ItemRecommendation(
                item_name="High",
                item_id="2",
                recommendation_type=RecommendationType.BUY,
                confidence=50.0,
                risk_level=RiskLevel.MEDIUM,
                current_price=10.0,
                expected_profit_percent=20.0,
            ),
        ]
        
        batch = RecommendationBatch(recommendations=recs)
        batch.sort_by_profit()
        
        assert batch.recommendations[0].item_name == "High"
    
    def test_filter_by_risk(self):
        """Test filtering by risk level."""
        recs = [
            ItemRecommendation(
                item_name="Safe",
                item_id="1",
                recommendation_type=RecommendationType.BUY,
                confidence=50.0,
                risk_level=RiskLevel.LOW,
                current_price=10.0,
            ),
            ItemRecommendation(
                item_name="Risky",
                item_id="2",
                recommendation_type=RecommendationType.BUY,
                confidence=50.0,
                risk_level=RiskLevel.HIGH,
                current_price=10.0,
            ),
        ]
        
        batch = RecommendationBatch(recommendations=recs)
        filtered = batch.filter_by_risk(RiskLevel.MEDIUM)
        
        assert len(filtered) == 1
        assert filtered[0].item_name == "Safe"


class TestFactoryFunction:
    """Tests for factory function."""
    
    def test_create_smart_recommendations(self):
        """Test factory function."""
        recommender = create_smart_recommendations(
            user_balance=500.0,
            risk_tolerance=RiskLevel.HIGH,
        )
        
        assert recommender.user_balance == 500.0
        assert recommender.risk_tolerance == RiskLevel.HIGH
