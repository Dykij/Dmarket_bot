"""Steam Sales Protector - защита от падения цен во время распродаж.

Этот модуль отслеживает календарь распродаж Steam и автоматически
переводит бота в защитный режим перед крупными событиями.

Режимы работы:
1. NORMAL - обычный арбитраж
2. PRE_SALE - за 3 дня до распродажи:
   - Прекращаем покупки
   - Снижаем цены на 2% для быстрой продажи
3. SALE - во время распродажи:
   - Агрессивные закупки со скидкой 25%+
   - Покупаем ликвидные предметы (кейсы, ключи)
4. POST_SALE - 3 дня после распродажи:
   - Постепенное возвращение к нормальному режиму

Календарь распродаж Steam:
- Steam Summer Sale (июнь-июль)
- Steam Autumn Sale (ноябрь)
- Steam Winter Sale (декабрь)
- Steam Spring Sale (март)
- Halloween Sale (октябрь)
- Lunar New Year Sale (февраль)

Использование:
    ```python
    from src.dmarket.steam_sales_protector import SteamSalesProtector

    protector = SteamSalesProtector()

    # Проверить текущий режим
    mode = protector.get_current_mode()
    if mode.should_stop_buying:
        # Прекратить покупки
        pass

    # Получить модификаторы
    modifiers = protector.get_price_modifiers()
    ```
"""

from __future__ import annotations

import logging
import operator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


def _get_today_utc() -> date:
    """Get current date in UTC timezone."""
    return datetime.now(UTC).date()


class SaleMode(StrEnum):
    """Режим работы относительно распродажи."""

    NORMAL = "normal"  # Обычный режим
    PRE_SALE = "pre_sale"  # За 3 дня до распродажи
    SALE = "sale"  # Во время распродажи
    POST_SALE = "post_sale"  # После распродажи


class SaleType(StrEnum):
    """Тип распродажи Steam."""

    SUMMER = "summer"  # Летняя распродажа
    AUTUMN = "autumn"  # Осенняя распродажа
    WINTER = "winter"  # Зимняя распродажа
    SPRING = "spring"  # Весенняя распродажа
    HALLOWEEN = "halloween"  # Хэллоуин
    LUNAR_NEW_YEAR = "lunar_new_year"  # Лунный новый год
    PUBLISHER = "publisher"  # Издательские распродажи
    OTHER = "other"  # Другие


@dataclass
class SaleEvent:
    """Событие распродажи Steam."""

    name: str
    sale_type: SaleType
    start_date: date
    end_date: date
    expected_discount_percent: float = 15.0  # Ожидаемое падение цен на скины
    is_major: bool = True  # Крупная распродажа

    @property
    def duration_days(self) -> int:
        """Длительность распродажи в днях."""
        return (self.end_date - self.start_date).days + 1

    def is_active(self, current_date: date | None = None) -> bool:
        """Активна ли распродажа сейчас."""
        if current_date is None:
            current_date = _get_today_utc()
        return self.start_date <= current_date <= self.end_date

    def days_until_start(self, current_date: date | None = None) -> int:
        """Дней до начала распродажи."""
        if current_date is None:
            current_date = _get_today_utc()
        return (self.start_date - current_date).days

    def days_since_end(self, current_date: date | None = None) -> int:
        """Дней после окончания распродажи."""
        if current_date is None:
            current_date = _get_today_utc()
        return (current_date - self.end_date).days


@dataclass
class SaleModeStatus:
    """Текущий статус режима распродажи."""

    mode: SaleMode
    active_sale: SaleEvent | None = None
    upcoming_sale: SaleEvent | None = None

    # Флаги действий
    should_stop_buying: bool = False  # Прекратить покупки
    should_liquidate: bool = False  # Распродать инвентарь
    should_buy_aggressively: bool = False  # Агрессивные закупки

    # Модификаторы
    sell_price_modifier: float = 1.0  # Множитель цены продажи (1.0 = без изменений)
    buy_discount_threshold: float = 0.0  # Минимальная скидка для покупки

    # Информация
    reason: str = ""
    days_until_event: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            "mode": self.mode,
            "active_sale": self.active_sale.name if self.active_sale else None,
            "upcoming_sale": self.upcoming_sale.name if self.upcoming_sale else None,
            "should_stop_buying": self.should_stop_buying,
            "should_liquidate": self.should_liquidate,
            "should_buy_aggressively": self.should_buy_aggressively,
            "sell_price_modifier": self.sell_price_modifier,
            "buy_discount_threshold": self.buy_discount_threshold,
            "reason": self.reason,
        }


