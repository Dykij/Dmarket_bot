"""
models.py — Dataclasses for historical price data.

Two simple immutable-shaped records that backtesters consume:
    PricePoint   — one observation (game, title, price, volume, ts, source)
    PriceHistory — bundle of PricePoints with computed properties (avg/min/max
                   /volume/volatility).

The dataclasses intentionally use Decimal for price to avoid float drift
during aggregation in `PriceHistory.average_price`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


@dataclass
class PricePoint:
    """A single price point in historical data.

    Attributes:
        game: Game code (csgo, dota2, etc.)
        title: Item name
        price: Price in USD
        volume: Number of sales (if avAlgolable)
        timestamp: When this price was recorded
        source: Data source (market, sales_history, aggregated)
    """

    game: str
    title: str
    price: Decimal
    timestamp: datetime
    volume: int = 0
    source: str = "market"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "game": self.game,
            "title": self.title,
            "price": float(self.price),
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PricePoint:
        """Create from dictionary."""
        return cls(
            game=data["game"],
            title=data["title"],
            price=Decimal(str(data["price"])),
            volume=data.get("volume", 0),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data.get("source", "market"),
        )


@dataclass
class PriceHistory:
    """Historical price data for an item.

    Attributes:
        game: Game code
        title: Item name
        points: List of price points sorted by timestamp
        collected_at: When this history was collected
    """

    game: str
    title: str
    points: list[PricePoint] = field(default_factory=list)
    collected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def average_price(self) -> Decimal:
        """Calculate average price across all points."""
        if not self.points:
            return Decimal(0)
        return Decimal(sum(p.price for p in self.points)) / Decimal(len(self.points))

    @property
    def min_price(self) -> Decimal:
        """Get minimum price."""
        if not self.points:
            return Decimal(0)
        return min(p.price for p in self.points)

    @property
    def max_price(self) -> Decimal:
        """Get maximum price."""
        if not self.points:
            return Decimal(0)
        return max(p.price for p in self.points)

    @property
    def total_volume(self) -> int:
        """Get total volume across all points."""
        return sum(p.volume for p in self.points)

    @property
    def price_volatility(self) -> float:
        """Calculate price volatility (standard deviation / mean)."""
        if len(self.points) < 2:
            return 0.0

        prices = [float(p.price) for p in self.points]
        mean = sum(prices) / len(prices)
        if mean == 0:
            return 0.0

        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        std_dev = variance**0.5
        return float(std_dev / mean)


__all__ = ["PricePoint", "PriceHistory"]
