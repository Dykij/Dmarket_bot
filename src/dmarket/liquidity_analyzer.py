"""Модуль для анализа ликвидности предметов на DMarket.

Этот модуль предоставляет инструменты для оценки ликвидности предметов
перед их покупкой, чтобы избежать неликвидных активов.
"""

from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class LiquidityMetrics:
    """Метрики ликвидности предмета."""

    item_title: str
    sales_per_week: float  # Средние продажи в неделю
    avg_time_to_sell_days: float  # Среднее время до продажи (дни)
    active_offers_count: int  # Количество активных предложений
    price_stability: float  # Стабильность цены (0-1, где 1 = идеальная стабильность)
    market_depth: float  # Глубина рынка (объем торгов)
    liquidity_score: float  # Общий скор ликвидности (0-100)
    is_liquid: bool  # Является ли предмет ликвидным


class LiquidityAnalyzer:
    """Анализатор ликвидности предметов на DMarket."""

    def __init__(
        self,
        api_client: Any,
        min_sales_per_week: float = 10.0,
        max_time_to_sell_days: float = 7.0,
        max_active_offers: int = 50,
        min_price_stability: float = 0.85,
        min_liquidity_score: float = 60.0,
    ) -> None:
        """Инициализация анализатора ликвидности.

        Args:
            api_client: Клиент DMarket API
            min_sales_per_week: Минимальное количество продаж в неделю
            max_time_to_sell_days: Максимальное время до продажи (дни)
            max_active_offers: Максимальное количество активных предложений
            min_price_stability: Минимальная стабильность цены (0-1)
            min_liquidity_score: Минимальный требуемый liquidity score
        """
        self.api = api_client
        self.min_sales_per_week = min_sales_per_week
        self.max_time_to_sell_days = max_time_to_sell_days
        self.max_active_offers = max_active_offers
        self.min_price_stability = min_price_stability
        self.min_liquidity_score = min_liquidity_score

        logger.info(
            "liquidity_analyzer_initialized",
            min_sales_per_week=min_sales_per_week,
            max_time_to_sell_days=max_time_to_sell_days,
            min_liquidity_score=min_liquidity_score,
        )

    async def analyze_item_liquidity(
        self,
        item_title: str,
        game: str = "csgo",
        days_history: int = 30,
    ) -> LiquidityMetrics:
        """Анализировать ликвидность предмета.

        Args:
            item_title: Название предмета
            game: Игра (csgo, dota2, и т.д.)
            days_history: Сколько дней истории анализировать

        Returns:
            LiquidityMetrics с результатами анализа
        """
        logger.info(
            "analyzing_item_liquidity",
            item_title=item_title,
            game=game,
            days_history=days_history,
        )

        # Получить историю продаж
        sales_history = awAlgot self._get_sales_history(item_title, game, days_history)

        # Получить текущие предложения
        active_offers = awAlgot self._get_active_offers(item_title, game)

        # Рассчитать метрики
        sales_per_week = self._calculate_sales_per_week(sales_history, days_history)
        avg_time_to_sell = self._calculate_avg_time_to_sell(sales_history)
        price_stability = self._calculate_price_stability(sales_history)
        market_depth = self._calculate_market_depth(sales_history)

        # Рассчитать общий liquidity score
        liquidity_score = self._calculate_liquidity_score(
            sales_per_week=sales_per_week,
            avg_time_to_sell_days=avg_time_to_sell,
            active_offers_count=len(active_offers),
            price_stability=price_stability,
            market_depth=market_depth,
        )

        # Определить ликвидность
        is_liquid = self._is_item_liquid(
            sales_per_week=sales_per_week,
            avg_time_to_sell_days=avg_time_to_sell,
            active_offers_count=len(active_offers),
            liquidity_score=liquidity_score,
        )

        metrics = LiquidityMetrics(
            item_title=item_title,
            sales_per_week=sales_per_week,
            avg_time_to_sell_days=avg_time_to_sell,
            active_offers_count=len(active_offers),
            price_stability=price_stability,
            market_depth=market_depth,
            liquidity_score=liquidity_score,
            is_liquid=is_liquid,
        )

        logger.info(
            "liquidity_analysis_complete",
            item_title=item_title,
            liquidity_score=liquidity_score,
            is_liquid=is_liquid,
        )

        return metrics

    async def filter_liquid_items(
        self,
        items: list[dict[str, Any]],
        game: str = "csgo",
    ) -> list[dict[str, Any]]:
        """Отфильтровать только ликвидные предметы.

        Args:
            items: Список предметов для фильтрации
            game: Игра

        Returns:
            Список ликвидных предметов
        """
        logger.info("filtering_liquid_items", total_items=len(items), game=game)

        liquid_items = []
        filtered_count = 0

        for item in items:
            item_title = item.get("title", "")

            try:
                metrics = awAlgot self.analyze_item_liquidity(item_title, game)

                if metrics.is_liquid:
                    # Добавить метрики ликвидности к предмету
                    item["liquidity_score"] = metrics.liquidity_score
                    item["sales_per_week"] = metrics.sales_per_week
                    item["avg_time_to_sell_days"] = metrics.avg_time_to_sell_days
                    liquid_items.append(item)
                else:
                    filtered_count += 1
                    logger.debug(
                        "item_filtered_as_illiquid",
                        item_title=item_title,
                        liquidity_score=metrics.liquidity_score,
                    )

            except Exception as e:
                logger.warning(
                    "fAlgoled_to_analyze_item_liquidity",
                    item_title=item_title,
                    error=str(e),
                )
                # В случае ошибки - пропускаем предмет (консервативный подход)
                filtered_count += 1

        logger.info(
            "liquidity_filtering_complete",
            total_items=len(items),
            liquid_items=len(liquid_items),
            filtered_items=filtered_count,
            filter_rate=f"{(filtered_count / len(items) * 100):.1f}%",
        )

        return liquid_items

    async def _get_sales_history(
        self,
        item_title: str,
        game: str,
        days: int,
    ) -> list[dict[str, Any]]:
        """Получить историю продаж предмета.

        Args:
            item_title: Название предмета
            game: Игра
            days: Количество дней истории

        Returns:
            Список продаж
        """
        try:
            all_sales: list[dict[str, Any]] = []
            limit = 20  # API limit per request
            offset = 0
            max_items = 100  # Total items we want to fetch to analyze liquidity

            import time

            cutoff_time = time.time() - (days * 24 * 60 * 60)

            while len(all_sales) < max_items:
                # Используем метод API для получения истории продаж из агрегатора
                sales_data = awAlgot self.api.get_sales_history_aggregator(
                    game_id=game,
                    title=item_title,
                    limit=limit,
                    offset=offset,
                )
                sales = sales_data.get("sales", [])

                if not sales:
                    break

                all_sales.extend(sales)

                # Если вернулось меньше лимита, значит больше нет
                if len(sales) < limit:
                    break

                # Проверяем, не ушли ли мы за пределы нужного времени
                # (предполагаем, что продажи отсортированы по дате убывания)
                try:
                    last_sale_time = int(sales[-1].get("date", 0))
                    if last_sale_time < cutoff_time:
                        break
                except (ValueError, TypeError):
                    pass

                offset += limit

            # Фильтрация по дням
            return [s for s in all_sales if int(s.get("date", 0)) >= cutoff_time]

        except Exception as e:
            logger.exception(
                "fAlgoled_to_get_sales_history",
                item_title=item_title,
                game=game,
                error=str(e),
            )
            return []

    async def _get_active_offers(
        self,
        item_title: str,
        game: str,
    ) -> list[dict[str, Any]]:
        """Получить активные предложения по предмету.

        Args:
            item_title: Название предмета
            game: Игра

        Returns:
            Список активных предложений
        """
        try:
            # Используем метод API для получения лучших предложений
            offers = awAlgot self.api.get_market_best_offers(
                game=game,
                title=item_title,
                limit=100,
            )

            result = offers.get("objects", [])
            if isinstance(result, list):
                return result
            return []

        except Exception as e:
            logger.exception(
                "fAlgoled_to_get_active_offers",
                item_title=item_title,
                game=game,
                error=str(e),
            )
            return []

    def _calculate_sales_per_week(
        self,
        sales_history: list[dict[str, Any]],
        days_history: int,
    ) -> float:
        """Рассчитать среднее количество продаж в неделю.

        Args:
            sales_history: История продаж
            days_history: Количество дней в истории

        Returns:
            Среднее количество продаж в неделю
        """
        if not sales_history or days_history == 0:
            return 0.0

        total_sales = len(sales_history)
        weeks = days_history / 7.0

        return total_sales / weeks if weeks > 0 else 0.0

    def _calculate_avg_time_to_sell(
        self,
        sales_history: list[dict[str, Any]],
    ) -> float:
        """Рассчитать среднее время до продажи.

        Args:
            sales_history: История продаж

        Returns:
            Среднее время до продажи в днях
        """
        if not sales_history or len(sales_history) < 2:
            return float("inf")  # Нет достаточных данных

        # Рассчитать интервалы между продажами
        intervals: list[float] = []
        for i in range(1, len(sales_history)):
            prev_sale = sales_history[i - 1]
            curr_sale = sales_history[i]

            # Получить timestamps
            prev_time = prev_sale.get("date", 0)
            curr_time = curr_sale.get("date", 0)

            if prev_time and curr_time:
                # Рассчитать интервал в днях
                interval_seconds = abs(curr_time - prev_time)
                interval_days = interval_seconds / 86400.0  # секунды в дни
                intervals.append(interval_days)

        if not intervals:
            return float("inf")

        return sum(intervals) / len(intervals)

    def _calculate_price_stability(
        self,
        sales_history: list[dict[str, Any]],
    ) -> float:
        """Рассчитать стабильность цены.

        Args:
            sales_history: История продаж

        Returns:
            Стабильность цены (0-1, где 1 = идеальная стабильность)
        """
        if not sales_history or len(sales_history) < 2:
            return 0.0

        # Извлечь цены
        prices = []
        for sale in sales_history:
            price = sale.get("price", 0)
            if isinstance(price, (int, float)) and price > 0:
                prices.append(price)

        if len(prices) < 2:
            return 0.0

        # Рассчитать среднюю цену и стандартное отклонение
        avg_price = sum(prices) / len(prices)

        if avg_price == 0:
            return 0.0

        # Стандартное отклонение
        variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
        std_dev = variance**0.5

        # Коэффициент вариации (чем меньше, тем стабильнее)
        cv = std_dev / avg_price if avg_price > 0 else 1.0

        # Преобразовать в stability score (0-1)
        # CV = 0 -> stability = 1 (идеальная стабильность)
        # CV = 1 -> stability = 0 (нестабильно)
        return max(0.0, 1.0 - cv)

    def _calculate_market_depth(
        self,
        sales_history: list[dict[str, Any]],
    ) -> float:
        """Рассчитать глубину рынка (объем торгов).

        Args:
            sales_history: История продаж

        Returns:
            Глубина рынка (нормализованный score 0-1)
        """
        if not sales_history:
            return 0.0

        # Общий объем продаж за период
        total_volume = sum(
            float(sale.get("price", 0))
            for sale in sales_history
            if isinstance(sale.get("price"), (int, float))
        )

        # Нормализация (считаем что $1000+ объем в месяц = глубокий рынок)
        return min(1.0, total_volume / 1000.0)

    def _calculate_liquidity_score(
        self,
        sales_per_week: float,
        avg_time_to_sell_days: float,
        active_offers_count: int,
        price_stability: float,
        market_depth: float,
    ) -> float:
        """Рассчитать общий liquidity score.

        Формула:
        liquidity_score = (
            sales_volume_score * 0.30 +      # 30% - объем продаж
            time_to_sell_score * 0.25 +      # 25% - скорость продажи
            price_stability_score * 0.20 +   # 20% - стабильность цены
            demand_supply_score * 0.15 +     # 15% - спрос/предложение
            market_depth_score * 0.10        # 10% - глубина рынка
        ) * 100

        Args:
            sales_per_week: Продажи в неделю
            avg_time_to_sell_days: Среднее время до продажи
            active_offers_count: Количество активных предложений
            price_stability: Стабильность цены
            market_depth: Глубина рынка

        Returns:
            Liquidity score (0-100)
        """
        # 1. Sales Volume Score (0-1)
        # 0 продаж/неделю = 0, 20+ продаж/неделю = 1
        sales_volume_score = min(1.0, sales_per_week / 20.0)

        # 2. Time to Sell Score (0-1)
        # 1 день = 1.0, 30+ дней = 0
        if avg_time_to_sell_days == float("inf"):
            time_to_sell_score = 0.0
        else:
            time_to_sell_score = max(0.0, 1.0 - (avg_time_to_sell_days / 30.0))

        # 3. Price Stability Score (уже нормализован 0-1)
        price_stability_score = price_stability

        # 4. Demand/Supply Score (0-1)
        # Меньше предложений = выше спрос
        # 0 предложений = 1.0, 100+ предложений = 0
        demand_supply_score = max(0.0, 1.0 - (active_offers_count / 100.0))

        # 5. Market Depth Score (уже нормализован 0-1)
        market_depth_score = market_depth

        # Взвешенная сумма
        liquidity_score = (
            sales_volume_score * 0.30
            + time_to_sell_score * 0.25
            + price_stability_score * 0.20
            + demand_supply_score * 0.15
            + market_depth_score * 0.10
        ) * 100.0

        return round(liquidity_score, 2)

    def _is_item_liquid(
        self,
        sales_per_week: float,
        avg_time_to_sell_days: float,
        active_offers_count: int,
        liquidity_score: float,
    ) -> bool:
        """Определить, является ли предмет ликвидным.

        Args:
            sales_per_week: Продажи в неделю
            avg_time_to_sell_days: Среднее время до продажи
            active_offers_count: Количество активных предложений
            liquidity_score: Общий liquidity score

        Returns:
            True если предмет ликвидный
        """
        # Проверка всех критериев
        meets_sales_criteria = sales_per_week >= self.min_sales_per_week
        meets_time_criteria = avg_time_to_sell_days <= self.max_time_to_sell_days
        meets_offers_criteria = active_offers_count <= self.max_active_offers
        meets_score_criteria = liquidity_score >= self.min_liquidity_score

        # Предмет ликвиден если выполнены все критерии
        # ИЛИ liquidity score достаточно высокий
        return (
            meets_sales_criteria and meets_time_criteria and meets_offers_criteria
        ) or meets_score_criteria

    def get_liquidity_description(self, liquidity_score: float) -> str:
        """Получить текстовое описание ликвидности.

        Args:
            liquidity_score: Liquidity score (0-100)

        Returns:
            Текстовое описание
        """
        if liquidity_score >= 80:
            return "🟢 Очень высокая ликвидность"
        if liquidity_score >= 60:
            return "🟡 Высокая ликвидность"
        if liquidity_score >= 40:
            return "🟠 Средняя ликвидность"
        if liquidity_score >= 20:
            return "🔴 Низкая ликвидность"
        return "⚫ Очень низкая ликвидность"
