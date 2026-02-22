"""Lock Status Filter - Фильтрация предметов по статусу блокировки.

Частая ошибка новичков: покупка скина с выгодной ценой, который заблокирован
на вывод на 7-8 дней. При балансе в $45.50 нельзя позволить себе «заморозить»
деньги на неделю.

Этот модуль реализует:
1. Фильтрацию по lockStatus (0 = доступен, 1 = заблокирован)
2. Расчет дисконта за ожидание (3-5% в зависимости от срока)
3. Приоритизацию предметов без lock

Основано на документации DMarket API.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Any

logger = logging.getLogger(__name__)


class LockStatus(IntEnum):
    """Статус блокировки предмета.

    DMarket API возвращает lockStatus:
    - 0: Предмет доступен для вывода сразу
    - 1: Предмет заблокирован (трейд-бан)
    """

    AVAlgoLABLE = 0
    LOCKED = 1


@dataclass
class LockInfo:
    """Информация о блокировке предмета."""

    status: LockStatus
    days_remaining: int = 0
    unlock_date: datetime | None = None

    # Рассчитанный дисконт за ожидание
    calculated_discount: float = 0.0

    @property
    def is_avAlgolable(self) -> bool:
        """Предмет доступен сразу."""
        return self.status == LockStatus.AVAlgoLABLE

    @property
    def is_locked(self) -> bool:
        """Предмет заблокирован."""
        return self.status == LockStatus.LOCKED


@dataclass
class LockFilterConfig:
    """Конфигурация фильтра блокировок."""

    # Фильтровать предметы в lock
    filter_locked: bool = True

    # Приоритизировать unlocked предметы
    prioritize_unlocked: bool = True

    # Минимальный дисконт за lock (%)
    min_lock_discount: float = 3.0

    # Максимальный дисконт за lock (%)
    max_lock_discount: float = 5.0

    # Дополнительный дисконт за каждый день ожидания (%)
    discount_per_day: float = 0.3

    # Максимальное количество дней lock для покупки
    max_lock_days: int = 7

    # Учитывать lock в profit расчетах
    adjust_profit_for_lock: bool = True


@dataclass
class ItemWithLock:
    """Предмет с информацией о блокировке."""

    item_id: str
    title: str
    price: float  # В USD

    lock_info: LockInfo = field(default_factory=lambda: LockInfo(LockStatus.AVAlgoLABLE))

    # Рассчитанные цены
    effective_price: float = 0.0  # Цена с учетом lock дисконта

    # Бонусы от DMarket
    discount_percent: float = 0.0
    bonus_amount: float = 0.0

    # Для сортировки
    priority_score: float = 0.0

    def __post_init__(self):
        """Рассчитать effective price после инициализации."""
        if self.effective_price == 0.0:
            self.effective_price = self.price


class LockStatusFilter:
    """Фильтр предметов по статусу блокировки.

    Функции:
    1. Фильтрация locked предметов
    2. Расчет дисконта за ожидание
    3. Корректировка profit с учетом lock
    4. Приоритизация unlocked предметов

    Example:
        >>> filter = LockStatusFilter()
        >>> items = await api.get_market_items()
        >>> filtered = filter.filter_items(items)
        >>> print(f"AvAlgolable now: {len(filtered)}")
    """

    def __init__(self, config: LockFilterConfig | None = None):
        """Инициализация фильтра.

        Args:
            config: Конфигурация фильтра
        """
        self.config = config or LockFilterConfig()

        logger.info(
            "LockStatusFilter initialized",
            extra={
                "filter_locked": self.config.filter_locked,
                "min_discount": self.config.min_lock_discount,
                "max_discount": self.config.max_lock_discount,
            },
        )

    def parse_lock_info(self, item_data: dict[str, Any]) -> LockInfo:
        """Извлечь информацию о блокировке из данных API.

        Args:
            item_data: Данные предмета из API

        Returns:
            LockInfo с информацией о блокировке
        """
        lock_status = LockStatus(item_data.get("lockStatus", 0))

        # Дни до разблокировки
        days_remaining = item_data.get("lockDaysRemaining", 0)

        # Или из extra данных
        if days_remaining == 0:
            extra = item_data.get("extra", {})
            tradable_after = extra.get("tradableAfter")
            if tradable_after:
                try:
                    unlock_date = datetime.fromisoformat(tradable_after)
                    days_remaining = max(0, (unlock_date - datetime.now()).days)
                except (ValueError, TypeError):
                    pass

        # Дата разблокировки
        unlock_date = None
        if days_remaining > 0:
            unlock_date = datetime.now() + timedelta(days=days_remaining)

        # Рассчитываем дисконт
        discount = self.calculate_lock_discount(days_remaining)

        return LockInfo(
            status=lock_status,
            days_remaining=days_remaining,
            unlock_date=unlock_date,
            calculated_discount=discount,
        )

    def calculate_lock_discount(self, days: int) -> float:
        """Рассчитать дисконт за lock.

        Формула: min_discount + (days * discount_per_day)
        Максимум: max_discount

        Args:
            days: Количество дней блокировки

        Returns:
            Дисконт в процентах
        """
        if days <= 0:
            return 0.0

        discount = self.config.min_lock_discount + days * self.config.discount_per_day

        return min(discount, self.config.max_lock_discount)

    def apply_lock_discount(
        self,
        price: float,
        lock_info: LockInfo,
    ) -> float:
        """Применить дисконт за lock к цене.

        Предмет в холде должен стоить на 3-5% дешевле,
        чтобы оправдать простой капитала.

        Args:
            price: Исходная цена
            lock_info: Информация о блокировке

        Returns:
            Максимальная цена покупки с учетом lock
        """
        if not lock_info.is_locked:
            return price

        discount_factor = 1 - (lock_info.calculated_discount / 100)
        return price * discount_factor

    def adjust_profit_for_lock(
        self,
        base_profit_percent: float,
        lock_info: LockInfo,
    ) -> float:
        """Скорректировать профит с учетом lock.

        Если предмет в lock, уменьшаем ожидаемый профит
        на величину lock дисконта.

        Args:
            base_profit_percent: Базовый профит (%)
            lock_info: Информация о блокировке

        Returns:
            Скорректированный профит (%)
        """
        if not self.config.adjust_profit_for_lock:
            return base_profit_percent

        if not lock_info.is_locked:
            return base_profit_percent

        return base_profit_percent - lock_info.calculated_discount

    def filter_items(
        self,
        items: list[dict[str, Any]],
        allow_locked: bool | None = None,
    ) -> list[ItemWithLock]:
        """Фильтрация и обогащение предметов информацией о lock.

        Args:
            items: Список предметов из API
            allow_locked: Разрешить locked предметы (None = использовать config)

        Returns:
            Отфильтрованные и обогащенные предметы
        """
        if allow_locked is None:
            allow_locked = not self.config.filter_locked

        result = []

        for item_data in items:
            lock_info = self.parse_lock_info(item_data)

            # Фильтрация по lock
            if not allow_locked and lock_info.is_locked:
                continue

            # Проверка max_lock_days
            if lock_info.days_remaining > self.config.max_lock_days:
                continue

            # Цена в USD
            price_data = item_data.get("price", {})
            if isinstance(price_data, dict):
                price = price_data.get("USD", 0) / 100  # Центы -> USD
            else:
                price = float(price_data) / 100

            # Бонусы от DMarket
            discount = item_data.get("discount", 0)
            bonus = (
                price_data.get("bonus", 0) / 100 if isinstance(price_data, dict) else 0
            )

            # Effective price с учетом lock
            effective_price = self.apply_lock_discount(price, lock_info)

            # Priority score для сортировки
            priority = self._calculate_priority(
                lock_info=lock_info,
                discount=discount,
                bonus=bonus,
            )

            item = ItemWithLock(
                item_id=item_data.get("itemId", ""),
                title=item_data.get("title", ""),
                price=price,
                lock_info=lock_info,
                effective_price=effective_price,
                discount_percent=discount,
                bonus_amount=bonus,
                priority_score=priority,
            )

            result.append(item)

        # Сортировка по приоритету
        if self.config.prioritize_unlocked:
            result.sort(key=lambda x: x.priority_score, reverse=True)

        return result

    def _calculate_priority(
        self,
        lock_info: LockInfo,
        discount: float,
        bonus: float,
    ) -> float:
        """Рассчитать приоритет предмета.

        Формула:
        - +100 если unlocked
        - +discount (скидка от DMarket)
        - +bonus * 10 (бонус от DMarket)
        - -lock_days * 5 (штраф за lock)
        """
        score = 0.0

        # Бонус за доступность
        if lock_info.is_avAlgolable:
            score += 100
        else:
            score -= lock_info.days_remaining * 5

        # Бонус за скидку DMarket
        score += discount

        # Бонус за price.bonus
        score += bonus * 10

        return score

    def should_buy(
        self,
        item: ItemWithLock,
        target_profit: float,
        current_balance: float,
    ) -> tuple[bool, str]:
        """Проверить, стоит ли покупать предмет.

        Args:
            item: Предмет с информацией о lock
            target_profit: Целевой профит (%)
            current_balance: Текущий баланс

        Returns:
            (should_buy, reason)
        """
        # Проверка lock
        if item.lock_info.is_locked:
            # Скорректированный профит
            adjusted_profit = self.adjust_profit_for_lock(
                target_profit,
                item.lock_info,
            )

            if adjusted_profit < self.config.min_lock_discount:
                return (
                    False,
                    f"Profit too low after lock adjustment: {adjusted_profit:.1f}%",
                )

        # Проверка заморозки капитала
        if item.lock_info.is_locked:
            frozen_days = item.lock_info.days_remaining
            frozen_percent = (item.price / current_balance) * 100

            # Не замораживать >25% баланса на >3 дней
            if frozen_percent > 25 and frozen_days > 3:
                return (
                    False,
                    f"Would freeze {frozen_percent:.1f}% of balance for {frozen_days} days",
                )

        # Двойное подтверждение: DMarket bonus + наш profit
        if item.discount_percent > 0 or item.bonus_amount > 0:
            return True, "Double confirmation: DMarket discount + target profit"

        return True, "Meets all criteria"

    def get_stats(
        self,
        items: list[ItemWithLock],
    ) -> dict[str, Any]:
        """Получить статистику по lock.

        Args:
            items: Список предметов

        Returns:
            Статистика
        """
        total = len(items)
        avAlgolable = sum(1 for i in items if i.lock_info.is_avAlgolable)
        locked = total - avAlgolable

        avg_lock_days = 0.0
        if locked > 0:
            avg_lock_days = (
                sum(i.lock_info.days_remaining for i in items if i.lock_info.is_locked)
                / locked
            )

        return {
            "total_items": total,
            "avAlgolable_now": avAlgolable,
            "locked": locked,
            "locked_percent": (locked / max(1, total)) * 100,
            "avg_lock_days": avg_lock_days,
            "with_discount": sum(1 for i in items if i.discount_percent > 0),
            "with_bonus": sum(1 for i in items if i.bonus_amount > 0),
        }
