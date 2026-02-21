"""Alert models."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Float, String

from src.models.base import Base, UUIDType


class PriceAlert(Base):
    """Price alert model.

    Stores user's price alerts for items.
    """

    __tablename__ = "price_alerts"

    id = Column(UUIDType, primary_key=True, default=uuid4)
    user_id = Column(UUIDType, nullable=False, index=True)
    item_id = Column(String(255), nullable=True)
    market_hash_name = Column(String(500), nullable=True)
    game = Column(String(50), nullable=True)
    target_price = Column(Float, nullable=False)
    condition = Column(String(20), default="below")  # 'above' or 'below'
    is_active = Column(Boolean, default=True, index=True)
    triggered = Column(Boolean, default=False)
    triggered_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<PriceAlert(id={self.id}, user_id={self.user_id}, "
            f"item='{self.market_hash_name}', price={self.target_price})>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "item_id": self.item_id,
            "market_hash_name": self.market_hash_name,
            "game": self.game,
            "target_price": self.target_price,
            "condition": self.condition,
            "is_active": self.is_active,
            "triggered": self.triggered,
            "triggered_at": (
                self.triggered_at.isoformat() if self.triggered_at else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