@dataclass
class ProtectorConfig:
    """Конфигурация защитника от распродаж."""

    # Временные окна (дни)
    pre_sale_days: int = 3  # За сколько дней начинаем готовиться
    post_sale_days: int = 3  # Сколько дней после распродажи ждем
    major_sale_pre_days: int = 5  # Для крупных распродаж готовимся раньше

    # Модификаторы цен
    pre_sale_price_reduction: float = 0.02  # -2% на цены перед распродажей
    sale_buy_min_discount: float = 0.25  # Минимум 25% скидка для покупки
    post_sale_price_recovery: float = 0.98  # 98% от нормальной цены после
    major_sale_price_reduction: float = 0.05  # -5% для крупных распродаж

    # Лимиты
    max_inventory_before_sale: int = 5  # Максимум вещей перед распродажей
    enable_aggressive_buying_on_sale: bool = True  # Агрессивные закупки

    # Уведомления
    notify_days_before: list[int] = field(default_factory=lambda: [7, 3, 1])

    # Автоматическое восстановление после распродажи
    auto_recovery_enabled: bool = True
    recovery_price_step: float = 0.01  # +1% каждый день после распродажи


class SteamSalesProtector:
    """Защитник от падения цен во время распродаж Steam.

    Отслеживает календарь распродаж и автоматически корректирует
    стратегию торговли для защиты капитала.
    """

    def __init__(self, config: ProtectorConfig | None = None) -> None:
        """Инициализация защитника.

        Args:
            config: Конфигурация (опционально)
        """
        self.config = config or ProtectorConfig()
        self._sales_calendar: list[SaleEvent] = []
        self._load_sales_calendar()

        logger.info(
            "SteamSalesProtector initialized: "
            f"pre_sale_days={self.config.pre_sale_days}, "
            f"events_loaded={len(self._sales_calendar)}"
        )

    def _load_sales_calendar(self) -> None:
        """Загрузить календарь распродаж Steam на 2026 год.

        Даты основаны на исторических данных Steam.
        """
        year = 2026

        self._sales_calendar = [
            # Lunar New Year Sale (февраль)
            SaleEvent(
                name="Lunar New Year Sale 2026",
                sale_type=SaleType.LUNAR_NEW_YEAR,
                start_date=date(year, 2, 10),
                end_date=date(year, 2, 17),
                expected_discount_percent=10.0,
                is_major=False,
            ),
            # Spring Sale (март)
            SaleEvent(
                name="Spring Sale 2026",
                sale_type=SaleType.SPRING,
                start_date=date(year, 3, 14),
                end_date=date(year, 3, 21),
                expected_discount_percent=12.0,
                is_major=False,
            ),
            # Summer Sale (июнь-июль) - MAJOR
            SaleEvent(
                name="Summer Sale 2026",
                sale_type=SaleType.SUMMER,
                start_date=date(year, 6, 25),
                end_date=date(year, 7, 9),
                expected_discount_percent=20.0,
                is_major=True,
            ),
            # Halloween Sale (октябрь)
            SaleEvent(
                name="Halloween Sale 2026",
                sale_type=SaleType.HALLOWEEN,
                start_date=date(year, 10, 28),
                end_date=date(year, 11, 1),
                expected_discount_percent=10.0,
                is_major=False,
            ),
            # Autumn Sale (ноябрь) - MAJOR
            SaleEvent(
                name="Autumn Sale 2026",
                sale_type=SaleType.AUTUMN,
                start_date=date(year, 11, 25),
                end_date=date(year, 12, 2),
                expected_discount_percent=18.0,
                is_major=True,
            ),
            # Winter Sale (декабрь) - MAJOR
            SaleEvent(
                name="Winter Sale 2026",
                sale_type=SaleType.WINTER,
                start_date=date(year, 12, 19),
                end_date=date(year + 1, 1, 2),
                expected_discount_percent=25.0,
                is_major=True,
            ),
        ]

        # Добавляем 2025 год для тестирования
        self._sales_calendar.extend(
            [
                SaleEvent(
                    name="Winter Sale 2025",
                    sale_type=SaleType.WINTER,
                    start_date=date(2025, 12, 19),
                    end_date=date(2026, 1, 2),
                    expected_discount_percent=25.0,
                    is_major=True,
                ),
            ]
        )

    def add_sale_event(self, event: SaleEvent) -> None:
        """Добавить событие распродажи вручную.

        Args:
            event: Событие распродажи
        """
        self._sales_calendar.append(event)
        self._sales_calendar.sort(key=lambda e: e.start_date)
        logger.info(f"Sale event added: {event.name}")

    def get_active_sale(self, current_date: date | None = None) -> SaleEvent | None:
        """Получить активную распродажу.

        Args:
            current_date: Текущая дата (опционально)

        Returns:
            Активное событие или None
        """
        if current_date is None:
            current_date = _get_today_utc()

        for sale in self._sales_calendar:
            if sale.is_active(current_date):
                return sale
        return None

    def get_upcoming_sale(
        self,
        current_date: date | None = None,
        days_ahead: int = 14,
    ) -> SaleEvent | None:
        """Получить ближайшую предстоящую распродажу.

        Args:
            current_date: Текущая дата
            days_ahead: Смотреть на сколько дней вперед

        Returns:
            Ближайшее событие или None
        """
        if current_date is None:
            current_date = _get_today_utc()

        for sale in self._sales_calendar:
            days_until = sale.days_until_start(current_date)
            if 0 < days_until <= days_ahead:
                return sale
        return None

    def get_recent_sale(
        self,
        current_date: date | None = None,
        days_back: int = 7,
    ) -> SaleEvent | None:
        """Получить недавно завершившуюся распродажу.

        Args:
            current_date: Текущая дата
            days_back: Смотреть на сколько дней назад

        Returns:
            Недавнее событие или None
        """
        if current_date is None:
            current_date = _get_today_utc()

        for sale in reversed(self._sales_calendar):
            days_since = sale.days_since_end(current_date)
            if 0 < days_since <= days_back:
                return sale
        return None

    def get_current_mode(self, current_date: date | None = None) -> SaleModeStatus:
        """Получить текущий режим работы.

        Args:
            current_date: Текущая дата

        Returns:
            SaleModeStatus с полной информацией
        """
        if current_date is None:
            current_date = _get_today_utc()

        # 1. Проверяем активную распродажу
        active_sale = self.get_active_sale(current_date)
        if active_sale:
            return SaleModeStatus(
                mode=SaleMode.SALE,
                active_sale=active_sale,
                should_stop_buying=False,  # Во время распродажи наоборот покупаем
                should_liquidate=False,
                should_buy_aggressively=self.config.enable_aggressive_buying_on_sale,
                sell_price_modifier=1.0,  # Не меняем цены продажи
                buy_discount_threshold=self.config.sale_buy_min_discount,
                reason=f"Active sale: {active_sale.name}. Aggressive buying mode with {self.config.sale_buy_min_discount * 100:.0f}%+ discount threshold.",
            )

        # 2. Проверяем приближающуюся распродажу
        upcoming_sale = self.get_upcoming_sale(
            current_date, days_ahead=self.config.pre_sale_days
        )
        if upcoming_sale:
            days_until = upcoming_sale.days_until_start(current_date)
            return SaleModeStatus(
                mode=SaleMode.PRE_SALE,
                upcoming_sale=upcoming_sale,
                should_stop_buying=True,
                should_liquidate=True,
                should_buy_aggressively=False,
                sell_price_modifier=1.0 - self.config.pre_sale_price_reduction,
                buy_discount_threshold=0.0,
                reason=f"Upcoming sale: {upcoming_sale.name} in {days_until} days. Liquidating inventory.",
                days_until_event=days_until,
            )

        # 3. Проверяем недавно завершившуюся распродажу
        recent_sale = self.get_recent_sale(
            current_date, days_back=self.config.post_sale_days
        )
        if recent_sale:
            days_since = recent_sale.days_since_end(current_date)
            return SaleModeStatus(
                mode=SaleMode.POST_SALE,
                active_sale=recent_sale,
                should_stop_buying=False,
                should_liquidate=False,
                should_buy_aggressively=False,
                sell_price_modifier=self.config.post_sale_price_recovery,
                buy_discount_threshold=0.0,
                reason=f"Post-sale recovery: {recent_sale.name} ended {days_since} days ago. Gradual price normalization.",
            )

        # 4. Нормальный режим
        next_sale = self.get_upcoming_sale(current_date, days_ahead=30)
        return SaleModeStatus(
            mode=SaleMode.NORMAL,
            upcoming_sale=next_sale,
            should_stop_buying=False,
            should_liquidate=False,
            should_buy_aggressively=False,
            sell_price_modifier=1.0,
            buy_discount_threshold=0.0,
            reason="Normal trading mode. No sales affecting market.",
            days_until_event=(
                next_sale.days_until_start(current_date) if next_sale else 0
            ),
        )

    def get_price_modifiers(self, current_date: date | None = None) -> dict[str, float]:
        """Получить модификаторы цен для текущего режима.

        Args:
            current_date: Текущая дата

        Returns:
            Словарь с модификаторами
        """
        status = self.get_current_mode(current_date)

        return {
            "sell_price_modifier": status.sell_price_modifier,
            "buy_discount_threshold": status.buy_discount_threshold,
            "mode": status.mode,
        }

    def should_buy_item(
        self,
        item_discount_percent: float,
        current_date: date | None = None,
    ) -> tuple[bool, str]:
        """Проверить, можно ли покупать предмет.

        Args:
            item_discount_percent: Скидка на предмет (0-100)
            current_date: Текущая дата

        Returns:
            Tuple of (should_buy, reason)
        """
        status = self.get_current_mode(current_date)

        if status.should_stop_buying:
            return False, f"Buying paused: {status.reason}"

        if status.buy_discount_threshold > 0:
            if item_discount_percent < status.buy_discount_threshold * 100:
                return (
                    False,
                    (
                        f"Discount {item_discount_percent:.1f}% below threshold "
                        f"{status.buy_discount_threshold * 100:.0f}%"
                    ),
                )

        return True, "OK to buy"

    def get_all_sales(self) -> list[SaleEvent]:
        """Получить список всех запланированных распродаж.

        Returns:
            Список событий
        """
        return sorted(self._sales_calendar, key=lambda e: e.start_date)

    def get_next_notification_dates(
        self,
        current_date: date | None = None,
    ) -> list[tuple[date, SaleEvent, int]]:
        """Получить даты следующих уведомлений.

        Args:
            current_date: Текущая дата

        Returns:
            Список (дата, событие, дней до события)
        """
        if current_date is None:
            current_date = _get_today_utc()

        notifications: list[tuple[date, SaleEvent, int]] = []

        for sale in self._sales_calendar:
            for days_before in self.config.notify_days_before:
                notify_date = sale.start_date - timedelta(days=days_before)
                if notify_date >= current_date:
                    notifications.append((notify_date, sale, days_before))

        return sorted(notifications, key=operator.itemgetter(0))

    def format_status_message(self, current_date: date | None = None) -> str:
        """Форматировать статус для отображения в Telegram.

        Args:
            current_date: Текущая дата

        Returns:
            Форматированное сообщение
        """
        status = self.get_current_mode(current_date)

        mode_emoji = {
            SaleMode.NORMAL: "🟢",
            SaleMode.PRE_SALE: "🟡",
            SaleMode.SALE: "🔴",
            SaleMode.POST_SALE: "🟠",
        }

        lines = [
            f"{mode_emoji.get(status.mode, '⚪')} **Market Mode: {status.mode.upper()}**",
            "",
        ]

        if status.active_sale:
            lines.extend(
                (
                    f"📢 Active: {status.active_sale.name}",
                    f"   Expected price drop: -{status.active_sale.expected_discount_percent:.0f}%",
                )
            )

        if status.upcoming_sale and status.days_until_event > 0:
            lines.extend(
                (
                    f"⏰ Upcoming: {status.upcoming_sale.name}",
                    f"   Starts in: {status.days_until_event} days",
                )
            )

        lines.extend(("", f"💡 {status.reason}"))

        if status.should_stop_buying:
            lines.append("🛑 **BUYING PAUSED**")
        if status.should_liquidate:
            lines.append("📤 **LIQUIDATING INVENTORY**")
        if status.should_buy_aggressively:
            lines.append(
                f"💰 **AGGRESSIVE BUYING** (min {status.buy_discount_threshold * 100:.0f}% off)"
            )

        return "\n".join(lines)


# Глобальный экземпляр
_protector: SteamSalesProtector | None = None


def get_steam_sales_protector() -> SteamSalesProtector:
    """Получить глобальный экземпляр SteamSalesProtector."""
    global _protector
    if _protector is None:
        _protector = SteamSalesProtector()
    return _protector
