"""Float Value Arbitrage Module - Стратегии заработка на флоате.

Реализация стратегий CS Float для DMarket бота:
1. Float Range Orders - ордера с фильтрами по диапазону флоата
2. Float Premium Calculator - расчёт премии за низкий флоат
3. Historical Quartile Analysis - покупка только ниже 25% квартиля
4. Float-based Auto Pricing - автоматическое ценообразование

Основано на статье:
https://info.tacompany.ru/skhemy-zarabotka-v-steam/rasshirennye-ordera-cs-float

Январь 2026
"""

import logging
import statistics
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.interfaces import IDMarketAPI


logger = logging.getLogger(__name__)


class FloatQuality(StrEnum):
    """Категории флоата для CS2 предметов."""

    FACTORY_NEW = "fn"  # 0.00 - 0.07
    MINIMAL_WEAR = "mw"  # 0.07 - 0.15
    FIELD_TESTED = "ft"  # 0.15 - 0.38
    WELL_WORN = "ww"  # 0.38 - 0.45
    BATTLE_SCARRED = "bs"  # 0.45 - 1.00


# Диапазоны флоата по качеству
FLOAT_RANGES: dict[FloatQuality, tuple[float, float]] = {
    FloatQuality.FACTORY_NEW: (0.00, 0.07),
    FloatQuality.MINIMAL_WEAR: (0.07, 0.15),
    FloatQuality.FIELD_TESTED: (0.15, 0.38),
    FloatQuality.WELL_WORN: (0.38, 0.45),
    FloatQuality.BATTLE_SCARRED: (0.45, 1.00),
}

# Премиальные диапазоны флоата с множителем цены
# Пример: AK-47 Redline FT с флоатом 0.15-0.155 стоит ~$62 vs $33 за 0.30
PREMIUM_FLOAT_RANGES: dict[str, dict[str, tuple[float, float, float]]] = {
    # weapon_skin: {quality: (float_min, float_max, price_multiplier)}
    "AK-47 | Redline": {
        "ft_premium": (0.15, 0.155, 1.88),  # 88% премия за лучший FT
        "ft_good": (0.15, 0.16, 1.80),  # 80% премия
        "ft_standard": (0.16, 0.20, 1.30),  # 30% премия
    },
    "AWP | Asiimov": {
        "ft_premium": (0.18, 0.20, 1.25),  # Asiimov FT минимум 0.18
        "ft_good": (0.18, 0.22, 1.15),
        "bs_clean": (0.45, 0.50, 1.40),  # "Черный" Asiimov
    },
    "M4A1-S | Hyper Beast": {
        "fn_premium": (0.00, 0.01, 1.50),  # Очень низкий FN
        "fn_good": (0.00, 0.03, 1.20),
    },
    # Добавьте больше скинов по мере надобности
}


@dataclass
class FloatOrderConfig:
    """Конфигурация ордера с фильтром по флоату.

    Пример из CS Float:
    - AK-47 Redline FT, Float 0.15-0.155 = $61.85
    - AK-47 Redline FT, Float 0.15-0.16 = $59.11
    - AK-47 Redline FT, Float 0.30 (обычный) = $32.82
    """

    item_title: str
    float_min: float
    float_max: float
    max_price_usd: float
    expected_premium: float = 1.0  # Ожидаемый множитель продажи
    amount: int = 1
    notes: str = ""

    def to_target_attrs(self) -> dict[str, Any]:
        """Конвертировать в атрибуты для DMarket API."""
        return {
            "floatMin": str(self.float_min),
            "floatMax": str(self.float_max),
        }


@dataclass
class FloatPremiumResult:
    """Результат анализа премии за флоат."""

    item_title: str
    current_float: float
    quality: FloatQuality
    base_market_price: float  # Обычная цена на рынке
    premium_price: float  # Цена с учётом флоата
    premium_multiplier: float  # Множитель премии
    is_profitable: bool
    reason: str
    recommended_buy_price: float
    expected_sell_price: float
    estimated_profit_usd: float
    estimated_profit_percent: float


