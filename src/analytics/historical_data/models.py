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
        timestamp: When this price was recorded
        price: Price in USD (None for orderbook snapshots)
        best_bid: Best bid price in USD
        best_ask: Best ask price in USD
        volume: Number of sales (if avAlgolable)
        source: Data source (market, sales_history, aggregated)
    """

    game: str
    title: str
    timestamp: datetime
    price: Decimal | None = None
    best_bid: Decimal | None = None
    best_ask: Decimal | None = None
    volume: int = 0
    source: str = "market"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "game": self.game,
            "title": self.title,
            "price": float(self.price) if self.price is not None else None,
            "best_bid": float(self.best_bid) if self.best_bid is not None else None,
            "best_ask": float(self.best_ask) if self.best_ask is not None else None,
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
            timestamp=datetime.fromisoformat(data["timestamp"]),
            price=Decimal(str(data["price"])) if data.get("price") is not None else None,
            best_bid=Decimal(str(data["best_bid"])) if data.get("best_bid") is not None else None,
            best_ask=Decimal(str(data["best_ask"])) if data.get("best_ask") is not None else None,
            volume=data.get("volume", 0),
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

    def _get_price_val(self, p: PricePoint) -> Decimal | None:
        if p.price is not None:
            return p.price
        if p.best_bid is not None and p.best_ask is not None:
            return (p.best_bid + p.best_ask) / Decimal(2)
        return p.best_ask or p.best_bid

    @property
    def average_price(self) -> Decimal:
        """Calculate average price across all points."""
        prices = [val for p in self.points if (val := self._get_price_val(p)) is not None]
        if not prices:
            return Decimal(0)
        return Decimal(sum(prices)) / Decimal(len(prices))

    @property
    def min_price(self) -> Decimal:
        """Get minimum price."""
        prices = [val for p in self.points if (val := self._get_price_val(p)) is not None]
        if not prices:
            return Decimal(0)
        return min(prices)

    @property
    def max_price(self) -> Decimal:
        """Get maximum price."""
        prices = [val for p in self.points if (val := self._get_price_val(p)) is not None]
        if not prices:
            return Decimal(0)
        return max(prices)

    @property
    def total_volume(self) -> int:
        """Get total volume across all points."""
        return sum(p.volume for p in self.points)

    @property
    def price_volatility(self) -> float:
        """Calculate price volatility (standard deviation / mean)."""
        prices = [float(val) for p in self.points if (val := self._get_price_val(p)) is not None]
        if len(prices) < 2:
            return 0.0

        mean = sum(prices) / len(prices)
        if mean == 0:
            return 0.0

        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        std_dev = variance**0.5
        return float(std_dev / mean)


__all__ = ["PricePoint", "PriceHistory"]
