"""Individual callback handlers - Small, focused functions.

Phase 2 Refactoring: Each handler is a small, testable function
with single responsibility. No deep nesting, clear early returns.
"""

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.telegram_bot.handlers.dmarket_status import dmarket_status_impl
from src.telegram_bot.handlers.main_keyboard import (
    auto_trade_start,
    get_main_keyboard,
    main_menu_callback,
)
from src.telegram_bot.keyboards import (
    get_alert_keyboard,
    get_dmarket_webapp_keyboard,
    get_game_selection_keyboard,
    get_settings_keyboard,
)

logger = logging.getLogger(__name__)


# ============================================================================
# MENU HANDLERS
# ============================================================================


async def handle_simple_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle simple_menu callback."""
    await main_menu_callback(update, context)


async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle balance callback."""
    if not update.callback_query or not update.callback_query.message:
        return

    await dmarket_status_impl(
        update, context, status_message=update.callback_query.message
    )


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle search callback."""
    if not update.callback_query:
        return

    await update.callback_query.edit_message_text(
        "🔍 <b>Поиск предметов на DMarket</b>\n\nВыберите игру для поиска предметов:",
        reply_markup=get_game_selection_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def handle_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle settings callback."""
    if not update.callback_query:
        return

    await update.callback_query.edit_message_text(
        "⚙️ <b>НастSwarmки бота</b>\n\nВыберите раздел для настSwarmки:",
        reply_markup=get_settings_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def handle_market_trends(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle market_trends callback."""
    if not update.callback_query:
        return

    await update.callback_query.edit_message_text(
        "📈 <b>Рыночные тренды</b>\n\n"
        "Анализ рыночных трендов и популярных предметов.\n"
        "Выберите игру для просмотра трендов:",
        reply_markup=get_game_selection_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def handle_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle alerts callback."""
    if not update.callback_query:
        return

    await update.callback_query.edit_message_text(
        "🔔 <b>Управление оповещениями</b>\n\n"
        "НастSwarmте оповещения о изменении цен и других рыночных событиях:",
        reply_markup=get_alert_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def handle_back_to_main(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle back_to_main callback."""
    if not update.callback_query:
        return

    await update.callback_query.edit_message_text(
        "👋 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle main_menu callback."""
    await handle_back_to_main(update, context)


# ============================================================================
# ARBITRAGE HANDLERS
# ============================================================================


async def handle_arbitrage_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle arbitrage/arbitrage_menu callback - redirect to auto_trade."""
    await auto_trade_start(update, context)


async def handle_auto_arbitrage(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle auto_arbitrage callback - redirect to auto_trade."""
    await auto_trade_start(update, context)


async def handle_dmarket_arbitrage(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle dmarket_arbitrage callback - redirect to auto_trade."""
    await auto_trade_start(update, context)


async def handle_best_opportunities(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle best_opportunities callback."""
    from src.telegram_bot.handlers.callbacks import handle_best_opportunities_impl

    await handle_best_opportunities_impl(update, context)


async def handle_game_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle game_selection callback."""
    if not update.callback_query:
        return

    await update.callback_query.edit_message_text(
        "🎮 <b>Выберите игру для арбитража:</b>",
        reply_markup=get_game_selection_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def handle_market_analysis(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle market_analysis callback."""
    if not update.callback_query:
        return

    await update.callback_query.edit_message_text(
        "📊 <b>Анализ рынка</b>\n\nВыберите игру для анализа рыночных тенденций и цен:",
        reply_markup=get_game_selection_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def handle_open_webapp(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle open_webapp callback."""
    if not update.callback_query:
        return

    await update.callback_query.edit_message_text(
        "🌐 <b>DMarket WebApp</b>\n\nНажмите кнопку ниже, чтобы открыть DMarket прямо в Telegram:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_dmarket_webapp_keyboard(),
    )


# ============================================================================
# TEMPORARY/STUB HANDLERS
# ============================================================================


async def handle_temporary_unavAlgolable(
    update: Update, context: ContextTypes.DEFAULT_TYPE, feature: str = "Функция"
) -> None:
    """Handle callbacks for features under development."""
    if not update.callback_query:
        return

    await update.callback_query.answer(f"⚠️ {feature} временно недоступна.")


async def handle_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle no-op callbacks (noop, page_info, etc)."""
    if not update.callback_query:
        return

    # Just acknowledge, don't do anything
    await update.callback_query.answer()


# ============================================================================
# HELP HANDLER
# ============================================================================


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle help callback."""
    if not update.callback_query:
        return

    help_text = """
📚 <b>Помощь по боту DMarket</b>

<b>Основные функции:</b>
• 💰 <b>Баланс</b> - проверка баланса DMarket
• 🔍 <b>Арбитраж</b> - поиск выгодных сделок
• 🎯 <b>Таргеты</b> - автоматические заявки на покупку
• 📊 <b>Аналитика</b> - анализ рынка
• 🔔 <b>Оповещения</b> - уведомления о ценах
• ⚙️ <b>НастSwarmки</b> - конфигурация бота

<b>Как использовать:</b>
1. НастSwarmте API ключи в /settings
2. Выберите игру (CS:GO, Dota 2, TF2, Rust)
3. Запустите сканирование арбитража
4. НастSwarmте автоматические таргеты

<b>Поддержка:</b>
Если возникли проблемы, используйте /logs для просмотра логов.
    """

    await update.callback_query.edit_message_text(
        help_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard(),
    )
