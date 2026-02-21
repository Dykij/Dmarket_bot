"""Modular main keyboard handler for DMarket Bot."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.telegram_bot.handlers.keyboard_parts.info import show_balance, show_inventory
from src.telegram_bot.handlers.keyboard_parts.ml_ai import (
    ml_ai_menu_callback,
    ml_ai_status_callback,
)
from src.telegram_bot.handlers.keyboard_parts.targets import (
    target_auto,
    target_create,
    targets_menu,
)
from src.telegram_bot.handlers.trading_handlers import (
    auto_trade_run,
    auto_trade_start,
    auto_trade_stop,
)
from src.utils.canonical_logging import get_logger

logger = get_logger(__name__)


def get_main_keyboard(balance: float | None = None) -> InlineKeyboardMarkup:
    balance_text = f"💰 ${balance:.2f}" if balance else "💰 Баланс"
    keyboard = [
        [InlineKeyboardButton("🤖 АВТО-ТОРГОВЛЯ", callback_data="auto_trade_start")],
        [InlineKeyboardButton("🎯 ТАРГЕТЫ", callback_data="targets_menu")],
        [InlineKeyboardButton("🧠 ML/AI ОБУЧЕНИЕ", callback_data="ml_ai_menu")],
        [
            InlineKeyboardButton(balance_text, callback_data="show_balance"),
            InlineKeyboardButton("📦 Инвентарь", callback_data="show_inventory"),
        ],
        [InlineKeyboardButton("🖥️ СИСТЕМА", callback_data="system_status")],
        [
            InlineKeyboardButton(
                "🛑 ЭКСТРЕННАЯ ОСТАНОВКА", callback_data="emergency_stop"
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\nВыберите действие:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard(),
    )


async def main_menu_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "👋 <b>Главное меню</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard(),
    )


async def emergency_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("⚠️ ЭКСТРЕННАЯ ОСТАНОВКА!")
    await query.edit_message_text(
        "🛑 Все процессы остановлены.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]]
        ),
    )


def register_main_keyboard_handlers(application) -> None:
    from telegram.ext import CallbackQueryHandler, CommandHandler

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(
        CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
    )
    application.add_handler(
        CallbackQueryHandler(auto_trade_start, pattern="^auto_trade_start$")
    )
    application.add_handler(
        CallbackQueryHandler(auto_trade_run, pattern="^auto_trade_run$")
    )
    application.add_handler(
        CallbackQueryHandler(auto_trade_stop, pattern="^auto_trade_stop$")
    )
    application.add_handler(
        CallbackQueryHandler(targets_menu, pattern="^targets_menu$")
    )
    application.add_handler(
        CallbackQueryHandler(target_create, pattern="^target_create$")
    )
    application.add_handler(CallbackQueryHandler(target_auto, pattern="^target_auto$"))
    application.add_handler(
        CallbackQueryHandler(ml_ai_menu_callback, pattern="^ml_ai_menu$")
    )
    application.add_handler(
        CallbackQueryHandler(ml_ai_status_callback, pattern="^ml_ai_status$")
    )
    application.add_handler(
        CallbackQueryHandler(show_balance, pattern="^show_balance$")
    )
    application.add_handler(
        CallbackQueryHandler(show_inventory, pattern="^show_inventory$")
    )
    application.add_handler(
        CallbackQueryHandler(emergency_stop, pattern="^emergency_stop$")
    )
    logger.info("✅ Modular main keyboard handlers registered")
