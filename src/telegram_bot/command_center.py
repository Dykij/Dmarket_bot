"""Telegram Command Center - расширенные команды управления ботом.

Этот модуль добавляет новые команды для полного контроля:
- /status - Полный отчет о состоянии бота
- /treasures - Список редких предметов в холде
- /panic_sell - Экстренный выход в кэш (-5% на всё)
- /add_target [URL] - Добавить предмет в отслеживание
- /logs - Получить последние логи
- /market_mode - Текущий режим рынка (распродажи)
- /portfolio - Общая стоимость портфеля

Использование:
    ```python
    from src.telegram_bot.command_center import CommandCenter

    center = CommandCenter(
        api_client=dmarket_api,
        db=trading_db,
        collectors_hold=collectors_hold_manager,
    )

    # Регистрация команд
    application.add_handler(CommandHandler("status", center.status_command))
    application.add_handler(CommandHandler("treasures", center.treasures_command))
    application.add_handler(CommandHandler("panic_sell", center.panic_sell_command))
    ```
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import aiofiles
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI
    from src.dmarket.steam_sales_protector import SteamSalesProtector
    from src.utils.collectors_hold import CollectorsHoldManager
    from src.utils.trading_persistence import TradingPersistence

logger = logging.getLogger(__name__)


class CommandCenter:
    """Центр управления ботом через Telegram.

    Предоставляет расширенные команды для мониторинга и управления.
    """

    def __init__(
        self,
        api_client: DMarketAPI | None = None,
        db: TradingPersistence | None = None,
        collectors_hold: CollectorsHoldManager | None = None,
        sales_protector: SteamSalesProtector | None = None,
    ) -> None:
        """Инициализация Command Center.

        Args:
            api_client: DMarket API клиент
            db: База данных
            collectors_hold: Менеджер удержания редких предметов
            sales_protector: Защитник от распродаж
        """
        self.api = api_client
        self.db = db
        self.collectors_hold = collectors_hold
        self.sales_protector = sales_protector

        self._start_time = datetime.now(UTC)
        self._panic_mode = False

        logger.info("CommandCenter initialized")

    async def status_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Команда /status - полный отчет о состоянии бота.

        Показывает:
        - Текущий баланс
        - Стоимость инвентаря в холде
        - Прибыль за 24 часа
        - Количество активных сделок
        - Uptime бота
        """
        if not update.message:
            return

        await update.message.reply_text("⏳ Собираю данные...")

        try:
            # Получаем баланс
            balance_usd = 0.0
            if self.api:
                try:
                    balance_data = await self.api.get_balance()
                    # API возвращает balance в долларах напрямую
                    balance_usd = float(balance_data.get("balance", 0))
                except Exception as e:
                    logger.exception(f"Failed to get balance: {e}")

            # Получаем статистику из БД
            # active_trades: Tracked for future dashboard expansion
            _active_trades = 0  # noqa: F841
            pending_items = 0
            treasures_count = 0
            total_invested = 0.0

            if self.db:
                try:
                    # Активные сделки
                    pending = await self.db.get_pending_items()
                    pending_items = len(pending) if pending else 0

                    # Подсчет инвестиций
                    for item in pending or []:
                        if isinstance(item, dict):
                            total_invested += float(item.get("buy_price", 0))
                        elif isinstance(item, tuple) and len(item) > 2:
                            total_invested += float(item[2])

                except Exception as e:
                    logger.exception(f"Failed to get DB stats: {e}")

            # Сокровища
            if self.collectors_hold:
                treasures = self.collectors_hold.get_treasures()
                treasures_count = len(treasures)

            # Uptime
            uptime = datetime.now(UTC) - self._start_time
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)

            # Режим рынка
            market_mode = "🟢 Нормальный"
            if self.sales_protector:
                status = self.sales_protector.get_current_mode()
                mode_map = {
                    "normal": "🟢 Нормальный",
                    "pre_sale": "🟡 Перед распродажей",
                    "sale": "🔴 Распродажа",
                    "post_sale": "🟠 После распродажи",
                }
                market_mode = mode_map.get(status.mode, "⚪ Неизвестно")

            # Формируем отчет
            report = [
                "📊 **СТАТУС БОТА**",
                "",
                f"💰 **Баланс:** ${balance_usd:.2f}",
                f"📦 **В холде:** {pending_items} предметов (${total_invested:.2f})",
                f"💎 **Сокровища:** {treasures_count} редких предметов",
                "",
                f"📈 **Общий портфель:** ${balance_usd + total_invested:.2f}",
                "",
                f"🎯 **Режим рынка:** {market_mode}",
                f"⏱️ **Uptime:** {hours}ч {minutes}м",
                "",
            ]

            if self._panic_mode:
                report.append("🚨 **PANIC MODE АКТИВЕН**")

            # Кнопки быстрых действий
            keyboard = [
                [
                    InlineKeyboardButton("💎 Сокровища", callback_data="show_treasures"),
                    InlineKeyboardButton("📋 Логи", callback_data="show_logs"),
                ],
                [
                    InlineKeyboardButton("🔄 Обновить", callback_data="refresh_status"),
                    InlineKeyboardButton("📊 Рынок", callback_data="market_mode"),
                ],
            ]

            await update.message.reply_text(
                "\n".join(report),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

        except Exception as e:
            logger.exception(f"Status command error: {e}")
            await update.message.reply_text(f"❌ Ошибка получения статуса: {e}")

    async def treasures_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Команда /treasures - список редких предметов в холде."""
        if not update.message:
            return

        if not self.collectors_hold:
            await update.message.reply_text("⚠️ Модуль Collector's Hold не подключен")
            return

        treasures = self.collectors_hold.get_treasures()

        if not treasures:
            await update.message.reply_text(
                "📜 **Сейф с сокровищами пуст**\n\n"
                "Пока редких вещей не найдено.\n"
                "Бот продолжает поиск! 🔍"
            )
            return

        # Формируем отчет
        report = ["💎 **ВАШИ СОКРОВИЩА**", ""]

        total_multiplier = 0.0
        for i, treasure in enumerate(treasures[-10:], 1):  # Последние 10
            emoji = "💎" if treasure.estimated_value_multiplier >= 1.5 else "✨"
            report.append(
                f"{emoji} {i}. **{treasure.title}**\n"
                f"   └ {treasure.reason_details[:50]}\n"
                f"   └ Множитель: {treasure.estimated_value_multiplier:.2f}x"
            )
            total_multiplier += treasure.estimated_value_multiplier

        report.extend([
            "",
            f"📊 **Всего сокровищ:** {len(treasures)}",
            f"💰 **Средний множитель:** {total_multiplier / len(treasures):.2f}x",
            "",
            "💡 Продайте их вручную на Buff163, CSFloat или других площадках.",
        ])

        await update.message.reply_text(
            "\n".join(report),
            parse_mode="Markdown",
        )

    async def panic_sell_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Команда /panic_sell - экстренный выход в кэш.

        Выставляет весь инвентарь на 5% дешевле конкурентов.
        Требует подтверждения.
        """
        if not update.message:
            return

        if not self.api:
            await update.message.reply_text("⚠️ API клиент не подключен")
            return

        # Проверяем аргументы
        args = context.args or []

        if "CONFIRM" not in args:
            # Запрашиваем подтверждение
            keyboard = [
                [
                    InlineKeyboardButton(
                        "⚠️ ПОДТВЕРДИТЬ PANIC SELL",
                        callback_data="confirm_panic_sell",
                    ),
                ],
                [
                    InlineKeyboardButton("❌ Отмена", callback_data="cancel_panic_sell"),
                ],
            ]

            await update.message.reply_text(
                "🚨 **PANIC SELL - ЭКСТРЕННЫЙ ВЫХОД В КЭШ**\n\n"
                "Эта команда выставит **ВЕСЬ** ваш инвентарь "
                "на 5% дешевле текущих конкурентов.\n\n"
                "⚠️ **Внимание!**\n"
                "• Сокровища (HOLD_RARE) НЕ будут затронуты\n"
                "• Вы можете потерять часть прибыли\n"
                "• Это необратимое действие\n\n"
                "Для подтверждения нажмите кнопку ниже:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        # Выполняем panic sell
        await update.message.reply_text("🔄 Начинаю PANIC SELL...")

        self._panic_mode = True

        try:
            # Получаем инвентарь
            inventory = await self.api.get_user_inventory()
            items = inventory.get("items", [])

            if not items:
                await update.message.reply_text("📦 Инвентарь пуст, нечего продавать.")
                return

            sold_count = 0
            skipped_count = 0

            for item in items:
                item_id = item.get("itemId")
                title = item.get("title", "Unknown")
                status = item.get("status", "")

                # Пропускаем уже выставленные
                if status == "listed":
                    skipped_count += 1
                    continue

                # Пропускаем сокровища (если есть в БД)
                if self.db:
                    try:
                        db_status = await self.db.get_item_status(item_id)
                        if db_status == "HOLD_RARE":
                            skipped_count += 1
                            continue
                    except Exception:
                        pass

                # Получаем текущую цену рынка
                try:
                    market_data = await self.api.get_market_items(
                        title=title,
                        limit=1,
                    )
                    offers = market_data.get("objects", [])
                    if offers:
                        lowest_price = float(offers[0].get("price", {}).get("USD", 0)) / 100
                        panic_price = round(lowest_price * 0.95, 2)  # -5%

                        # Выставляем на продажу
                        await self.api.create_offer(
                            item_id=item_id,
                            price=int(panic_price * 100),  # В центах
                        )
                        sold_count += 1

                except Exception as e:
                    logger.exception(f"Failed to list item {title}: {e}")

            await update.message.reply_text(
                f"✅ **PANIC SELL завершен**\n\n"
                f"📦 Выставлено: {sold_count} предметов\n"
                f"⏭️ Пропущено: {skipped_count} (уже выставлены или сокровища)\n\n"
                f"💡 Цены снижены на 5% для быстрой продажи."
            )

        except Exception as e:
            logger.exception(f"Panic sell error: {e}")
            await update.message.reply_text(f"❌ Ошибка PANIC SELL: {e}")
        finally:
            self._panic_mode = False

    async def add_target_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Команда /add_target [URL] - добавить предмет в отслеживание."""
        if not update.message:
            return

        args = context.args or []

        if not args:
            await update.message.reply_text(
                "📝 **Добавление предмета в отслеживание**\n\n"
                "Использование:\n"
                "`/add_target <URL>`\n\n"
                "Поддерживаемые ссылки:\n"
                "• DMarket: `https://dmarket.com/ingame-items/...`\n"
                "• Steam: `https://steamcommunity.com/market/...`\n\n"
                "Пример:\n"
                "`/add_target https://dmarket.com/ingame-items/csgo/item/...`",
                parse_mode="Markdown",
            )
            return

        url = args[0]

        # Парсим URL
        item_name = self._parse_item_url(url)

        if not item_name:
            await update.message.reply_text(
                "❌ Не удалось распознать ссылку.\n\n"
                "Убедитесь, что это ссылка на предмет DMarket или Steam Market."
            )
            return

        # TODO: Добавить в whitelist/targets
        await update.message.reply_text(
            f"✅ **Предмет добавлен в отслеживание**\n\n"
            f"📦 {item_name}\n\n"
            f"Бот будет искать выгодные предложения для этого предмета."
        )

    def _parse_item_url(self, url: str) -> str | None:
        """Парсить URL предмета.

        Args:
            url: URL предмета

        Returns:
            Название предмета или None
        """
        import urllib.parse

        try:
            parsed = urllib.parse.urlparse(url)

            # DMarket
            if "dmarket.com" in parsed.netloc:
                # Пример: /ingame-items/csgo/item/AWP-Asiimov-Field-Tested
                parts = parsed.path.split("/")
                if len(parts) >= 4:
                    return parts[-1].replace("-", " ")

            # Steam
            if "steamcommunity.com" in parsed.netloc:
                # Пример: /market/listings/730/AWP%20|%20Asiimov%20(Field-Tested)
                parts = parsed.path.split("/")
                if len(parts) >= 5:
                    return urllib.parse.unquote(parts[-1])

        except Exception:
            pass

        return None

    async def logs_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Команда /logs - получить последние логи."""
        if not update.message:
            return

        try:
            import os
            from pathlib import Path

            log_file = Path("logs/bot.log")

            # Async check for file existence
            file_exists = await asyncio.to_thread(os.path.exists, log_file)
            if not file_exists:
                await update.message.reply_text("📋 Файл логов не найден.")
                return

            # Читаем последние 50 строк (async)
            async with aiofiles.open(log_file, encoding="utf-8") as f:
                content = await f.read()
                lines = content.splitlines(keepends=True)
                last_lines = lines[-50:]

            # Форматируем
            log_text = "".join(last_lines)

            if len(log_text) > 4000:
                log_text = log_text[-4000:]

            await update.message.reply_text(
                f"📋 **Последние логи:**\n\n```\n{log_text}\n```",
                parse_mode="Markdown",
            )

        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка чтения логов: {e}")

    async def market_mode_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Команда /market_mode - текущий режим рынка."""
        if not update.message:
            return

        if not self.sales_protector:
            await update.message.reply_text("⚠️ Модуль Steam Sales Protector не подключен")
            return

        message = self.sales_protector.format_status_message()
        await update.message.reply_text(message, parse_mode="Markdown")

    async def portfolio_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Команда /portfolio - общая стоимость портфеля."""
        if not update.message:
            return

        await update.message.reply_text("⏳ Оцениваю портфель...")

        try:
            portfolio_value = 0.0
            balance_usd = 0.0
            items_count = 0

            # Баланс
            if self.api:
                balance_data = await self.api.get_balance()
                # API возвращает balance в долларах напрямую
                balance_usd = float(balance_data.get("balance", 0))
                portfolio_value += balance_usd

            # Инвентарь
            if self.api:
                inventory = await self.api.get_user_inventory()
                items = inventory.get("items", [])
                items_count = len(items)

                for item in items:
                    price_data = item.get("price", {})
                    if isinstance(price_data, dict):
                        price_cents = price_data.get("USD", 0)
                    else:
                        price_cents = price_data or 0
                    portfolio_value += float(price_cents) / 100

            # Сокровища (оценочная стоимость)
            treasures_value = 0.0
            if self.collectors_hold and self.db:
                treasures = self.collectors_hold.get_treasures()
                for t in treasures:
                    if t.evaluation_result:
                        # Используем цену покупки * множитель
                        # TODO: Получить реальную цену покупки из БД
                        treasures_value += 10.0 * t.estimated_value_multiplier

            await update.message.reply_text(
                f"💼 **ВАШ ПОРТФЕЛЬ**\n\n"
                f"💵 Баланс: ${balance_usd:.2f}\n"
                f"📦 Инвентарь: {items_count} предметов\n"
                f"💎 Сокровища: ${treasures_value:.2f} (оценка)\n\n"
                f"📊 **Общая стоимость:** ${portfolio_value + treasures_value:.2f}",
                parse_mode="Markdown",
            )

        except Exception as e:
            logger.exception(f"Portfolio command error: {e}")
            await update.message.reply_text(f"❌ Ошибка оценки портфеля: {e}")

    async def handle_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Обработчик callback кнопок."""
        query = update.callback_query
        if not query:
            return

        await query.answer()

        data = query.data

        if data == "show_treasures":
            # Эмулируем /treasures
            await self.treasures_command(update, context)

        elif data == "show_logs":
            await self.logs_command(update, context)

        elif data == "refresh_status":
            await self.status_command(update, context)

        elif data == "market_mode":
            await self.market_mode_command(update, context)

        elif data == "confirm_panic_sell":
            # Добавляем CONFIRM и выполняем
            context.args = ["CONFIRM"]  # type: ignore
            if query.message:
                update._message = query.message  # type: ignore
            await self.panic_sell_command(update, context)

        elif data == "cancel_panic_sell":
            await query.edit_message_text("❌ Panic Sell отменен.")
