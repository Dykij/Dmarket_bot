"""Shadow Listing Manager - умное ценообразование при дефиците.

Этот модуль реализует стратегию "теневого выставления":
- Анализ глубины рынка (сколько конкурентов)
- Режим дефицита (поднятие цены когда товара мало)
- Умный undercut (не сразу снижать цену)
- Ожидание продажи конкурента

Алгоритм:
1. Проверяем 5 самых дешевых лотов конкурентов
2. Если разрыв между 1 и 2 ценой > 5%, ставим цену 2-го минус 1 цент
3. Если на рынке < 3 предметов, ставим цену +10% от Steam
4. Если конкурент "подрезал" на 1 цент, ждем 2 часа

Использование:
    ```python
    from src.dmarket.shadow_listing import ShadowListingManager

    manager = ShadowListingManager(api_client)
    price = await manager.calculate_optimal_price(
        item_id="item123", buy_price=10.0, current_market_price=11.0
    )
    ```
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI


logger = logging.getLogger(__name__)


class MarketCondition(StrEnum):
    """Состояние рынка для предмета."""

    OVERSUPPLY = "oversupply"  # Много предложений - агрессивный демпинг
    NORMAL = "normal"  # Нормальный рынок - стандартный undercut
    SCARCITY = "scarcity"  # Дефицит - можно поднять цену
    MONOPOLY = "monopoly"  # Мы единственный продавец - максимальная цена


class PricingAction(StrEnum):
    """Рекомендуемое действие по цене."""

    UNDERCUT = "undercut"  # Снизить цену
    HOLD = "hold"  # Держать текущую цену
    RAISE = "raise"  # Поднять цену
    WAIT = "wait"  # Подождать (не реагировать на мелкий undercut)


@dataclass
class MarketDepthAnalysis:
    """Результат анализа глубины рынка."""

    item_title: str
    total_offers: int  # Всего предложений на рынке
    our_offer_id: str | None  # ID нашего предложения
    our_price: float | None  # Наша текущая цена

    # Цены конкурентов (топ-5)
    competitor_prices: list[float]  # Цены от низкой к высокой
    lowest_competitor_price: float | None
    second_lowest_price: float | None

    # Референсные цены
    steam_price: float | None  # Цена Steam Market
    suggested_price: float | None  # Рекомендованная DMarket

    # Анализ
    market_condition: MarketCondition
    price_gap_percent: float  # Разрыв между 1 и 2 ценой (%)
    our_position: int  # Наша позиция в списке (1 = самый дешевый)

    # Рекомендации
    recommended_action: PricingAction
    recommended_price: float | None
    reason: str


@dataclass
class ShadowListingConfig:
    """Конфигурация Shadow Listing."""

    # Пороги дефицита
    scarcity_threshold: int = 3  # Менее 3 лотов = дефицит
    monopoly_threshold: int = 1  # Только наш лот = монополия

    # Ценообразование при дефиците
    scarcity_markup_percent: float = 10.0  # +10% при дефиците
    monopoly_markup_percent: float = 15.0  # +15% при монополии

    # Умный undercut
    min_undercut_cents: int = 1  # Минимум 1 цент ниже
    max_undercut_percent: float = 2.0  # Максимум 2% ниже

    # Ожидание при мелком undercut
    wait_hours_on_small_undercut: int = 2  # Ждать 2 часа
    small_undercut_threshold_cents: int = 5  # Менее 5 центов = мелкий

    # Анализ разрыва цен
    large_gap_threshold_percent: float = 5.0  # Разрыв > 5% = большой

    # Лимиты
    max_price_above_steam_percent: float = 15.0  # Не более +15% от Steam
    min_profit_margin_percent: float = 3.0  # Минимум 3% маржи


class ShadowListingManager:
    """Менеджер умного ценообразования.

    Анализирует рынок и предлагает оптимальную цену продажи
    с учетом конкуренции, дефицита и истории цен.
    """

    def __init__(
        self,
        api_client: DMarketAPI,
        config: ShadowListingConfig | None = None,
    ) -> None:
        """Инициализация менеджера.

        Args:
            api_client: DMarket API клиент
            config: Конфигурация (опционально)
        """
        self.api = api_client
        self.config = config or ShadowListingConfig()

        # Кэш истории undercut (для отслеживания мелких подрезов)
        self._undercut_history: dict[str, list[tuple[datetime, float]]] = {}

        logger.info(
            "ShadowListingManager initialized: "
            f"scarcity_threshold={self.config.scarcity_threshold}, "
            f"scarcity_markup={self.config.scarcity_markup_percent}%"
        )

    async def analyze_market_depth(
        self,
        item_title: str,
        game: str = "csgo",
        our_offer_id: str | None = None,
        our_current_price: float | None = None,
    ) -> MarketDepthAnalysis:
        """Анализировать глубину рынка для предмета.

        Args:
            item_title: Название предмета
            game: Код игры
            our_offer_id: ID нашего предложения (если есть)
            our_current_price: Наша текущая цена

        Returns:
            MarketDepthAnalysis с результатами
        """
        # Получаем предложения с рынка
        try:
            market_data = await self.api.get_market_items(
                title=item_title,
                game=game,
                limit=20,  # Берем топ-20 для анализа
            )
        except Exception as e:
            logger.exception(f"Failed to fetch market data: {e}")
            return self._create_default_analysis(item_title, our_current_price)

        # Парсим данные
        offers = market_data.get("objects", [])
        if not offers:
            return self._create_monopoly_analysis(item_title, our_current_price)

        # Извлекаем цены конкурентов
        competitor_prices: list[float] = []
        steam_price: float | None = None
        suggested_price: float | None = None
        our_position = 0

        for i, offer in enumerate(offers):
            # Парсим цену
            price_data = offer.get("price", {})
            if isinstance(price_data, dict):
                price_cents = price_data.get("USD") or price_data.get("amount", 0)
            else:
                price_cents = price_data or 0

            try:
                price_usd = float(price_cents) / 100
            except (ValueError, TypeError):
                continue

            # Проверяем, наше ли это предложение
            offer_id = offer.get("offerId") or offer.get("extra", {}).get("offerId")
            if our_offer_id and offer_id == our_offer_id:
                our_position = i + 1
                continue

            competitor_prices.append(price_usd)

            # Steam price (берем из первого предложения)
            if steam_price is None:
                steam_data = offer.get("suggestedPrice", {})
                if isinstance(steam_data, dict):
                    steam_cents = steam_data.get("USD") or steam_data.get("amount", 0)
                    if steam_cents:
                        steam_price = float(steam_cents) / 100

        # Сортируем цены
        competitor_prices.sort()

        # Определяем состояние рынка
        market_condition = self._determine_market_condition(len(competitor_prices))

        # Анализируем разрыв цен
        price_gap = 0.0
        if len(competitor_prices) >= 2:
            gap = competitor_prices[1] - competitor_prices[0]
            if competitor_prices[0] > 0:
                price_gap = (gap / competitor_prices[0]) * 100

        # Получаем рекомендацию
        action, price, reason = self._get_pricing_recommendation(
            competitor_prices=competitor_prices,
            our_price=our_current_price,
            steam_price=steam_price,
            market_condition=market_condition,
            price_gap=price_gap,
            item_title=item_title,
        )

        return MarketDepthAnalysis(
            item_title=item_title,
            total_offers=len(offers),
            our_offer_id=our_offer_id,
            our_price=our_current_price,
            competitor_prices=competitor_prices[:5],
            lowest_competitor_price=competitor_prices[0] if competitor_prices else None,
            second_lowest_price=competitor_prices[1] if len(competitor_prices) > 1 else None,
            steam_price=steam_price,
            suggested_price=suggested_price,
            market_condition=market_condition,
            price_gap_percent=price_gap,
            our_position=our_position,
            recommended_action=action,
            recommended_price=price,
            reason=reason,
        )

    def _determine_market_condition(self, competitor_count: int) -> MarketCondition:
        """Определить состояние рынка."""
        if competitor_count == 0:
            return MarketCondition.MONOPOLY
        if competitor_count < self.config.scarcity_threshold:
            return MarketCondition.SCARCITY
        if competitor_count > 20:
            return MarketCondition.OVERSUPPLY
        return MarketCondition.NORMAL

    def _get_pricing_recommendation(
        self,
        competitor_prices: list[float],
        our_price: float | None,
        steam_price: float | None,
        market_condition: MarketCondition,
        price_gap: float,
        item_title: str,
    ) -> tuple[PricingAction, float | None, str]:
        """Получить рекомендацию по цене.

        Returns:
            Tuple of (action, recommended_price, reason)
        """
        # МОНОПОЛИЯ: мы единственные
        if market_condition == MarketCondition.MONOPOLY:
            if steam_price:
                markup = 1 + (self.config.monopoly_markup_percent / 100)
                price = round(steam_price * markup, 2)
                return (
                    PricingAction.RAISE,
                    price,
                    f"Monopoly: No competitors, set price {self.config.monopoly_markup_percent}% above Steam",
                )
            return (PricingAction.HOLD, our_price, "Monopoly: No competitors, hold current price")

        lowest = competitor_prices[0] if competitor_prices else None
        if lowest is None:
            return (PricingAction.HOLD, our_price, "No competitor prices available")

        # ДЕФИЦИТ: мало товара на рынке
        if market_condition == MarketCondition.SCARCITY:
            if steam_price:
                # Ставим выше Steam, но ниже максимума
                markup = 1 + (self.config.scarcity_markup_percent / 100)
                max_markup = 1 + (self.config.max_price_above_steam_percent / 100)

                target_price = min(steam_price * markup, steam_price * max_markup)
                # Но не выше второй цены (если есть)
                if len(competitor_prices) > 1:
                    target_price = min(target_price, competitor_prices[1])

                return (
                    PricingAction.RAISE,
                    round(target_price, 2),
                    f"Scarcity: Only {len(competitor_prices)} offers, raised price",
                )

        # БОЛЬШОЙ РАЗРЫВ: между 1 и 2 ценой
        if price_gap > self.config.large_gap_threshold_percent and len(competitor_prices) >= 2:
            # Ставим цену второго минус 1 цент
            second_price = competitor_prices[1]
            new_price = round(second_price - 0.01, 2)

            return (
                PricingAction.UNDERCUT,
                new_price,
                f"Large gap ({price_gap:.1f}%): Set price just below 2nd offer",
            )

        # МЕЛКИЙ UNDERCUT: проверяем нужно ли реагировать
        if our_price is not None:
            undercut_amount = (our_price - lowest) * 100  # В центах
            if 0 < undercut_amount <= self.config.small_undercut_threshold_cents:
                # Проверяем историю undercut
                if self._should_wait_for_competitor_sale(item_title, lowest):
                    return (
                        PricingAction.WAIT,
                        our_price,
                        f"Small undercut ({undercut_amount:.0f}¢): Waiting for competitor to sell",
                    )

        # СТАНДАРТНЫЙ UNDERCUT
        undercut_amount = min(
            self.config.min_undercut_cents / 100,  # Минимум N центов
            lowest * (self.config.max_undercut_percent / 100),  # Максимум N%
        )
        new_price = round(lowest - undercut_amount, 2)

        return (
            PricingAction.UNDERCUT,
            new_price,
            f"Standard undercut: ${lowest:.2f} -> ${new_price:.2f}",
        )

    def _should_wait_for_competitor_sale(self, item_title: str, competitor_price: float) -> bool:
        """Проверить, нужно ли ждать продажи конкурента.

        Если конкурент только что "подрезал" нас на мелкую сумму,
        имеет смысл подождать - возможно его купят.
        """
        history = self._undercut_history.get(item_title, [])

        # Записываем текущий undercut
        now = datetime.now(UTC)
        history.append((now, competitor_price))

        # Оставляем только записи за последние N часов
        cutoff = now - timedelta(hours=self.config.wait_hours_on_small_undercut)
        history = [(t, p) for t, p in history if t > cutoff]
        self._undercut_history[item_title] = history

        # Если это первый undercut за период - ждем
        if len(history) <= 1:
            return True

        # Если undercut был недавно по такой же цене - продолжаем ждать
        recent = [p for t, p in history if t > now - timedelta(hours=1)]
        return bool(len(recent) >= 1 and recent[-1] == competitor_price)

    def _create_default_analysis(
        self,
        item_title: str,
        our_price: float | None,
    ) -> MarketDepthAnalysis:
        """Создать дефолтный анализ при ошибке."""
        return MarketDepthAnalysis(
            item_title=item_title,
            total_offers=0,
            our_offer_id=None,
            our_price=our_price,
            competitor_prices=[],
            lowest_competitor_price=None,
            second_lowest_price=None,
            steam_price=None,
            suggested_price=None,
            market_condition=MarketCondition.NORMAL,
            price_gap_percent=0.0,
            our_position=0,
            recommended_action=PricingAction.HOLD,
            recommended_price=our_price,
            reason="Market data unavailable, holding current price",
        )

    def _create_monopoly_analysis(
        self,
        item_title: str,
        our_price: float | None,
    ) -> MarketDepthAnalysis:
        """Создать анализ для ситуации монополии."""
        return MarketDepthAnalysis(
            item_title=item_title,
            total_offers=0,
            our_offer_id=None,
            our_price=our_price,
            competitor_prices=[],
            lowest_competitor_price=None,
            second_lowest_price=None,
            steam_price=None,
            suggested_price=None,
            market_condition=MarketCondition.MONOPOLY,
            price_gap_percent=0.0,
            our_position=1,
            recommended_action=PricingAction.RAISE,
            recommended_price=our_price,
            reason="Monopoly: You are the only seller",
        )

    async def calculate_optimal_price(
        self,
        item_title: str,
        buy_price: float,
        current_market_price: float | None = None,
        game: str = "csgo",
        our_offer_id: str | None = None,
    ) -> float:
        """Рассчитать оптимальную цену для выставления.

        Args:
            item_title: Название предмета
            buy_price: Цена покупки (для расчета минимальной маржи)
            current_market_price: Текущая рыночная цена (опционально)
            game: Код игры
            our_offer_id: ID нашего предложения

        Returns:
            Оптимальная цена в USD
        """
        # Анализируем рынок
        analysis = await self.analyze_market_depth(
            item_title=item_title,
            game=game,
            our_offer_id=our_offer_id,
            our_current_price=current_market_price,
        )

        # Получаем рекомендованную цену
        recommended = analysis.recommended_price

        if recommended is None:
            # Fallback: цена покупки + минимальная маржа
            min_margin = 1 + (self.config.min_profit_margin_percent / 100)
            recommended = round(buy_price * min_margin / 0.93, 2)  # С учетом комиссии

        # Проверяем минимальную маржу
        min_margin = 1 + (self.config.min_profit_margin_percent / 100)
        min_price = round(buy_price * min_margin / 0.93, 2)

        final_price = max(recommended, min_price)

        logger.info(
            f"Optimal price calculated: {item_title} "
            f"(buy=${buy_price:.2f}, recommended=${recommended:.2f}, "
            f"final=${final_price:.2f}, action={analysis.recommended_action})"
        )

        return final_price

    def get_statistics(self) -> dict[str, Any]:
        """Получить статистику работы менеджера."""
        return {
            "tracked_items": len(self._undercut_history),
            "config": {
                "scarcity_threshold": self.config.scarcity_threshold,
                "scarcity_markup": self.config.scarcity_markup_percent,
                "monopoly_markup": self.config.monopoly_markup_percent,
                "wait_hours": self.config.wait_hours_on_small_undercut,
            },
        }
