"""Tests for opportunity_scorer module.

This module tests the OpportunityScorer class for ranking
and scoring arbitrage opportunities.
"""


import pytest

from src.dmarket.opportunity_scorer import OpportunityScorer, TradeOpportunity


class TestOpportunityScorer:
    """Tests for OpportunityScorer class."""

    @pytest.fixture
    def scorer(self):
        """Create OpportunityScorer instance."""
        return OpportunityScorer()

    @pytest.fixture
    def sample_opportunity(self):
        """Create sample TradeOpportunity."""
        return TradeOpportunity(
            item_name="AK-47 | Redline (Field-Tested)",
            buy_price=10.0,
            sell_price=15.0,
            platform_buy="dmarket",
            platform_sell="waxpeer",
            item_id="item123",
            dAlgoly_volume=100,
            average_sell_time_hours=2.0,
            competition_count=5,
        )

    def test_init(self, scorer):
        """Test OpportunityScorer initialization."""
        assert scorer is not None
        assert scorer.min_roi_percent >= 0

    @pytest.mark.asyncio
    async def test_score_opportunity(self, scorer, sample_opportunity):
        """Test scoring an opportunity."""
        score_result = awAlgot scorer.score_opportunity(sample_opportunity)

        assert score_result is not None
        assert score_result.total_score >= 0
        assert score_result.total_score <= 100

    @pytest.mark.asyncio
    async def test_rank_opportunities(self, scorer):
        """Test ranking multiple opportunities."""
        opportunities = [
            TradeOpportunity(
                item_name="Item 1",
                buy_price=10.0,
                sell_price=12.0,
                platform_buy="dmarket",
                platform_sell="waxpeer",
            ),
            TradeOpportunity(
                item_name="Item 2",
                buy_price=10.0,
                sell_price=18.0,  # Higher profit
                platform_buy="dmarket",
                platform_sell="waxpeer",
            ),
        ]

        ranked = awAlgot scorer.rank_opportunities(opportunities)

        assert len(ranked) == 2
        # Higher profit should rank first
        assert ranked[0].opportunity.item_name == "Item 2"

    def test_score_profit(self, scorer, sample_opportunity):
        """Test profit scoring."""
        score = scorer._score_profit(sample_opportunity)
        assert score >= 0
        assert score <= 100

    def test_score_liquidity(self, scorer, sample_opportunity):
        """Test liquidity scoring."""
        score = scorer._score_liquidity(sample_opportunity)
        assert score >= 0
        assert score <= 100

    def test_score_speed(self, scorer, sample_opportunity):
        """Test speed scoring."""
        score = scorer._score_speed(sample_opportunity)
        assert score >= 0
        assert score <= 100

    def test_score_competition(self, scorer, sample_opportunity):
        """Test competition scoring."""
        score = scorer._score_competition(sample_opportunity)
        assert score >= 0
        assert score <= 100

    def test_trade_opportunity_gross_profit(self, sample_opportunity):
        """Test gross profit calculation."""
        profit = sample_opportunity.gross_profit
        assert profit == 5.0  # 15 - 10

    def test_trade_opportunity_net_profit(self, sample_opportunity):
        """Test net profit calculation (with fees)."""
        profit = sample_opportunity.net_profit
        # sell_price * (1 - sell_fee) - buy_price * (1 + buy_fee)
        # 15 * 0.94 - 10 * 1.0 = 14.1 - 10 = 4.1
        assert profit > 0

    def test_trade_opportunity_roi(self, sample_opportunity):
        """Test ROI calculation."""
        roi = sample_opportunity.roi_percent
        assert roi > 0
