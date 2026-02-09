"""Умный поиск выгодных предметов для покупки и продажи на DMarket.

Этот модуль использует комплексный анализ рынка для поиска наиболее выгодных
возможностей для арбитража на основе множества факторов:
- Текущие цены на маркете
- Агрегированные цены (лучшие предложения на продажу/покупку)
- История продаж и трендов
- Ликвидность предметов
- Волатильность цен
- Популярность предметов

Основан на официальной документации DMarket API.
"""

import logging
import operator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from src.dmarket.dmarket_api import DMarketAPI

logger = logging.getLogger(__name__)


class MarketOpportunityType(StrEnum):
    """Типы рыночных возможностей."""

    UNDERPRICED = "underpriced"  # Заниженная цена относительно среднего
    TRENDING_UP = "trending_up"  # Растущий тренд цены
    HIGH_LIQUIDITY = "high_liquidity"  # Высокая ликвидность
    TARGET_OPPORTUNITY = "target_opportunity"  # Возможность создания таргета
    QUICK_FLIP = "quick_flip"  # Быстрая перепродажа
    VALUE_INVESTMENT = "value_investment"  # Долгосрочная инвестиция


@dataclass
class MarketOpportunity:
    """Представляет возможность на рынке."""

    item_id: str
    title: str
    current_price: float
    suggested_price: float
    profit_potential: float
    profit_percent: float
    opportunity_type: MarketOpportunityType
    confidence_score: float  # 0-100
    liquidity_score: float  # 0-100
    risk_level: str  # low, medium, high

    # Дополнительная информация
    best_offer_price: float | None = None
    best_order_price: float | None = None
    offers_count: int = 0
    orders_count: int = 0

    # Метаданные
    game: str = "csgo"
    category: str | None = None
    rarity: str | None = None
    exterior: str | None = None
    image_url: str | None = None

    # Рекомендации
    recommended_action: str | None = None
    estimated_time_to_sell: str | None = None
    notes: list[str] | None = None


