"""User models."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, String, Text

from src.models.base import Base, UUIDType


class User(Base):
    """User model.

    Stores information about bot users.
    """

    __tablename__ = "users"

    id = Column(UUIDType, primary_key=True, default=uuid4)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    language_code = Column(String(10), default="en")
    is_active = Column(Boolean, default=True, index=True)
    is_admin = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False, index=True)
    dmarket_api_key_encrypted = Column(Text, nullable=True)
    dmarket_secret_key_encrypted = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    last_activity = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    notes = Column(Text, nullable=True)

    def __repr__(self) -> str:
        """String representation."""
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username='{self.username}')>"

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "telegram_id": self.telegram_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "language_code": self.language_code,
            "is_active": self.is_active,
            "is_admin": self.is_admin,
            "is_banned": self.is_banned,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_activity": (
                self.last_activity.isoformat() if self.last_activity else None
            ),
        }


class UserSettings(Base):
    """User settings model.

    Stores user's bot preferences and settings.
    """

    __tablename__ = "user_settings"

    id = Column(UUIDType, primary_key=True, default=uuid4)
    user_id = Column(UUIDType, nullable=False, index=True)
    default_game = Column(String(50), default="csgo")
    notifications_enabled = Column(Boolean, default=True)
    price_alerts_enabled = Column(Boolean, default=True)
    arbitrage_alert_enabled = Column(Boolean, default=True)
    min_profit_percent = Column(Float, default=5.0)
    preferred_currency = Column(String(10), default="USD")
    language = Column(String(10), default="en")
    timezone = Column(String(50), default="UTC")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<UserSettings(user_id={self.user_id}, game='{self.default_game}')>"

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "default_game": self.default_game,
            "notifications_enabled": self.notifications_enabled,
            "price_alerts_enabled": self.price_alerts_enabled,
            "arbitrage_alert_enabled": self.arbitrage_alert_enabled,
            "min_profit_percent": self.min_profit_percent,
            "preferred_currency": self.preferred_currency,
            "language": self.language,
            "timezone": self.timezone,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
