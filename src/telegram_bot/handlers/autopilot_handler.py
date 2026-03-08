"""Autopilot command handlers for Telegram bot.

Implements "One Button" interface:
- /autopilot - Start autonomous trading
- /autopilot_stop - Stop trading
- /autopilot_status - Get current status
- /autopilot_stats - Get detailed statistics

Created: January 2, 2026
"""

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.dmarket.autopilot_orchestrator import AutopilotOrchestrator

logger = structlog.get_logger(__name__)


async def autopilot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /autopilot command - start autonomous trading.

    Usage:
        /autopilot - Start with default settings
        /autopilot custom - Show settings before start
    """
    if not update.message:
        return

    args = context.args

    # Get orchestrator from context
    orchestrator: AutopilotOrchestrator | None = context.bot_data.get("orchestrator")

    if not orchestrator:
        await update.message.reply_text(
            "❌ Автопилот не инициализирован. Перезапустите бота."
        )
        return

    # Check if already running
    if orchestrator.is_active():
        await update.message.reply_text(
            "ℹ️ Автопилот уже работает!\n\n"
            "Для просмотра статуса: /autopilot_status\n"
            "Для остановки: /autopilot_stop"
        )
        return

    # Show settings menu if requested
    if args and args[0].lower() == "custom":
        await show_autopilot_settings(update, context)
        return

    # Start with default settings
    await start_autopilot(update, context, orchestrator)


async def start_autopilot(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    orchestrator: AutopilotOrchestrator,
) -> None:
    """Start autopilot with current settings."""
    user_id = update.effective_user.id

    try:
        # Start orchestrator
        await orchestrator.start(telegram_bot=context.bot, user_id=user_id)

        logger.info("autopilot_started_by_user", user_id=user_id)

    except Exception as e:
        logger.exception("autopilot_start_failed", user_id=user_id, error=str(e))
        await update.message.reply_text(f"❌ Не удалось запустить автопилот: {e!s}")


async def autopilot_stop_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /autopilot_stop command - stop autonomous trading."""
    if not update.message:
        return

    user_id = update.effective_user.id
    orchestrator: AutopilotOrchestrator | None = context.bot_data.get("orchestrator")

    if not orchestrator:
        await update.message.reply_text("❌ Автопилот не инициализирован")
        return

    if not orchestrator.is_active():
        await update.message.reply_text("ℹ️ Автопилот не запущен")
        return

    # Show confirmation message
    await update.message.reply_text(
        "⏳ Останавливаю автопилот...\nЗавершаю текущие операции..."
    )

    try:
        # Stop orchestrator
        await orchestrator.stop()

        logger.info("autopilot_stopped_by_user", user_id=user_id)

    except Exception as e:
        logger.exception("autopilot_stop_failed", user_id=user_id, error=str(e))
        await update.message.reply_text(f"❌ Ошибка при остановке: {e!s}")


async def autopilot_status_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /autopilot_status command - show current status."""
    if not update.message:
        return

    orchestrator: AutopilotOrchestrator | None = context.bot_data.get("orchestrator")

    if not orchestrator:
        await update.message.reply_text("❌ Автопилот не инициализирован")
        return

    # Get current status
    is_active = orchestrator.is_active()
    stats = orchestrator.get_stats()

    if not is_active:
        await update.message.reply_text(
            "⏸️ <b>Автопилот остановлен</b>\n\nДля запуска: /autopilot",
            parse_mode=ParseMode.HTML,
        )
        return

    # Format status message
    status_emoji = "🟢" if is_active else "🔴"
    buyer_status = "✅" if orchestrator.buyer.config.enabled else "❌"
    seller_status = "✅" if getattr(orchestrator.seller, "enabled", False) else "❌"

    message = (
        f"{status_emoji} <b>Автопилот активен</b>\n\n"
        f"⏱️ Работает: {stats['uptime_minutes']} минут\n\n"
        f"<b>Подсистемы:</b>\n"
        f"{buyer_status} Автопокупка\n"
        f"{seller_status} Автопродажа\n"
        f"✅ Сканирование\n\n"
        f"<b>Быстрая статистика:</b>\n"
        f"• Куплено: {stats['purchases']}\n"
        f"• Продано: {stats['sales']}\n"
        f"• Прибыль: ${stats['net_profit_usd']:.2f}\n\n"
        f"Для детальной статистики: /autopilot_stats\n"
        f"Для остановки: /autopilot_stop"
    )

    await update.message.reply_text(message, parse_mode=ParseMode.HTML)


async def autopilot_stats_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /autopilot_stats command - show detailed statistics."""
    if not update.message:
        return

    orchestrator: AutopilotOrchestrator | None = context.bot_data.get("orchestrator")

    if not orchestrator:
        await update.message.reply_text("❌ Автопилот не инициализирован")
        return

    stats = orchestrator.get_stats()

    # Calculate additional metrics
    success_rate = 0.0
    if stats["purchases"] > 0:
        success_rate = (
            stats["purchases"] / (stats["purchases"] + stats["failed_purchases"]) * 100
        )

    message = (
        f"📊 <b>Детальная статистика автопилота</b>\n\n"
        f"⏱️ <b>Время работы:</b> {stats['uptime_minutes']} минут "
        f"({stats['uptime_minutes'] / 60:.1f} часов)\n\n"
        f"<b>💰 Покупки:</b>\n"
        f"• Успешных: {stats['purchases']}\n"
        f"• Неудачных: {stats['failed_purchases']}\n"
        f"• Успешность: {success_rate:.1f}%\n"
        f"• Потрачено: ${stats['total_spent_usd']:.2f}\n\n"
        f"<b>💵 Продажи:</b>\n"
        f"• Успешных: {stats['sales']}\n"
        f"• Неудачных: {stats['failed_sales']}\n"
        f"• Выручка: ${stats['total_earned_usd']:.2f}\n\n"
        f"<b>📈 Итого:</b>\n"
        f"• Чистая прибыль: ${stats['net_profit_usd']:.2f}\n"
        f"• ROI: {stats['roi_percent']:.2f}%\n"
        f"• Средний чек: ${stats['total_spent_usd'] / max(stats['purchases'], 1):.2f}\n\n"
        f"<b>🔍 Возможности:</b>\n"
        f"• Найдено: {stats['opportunities_found']}\n"
        f"• Использовано: {stats['opportunities_found'] - stats['opportunities_skipped']}\n"
        f"• Пропущено: {stats['opportunities_skipped']}\n"
        f"• Конверсия: "
        f"{(stats['opportunities_found'] - stats['opportunities_skipped']) / max(stats['opportunities_found'], 1) * 100:.1f}%\n\n"
        f"<b>💳 Баланс:</b>\n"
        f"• Проверок: {stats['balance_checks']}\n"
        f"• Предупреждений: {stats['low_balance_warnings']}"
    )

    await update.message.reply_text(message, parse_mode=ParseMode.HTML)


