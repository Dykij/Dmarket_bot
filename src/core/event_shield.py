"""
EventShield — CS2 Event Calendar Awareness Module.

Reads data/cs2_events.json and adjusts bot behavior during active events:
  - 'caution'     → raise required profit margin, skip risky categories
  - 'opportunity'  → lower thresholds for items that recover post-event
"""

import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("EventShield")

EVENTS_FILE = Path(__file__).parent.parent.parent / "data" / "cs2_events.json"


class EventShield:
    """Protects the bot from event-driven price crashes and detects buying opportunities."""

    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self._load_events()

    def _load_events(self):
        """Load events from JSON file."""
        try:
            if EVENTS_FILE.exists():
                with open(EVENTS_FILE, "r", encoding="utf-8") as f:
                    self.events = json.load(f)
                logger.info(f"📅 EventShield loaded {len(self.events)} events from calendar.")
            else:
                logger.warning(f"📅 Event calendar not found at {EVENTS_FILE}. Running without event awareness.")
        except Exception as e:
            logger.error(f"Failed to load event calendar: {e}")

    def reload(self):
        """Hot-reload events (e.g. after Telegram /add_event command)."""
        self._load_events()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def get_active_events(self, check_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """Return all events active on the given date (defaults to today)."""
        today = check_date or date.today()
        active = []
        for ev in self.events:
            try:
                start = datetime.strptime(ev["start"], "%Y-%m-%d").date()
                end = datetime.strptime(ev["end"], "%Y-%m-%d").date()
                if start <= today <= end:
                    active.append(ev)
            except (KeyError, ValueError):
                continue
        return active

    def get_margin_multiplier(self) -> float:
        """
        Returns the highest margin multiplier from all currently active events.
        If no event is active, returns 1.0 (no change).
        """
        active = self.get_active_events()
        if not active:
            return 1.0
        return max(ev.get("margin_multiplier", 1.0) for ev in active)

    def is_category_risky(self, item_title: str) -> bool:
        """
        Check if an item title matches any risky category from active 'caution' events.
        Uses simple keyword matching against affected_categories.
        """
        active = self.get_active_events()
        caution_events = [ev for ev in active if ev.get("effect") == "caution"]
        
        if not caution_events:
            return False

        title_lower = item_title.lower()
        for ev in caution_events:
            for category in ev.get("affected_categories", []):
                if category.lower() in title_lower:
                    return True
        return False

    def is_opportunity_mode(self) -> bool:
        """Returns True if any active event has effect='opportunity' (buy the dip)."""
        active = self.get_active_events()
        return any(ev.get("effect") == "opportunity" for ev in active)

    def get_status_summary(self) -> str:
        """Human-readable summary for Telegram /events command."""
        active = self.get_active_events()
        if not active:
            return "✅ Нет активных ивентов. Бот работает в штатном режиме (маржа 5%)."

        lines = ["🎯 **Активные ивенты CS2:**\n"]
        for ev in active:
            effect_icon = "⚠️" if ev["effect"] == "caution" else "💰"
            lines.append(
                f"{effect_icon} **{ev['name']}**\n"
                f"   Период: {ev['start']} — {ev['end']}\n"
                f"   Эффект: {ev['effect'].upper()}\n"
                f"   Множитель маржи: x{ev.get('margin_multiplier', 1.0)}\n"
                f"   {ev.get('notes', '')}\n"
            )
        return "\n".join(lines)

    def save_events(self):
        """Persist current events list back to JSON (for Telegram /add_event)."""
        try:
            with open(EVENTS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.events, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save event calendar: {e}")

    def add_event(self, name: str, start: str, end: str, effect: str = "caution",
                  margin_multiplier: float = 2.0, affected_categories: Optional[List[str]] = None,
                  notes: str = ""):
        """Add a new event and persist."""
        self.events.append({
            "name": name,
            "start": start,
            "end": end,
            "type": "custom",
            "effect": effect,
            "affected_categories": affected_categories or [],
            "margin_multiplier": margin_multiplier,
            "notes": notes,
        })
        self.save_events()
        logger.info(f"📅 Added event: {name} ({start} — {end})")
