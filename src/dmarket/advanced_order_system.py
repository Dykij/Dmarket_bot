"""Advanced Order System - Расширенная система ордеров как на CS Float.

Реализация "расширенных ордеров" с возможностями:
1. Фильтрация по Float Value (диапазоны)
2. Фильтрация по Pattern ID (Case Hardened Blue Gem, Doppler Phase)
3. Фильтрация по стикерам (Katowice 2014, Holo)
4. Комбинированные фильтры
5. Автоматическое управление ордерами

Основано на статье:
https://info.tacompany.ru/skhemy-zarabotka-v-steam/rasshirennye-ordera-cs-float

Январь 2026
"""

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from src.dmarket.models.target_enhancements import StickerFilter, TargetOperationResult

if TYPE_CHECKING:
    from src.dmarket.targets.manager import TargetManager


logger = logging.getLogger(__name__)


class DopplerPhase(StrEnum):
    """Фазы Doppler ножей и оружия."""

    PHASE_1 = "Phase 1"
    PHASE_2 = "Phase 2"
    PHASE_3 = "Phase 3"
    PHASE_4 = "Phase 4"
    RUBY = "Ruby"
    SAPPHIRE = "Sapphire"
    BLACK_PEARL = "Black Pearl"
    EMERALD = "Emerald"


class PatternType(StrEnum):
    """Типы паттернов с премией."""

    CASE_HARDENED_BLUE = "blue_gem"  # Case Hardened Blue Gem
    CASE_HARDENED_GOLD = "gold_gem"  # Case Hardened Gold
    FADE_MAX = "max_fade"  # Maximum Fade
    MARBLE_FIRE_ICE = "fire_ice"  # Marble Fade Fire & Ice
    CRIMSON_WEB_CENTERED = "centered_web"  # Centered web pattern


# Паттерны Case Hardened с высокой ценностью (Blue Gem seeds)
BLUE_GEM_PATTERNS: dict[str, list[int]] = {
    "AK-47 | Case Hardened": [661, 670, 321, 955, 179, 168],
    "Five-SeveN | Case Hardened": [690, 278, 868, 363],
    "Karambit | Case Hardened": [387, 269, 463, 442],
    "Bayonet | Case Hardened": [555, 727, 152, 470],
}

# Премиальные Doppler фазы с множителями
DOPPLER_PREMIUMS: dict[DopplerPhase, float] = {
    DopplerPhase.RUBY: 5.0,  # 5x базовой цены
    DopplerPhase.SAPPHIRE: 4.5,
    DopplerPhase.BLACK_PEARL: 3.0,
    DopplerPhase.EMERALD: 6.0,
    DopplerPhase.PHASE_2: 1.15,  # Pink galaxy
    DopplerPhase.PHASE_4: 1.10,  # Blue
    DopplerPhase.PHASE_1: 1.0,
    DopplerPhase.PHASE_3: 0.95,
}


@dataclass
class AdvancedOrderFilter:
    """Расширенный фильтр для ордера.

    Позволяет создавать ордера с комбинацией условий:
    - Float value диапазон
    - Pattern ID
    - Doppler Phase
    - Стикеры
    - StatTrak
    """

    # Float фильтры
    float_min: float | None = None
    float_max: float | None = None

    # Pattern фильтры
    paint_seed: int | None = None  # Конкретный паттерн
    paint_seeds: list[int] | None = None  # Список паттернов

    # Doppler фильтры
    phase: DopplerPhase | None = None

    # Стикер фильтры
    sticker_filter: StickerFilter | None = None

    # Прочие
    stat_trak: bool | None = None
    souvenir: bool | None = None

    def to_target_attrs(self) -> dict[str, Any]:
        """Конвертировать в атрибуты для DMarket Target API."""
        attrs: dict[str, Any] = {}

        if self.float_min is not None:
            attrs["floatMin"] = str(self.float_min)
        if self.float_max is not None:
            attrs["floatMax"] = str(self.float_max)

        if self.paint_seed is not None:
            attrs["paintSeed"] = self.paint_seed
        elif self.paint_seeds:
            attrs["paintSeed"] = self.paint_seeds

        if self.phase is not None:
            attrs["phase"] = self.phase.value

        if self.stat_trak is not None:
            attrs["isStatTrak"] = self.stat_trak
        if self.souvenir is not None:
            attrs["isSouvenir"] = self.souvenir

        return attrs

    def count_conditions(self) -> int:
        """Подсчитать количество условий (DMarket лимит ~10)."""
        count = 0

        if self.float_min is not None:
            count += 1
        if self.float_max is not None:
            count += 1
        if self.paint_seed is not None:
            count += 1
        elif self.paint_seeds:
            count += len(self.paint_seeds)
        if self.phase is not None:
            count += 1
        if self.stat_trak is not None:
            count += 1
        if self.souvenir is not None:
            count += 1
        if self.sticker_filter:
            count += self.sticker_filter.count_conditions()

        return count