class SmartMarketFinder:
    """Умный поисковик выгодных предметов на DMarket."""

    def __init__(self, api_client: DMarketAPI) -> None:
        """Инициализация поисковика.

        Args:
            api_client: Экземпляр DMarketAPI для работы с API
        """
        self.api = api_client
        self._cache = {}
        self._cache_ttl = 300  # 5 минут

        # Настройки анализа
        self.min_profit_percent = 5.0  # Минимальный процент прибыли
        self.min_confidence = 60.0  # Минимальная уверенность
        self.max_price = 100.0  # Максимальная цена для анализа

        logger.info("SmartMarketFinder инициализирован")

    async def find_best_opportunities(
        self,
        game: str = "csgo",
        min_price: float = 0.5,
        max_price: float = 100.0,
        limit: int = 50,
        opportunity_types: list[MarketOpportunityType] | None = None,
        min_confidence: float = 60.0,
    ) -> list[MarketOpportunity]:
        """Найти лучшие возможности на рынке.

        Args:
            game: Код игры (csgo, dota2, rust, tf2)
            min_price: Минимальная цена предмета в USD
            max_price: Максимальная цена предмета в USD
            limit: Максимальное количество результатов
            opportunity_types: Типы возможностей для поиска (None = все)
            min_confidence: Минимальная уверенность (0-100)

        Returns:
            Список найденных возможностей, отсортированный по убыванию confidence_score
        """
        logger.info(
            f"Поиск возможностей для {game}: "
            f"цена ${min_price:.2f}-${max_price:.2f}, "
            f"мин. уверенность {min_confidence}%"
        )

        # Конвертируем коды игр
        game_ids = {
            "csgo": "a8db",
            "dota2": "9a92",
            "tf2": "tf2",
            "rust": "rust",
        }
        game_id = game_ids.get(game, game)

        try:
            # Получаем предметы с маркета с агрегированной информацией
            market_items = await self._get_market_items_with_aggregated_prices(
                game=game_id,
                min_price=min_price,
                max_price=max_price,
                limit=limit * 2,  # Берем больше для фильтрации
            )

            if not market_items:
                logger.warning(f"Не найдено предметов для {game}")
                return []

            # Анализируем каждый предмет
            opportunities = []
            for item in market_items:
                opportunity = await self._analyze_item_opportunity(item, game)

                if opportunity is None:
                    continue

                # Фильтруем по уверенности
                if opportunity.confidence_score < min_confidence:
                    continue

                # Фильтруем по типам возможностей
                if opportunity_types and opportunity.opportunity_type not in opportunity_types:
                    continue

                opportunities.append(opportunity)

            # Сортируем по уверенности и потенциальной прибыли
            opportunities.sort(
                key=lambda x: (x.confidence_score, x.profit_percent),
                reverse=True,
            )

            logger.info(f"Найдено {len(opportunities)} возможностей")
            return opportunities[:limit]

        except Exception as e:
            logger.exception(f"Ошибка при поиске возможностей: {e}")
            return []

    async def find_underpriced_items(
        self,
        game: str = "csgo",
        min_price: float = 1.0,
        max_price: float = 50.0,
        min_discount_percent: float = 10.0,
        limit: int = 20,
    ) -> list[MarketOpportunity]:
        """Найти предметы с заниженной ценой.

        Args:
            game: Код игры
            min_price: Минимальная цена
            max_price: Максимальная цена
            min_discount_percent: Минимальный процент скидки относительно suggestedPrice
            limit: Лимит результатов

        Returns:
            Список предметов с заниженной ценой
        """
        logger.info(
            f"Поиск предметов с заниженной ценой для {game} (мин. скидка {min_discount_percent}%)"
        )

        game_ids = {"csgo": "a8db", "dota2": "9a92", "tf2": "tf2", "rust": "rust"}
        game_id = game_ids.get(game, game)

        try:
            # Получаем предметы, отсортированные по лучшей сделке
            response = await self.api._request(
                method="GET",
                path="/exchange/v1/market/items",
                params={
                    "gameId": game_id,
                    "currency": "USD",
                    "priceFrom": int(min_price * 100),
                    "priceTo": int(max_price * 100),
                    "limit": limit * 3,
                    "orderBy": "best_deal",
                    "orderDir": "desc",
                },
            )

            if not response or "objects" not in response:
                return []

            underpriced = []
            for item in response["objects"]:
                # Проверяем наличие suggestedPrice
                if "suggestedPrice" not in item or "price" not in item:
                    continue

                current_price = float(item["price"]["USD"]) / 100
                suggested_price = float(item["suggestedPrice"]["USD"]) / 100

                # Рассчитываем скидку
                discount_percent = (suggested_price - current_price) / suggested_price * 100

                if discount_percent >= min_discount_percent:
                    # Рассчитываем потенциальную прибыль с учетом комиссии
                    fee = 0.07  # 7% комиссия DMarket
                    profit = suggested_price * (1 - fee) - current_price
                    profit_percent = (profit / current_price) * 100

                    # Определяем уровень риска
                    risk_level = "medium"
                    if discount_percent > 30:
                        risk_level = "high"  # Слишком большая скидка может быть подозрительной
                    elif discount_percent < 15:
                        risk_level = "low"

                    # Рассчитываем confidence score
                    confidence = min(100, 50 + discount_percent * 1.5)

                    opportunity = MarketOpportunity(
                        item_id=item.get("itemId", ""),
                        title=item.get("title", ""),
                        current_price=current_price,
                        suggested_price=suggested_price,
                        profit_potential=profit,
                        profit_percent=profit_percent,
                        opportunity_type=MarketOpportunityType.UNDERPRICED,
                        confidence_score=confidence,
                        liquidity_score=self._calculate_liquidity_score(item),
                        risk_level=risk_level,
                        game=game,
                        category=item.get("extra", {}).get("category"),
                        rarity=item.get("extra", {}).get("rarity"),
                        exterior=item.get("extra", {}).get("exterior"),
                        image_url=item.get("imageUrl"),
                        recommended_action=f"Купить по ${current_price:.2f}, продать по ${suggested_price:.2f}",
                        notes=[
                            f"Скидка {discount_percent:.1f}% от рекомендованной цены",
                            f"Потенциальная прибыль: ${profit:.2f} ({profit_percent:.1f}%)",
                        ],
                    )

                    underpriced.append(opportunity)

            # Сортируем по проценту скидки
            underpriced.sort(key=lambda x: x.profit_percent, reverse=True)

            logger.info(f"Найдено {len(underpriced)} предметов с заниженной ценой")
            return underpriced[:limit]

        except Exception as e:
            logger.exception(f"Ошибка при поиске предметов с заниженной ценой: {e}")
            return []

    async def find_target_opportunities(
        self,
        game: str = "csgo",
        min_price: float = 1.0,
        max_price: float = 50.0,
        min_spread_percent: float = 5.0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Найти возможности для создания выгодных таргетов.

        Анализирует спред между лучшим предложением на покупку (order)
        и лучшим предложением на продажу (offer), чтобы найти предметы,
        где можно создать таргет и быстро перепродать с прибылью.

        Args:
            game: Код игры
            min_price: Минимальная цена
            max_price: Максимальная цена
            min_spread_percent: Минимальный процент спреда
            limit: Лимит результатов

        Returns:
            Список возможностей для создания таргетов
        """
        logger.info(f"Поиск возможностей для таргетов {game} (мин. спред {min_spread_percent}%)")

        game_ids = {"csgo": "a8db", "dota2": "9a92", "tf2": "tf2", "rust": "rust"}
        game_id = game_ids.get(game, game)

        try:
            # Получаем предметы с рынка
            market_response = await self.api._request(
                method="GET",
                path="/exchange/v1/market/items",
                params={
                    "gameId": game_id,
                    "currency": "USD",
                    "priceFrom": int(min_price * 100),
                    "priceTo": int(max_price * 100),
                    "limit": 100,
                },
            )

            if not market_response or "objects" not in market_response:
                return []

            # Собираем названия предметов для запроса агрегированных цен
            titles = [item.get("title") for item in market_response["objects"] if item.get("title")]

            if not titles:
                return []

            # Получаем агрегированные цены
            aggregated_response = await self.api._request(
                method="POST",
                path="/marketplace-api/v1/aggregated-prices",
                data={
                    "filter": {
                        "game": game,
                        "titles": titles[:100],  # Ограничиваем размер запроса
                    },
                    "limit": "100",
                },
            )

            if not aggregated_response or "aggregatedPrices" not in aggregated_response:
                return []

            opportunities = []
            for agg_data in aggregated_response["aggregatedPrices"]:
                # Проверяем наличие данных о ценах
                if not agg_data.get("orderBestPrice") or not agg_data.get("offerBestPrice"):
                    continue

                order_price = float(agg_data["orderBestPrice"]) / 100  # Цена таргета
                offer_price = float(agg_data["offerBestPrice"]) / 100  # Цена офера

                # Рассчитываем спред
                spread = offer_price - order_price
                spread_percent = (spread / order_price) * 100

                # Фильтруем по минимальному спреду
                if spread_percent < min_spread_percent:
                    continue

                # Рассчитываем потенциальную прибыль с учетом комиссии
                fee = 0.07  # 7% комиссия
                target_price = order_price * 1.01  # Ставим на 1% выше лучшего таргета
                sell_price = offer_price * 0.99  # Продаем на 1% ниже лучшего офера

                profit = sell_price * (1 - fee) - target_price
                profit_percent = (profit / target_price) * 100

                # Проверяем прибыльность
                if profit <= 0:
                    continue

                # Оцениваем ликвидность на основе количества заявок
                order_count = agg_data.get("orderCount", 0)
                offer_count = agg_data.get("offerCount", 0)
                liquidity_score = min(100, (order_count + offer_count) * 2)

                # Определяем уровень риска
                risk_level = (
                    "low" if spread_percent < 15 else "medium" if spread_percent < 30 else "high"
                )

                # Confidence на основе спреда и ликвидности
                confidence = min(100, spread_percent * 2 + liquidity_score * 0.3)

                opportunities.append({
                    "title": agg_data.get("title"),
                    "order_best_price": order_price,
                    "offer_best_price": offer_price,
                    "spread": spread,
                    "spread_percent": spread_percent,
                    "recommended_target_price": target_price,
                    "recommended_sell_price": sell_price,
                    "profit_potential": profit,
                    "profit_percent": profit_percent,
                    "order_count": order_count,
                    "offer_count": offer_count,
                    "liquidity_score": liquidity_score,
                    "confidence_score": confidence,
                    "risk_level": risk_level,
                    "game": game,
                    "recommended_action": (
                        f"Создать таргет по ${target_price:.2f}, продать по ${sell_price:.2f}"
                    ),
                    "notes": [
                        f"Спред между лучшим таргетом и офером: {spread_percent:.1f}%",
                        f"Заявок на покупку: {order_count}, на продажу: {offer_count}",
                        f"Потенциальная прибыль: ${profit:.2f} ({profit_percent:.1f}%)",
                    ],
                })

            # Сортируем по прибыльности и уверенности
            opportunities.sort(
                key=operator.itemgetter("confidence_score", "profit_percent"),
                reverse=True,
            )

            logger.info(f"Найдено {len(opportunities)} возможностей для таргетов")
            return opportunities[:limit]

        except Exception as e:
            logger.exception(f"Ошибка при поиске возможностей для таргетов: {e}")
            return []

    async def find_quick_flip_opportunities(
        self,
        game: str = "csgo",
        min_price: float = 1.0,
        max_price: float = 20.0,
        min_profit_percent: float = 10.0,
        max_risk: str = "medium",
        limit: int = 15,
    ) -> list[MarketOpportunity]:
        """Найти возможности для быстрой перепродажи.

        Ищет предметы с высокой ликвидностью и хорошим спредом,
        которые можно быстро купить и продать.

        Args:
            game: Код игры
            min_price: Минимальная цена
            max_price: Максимальная цена
            min_profit_percent: Минимальный процент прибыли
            max_risk: Максимальный уровень риска (low, medium, high)
            limit: Лимит результатов

        Returns:
            Список возможностей для быстрой перепродажи
        """
        logger.info(f"Поиск возможностей для быстрой перепродажи {game}")

        # Ищем предметы с заниженной ценой и высокой ликвидностью
        underpriced = await self.find_underpriced_items(
            game=game,
            min_price=min_price,
            max_price=max_price,
            min_discount_percent=min_profit_percent,
            limit=limit * 2,
        )

        # Фильтруем по ликвидности и риску
        risk_levels = {"low": 1, "medium": 2, "high": 3}
        max_risk_level = risk_levels.get(max_risk, 2)

        quick_flips = []
        for opp in underpriced:
            # Фильтруем по ликвидности (минимум 50)
            if opp.liquidity_score < 50:
                continue

            # Фильтруем по риску
            if risk_levels.get(opp.risk_level, 2) > max_risk_level:
                continue

            # Обновляем тип возможности
            opp.opportunity_type = MarketOpportunityType.QUICK_FLIP
            opp.estimated_time_to_sell = "< 24 часа" if opp.liquidity_score > 70 else "1-3 дня"

            quick_flips.append(opp)

        # Сортируем по ликвидности и прибыли
        quick_flips.sort(
            key=lambda x: (x.liquidity_score, x.profit_percent),
            reverse=True,
        )

        logger.info(f"Найдено {len(quick_flips)} возможностей для быстрой перепродажи")
        return quick_flips[:limit]

    async def _get_market_items_with_aggregated_prices(
        self,
        game: str,
        min_price: float,
        max_price: float,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Получить предметы с маркета вместе с агрегированными ценами."""
        try:
            # Получаем предметы с маркета
            market_response = await self.api._request(
                method="GET",
                path="/exchange/v1/market/items",
                params={
                    "gameId": game,
                    "currency": "USD",
                    "priceFrom": int(min_price * 100),
                    "priceTo": int(max_price * 100),
                    "limit": limit,
                },
            )

            if not market_response or "objects" not in market_response:
                return []

            items = market_response["objects"]

            # Получаем агрегированные цены для предметов
            titles = [item.get("title") for item in items if item.get("title")]

            if not titles:
                return items

            try:
                aggregated_response = await self.api._request(
                    method="POST",
                    path="/marketplace-api/v1/aggregated-prices",
                    data={
                        "filter": {
                            "game": game.replace("a8db", "csgo").replace("9a92", "dota2"),
                            "titles": titles,
                        },
                        "limit": str(limit),
                    },
                )

                if aggregated_response and "aggregatedPrices" in aggregated_response:
                    # Добавляем агрегированные данные к предметам
                    agg_dict = {
                        agg["title"]: agg for agg in aggregated_response["aggregatedPrices"]
                    }

                    for item in items:
                        title = item.get("title")
                        if title in agg_dict:
                            item["aggregated"] = agg_dict[title]
            except Exception as e:
                logger.warning(f"Не удалось получить агрегированные цены: {e}")

            return items

        except Exception as e:
            logger.exception(f"Ошибка при получении предметов с маркета: {e}")
            return []

    async def _analyze_item_opportunity(
        self,
        item: dict[str, Any],
        game: str,
    ) -> MarketOpportunity | None:
        """Проанализировать предмет на предмет возможности."""
        try:
            # Извлекаем базовую информацию
            item_id = item.get("itemId", "")
            title = item.get("title", "")

            if not title:
                return None

            # Извлекаем цены
            price_data = item.get("price", {})
            current_price = float(price_data.get("USD", 0)) / 100

            suggested_data = item.get("suggestedPrice", {})
            suggested_price = float(suggested_data.get("USD", 0)) / 100

            if current_price <= 0:
                return None

            # Если нет suggested price, используем текущую цену + 10%
            if suggested_price <= 0:
                suggested_price = current_price * 1.1

            # Рассчитываем потенциальную прибыль
            fee = 0.07  # 7% комиссия
            profit = suggested_price * (1 - fee) - current_price
            profit_percent = (profit / current_price) * 100

            # Определяем тип возможности
            opportunity_type = self._determine_opportunity_type(
                item,
                profit_percent,
            )

            # Рассчитываем уверенность
            confidence = self._calculate_confidence_score(item, profit_percent)

            # Рассчитываем ликвидность
            liquidity = self._calculate_liquidity_score(item)

            # Определяем риск
            risk_level = self._determine_risk_level(
                profit_percent,
                liquidity,
                confidence,
            )

            # Извлекаем агрегированные данные, если доступны
            aggregated = item.get("aggregated", {})
            best_offer = None
            best_order = None
            offers_count = 0
            orders_count = 0

            if aggregated:
                best_offer = float(aggregated.get("offerBestPrice", 0)) / 100
                best_order = float(aggregated.get("orderBestPrice", 0)) / 100
                offers_count = aggregated.get("offerCount", 0)
                orders_count = aggregated.get("orderCount", 0)

            # Формируем рекомендацию
            action = self._generate_recommendation(
                opportunity_type,
                current_price,
                suggested_price,
                best_order,
            )

            # Оцениваем время продажи
            time_to_sell = self._estimate_time_to_sell(liquidity)

            # Формируем заметки
            notes = self._generate_notes(
                item,
                profit,
                profit_percent,
                liquidity,
            )

            # Создаем объект возможности
            return MarketOpportunity(
                item_id=item_id,
                title=title,
                current_price=current_price,
                suggested_price=suggested_price,
                profit_potential=profit,
                profit_percent=profit_percent,
                opportunity_type=opportunity_type,
                confidence_score=confidence,
                liquidity_score=liquidity,
                risk_level=risk_level,
                best_offer_price=best_offer,
                best_order_price=best_order,
                offers_count=offers_count,
                orders_count=orders_count,
                game=game,
                category=item.get("extra", {}).get("category"),
                rarity=item.get("extra", {}).get("rarity"),
                exterior=item.get("extra", {}).get("exterior"),
                image_url=item.get("imageUrl"),
                recommended_action=action,
                estimated_time_to_sell=time_to_sell,
                notes=notes,
            )

        except Exception as e:
            logger.warning(f"Ошибка при анализе предмета: {e}")
            return None

    def _determine_opportunity_type(
        self,
        item: dict[str, Any],
        profit_percent: float,
    ) -> MarketOpportunityType:
        """Определить тип возможности."""
        # Проверяем популярность
        popularity = item.get("extra", {}).get("popularity", 0)

        if profit_percent > 15:
            return MarketOpportunityType.UNDERPRICED

        if popularity > 0.7:
            return MarketOpportunityType.HIGH_LIQUIDITY

        if profit_percent > 10:
            return MarketOpportunityType.QUICK_FLIP

        if profit_percent > 5:
            return MarketOpportunityType.VALUE_INVESTMENT

        return MarketOpportunityType.TARGET_OPPORTUNITY

    def _calculate_confidence_score(
        self,
        item: dict[str, Any],
        profit_percent: float,
    ) -> float:
        """Рассчитать уверенность в возможности."""
        score = 50.0  # Базовая уверенность

        # Увеличиваем за прибыль
        score += min(30, profit_percent * 1.5)

        # Увеличиваем за популярность
        popularity = item.get("extra", {}).get("popularity", 0)
        score += popularity * 15

        # Увеличиваем если есть suggested price
        if "suggestedPrice" in item:
            score += 5

        return min(100, score)

    def _calculate_liquidity_score(self, item: dict[str, Any]) -> float:
        """Рассчитать показатель ликвидности."""
        score = 30.0  # Базовая ликвидность

        # Учитываем популярность
        popularity = item.get("extra", {}).get("popularity", 0)
        score += popularity * 40

        # Учитываем количество предложений из aggregated данных
        aggregated = item.get("aggregated", {})
        if aggregated:
            offers = aggregated.get("offerCount", 0)
            orders = aggregated.get("orderCount", 0)
            score += min(30, (offers + orders) * 0.5)

        return min(100, score)

    def _determine_risk_level(
        self,
        profit_percent: float,
        liquidity: float,
        confidence: float,
    ) -> str:
        """Определить уровень риска."""
        # Низкий риск: высокая ликвидность и умеренная прибыль
        if liquidity > 70 and 5 <= profit_percent <= 20 and confidence > 70:
            return "low"

        # Высокий риск: низкая ликвидность или очень высокая прибыль
        if liquidity < 40 or profit_percent > 30 or confidence < 50:
            return "high"

        return "medium"

    def _generate_recommendation(
        self,
        opportunity_type: MarketOpportunityType,
        current_price: float,
        suggested_price: float,
        best_order: float | None,
    ) -> str:
        """Сгенерировать рекомендацию по действию."""
        if opportunity_type == MarketOpportunityType.TARGET_OPPORTUNITY and best_order:
            target_price = best_order * 1.01
            return f"Создать таргет по ${target_price:.2f}, продать по ${suggested_price:.2f}"

        if opportunity_type == MarketOpportunityType.QUICK_FLIP:
            return f"Быстро купить по ${current_price:.2f}, продать по ${suggested_price:.2f}"

        return f"Купить по ${current_price:.2f}, продать по ${suggested_price:.2f}"

    def _estimate_time_to_sell(self, liquidity: float) -> str:
        """Оценить время продажи."""
        if liquidity > 80:
            return "< 12 часов"
        if liquidity > 60:
            return "< 24 часа"
        if liquidity > 40:
            return "1-3 дня"
        if liquidity > 20:
            return "3-7 дней"
        return "> 7 дней"

    def _generate_notes(
        self,
        item: dict[str, Any],
        profit: float,
        profit_percent: float,
        liquidity: float,
    ) -> list[str]:
        """Сгенерировать заметки о возможности."""
        notes = []

        notes.append(f"Потенциальная прибыль: ${profit:.2f} ({profit_percent:.1f}%)")

        if liquidity > 70:
            notes.append("Высокая ликвидность - быстрая продажа")
        elif liquidity < 40:
            notes.append("Низкая ликвидность - может долго продаваться")

        rarity = item.get("extra", {}).get("rarity")
        if rarity:
            notes.append(f"Редкость: {rarity}")

        popularity = item.get("extra", {}).get("popularity", 0)
        if popularity > 0.7:
            notes.append("Популярный предмет - высокий спрос")

        return notes


# Вспомогательные функции для удобного использования


async def find_best_deals(
    api_client: DMarketAPI,
    game: str = "csgo",
    min_price: float = 0.5,
    max_price: float = 50.0,
    limit: int = 20,
) -> list[MarketOpportunity]:
    """Быстрый поиск лучших сделок.

    Args:
        api_client: Экземпляр DMarketAPI
        game: Код игры
        min_price: Минимальная цена
        max_price: Максимальная цена
        limit: Лимит результатов

    Returns:
        Список лучших возможностей
    """
    finder = SmartMarketFinder(api_client)
    return await finder.find_best_opportunities(
        game=game,
        min_price=min_price,
        max_price=max_price,
        limit=limit,
    )


async def find_quick_profits(
    api_client: DMarketAPI,
    game: str = "csgo",
    max_price: float = 20.0,
    limit: int = 10,
) -> list[MarketOpportunity]:
    """Быстрый поиск возможностей для быстрой прибыли.

    Args:
        api_client: Экземпляр DMarketAPI
        game: Код игры
        max_price: Максимальная цена
        limit: Лимит результатов

    Returns:
        Список возможностей для быстрой прибыли
    """
    finder = SmartMarketFinder(api_client)
    return await finder.find_quick_flip_opportunities(
        game=game,
        min_price=1.0,
        max_price=max_price,
        limit=limit,
    )
