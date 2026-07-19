"""
event_driven.py — CS2 Event-Driven & Seasonal Strategy for DMarket.

Source: CS2Ref market analysis (cs2ref.com) 2024-2026
        CSBoard profitability guide 2026
        Steam market seasonal patterns

CS2 skin market has predictable seasonal patterns driven by:
  1. CS2 Major tournaments — souvenir items spike +25-60%
  2. Case releases — existing skin prices drop temporarily
  3. Operation launches — new content absorbs demand
  4. Steam Sales — influx of new players
  5. Holiday periods — increased gifting activity
  6. Anniversary events — price spikes on legacy items

This module provides:
  - Event calendar with historical impact data
  - Days-until-event proximity scoring
  - Historical seasonal price patterns (monthly/weekly)
  - Event category impact scoring
  - Combined event + seasonal signal

Applications in DMarket:
  - Pre-event accumulation: buy items before Major announcements
  - Post-event distribution: sell after price spikes
  - Seasonal timing: adjust min_spread by month/weekday
  - Event-specific item filtering (souvenir items near Majors)

Complexity: O(1) per signal (calendar lookup + interpolation)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger("EventDriven")


class EventType(Enum):
    """Types of CS2 market events."""
    MAJOR = "major"                    # CS2 Major tournament
    MINOR = "minor"                    # Minor tournament
    CASE_RELEASE = "case_release"      # New case/collection
    OPERATION = "operation"            # New operation
    STEAM_SALE = "steam_sale"          # Steam seasonal sale
    ANNIVERSARY = "anniversary"        # CS2/CS:GO anniversary
    GAME_UPDATE = "game_update"        # Major game update
    HOLIDAY = "holiday"                # Christmas, New Year, etc.


class EventImpact(Enum):
    """Historical impact levels."""
    HIGH = "high"          # >20% price movement
    MEDIUM = "medium"      # 5-20% price movement
    LOW = "low"            # <5% price movement
    UNKNOWN = "unknown"


@dataclass
class CS2Event:
    """A single CS2 market event."""
    name: str
    event_type: EventType
    start_date: datetime
    end_date: datetime | None = None
    impact: EventImpact = EventImpact.MEDIUM
    affected_items: list[str] = field(default_factory=list)  # item categories
    historical_price_impact_pct: float = 0.0  # average historical impact
    notes: str = ""


@dataclass
class SeasonalPattern:
    """Seasonal price pattern for a time period."""
    month: int = 0          # 1-12 (0 = any)
    weekday: int = -1       # 0-6 (Mon-Sun), -1 = any
    hour_range: tuple[int, int] = (0, 23)  # UTC hours
    multiplier: float = 1.0  # price activity multiplier
    confidence: float = 0.5  # pattern confidence 0-1


@dataclass
class EventSignal:
    """Combined event + seasonal signal."""
    event_score: float = 0.0        # -1.0 to +1.0 (bearish to bullish)
    seasonal_score: float = 0.0     # -1.0 to +1.0
    combined_score: float = 0.0     # weighted combination
    nearest_event: str = ""
    days_until_event: float = 0.0
    event_impact: EventImpact = EventImpact.UNKNOWN
    seasonal_multiplier: float = 1.0
    action: str = "hold"           # "accumulate", "distribute", "hold"
    confidence: float = 0.0


class CS2EventCalendar:
    """
    CS2 event calendar with historical impact data.

    Maintains a database of known CS2 events and their typical
    market impact. Events are added manually or from API feeds.
    """

    def __init__(self) -> None:
        self._events: list[CS2Event] = []
        self._seasonal_patterns: list[SeasonalPattern] = []
        self._init_default_events()
        self._init_seasonal_patterns()

    def _init_default_events(self) -> None:
        """Initialize with known CS2 Major schedule and recurring events."""
        now = datetime.now(timezone.utc)

        # CS2 Majors (typically May and November)
        # 2026 schedule (estimated based on historical pattern)
        majors = [
            ("PGL Major Copenhagen 2026", datetime(2026, 5, 15, tzinfo=timezone.utc)),
            ("BLAST.tv Major 2026", datetime(2026, 11, 20, tzinfo=timezone.utc)),
        ]

        for name, start in majors:
            self._events.append(CS2Event(
                name=name,
                event_type=EventType.MAJOR,
                start_date=start,
                end_date=start + timedelta(days=14),
                impact=EventImpact.HIGH,
                affected_items=["souvenir", "knife", "glove", "sticker_capsule"],
                historical_price_impact_pct=35.0,
                notes="Major tournaments historically spike souvenir and high-tier item prices",
            ))

        # Steam Sales (June & December typically)
        self._events.append(CS2Event(
            name="Steam Summer Sale 2026",
            event_type=EventType.STEAM_SALE,
            start_date=datetime(2026, 6, 25, tzinfo=timezone.utc),
            end_date=datetime(2026, 7, 9, tzinfo=timezone.utc),
            impact=EventImpact.MEDIUM,
            affected_items=["all"],
            historical_price_impact_pct=-8.0,
            notes="Steam sales temporarily depress prices as players sell to buy games",
        ))

        self._events.append(CS2Event(
            name="Steam Winter Sale 2026",
            event_type=EventType.STEAM_SALE,
            start_date=datetime(2026, 12, 22, tzinfo=timezone.utc),
            end_date=datetime(2027, 1, 5, tzinfo=timezone.utc),
            impact=EventImpact.MEDIUM,
            affected_items=["all"],
            historical_price_impact_pct=-10.0,
            notes="Winter sale typically has larger impact than summer",
        ))

        # CS2 Anniversary (September 27 — CS2 launch was Sept 27, 2023)
        self._events.append(CS2Event(
            name="CS2 Anniversary",
            event_type=EventType.ANNIVERSARY,
            start_date=datetime(2026, 9, 27, tzinfo=timezone.utc),
            end_date=datetime(2026, 9, 30, tzinfo=timezone.utc),
            impact=EventImpact.MEDIUM,
            affected_items=["legacy", "discontinued"],
            historical_price_impact_pct=12.0,
            notes="Anniversary events often bring nostalgia buying and legacy item interest",
        ))

        # Holiday season
        self._events.append(CS2Event(
            name="Holiday Season",
            event_type=EventType.HOLIDAY,
            start_date=datetime(2026, 12, 15, tzinfo=timezone.utc),
            end_date=datetime(2027, 1, 5, tzinfo=timezone.utc),
            impact=EventImpact.MEDIUM,
            affected_items=["giftable", "knife", "glove"],
            historical_price_impact_pct=15.0,
            notes="Holiday gifting drives demand for premium items",
        ))

    def _init_seasonal_patterns(self) -> None:
        """Initialize seasonal price patterns from historical data."""
        # Monthly patterns (from CS2Ref analysis)
        # January: post-holiday dip (players selling gifts)
        self._seasonal_patterns.append(SeasonalPattern(
            month=1, multiplier=0.85, confidence=0.6,
        ))
        # February-March: quiet period, good for accumulation
        self._seasonal_patterns.append(SeasonalPattern(
            month=2, multiplier=0.90, confidence=0.5,
        ))
        self._seasonal_patterns.append(SeasonalPattern(
            month=3, multiplier=0.92, confidence=0.5,
        ))
        # April-May: pre-Major buildup
        self._seasonal_patterns.append(SeasonalPattern(
            month=4, multiplier=1.05, confidence=0.4,
        ))
        self._seasonal_patterns.append(SeasonalPattern(
            month=5, multiplier=1.10, confidence=0.6,
        ))
        # June: Summer sale begins (price dip)
        self._seasonal_patterns.append(SeasonalPattern(
            month=6, multiplier=0.90, confidence=0.5,
        ))
        # July-August: recovery
        self._seasonal_patterns.append(SeasonalPattern(
            month=7, multiplier=0.95, confidence=0.4,
        ))
        self._seasonal_patterns.append(SeasonalPattern(
            month=8, multiplier=0.98, confidence=0.4,
        ))
        # September: Anniversary + new operation potential
        self._seasonal_patterns.append(SeasonalPattern(
            month=9, multiplier=1.05, confidence=0.5,
        ))
        # October: pre-Major buildup
        self._seasonal_patterns.append(SeasonalPattern(
            month=10, multiplier=1.08, confidence=0.5,
        ))
        # November: Major month
        self._seasonal_patterns.append(SeasonalPattern(
            month=11, multiplier=1.15, confidence=0.7,
        ))
        # December: Holiday + Major aftermath
        self._seasonal_patterns.append(SeasonalPattern(
            month=12, multiplier=1.10, confidence=0.6,
        ))

        # Weekend patterns (lower volume, less competition)
        self._seasonal_patterns.append(SeasonalPattern(
            weekday=5, multiplier=0.90, confidence=0.7,  # Saturday
        ))
        self._seasonal_patterns.append(SeasonalPattern(
            weekday=6, multiplier=0.88, confidence=0.7,  # Sunday
        ))

    def add_event(self, event: CS2Event) -> None:
        """Add a new event to the calendar."""
        self._events.append(event)
        logger.info(f"[EventCalendar] Added: {event.name} ({event.event_type.value})")

    def get_upcoming_events(
        self,
        days_ahead: int = 90,
        now: datetime | None = None,
    ) -> list[CS2Event]:
        """Get events within the next N days."""
        if now is None:
            now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days_ahead)

        return [
            e for e in self._events
            if now <= e.start_date <= cutoff
        ]

    def get_nearest_event(
        self,
        event_type: EventType | None = None,
        now: datetime | None = None,
    ) -> CS2Event | None:
        """Get the nearest upcoming event."""
        if now is None:
            now = datetime.now(timezone.utc)

        upcoming = [
            e for e in self._events
            if e.start_date > now
            and (event_type is None or e.event_type == event_type)
        ]

        if not upcoming:
            return None

        return min(upcoming, key=lambda e: e.start_date)


class EventDrivenStrategy:
    """
    Event-driven + seasonal strategy for DMarket.

    Combines:
    1. Proximity to major CS2 events (pre-event accumulation)
    2. Seasonal patterns (monthly/weekday multipliers)
    3. Historical impact data for position sizing

    Usage:
        strategy = EventDrivenStrategy()
        signal = strategy.get_signal(item_category="knife")
        if signal.action == "accumulate":
            # increase position size, tighten spreads
        elif signal.action == "distribute":
            # reduce positions, widen spreads for selling
    """

    # Weight configuration
    EVENT_PROXIMITY_WEIGHT: float = 0.6
    SEASONAL_WEIGHT: float = 0.4

    # Pre-event accumulation windows (days before event)
    ACCUMULATION_START_DAYS: int = 30   # start buying 30 days before
    ACCUMULATION_PEAK_DAYS: int = 7     # peak accumulation 7 days before
    DISTRIBUTION_START_DAYS: int = -3   # start selling 3 days after

    # Signal thresholds
    ACCUMULATE_THRESHOLD: float = 0.3   # score > 0.3 → accumulate
    DISTRIBUTE_THRESHOLD: float = -0.3  # score < -0.3 → distribute

    def __init__(self, calendar: CS2EventCalendar | None = None) -> None:
        from src.config import Config
        # FIX W11: Override class constants with Config values
        self.EVENT_PROXIMITY_WEIGHT = Config.EVENT_PROXIMITY_WEIGHT
        self.SEASONAL_WEIGHT = Config.SEASONAL_WEIGHT
        self.ACCUMULATION_START_DAYS = Config.ACCUMULATION_START_DAYS
        self.ACCUMULATION_PEAK_DAYS = Config.ACCUMULATION_PEAK_DAYS
        self.calendar = calendar or CS2EventCalendar()

    def get_signal(
        self,
        item_category: str = "all",
        now: datetime | None = None,
    ) -> EventSignal:
        """
        Get combined event + seasonal signal.

        Args:
            item_category: Item category ("knife", "glove", "souvenir", "all")
            now: Current datetime (for testing)

        Returns:
            EventSignal with action recommendation.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # 1. Event proximity signal
        event_score, nearest_event, days_until, event_impact = (
            self._event_proximity_signal(now, item_category)
        )

        # 2. Seasonal signal
        seasonal_score, seasonal_mult = self._seasonal_signal(now)

        # 3. Combined score
        combined = (
            self.EVENT_PROXIMITY_WEIGHT * event_score
            + self.SEASONAL_WEIGHT * seasonal_score
        )

        # 4. Action determination
        action = "hold"
        if combined > self.ACCUMULATE_THRESHOLD:
            action = "accumulate"
        elif combined < self.DISTRIBUTE_THRESHOLD:
            action = "distribute"

        # 5. Confidence
        confidence = min(1.0, abs(combined) * 1.5)

        signal = EventSignal(
            event_score=round(event_score, 4),
            seasonal_score=round(seasonal_score, 4),
            combined_score=round(combined, 4),
            nearest_event=nearest_event.name if nearest_event else "",
            days_until_event=round(days_until, 1),
            event_impact=event_impact,
            seasonal_multiplier=round(seasonal_mult, 4),
            action=action,
            confidence=round(confidence, 4),
        )

        logger.debug(
            f"[EventDriven] event={event_score:.2f} seasonal={seasonal_score:.2f} "
            f"combined={combined:.2f} → {action} (conf={confidence:.2f})"
        )

        return signal

    def _event_proximity_signal(
        self,
        now: datetime,
        item_category: str,
    ) -> tuple[float, CS2Event | None, float, EventImpact]:
        """
        Score based on proximity to nearest relevant event.

        Returns:
            (score, nearest_event, days_until, impact)
        """
        upcoming = self.calendar.get_upcoming_events(days_ahead=90, now=now)

        if not upcoming:
            return 0.0, None, 999.0, EventImpact.UNKNOWN

        # Filter by item category relevance
        relevant = [
            e for e in upcoming
            if item_category in e.affected_items or "all" in e.affected_items
        ]

        if not relevant:
            return 0.0, None, 999.0, EventImpact.UNKNOWN

        nearest = min(relevant, key=lambda e: e.start_date)
        days_until = (nearest.start_date - now).total_seconds() / 86400.0

        # Score based on proximity and impact
        impact_multiplier = {
            EventImpact.HIGH: 1.0,
            EventImpact.MEDIUM: 0.6,
            EventImpact.LOW: 0.3,
            EventImpact.UNKNOWN: 0.2,
        }.get(nearest.impact, 0.2)

        # Proximity score: peaks at ACCUMULATION_PEAK_DAYS before event
        if days_until <= 0:
            # Event is happening or passed — distribution phase
            if days_until >= self.DISTRIBUTION_START_DAYS:
                # During/just after event: hold or distribute
                score = -0.2 * impact_multiplier
            else:
                # Well past event: neutral
                score = 0.0
        elif days_until <= self.ACCUMULATION_PEAK_DAYS:
            # Peak accumulation window
            score = impact_multiplier
        elif days_until <= self.ACCUMULATION_START_DAYS:
            # Accumulation window (ramp up)
            progress = 1.0 - (days_until - self.ACCUMULATION_PEAK_DAYS) / (
                self.ACCUMULATION_START_DAYS - self.ACCUMULATION_PEAK_DAYS
            )
            score = impact_multiplier * progress * 0.8
        else:
            # Too far out
            score = 0.0

        return score, nearest, days_until, nearest.impact

    def _seasonal_signal(self, now: datetime) -> tuple[float, float]:
        """
        Score based on seasonal patterns.

        Returns:
            (score, multiplier)
        """
        current_month = now.month
        current_weekday = now.weekday()

        # Find matching patterns
        monthly_mult = 1.0
        monthly_confidence = 0.0
        weekday_mult = 1.0
        weekday_confidence = 0.0

        for pattern in self.calendar._seasonal_patterns:
            if pattern.month == current_month:
                monthly_mult = pattern.multiplier
                monthly_confidence = pattern.confidence
            if pattern.weekday == current_weekday:
                weekday_mult = pattern.multiplier
                weekday_confidence = pattern.confidence

        # Combined multiplier
        combined_mult = monthly_mult * weekday_mult

        # Score: >1.0 = bullish (price activity up), <1.0 = bearish
        # Map to [-1, 1] range
        if combined_mult > 1.0:
            score = min(1.0, (combined_mult - 1.0) * 5.0)  # +20% → score 1.0
        else:
            score = max(-1.0, (combined_mult - 1.0) * 5.0)  # -20% → score -1.0

        return score, combined_mult

    def get_state(self) -> dict:
        """Get current state for diagnostics."""
        now = datetime.now(timezone.utc)
        upcoming = self.calendar.get_upcoming_events(days_ahead=90, now=now)
        return {
            "upcoming_events": len(upcoming),
            "next_event": upcoming[0].name if upcoming else None,
            "next_event_date": upcoming[0].start_date.isoformat() if upcoming else None,
            "seasonal_month": now.month,
            "seasonal_weekday": now.strftime("%A"),
        }


