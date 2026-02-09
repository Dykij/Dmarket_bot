"""Knowledge Base - User-specific trading memory system.

This module provides a knowledge management system that automatically:
- Remembers successful trading patterns
- Stores lessons learned from failed trades
- Provides personalized recommendations based on history
- Proactively checks knowledge when analyzing opportunities

Inspired by Anthropic's Knowledge Bases concept for Claude.

Features:
- Automatic knowledge accumulation from trades
- Context-aware knowledge retrieval
- Relevance decay for outdated information
- Pattern detection and learning

Usage:
    ```python
    from src.utils.knowledge_base import KnowledgeBase, KnowledgeType

    kb = KnowledgeBase(user_id=123456789)

    # Add knowledge from a successful trade
    await kb.learn_from_trade({
        "item_name": "AK-47 | Redline",
        "profit": 15.5,
        "buy_price": 10.0,
        "sell_price": 11.55,
        "game": "csgo",
    })

    # Query relevant knowledge for new opportunity
    knowledge = await kb.query_relevant(
        context={"item": "AK-47", "game": "csgo"},
        limit=5,
    )
    ```

Created: January 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from operator import itemgetter
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


# ============================================================================
# Knowledge Types
# ============================================================================


class KnowledgeType(StrEnum):
    """Types of knowledge entries.

    Each type represents a different category of learned information.
    """

    USER_PREFERENCE = "user_preference"  # User's trading preferences
    TRADING_PATTERN = "trading_pattern"  # Successful trading patterns
    LESSON_LEARNED = "lesson_learned"  # Lessons from mistakes
    MARKET_INSIGHT = "market_insight"  # Market behavior insights
    PRICE_ANOMALY = "price_anomaly"  # Price anomaly detections
    ITEM_KNOWLEDGE = "item_knowledge"  # Item-specific knowledge
    TIMING_PATTERN = "timing_pattern"  # Best trading times


class PatternType(StrEnum):
    """Types of trading patterns."""

    PROFITABLE_ITEM = "profitable_item"  # Item that's consistently profitable
    PROFITABLE_CATEGORY = "profitable_category"  # Category that works well
    BEST_TIME = "best_time"  # Optimal trading time
    PRICE_RANGE = "price_range"  # Optimal price range
    HOLD_DURATION = "hold_duration"  # Optimal hold time
    QUICK_FLIP = "quick_flip"  # Items good for quick resale


class LessonType(StrEnum):
    """Types of lessons learned."""

    OVERPAY = "overpay"  # Paid too much
    BAD_TIMING = "bad_timing"  # Traded at wrong time
    LOW_LIQUIDITY = "low_liquidity"  # Item was hard to sell
    PRICE_DROP = "price_drop"  # Price dropped after purchase
    MARKET_MANIPULATION = "market_manipulation"  # Fell for manipulation
    MISSED_OPPORTUNITY = "missed_opportunity"  # Should have bought


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class KnowledgeItem:
    """A single knowledge item (in-memory representation)."""

    id: str
    user_id: int
    knowledge_type: KnowledgeType
    title: str
    content: dict[str, Any]
    relevance_score: float = 1.0
    game: str | None = None
    item_category: str | None = None
    use_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "knowledge_type": self.knowledge_type.value,
            "title": self.title,
            "content": self.content,
            "relevance_score": round(self.relevance_score, 3),
            "game": self.game,
            "item_category": self.item_category,
            "use_count": self.use_count,
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }


@dataclass
class TradeResult:
    """Result of a trade for learning."""

    item_name: str
    buy_price: float
    sell_price: float
    profit: float
    profit_percent: float
    game: str
    hold_duration_hours: float = 0.0
    item_category: str | None = None
    trade_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    extra_data: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Configuration Constants
# ============================================================================

# Relevance decay settings
RELEVANCE_DECAY_RATE = 0.01  # 1% decay per day
MIN_RELEVANCE_THRESHOLD = 0.1  # Below this, knowledge is considered stale

# Scoring thresholds
HIGH_PROFIT_THRESHOLD = 10.0  # 10% profit is considered high
MODERATE_PROFIT_THRESHOLD = 5.0  # 5% profit is moderate
GOOD_LIQUIDITY_THRESHOLD = 0.7
ACCEPTABLE_LIQUIDITY_THRESHOLD = 0.5

# Knowledge limits
MAX_KNOWLEDGE_ENTRIES_PER_USER = 1000
MAX_QUERY_RESULTS = 50


# ============================================================================
# Knowledge Base Class
# ============================================================================


class KnowledgeBase:
    """User-specific knowledge base for trading insights.

    Inspired by Anthropic's Knowledge Bases concept - proactive
    context checking and automatic knowledge accumulation.

    The knowledge base automatically:
    1. Learns from successful and failed trades
    2. Detects patterns in trading behavior
    3. Provides relevant knowledge when analyzing opportunities
    4. Decays old knowledge to keep recommendations fresh

    Attributes:
        user_id: Telegram user ID
        session: Optional database session for persistence

    Example:
        >>> kb = KnowledgeBase(user_id=123456789)
        >>> await kb.learn_from_trade(trade_result)
        >>> knowledge = await kb.query_relevant(context={"item": "AK-47"})
    """

    def __init__(
        self,
        user_id: int,
        session: AsyncSession | None = None,
    ) -> None:
        """Initialize knowledge base.

        Args:
            user_id: Telegram user ID
            session: Optional async database session for persistence
        """
        self.user_id = user_id
        self.session = session

        # In-memory cache
        self._cache: dict[str, KnowledgeItem] = {}
        self._cache_loaded = False

        # Metrics
        self._metrics = {
            "queries": 0,
            "cache_hits": 0,
            "knowledge_added": 0,
            "patterns_detected": 0,
        }

        logger.info(
            "knowledge_base_initialized",
            user_id=user_id,
            has_session=session is not None,
        )

    # =========================================================================
    # Core Knowledge Operations
    # =========================================================================

    async def add_knowledge(
        self,
        knowledge_type: KnowledgeType,
        title: str,
        content: dict[str, Any],
        relevance_score: float = 1.0,
        game: str | None = None,
        item_category: str | None = None,
    ) -> str:
        """Add new knowledge entry.

        Args:
            knowledge_type: Type of knowledge
            title: Short description
            content: Full knowledge content
            relevance_score: Initial relevance (0.0-1.0)
            game: Game this applies to
            item_category: Item category filter

        Returns:
            ID of created knowledge entry
        """
        entry_id = f"{self.user_id}_{knowledge_type.value}_{uuid4().hex[:8]}"

        knowledge = KnowledgeItem(
            id=entry_id,
            user_id=self.user_id,
            knowledge_type=knowledge_type,
            title=title,
            content=content,
            relevance_score=min(1.0, max(0.0, relevance_score)),
            game=game,
            item_category=item_category,
        )

        # Store in cache
        self._cache[entry_id] = knowledge

        # Persist to database if session available
        if self.session:
            await self._persist_knowledge(knowledge)

        self._metrics["knowledge_added"] += 1

        logger.info(
            "knowledge_added",
            user_id=self.user_id,
            knowledge_type=knowledge_type.value,
            title=title[:50],
            entry_id=entry_id,
        )

        return entry_id

    async def query_relevant(
        self,
        context: dict[str, Any],
        min_relevance: float = 0.3,
        limit: int = 10,
        knowledge_types: list[KnowledgeType] | None = None,
    ) -> list[KnowledgeItem]:
        """Query knowledge base for relevant entries.

        Proactively checks knowledge base when:
        - Analyzing new arbitrage opportunity
        - Making trade recommendation
        - User asks about specific item

        Args:
            context: Query context (item name, game, price, etc.)
            min_relevance: Minimum relevance score threshold
            limit: Maximum number of results
            knowledge_types: Filter by specific types

        Returns:
            List of relevant KnowledgeItem objects
        """
        self._metrics["queries"] += 1

        # Get all entries from cache
        entries = list(self._cache.values())

        # Filter by relevance threshold
        filtered = [e for e in entries if e.relevance_score >= min_relevance]

        # Filter by knowledge type if specified
        if knowledge_types:
            filtered = [e for e in filtered if e.knowledge_type in knowledge_types]

        # Score by context match
        scored: list[tuple[KnowledgeItem, float]] = []
        for entry in filtered:
            score = self._calculate_context_match(entry, context)
            if score > 0:
                scored.append((entry, score))

        # Sort by score (descending)
        scored.sort(key=itemgetter(1), reverse=True)

        # Limit results
        results = [e for e, _ in scored[: min(limit, MAX_QUERY_RESULTS)]]

        # Update usage stats
        now = datetime.now(UTC)
        for entry in results:
            entry.last_used_at = now
            entry.use_count += 1

        logger.debug(
            "knowledge_queried",
            user_id=self.user_id,
            context_keys=list(context.keys()),
            results_count=len(results),
        )

        return results

    # =========================================================================
    # Learning from Trades
    # =========================================================================

    async def learn_from_trade(self, trade_result: dict[str, Any] | TradeResult) -> str | None:
        """Automatically learn from trade outcome.

        Called after every trade to extract lessons:
        - If profitable: record successful pattern
        - If loss: record lesson learned
        - Always: update market insights

        Args:
            trade_result: Trade result data (dict or TradeResult)

        Returns:
            ID of created knowledge entry, or None if nothing learned
        """
        # Convert dict to TradeResult if needed
        if isinstance(trade_result, dict):
            trade = TradeResult(
                item_name=trade_result.get("item_name", "Unknown"),
                buy_price=trade_result.get("buy_price", 0),
                sell_price=trade_result.get("sell_price", 0),
                profit=trade_result.get("profit", 0),
                profit_percent=trade_result.get("profit_percent", 0),
                game=trade_result.get("game", "csgo"),
                hold_duration_hours=trade_result.get("hold_duration_hours", 0),
                item_category=trade_result.get("item_category"),
                extra_data=trade_result.get("extra_data", {}),
            )
        else:
            trade = trade_result

        # Learn based on outcome
        if trade.profit > 0:
            return await self._learn_success(trade)
        if trade.profit < 0:
            return await self._learn_failure(trade)

        return None

    async def _learn_success(self, trade: TradeResult) -> str:
        """Learn from successful trade."""
        # Determine what made this successful
        if trade.profit_percent >= HIGH_PROFIT_THRESHOLD:
            title = f"Highly profitable: {trade.item_name}"
            relevance = 1.0
        elif trade.profit_percent >= MODERATE_PROFIT_THRESHOLD:
            title = f"Profitable trade: {trade.item_name}"
            relevance = 0.8
        else:
            title = f"Small profit: {trade.item_name}"
            relevance = 0.5

        content = {
            "item_name": trade.item_name,
            "profit": trade.profit,
            "profit_percent": trade.profit_percent,
            "buy_price": trade.buy_price,
            "sell_price": trade.sell_price,
            "hold_duration_hours": trade.hold_duration_hours,
            "trade_time": trade.trade_time.isoformat(),
            "pattern": "profitable_trade",
            "learned": (
                f"Item '{trade.item_name}' was profitable with "
                f"{trade.profit_percent:.1f}% margin"
            ),
        }

        return await self.add_knowledge(
            knowledge_type=KnowledgeType.TRADING_PATTERN,
            title=title,
            content=content,
            relevance_score=relevance,
            game=trade.game,
            item_category=trade.item_category,
        )

    async def _learn_failure(self, trade: TradeResult) -> str:
        """Learn from failed trade."""
        loss_percent = abs(trade.profit_percent)

        if loss_percent >= 10:
            severity = "high"
            title = f"⚠️ Major loss: {trade.item_name}"
        elif loss_percent >= 5:
            severity = "medium"
            title = f"Loss: {trade.item_name}"
        else:
            severity = "low"
            title = f"Small loss: {trade.item_name}"

        content = {
            "item_name": trade.item_name,
            "loss": abs(trade.profit),
            "loss_percent": loss_percent,
            "buy_price": trade.buy_price,
            "sell_price": trade.sell_price,
            "severity": severity,
            "trade_time": trade.trade_time.isoformat(),
            "lesson": f"Avoid similar trades with {trade.item_name}",
            "avoid_reason": "resulted_in_loss",
        }

        return await self.add_knowledge(
            knowledge_type=KnowledgeType.LESSON_LEARNED,
            title=title,
            content=content,
            relevance_score=1.0,  # Lessons are always highly relevant
            game=trade.game,
            item_category=trade.item_category,
        )

    # =========================================================================
    # Context Matching
    # =========================================================================

    def _calculate_context_match(
        self,
        entry: KnowledgeItem,
        context: dict[str, Any],
    ) -> float:
        """Calculate how well an entry matches the context.

        Args:
            entry: Knowledge entry to score
            context: Query context

        Returns:
            Match score (higher is better)
        """
        score = entry.relevance_score

        # Match by item name
        entry_item = entry.content.get("item_name")
        context_item = context.get("item") or context.get("item_name")
        if entry_item and context_item:
            # Partial match
            if entry_item.lower() in context_item.lower():
                score *= 2.0
            elif context_item.lower() in entry_item.lower():
                score *= 1.5

        # Match by game
        if entry.game and context.get("game"):
            if entry.game == context["game"]:
                score *= 1.5
            else:
                score *= 0.5  # Penalty for wrong game

        # Match by category
        if entry.item_category and context.get("category"):
            if entry.item_category.lower() in context["category"].lower():
                score *= 1.3

        # Boost recent entries
        if entry.last_used_at:
            days_ago = (datetime.now(UTC) - entry.last_used_at).days
            recency_boost = max(0.1, 1.0 - (days_ago * 0.05))
            score *= recency_boost

        # Boost frequently used entries
        if entry.use_count > 0:
            usage_boost = min(1.5, 1.0 + (entry.use_count * 0.05))
            score *= usage_boost

        return score

    # =========================================================================
    # Maintenance Operations
    # =========================================================================

    async def decay_relevance(self) -> int:
        """Apply relevance decay to all entries.

        Called periodically to "forget" outdated knowledge.
        Entries below MIN_RELEVANCE_THRESHOLD are marked inactive.

        Returns:
            Number of entries marked inactive
        """
        removed = 0
        now = datetime.now(UTC)

        for entry_id, entry in list(self._cache.items()):
            # Calculate days since creation or last use
            reference_time = entry.last_used_at or entry.created_at
            days_old = (now - reference_time).days

            # Apply decay
            decay = RELEVANCE_DECAY_RATE * days_old
            entry.relevance_score = max(0, entry.relevance_score - decay)

            # Remove if below threshold
            if entry.relevance_score < MIN_RELEVANCE_THRESHOLD:
                del self._cache[entry_id]
                removed += 1

        if removed > 0:
            logger.info(
                "knowledge_decay_applied",
                user_id=self.user_id,
                removed_count=removed,
                remaining=len(self._cache),
            )

        return removed

    async def get_summary(self) -> dict[str, Any]:
        """Get summary of knowledge base.

        Returns:
            Summary statistics
        """
        type_counts: dict[str, int] = {}
        for entry in self._cache.values():
            key = entry.knowledge_type.value
            type_counts[key] = type_counts.get(key, 0) + 1

        return {
            "user_id": self.user_id,
            "total_entries": len(self._cache),
            "by_type": type_counts,
            "avg_relevance": (
                sum(e.relevance_score for e in self._cache.values()) / len(self._cache)
                if self._cache
                else 0
            ),
            "total_queries": self._metrics["queries"],
            "knowledge_added": self._metrics["knowledge_added"],
        }

    async def clear(self) -> int:
        """Clear all knowledge entries.

        Returns:
            Number of entries cleared
        """
        count = len(self._cache)
        self._cache.clear()

        logger.info(
            "knowledge_base_cleared",
            user_id=self.user_id,
            entries_cleared=count,
        )

        return count

    # =========================================================================
    # Persistence
    # =========================================================================

    async def _persist_knowledge(self, knowledge: KnowledgeItem) -> None:
        """Persist knowledge entry to database.

        Args:
            knowledge: Knowledge item to persist
        """
        if not self.session:
            logger.debug(
                "persistence_skipped",
                user_id=self.user_id,
                reason="no_session",
            )
            return

        try:
            from src.models.knowledge import KnowledgeEntry

            entry = KnowledgeEntry(
                id=knowledge.id,
                user_id=knowledge.user_id,
                knowledge_type=knowledge.knowledge_type.value,
                title=knowledge.title,
                content=knowledge.content,
                relevance_score=knowledge.relevance_score,
                game=knowledge.game,
                item_category=knowledge.item_category,
                use_count=knowledge.use_count,
                created_at=knowledge.created_at,
                last_used_at=knowledge.last_used_at,
            )

            self.session.add(entry)
            await self.session.commit()

        except Exception as e:
            logger.exception(
                "knowledge_persist_failed",
                user_id=self.user_id,
                knowledge_id=knowledge.id,
                error=str(e),
            )

    async def load_from_database(self) -> int:
        """Load knowledge from database into cache.

        Returns:
            Number of entries loaded
        """
        if not self.session:
            return 0

        if self._cache_loaded:
            return len(self._cache)

        try:
            from sqlalchemy import select

            from src.models.knowledge import KnowledgeEntry

            stmt = (
                select(KnowledgeEntry)
                .where(KnowledgeEntry.user_id == self.user_id)
                .where(KnowledgeEntry.is_active.is_(True))
            )

            result = await self.session.execute(stmt)
            entries = result.scalars().all()

            for entry in entries:
                knowledge = KnowledgeItem(
                    id=str(entry.id),
                    user_id=entry.user_id,
                    knowledge_type=KnowledgeType(entry.knowledge_type),
                    title=entry.title,
                    content=entry.content or {},
                    relevance_score=entry.relevance_score,
                    game=entry.game,
                    item_category=entry.item_category,
                    use_count=entry.use_count or 0,
                    created_at=entry.created_at,
                    last_used_at=entry.last_used_at,
                )
                self._cache[knowledge.id] = knowledge

            self._cache_loaded = True

            logger.info(
                "knowledge_loaded_from_db",
                user_id=self.user_id,
                entries_loaded=len(entries),
            )

            return len(entries)

        except Exception as e:
            logger.exception(
                "knowledge_load_failed",
                user_id=self.user_id,
                error=str(e),
            )
            return 0


# ============================================================================
# Factory Functions
# ============================================================================

# Global cache of knowledge bases
_knowledge_bases: dict[int, KnowledgeBase] = {}


def get_knowledge_base(
    user_id: int,
    session: AsyncSession | None = None,
) -> KnowledgeBase:
    """Get or create knowledge base for user.

    Args:
        user_id: Telegram user ID
        session: Optional database session

    Returns:
        KnowledgeBase instance for the user
    """
    if user_id not in _knowledge_bases:
        _knowledge_bases[user_id] = KnowledgeBase(
            user_id=user_id,
            session=session,
        )
    return _knowledge_bases[user_id]


def clear_knowledge_base_cache() -> None:
    """Clear global knowledge base cache (for testing)."""
    _knowledge_bases.clear()