@dataclass
class AdvancedOrder:
    """Расширенный ордер с фильтрами.

    Аналог "Advanced Buy Order" на CS Float.
    """

    item_title: str
    game: str = "csgo"
    max_price_usd: float = 0
    amount: int = 1
    filter: AdvancedOrderFilter = field(default_factory=AdvancedOrderFilter)

    # Метаданные
    expected_sell_price: float | None = None
    notes: str = ""

    # Состояние
    target_id: str | None = None
    is_active: bool = False
    filled_count: int = 0

    def calculate_expected_profit(self, commission: float = 0.05) -> float:
        """Рассчитать ожидаемую прибыль."""
        if self.expected_sell_price is None:
            return 0

        sell_after_commission = self.expected_sell_price * (1 - commission)
        return sell_after_commission - self.max_price_usd

    def calculate_roi(self, commission: float = 0.05) -> float:
        """Рассчитать ROI в процентах."""
        profit = self.calculate_expected_profit(commission)
        if self.max_price_usd <= 0:
            return 0
        return (profit / self.max_price_usd) * 100


@dataclass
class OrderTemplate:
    """Шаблон ордера для быстрого создания."""

    name: str
    description: str
    item_title: str
    filter: AdvancedOrderFilter
    base_price_usd: float  # Базовая цена без премии
    expected_premium_multiplier: float = 1.0

    def create_order(self, max_price_usd: float | None = None) -> AdvancedOrder:
        """Создать ордер из шаблона."""
        price = max_price_usd or self.base_price_usd
        expected_sell = self.base_price_usd * self.expected_premium_multiplier

        return AdvancedOrder(
            item_title=self.item_title,
            max_price_usd=price,
            filter=self.filter,
            expected_sell_price=expected_sell,
            notes=f"Template: {self.name}",
        )


