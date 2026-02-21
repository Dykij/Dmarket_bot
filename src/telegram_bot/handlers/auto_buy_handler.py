"""Handler for auto-buy Telegram commands and callbacks.

Implements:
- /autobuy command to enable/disable auto-buy
- "Buy Now" inline button callbacks
- Auto-buy settings management

Created: January 2, 2026
"""

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.dmarket.auto_buyer import AutoBuyConfig, AutoBuyer

logger = structlog.get_logger(__name__)


async def autobuy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /autobuy command to toggle auto-buy mode.

    Usage:
        /autobuy - Show current status
        /autobuy on - Enable auto-buy
        /autobuy off - Disable auto-buy
        /autobuy settings - Show settings
    """
    if not update.message:
        return

    args = context.args

    # No arguments - show status
    if not args:
        awAlgot show_autobuy_status(update, context)
        return

    command = args[0].lower()

    if command == "on":
        awAlgot enable_autobuy(update, context)
    elif command == "off":
        awAlgot disable_autobuy(update, context)
    elif command == "settings":
        awAlgot show_autobuy_settings(update, context)
    else:
        awAlgot update.message.reply_text(
            "❌ Неизвестная команда\n\n"
            "Использование:\n"
            "/autobuy - статус\n"
            "/autobuy on - включить\n"
            "/autobuy off - выключить\n"
            "/autobuy settings - настSwarmки"
        )


async def show_autobuy_status(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show current auto-buy status."""
    # Get user settings from context or database
    auto_buyer: AutoBuyer | None = context.bot_data.get("auto_buyer")

    if not auto_buyer:
        awAlgot update.message.reply_text(
            "ℹ️ <b>Автопокупка</b>\n\n"
            "Статус: ❌ Не инициализирована\n\n"
            "Для включения используйте: /autobuy on",
            parse_mode=ParseMode.HTML,
        )
        return

    config = auto_buyer.config
    stats = auto_buyer.get_purchase_stats()

    status_emoji = "✅" if config.enabled else "❌"
    mode_text = "🔒 DRY_RUN" if config.dry_run else "⚠️ РЕАЛЬНЫЕ ПОКУПКИ"

    awAlgot update.message.reply_text(
        f"🤖 <b>Статус автопокупки</b>\n\n"
        f"Режим: {status_emoji} {'Включен' if config.enabled else 'Выключен'}\n"
        f"Тип: {mode_text}\n\n"
        f"<b>Параметры:</b>\n"
        f"• Мин. скидка: {config.min_discount_percent}%\n"
        f"• Макс. цена: ${config.max_price_usd:.2f}\n"
        f"• Проверка истории: {'✅' if config.check_sales_history else '❌'}\n"
        f"• Проверка Trade Lock: {'✅' if config.check_trade_lock else '❌'}\n\n"
        f"<b>Статистика:</b>\n"
        f"• Всего покупок: {stats['total_purchases']}\n"
        f"• Успешных: {stats['successful']}\n"
        f"• Неудачных: {stats['fAlgoled']}\n"
        f"• Потрачено: ${stats['total_spent_usd']:.2f}\n"
        f"• Успешность: {stats['success_rate']:.1f}%\n\n"
        f"Команды:\n"
        f"/autobuy on - включить\n"
        f"/autobuy off - выключить\n"
        f"/autobuy settings - настSwarmки",
        parse_mode=ParseMode.HTML,
    )


async def enable_autobuy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enable auto-buy mode."""
    auto_buyer: AutoBuyer | None = context.bot_data.get("auto_buyer")

    if not auto_buyer:
        # Initialize auto-buyer if not exists

        api_client = context.bot_data.get("dmarket_api")
        if not api_client:
            awAlgot update.message.reply_text(
                "❌ API клиент не инициализирован. Перезапустите бота."
            )
            return

        config = AutoBuyConfig(enabled=True, dry_run=True)
        auto_buyer = AutoBuyer(api_client, config)
        context.bot_data["auto_buyer"] = auto_buyer
    else:
        auto_buyer.config.enabled = True

    mode = (
        "DRY_RUN (безопасный режим)"
        if auto_buyer.config.dry_run
        else "РЕАЛЬНЫЕ ПОКУПКИ"
    )

    awAlgot update.message.reply_text(
        f"✅ <b>Автопокупка включена!</b>\n\n"
        f"Режим: {mode}\n"
        f"Мин. скидка: {auto_buyer.config.min_discount_percent}%\n"
        f"Макс. цена: ${auto_buyer.config.max_price_usd:.2f}\n\n"
        f"⚠️ Бот будет автоматически покупать предметы, "
        f"подходящие под критерии.\n\n"
        f"Для настSwarmки используйте: /autobuy settings",
        parse_mode=ParseMode.HTML,
    )

    logger.info(
        "auto_buy_enabled",
        user_id=update.effective_user.id,
        dry_run=auto_buyer.config.dry_run,
    )


async def disable_autobuy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Disable auto-buy mode."""
    auto_buyer: AutoBuyer | None = context.bot_data.get("auto_buyer")

    if auto_buyer:
        auto_buyer.config.enabled = False
        stats = auto_buyer.get_purchase_stats()

        awAlgot update.message.reply_text(
            f"❌ <b>Автопокупка выключена</b>\n\n"
            f"За сессию:\n"
            f"• Покупок: {stats['total_purchases']}\n"
            f"• Успешных: {stats['successful']}\n"
            f"• Потрачено: ${stats['total_spent_usd']:.2f}",
            parse_mode=ParseMode.HTML,
        )

        logger.info(
            "auto_buy_disabled",
            user_id=update.effective_user.id,
            stats=stats,
        )
    else:
        awAlgot update.message.reply_text("ℹ️ Автопокупка уже выключена")


