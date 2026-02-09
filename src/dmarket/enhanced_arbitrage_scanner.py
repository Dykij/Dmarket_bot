"""Enhanced Arbitrage Scanner с продвинутыми фильтрами и оптимизациями.

Этот модуль реализует все рекомендации по улучшению арбитража:
1. orderBy: best_discount для приоритизации лучших скидок
2. Sales History проверка для фильтрации неликвидных предметов
3. External price comparison (Steam, CSGOFloat)
4. Realistic profit thresholds (15-20% вместо 30%+)
5. Advanced liquidity scoring
"""

import logging
from typing import Any

from src.dmarket.dmarket_api import DMarketAPI
from src.dmarket.external_price_api import get_external_price_api
from src.dmarket.liquidity_analyzer import LiquidityAnalyzer
from src.dmarket.sales_history import SalesHistoryAnalyzer
from src.interfaces import IDMarketAPI

logger = logging.getLogger(__name__)


class EnhancedArbitrageScanner:
    """Продвинутый сканер арбитража с улучшенными фильтрами."""

    def __init__(
        self,
        api_client: IDMarketAPI | None = None,
        min_discount: float = 15.0,  # Реалистичный порог 15%
        enable_external_comparison: bool = True,
        enable_sales_history: bool = True,
    ) -> None:
        """Инициализация сканера.

        Args:
            api_client: DMarket API клиент
            min_discount: Минимальный процент скидки (default: 15%)
            enable_external_comparison: Включить сравнение с внешними ценами
            enable_sales_history: Включить проверку истории продаж
        """
        self.api_client = api_client or DMarketAPI()
        self.min_discount = min_discount
        self.enable_external_comparison = enable_external_comparison
        self.enable_sales_history = enable_sales_history

        # Инициализируем вспомогательные компоненты
        self.liquidity_analyzer = LiquidityAnalyzer(self.api_client)
        self.sales_analyzer = (
            SalesHistoryAnalyzer(self.api_client) if enable_sales_history else None
        )
        self.external_api = get_external_price_api() if enable_external_comparison else None

    async def find_opportunities(
        self,
        game_id: str = "a8db",
        min_price: float = 1.0,
        max_price: float = 50.0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Найти арбитражные возможности с продвинутыми фильтрами.

        Args:
            game_id: ID игры (a8db=CS2, 9a92=Dota2, rust=Rust)
            min_price: Минимальная цена в USD
            max_price: Максимальная цена в USD
            limit: Максимальное количество результатов

        Returns:
            Список арбитражных возможностей с детальной информацией
        """
        logger.info(
            f"🔍 Запуск Enhanced Arbitrage Scanner: "
            f"game={game_id}, price=${min_price}-${max_price}, "
            f"min_discount={self.min_discount}%"
        )

        try:
            # Шаг 1: Получаем предметы с DMarket с orderBy=best_discount
            items = await self._fetch_items_by_discount(
                game_id=game_id,
                min_price=min_price,
                max_price=max_price,
                limit=limit * 2,  # Берем больше для фильтрации
            )

            if not items:
                logger.info("❌ Не найдено предметов для анализа")
                return []

            logger.info(f"📦 Получено {len(items)} предметов для анализа")

            # Шаг 2: Базовая фильтрация
            filtered_items = self._apply_basic_filters(items)
            logger.info(f"✅ После базовой фильтрации: {len(filtered_items)} предметов")

            # Шаг 3: Проверка ликвидности через историю продаж
            if self.enable_sales_history and self.sales_analyzer:
                filtered_items = await self._filter_by_sales_history(filtered_items)
                logger.info(f"✅ После проверки истории продаж: {len(filtered_items)} предметов")

            # Шаг 4: Сравнение с внешними ценами
            if self.enable_external_comparison and self.external_api:
                game_str = self._game_id_to_string(game_id)
                filtered_items = await self.external_api.batch_compare_prices(
                    filtered_items,
                    game=game_str,
                )
                logger.info("✅ Добавлена информация о внешних ценах")

            # Шаг 5: Финальный рейтинг и сортировка
            opportunities = self._rank_opportunities(filtered_items)

            logger.info(f"🎯 Найдено {len(opportunities)} арбитражных возможностей")

            return opportunities[:limit]

        except Exception as e:
            logger.exception(f"Ошибка в Enhanced Arbitrage Scanner: {e}")
            return []

    async def _fetch_items_by_discount(
        self,
        game_id: str,
        min_price: float,
        max_price: float,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Получить предметы отсортированные по best_discount.

        Это критически важный параметр для арбитража!
        """
        try:
            # Конвертируем цены в центы
            price_from = int(min_price * 100)
            price_to = int(max_price * 100)

            # Запрос к API с orderBy=best_discount
            response = await self.api_client.get_market_items(
                game_id=game_id,
                limit=limit,
                price_from=price_from,
                price_to=price_to,
                # КРИТИЧЕСКИ ВАЖНО: сортировка по скидке
                order_by="best_discount",
                order_dir="desc",
            )

            if not response or "objects" not in response:
                return []

            items = response["objects"]

            # Нормализуем формат цен
            for item in items:
                if "price" in item and isinstance(item["price"], dict):
                    item["price_usd"] = float(item["price"].get("USD", 0)) / 100

                if "suggestedPrice" in item and isinstance(item["suggestedPrice"], dict):
                    item["suggested_usd"] = float(item["suggestedPrice"].get("USD", 0)) / 100

            return items

        except Exception as e:
            logger.exception(f"Ошибка при получении предметов: {e}")
            return []

    def _apply_basic_filters(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Применить базовые фильтры ликвидности.

        Исключаем:
        - Souvenir предметы (манипулированные цены)
        - Stickers (низкая ликвидность)
        - Cases/Capsules (не подходят для арбитража)
        - Предметы без suggestedPrice
        """
        filtered = []

        for item in items:
            title = item.get("title", "").lower()
            price_usd = item.get("price_usd", 0)
            suggested_usd = item.get("suggested_usd", 0)

            # Фильтр 1: Проверяем наличие цен
            if price_usd <= 0 or suggested_usd <= 0:
                continue

            # Фильтр 2: Рассчитываем скидку
            discount = ((suggested_usd - price_usd) / suggested_usd) * 100
            item["discount_percent"] = round(discount, 2)

            if discount < self.min_discount:
                continue

            # Фильтр 3: Черный список неликвидных категорий
            blacklisted_keywords = [
                "souvenir",
                "sticker",
                "package",
                "case key",
                "capsule",
                "pin",
                "music kit",
                "graffiti",
            ]

            if any(keyword in title for keyword in blacklisted_keywords):
                continue

            # Фильтр 4: Проверяем trade lock
            extra = item.get("extra", {})
            trade_lock = extra.get("tradeLockDuration", 0)

            # Пропускаем если trade lock > 7 дней (168 часов)
            if trade_lock and trade_lock > 168:
                continue

            filtered.append(item)

        return filtered

    async def _filter_by_sales_history(
        self,
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Фильтровать по истории продаж.

        Критически важно: исключаем предметы с падающей ценой!

        Логика:
        - Если цена падает (последние 5 продаж ниже текущей) - НЕ ПОКУПАТЬ
        - Если объем продаж < 5 за неделю - низкая ликвидность
        """
        if not self.sales_analyzer:
            return items

        filtered = []

        for item in items:
            item_id = item.get("itemId") or item.get("extra", {}).get("linkId")

            if not item_id:
                continue

            try:
                # Получаем историю продаж
                sales_data = await self.sales_analyzer.get_sales_history(item_id)

                if not sales_data or "sales" not in sales_data:
                    # Нет истории - пропускаем (может быть новый листинг)
                    continue

                sales = sales_data["sales"]

                if len(sales) < 5:
                    # Мало данных для анализа
                    continue

                # Анализируем последние 5 продаж
                recent_sales = sales[:5]
                prices = [float(sale.get("price", {}).get("USD", 0)) / 100 for sale in recent_sales]

                # Текущая цена
                current_price = item.get("price_usd", 0)

                # Средняя цена последних продаж
                avg_recent_price = sum(prices) / len(prices)

                # КРИТИЧЕСКАЯ ПРОВЕРКА: если текущая цена ниже средней - это НЕ скидка, а падение!
                if current_price < avg_recent_price * 0.9:  # -10% от средней
                    logger.debug(
                        f"❌ {item.get('title')}: падающая цена "
                        f"(текущая ${current_price} < средняя ${avg_recent_price:.2f})"
                    )
                    continue

                # Проверяем объем продаж (liquidity score)
                total_sales = len(sales)
                if total_sales < 5:
                    logger.debug(
                        f"❌ {item.get('title')}: низкая ликвидность ({total_sales} продаж)"
                    )
                    continue

                # Добавляем метаданные о продажах
                item["sales_volume"] = total_sales
                item["avg_recent_price"] = round(avg_recent_price, 2)

                filtered.append(item)

            except Exception as e:
                logger.warning(f"Ошибка при анализе истории продаж для {item.get('title')}: {e}")
                # В случае ошибки пропускаем предмет (safety first)
                continue

        return filtered

    def _rank_opportunities(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ранжировать возможности по качеству.

        Критерии:
        1. External arbitrage (если доступно) - наивысший приоритет
        2. Discount % от suggested price
        3. Sales volume (ликвидность)
        4. Price range (средние цены предпочтительнее)
        """
        for item in items:
            score = 0.0

            # 1. External arbitrage bonus (+50 points if profitable)
            ext_arb = item.get("external_arbitrage", {})
            if ext_arb.get("has_opportunity"):
                score += 50
                score += ext_arb.get("profit_margin", 0) * 2  # x2 multiplier

            # 2. Discount score
            discount = item.get("discount_percent", 0)
            score += discount

            # 3. Liquidity score
            sales_volume = item.get("sales_volume", 0)
            if sales_volume > 20:
                score += 20
            elif sales_volume > 10:
                score += 10
            elif sales_volume > 5:
                score += 5

            # 4. Price range bonus (средние цены $5-$30 более ликвидны)
            price = item.get("price_usd", 0)
            if 5 <= price <= 30:
                score += 10
            elif 30 < price <= 100:
                score += 5

            item["opportunity_score"] = round(score, 2)

        # Сортируем по score
        items.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)

        return items

    def _game_id_to_string(self, game_id: str) -> str:
        """Конвертировать game_id в строковое название."""
        mapping = {
            "a8db": "csgo",
            "9a92": "dota2",
            "rust": "rust",
            "tf2": "tf2",
        }
        return mapping.get(game_id, "csgo")

    async def close(self) -> None:
        """Закрыть все соединения."""
        if self.external_api:
            await self.external_api.close()


# Convenience function
async def scan_with_enhancements(
    game: str = "csgo",
    min_price: float = 5.0,
    max_price: float = 50.0,
    min_discount: float = 15.0,
) -> list[dict[str, Any]]:
    """Быстрый запуск enhanced сканера.

    Args:
        game: Игра (csgo, dota2, rust, tf2)
        min_price: Минимальная цена
        max_price: Максимальная цена
        min_discount: Минимальная скидка в процентах (default: 15%)

    Returns:
        Список арбитражных возможностей
    """
    game_ids = {
        "csgo": "a8db",
        "dota2": "9a92",
        "rust": "rust",
        "tf2": "tf2",
    }

    game_id = game_ids.get(game, "a8db")

    scanner = EnhancedArbitrageScanner(min_discount=min_discount)

    try:
        return await scanner.find_opportunities(
            game_id=game_id,
            min_price=min_price,
            max_price=max_price,
        )
    finally:
        await scanner.close()
