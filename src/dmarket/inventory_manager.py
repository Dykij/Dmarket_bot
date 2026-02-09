"""Inventory Manager for automatic selling and price undercutting.

This module manages user inventory and active sell offers, automatically:
- Lists newly purchased items for sale
- Undercuts competitor prices to stay at the top
- Protects against selling at a loss
"""

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from telegram import Bot

    from src.dmarket.dmarket_api import DMarketAPI

logger = logging.getLogger(__name__)


class InventoryManager:
    """Менеджер инвентаря для автоматической продажи и undercutting."""

    def __init__(
        self,
        api_client: "DMarketAPI",
        telegram_bot: "Bot | None" = None,
        undercut_step: int = 1,
        max_relist_attempts: int = 5,
        min_profit_margin: float = 1.02,
        check_interval: int = 1800,
        config: dict | None = None,
    ):
        """Инициализирует менеджер инвентаря.

        Args:
            api_client: DMarket API клиент
            telegram_bot: Telegram Bot для уведомлений (опционально)
            undercut_step: На сколько центов снижать цену (в единицах API DMarket)
            max_relist_attempts: Сколько раз снижать цену перед уведомлением
            min_profit_margin: Минимальная маржа (1.02 = +2% от цены покупки)
            check_interval: Интервал проверки инвентаря в секундах (по умолчанию 30 минут)
            config: Configuration dictionary for advanced features
        """
        self.api = api_client
        self.tg = telegram_bot
        self.undercut_step = undercut_step
        self.max_relist_attempts = max_relist_attempts
        self.min_profit_margin = min_profit_margin
        self.check_interval = check_interval
        self.config = config or {}

        # Счетчики для статистики
        self.total_undercuts = 0
        self.total_listed = 0
        self.failed_listings = 0

        # Карта попыток перевыставления (item_id -> attempts)
        self.relist_attempts: dict[str, int] = {}

        # Initialize smart repricing if enabled
        self.smart_repricer = None
        self.blacklist_manager = None

        try:
            from src.dmarket.smart_repricing import SmartRepricer

            repricing_config = self.config.get("repricing", {})
            if repricing_config.get("enabled", True):
                self.smart_repricer = SmartRepricer(api_client, repricing_config)
                logger.info("SmartRepricer enabled for age-based price adjustments")
        except ImportError:
            logger.debug("SmartRepricer not available")

        try:
            from src.dmarket.blacklist_manager import BlacklistManager

            blacklist_config = self.config.get("blacklist", {})
            if blacklist_config.get("enabled", True):
                self.blacklist_manager = BlacklistManager(
                    config=self.config,
                    blacklist_file=blacklist_config.get("file_path", "data/blacklist.json"),
                )
                logger.info("BlacklistManager enabled for seller/item filtering")
        except ImportError:
            logger.debug("BlacklistManager not available")

    async def refresh_inventory_loop(self) -> None:
        """Главный цикл управления инвентарем и продажами.

        Запускается в фоне и периодически проверяет:
        1. Активные продажи (для undercutting)
        2. Новые предметы в инвентаре (для автоматического выставления)
        """
        logger.info(f"📦 Inventory Manager started (check interval: {self.check_interval}s)")

        while True:
            try:
                logger.debug("📦 Checking inventory and active offers...")

                # 1. Проверяем и обновляем активные продажи
                await self._manage_active_offers()

                # 2. Проверяем новые предметы в инвентаре
                await self._list_new_inventory_items()

                # Пауза между проверками
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.exception(f"⚠️ Error in InventoryManager loop: {e}")
                # При ошибке делаем короткую паузу и продолжаем
                await asyncio.sleep(60)

    async def _manage_active_offers(self) -> None:
        """Управляет активными предложениями (undercutting)."""
        try:
            # Получаем список активных продаж
            # FIX: Используем правильный метод list_user_offers вместо get_user_offers
            my_offers_response = await self.api.list_user_offers()

            # API может вернуть dict с ключом "Items" или "objects"
            if isinstance(my_offers_response, dict):
                my_offers = my_offers_response.get("Items", my_offers_response.get("objects", []))
            else:
                my_offers = []

            if not my_offers:
                logger.debug("No active offers to manage")
                return

            logger.info(f"📊 Managing {len(my_offers)} active offers")

            # Проверяем каждое предложение
            for offer in my_offers:
                await self._manage_single_offer(offer)

        except Exception as e:
            logger.exception(f"Error managing active offers: {e}")

    async def _manage_single_offer(self, offer: dict[str, Any]) -> None:
        """Управляет одним предложением (логика Undercutting).

        Args:
            offer: Данные предложения
        """
        title = offer.get("title", "Unknown")
        offer_id = offer.get("offerId") or offer.get("OfferId")

        # Получаем текущую цену (может быть dict или int)
        price_data = offer.get("price", {})
        if isinstance(price_data, dict):
            my_price = int(price_data.get("amount", 0))
        else:
            my_price = int(price_data)

        if my_price <= 0:
            logger.warning(f"Invalid price for offer {offer_id}: {my_price}")
            return

        try:
            # Получаем минимальную цену конкурентов на маркете
            market_min_price = await self._get_market_min_price(title)

            if market_min_price <= 0:
                logger.debug(f"No market price data for {title}")
                return

            # Если кто-то выставил дешевле нас
            if market_min_price < my_price:
                new_price = market_min_price - self.undercut_step

                # Проверка "пола" (нижней границы цены)
                # Не продаем дешевле, чем цена покупки + min_profit_margin
                buy_price_data = offer.get("buy_price", offer.get("buyPrice", 0))
                if isinstance(buy_price_data, dict):
                    buy_price = int(buy_price_data.get("amount", 0))
                else:
                    buy_price = int(buy_price_data)

                min_price_threshold = int(buy_price * self.min_profit_margin)

                if new_price >= min_price_threshold:
                    logger.info(
                        f"📉 Undercutting {title}: ${my_price / 100:.2f} -> ${new_price / 100:.2f}"
                    )

                    # Обновляем цену предложения
                    success = await self._edit_offer_price(offer_id, new_price)

                    if success:
                        self.total_undercuts += 1
                        # Уведомляем в Telegram (опционально)
                        if self.tg:
                            await self._send_telegram_message(
                                f"📉 Price updated: {title}\n"
                                f"Old: ${my_price / 100:.2f} → New: ${new_price / 100:.2f}"
                            )
                else:
                    logger.warning(
                        f"⛔ Cannot undercut {title}: "
                        f"would go below profit threshold "
                        f"(${new_price / 100:.2f} < ${min_price_threshold / 100:.2f})"
                    )

        except Exception as e:
            logger.exception(f"Error managing offer for {title}: {e}")

    async def _list_new_inventory_items(self) -> None:
        """Проверяет инвентарь и выставляет новые предметы на продажу."""
        try:
            # Получаем инвентарь пользователя
            inventory_response = await self.api.get_user_inventory()

            # API может вернуть dict с ключом "objects" или "Items"
            if isinstance(inventory_response, dict):
                inventory_items = inventory_response.get(
                    "objects", inventory_response.get("Items", [])
                )
            else:
                inventory_items = []

            # Фильтруем только предметы, которые не выставлены на продажу
            new_items = [
                item
                for item in inventory_items
                if item.get("status") == "at_inventory" or item.get("inMarket") is False
            ]

            if not new_items:
                logger.debug("No new inventory items to list")
                return

            logger.info(f"📦 Found {len(new_items)} new items to list")

            for item in new_items:
                await self._list_single_item(item)

        except Exception as e:
            logger.exception(f"Error listing new inventory items: {e}")

    async def _list_single_item(self, item: dict[str, Any]) -> None:
        """Выставляет один предмет на продажу.

        Args:
            item: Данные предмета из инвентаря
        """
        title = item.get("title", "Unknown")
        item_id = item.get("itemId") or item.get("assetId")

        if not item_id:
            logger.warning(f"No item_id for {title}")
            return

        try:
            # Получаем конкурентную цену
            market_min_price = await self._get_market_min_price(title)

            # Если данных о рынке нет, используем Steam Price + 10%
            if market_min_price <= 0:
                steam_price_data = item.get("steamPrice", {})
                if isinstance(steam_price_data, dict):
                    steam_price = steam_price_data.get("amount", 0)
                else:
                    steam_price = steam_price_data or 0

                if steam_price > 0:
                    market_min_price = int(steam_price * 1.1)
                else:
                    logger.warning(f"No price data for {title}, skipping")
                    return

            # Выставляем предмет
            logger.info(f"🚀 Listing {title} for ${market_min_price / 100:.2f}")

            success = await self._create_sell_offer(item_id, market_min_price)

            if success:
                self.total_listed += 1
                # Уведомляем в Telegram
                if self.tg:
                    await self._send_telegram_message(
                        f"🚀 Listed for sale: {title}\nPrice: ${market_min_price / 100:.2f}"
                    )
            else:
                self.failed_listings += 1

        except Exception as e:
            logger.exception(f"Error listing item {title}: {e}")
            self.failed_listings += 1

    async def _get_market_min_price(self, title: str) -> int:
        """Получает минимальную цену предмета на маркете.

        Args:
            title: Название предмета

        Returns:
            Минимальная цена в центах (0 если не найдена)
        """
        try:
            # Ищем предмет на маркете
            market_items = await self.api.get_market_items(title=title, limit=10)

            if isinstance(market_items, dict):
                items = market_items.get("objects", [])
            else:
                items = []

            if not items:
                return 0

            # Находим минимальную цену среди первых 10 результатов
            min_price = float("inf")
            for item in items:
                price_data = item.get("price", {})
                if isinstance(price_data, dict):
                    price = price_data.get("amount", 0)
                else:
                    price = price_data or 0

                if price > 0 and price < min_price:
                    min_price = price

            return int(min_price) if min_price != float("inf") else 0

        except Exception as e:
            logger.exception(f"Error getting market price for {title}: {e}")
            return 0

    async def _edit_offer_price(self, offer_id: str, new_price: int) -> bool:
        """Изменяет цену активного предложения.

        Args:
            offer_id: ID предложения
            new_price: Новая цена в центах

        Returns:
            True если успешно, False иначе
        """
        try:
            result = await self.api.edit_offer(offer_id, {"price": {"amount": new_price}})
            return result.get("success", False) if isinstance(result, dict) else False
        except Exception as e:
            logger.exception(f"Error editing offer {offer_id}: {e}")
            return False

    async def _create_sell_offer(self, item_id: str, price: int) -> bool:
        """Создает предложение о продаже.

        Args:
            item_id: ID предмета
            price: Цена в центах

        Returns:
            True если успешно, False иначе
        """
        try:
            result = await self.api.create_sell_offer(item_id, {"price": {"amount": price}})
            return result.get("success", False) if isinstance(result, dict) else False
        except Exception as e:
            logger.exception(f"Error creating sell offer for {item_id}: {e}")
            return False

    async def _send_telegram_message(self, text: str) -> None:
        """Отправляет сообщение в Telegram.

        Args:
            text: Текст сообщения
        """
        if not self.tg:
            return

        try:
            chat_id = os.getenv("ADMIN_CHAT_ID")
            if chat_id:
                await self.tg.send_message(chat_id=chat_id, text=text)
        except Exception as e:
            logger.exception(f"Error sending Telegram message: {e}")

    def get_statistics(self) -> dict[str, Any]:
        """Получает статистику работы менеджера.

        Returns:
            Словарь со статистикой
        """
        return {
            "total_undercuts": self.total_undercuts,
            "total_listed": self.total_listed,
            "failed_listings": self.failed_listings,
            "active_relist_attempts": len(self.relist_attempts),
        }