# ══════════════════════════════════════════════════════════════════════
# Quick utility
# ══════════════════════════════════════════════════════════════════════

def event_signal_for_item(
    item_category: str = "all",
    now: datetime | None = None,
) -> EventSignal:
    """One-shot event signal for an item category."""
    strategy = EventDrivenStrategy()
    return strategy.get_signal(item_category=item_category, now=now)


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for event-driven strategy."""
    from datetime import datetime, timezone

    strategy = EventDrivenStrategy()

    # Test near a Major (simulate being 10 days before)
    major_date = datetime(2026, 5, 5, tzinfo=timezone.utc)
    signal = strategy.get_signal(item_category="souvenir", now=major_date)
    print(f"[EventDriven] 10 days before Major:")
    print(f"  event_score={signal.event_score:.2f}")
    print(f"  nearest_event={signal.nearest_event}")
    print(f"  days_until={signal.days_until_event}")
    print(f"  action={signal.action}")

    # Test during Steam sale
    sale_date = datetime(2026, 7, 1, tzinfo=timezone.utc)
    signal_sale = strategy.get_signal(item_category="all", now=sale_date)
    print(f"\n[EventDriven] During Steam Sale:")
    print(f"  event_score={signal_sale.event_score:.2f}")
    print(f"  nearest_event={signal_sale.nearest_event}")
    print(f"  action={signal_sale.action}")

    # Test normal day
    normal_date = datetime(2026, 3, 15, tzinfo=timezone.utc)
    signal_normal = strategy.get_signal(item_category="knife", now=normal_date)
    print(f"\n[EventDriven] Normal day (March):")
    print(f"  seasonal_score={signal_normal.seasonal_score:.2f}")
    print(f"  seasonal_multiplier={signal_normal.seasonal_multiplier:.2f}")
    print(f"  action={signal_normal.action}")

    # Sanity checks
    assert signal.days_until_event > 0, "Major should be in the future"
    assert signal.action in ("accumulate", "distribute", "hold"), "Valid action"
    print("\n[EventDriven] Self-check PASSED")


if __name__ == "__main__":
    _demo()
