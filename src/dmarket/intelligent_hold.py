"""
Intelligent Hold Module - Smart inventory retention strategy.

Analyzes upcoming events (tournaments, sales, updates) and recommends
whether to hold items for potential price increase.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class EventType(Enum):
    """Types of market-moving events."""

    MAJOR_TOURNAMENT = "major_tournament"
    MINOR_TOURNAMENT = "minor_tournament"
    STEAM_SALE = "steam_sale"
    GAME_UPDATE = "game_update"
    OPERATION_END = "operation_end"
    NEW_CASE = "new_case"
    STICKER_CAPSULE = "sticker_capsule"


@dataclass
class MarketEvent:
    """Represents a market-moving event."""

    event_type: EventType
    name: str
    start_date: datetime
    end_date: datetime | None = None
    expected_impact: float = 0.0  # -1.0 to +1.0 (negative = price drop)
    affected_items: list[str] = field(default_factory=list)
    affected_games: list[str] = field(default_factory=list)

    @property
    def days_until(self) -> int:
        """Days until event starts."""
        delta = self.start_date - datetime.now()
        return max(0, delta.days)

    @property
    def is_active(self) -> bool:
        """Check if event is currently active."""
        now = datetime.now()
        if self.end_date:
            return self.start_date <= now <= self.end_date
        return self.start_date <= now


@dataclass
class HoldRecommendation:
    """Recommendation for holding or selling an item."""

    item_name: str
    action: str  # "hold", "sell", "hold_partial"
    confidence: float  # 0.0 to 1.0
    reason: str
    expected_change_percent: float
    hold_duration_days: int
    related_events: list[MarketEvent] = field(default_factory=list)


class IntelligentHoldManager:
    """
    Analyzes market events and provides hold/sell recommendations.

    Features:
    - Event calendar tracking (tournaments, sales, updates)
    - Item-specific impact analysis
    - Multi-factor recommendation engine
    - Historical pattern recognition
    """

    # Known CS2 Major dates (update as needed)
    KNOWN_EVENTS = [
        # Steam Sales (approximate dates)
        {
            "type": EventType.STEAM_SALE,
            "name": "Steam Summer Sale 2026",
            "start": "2026-06-25",
            "end": "2026-07-09",
            "impact": -0.20,  # Prices typically drop 20%
            "games": ["csgo", "dota2", "tf2", "rust"],
        },
        {
            "type": EventType.STEAM_SALE,
            "name": "Steam Winter Sale 2026",
            "start": "2026-12-19",
            "end": "2027-01-02",
            "impact": -0.15,
            "games": ["csgo", "dota2", "tf2", "rust"],
        },
        # CS2 Majors 2026 (based on Valve's typical schedule)
        {
            "type": EventType.MAJOR_TOURNAMENT,
            "name": "PGL Copenhagen Major 2026",
            "start": "2026-03-15",
            "end": "2026-03-30",
            "impact": 0.25,  # Sticker prices up 25%
            "items": ["Sticker", "Capsule", "Copenhagen"],
            "games": ["csgo"],
        },
        {
            "type": EventType.MAJOR_TOURNAMENT,
            "name": "IEM Cologne Major 2026",
            "start": "2026-07-15",
            "end": "2026-07-28",
            "impact": 0.30,  # Summer major - higher impact
            "items": ["Sticker", "Capsule", "Cologne"],
            "games": ["csgo"],
        },
        # RMR Events (Regional Minor Rankings) - sticker capsules available
        {
            "type": EventType.MINOR_TOURNAMENT,
            "name": "Europe RMR Spring 2026",
            "start": "2026-02-20",
            "end": "2026-02-28",
            "impact": 0.10,  # Moderate price increase
            "items": ["Sticker", "Capsule"],
            "games": ["csgo"],
        },
        {
            "type": EventType.MINOR_TOURNAMENT,
            "name": "Americas RMR Spring 2026",
            "start": "2026-03-01",
            "end": "2026-03-08",
            "impact": 0.10,
            "items": ["Sticker", "Capsule"],
            "games": ["csgo"],
        },
        # Steam Autumn Sale
        {
            "type": EventType.STEAM_SALE,
            "name": "Steam Autumn Sale 2026",
            "start": "2026-11-25",
            "end": "2026-12-02",
            "impact": -0.18,
            "games": ["csgo", "dota2", "tf2", "rust"],
        },
        # The International (Dota 2)
        {
            "type": EventType.MAJOR_TOURNAMENT,
            "name": "The International 2026",
            "start": "2026-08-15",
            "end": "2026-08-30",
            "impact": 0.35,  # TI has huge impact on Dota 2 items
            "items": ["Immortal", "Arcana", "Collector's Cache"],
            "games": ["dota2"],
        },
    ]

    def __init__(self):
        """Initialize hold manager."""
        self.events: list[MarketEvent] = []
        self._load_known_events()

        # Item category mappings
        self.item_categories = {
            "stickers": ["Sticker |", "Autograph"],
            "cases": ["Case", "Crate"],
            "capsules": ["Capsule", "Package"],
            "knives": ["Knife", "Karambit", "Bayonet", "M9", "Butterfly"],
            "gloves": ["Gloves", "Wraps"],
        }

        # Event impact by item category
        self.category_event_impact = {
            "stickers": {
                EventType.MAJOR_TOURNAMENT: 0.30,  # +30% during majors
                EventType.STEAM_SALE: -0.10,
            },
            "cases": {
                EventType.NEW_CASE: -0.25,  # Old cases drop when new releases
                EventType.STEAM_SALE: -0.15,
                EventType.OPERATION_END: 0.20,  # Operation cases rise after end
            },
            "capsules": {
                EventType.MAJOR_TOURNAMENT: 0.40,  # Huge spike during majors
                EventType.STEAM_SALE: -0.05,
            },
            "knives": {
                EventType.STEAM_SALE: -0.10,
                EventType.GAME_UPDATE: 0.05,
            },
            "gloves": {
                EventType.STEAM_SALE: -0.08,
                EventType.NEW_CASE: -0.15,
            },
        }

        logger.info("intelligent_hold_initialized", events_loaded=len(self.events))

    def _load_known_events(self) -> None:
        """Load known market events."""
        for event_data in self.KNOWN_EVENTS:
            try:
                event = MarketEvent(
                    event_type=event_data["type"],
                    name=event_data["name"],
                    start_date=datetime.strptime(event_data["start"], "%Y-%m-%d").replace(tzinfo=UTC),
                    end_date=datetime.strptime(event_data["end"], "%Y-%m-%d").replace(tzinfo=UTC)
                    if "end" in event_data
                    else None,
                    expected_impact=event_data.get("impact", 0.0),
                    affected_items=event_data.get("items", []),
                    affected_games=event_data.get("games", []),
                )
                self.events.append(event)
            except Exception as e:
                logger.exception("event_load_error", event=event_data.get("name"), error=str(e))

    def add_event(self, event: MarketEvent) -> None:
        """Add a custom event to track."""
        self.events.append(event)
        logger.info("event_added", event_name=event.name)

    def _get_item_category(self, item_name: str) -> str | None:
        """Determine item category from name."""
        item_lower = item_name.lower()
        for category, keywords in self.item_categories.items():
            for keyword in keywords:
                if keyword.lower() in item_lower:
                    return category
        return None

    def _get_upcoming_events(
        self, days_ahead: int = 14, game: str | None = None
    ) -> list[MarketEvent]:
        """Get events happening within specified days."""
        now = datetime.now()
        future = now + timedelta(days=days_ahead)

        upcoming = []
        for event in self.events:
            # Check if event is within range
            if now <= event.start_date <= future or event.is_active:
                # Filter by game if specified
                if game and event.affected_games:
                    if game.lower() not in [g.lower() for g in event.affected_games]:
                        continue
                upcoming.append(event)

        return sorted(upcoming, key=lambda e: e.start_date)

    def _calculate_expected_change(self, item_name: str, events: list[MarketEvent]) -> float:
        """Calculate expected price change based on upcoming events."""
        if not events:
            return 0.0

        category = self._get_item_category(item_name)
        total_impact = 0.0

        for event in events:
            # Base impact from event
            impact = event.expected_impact

            # Adjust by category-specific impact if available
            if category and category in self.category_event_impact:
                category_impacts = self.category_event_impact[category]
                if event.event_type in category_impacts:
                    impact = category_impacts[event.event_type]

            # Check if item is specifically affected
            for affected in event.affected_items:
                if affected.lower() in item_name.lower():
                    impact *= 1.5  # 50% stronger impact for directly affected items
                    break

            # Weight by proximity (closer events have more impact)
            days_until = event.days_until
            if days_until == 0:  # Event is now
                weight = 1.0
            elif days_until <= 3:
                weight = 0.9
            elif days_until <= 7:
                weight = 0.7
            elif days_until <= 14:
                weight = 0.5
            else:
                weight = 0.3

            total_impact += impact * weight

        # Cap impact at reasonable levels
        return max(-0.50, min(0.50, total_impact))

    def get_recommendation(
        self,
        item_name: str,
        current_price: float,
        buy_price: float,
        game: str = "csgo",
        days_held: int = 0,
    ) -> HoldRecommendation:
        """
        Get hold/sell recommendation for an item.

        Args:
            item_name: Name of the item
            current_price: Current market price
            buy_price: Price item was bought for
            game: Game the item is from
            days_held: How long item has been held

        Returns:
            HoldRecommendation with action and reasoning
        """
        # Get upcoming events
        upcoming_events = self._get_upcoming_events(days_ahead=14, game=game)

        # Calculate expected price change
        expected_change = self._calculate_expected_change(item_name, upcoming_events)

        # Calculate current profit/loss
        current_roi = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0

        # Decision logic
        action = "sell"
        confidence = 0.5
        reason = ""
        hold_days = 0

        # Check for positive upcoming events
        if expected_change > 0.10:  # >10% expected increase
            action = "hold"
            confidence = min(0.9, 0.5 + expected_change)

            # Find nearest positive event
            positive_events = [e for e in upcoming_events if e.expected_impact > 0]
            if positive_events:
                hold_days = positive_events[0].days_until + 3  # Hold until event + 3 days
                reason = f"Expected +{expected_change * 100:.1f}% due to {positive_events[0].name}"
            else:
                reason = f"Expected +{expected_change * 100:.1f}% based on market trends"

        # Check for negative upcoming events (sell before they hit)
        elif expected_change < -0.10:  # >10% expected decrease
            action = "sell"
            confidence = min(0.9, 0.5 + abs(expected_change))

            negative_events = [e for e in upcoming_events if e.expected_impact < 0]
            if negative_events:
                reason = (
                    f"Sell before {expected_change * 100:.1f}% drop from {negative_events[0].name}"
                )
            else:
                reason = f"Expected {expected_change * 100:.1f}% price drop"

        # Check if already profitable
        elif current_roi >= 15:
            action = "sell"
            confidence = 0.7
            reason = f"Take profit: +{current_roi:.1f}% ROI achieved"

        # Item held too long without profit
        elif days_held > 7 and current_roi < 5:
            action = "sell"
            confidence = 0.6
            reason = f"Cut losses: Held {days_held} days with only {current_roi:.1f}% ROI"

        # Neutral case
        else:
            action = "hold"
            confidence = 0.4
            hold_days = 3
            reason = "No strong signals, monitor market"

        return HoldRecommendation(
            item_name=item_name,
            action=action,
            confidence=confidence,
            reason=reason,
            expected_change_percent=expected_change * 100,
            hold_duration_days=hold_days,
            related_events=upcoming_events[:3],  # Top 3 relevant events
        )

    async def analyze_inventory(
        self, inventory: list[dict[str, Any]], game: str = "csgo"
    ) -> dict[str, Any]:
        """
        Analyze entire inventory and provide recommendations.

        Args:
            inventory: List of items with name, current_price, buy_price, days_held
            game: Game for all items

        Returns:
            Analysis results with recommendations per item
        """
        recommendations = []
        hold_count = 0
        sell_count = 0
        total_expected_change = 0.0

        for item in inventory:
            rec = self.get_recommendation(
                item_name=item.get("name", "Unknown"),
                current_price=item.get("current_price", 0),
                buy_price=item.get("buy_price", 0),
                game=game,
                days_held=item.get("days_held", 0),
            )

            recommendations.append({
                "item": item.get("name"),
                "action": rec.action,
                "confidence": rec.confidence,
                "reason": rec.reason,
                "expected_change": rec.expected_change_percent,
            })

            if rec.action == "hold":
                hold_count += 1
            else:
                sell_count += 1

            total_expected_change += rec.expected_change_percent

        upcoming = self._get_upcoming_events(days_ahead=14, game=game)

        return {
            "total_items": len(inventory),
            "recommendations": recommendations,
            "summary": {
                "hold": hold_count,
                "sell": sell_count,
                "avg_expected_change": total_expected_change / len(inventory) if inventory else 0,
            },
            "upcoming_events": [
                {
                    "name": e.name,
                    "type": e.event_type.value,
                    "days_until": e.days_until,
                    "impact": e.expected_impact,
                }
                for e in upcoming[:5]
            ],
        }

    def format_telegram_message(self, recommendation: HoldRecommendation) -> str:
        """Format recommendation as Telegram message."""
        emoji = "📈" if recommendation.action == "hold" else "💰"
        action_text = "ДЕРЖАТЬ" if recommendation.action == "hold" else "ПРОДАТЬ"

        msg = f"{emoji} **{recommendation.item_name}**\n\n"
        msg += f"🎯 Рекомендация: **{action_text}**\n"
        msg += f"📊 Уверенность: {recommendation.confidence * 100:.0f}%\n"
        msg += f"📈 Ожидаемое изменение: {recommendation.expected_change_percent:+.1f}%\n"
        msg += f"💡 Причина: {recommendation.reason}\n"

        if recommendation.hold_duration_days > 0:
            msg += f"⏰ Держать дней: {recommendation.hold_duration_days}\n"

        if recommendation.related_events:
            msg += "\n📅 Ближайшие события:\n"
            for event in recommendation.related_events[:2]:
                msg += f"  • {event.name} (через {event.days_until} дн.)\n"

        return msg


# Global instance
_hold_manager: IntelligentHoldManager | None = None


def get_hold_manager() -> IntelligentHoldManager:
    """Get or create global hold manager instance."""
    global _hold_manager
    if _hold_manager is None:
        _hold_manager = IntelligentHoldManager()
    return _hold_manager
