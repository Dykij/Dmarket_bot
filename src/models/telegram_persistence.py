"""Model for Telegram bot persistence storage."""

from sqlalchemy import Column, String, JSON, BigInteger
from src.models.base import Base

class TelegramPersistence(Base):
    """Stores bot_data, chat_data, and user_data for Telegram bot."""
    
    __tablename__ = "telegram_persistence"
    
    # primary key is a combination of type and id
    # type can be 'bot', 'chat', or 'user'
    key = Column(String(100), primary_key=True)
    data = Column(JSON, nullable=False, default={})

    def __repr__(self) -> str:
        return f"<TelegramPersistence(key='{self.key}')>"
