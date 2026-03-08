"""Auto-trading and scanning handlers."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.utils.canonical_logging import get_logger

logger = get_logger(__name__)


def _get_dmarket_api(context: ContextTypes.DEFAULT_TYPE):
    return getattr(context.application, "dmarket_api", None)


def _get_auto_buyer(context: ContextTypes.DEFAULT_TYPE):
    return getattr(context.application, "auto_buyer", None)


def _get_orchestrator(context: ContextTypes.DEFAULT_TYPE):
    return getattr(context.application, "orchestrator", None)


async def auto_trade_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    is_running = context.bot_data.get("auto_trade_running", False)
    if is_running:
        keyboard = [
            [
                InlineKeyboardButton(
                    "🛑 Остановить торговлю", callback_data="auto_trade_stop"
                )
            ],
            [InlineKeyboardButton("📊 Статус", callback_data="auto_trade_status")],
            [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")],
        ]
        await query.edit_message_text(
            "🤖 🟢 <b>Статус: РАБОТАЕТ</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        keyboard = [
            [InlineKeyboardButton("🚀 ЗАПУСТИТЬ", callback_data="auto_trade_run")],
            [
                InlineKeyboardButton(
                    "🔎 СКАНИРОВАТЬ ВСЁ", callback_data="auto_trade_scan_all"
                )
            ],
            [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")],
        ]
        await query.edit_message_text(
            "🤖 🔴 <b>Статус: ОСТАНОВЛЕНА</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def auto_trade_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Запуск...")
    context.bot_data["auto_trade_running"] = True
    await query.edit_message_text(
        "✅ Авто-торговля запущена!",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("◀️ Назад", callback_data="auto_trade_start")]]
        ),
    )


async def auto_trade_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Остановка...")
    context.bot_data["auto_trade_running"] = False
    await query.edit_message_text(
        "🛑 Торговля остановлена.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("◀️ Назад", callback_data="auto_trade_start")]]
        ),
    )
