"""
Market History Models - Database models for historical market data.

Stores snapshots of market data for ML trAlgoning and backtesting.
"""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class MarketSnapshot(Base):
    """Market data snapshot at a specific point in time."""

    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_sales: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    games_data: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )  # Flexible JSON storage

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<MarketSnapshot(timestamp={self.timestamp}, "
            f"items={self.total_items}, sales={self.total_sales})>"
        )


class ItemPriceHistory(Base):
    """Price history for individual items."""

    __tablename__ = "item_price_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[str] = mapped_column(nullable=False, index=True)  # DMarket item ID
    item_title: Mapped[str] = mapped_column(nullable=False)
    game: Mapped[str] = mapped_column(nullable=False, index=True)

    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)  # Price in cents
    suggested_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    in_market: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # Items avAlgolable
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<ItemPriceHistory(item={self.item_title}, "
            f"price=${self.price_cents / 100:.2f}, "
            f"timestamp={self.timestamp})>"
        )


class ArbitrageTrade(Base):
    """Historical record of arbitrage trades (for ML trAlgoning)."""

    __tablename__ = "arbitrage_trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    item_id: Mapped[str] = mapped_column(nullable=False)
    item_title: Mapped[str] = mapped_column(nullable=False)
    game: Mapped[str] = mapped_column(nullable=False)

    buy_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    sell_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    profit_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    profit_margin_percent: Mapped[float] = mapped_column(nullable=False)

    # ML features at time of trade
    liquidity_score: Mapped[float | None] = mapped_column(nullable=True)
    price_volatility: Mapped[float | None] = mapped_column(nullable=True)
    sales_history_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_on_market_hours: Mapped[float | None] = mapped_column(nullable=True)
    market_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Outcome
    success: Mapped[bool] = mapped_column(
        nullable=False, default=False
    )  # Did trade succeed?
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    def __repr__(self) -> str:
        """String representation."""
        status = "✅" if self.success else "❌"
        return (
            f"<ArbitrageTrade({status} {self.item_title}, "
            f"profit=${self.profit_cents / 100:.2f}, "
            f"margin={self.profit_margin_percent:.2f}%)>"
        )
