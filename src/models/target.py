"""Модель базы данных для таргетов (buy orders)."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Column, DateTime, Float, Integer, String
from src.models.base import Base


class Target(Base):
    """Модель таргета (buy order) для DMarket.

    Хранит информацию о заявках на покупку предметов пользователей.

    Attributes:
        id: Уникальный идентификатор записи
        user_id: Telegram ID пользователя
        target_id: ID таргета от DMarket API
        game: Код игры (csgo, dota2, tf2, rust)
        title: Название предмета
        price: Цена покупки в USD
        amount: Количество предметов
        status: Статус таргета (active, inactive, completed)
        created_at: Дата создания
        updated_at: Дата последнего обновления
        attributes: Дополнительные атрибуты (float, phase, pattern)

    """

    __tablename__ = "targets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    target_id = Column(String(255), unique=True, nullable=False, index=True)
    game = Column(String(50), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    price = Column(Float, nullable=False)
    amount = Column(Integer, default=1, nullable=False)
    status = Column(String(50), default="active", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    attributes = Column(JSON, nullable=True)

    def __repr__(self) -> str:
        """Строковое представление таргета."""
        return (
            f"<Target(id={self.id}, user_id={self.user_id}, "
            f"title='{self.title}', price=${self.price:.2f}, "
            f"status='{self.status}')>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать модель в словарь.

        Returns:
            Словарь с данными таргета

        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "target_id": self.target_id,
            "game": self.game,
            "title": self.title,
            "price": self.price,
            "amount": self.amount,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "attributes": self.attributes,
        }


class TradeHistory(Base):
    """История сделок пользователя.

    Attributes:
        id: Уникальный идентификатор записи
        user_id: Telegram ID пользователя
        trade_type: Тип сделки (buy, sell, target)
        item_title: Название предмета
        price: Цена сделки в USD
        profit: Прибыль от сделки в USD
        game: Код игры
        status: Статус сделки (pending, completed, failed)
        created_at: Дата создания
        completed_at: Дата завершения
        trade_metadata: Дополнительные данные о сделке

    """

    __tablename__ = "trade_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    trade_type = Column(String(50), nullable=False)
    item_title = Column(String(500), nullable=False)
    price = Column(Float, nullable=False)
    profit = Column(Float, default=0.0)
    game = Column(String(50), nullable=False)
    status = Column(String(50), default="pending", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    trade_metadata = Column(JSON, nullable=True)  # Переименовано с metadata на trade_metadata

    def __repr__(self) -> str:
        """Строковое представление записи истории."""
        return (
            f"<TradeHistory(id={self.id}, user_id={self.user_id}, "
            f"type='{self.trade_type}', title='{self.item_title}', "
            f"price=${self.price:.2f}, status='{self.status}')>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать модель в словарь.

        Returns:
            Словарь с данными сделки

        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "trade_type": self.trade_type,
            "item_title": self.item_title,
            "price": self.price,
            "profit": self.profit,
            "game": self.game,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": (self.completed_at.isoformat() if self.completed_at else None),
            "trade_metadata": self.trade_metadata,  # Переименовано
        }


class TradingSettings(Base):
    """Настройки торговли пользователя.

    Attributes:
        id: Уникальный идентификатор записи
        user_id: Telegram ID пользователя
        max_trade_value: Максимальная сумма одной сделки в USD
        daily_limit: Дневной лимит торговли в USD
        min_profit_percent: Минимальный процент прибыли
        strategy: Стратегия торговли (conservative, balanced, aggressive)
        auto_trading_enabled: Включена ли автоторговля
        games_enabled: Список включенных игр
        notifications_enabled: Включены ли уведомления
        created_at: Дата создания
        updated_at: Дата последнего обновления

    """

    __tablename__ = "trading_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True, nullable=False, index=True)
    max_trade_value = Column(Float, default=50.0)
    daily_limit = Column(Float, default=500.0)
    min_profit_percent = Column(Float, default=5.0)
    strategy = Column(String(50), default="balanced")
    auto_trading_enabled = Column(Integer, default=0)  # 0 = False, 1 = True
    games_enabled = Column(JSON, default=["csgo"])
    notifications_enabled = Column(Integer, default=1)  # 0 = False, 1 = True
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        """Строковое представление настроек."""
        return (
            f"<TradingSettings(user_id={self.user_id}, "
            f"max_trade=${self.max_trade_value:.2f}, "
            f"strategy='{self.strategy}')>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать модель в словарь.

        Returns:
            Словарь с настройками торговли

        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "max_trade_value": self.max_trade_value,
            "daily_limit": self.daily_limit,
            "min_profit_percent": self.min_profit_percent,
            "strategy": self.strategy,
            "auto_trading_enabled": bool(self.auto_trading_enabled),
            "games_enabled": self.games_enabled,
            "notifications_enabled": bool(self.notifications_enabled),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