class AdvancedOrderManager:
    """Менеджер расширенных ордеров.

    Реализует функционал как на CS Float:
    - Создание ордеров с фильтрами
    - Шаблоны популярных ордеров
    - Автоматическое управление
    """

    def __init__(
        self,
        target_manager: "TargetManager",
        commission: float = 0.05,
    ):
        """Инициализация менеджера.

        Args:
            target_manager: Менеджер таргетов DMarket
            commission: Комиссия площадки
        """
        self.targets = target_manager
        self.commission = commission
        self.active_orders: dict[str, AdvancedOrder] = {}
        self.templates = self._load_default_templates()

        logger.info("AdvancedOrderManager initialized")

    def _load_default_templates(self) -> dict[str, OrderTemplate]:
        """Загрузить шаблоны популярных ордеров."""
        templates = {}

        # AK-47 Redline с премиальным флоатом
        templates["ak47_redline_premium_ft"] = OrderTemplate(
            name="AK-47 Redline Premium FT",
            description="Float 0.15-0.155 - лучший FT флоат",
            item_title="AK-47 | Redline (Field-Tested)",
            filter=AdvancedOrderFilter(float_min=0.15, float_max=0.155),
            base_price_usd=33.0,
            expected_premium_multiplier=1.88,
        )

        templates["ak47_redline_good_ft"] = OrderTemplate(
            name="AK-47 Redline Good FT",
            description="Float 0.15-0.16",
            item_title="AK-47 | Redline (Field-Tested)",
            filter=AdvancedOrderFilter(float_min=0.15, float_max=0.16),
            base_price_usd=33.0,
            expected_premium_multiplier=1.80,
        )

        # AWP Asiimov
        templates["awp_asiimov_best_ft"] = OrderTemplate(
            name="AWP Asiimov Best FT",
            description="Float 0.18-0.20 - минимальный FT",
            item_title="AWP | Asiimov (Field-Tested)",
            filter=AdvancedOrderFilter(float_min=0.18, float_max=0.20),
            base_price_usd=85.0,
            expected_premium_multiplier=1.25,
        )

        templates["awp_asiimov_blackiimov"] = OrderTemplate(
            name="AWP Blackiimov",
            description="BS 0.90+ - черный прицел",
            item_title="AWP | Asiimov (Battle-Scarred)",
            filter=AdvancedOrderFilter(float_min=0.90, float_max=1.00),
            base_price_usd=30.0,
            expected_premium_multiplier=2.0,
        )

        # Doppler фазы
        templates["karambit_doppler_ruby"] = OrderTemplate(
            name="Karambit Doppler Ruby",
            description="Ruby - максимальная премия",
            item_title="★ Karambit | Doppler (Factory New)",
            filter=AdvancedOrderFilter(phase=DopplerPhase.RUBY),
            base_price_usd=500.0,
            expected_premium_multiplier=5.0,
        )

        templates["karambit_doppler_sapphire"] = OrderTemplate(
            name="Karambit Doppler Sapphire",
            description="Sapphire",
            item_title="★ Karambit | Doppler (Factory New)",
            filter=AdvancedOrderFilter(phase=DopplerPhase.SAPPHIRE),
            base_price_usd=500.0,
            expected_premium_multiplier=4.5,
        )

        # Case Hardened Blue Gem
        templates["ak47_ch_blue_gem"] = OrderTemplate(
            name="AK-47 Case Hardened Blue Gem",
            description="Паттерны #661, #670 и др.",
            item_title="AK-47 | Case Hardened (Field-Tested)",
            filter=AdvancedOrderFilter(paint_seeds=[661, 670, 321, 955]),
            base_price_usd=100.0,
            expected_premium_multiplier=10.0,  # Blue gems очень дорогие
        )

        # Стикеры
        templates["ak47_kato14_holo"] = OrderTemplate(
            name="AK-47 with Katowice 2014 Holo",
            description="Любой AK с Katowice 2014 Holo стикером",
            item_title="AK-47",
            filter=AdvancedOrderFilter(
                sticker_filter=StickerFilter(
                    sticker_categories=["Katowice 2014"],
                    holo=True,
                    min_stickers=1,
                )
            ),
            base_price_usd=50.0,
            expected_premium_multiplier=3.0,
        )

        return templates

    async def create_order(
        self,
        order: AdvancedOrder,
    ) -> TargetOperationResult:
        """Создать расширенный ордер.

        Args:
            order: Конфигурация ордера

        Returns:
            Результат операции
        """
        logger.info(
            "Creating advanced order",
            extra={
                "item": order.item_title,
                "price": order.max_price_usd,
                "conditions": order.filter.count_conditions(),
            },
        )

        # Проверяем лимит условий
        if order.filter.count_conditions() > 10:
            from src.dmarket.models.target_enhancements import (
                TargetErrorCode,
                TargetOperationStatus,
            )

            return TargetOperationResult(
                success=False,
                status=TargetOperationStatus.FAlgoLED,
                error_code=TargetErrorCode.TOO_MANY_CONDITIONS,
                message="Too many filter conditions (max 10)",
            )

        # Собираем атрибуты
        attrs = order.filter.to_target_attrs()

        # Создаём таргет через менеджер
        result = await self.targets.create_target(
            title=order.item_title,
            price=int(order.max_price_usd * 100),
            amount=order.amount,
            attrs=attrs,
        )

        if result.success and result.target_id:
            order.target_id = result.target_id
            order.is_active = True
            self.active_orders[result.target_id] = order

        return result

    async def create_from_template(
        self,
        template_name: str,
        max_price_usd: float | None = None,
    ) -> TargetOperationResult | None:
        """Создать ордер из шаблона.

        Args:
            template_name: Название шаблона
            max_price_usd: Максимальная цена (опционально)

        Returns:
            Результат операции или None если шаблон не найден
        """
        template = self.templates.get(template_name)
        if not template:
            logger.warning(f"Template not found: {template_name}")
            return None

        order = template.create_order(max_price_usd)
        return await self.create_order(order)

    def list_templates(self) -> list[dict[str, Any]]:
        """Получить список доступных шаблонов."""
        return [
            {
                "name": name,
                "description": t.description,
                "item": t.item_title,
                "base_price": t.base_price_usd,
                "expected_premium": t.expected_premium_multiplier,
            }
            for name, t in self.templates.items()
        ]

    def get_active_orders(self) -> list[AdvancedOrder]:
        """Получить активные ордера."""
        return [o for o in self.active_orders.values() if o.is_active]

    async def cancel_order(self, target_id: str) -> bool:
        """Отменить ордер."""
        if target_id not in self.active_orders:
            return False

        result = await self.targets.delete_target(target_id)
        if result:
            self.active_orders[target_id].is_active = False

        return result

    async def cancel_all_orders(self) -> int:
        """Отменить все активные ордера.

        Returns:
            Количество отменённых ордеров
        """
        cancelled = 0
        for target_id in list(self.active_orders.keys()):
            if await self.cancel_order(target_id):
                cancelled += 1

        return cancelled


