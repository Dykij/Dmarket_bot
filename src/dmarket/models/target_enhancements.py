"""Расширенные модели для улучшенной системы таргетов (Buy Orders).

Этот модуль содержит новые модели для продвинутых функций:
- Пакетные ордера на несколько предметов
- Конфигурация автоперебития
- Фильтры по стикерам и редкости
- Контроль лимитов перевыставлений
- Мониторинг диапазона цен

Документация: docs/DMARKET_API_FULL_SPEC.md (разделы 5.1-5.5)
API Version: v1.1.0
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ==================== ENUMS ====================


class PriceRangeAction(StrEnum):
    """Действия при выходе цены ордера из заданного диапазона."""

    CANCEL = "cancel"  # Отменить ордер
    ADJUST = "adjust"  # Автоматически скорректировать цену
    NOTIFY = "notify"  # Уведомить пользователя
    KEEP = "keep"  # Оставить как есть


class RelistAction(StrEnum):
    """Действие при достижении лимита перевыставлений."""

    PAUSE = "pause"  # Приостановить перевыставления
    CANCEL = "cancel"  # Отменить ордер
    LOWER_PRICE = "lower_price"  # Понизить цену
    NOTIFY = "notify"  # Только уведомить


class TargetOperationStatus(StrEnum):
    """Статусы операций с таргетами."""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # Частично выполнено (для batch)
    PENDING = "pending"


class TargetErrorCode(StrEnum):
    """Коды ошибок при работе с таргетами."""

    PRICE_TOO_LOW = "price_too_low"
    PRICE_TOO_HIGH = "price_too_high"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    DUPLICATE_ORDER = "duplicate_order"
    TOO_MANY_CONDITIONS = "too_many_conditions"
    INVALID_ATTRIBUTES = "invalid_attributes"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    ORDER_LIMIT_REACHED = "order_limit_reached"
    UNKNOWN_ERROR = "unknown_error"


# ==================== STICKER FILTERS (CS:GO) ====================


class StickerFilter(BaseModel):
    """Фильтр по стикерам для таргетов (CS:GO).

    Позволяет создавать ордера с требованиями к стикерам на оружии.
    DMarket API ограничивает количество условий в фильтре (обычно до 10).

    Примеры:
        >>> # Фильтр на конкретный стикер
        >>> filter1 = StickerFilter(
        ...     sticker_names=["iBUYPOWER | Katowice 2014 (Holo)"], min_stickers=1
        ... )
        >>>
        >>> # Фильтр на категорию + холо
        >>> filter2 = StickerFilter(sticker_categories=["Katowice 2014"], min_stickers=3, holo=True)
    """

    sticker_names: list[str] | None = Field(
        None,
        description="Конкретные названия стикеров",
        max_length=10,
    )
    sticker_categories: list[str] | None = Field(
        None,
        description="Категории стикеров (например, 'Katowice 2014')",
        max_length=5,
    )
    min_stickers: int = Field(
        default=0,
        ge=0,
        le=5,
        description="Минимальное количество стикеров на предмете",
    )
    max_stickers: int = Field(
        default=5,
        ge=0,
        le=5,
        description="Максимальное количество стикеров на предмете",
    )
    holo: bool | None = Field(
        None,
        description="Только холографические стикеры (True/False/None=любые)",
    )
    foil: bool | None = Field(
        None,
        description="Только фольгированные стикеры (True/False/None=любые)",
    )

    @field_validator("max_stickers")
    @classmethod
    def validate_max_stickers(cls, v: int, info) -> int:
        """Проверить что max_stickers >= min_stickers."""
        min_val = info.data.get("min_stickers", 0)
        if v < min_val:
            msg = f"max_stickers ({v}) должен быть >= min_stickers ({min_val})"
            raise ValueError(msg)
        return v

    def count_conditions(self) -> int:
        """Подсчитать количество условий в фильтре для DMarket API лимита."""
        count = 0
        if self.sticker_names:
            count += len(self.sticker_names)
        if self.sticker_categories:
            count += len(self.sticker_categories)
        if self.min_stickers > 0:
            count += 1
        if self.max_stickers < 5:
            count += 1
        if self.holo is not None:
            count += 1
        if self.foil is not None:
            count += 1
        return count


# ==================== RARITY FILTERS (Dota 2, TF2) ====================


class RarityLevel(StrEnum):
    """Уровни редкости предметов (Dota 2, TF2)."""

    COMMON = "common"  # Index 0
    UNCOMMON = "uncommon"  # Index 1
    RARE = "rare"  # Index 2
    MYTHICAL = "mythical"  # Index 3
    LEGENDARY = "legendary"  # Index 4
    IMMORTAL = "immortal"  # Index 5
    ARCANA = "arcana"  # Index 6 (Dota 2)
    ANCIENT = "ancient"  # Index 7 (Dota 2)


# Маппинг редкости на индексы
RARITY_INDEX_MAP = {
    RarityLevel.COMMON: 0,
    RarityLevel.UNCOMMON: 1,
    RarityLevel.RARE: 2,
    RarityLevel.MYTHICAL: 3,
    RarityLevel.LEGENDARY: 4,
    RarityLevel.IMMORTAL: 5,
    RarityLevel.ARCANA: 6,
    RarityLevel.ANCIENT: 7,
}


class RarityFilter(BaseModel):
    """Фильтр по редкости предмета (Dota 2, TF2).

    Позволяет создавать ордера с требованиями к редкости.

    Примеры:
        >>> # Только Arcana
        >>> filter1 = RarityFilter(rarity=RarityLevel.ARCANA)
        >>>
        >>> # От Mythical до Immortal
        >>> filter2 = RarityFilter(
        ...     min_rarity_index=3,  # Mythical
        ...     max_rarity_index=5,  # Immortal
        ... )
    """

    rarity: RarityLevel | None = Field(
        None,
        description="Конкретный уровень редкости",
    )
    min_rarity_index: int | None = Field(
        None,
        ge=0,
        le=7,
        description="Минимальный индекс редкости (0-7)",
    )
    max_rarity_index: int | None = Field(
        None,
        ge=0,
        le=7,
        description="Максимальный индекс редкости (0-7)",
    )

    @field_validator("max_rarity_index")
    @classmethod
    def validate_max_rarity(cls, v: int | None, info) -> int | None:
        """Проверить что max_rarity_index >= min_rarity_index."""
        if v is None:
            return v
        min_val = info.data.get("min_rarity_index")
        if min_val is not None and v < min_val:
            msg = f"max_rarity_index ({v}) должен быть >= min_rarity_index ({min_val})"
            raise ValueError(msg)
        return v

    def count_conditions(self) -> int:
        """Подсчитать количество условий в фильтре."""
        count = 0
        if self.rarity:
            count += 1
        if self.min_rarity_index is not None:
            count += 1
        if self.max_rarity_index is not None:
            count += 1
        return count


# ==================== OVERBID CONFIGURATION ====================


class TargetOverbidConfig(BaseModel):
    """Конфигурация автоматического перебития ордеров.

    Управляет тем, как бот реагирует когда конкуренты создают
    ордера с более высокой ценой.

    Примеры:
        >>> # Консервативное перебитие
        >>> config1 = TargetOverbidConfig(
        ...     enabled=True,
        ...     max_overbid_percent=2.0,  # Макс +2% от начальной цены
        ...     min_price_gap=0.01,  # Минимум $0.01 разница
        ...     max_overbids_per_day=5,  # Макс 5 перебитий в день
        ... )
        >>>
        >>> # Агрессивное перебитие
        >>> config2 = TargetOverbidConfig(
        ...     enabled=True,
        ...     max_overbid_percent=10.0,  # До +10%
        ...     check_interval_seconds=60,  # Проверять каждую минуту
        ...     max_overbids_per_day=20,  # До 20 перебитий
        ... )
    """

    enabled: bool = Field(
        default=True,
        description="Включить автоматическое перебитие",
    )
    max_overbid_percent: float = Field(
        default=2.0,
        gt=0,
        le=100,
        description="Максимальный процент повышения от изначальной цены",
    )
    min_price_gap: float = Field(
        default=0.01,
        gt=0,
        description="Минимальная разница в цене для перебития (USD)",
    )
    check_interval_seconds: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Интервал проверки конкуренции (секунды)",
    )
    max_overbids_per_day: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Максимум перебитий за 24 часа",
    )
    notify_on_overbid: bool = Field(
        default=True,
        description="Отправлять уведомление при перебитии",
    )


# ==================== PRICE RANGE MONITORING ====================


class PriceRangeConfig(BaseModel):
    """Конфигурация контроля диапазона рыночных цен.

    Мониторит рыночную цену и реагирует когда она выходит
    за пределы установленного диапазона.

    Примеры:
        >>> # Отменить если цена упала ниже минимума
        >>> config1 = PriceRangeConfig(
        ...     min_price=8.0, max_price=15.0, action_on_breach=PriceRangeAction.CANCEL
        ... )
        >>>
        >>> # Автокорректировка цены в пределах диапазона
        >>> config2 = PriceRangeConfig(
        ...     min_price=8.0, max_price=15.0, action_on_breach=PriceRangeAction.ADJUST
        ... )
    """

    min_price: float = Field(
        gt=0,
        description="Минимальная допустимая рыночная цена (USD)",
    )
    max_price: float = Field(
        gt=0,
        description="Максимальная допустимая рыночная цена (USD)",
    )
    action_on_breach: PriceRangeAction = Field(
        default=PriceRangeAction.NOTIFY,
        description="Действие при выходе за диапазон",
    )
    check_interval_minutes: int = Field(
        default=30,
        ge=5,
        le=1440,
        description="Интервал проверки цен (минуты)",
    )
    notify_on_breach: bool = Field(
        default=True,
        description="Отправлять уведомление при выходе из диапазона",
    )

    @field_validator("max_price")
    @classmethod
    def validate_max_price(cls, v: float, info) -> float:
        """Проверить что max_price > min_price."""
        min_val = info.data.get("min_price", 0)
        if v <= min_val:
            msg = f"max_price ({v}) должен быть > min_price ({min_val})"
            raise ValueError(msg)
        return v


# ==================== RELIST LIMIT CONFIGURATION ====================


class RelistLimitConfig(BaseModel):
    """Конфигурация лимита перевыставлений ордера.

    Контролирует сколько раз ордер может быть перевыставлен
    (отменен и создан заново) и что делать при достижении лимита.

    Примеры:
        >>> # Пауза после 5 перевыставлений
        >>> config1 = RelistLimitConfig(max_relists=5, action_on_limit=RelistAction.PAUSE)
        >>>
        >>> # Отмена после 10 перевыставлений
        >>> config2 = RelistLimitConfig(
        ...     max_relists=10, reset_period_hours=24, action_on_limit=RelistAction.CANCEL
        ... )
    """

    max_relists: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Максимальное количество перевыставлений",
    )
    reset_period_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Период сброса счетчика перевыставлений (часы)",
    )
    action_on_limit: RelistAction = Field(
        default=RelistAction.PAUSE,
        description="Действие при достижении лимита",
    )
    notify_on_limit: bool = Field(
        default=True,
        description="Отправлять уведомление при достижении лимита",
    )
    lower_price_percent: float = Field(
        default=5.0,
        ge=0.1,
        le=50.0,
        description="На сколько процентов понизить цену при action=lower_price",
    )


# ==================== TARGET DEFAULTS ====================


class TargetDefaults(BaseModel):
    """Дефолтные параметры для базы предметов.

    Позволяет установить общие настройки для всех ордеров,
    чтобы не повторять одинаковые параметры каждый раз.

    Примеры:
        >>> defaults = TargetDefaults(
        ...     default_amount=1,
        ...     default_price_strategy="market_minus_5_percent",
        ...     default_overbid_config=TargetOverbidConfig(enabled=True),
        ... )
    """

    default_amount: int = Field(
        default=1,
        ge=1,
        le=100,
        description="Дефолтное количество предметов",
    )
    default_price_strategy: str = Field(
        default="manual",
        description="Стратегия ценообразования: manual, market_minus_X_percent",
    )
    default_overbid_config: TargetOverbidConfig | None = Field(
        None,
        description="Дефолтная конфигурация перебития",
    )
    default_price_range_config: PriceRangeConfig | None = Field(
        None,
        description="Дефолтная конфигурация диапазона цен",
    )
    default_relist_config: RelistLimitConfig | None = Field(
        None,
        description="Дефолтная конфигурация лимитов перевыставлений",
    )
    default_sticker_filter: StickerFilter | None = Field(
        None,
        description="Дефолтный фильтр по стикерам (CS:GO)",
    )
    default_rarity_filter: RarityFilter | None = Field(
        None,
        description="Дефолтный фильтр по редкости (Dota 2, TF2)",
    )
    default_max_conditions: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Максимум условий в одном ордере (DMarket API лимит)",
    )


# ==================== OPERATION RESULT ====================


class TargetOperationResult(BaseModel):
    """Результат операции с таргетом.

    Содержит детальную информацию о результате операции,
    включая успех/неудачу, причины, ошибки и рекомендации.

    Примеры:
        >>> # Успешное создание
        >>> result1 = TargetOperationResult(
        ...     success=True,
        ...     target_id="abc123",
        ...     message="Order created successfully",
        ...     reason="Created in 0.5s, position #3 in queue",
        ... )
        >>>
        >>> # Ошибка валидации
        >>> result2 = TargetOperationResult(
        ...     success=False,
        ...     message="Failed to create order",
        ...     reason="Price $4.50 is below minimum $5.00",
        ...     error_code=TargetErrorCode.PRICE_TOO_LOW,
        ...     suggestions=["Set price to at least $5.00", "Try different item"],
        ... )
    """

    success: bool = Field(description="Успешность операции")
    status: TargetOperationStatus = Field(
        default=TargetOperationStatus.SUCCESS,
        description="Статус операции",
    )
    target_id: str | None = Field(
        None,
        description="ID созданного/измененного таргета",
    )
    message: str = Field(
        description="Краткое сообщение о результате",
    )
    reason: str | None = Field(
        None,
        description="Детальная причина результата",
    )
    error_code: TargetErrorCode | None = Field(
        None,
        description="Код ошибки (если применимо)",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Рекомендации по исправлению/улучшению",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные данные (время, позиция в очереди и т.д.)",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Время операции",
    )


# ==================== BATCH TARGET ITEM ====================


class BatchTargetItem(BaseModel):
    """Предмет для пакетного создания ордера.

    Используется в create_batch_target для создания одного ордера
    на несколько предметов.

    Примеры:
        >>> item1 = BatchTargetItem(title="AK-47 | Redline (FT)", attrs={"floatPartValue": "0.25"})
        >>> item2 = BatchTargetItem(title="AK-47 | Redline (MW)", attrs={"floatPartValue": "0.12"})
    """

    title: str = Field(description="Полное название предмета")
    attrs: dict[str, Any] | None = Field(
        None,
        description="Специфические атрибуты предмета (float, pattern, phase)",
    )
    weight: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Вес предмета в распределении цены (для batch)",
    )


# ==================== RELIST TRACKING ====================


class RelistHistory(BaseModel):
    """Запись истории перевыставления ордера."""

    timestamp: datetime = Field(description="Время перевыставления")
    old_price: float = Field(description="Старая цена (USD)")
    new_price: float = Field(description="Новая цена (USD)")
    reason: str = Field(description="Причина перевыставления")
    triggered_by: str = Field(
        default="system",
        description="Кто инициировал: system, user, competitor",
    )


class RelistStatistics(BaseModel):
    """Статистика перевыставлений для ордера."""

    target_id: str = Field(description="ID таргета")
    total_relists: int = Field(description="Всего перевыставлений")
    max_relists: int = Field(description="Максимум разрешенных перевыставлений")
    remaining_relists: int = Field(description="Осталось перевыставлений")
    last_relist_time: datetime | None = Field(None, description="Последнее перевыставление")
    reset_time: datetime = Field(description="Время сброса счетчика")
    time_until_reset: str = Field(description="Время до сброса (человекочитаемое)")
    action_on_limit: RelistAction = Field(description="Действие при лимите")
    will_pause_at: float | None = Field(
        None,
        description="Прогноз цены при следующем перебитии",
    )
    history: list[RelistHistory] = Field(
        default_factory=list,
        description="История перевыставлений",
    )


# ==================== EXISTING ORDER DETECTION ====================


class ExistingOrderInfo(BaseModel):
    """Информация о существующих ордерах для предмета."""

    has_user_order: bool = Field(
        description="Есть ли у пользователя активный ордер на этот предмет",
    )
    user_order: dict[str, Any] | None = Field(
        None,
        description="Детали ордера пользователя (если есть)",
    )
    total_orders: int = Field(
        description="Всего активных ордеров на этот предмет",
    )
    best_price: float | None = Field(
        None,
        description="Лучшая цена среди всех ордеров (USD)",
    )
    average_price: float | None = Field(
        None,
        description="Средняя цена среди ордеров (USD)",
    )
    can_create: bool = Field(
        description="Можно ли создать новый ордер",
    )
    reason: str = Field(
        description="Причина почему можно/нельзя создать",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Рекомендации для пользователя",
    )
    recommended_price: float | None = Field(
        None,
        description="Рекомендуемая цена для быстрой покупки",
    )