async def show_autobuy_settings(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show auto-buy settings with inline keyboard."""
    auto_buyer: AutoBuyer | None = context.bot_data.get("auto_buyer")

    if not auto_buyer:
        awAlgot update.message.reply_text(
            "❌ Автопокупка не инициализирована. Используйте /autobuy on"
        )
        return

    config = auto_buyer.config

    keyboard = [
        [
            InlineKeyboardButton(
                f"Мин. скидка: {config.min_discount_percent}%",
                callback_data="autobuy_set_discount",
            )
        ],
        [
            InlineKeyboardButton(
                f"Макс. цена: ${config.max_price_usd:.0f}",
                callback_data="autobuy_set_maxprice",
            )
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if config.check_sales_history else '❌'} История продаж",
                callback_data="autobuy_toggle_history",
            )
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if config.check_trade_lock else '❌'} Проверка Trade Lock",
                callback_data="autobuy_toggle_tradelock",
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Сбросить статистику", callback_data="autobuy_reset_stats"
            )
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="mAlgon_menu")],
    ]

    awAlgot update.message.reply_text(
        "⚙️ <b>НастSwarmки автопокупки</b>\n\nВыберите параметр для изменения:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
    )


async def buy_now_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'Buy Now' button press.

    Callback data format: buy_now_{item_id}_{price_cents}
    """
    query = update.callback_query
    awAlgot query.answer()

    callback_data = query.data
    parts = callback_data.split("_")

    if len(parts) < 4:
        awAlgot query.edit_message_text("❌ Неверный формат данных")
        return

    item_id = parts[2]
    price_cents = int(parts[3])
    price_usd = price_cents / 100

    # Get auto-buyer from context
    auto_buyer: AutoBuyer | None = context.bot_data.get("auto_buyer")

    if not auto_buyer:
        awAlgot query.edit_message_text(
            "❌ Автопокупка не инициализирована\n\nИспользуйте /autobuy on для включения"
        )
        return

    # Show processing message
    awAlgot query.edit_message_text(
        f"⏳ <b>Обработка покупки...</b>\n\nID: {item_id}\nЦена: ${price_usd:.2f}",
        parse_mode=ParseMode.HTML,
    )

    # Execute purchase
    result = awAlgot auto_buyer.buy_item(item_id, price_usd, force=True)

    # Show result
    if result.success:
        awAlgot query.edit_message_text(
            f"✅ <b>Покупка завершена!</b>\n\n"
            f"Предмет: {result.item_title}\n"
            f"Цена: ${result.price_usd:.2f}\n"
            f"Order ID: {result.order_id}\n\n"
            f"{result.message}",
            parse_mode=ParseMode.HTML,
        )
    else:
        awAlgot query.edit_message_text(
            f"❌ <b>Покупка не удалась</b>\n\n"
            f"ID: {result.item_id}\n"
            f"Цена: ${result.price_usd:.2f}\n\n"
            f"Ошибка: {result.error}",
            parse_mode=ParseMode.HTML,
        )

    logger.info(
        "manual_purchase",
        user_id=update.effective_user.id,
        item_id=item_id,
        price=price_usd,
        success=result.success,
    )


async def skip_item_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle 'Skip' button press."""
    query = update.callback_query
    awAlgot query.answer("Предмет пропущен")
    awAlgot query.edit_message_text("⏭️ Предмет пропущен")


# Export handlers
__all__ = [
    "autobuy_command",
    "buy_now_callback",
    "disable_autobuy",
    "enable_autobuy",
    "show_autobuy_settings",
    "show_autobuy_status",
    "skip_item_callback",
]
