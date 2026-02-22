"""Модель базы данных для активных сделок (pending trades).

Этот модуль реализует персистентность для сделок, которые еще не завершены.
Бот не забудет о купленных предметах даже после перезапуска.

Ключевые возможности:
- Хранение информации о покупках с ценой закупки
- Отслеживание статуса сделки (bought, listed, sold)
- Восстановление незавершенных сделок при старте бота
- Расчет минимальной цены продажи для защиты от убытков
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, Column, DateTime, Float, Index, Integer, String

from src.models.base import Base


class PendingTradeStatus(StrEnum):
    """Статус активной сделки."""

    BOUGHT = "bought"  # Куплено, ожидает выставления
    LISTED = "listed"  # Выставлено на продажу
    ADJUSTING = "adjusting"  # Цена корректируется
    SOLD = "sold"  # Продано успешно
    CANCELLED = "cancelled"  # Отменено пользователем
    STOP_LOSS = "stop_loss"  # Продано по stop-loss
    FAlgoLED = "failed"  # Ошибка при обработке


class PendingTrade(Base):
    """Модель активной сделки для персистентного хранения.

    Эта модель гарантирует, что бот не "забудет" о купленных предметах
    после перезапуска или выключения ПК.

    Attributes:
        id: Уникальный идентификатор записи
        asset_id: ID предмета в DMarket (уникальный)
        item_id: Альтернативный ID предмета (offer_id)
        user_id: Telegram ID пользователя (опционально)
        title: Название предмета
        game: Код игры (csgo, dota2, tf2, rust)
        buy_price: Цена покупки в USD
        min_sell_price: Минимальная цена продажи (защита от убытков)
        target_sell_price: Целевая цена продажи
        current_price: Текущая цена предложения
        offer_id: ID предложения на DMarket (когда выставлено)
        status: Статус сделки
        adjustments_count: Количество корректировок цены
        created_at: Время создания записи (покупки)
        listed_at: Время выставления на продажу
        sold_at: Время продажи
        updated_at: Время последнего обновления
        metadata: Дополнительные данные (JSON)
    """

    __tablename__ = "pending_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(String(255), unique=True, nullable=False, index=True)
    item_id = Column(String(255), nullable=True, index=True)
    user_id = Column(BigInteger, nullable=True, index=True)
    title = Column(String(500), nullable=False)
    game = Column(String(50), nullable=False, default="csgo")

    # Цены в USD
    buy_price = Column(Float, nullable=False)
    min_sell_price = Column(Float, nullable=False)
    target_sell_price = Column(Float, nullable=True)
    current_price = Column(Float, nullable=True)

    # Связь с DMarket API
    offer_id = Column(String(255), nullable=True, index=True)

    # Статус и счетчики
    status = Column(String(50), default=PendingTradeStatus.BOUGHT, index=True)
    adjustments_count = Column(Integer, default=0)

    # Временные метки
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    listed_at = Column(DateTime, nullable=True)
    sold_at = Column(DateTime, nullable=True)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Дополнительные индексы для частых запросов
    __table_args__ = (
        Index("idx_pending_trades_status_created", "status", "created_at"),
        Index("idx_pending_trades_game_status", "game", "status"),
    )

    def __repr__(self) -> str:
        """Строковое представление сделки."""
        return (
            f"<PendingTrade(asset_id={self.asset_id}, title='{self.title}', "
            f"buy=${self.buy_price:.2f}, status='{self.status}')>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать модель в словарь.

        Returns:
            Словарь с данными сделки
        """
        return {
            "id": self.id,
            "asset_id": self.asset_id,
            "item_id": self.item_id,
            "user_id": self.user_id,
            "title": self.title,
            "game": self.game,
            "buy_price": self.buy_price,
            "min_sell_price": self.min_sell_price,
            "target_sell_price": self.target_sell_price,
            "current_price": self.current_price,
            "offer_id": self.offer_id,
            "status": self.status,
            "adjustments_count": self.adjustments_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "listed_at": self.listed_at.isoformat() if self.listed_at else None,
            "sold_at": self.sold_at.isoformat() if self.sold_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def calculate_profit(self, sale_price: float | None = None) -> tuple[float, float]:
        """Рассчитать прибыль от сделки.

        Args:
            sale_price: Цена продажи (используется current_price если не указана)

        Returns:
            Кортеж (прибыль в USD, процент прибыли)
        """
        price = sale_price or self.current_price or self.target_sell_price
        if not price or self.buy_price <= 0:
            return 0.0, 0.0

        profit = price - self.buy_price
        profit_percent = (profit / self.buy_price) * 100
        return round(profit, 2), round(profit_percent, 2)

    def is_profitable(self, dmarket_fee_percent: float = 7.0) -> bool:
        """Проверить, будет ли сделка прибыльной с учетом комиссии.

        Args:
            dmarket_fee_percent: Процент комиссии DMarket (по умолчанию 7%)

        Returns:
            True если сделка принесет прибыль
        """
        price = self.current_price or self.target_sell_price
        if not price:
            return False

        # Чистая прибыль после комиссии
        net_price = price * (1 - dmarket_fee_percent / 100)
        return net_price > self.buy_price

    @classmethod
    def calculate_min_sell_price(
        cls,
        buy_price: float,
        min_margin_percent: float = 5.0,
        dmarket_fee_percent: float = 7.0,
    ) -> float:
        """Рассчитать минимальную цену продажи для защиты от убытков.

        Формула: min_sell = buy_price * (1 + margin) / (1 - fee)

        Args:
            buy_price: Цена покупки в USD
            min_margin_percent: Минимальный процент маржи (по умолчанию 5%)
            dmarket_fee_percent: Процент комиссии DMarket (по умолчанию 7%)

        Returns:
            Минимальная цена продажи в USD
        """
        margin_multiplier = 1 + (min_margin_percent / 100)
        fee_multiplier = 1 - (dmarket_fee_percent / 100)

        min_price = (buy_price * margin_multiplier) / fee_multiplier
        return round(min_price, 2)