@dataclass
class QuartileAnalysisResult:
    """Результат квартильного анализа цен."""

    item_title: str
    current_price: float
    q1_price: float  # 25% квартиль
    q2_price: float  # Медиана (50%)
    q3_price: float  # 75% квартиль
    mean_price: float
    min_price: float
    max_price: float
    sales_count: int
    is_good_buy: bool  # Цена ниже Q1?
    percentile: float  # В каком перцентиле текущая цена


@dataclass
class FloatArbitrageOpportunity:
    """Возможность арбитража на флоате."""

    item_title: str
    item_id: str
    current_price_usd: float
    float_value: float
    quality: FloatQuality

    # Анализ премии
    expected_sell_price: float
    profit_usd: float
    profit_percent: float
    premium_tier: str  # "premium", "good", "standard"

    # Конкуренция
    competing_orders: int
    highest_competitor_bid: float | None

    # Рекомендации
    recommended_action: str
    confidence_score: float  # 0-100

    # Метаданные
    detected_at: str = field(default_factory=lambda: "")


class FloatValueArbitrage:
    """Модуль арбитража на основе Float Value.

    Стратегии:
    1. Premium Float Orders - ордера на скины с премиальным флоатом
    2. Quartile Analysis - покупка только ниже 25% квартиля
    3. Float-based Pricing - ценообразование с учётом флоата
    """

    def __init__(
        self,
        api_client: "IDMarketAPI",
        commission_percent: float = 5.0,  # DMarket комиссия
        min_profit_margin: float = 10.0,  # Минимальная маржа %
    ):
        """Инициализация модуля.

        Args:
            api_client: DMarket API клиент
            commission_percent: Комиссия площадки (%)
            min_profit_margin: Минимальная маржа для сделки (%)
        """
        self.api = api_client
        self.commission = commission_percent / 100
        self.min_margin = min_profit_margin / 100

        logger.info(
            "FloatValueArbitrage initialized",
            extra={
                "commission": commission_percent,
                "min_margin": min_profit_margin,
            },
        )

    def get_float_quality(self, float_value: float) -> FloatQuality:
        """Определить качество предмета по флоату.

        Args:
            float_value: Значение флоата (0.0 - 1.0)

        Returns:
            Категория качества
        """
        for quality, (min_f, max_f) in FLOAT_RANGES.items():
            if min_f <= float_value < max_f:
                return quality
        return FloatQuality.BATTLE_SCARRED

    def calculate_float_premium(
        self,
        item_title: str,
        float_value: float,
        base_market_price: float,
    ) -> FloatPremiumResult:
        """Рассчитать премию за низкий флоат.

        Пример:
        - AK-47 Redline FT обычная цена: $32.82
        - С флоатом 0.15-0.155: $61.85 (премия 88%)

        Args:
            item_title: Название предмета
            float_value: Значение флоата
            base_market_price: Базовая рыночная цена

        Returns:
            Результат анализа премии
        """
        quality = self.get_float_quality(float_value)

        # Поиск премиальных диапазонов для этого предмета
        premium_multiplier = 1.0
        premium_tier = "standard"

        # Ищем совпадение по названию (частичное)
        for skin_name, ranges in PREMIUM_FLOAT_RANGES.items():
            if skin_name.lower() in item_title.lower():
                for tier_name, (f_min, f_max, multiplier) in ranges.items():
                    if f_min <= float_value < f_max:
                        if multiplier > premium_multiplier:
                            premium_multiplier = multiplier
                            premium_tier = tier_name
                break

        # Если не найдено в словаре, используем общую формулу
        if premium_multiplier == 1.0:
            premium_multiplier = self._calculate_generic_premium(float_value, quality)

        premium_price = base_market_price * premium_multiplier
        sell_price_after_commission = premium_price * (1 - self.commission)
        recommended_buy_price = sell_price_after_commission / (1 + self.min_margin)

        profit = sell_price_after_commission - base_market_price
        profit_percent = (
            (profit / base_market_price) * 100 if base_market_price > 0 else 0
        )

        is_profitable = profit_percent >= self.min_margin * 100

        return FloatPremiumResult(
            item_title=item_title,
            current_float=float_value,
            quality=quality,
            base_market_price=base_market_price,
            premium_price=premium_price,
            premium_multiplier=premium_multiplier,
            is_profitable=is_profitable,
            reason=f"Float {float_value:.4f} ({premium_tier}): {premium_multiplier:.0%} премия",
            recommended_buy_price=recommended_buy_price,
            expected_sell_price=premium_price,
            estimated_profit_usd=profit,
            estimated_profit_percent=profit_percent,
        )

    def _calculate_generic_premium(
        self,
        float_value: float,
        quality: FloatQuality,
    ) -> float:
        """Рассчитать общую премию для предмета без специфичных данных.

        Формула основана на позиции флоата в диапазоне качества.
        Чем ниже флоат в диапазоне, тем выше премия.
        """
        f_min, f_max = FLOAT_RANGES[quality]
        range_size = f_max - f_min

        if range_size == 0:
            return 1.0

        # Позиция в диапазоне (0 = лучший, 1 = худший)
        position = (float_value - f_min) / range_size

        # Премия растёт экспоненциально для низких флоатов
        # Максимум 50% премии для лучших флоатов в диапазоне
        max_premium = 0.50

        if position < 0.05:  # Топ 5% в диапазоне
            return 1.0 + max_premium
        if position < 0.10:  # Топ 10%
            return 1.0 + max_premium * 0.7
        if position < 0.20:  # Топ 20%
            return 1.0 + max_premium * 0.4
        if position < 0.30:  # Топ 30%
            return 1.0 + max_premium * 0.2

        return 1.0  # Нет премии

    def _percentile(self, data: list[float], percentile: float) -> float:
        """Рассчитать перцентиль без numpy."""
        if not data:
            return 0.0

        n = len(data)
        k = (n - 1) * percentile / 100
        f = int(k)
        c = f + 1 if f + 1 < n else f

        if f == c:
            return data[f]

        return data[f] * (c - k) + data[c] * (k - f)

    async def analyze_sales_quartiles(
        self,
        item_title: str,
        days: int = 30,
    ) -> QuartileAnalysisResult | None:
        """Квартильный анализ истории продаж.

        Стратегия: покупать только если цена ниже 25% квартиля (Q1).
        Это гарантирует что мы покупаем дешевле чем 75% продаж.

        Args:
            item_title: Название предмета
            days: Период анализа в днях

        Returns:
            Результат квартильного анализа или None
        """
        try:
            # Получаем историю продаж
            history = await self.api.get_sales_history(item_title, period=days)

            if not history or "sales" not in history:
                logger.warning(f"No sales history for {item_title}")
                return None

            sales = history["sales"]
            if len(sales) < 10:
                logger.warning(f"Not enough sales data for {item_title}: {len(sales)}")
                return None

            # Извлекаем цены
            prices = [float(s.get("price", {}).get("USD", 0)) / 100 for s in sales]
            prices = [p for p in prices if p > 0]

            if not prices:
                return None

            # Расчёт квартилей (используем statistics вместо numpy)
            sorted_prices = sorted(prices)
            n = len(sorted_prices)

            # Q1 (25%), Q2 (50% медиана), Q3 (75%)
            q1 = self._percentile(sorted_prices, 25)
            q2 = statistics.median(sorted_prices)
            q3 = self._percentile(sorted_prices, 75)
            mean_price = statistics.mean(sorted_prices)

            # Текущая минимальная цена на рынке
            current_price = await self._get_current_min_price(item_title)

            if current_price is None:
                return None

            # Определяем перцентиль текущей цены
            below_count = sum(1 for p in sorted_prices if p <= current_price)
            percentile = (below_count / n) * 100

            return QuartileAnalysisResult(
                item_title=item_title,
                current_price=current_price,
                q1_price=q1,
                q2_price=q2,
                q3_price=q3,
                mean_price=mean_price,
                min_price=min(sorted_prices),
                max_price=max(sorted_prices),
                sales_count=n,
                is_good_buy=current_price <= q1,
                percentile=percentile,
            )

        except Exception as e:
            logger.exception(f"Error analyzing quartiles for {item_title}: {e}")
            return None

    async def _get_current_min_price(self, item_title: str) -> float | None:
        """Получить текущую минимальную цену на рынке."""
        try:
            items = await self.api.get_market_items(
                game="csgo",
                title=item_title,
                limit=1,
                order_by="price",
                order_dir="asc",
            )

            if items and "objects" in items and items["objects"]:
                price_data = items["objects"][0].get("price", {})
                return float(price_data.get("USD", 0)) / 100

            return None
        except Exception as e:
            logger.exception(f"Error getting min price for {item_title}: {e}")
            return None

    def create_float_order_config(
        self,
        item_title: str,
        float_range: tuple[float, float],
        max_price_usd: float,
        expected_sell_multiplier: float = 1.0,
    ) -> FloatOrderConfig:
        """Создать конфигурацию ордера с фильтром по флоату.

        Пример использования (как на CS Float):
        - AK-47 Redline FT, Float 0.15-0.155, Max $50
        - Ожидаемая продажа: $62 (множитель 1.24)

        Args:
            item_title: Название предмета
            float_range: (мин_флоат, макс_флоат)
            max_price_usd: Максимальная цена покупки
            expected_sell_multiplier: Ожидаемый множитель продажи

        Returns:
            Конфигурация ордера
        """
        float_min, float_max = float_range

        return FloatOrderConfig(
            item_title=item_title,
            float_min=float_min,
            float_max=float_max,
            max_price_usd=max_price_usd,
            expected_premium=expected_sell_multiplier,
            notes=f"Float filter: {float_min:.3f}-{float_max:.3f}",
        )

    async def find_float_arbitrage_opportunities(
        self,
        game: str = "csgo",
        min_price: float = 10.0,
        max_price: float = 100.0,
        limit: int = 50,
    ) -> list[FloatArbitrageOpportunity]:
        """Найти возможности арбитража на флоате.

        Ищет предметы где флоат значительно лучше среднего,
        но цена не отражает эту премию.

        Args:
            game: Игра (только csgo поддерживает float)
            min_price: Минимальная цена
            max_price: Максимальная цена
            limit: Лимит результатов

        Returns:
            Список возможностей арбитража
        """
        if game != "csgo":
            logger.warning("Float arbitrage only avAlgolable for CS:GO")
            return []

        opportunities: list[FloatArbitrageOpportunity] = []

        try:
            # Получаем предметы с рынка
            items = await self.api.get_market_items(
                game=game,
                price_from=int(min_price * 100),
                price_to=int(max_price * 100),
                limit=limit,
                order_by="updated",
            )

            if not items or "objects" not in items:
                return []

            for item in items["objects"]:
                opportunity = await self._analyze_item_float(item)
                if opportunity and opportunity.profit_percent >= self.min_margin * 100:
                    opportunities.append(opportunity)

            # Сортируем по прибыли
            opportunities.sort(key=lambda x: x.profit_percent, reverse=True)

            return opportunities[:limit]

        except Exception as e:
            logger.exception(f"Error finding float opportunities: {e}")
            return []

    async def _analyze_item_float(
        self,
        item: dict[str, Any],
    ) -> FloatArbitrageOpportunity | None:
        """Проанализировать флоат предмета для арбитража."""
        try:
            # Извлекаем данные
            item_id = item.get("itemId", "")
            title = item.get("title", "")
            price_data = item.get("price", {})
            current_price = float(price_data.get("USD", 0)) / 100

            if current_price <= 0:
                return None

            # Извлекаем флоат из extra
            extra = item.get("extra", {})
            float_value = extra.get("floatValue")

            if float_value is None:
                # Пробуем из exterior
                float_str = extra.get("floatPartValue")
                if float_str:
                    try:
                        float_value = float(float_str)
                    except (ValueError, TypeError):
                        return None
                else:
                    return None

            float_value = float(float_value)
            quality = self.get_float_quality(float_value)

            # Анализ премии
            premium_result = self.calculate_float_premium(
                title,
                float_value,
                current_price,
            )

            if not premium_result.is_profitable:
                return None

            # Определяем tier
            premium_tier = "standard"
            if premium_result.premium_multiplier >= 1.5:
                premium_tier = "premium"
            elif premium_result.premium_multiplier >= 1.2:
                premium_tier = "good"

            from datetime import datetime

            return FloatArbitrageOpportunity(
                item_title=title,
                item_id=item_id,
                current_price_usd=current_price,
                float_value=float_value,
                quality=quality,
                expected_sell_price=premium_result.expected_sell_price,
                profit_usd=premium_result.estimated_profit_usd,
                profit_percent=premium_result.estimated_profit_percent,
                premium_tier=premium_tier,
                competing_orders=0,  # TODO: получить из API
                highest_competitor_bid=None,
                recommended_action="BUY" if premium_result.is_profitable else "SKIP",
                confidence_score=min(premium_result.premium_multiplier * 50, 100),
                detected_at=datetime.now().isoformat(),
            )

        except Exception as e:
            logger.debug(f"Error analyzing item float: {e}")
            return None


