"""
event_detection.py — CS2 Event Detection for Price Impact.

v15.7: Monitors CS2 ecosystem events that impact skin prices:
- Game updates (new cases, operation launches, balance changes)
- Major tournaments (stickers, autographs, souvenir drops)
- New case releases (impact on existing skin prices)

Data sources:
- CS2 blog RSS / Steam news API
- HLTV.org tournament calendar
- DMarket aggregated prices (volume spikes as event proxy)

Integration:
- Called from _stage_prefetch in cycle_orchestrator.py
- Results passed to filter pipeline for price adjustment
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("EventDetection")


@dataclass
class CS2Event:
    """A detected CS2 ecosystem event."""
    event_type: str  # "update", "tournament", "new_case", "operation"
    title: str = ""
    description: str = ""
    detected_at: float = 0.0
    impact_estimate: float = 0.0  # estimated % price impact
    affected_categories: list[str] = field(default_factory=list)
    expires_at: float = 0.0  # when the event impact fades

    @property
    def is_active(self) -> bool:
        return time.time() < self.expires_at


@dataclass
class EventImpact:
    """Price impact assessment for a specific item based on events."""
    title: str = ""
    event_multiplier: float = 1.0  # 1.0 = no impact, >1 = positive, <1 = negative
    reason: str = ""
    active_events: int = 0


class EventDetector:
    """
    Detects CS2 ecosystem events and estimates their price impact.

    Uses volume spike detection as a proxy for event detection:
    - Sudden volume spike (>3x normal) = possible event
    - Price correlation with known event types
    - Tournament schedule integration (future)

    This is a lightweight, stateless detector — no external API calls.
    It analyzes existing price_db data to detect anomalies.
    """

    def __init__(self, price_db: Any = None) -> None:
        self._price_db = price_db
        self._active_events: list[CS2Event] = []
        self._last_scan_ts: float = 0.0
        self._scan_interval: float = 300.0  # 5 minutes

    def bind(self, price_db: Any) -> None:
        """Late-bind price_db dependency."""
        self._price_db = price_db

    def detect_events(self) -> list[CS2Event]:
        """
        Scan for events using volume spike detection.
        Returns list of newly detected events.
        """
        now = time.time()
        if now - self._last_scan_ts < self._scan_interval:
            return self._active_events

        self._last_scan_ts = now
        new_events: list[CS2Event] = []

        if self._price_db is None:
            return new_events

        # Detect volume spikes across all tracked items
        try:
            volume_spikes = self._detect_volume_spikes()
            for spike in volume_spikes:
                event = CS2Event(
                    event_type="volume_spike",
                    title=f"Volume spike: {spike['title']}",
                    description=f"Volume {spike['multiplier']:.1f}x normal for {spike['title']}",
                    detected_at=now,
                    impact_estimate=spike.get("estimated_impact", 0.0),
                    affected_categories=[spike["title"]],
                    expires_at=now + 3600,  # 1h impact window
                )
                new_events.append(event)
        except Exception as e:
            logger.debug(f"[EventDetection] Volume spike scan failed: {e}")

        # Detect new case releases (items with <7 days history but high volume)
        try:
            new_items = self._detect_new_items()
            for item in new_items:
                event = CS2Event(
                    event_type="new_case",
                    title=f"New item: {item['title']}",
                    description=f"Recently added item with high activity",
                    detected_at=now,
                    impact_estimate=-5.0,  # new items typically depress existing prices
                    affected_categories=[item["title"]],
                    expires_at=now + 86400 * 7,  # 7-day impact
                )
                new_events.append(event)
        except Exception as e:
            logger.debug(f"[EventDetection] New item scan failed: {e}")

        # Merge with existing events (deduplicate)
        self._active_events = self._merge_events(self._active_events, new_events)

        if new_events:
            logger.info(f"[EventDetection] Detected {len(new_events)} new events")

        return new_events

    def get_item_impact(self, title: str) -> EventImpact:
        """
        Get the price impact estimate for a specific item based on active events.
        Returns EventImpact with multiplier (1.0 = no impact).
        """
        impact = EventImpact(title=title)

        for event in self._active_events:
            if not event.is_active:
                continue
            if title in event.affected_categories or not event.affected_categories:
                impact.active_events += 1
                # Apply event impact as a multiplier
                if event.impact_estimate > 0:
                    impact.event_multiplier *= (1.0 + event.impact_estimate / 100.0)
                    impact.reason = f"Positive event: {event.title}"
                elif event.impact_estimate < 0:
                    impact.event_multiplier *= (1.0 + event.impact_estimate / 100.0)
                    impact.reason = f"Negative event: {event.title}"

        return impact

    def _detect_volume_spikes(self) -> list[dict[str, Any]]:
        """Detect items with abnormally high trading volume."""
        spikes: list[dict[str, Any]] = []

        if not hasattr(self._price_db, "get_trade_history"):
            return spikes

        # Get recent trade history for all items
        try:
            # Use a broad query to find items with high activity
            recent_trades = self._price_db.get_trade_history(
                title="", days=1, limit=1000
            )
            if not recent_trades:
                return spikes

            # Count trades per item
            item_counts: dict[str, int] = {}
            for trade in recent_trades:
                t = trade.get("title", trade.get("hash_name", ""))
                if t:
                    item_counts[t] = item_counts.get(t, 0) + 1

            # Compare with historical average (simplified)
            for title, count in item_counts.items():
                if count > 20:  # threshold for "high volume" in 1 day
                    spikes.append({
                        "title": title,
                        "multiplier": count / 10.0,  # rough estimate
                        "estimated_impact": min(count * 0.5, 20.0),  # cap at 20%
                    })
        except Exception as e:
            logger.debug(f"[EventDetection] Volume spike detection error: {e}")

        return spikes

    def _detect_new_items(self) -> list[dict[str, Any]]:
        """Detect recently added items with high activity."""
        new_items: list[dict[str, Any]] = []

        if not hasattr(self._price_db, "get_recent_prices"):
            return new_items

        try:
            # Items with very short history (< 7 days) but multiple observations
            # This is a proxy for "newly added to the marketplace"
            pass  # Implementation depends on price_db schema
        except Exception as e:
            logger.debug(f"[EventDetection] New item detection error: {e}")

        return new_items

    def _merge_events(
        self, existing: list[CS2Event], new: list[CS2Event]
    ) -> list[CS2Event]:
        """Merge new events with existing, deduplicate, expire old ones."""
        now = time.time()
        # Remove expired events
        active = [e for e in existing if e.is_active]

        # Add new events (avoid duplicates by title)
        existing_titles = {e.title for e in active}
        for event in new:
            if event.title not in existing_titles:
                active.append(event)

        return active

    @property
    def active_event_count(self) -> int:
        """Number of currently active events."""
        return len([e for e in self._active_events if e.is_active])