# ==================== БЫСТРЫЕ ФУНКЦИИ ДЛЯ СОЗДАНИЯ ОРДЕРОВ ====================


def create_float_order(
    item_title: str,
    float_min: float,
    float_max: float,
    max_price: float,
    expected_sell: float | None = None,
) -> AdvancedOrder:
    """Быстрое создание ордера с фильтром по флоату.

    Пример:
        order = create_float_order(
            "AK-47 | Redline (Field-Tested)",
            float_min=0.15,
            float_max=0.155,
            max_price=55.0,
            expected_sell=62.0
        )
    """
    return AdvancedOrder(
        item_title=item_title,
        max_price_usd=max_price,
        filter=AdvancedOrderFilter(float_min=float_min, float_max=float_max),
        expected_sell_price=expected_sell,
    )


def create_doppler_order(
    item_title: str,
    phase: DopplerPhase,
    max_price: float,
) -> AdvancedOrder:
    """Быстрое создание ордера на Doppler определённой фазы."""
    premium = DOPPLER_PREMIUMS.get(phase, 1.0)
    expected_sell = max_price * premium

    return AdvancedOrder(
        item_title=item_title,
        max_price_usd=max_price,
        filter=AdvancedOrderFilter(phase=phase),
        expected_sell_price=expected_sell,
        notes=f"Doppler {phase.value}",
    )


def create_pattern_order(
    item_title: str,
    paint_seeds: list[int],
    max_price: float,
    expected_premium: float = 2.0,
) -> AdvancedOrder:
    """Быстрое создание ордера на определённые паттерны."""
    return AdvancedOrder(
        item_title=item_title,
        max_price_usd=max_price,
        filter=AdvancedOrderFilter(paint_seeds=paint_seeds),
        expected_sell_price=max_price * expected_premium,
        notes=f"Patterns: {paint_seeds}",
    )


def create_sticker_order(
    item_title: str,
    sticker_categories: list[str],
    max_price: float,
    holo: bool = False,
    min_stickers: int = 1,
) -> AdvancedOrder:
    """Быстрое создание ордера с фильтром по стикерам."""
    return AdvancedOrder(
        item_title=item_title,
        max_price_usd=max_price,
        filter=AdvancedOrderFilter(
            sticker_filter=StickerFilter(
                sticker_categories=sticker_categories,
                holo=holo,
                min_stickers=min_stickers,
            )
        ),
        notes=f"Stickers: {sticker_categories}, Holo: {holo}",
    )
