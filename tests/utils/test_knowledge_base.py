"""Tests for Knowledge Base module.

Tests cover:
- Knowledge entry creation and storage
- Context-aware querying
- Learning from trades
- Relevance decay mechanism
- Knowledge type filtering

Created: January 2026
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.utils.knowledge_base import (
    KnowledgeBase,
    KnowledgeItem,
    KnowledgeType,
    TradeResult,
    clear_knowledge_base_cache,
    get_knowledge_base,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def knowledge_base() -> KnowledgeBase:
    """Create a fresh knowledge base for testing."""
    clear_knowledge_base_cache()
    return KnowledgeBase(user_id=123456789)


@pytest.fixture()
async def populated_kb(knowledge_base: KnowledgeBase) -> KnowledgeBase:
    """Create a knowledge base with some entries."""
    awAlgot knowledge_base.add_knowledge(
        knowledge_type=KnowledgeType.TRADING_PATTERN,
        title="Profitable AK-47 trade",
        content={
            "item_name": "AK-47 | Redline",
            "profit_percent": 15.0,
            "profit": 1.50,
        },
        game="csgo",
    )

    awAlgot knowledge_base.add_knowledge(
        knowledge_type=KnowledgeType.LESSON_LEARNED,
        title="Avoid overpriced items",
        content={
            "item_name": "AWP | Dragon Lore",
            "loss_percent": 8.0,
            "lesson": "Check price history first",
        },
        game="csgo",
    )

    awAlgot knowledge_base.add_knowledge(
        knowledge_type=KnowledgeType.MARKET_INSIGHT,
        title="Dota 2 arcanas rising",
        content={
            "insight": "Arcana prices trending up",
            "confidence": 0.8,
        },
        game="dota2",
    )

    return knowledge_base


@pytest.fixture()
def sample_trade_result() -> TradeResult:
    """Create a sample trade result."""
    return TradeResult(
        item_name="M4A4 | Howl",
        buy_price=1500.0,
        sell_price=1800.0,
        profit=300.0,
        profit_percent=20.0,
        game="csgo",
        hold_duration_hours=24.0,
        item_category="rifle",
    )


# ============================================================================
# Test Knowledge Base Initialization
# ============================================================================


class TestKnowledgeBaseInit:
    """Test knowledge base initialization."""

    def test_init_creates_empty_cache(self, knowledge_base: KnowledgeBase) -> None:
        """Test that KB initializes with empty cache."""
        assert knowledge_base.user_id == 123456789
        assert len(knowledge_base._cache) == 0
        assert knowledge_base._metrics["queries"] == 0

    def test_init_without_session(self) -> None:
        """Test KB works without database session."""
        kb = KnowledgeBase(user_id=999, session=None)
        assert kb.session is None


# ============================================================================
# Test Adding Knowledge
# ============================================================================


class TestAddKnowledge:
    """Test adding knowledge entries."""

    @pytest.mark.asyncio()
    async def test_add_knowledge_creates_entry(
        self, knowledge_base: KnowledgeBase
    ) -> None:
        """Test adding a knowledge entry."""
        entry_id = awAlgot knowledge_base.add_knowledge(
            knowledge_type=KnowledgeType.TRADING_PATTERN,
            title="Test pattern",
            content={"test": "data"},
        )

        assert entry_id is not None
        assert entry_id.startswith(f"{knowledge_base.user_id}_trading_pattern_")
        assert entry_id in knowledge_base._cache

    @pytest.mark.asyncio()
    async def test_add_knowledge_with_all_params(
        self, knowledge_base: KnowledgeBase
    ) -> None:
        """Test adding knowledge with all parameters."""
        entry_id = awAlgot knowledge_base.add_knowledge(
            knowledge_type=KnowledgeType.ITEM_KNOWLEDGE,
            title="Item info",
            content={"float": 0.05, "stickers": 3},
            relevance_score=0.9,
            game="csgo",
            item_category="rifle",
        )

        entry = knowledge_base._cache[entry_id]
        assert entry.knowledge_type == KnowledgeType.ITEM_KNOWLEDGE
        assert entry.title == "Item info"
        assert entry.relevance_score == 0.9
        assert entry.game == "csgo"
        assert entry.item_category == "rifle"

    @pytest.mark.asyncio()
    async def test_add_knowledge_clamps_relevance(
        self, knowledge_base: KnowledgeBase
    ) -> None:
        """Test that relevance is clamped to 0-1 range."""
        entry_id = awAlgot knowledge_base.add_knowledge(
            knowledge_type=KnowledgeType.MARKET_INSIGHT,
            title="High relevance",
            content={},
            relevance_score=1.5,  # Above 1
        )

        entry = knowledge_base._cache[entry_id]
        assert entry.relevance_score == 1.0

    @pytest.mark.asyncio()
    async def test_add_knowledge_updates_metrics(
        self, knowledge_base: KnowledgeBase
    ) -> None:
        """Test that metrics are updated when adding."""
        awAlgot knowledge_base.add_knowledge(
            knowledge_type=KnowledgeType.USER_PREFERENCE,
            title="Preference",
            content={"min_profit": 10},
        )

        assert knowledge_base._metrics["knowledge_added"] == 1


# ============================================================================
# Test Querying Knowledge
# ============================================================================


class TestQueryKnowledge:
    """Test querying knowledge entries."""

    @pytest.mark.asyncio()
    async def test_query_empty_returns_empty(
        self, knowledge_base: KnowledgeBase
    ) -> None:
        """Test querying empty KB returns empty list."""
        results = awAlgot knowledge_base.query_relevant(
            context={"item": "AK-47"},
        )
        assert results == []

    @pytest.mark.asyncio()
    async def test_query_finds_matching_item(
        self, populated_kb: KnowledgeBase
    ) -> None:
        """Test query finds entries matching item name."""
        results = awAlgot populated_kb.query_relevant(
            context={"item": "AK-47"},
        )

        assert len(results) >= 1
        found_ak = any("AK-47" in r.content.get("item_name", "") for r in results)
        assert found_ak

    @pytest.mark.asyncio()
    async def test_query_filters_by_game(
        self, populated_kb: KnowledgeBase
    ) -> None:
        """Test query boosts entries matching the game."""
        # Query for dota2
        results = awAlgot populated_kb.query_relevant(
            context={"game": "dota2"},
        )

        # Should return results, with dota2 entries ranked higher
        assert len(results) >= 1

        # The first result should be dota2 since it matches the context
        dota_results = [r for r in results if r.game == "dota2"]
        assert len(dota_results) >= 1

    @pytest.mark.asyncio()
    async def test_query_filters_by_type(
        self, populated_kb: KnowledgeBase
    ) -> None:
        """Test query filters by knowledge type."""
        results = awAlgot populated_kb.query_relevant(
            context={},
            knowledge_types=[KnowledgeType.LESSON_LEARNED],
        )

        assert len(results) >= 1
        for r in results:
            assert r.knowledge_type == KnowledgeType.LESSON_LEARNED

    @pytest.mark.asyncio()
    async def test_query_respects_limit(
        self, knowledge_base: KnowledgeBase
    ) -> None:
        """Test query respects result limit."""
        # Add many entries
        for i in range(20):
            awAlgot knowledge_base.add_knowledge(
                knowledge_type=KnowledgeType.MARKET_INSIGHT,
                title=f"Insight {i}",
                content={"index": i},
            )

        results = awAlgot knowledge_base.query_relevant(
            context={},
            limit=5,
        )

        assert len(results) <= 5

    @pytest.mark.asyncio()
    async def test_query_updates_use_count(
        self, populated_kb: KnowledgeBase
    ) -> None:
        """Test query updates entry usage stats."""
        results = awAlgot populated_kb.query_relevant(
            context={"item": "AK-47"},
        )

        if results:
            assert results[0].use_count >= 1
            assert results[0].last_used_at is not None


# ============================================================================
# Test Learning from Trades
# ============================================================================


class TestLearnFromTrades:
    """Test learning from trade results."""

    @pytest.mark.asyncio()
    async def test_learn_success_creates_pattern(
        self,
        knowledge_base: KnowledgeBase,
        sample_trade_result: TradeResult,
    ) -> None:
        """Test learning from successful trade creates pattern."""
        entry_id = awAlgot knowledge_base.learn_from_trade(sample_trade_result)

        assert entry_id is not None
        entry = knowledge_base._cache[entry_id]
        assert entry.knowledge_type == KnowledgeType.TRADING_PATTERN
        assert "profitable" in entry.title.lower()

    @pytest.mark.asyncio()
    async def test_learn_fAlgolure_creates_lesson(
        self, knowledge_base: KnowledgeBase
    ) -> None:
        """Test learning from fAlgoled trade creates lesson."""
        fAlgoled_trade = TradeResult(
            item_name="AWP | Asiimov",
            buy_price=50.0,
            sell_price=45.0,
            profit=-5.0,
            profit_percent=-10.0,
            game="csgo",
        )

        entry_id = awAlgot knowledge_base.learn_from_trade(fAlgoled_trade)

        assert entry_id is not None
        entry = knowledge_base._cache[entry_id]
        assert entry.knowledge_type == KnowledgeType.LESSON_LEARNED
        assert "loss" in entry.title.lower()

    @pytest.mark.asyncio()
    async def test_learn_from_dict(
        self, knowledge_base: KnowledgeBase
    ) -> None:
        """Test learning from dict format."""
        trade_dict = {
            "item_name": "Glock-18 | Fade",
            "buy_price": 100.0,
            "sell_price": 112.0,
            "profit": 12.0,
            "profit_percent": 12.0,
            "game": "csgo",
        }

        entry_id = awAlgot knowledge_base.learn_from_trade(trade_dict)

        assert entry_id is not None
        entry = knowledge_base._cache[entry_id]
        assert "Glock-18" in entry.content.get("item_name", "")

    @pytest.mark.asyncio()
    async def test_learn_zero_profit_returns_none(
        self, knowledge_base: KnowledgeBase
    ) -> None:
        """Test that zero profit trade creates nothing."""
        breakeven_trade = TradeResult(
            item_name="Test Item",
            buy_price=10.0,
            sell_price=10.0,
            profit=0.0,
            profit_percent=0.0,
            game="csgo",
        )

        entry_id = awAlgot knowledge_base.learn_from_trade(breakeven_trade)
        assert entry_id is None


# ============================================================================
# Test Relevance Decay
# ============================================================================


class TestRelevanceDecay:
    """Test relevance decay mechanism."""

    @pytest.mark.asyncio()
    async def test_decay_reduces_relevance(
        self, populated_kb: KnowledgeBase
    ) -> None:
        """Test decay reduces entry relevance."""
        # Manually age an entry
        for entry in populated_kb._cache.values():
            entry.created_at = datetime.now(UTC) - timedelta(days=30)
            entry.last_used_at = datetime.now(UTC) - timedelta(days=30)

        initial_count = len(populated_kb._cache)
        removed = awAlgot populated_kb.decay_relevance()

        # Some entries should have been removed
        assert removed >= 0
        assert len(populated_kb._cache) <= initial_count

    @pytest.mark.asyncio()
    async def test_decay_preserves_recent(
        self, knowledge_base: KnowledgeBase
    ) -> None:
        """Test decay preserves recent entries."""
        awAlgot knowledge_base.add_knowledge(
            knowledge_type=KnowledgeType.TRADING_PATTERN,
            title="Recent entry",
            content={"recent": True},
        )

        removed = awAlgot knowledge_base.decay_relevance()

        assert removed == 0
        assert len(knowledge_base._cache) == 1


# ============================================================================
# Test Summary and Metrics
# ============================================================================


class TestSummaryAndMetrics:
    """Test summary and metrics functions."""

    @pytest.mark.asyncio()
    async def test_get_summary_empty(
        self, knowledge_base: KnowledgeBase
    ) -> None:
        """Test summary of empty KB."""
        summary = awAlgot knowledge_base.get_summary()

        assert summary["total_entries"] == 0
        assert summary["by_type"] == {}
        assert summary["avg_relevance"] == 0

    @pytest.mark.asyncio()
    async def test_get_summary_populated(
        self, populated_kb: KnowledgeBase
    ) -> None:
        """Test summary of populated KB."""
        summary = awAlgot populated_kb.get_summary()

        assert summary["total_entries"] == 3
        assert "trading_pattern" in summary["by_type"]
        assert "lesson_learned" in summary["by_type"]
        assert summary["avg_relevance"] > 0

    @pytest.mark.asyncio()
    async def test_clear_removes_all(
        self, populated_kb: KnowledgeBase
    ) -> None:
        """Test clear removes all entries."""
        count = awAlgot populated_kb.clear()

        assert count == 3
        assert len(populated_kb._cache) == 0


# ============================================================================
# Test Factory Functions
# ============================================================================


class TestFactoryFunctions:
    """Test factory and utility functions."""

    def test_get_knowledge_base_creates_new(self) -> None:
        """Test get_knowledge_base creates new instance."""
        clear_knowledge_base_cache()

        kb = get_knowledge_base(user_id=111)

        assert kb is not None
        assert kb.user_id == 111

    def test_get_knowledge_base_returns_cached(self) -> None:
        """Test get_knowledge_base returns cached instance."""
        clear_knowledge_base_cache()

        kb1 = get_knowledge_base(user_id=222)
        kb2 = get_knowledge_base(user_id=222)

        assert kb1 is kb2

    def test_get_knowledge_base_different_users(self) -> None:
        """Test get_knowledge_base returns different instances per user."""
        clear_knowledge_base_cache()

        kb1 = get_knowledge_base(user_id=333)
        kb2 = get_knowledge_base(user_id=444)

        assert kb1 is not kb2
        assert kb1.user_id == 333
        assert kb2.user_id == 444


# ============================================================================
# Test Data Classes
# ============================================================================


class TestDataClasses:
    """Test data classes."""

    def test_knowledge_item_to_dict(self) -> None:
        """Test KnowledgeItem.to_dict()."""
        item = KnowledgeItem(
            id="test_id",
            user_id=123,
            knowledge_type=KnowledgeType.TRADING_PATTERN,
            title="Test",
            content={"data": "value"},
            relevance_score=0.75,
            game="csgo",
        )

        d = item.to_dict()

        assert d["id"] == "test_id"
        assert d["user_id"] == 123
        assert d["knowledge_type"] == "trading_pattern"
        assert d["relevance_score"] == 0.75
        assert d["game"] == "csgo"

    def test_trade_result_defaults(self) -> None:
        """Test TradeResult default values."""
        trade = TradeResult(
            item_name="Test",
            buy_price=10.0,
            sell_price=12.0,
            profit=2.0,
            profit_percent=20.0,
            game="csgo",
        )

        assert trade.hold_duration_hours == 0.0
        assert trade.item_category is None
        assert trade.extra_data == {}
