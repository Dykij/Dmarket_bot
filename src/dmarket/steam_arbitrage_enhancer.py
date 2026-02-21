"""
Интеграция Steam API в сканер арбитража.

Этот модуль добавляет проверку цен Steam к существующему сканеру DMarket.
"""

import asyncio
import logging

from src.dmarket.steam_api import (
    STEAM_CACHE_HOURS,
    ItemNotFoundError,
    RateLimitError,
    calculate_arbitrage,
    get_liquidity_status,
    get_steam_price,
    normalize_item_name,
)
from src.utils.steam_db_handler import get_steam_db

logger = logging.getLogger(__name__)


class SteamArbitrageEnhancer:
    """
    Класс для расширения сканера арбитража проверкой цен Steam.

    Добавляет к сканированию DMarket:
    - Сравнение с ценами Steam Market
    - Фильтрацию по ликвидности
    - Кэширование цен
    - Blacklist предметов
    """

    def __init__(self):
        """Инициализация enhancer."""
        self.db = get_steam_db()
        self.settings = self.db.get_settings()
        logger.info("SteamArbitrageEnhancer initialized")
        logger.info(
            f"Settings: min_profit={self.settings['min_profit']}%, min_volume={self.settings['min_volume']}"
        )

    async def enhance_items(self, dmarket_items: list[dict]) -> list[dict]:
        """
        Обогащает предметы DMarket данными Steam и фильтрует по профиту.

        Args:
            dmarket_items: Список предметов с DMarket

        Returns:
            Список предметов с добавленными данными Steam и расчетами профита
        """
        enhanced_items = []
        processed_count = 0
        skipped_count = 0

        logger.info(f"Starting enhancement of {len(dmarket_items)} items")

        for item in dmarket_items:
            processed_count += 1

            # Проверка blacklist
            item_name = item.get("title", "")
            if self.db.is_blacklisted(item_name):
                logger.debug(f"Skipping blacklisted item: {item_name}")
                skipped_count += 1
                continue

            # Нормализация названия
            normalized_name = normalize_item_name(item_name)

            # Проверка кэша Steam
            steam_data = self.db.get_steam_data(normalized_name)

            if steam_data and self.db.is_cache_actual(
                steam_data["last_updated"], STEAM_CACHE_HOURS
            ):
                logger.debug(f"Using cached Steam data for: {item_name}")
            else:
                # Запрос к Steam API
                try:
                    steam_data = await get_steam_price(normalized_name)

                    if steam_data:
                        # Сохраняем в кэш
                        self.db.update_steam_price(
                            normalized_name,
                            steam_data["price"],
                            steam_data["volume"],
                            steam_data.get("median_price"),
                        )
                        logger.info(
                            f"Fetched Steam price: {item_name} = ${steam_data['price']}"
                        )
                    else:
                        logger.warning(f"No Steam data returned for: {item_name}")
                        skipped_count += 1
                        continue

                    # Пауза между запросами (уже есть в декораторе)
                    await asyncio.sleep(0.5)

                except ItemNotFoundError:
                    logger.warning(f"Item not found on Steam: {item_name}")
                    skipped_count += 1
                    continue

                except RateLimitError:
                    logger.error(
                        "Steam Rate Limit hit! Stopping enhancement."
                    )  # noqa: TRY400
                    break

                except Exception as e:
                    logger.exception(f"Error fetching Steam price for {item_name}: {e}")
                    skipped_count += 1
                    continue

            # Проверка ликвидности
            if not steam_data or steam_data["volume"] < self.settings["min_volume"]:
                logger.debug(
                    f"Low liquidity for {item_name}: volume={steam_data['volume'] if steam_data else 0}"
                )
                skipped_count += 1
                continue

            # Расчет профита
            dmarket_price = (
                float(item.get("price", {}).get("USD", 0)) / 100
            )  # Cents to dollars
            steam_price = steam_data["price"]

            profit_pct = calculate_arbitrage(dmarket_price, steam_price)

            # Фильтр по минимальному профиту
            if profit_pct < self.settings["min_profit"]:
                logger.debug(f"Low profit for {item_name}: {profit_pct}%")
                skipped_count += 1
                continue

            # Логируем находку
            liquidity_status = get_liquidity_status(steam_data["volume"])
            self.db.log_opportunity(
                name=item_name,
                dmarket_price=dmarket_price,
                steam_price=steam_price,
                profit=profit_pct,
                volume=steam_data["volume"],
                liquidity_status=liquidity_status,
            )

            # Добавляем данные к предмету
            enhanced_item = item.copy()
            enhanced_item["steam_price"] = steam_price
            enhanced_item["steam_volume"] = steam_data["volume"]
            enhanced_item["profit_pct"] = profit_pct
            enhanced_item["liquidity_status"] = liquidity_status
            enhanced_item["dmarket_price_usd"] = dmarket_price

            enhanced_items.append(enhanced_item)

            logger.info(
                f"✅ Found opportunity: {item_name} | "
                f"DMarket: ${dmarket_price:.2f} | "
                f"Steam: ${steam_price:.2f} | "
                f"Profit: {profit_pct:.1f}% | "
                f"Volume: {steam_data['volume']} | "
                f"{liquidity_status}"
            )

        logger.info(
            f"Enhancement complete: {len(enhanced_items)} opportunities found, "
            f"{skipped_count} items skipped, "
            f"{processed_count} total processed"
        )

        return enhanced_items

    def update_settings(
        self, min_profit: float | None = None, min_volume: int | None = None
    ):
        """
        Обновляет настройки фильтрации.

        Args:
            min_profit: Минимальный процент прибыли
            min_volume: Минимальный объем продаж
        """
        self.db.update_settings(min_profit=min_profit, min_volume=min_volume)
        self.settings = self.db.get_settings()
        logger.info(f"Settings updated: {self.settings}")

    def add_to_blacklist(self, item_name: str, reason: str = "Manual"):
        """Добавляет предмет в blacklist."""
        self.db.add_to_blacklist(item_name, reason)
        logger.info(f"Added to blacklist: {item_name}")

    def get_daily_stats(self) -> dict:
        """Получает статистику за день."""
        return self.db.get_daily_stats()

    def get_top_items_today(self, limit: int = 5) -> list:
        """Получает топ предметов дня."""
        return self.db.get_top_items_today(limit)


# Singleton instance
_enhancer_instance: SteamArbitrageEnhancer | None = None


def get_steam_enhancer() -> SteamArbitrageEnhancer:
    """Получает singleton instance enhancer."""
    global _enhancer_instance
    if _enhancer_instance is None:
        _enhancer_instance = SteamArbitrageEnhancer()
    return _enhancer_instance
