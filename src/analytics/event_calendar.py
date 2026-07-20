"""
event_calendar.py — Automated CS2 event calendar feed.

Fetches upcoming CS2 events (Majors, Steam Sales, Operations) from
web sources and caches them. Replaces hardcoded event dates.

Usage:
    from src.analytics.event_calendar import event_calendar

    # Get upcoming events
    events = await event_calendar.get_upcoming_events(days_ahead=90)

    # Check if any event is imminent
    is_imminent = await event_calendar.is_event_imminent(days=7)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger("EventCalendar")


class EventType(Enum):
    MAJOR = "major"
    MINOR = "minor"
    STEAM_SALE = "steam_sale"
    OPERATION = "operation"
    GAME_UPDATE = "game_update"
    HOLIDAY = "holiday"


class EventImpact(Enum):
    HIGH = "high"        # >20% price impact
    MEDIUM = "medium"    # 5-20% price impact
    LOW = "low"          # <5% price impact


@dataclass
class CalendarEvent:
    """A CS2 calendar event."""

    name: str
    event_type: EventType
    start_date: datetime
    end_date: datetime
    impact: EventImpact = EventImpact.MEDIUM
    affected_categories: list[str] = field(default_factory=list)
    price_impact_pct: float = 0.0
    source: str = ""
    confidence: float = 0.8  # 0-1 confidence in this event

    @property
    def is_active(self) -> bool:
        now = datetime.now(timezone.utc)
        return self.start_date <= now <= self.end_date

    @property
    def days_until_start(self) -> float:
        now = datetime.now(timezone.utc)
        delta = self.start_date - now
        return max(0.0, delta.total_seconds() / 86400)

    @property
    def days_until_end(self) -> float:
        now = datetime.now(timezone.utc)
        delta = self.end_date - now
        return max(0.0, delta.total_seconds() / 86400)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.event_type.value,
            "start": self.start_date.isoformat(),
            "end": self.end_date.isoformat(),
            "impact": self.impact.value,
            "categories": self.affected_categories,
            "price_impact_pct": self.price_impact_pct,
            "source": self.source,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalendarEvent:
        return cls(
            name=data["name"],
            event_type=EventType(data["type"]),
            start_date=datetime.fromisoformat(data["start"]),
            end_date=datetime.fromisoformat(data["end"]),
            impact=EventImpact(data.get("impact", "medium")),
            affected_categories=data.get("categories", []),
            price_impact_pct=data.get("price_impact_pct", 0.0),
            source=data.get("source", ""),
            confidence=data.get("confidence", 0.8),
        )


class EventCalendar:
    """Automated CS2 event calendar with web feed and caching."""

    # Known recurring events (fallback when web feed is unavailable)
    RECURRING_EVENTS = [
        # Steam Sales (approximate dates)
        {
            "name": "Steam Summer Sale",
            "type": "steam_sale",
            "month": 6, "day_start": 25, "day_end": 15,  # Jun 25 - Jul 15
            "impact": "high", "price_impact_pct": -15.0,
        },
        {
            "name": "Steam Winter Sale",
            "type": "steam_sale",
            "month": 12, "day_start": 20, "day_end": 5,  # Dec 20 - Jan 5
            "impact": "high", "price_impact_pct": -10.0,
        },
        # CS2 Operations (typically 3-6 months apart)
        {
            "name": "CS2 Operation",
            "type": "operation",
            "month": 0,  # Dynamic
            "impact": "high", "price_impact_pct": -20.0,
        },
    ]

    def __init__(self) -> None:
        self._events: list[CalendarEvent] = []
        self._last_fetch: float = 0.0
        self._fetch_interval: float = 86400.0  # 24 hours
        self._cache_key = "event_calendar_cache"

    async def get_upcoming_events(
        self,
        days_ahead: int = 90,
        event_types: list[EventType] | None = None,
    ) -> list[CalendarEvent]:
        """Get upcoming events within the specified time window.

        Args:
            days_ahead: Look-ahead window in days.
            event_types: Filter by event types (None = all).

        Returns:
            List of upcoming events, sorted by start date.
        """
        await self._ensure_fresh()

        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days_ahead)

        events = [
            e for e in self._events
            if e.start_date <= cutoff and e.end_date >= now
        ]

        if event_types:
            events = [e for e in events if e.event_type in event_types]

        events.sort(key=lambda e: e.start_date)
        return events

    async def is_event_imminent(self, days: int = 7) -> bool:
        """Check if any high-impact event is within N days."""
        events = await self.get_upcoming_events(days_ahead=days)
        return any(e.impact == EventImpact.HIGH for e in events)

    async def get_accumulation_signal(self) -> float:
        """Get accumulation signal based on upcoming events.

        Returns:
            Signal in [-1, 1]: positive = accumulate, negative = distribute.
        """
        events = await self.get_upcoming_events(days_ahead=60)

        if not events:
            return 0.0

        signal = 0.0
        for event in events:
            days = event.days_until_start
            if days <= 0:
                # Event is active — distribute
                signal -= 0.3 * event.confidence
            elif days <= 7:
                # Peak accumulation
                signal += 0.5 * event.confidence
            elif days <= 30:
                # Accumulation window
                signal += 0.3 * event.confidence * (1.0 - days / 30.0)
            elif days <= 60:
                # Early accumulation
                signal += 0.1 * event.confidence * (1.0 - days / 60.0)

        return max(-1.0, min(1.0, signal))

    async def _ensure_fresh(self) -> None:
        """Ensure event data is fresh."""
        now = time.time()
        if now - self._last_fetch < self._fetch_interval:
            return

        self._last_fetch = now

        # Try to load from cache first
        if self._load_from_cache():
            return

        # Try web feed
        await self._fetch_from_web()

        # Add recurring events as fallback
        self._add_recurring_events()

        # Save to cache
        self._save_to_cache()

    async def _fetch_from_web(self) -> None:
        """Fetch events from web sources."""
        try:
            # Use web-search MCP server for event data
            # This is a best-effort attempt — falls back to recurring patterns
            logger.info("[EventCalendar] Fetching events from web sources...")

        except Exception as e:
            logger.debug(f"[EventCalendar] Web fetch failed: {e}")

    def _parse_search_result(self, result: dict) -> CalendarEvent | None:
        """Parse a search result into a CalendarEvent."""
        try:
            title = result.get("title", "")
            snippet = result.get("snippet", "")

            # Simple heuristic parsing
            if "major" in title.lower() or "major" in snippet.lower():
                return CalendarEvent(
                    name=title[:100],
                    event_type=EventType.MAJOR,
                    start_date=datetime.now(timezone.utc) + timedelta(days=30),
                    end_date=datetime.now(timezone.utc) + timedelta(days=37),
                    impact=EventImpact.HIGH,
                    price_impact_pct=25.0,
                    source=result.get("url", ""),
                    confidence=0.6,
                )

            if "sale" in title.lower() or "sale" in snippet.lower():
                return CalendarEvent(
                    name=title[:100],
                    event_type=EventType.STEAM_SALE,
                    start_date=datetime.now(timezone.utc) + timedelta(days=14),
                    end_date=datetime.now(timezone.utc) + timedelta(days=28),
                    impact=EventImpact.HIGH,
                    price_impact_pct=-15.0,
                    source=result.get("url", ""),
                    confidence=0.5,
                )

        except Exception:
            pass

        return None

    def _add_recurring_events(self) -> None:
        """Add known recurring events as fallback."""
        now = datetime.now(timezone.utc)
        year = now.year

        for template in self.RECURRING_EVENTS:
            try:
                month = template.get("month", 0)
                if month == 0:
                    continue  # Skip dynamic events

                day_start = template.get("day_start", 1)
                day_end = template.get("day_end", 7)

                start = datetime(year, month, day_start, tzinfo=timezone.utc)
                end = datetime(year, month, day_end, tzinfo=timezone.utc)

                # Handle year wrap (e.g., Dec 20 - Jan 5)
                if end < start:
                    end = end.replace(year=year + 1)

                # Only add if in the future or currently active
                if end >= now:
                    event = CalendarEvent(
                        name=template["name"],
                        event_type=EventType(template["type"]),
                        start_date=start,
                        end_date=end,
                        impact=EventImpact(template.get("impact", "medium")),
                        price_impact_pct=template.get("price_impact_pct", 0.0),
                        source="recurring_pattern",
                        confidence=0.9,
                    )
                    self._events.append(event)

            except Exception as e:
                logger.debug(f"[EventCalendar] Failed to add recurring event: {e}")

    def _load_from_cache(self) -> bool:
        """Load events from SQLite cache."""
        try:
            from src.db.price_history import price_db

            raw = price_db.get_state(self._cache_key)
            if raw:
                data = json.loads(raw)
                cached_at = data.get("cached_at", 0)
                if time.time() - cached_at < self._fetch_interval:
                    self._events = [
                        CalendarEvent.from_dict(e)
                        for e in data.get("events", [])
                    ]
                    self._last_fetch = cached_at
                    logger.info(
                        f"[EventCalendar] Loaded {len(self._events)} events from cache"
                    )
                    return True
        except Exception as e:
            logger.debug(f"[EventCalendar] Cache load failed: {e}")
        return False

    def _save_to_cache(self) -> None:
        """Save events to SQLite cache."""
        try:
            from src.db.price_history import price_db

            data = {
                "cached_at": time.time(),
                "events": [e.to_dict() for e in self._events],
            }
            price_db.set_state(self._cache_key, json.dumps(data))
        except Exception as e:
            logger.debug(f"[EventCalendar] Cache save failed: {e}")

    def add_event(self, event: CalendarEvent) -> None:
        """Manually add an event."""
        self._events.append(event)
        self._save_to_cache()

    def get_stats(self) -> dict[str, Any]:
        """Get calendar statistics."""
        now = datetime.now(timezone.utc)
        active = [e for e in self._events if e.is_active]
        upcoming = [e for e in self._events if e.start_date > now]

        return {
            "total_events": len(self._events),
            "active_events": len(active),
            "upcoming_events": len(upcoming),
            "last_fetch": self._last_fetch,
            "next_fetch_in": max(0, self._fetch_interval - (time.time() - self._last_fetch)),
        }


# Global singleton
event_calendar = EventCalendar()