async def show_autopilot_settings(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show autopilot settings menu with inline keyboard."""
    orchestrator: AutopilotOrchestrator | None = context.bot_data.get("orchestrator")

    if not orchestrator:
        await update.message.reply_text("❌ Автопилот не инициализирован")
        return

    config = orchestrator.config

    keyboard = [
        [
            InlineKeyboardButton(
                f"Игры: {', '.join(config.games).upper()}",
                callback_data="autopilot_set_games",
            )
        ],
        [
            InlineKeyboardButton(
                f"Мин. скидка: {config.min_discount_percent}%",
                callback_data="autopilot_set_discount",
            )
        ],
        [
            InlineKeyboardButton(
                f"Макс. цена: ${config.max_price_usd:.0f}",
                callback_data="autopilot_set_maxprice",
            )
        ],
        [
            InlineKeyboardButton(
                f"Наценка продажи: {config.auto_sell_markup_percent}%",
                callback_data="autopilot_set_markup",
            )
        ],
        [
            InlineKeyboardButton(
                "🚀 Запустить с этими настSwarmками",
                callback_data="autopilot_start_confirmed",
            )
        ],
        [InlineKeyboardButton("◀️ Отмена", callback_data="main_menu")],
    ]

    await update.message.reply_text(
        "⚙️ <b>НастSwarmки автопилота</b>\n\n"
        f"Текущие параметры:\n"
        f"• Игры: {', '.join(config.games).upper()}\n"
        f"• Мин. скидка: {config.min_discount_percent}%\n"
        f"• Макс. цена: ${config.max_price_usd:.2f}\n"
        f"• Наценка продажи: +{config.auto_sell_markup_percent}%\n"
        f"• Мин. баланс: ${config.min_balance_threshold_usd:.2f}\n\n"
        "Нажмите параметр для изменения или запустите:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
    )


async def autopilot_start_confirmed_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle confirmed autopilot start from settings."""
    query = update.callback_query
    await query.answer()

    orchestrator: AutopilotOrchestrator | None = context.bot_data.get("orchestrator")

    if not orchestrator:
        await query.edit_message_text("❌ Автопилот не инициализирован")
        return

    if orchestrator.is_active():
        await query.edit_message_text(
            "ℹ️ Автопилот уже работает!\n\nДля остановки: /autopilot_stop"
        )
        return

    # Show starting message
    await query.edit_message_text("⏳ Запускаю автопилот...")

    try:
        # Start orchestrator
        await orchestrator.start(
            telegram_bot=context.bot, user_id=update.effective_user.id
        )

        logger.info("autopilot_started_from_settings", user_id=update.effective_user.id)

    except Exception as e:
        logger.exception(
            "autopilot_start_failed", user_id=update.effective_user.id, error=str(e)
        )
        await query.edit_message_text(f"❌ Не удалось запустить: {e!s}")


# Export handlers
__all__ = [
    "autopilot_command",
    "autopilot_start_confirmed_callback",
    "autopilot_stats_command",
    "autopilot_status_command",
    "autopilot_stop_command",
    "show_autopilot_settings",
]
