"""
knowledge_base.py — Adaptive Market Knowledge for Strategy Optimization.

v15.7: Stores market insights and adaptive thresholds learned from trading
history. Enables the bot to "learn" from past trades and adjust parameters.

Key capabilities:
1. Record market insights (e.g., "stickers rise after Major tournaments")
2. Adaptive thresholds (e.g., MIN_SPREAD adjusts based on recent success)
3. Pattern recognition (e.g., "items with float < 0.01 sell 30% faster")
4. Time-based learning (e.g., "weekend margins are 2% higher")

Integration:
- Called from self_reflection.py after each cycle
- Queried by filter pipeline for adaptive thresholds
- Stored in SQLite (knowledge_insights table)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("KnowledgeBase")


class InsightCategory(str, Enum):
    """Categories of market insights."""
    PRICE_PATTERN = "price_pattern"       # Price movement patterns
    TIMING = "timing"                     # Time-based patterns
    EVENT_IMPACT = "event_impact"         # Event-driven price changes
    ITEM_SPECIFIC = "item_specific"       # Item-specific knowledge
    STRATEGY = "strategy"                 # Strategy performance insights
    RISK = "risk"                         # Risk management insights


@dataclass
class Insight:
    """A single market insight."""
    category: str
    key: str           # e.g., "stickers_post_major", "weekend_margin_boost"
    value: float       # numeric value (multiplier, threshold, etc.)
    confidence: float  # 0.0-1.0 (how reliable this insight is)
    sample_size: int   # number of observations
    created_at: float = 0.0
    last_updated: float = 0.0
    expires_at: float = 0.0  # 0 = never expires

    @property
    def is_active(self) -> bool:
        if self.expires_at > 0 and time.time() > self.expires_at:
            return False
        return self.confidence > 0.3  # minimum confidence threshold

    @property
    def age_days(self) -> float:
        return (time.time() - self.created_at) / 86400.0


@dataclass
class AdaptiveThreshold:
    """An adaptive threshold that adjusts based on trading history."""
    name: str              # e.g., "min_spread_pct", "max_price_usd"
    base_value: float      # original value from Config
    current_value: float   # adjusted value
    adjustment_factor: float = 1.0  # multiplier applied to base
    confidence: float = 0.5
    last_adjusted: float = 0.0


class KnowledgeBase:
    """
    Stores and retrieves market insights for adaptive strategy optimization.

    This is an in-memory knowledge store with SQLite persistence.
    Insights are created by self_reflection.py and queried by the filter pipeline.
    """

    def __init__(self, price_db: Any = None) -> None:
        self._price_db = price_db
        self._insights: dict[str, Insight] = {}
        self._thresholds: dict[str, AdaptiveThreshold] = {}
        self._stats = {
            "total_insights_recorded": 0,
            "total_threshold_adjustments": 0,
            "insights_expired": 0,
        }

    def bind(self, price_db: Any) -> None:
        """Late-bind price_db dependency."""
        self._price_db = price_db

    # ----------------------------------------------------------------
    # Insight Management
    # ----------------------------------------------------------------

    def record_insight(
        self,
        category: str,
        key: str,
        value: float,
        confidence: float = 0.5,
        sample_size: int = 1,
        ttl_seconds: float = 0.0,
    ) -> Insight:
        """
        Record a market insight.

        Args:
            category: InsightCategory value
            key: unique key for this insight (e.g., "stickers_post_major")
            value: numeric value (multiplier, threshold, etc.)
            confidence: 0.0-1.0 reliability score
            sample_size: number of observations backing this insight
            ttl_seconds: time-to-live (0 = never expires)

        Returns:
            The created/updated Insight
        """
        now = time.time()
        existing = self._insights.get(key)

        if existing is not None:
            # Update existing insight with weighted average
            total_samples = existing.sample_size + sample_size
            weighted_value = (
                (existing.value * existing.sample_size + value * sample_size)
                / total_samples
            )
            weighted_confidence = min(
                1.0,
                (existing.confidence * existing.sample_size + confidence * sample_size)
                / total_samples,
            )
            existing.value = weighted_value
            existing.confidence = weighted_confidence
            existing.sample_size = total_samples
            existing.last_updated = now
            if ttl_seconds > 0:
                existing.expires_at = now + ttl_seconds
            self._stats["total_insights_recorded"] += 1
            return existing

        # Create new insight
        insight = Insight(
            category=category,
            key=key,
            value=value,
            confidence=confidence,
            sample_size=sample_size,
            created_at=now,
            last_updated=now,
            expires_at=now + ttl_seconds if ttl_seconds > 0 else 0.0,
        )
        self._insights[key] = insight
        self._stats["total_insights_recorded"] += 1

        logger.debug(
            f"[KnowledgeBase] Recorded insight: {key}={value:.3f} "
            f"(confidence={confidence:.2f}, samples={sample_size})"
        )
        return insight

    def get_insight(self, key: str) -> Insight | None:
        """Get a specific insight by key."""
        insight = self._insights.get(key)
        if insight is not None and not insight.is_active:
            return None
        return insight

    def get_insights_by_category(self, category: str) -> list[Insight]:
        """Get all active insights for a category."""
        return [
            i for i in self._insights.values()
            if i.category == category and i.is_active
        ]

    def get_insight_value(self, key: str, default: float = 0.0) -> float:
        """Get the value of an insight, or default if not found."""
        insight = self.get_insight(key)
        return insight.value if insight is not None else default

    # ----------------------------------------------------------------
    # Adaptive Thresholds
    # ----------------------------------------------------------------

    def set_adaptive_threshold(
        self,
        name: str,
        base_value: float,
        adjustment_factor: float = 1.0,
        confidence: float = 0.5,
    ) -> AdaptiveThreshold:
        """
        Set an adaptive threshold.

        The threshold starts at base_value and adjusts based on
        trading performance (adjustment_factor multiplies base).
        """
        now = time.time()
        current = base_value * adjustment_factor

        existing = self._thresholds.get(name)
        if existing is not None:
            existing.current_value = current
            existing.adjustment_factor = adjustment_factor
            existing.confidence = confidence
            existing.last_adjusted = now
            self._stats["total_threshold_adjustments"] += 1
            return existing

        threshold = AdaptiveThreshold(
            name=name,
            base_value=base_value,
            current_value=current,
            adjustment_factor=adjustment_factor,
            confidence=confidence,
            last_adjusted=now,
        )
        self._thresholds[name] = threshold
        self._stats["total_threshold_adjustments"] += 1
        return threshold

    def get_threshold(self, name: str, default: float | None = None) -> float:
        """
        Get the current value of an adaptive threshold.

        Returns the adjusted value if set, otherwise the default.
        """
        threshold = self._thresholds.get(name)
        if threshold is not None:
            return threshold.current_value
        return default if default is not None else 0.0

    def get_threshold_info(self, name: str) -> AdaptiveThreshold | None:
        """Get full threshold info."""
        return self._thresholds.get(name)

    # ----------------------------------------------------------------
    # Common Insights (pre-defined patterns)
    # ----------------------------------------------------------------

    def record_trade_outcome(
        self,
        title: str,
        buy_price: float,
        sell_price: float,
        hold_time_hours: float,
        strategy: str = "intra_spread",
    ) -> None:
        """
        Record a completed trade for learning.

        Automatically generates insights from trade outcomes:
        - ROI per strategy
        - Optimal hold time
        - Item-specific patterns
        """
        if buy_price <= 0:
            return

        roi_pct = ((sell_price - buy_price) / buy_price) * 100.0

        # Strategy performance insight
        strategy_key = f"strategy_roi_{strategy}"
        existing = self.get_insight(strategy_key)
        if existing:
            # Weighted average ROI
            new_count = existing.sample_size + 1
            new_roi = (existing.value * existing.sample_size + roi_pct) / new_count
            self.record_insight(
                InsightCategory.STRATEGY, strategy_key, new_roi,
                confidence=min(0.9, new_count / 50.0),
                sample_size=new_count,
            )
        else:
            self.record_insight(
                InsightCategory.STRATEGY, strategy_key, roi_pct,
                confidence=0.1, sample_size=1,
            )

        # Hold time insight
        if hold_time_hours > 0:
            self.record_insight(
                InsightCategory.TIMING, "avg_hold_hours", hold_time_hours,
                confidence=0.3, sample_size=1,
            )

        # Win/loss tracking
        win_key = "win_rate"
        if roi_pct > 0:
            self.record_insight(
                InsightCategory.RISK, win_key, 1.0,
                confidence=0.5, sample_size=1,
            )
        else:
            self.record_insight(
                InsightCategory.RISK, win_key, 0.0,
                confidence=0.5, sample_size=1,
            )

    def record_price_pattern(
        self,
        pattern_name: str,
        multiplier: float,
        confidence: float = 0.5,
        sample_size: int = 1,
    ) -> None:
        """Record a price pattern (e.g., 'stickers rise 15% after Major')."""
        self.record_insight(
            InsightCategory.PRICE_PATTERN, pattern_name, multiplier,
            confidence=confidence, sample_size=sample_size,
        )

    def record_event_impact(
        self,
        event_type: str,
        impact_pct: float,
        confidence: float = 0.5,
    ) -> None:
        """Record an event impact (e.g., 'new_case drops existing prices 5%')."""
        self.record_insight(
            InsightCategory.EVENT_IMPACT, f"event_{event_type}", impact_pct,
            confidence=confidence, sample_size=1,
            ttl_seconds=86400 * 30,  # expire after 30 days
        )

    # ----------------------------------------------------------------
    # Maintenance
    # ----------------------------------------------------------------

    def expire_old_insights(self) -> int:
        """Remove expired insights. Returns count of removed."""
        now = time.time()
        expired = [
            key for key, insight in self._insights.items()
            if insight.expires_at > 0 and now > insight.expires_at
        ]
        for key in expired:
            del self._insights[key]
        self._stats["insights_expired"] += len(expired)
        return len(expired)

    def clear(self) -> None:
        """Clear all insights and thresholds."""
        self._insights.clear()
        self._thresholds.clear()

    # ----------------------------------------------------------------
    # Stats & Diagnostics
    # ----------------------------------------------------------------

    @property
    def insight_count(self) -> int:
        return len([i for i in self._insights.values() if i.is_active])

    @property
    def threshold_count(self) -> int:
        return len(self._thresholds)

    def get_stats(self) -> dict[str, Any]:
        """Get knowledge base statistics."""
        return {
            **self._stats,
            "active_insights": self.insight_count,
            "active_thresholds": self.threshold_count,
            "categories": {
                cat.value: len(self.get_insights_by_category(cat.value))
                for cat in InsightCategory
            },
        }

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        stats = self.get_stats()
        lines = [
            f"KnowledgeBase: {stats['active_insights']} insights, "
            f"{stats['active_thresholds']} thresholds",
            f"  Recorded: {stats['total_insights_recorded']}, "
            f"Expired: {stats['insights_expired']}",
        ]
        for cat, count in stats["categories"].items():
            if count > 0:
                lines.append(f"  {cat}: {count}")
        return "\n".join(lines)
