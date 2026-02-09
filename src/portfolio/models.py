"""Portfolio data models.

Defines data structures for portfolio management.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class ItemCategory(StrEnum):
    """Category of item for diversification analysis."""

    WEAPON = "weapon"
    KNIFE = "knife"
    GLOVES = "gloves"
    STICKER = "sticker"
    CASE = "case"
    KEY = "key"
    AGENT = "agent"
    MUSIC_KIT = "music_kit"
    GRAFFITI = "graffiti"
    PATCH = "patch"
    COLLECTIBLE = "collectible"
    OTHER = "other"


class ItemRarity(StrEnum):
    """Rarity tier of item."""

    CONSUMER = "consumer"
    INDUSTRIAL = "industrial"
    MIL_SPEC = "mil_spec"
    RESTRICTED = "restricted"
    CLASSIFIED = "classified"
    COVERT = "covert"
    CONTRABAND = "contraband"  # Knife, Gloves
    EXTRAORDINARY = "extraordinary"  # Special items


@dataclass
class PortfolioItem:
    """A single item in the portfolio.

    Attributes:
        item_id: DMarket item ID
        title: Item name
        game: Game code (csgo, dota2, etc.)
        buy_price: Purchase price in USD
        current_price: Current market price
        quantity: Number of items
        purchased_at: When item was purchased
        category: Item category for diversification
        rarity: Item rarity tier
        float_value: Float value for CS2 items (0.0-1.0)
    """

    item_id: str
    title: str
    game: str
    buy_price: Decimal
    current_price: Decimal
    quantity: int = 1
    purchased_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    category: ItemCategory = ItemCategory.OTHER
    rarity: ItemRarity = ItemRarity.MIL_SPEC
    float_value: float | None = None

    @property
    def pnl(self) -> Decimal:
        """Calculate profit/loss for this item.

        Returns:
            Profit (positive) or loss (negative) in USD
        """
        return (self.current_price - self.buy_price) * self.quantity

    @property
    def pnl_percent(self) -> float:
        """Calculate profit/loss as percentage.

        Returns:
            Percentage change from buy price
        """
        if self.buy_price == 0:
            return 0.0
        return float((self.current_price - self.buy_price) / self.buy_price * 100)

    @property
    def total_cost(self) -> Decimal:
        """Total cost of this position."""
        return self.buy_price * self.quantity

    @property
    def current_value(self) -> Decimal:
        """Current market value of this position."""
        return self.current_price * self.quantity

    @property
    def holding_days(self) -> int:
        """Number of days this item has been held."""
        return (datetime.now(UTC) - self.purchased_at).days

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "item_id": self.item_id,
            "title": self.title,
            "game": self.game,
            "buy_price": float(self.buy_price),
            "current_price": float(self.current_price),
            "quantity": self.quantity,
            "purchased_at": self.purchased_at.isoformat(),
            "category": self.category.value,
            "rarity": self.rarity.value,
            "float_value": self.float_value,
            "pnl": float(self.pnl),
            "pnl_percent": self.pnl_percent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PortfolioItem:
        """Create from dictionary."""
        return cls(
            item_id=data["item_id"],
            title=data["title"],
            game=data["game"],
            buy_price=Decimal(str(data["buy_price"])),
            current_price=Decimal(str(data["current_price"])),
            quantity=data.get("quantity", 1),
            purchased_at=(
                datetime.fromisoformat(data["purchased_at"])
                if "purchased_at" in data
                else datetime.now(UTC)
            ),
            category=ItemCategory(data.get("category", "other")),
            rarity=ItemRarity(data.get("rarity", "mil_spec")),
            float_value=data.get("float_value"),
        )


@dataclass
class PortfolioMetrics:
    """Calculated metrics for a portfolio.

    Attributes:
        total_value: Current total value
        total_cost: Total purchase cost
        total_pnl: Total profit/loss
        total_pnl_percent: Total P&L as percentage
        items_count: Number of unique items
        total_quantity: Total number of items
        best_performer: Item with highest P&L %
        worst_performer: Item with lowest P&L %
        avg_holding_days: Average days items held
        realized_pnl: P&L from closed positions
        unrealized_pnl: P&L from open positions
    """

    total_value: Decimal
    total_cost: Decimal
    total_pnl: Decimal
    total_pnl_percent: float
    items_count: int
    total_quantity: int
    best_performer: str | None = None
    best_performer_pnl: float = 0.0
    worst_performer: str | None = None
    worst_performer_pnl: float = 0.0
    avg_holding_days: float = 0.0
    realized_pnl: Decimal = Decimal(0)
    unrealized_pnl: Decimal = Decimal(0)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_value": float(self.total_value),
            "total_cost": float(self.total_cost),
            "total_pnl": float(self.total_pnl),
            "total_pnl_percent": self.total_pnl_percent,
            "items_count": self.items_count,
            "total_quantity": self.total_quantity,
            "best_performer": self.best_performer,
            "best_performer_pnl": self.best_performer_pnl,
            "worst_performer": self.worst_performer,
            "worst_performer_pnl": self.worst_performer_pnl,
            "avg_holding_days": self.avg_holding_days,
            "realized_pnl": float(self.realized_pnl),
            "unrealized_pnl": float(self.unrealized_pnl),
        }


@dataclass
class PortfolioSnapshot:
    """A point-in-time snapshot of portfolio state.

    Used for historical tracking and performance analysis.
    """

    timestamp: datetime
    total_value: Decimal
    total_cost: Decimal
    items_count: int

    @property
    def pnl(self) -> Decimal:
        """P&L at snapshot time."""
        return self.total_value - self.total_cost

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_value": float(self.total_value),
            "total_cost": float(self.total_cost),
            "items_count": self.items_count,
            "pnl": float(self.pnl),
        }


@dataclass
class Portfolio:
    """User's portfolio of items.

    Attributes:
        user_id: Telegram user ID
        items: List of portfolio items
        snapshots: Historical snapshots
        created_at: When portfolio was created
        updated_at: Last update time
    """

    user_id: int
    items: list[PortfolioItem] = field(default_factory=list)
    snapshots: list[PortfolioSnapshot] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def add_item(self, item: PortfolioItem) -> None:
        """Add item to portfolio.

        If item already exists, increases quantity.
        """
        # Check if item exists
        for existing in self.items:
            if existing.item_id == item.item_id:
                # Update average cost
                total_cost = existing.buy_price * existing.quantity + item.buy_price * item.quantity
                existing.quantity += item.quantity
                existing.buy_price = total_cost / existing.quantity
                self.updated_at = datetime.now(UTC)
                return

        self.items.append(item)
        self.updated_at = datetime.now(UTC)

    def remove_item(self, item_id: str, quantity: int = 1) -> PortfolioItem | None:
        """Remove item from portfolio.

        Args:
            item_id: ID of item to remove
            quantity: Number to remove (default: 1)

        Returns:
            Removed item or None if not found
        """
        for i, item in enumerate(self.items):
            if item.item_id == item_id:
                if item.quantity <= quantity:
                    # Remove completely
                    removed = self.items.pop(i)
                    self.updated_at = datetime.now(UTC)
                    return removed
                # Decrease quantity
                item.quantity -= quantity
                self.updated_at = datetime.now(UTC)
                return PortfolioItem(
                    item_id=item.item_id,
                    title=item.title,
                    game=item.game,
                    buy_price=item.buy_price,
                    current_price=item.current_price,
                    quantity=quantity,
                )
        return None

    def get_item(self, item_id: str) -> PortfolioItem | None:
        """Get item by ID."""
        for item in self.items:
            if item.item_id == item_id:
                return item
        return None

    def update_prices(self, prices: dict[str, Decimal]) -> None:
        """Update current prices for items.

        Args:
            prices: Dict of item_id -> current_price
        """
        for item in self.items:
            if item.item_id in prices:
                item.current_price = prices[item.item_id]
        self.updated_at = datetime.now(UTC)

    def calculate_metrics(self) -> PortfolioMetrics:
        """Calculate portfolio metrics.

        Returns:
            PortfolioMetrics with calculated values
        """
        if not self.items:
            return PortfolioMetrics(
                total_value=Decimal(0),
                total_cost=Decimal(0),
                total_pnl=Decimal(0),
                total_pnl_percent=0.0,
                items_count=0,
                total_quantity=0,
            )

        total_value = sum(item.current_value for item in self.items)
        total_cost = sum(item.total_cost for item in self.items)
        total_pnl = total_value - total_cost
        total_pnl_percent = float(total_pnl / total_cost * 100) if total_cost > 0 else 0.0

        # Find best and worst performers
        best = max(self.items, key=lambda x: x.pnl_percent)
        worst = min(self.items, key=lambda x: x.pnl_percent)

        # Calculate average holding days
        total_holding_days = sum(item.holding_days for item in self.items)
        avg_holding_days = total_holding_days / len(self.items)

        return PortfolioMetrics(
            total_value=total_value,
            total_cost=total_cost,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
            items_count=len(self.items),
            total_quantity=sum(item.quantity for item in self.items),
            best_performer=best.title,
            best_performer_pnl=best.pnl_percent,
            worst_performer=worst.title,
            worst_performer_pnl=worst.pnl_percent,
            avg_holding_days=avg_holding_days,
            unrealized_pnl=total_pnl,
        )

    def take_snapshot(self) -> PortfolioSnapshot:
        """Take a snapshot of current portfolio state."""
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(UTC),
            total_value=sum(item.current_value for item in self.items),
            total_cost=sum(item.total_cost for item in self.items),
            items_count=len(self.items),
        )
        self.snapshots.append(snapshot)

        # Keep only last 365 snapshots
        if len(self.snapshots) > 365:
            self.snapshots = self.snapshots[-365:]

        return snapshot

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "items": [item.to_dict() for item in self.items],
            "snapshots": [s.to_dict() for s in self.snapshots],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Portfolio:
        """Create from dictionary."""
        portfolio = cls(
            user_id=data["user_id"],
            created_at=datetime.fromisoformat(
                data.get("created_at", datetime.now(UTC).isoformat())
            ),
            updated_at=datetime.fromisoformat(
                data.get("updated_at", datetime.now(UTC).isoformat())
            ),
        )
        portfolio.items = [PortfolioItem.from_dict(item) for item in data.get("items", [])]
        return portfolio


__all__ = [
    "ItemCategory",
    "ItemRarity",
    "Portfolio",
    "PortfolioItem",
    "PortfolioMetrics",
    "PortfolioSnapshot",
]