# ==================== ПРЕДУСТАНОВЛЕННЫЕ КОНФИГИ ОРДЕРОВ ====================


def get_premium_ak47_redline_orders() -> list[FloatOrderConfig]:
    """Предустановленные ордера на AK-47 Redline с премиальным флоатом.

    Основано на реальных ценах CS Float:
    - Float 0.15-0.155: ~$62
    - Float 0.15-0.16: ~$59
    - Float обычный: ~$33
    """
    return [
        FloatOrderConfig(
            item_title="AK-47 | Redline (Field-Tested)",
            float_min=0.15,
            float_max=0.155,
            max_price_usd=55.0,
            expected_premium=1.88,
            notes="Top tier FT float, sell for ~$62",
        ),
        FloatOrderConfig(
            item_title="AK-47 | Redline (Field-Tested)",
            float_min=0.15,
            float_max=0.16,
            max_price_usd=52.0,
            expected_premium=1.80,
            notes="Good FT float, sell for ~$59",
        ),
        FloatOrderConfig(
            item_title="AK-47 | Redline (Field-Tested)",
            float_min=0.16,
            float_max=0.18,
            max_price_usd=42.0,
            expected_premium=1.40,
            notes="Above average FT, sell for ~$46",
        ),
    ]


def get_premium_awp_asiimov_orders() -> list[FloatOrderConfig]:
    """Предустановленные ордера на AWP Asiimov."""
    return [
        FloatOrderConfig(
            item_title="AWP | Asiimov (Field-Tested)",
            float_min=0.18,
            float_max=0.20,
            max_price_usd=95.0,
            expected_premium=1.25,
            notes="Best possible FT Asiimov float",
        ),
        FloatOrderConfig(
            item_title="AWP | Asiimov (Battle-Scarred)",
            float_min=0.45,
            float_max=0.50,
            max_price_usd=45.0,
            expected_premium=1.40,
            notes="Blackiimov - clean black scope",
        ),
    ]


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================


def format_float_opportunity(opp: FloatArbitrageOpportunity) -> str:
    """Форматировать возможность арбитража для отображения."""
    return (
        f"🎯 {opp.item_title}\n"
        f"   Float: {opp.float_value:.4f} ({opp.quality.value})\n"
        f"   Цена: ${opp.current_price_usd:.2f} → ${opp.expected_sell_price:.2f}\n"
        f"   Прибыль: ${opp.profit_usd:.2f} ({opp.profit_percent:.1f}%)\n"
        f"   Tier: {opp.premium_tier} | Confidence: {opp.confidence_score:.0f}%"
    )
