"""Market data database models (SQLAlchemy).

Keywords for RAG:
- DMarket item storage
- CS2 skin price history
- Market capitalization tracking
- Item valuation (suggested price)
- Trade volume analytics
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, Numeric
from src.models.base import Base, UUIDType


class MarketData(Base):
    """
    Core model for storing snapshot of DMarket item listings.
    
    Use this model to track historical pricing, volume, and suggested prices
    for individual items (skins, cases, keys) across different games (CS2, Dota2, etc.).
    
    Attributes:
        item_id (str): Unique DMarket item identifier (AssetID).
        game (str): Game identifier (e.g., 'a8db' for CS2).
        item_name (str): Full market hash name of the item.
        price_usd (Numeric): Current listing price in USD.
        suggested_price_usd (Numeric): DMarket's estimated value for the item.
        price_change_24h (Numeric): Percentage price change over 24 hours.
        volume_24h (Integer): Number of items sold in last 24h.
        market_cap (Numeric): Total valuation (price * volume).
        data_source (str): Source of data (default: 'dmarket').
        raw_data (JSON): Full original API response for debugging/rehydration.
    """

    __tablename__ = "market_data"

    id = Column(UUIDType, primary_key=True, default=uuid4)
    
    # Core Identity
    item_id = Column(String(255), nullable=False, index=True, doc="Unique DMarket AssetID")
    game = Column(String(100), nullable=False, index=True, doc="Game ID (a8db/csgo)")
    item_name = Column(Text, nullable=False, index=True, doc="Market Hash Name (e.g. AK-47 | Redline (Field-Tested))")
    
    # Financials (Using Numeric for precision)
    price_usd = Column(Numeric(18, 4), nullable=False, doc="Listing price in USD")
    suggested_price_usd = Column(Numeric(18, 4), nullable=True, doc="Algorithmic suggested price")
    
    # Analytics
    price_change_24h = Column(Numeric(10, 4), nullable=True)
    volume_24h = Column(Integer, nullable=True)
    market_cap = Column(Numeric(20, 4), nullable=True)
    
    # Meta
    data_source = Column(String(50), default="dmarket", index=True)
    raw_data = Column(JSON, nullable=True, doc="Original JSON payload from API")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        return f"<MarketData(name='{self.item_name}', price={self.price_usd}, game='{self.game}')>"


class MarketDataCache(Base):
    """
    Short-term cache for API responses to reduce rate limits.
    
    Stores raw JSON responses for specific query keys.
    Useful for high-frequency endpoints like market listings or inventory.
    """

    __tablename__ = "market_data_cache"

    id = Column(UUIDType, primary_key=True, default=uuid4)
    cache_key = Column(String(500), unique=True, nullable=False, index=True, doc="Hash of query params")
    game = Column(String(50), nullable=False, index=True)
    item_hash_name = Column(String(500), nullable=True)
    data_type = Column(String(50), nullable=False, doc="Type of cached data (listings, history, etc.)")
    data = Column(JSON, nullable=False, doc="Cached JSON payload")
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)

    def __repr__(self) -> str:
        return (
            f"<MarketDataCache(key='{self.cache_key}', "
            f"game='{self.game}', type='{self.data_type}')>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "cache_key": self.cache_key,
            "game": self.game,
            "item_hash_name": self.item_hash_name,
            "data_type": self.data_type,
            "data": self.data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
