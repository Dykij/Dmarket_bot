"""Trading Persistence Manager для сохранения и восстановления сделок.

Этот модуль реализует систему персистентности, которая гарантирует,
что бот не "забудет" о купленных предметах после перезагрузки или
выключения ПК.

Ключевые возможности:
1. Сохранение покупок в базу данных с ценой закупки
2. Восстановление незавершенных сделок при старте бота
3. Синхронизация с API DMarket для актуального статуса
4. Защита от продажи в убыток (минимальная цена)
5. Логирование и уведомления в Telegram

Использование:
    ```python
    from src.utils.trading_persistence import TradingPersistence

    # Инициализация
    persistence = TradingPersistence(database, dmarket_api, telegram_bot)

    # Сохранить покупку
    await persistence.save_purchase(
        asset_id="abc123", title="AK-47 | Redline", buy_price=10.50, game="csgo"
    )

    # Восстановить при старте
    pending = await persistence.recover_pending_trades()
    ```
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.models.pending_trade import PendingTrade, PendingTradeStatus

if TYPE_CHECKING:
    from telegram import Bot

    from src.dmarket.dmarket_api import DMarketAPI
    from src.utils.database import DatabaseManager


logger = logging.getLogger(__name__)


class TradingPersistence:
    """Менеджер персистентности сделок.

    Гарантирует сохранение данных о покупках и их восстановление
    после перезапуска бота.

    Attributes:
        db: Менеджер базы данных
        api: DMarket API клиент
        telegram_bot: Telegram Bot для уведомлений
        min_margin_percent: Минимальный процент маржи (защита от убытков)
        dmarket_fee_percent: Процент комиссии DMarket
    """

    def __init__(
        self,
        database: DatabaseManager,
        dmarket_api: DMarketAPI | None = None,
        telegram_bot: Bot | None = None,
        min_margin_percent: float = 5.0,
        dmarket_fee_percent: float = 7.0,
    ) -> None:
        """Инициализация менеджера персистентности.

        Args:
            database: Менеджер базы данных
            dmarket_api: DMarket API клиент (опционально)
            telegram_bot: Telegram Bot для уведомлений (опционально)
            min_margin_percent: Минимальный процент маржи
            dmarket_fee_percent: Процент комиссии DMarket
        """
        self.db = database
        self.api = dmarket_api
        self.tg = telegram_bot
        self.min_margin_percent = min_margin_percent
        self.dmarket_fee_percent = dmarket_fee_percent

        logger.info(
            "TradingPersistence initialized: "
            f"min_margin={min_margin_percent}%, fee={dmarket_fee_percent}%"
        )

    async def save_purchase(
        self,
        asset_id: str,
        title: str,
        buy_price: float,
        game: str = "csgo",
        item_id: str | None = None,
        user_id: int | None = None,
        target_sell_price: float | None = None,
    ) -> PendingTrade:
        """Сохранить покупку в базу данных.

        Автоматически рассчитывает минимальную цену продажи
        для защиты от убытков.

        Args:
            asset_id: ID предмета в DMarket
            title: Название предмета
            buy_price: Цена покупки в USD
            game: Код игры
            item_id: Альтернативный ID предмета
            user_id: Telegram ID пользователя
            target_sell_price: Целевая цена продажи

        Returns:
            Созданная или обновленная запись PendingTrade
        """
        # Рассчитываем минимальную цену продажи
        min_sell_price = PendingTrade.calculate_min_sell_price(
            buy_price=buy_price,
            min_margin_percent=self.min_margin_percent,
            dmarket_fee_percent=self.dmarket_fee_percent,
        )

        # Целевая цена = min_sell_price + 10% если не указана
        if target_sell_price is None:
            target_sell_price = round(min_sell_price * 1.10, 2)

        async with self.db.get_async_session() as session:
            # Upsert: вставка или обновление
            stmt = sqlite_insert(PendingTrade).values(
                asset_id=asset_id,
                item_id=item_id,
                user_id=user_id,
                title=title,
                game=game,
                buy_price=buy_price,
                min_sell_price=min_sell_price,
                target_sell_price=target_sell_price,
                status=PendingTradeStatus.BOUGHT,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

            # При конфликте обновляем цены и статус
            stmt = stmt.on_conflict_do_update(
                index_elements=["asset_id"],
                set_={
                    "buy_price": buy_price,
                    "min_sell_price": min_sell_price,
                    "target_sell_price": target_sell_price,
                    "status": PendingTradeStatus.BOUGHT,
                    "updated_at": datetime.now(UTC),
                },
            )

            await session.execute(stmt)
            await session.commit()

            # Получаем созданную запись
            result = await session.execute(
                select(PendingTrade).where(PendingTrade.asset_id == asset_id)
            )
            trade = result.scalar_one()

            logger.info(
                f"💾 Purchase saved: {title} (buy=${buy_price:.2f}, min_sell=${min_sell_price:.2f})"
            )

            return trade

    async def update_status(
        self,
        asset_id: str,
        status: PendingTradeStatus,
        offer_id: str | None = None,
        current_price: float | None = None,
    ) -> bool:
        """Обновить статус сделки.

        Args:
            asset_id: ID предмета
            status: Новый статус
            offer_id: ID предложения на DMarket
            current_price: Текущая цена предложения

        Returns:
            True если обновлено успешно
        """
        async with self.db.get_async_session() as session:
            update_values: dict[str, Any] = {
                "status": status,
                "updated_at": datetime.now(UTC),
            }

            if offer_id is not None:
                update_values["offer_id"] = offer_id

            if current_price is not None:
                update_values["current_price"] = current_price

            # Устанавливаем listed_at при первом выставлении
            if status == PendingTradeStatus.LISTED:
                update_values["listed_at"] = datetime.now(UTC)

            # Устанавливаем sold_at при продаже
            if status in {PendingTradeStatus.SOLD, PendingTradeStatus.STOP_LOSS}:
                update_values["sold_at"] = datetime.now(UTC)

            stmt = (
                update(PendingTrade)
                .where(PendingTrade.asset_id == asset_id)
                .values(**update_values)
            )

            result = await session.execute(stmt)
            await session.commit()

            if result.rowcount > 0:
                logger.debug(f"Status updated: {asset_id} -> {status}")
                return True

            logger.warning(f"Trade not found for status update: {asset_id}")
            return False

    async def mark_as_sold(
        self,
        asset_id: str,
        final_price: float | None = None,
    ) -> bool:
        """Пометить предмет как проданный.

        Args:
            asset_id: ID предмета
            final_price: Финальная цена продажи

        Returns:
            True если обновлено успешно
        """
        async with self.db.get_async_session() as session:
            # Получаем текущую запись для расчета прибыли
            result = await session.execute(
                select(PendingTrade).where(PendingTrade.asset_id == asset_id)
            )
            trade = result.scalar_one_or_none()

            if not trade:
                logger.warning(f"Trade not found to mark as sold: {asset_id}")
                return False

            price = final_price or trade.current_price or trade.target_sell_price
            profit, profit_percent = trade.calculate_profit(price)

            stmt = (
                update(PendingTrade)
                .where(PendingTrade.asset_id == asset_id)
                .values(
                    status=PendingTradeStatus.SOLD,
                    current_price=price,
                    sold_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )

            await session.execute(stmt)
            await session.commit()

            # Format price safely
            price_str = f"${price:.2f}" if price else "unknown"
            logger.info(
                f"✅ Item sold: {trade.title} "
                f"(buy=${trade.buy_price:.2f}, sell={price_str}, "
                f"profit=${profit:.2f} / {profit_percent:.1f}%)"
            )

            return True

    async def get_pending_trades(
        self,
        status: PendingTradeStatus | None = None,
        game: str | None = None,
    ) -> list[PendingTrade]:
        """Получить список незавершенных сделок.

        Args:
            status: Фильтр по статусу
            game: Фильтр по игре

        Returns:
            Список сделок
        """
        async with self.db.get_async_session() as session:
            query = select(PendingTrade)

            # Исключаем завершенные сделки по умолчанию
            if status is None:
                query = query.where(
                    PendingTrade.status.notin_([
                        PendingTradeStatus.SOLD,
                        PendingTradeStatus.CANCELLED,
                        PendingTradeStatus.STOP_LOSS,
                    ])
                )
            else:
                query = query.where(PendingTrade.status == status)

            if game:
                query = query.where(PendingTrade.game == game)

            query = query.order_by(PendingTrade.created_at.desc())

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_trade_by_asset_id(self, asset_id: str) -> PendingTrade | None:
        """Получить сделку по asset_id.

        Args:
            asset_id: ID предмета

        Returns:
            PendingTrade или None
        """
        async with self.db.get_async_session() as session:
            result = await session.execute(
                select(PendingTrade).where(PendingTrade.asset_id == asset_id)
            )
            return result.scalar_one_or_none()

    async def recover_pending_trades(self) -> list[dict[str, Any]]:
        """Восстановить незавершенные сделки при старте бота.

        Синхронизирует локальную базу с инвентарем DMarket:
        - Если предмет в инвентаре - нужно выставить на продажу
        - Если предмета нет - значит продался пока бот был выключен

        Returns:
            Список обработанных сделок с действиями
        """
        logger.info("🔍 Recovering pending trades after restart...")

        pending_trades = await self.get_pending_trades()

        if not pending_trades:
            logger.info("✅ No pending trades to recover")
            return []

        logger.info(f"📦 Found {len(pending_trades)} pending trades")

        results: list[dict[str, Any]] = []

        # Получаем актуальный инвентарь с DMarket
        inventory_ids: set[str] = set()
        if self.api:
            try:
                inventory = await self.api.get_user_inventory()
                if isinstance(inventory, dict):
                    items = inventory.get("objects", inventory.get("Items", []))
                    for item in items:
                        item_id = item.get("assetId") or item.get("asset_id") or item.get("itemId")
                        if item_id:
                            inventory_ids.add(item_id)
                logger.info(f"📋 Current inventory: {len(inventory_ids)} items")
            except Exception as e:
                logger.exception(f"Failed to get inventory: {e}")

        # Обрабатываем каждую незавершенную сделку
        for trade in pending_trades:
            action = await self._process_pending_trade(trade, inventory_ids)
            results.append(action)

        # Уведомляем в Telegram
        await self._send_recovery_summary(results)

        return results

    async def _process_pending_trade(
        self,
        trade: PendingTrade,
        inventory_ids: set[str],
    ) -> dict[str, Any]:
        """Обработать одну незавершенную сделку.

        Args:
            trade: Сделка для обработки
            inventory_ids: ID предметов в текущем инвентаре

        Returns:
            Словарь с информацией о действии
        """
        result: dict[str, Any] = {
            "asset_id": trade.asset_id,
            "title": trade.title,
            "buy_price": trade.buy_price,
            "status": trade.status,
            "action": "none",
        }

        # Предмет в инвентаре?
        if trade.asset_id in inventory_ids:
            if trade.status == PendingTradeStatus.BOUGHT:
                # Нужно выставить на продажу
                result["action"] = "list_for_sale"
                result["min_sell_price"] = trade.min_sell_price
                logger.info(
                    f"📦 Item needs listing: {trade.title} (min_sell=${trade.min_sell_price:.2f})"
                )
            elif trade.status == PendingTradeStatus.LISTED:
                # Уже выставлено, проверяем цену
                result["action"] = "check_price"
                logger.info(f"📊 Item listed, check price: {trade.title}")
        # Предмета нет в инвентаре
        elif trade.status in {
            PendingTradeStatus.BOUGHT,
            PendingTradeStatus.LISTED,
        }:
            # Продался пока бот был выключен
            await self.mark_as_sold(trade.asset_id)
            result["action"] = "marked_sold"
            result["status"] = PendingTradeStatus.SOLD
            logger.info(f"✅ Item sold while offline: {trade.title} (buy=${trade.buy_price:.2f})")

        return result

    async def _send_recovery_summary(
        self,
        results: list[dict[str, Any]],
    ) -> None:
        """Отправить сводку восстановления в Telegram.

        Args:
            results: Результаты обработки сделок
        """
        if not self.tg or not results:
            return

        # Подсчитываем статистику
        to_list = [r for r in results if r["action"] == "list_for_sale"]
        sold = [r for r in results if r["action"] == "marked_sold"]
        check = [r for r in results if r["action"] == "check_price"]

        lines = ["🔄 **Recovery Summary**", ""]

        if sold:
            lines.append(f"✅ Sold offline: {len(sold)} items")
            for item in sold[:5]:  # Показываем первые 5
                lines.append(f"  • {item['title']} (${item['buy_price']:.2f})")
            if len(sold) > 5:
                lines.append(f"  ... and {len(sold) - 5} more")
            lines.append("")

        if to_list:
            lines.append(f"📦 Need listing: {len(to_list)} items")
            for item in to_list[:5]:
                lines.append(f"  • {item['title']} (min ${item['min_sell_price']:.2f})")
            if len(to_list) > 5:
                lines.append(f"  ... and {len(to_list) - 5} more")
            lines.append("")

        if check:
            lines.append(f"📊 Price check: {len(check)} items")

        message = "\n".join(lines)

        try:
            import os

            admin_chat_id = os.getenv("ADMIN_CHAT_ID")
            if admin_chat_id:
                await self.tg.send_message(
                    chat_id=admin_chat_id,
                    text=message,
                    parse_mode="Markdown",
                )
        except Exception as e:
            logger.exception(f"Failed to send recovery summary: {e}")

    async def get_statistics(self) -> dict[str, Any]:
        """Получить статистику по сделкам.

        Returns:
            Словарь со статистикой
        """
        async with self.db.get_async_session() as session:
            # Общее количество по статусам
            all_trades = await session.execute(select(PendingTrade))
            trades = list(all_trades.scalars().all())

            stats: dict[str, Any] = {
                "total": len(trades),
                "by_status": {},
                "total_invested": 0.0,
                "total_profit": 0.0,
            }

            for trade in trades:
                status_key = trade.status
                stats["by_status"][status_key] = stats["by_status"].get(status_key, 0) + 1

                if trade.status != PendingTradeStatus.SOLD:
                    stats["total_invested"] += trade.buy_price
                else:
                    profit, _ = trade.calculate_profit()
                    stats["total_profit"] += profit

            return stats

    async def cleanup_old_trades(self, days: int = 30) -> int:
        """Очистить старые завершенные сделки.

        Args:
            days: Количество дней для хранения

        Returns:
            Количество удаленных записей
        """
        from datetime import timedelta

        cutoff = datetime.now(UTC) - timedelta(days=days)

        async with self.db.get_async_session() as session:
            from sqlalchemy import delete

            stmt = delete(PendingTrade).where(
                PendingTrade.status.in_([
                    PendingTradeStatus.SOLD,
                    PendingTradeStatus.CANCELLED,
                    PendingTradeStatus.STOP_LOSS,
                ]),
                PendingTrade.updated_at < cutoff,
            )

            result = await session.execute(stmt)
            await session.commit()

            deleted = result.rowcount or 0
            if deleted > 0:
                logger.info(f"🗑️ Cleaned up {deleted} old completed trades")

            return deleted


# Глобальный экземпляр для удобного доступа
_trading_persistence: TradingPersistence | None = None


def get_trading_persistence() -> TradingPersistence | None:
    """Получить глобальный экземпляр TradingPersistence.

    Returns:
        TradingPersistence или None если не инициализирован
    """
    return _trading_persistence


def init_trading_persistence(
    database: DatabaseManager,
    dmarket_api: DMarketAPI | None = None,
    telegram_bot: Bot | None = None,
    **kwargs: Any,
) -> TradingPersistence:
    """Инициализировать глобальный экземпляр TradingPersistence.

    Args:
        database: Менеджер базы данных
        dmarket_api: DMarket API клиент
        telegram_bot: Telegram Bot
        **kwargs: Дополнительные параметры

    Returns:
        Инициализированный TradingPersistence
    """
    global _trading_persistence
    _trading_persistence = TradingPersistence(
        database=database,
        dmarket_api=dmarket_api,
        telegram_bot=telegram_bot,
        **kwargs,
    )
    return _trading_persistence
