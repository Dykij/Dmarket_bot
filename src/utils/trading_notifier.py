"""Модуль для интеграции уведомлений с торговыми операциями.

Этот модуль предоставляет wrapper-функции для DMarketAPI,
которые автоматически отправляют уведомления пользователям
о торговых операциях (покупка, продажа).
"""

import logging
from typing import Any

from telegram import Bot

from src.dmarket.dmarket_api import DMarketAPI
from src.telegram_bot.notification_queue import NotificationQueue
from src.telegram_bot.notifier import (
    send_buy_failed_notification,
    send_buy_intent_notification,
    send_buy_success_notification,
    send_sell_success_notification,
)

logger = logging.getLogger(__name__)


class TradingNotifier:
    """Обертка над DMarketAPI с автоматическими уведомлениями."""

    def __init__(
        self,
        api_client: DMarketAPI,
        bot: Bot | None = None,
        notification_queue: NotificationQueue | None = None,
        user_id: int | None = None,
    ) -> None:
        """Инициализировать TradingNotifier.

        Args:
            api_client: Экземпляр DMarketAPI
            bot: Экземпляр Telegram Bot (опционально)
            notification_queue: Очередь уведомлений (опционально)
            user_id: ID пользователя для отправки уведомлений

        """
        self.api = api_client
        self.bot = bot
        self.notification_queue = notification_queue
        self.user_id = user_id

    def _create_item_dict(self, item_name: str, price: float, game: str) -> dict[str, Any]:
        """Create item dictionary for notification functions.

        Args:
            item_name: Item name/title
            price: Price in USD (will be converted to cents)
            game: Game code (csgo, dota2, etc.)

        Returns:
            Item dictionary compatible with notification functions

        """
        return {
            "title": item_name,
            "price": {"USD": int(price * 100)},
            "game": game,
        }

    async def buy_item_with_notifications(
        self,
        item_id: str,
        item_name: str,
        buy_price: float,
        sell_price: float,
        game: str = "csgo",
        source: str = "arbitrage_scanner",
    ) -> dict[str, Any]:
        """Купить предмет с уведомлениями.

        Args:
            item_id: ID предмета
            item_name: Название предмета
            buy_price: Цена покупки
            sell_price: Планируемая цена продажи
            game: Код игры
            source: Источник возможности

        Returns:
            Результат операции покупки

        """
        profit_usd = (sell_price * 0.93) - buy_price
        profit_percent = (profit_usd / buy_price) * 100

        # Отправить уведомление о намерении купить
        if self.bot and self.user_id:
            item_dict = self._create_item_dict(item_name, buy_price, game)
            reason = f"Источник: {source}, Прибыль: ${profit_usd:.2f} ({profit_percent:.1f}%)"
            await send_buy_intent_notification(
                bot=self.bot,
                user_id=self.user_id,
                item=item_dict,
                reason=reason,
                callback_data=item_id,
            )

        try:
            # Выполнить покупку
            result = await self.api.buy_item(item_id=item_id, price=buy_price, game=game)

            # Проверить успешность
            if result.get("success"):
                # Отправить уведомление об успешной покупке
                if self.bot and self.user_id:
                    item_dict = self._create_item_dict(item_name, buy_price, game)
                    await send_buy_success_notification(
                        bot=self.bot,
                        user_id=self.user_id,
                        item=item_dict,
                        buy_price=buy_price,
                        order_id=result.get("orderId"),
                    )
            elif self.bot and self.user_id:
                # Отправить уведомление об ошибке
                error_reason = result.get("error", "Unknown error")
                item_dict = self._create_item_dict(item_name, buy_price, game)
                await send_buy_failed_notification(
                    bot=self.bot,
                    user_id=self.user_id,
                    item=item_dict,
                    error=str(error_reason),
                )

            return result

        except Exception as e:
            # Отправить уведомление об ошибке
            if self.bot and self.user_id:
                item_dict = self._create_item_dict(item_name, buy_price, game)
                await send_buy_failed_notification(
                    bot=self.bot,
                    user_id=self.user_id,
                    item=item_dict,
                    error=str(e),
                )

            raise

    async def sell_item_with_notifications(
        self,
        item_id: str,
        item_name: str,
        buy_price: float,
        sell_price: float,
        game: str = "csgo",
    ) -> dict[str, Any]:
        """Продать предмет с уведомлениями.

        Args:
            item_id: ID предмета
            item_name: Название предмета
            buy_price: Цена покупки
            sell_price: Цена продажи
            game: Код игры

        Returns:
            Результат операции продажи

        """
        try:
            # Выполнить продажу
            result = await self.api.sell_item(item_id=item_id, price=sell_price, game=game)

            # Если продажа успешна, отправить уведомление
            if result.get("success"):
                if self.bot and self.user_id:
                    item_dict = self._create_item_dict(item_name, sell_price, game)
                    await send_sell_success_notification(
                        bot=self.bot,
                        user_id=self.user_id,
                        item=item_dict,
                        sell_price=sell_price,
                        buy_price=buy_price,
                    )

            return result

        except Exception as e:
            logger.exception("Ошибка при продаже предмета %s: %s", item_name, e)
            raise


# Вспомогательная функция для быстрой покупки с уведомлениями
async def buy_with_notifications(
    api_client: DMarketAPI,
    bot: Bot,
    user_id: int,
    item_id: str,
    item_name: str,
    buy_price: float,
    sell_price: float,
    game: str = "csgo",
    source: str = "arbitrage_scanner",
    notification_queue: NotificationQueue | None = None,
) -> dict[str, Any]:
    """Купить предмет с уведомлениями (функция-обертка).

    Args:
        api_client: Экземпляр DMarketAPI
        bot: Экземпляр Telegram Bot
        user_id: ID пользователя
        item_id: ID предмета
        item_name: Название предмета
        buy_price: Цена покупки
        sell_price: Планируемая цена продажи
        game: Код игры
        source: Источник возможности
        notification_queue: Очередь уведомлений (опционально)

    Returns:
        Результат операции покупки

    """
    notifier = TradingNotifier(
        api_client=api_client,
        bot=bot,
        notification_queue=notification_queue,
        user_id=user_id,
    )

    return await notifier.buy_item_with_notifications(
        item_id=item_id,
        item_name=item_name,
        buy_price=buy_price,
        sell_price=sell_price,
        game=game,
        source=source,
    )
