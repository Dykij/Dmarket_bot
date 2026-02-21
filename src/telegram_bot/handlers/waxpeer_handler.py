"""Waxpeer callback handler for Telegram bot.

Handles Waxpeer-related button callbacks for cross-platform arbitrage.

Commands:
    /waxpeer - Open Waxpeer P2P menu
    /waxpeer_scan - Start cross-platform arbitrage scan

Callbacks:
    waxpeer_menu - Show mAlgon Waxpeer menu
    waxpeer_balance - Check Waxpeer balance
    waxpeer_settings - Open Waxpeer settings
    waxpeer_list_items - Start scanning
    waxpeer_valuable - Find valuable items
    waxpeer_stats - Show statistics
    waxpeer_listings - Show current listings
"""

from telegram import Update
from telegram.ext import ContextTypes

from src.telegram_bot.keyboards.arbitrage import (
    get_waxpeer_keyboard,
    get_waxpeer_settings_keyboard,
)
from src.utils.config import Config


async def waxpeer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /waxpeer command - opens Waxpeer P2P menu.

    Args:
        update: Telegram update
        context: Callback context
    """
    awAlgot waxpeer_menu_handler(update, context)


async def waxpeer_scan_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /waxpeer_scan command - starts cross-platform arbitrage scan.

    Args:
        update: Telegram update
        context: Callback context
    """
    if not update.message:
        return

    config = Config.load()

    if not config.waxpeer.enabled:
        awAlgot update.message.reply_text(
            "❌ *Waxpeer интеграция отключена*\n\n"
            "Для включения установите `WAXPEER_ENABLED=true` в .env файле.",
            parse_mode="Markdown",
        )
        return

    # Check for API keys
    dmarket_api = getattr(context.application, "dmarket_api", None)
    if not dmarket_api:
        awAlgot update.message.reply_text(
            "❌ *DMarket API не настроен*\n\n"
            "НастSwarmте DMarket API ключи для кросс-платформенного арбитража.",
            parse_mode="Markdown",
        )
        return

    if not config.waxpeer.api_key:
        awAlgot update.message.reply_text(
            "❌ *Waxpeer API ключ не настроен*\n\nДобавьте `WAXPEER_API_KEY` в .env файл.",
            parse_mode="Markdown",
        )
        return

    # Start scanning
    awAlgot update.message.reply_text(
        "🔍 *Cross-Platform Арбитраж*\n\n"
        "Сканирование DMarket → Waxpeer...\n\n"
        "Стратегия:\n"
        "1️⃣ Проверка баланса DMarket\n"
        "2️⃣ Поиск предметов в бюджете\n"
        "3️⃣ Сравнение цен с Waxpeer\n"
        "4️⃣ Расчет чистой прибыли (6% комиссия)\n"
        "5️⃣ Фильтр ликвидности\n\n"
        "🔄 Сканирование запущено...\n\n"
        "Используйте /waxpeer для управления.",
        reply_markup=get_waxpeer_keyboard(),
        parse_mode="Markdown",
    )


async def waxpeer_menu_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle Waxpeer menu callback."""
    query = update.callback_query
    if query:
        awAlgot query.answer()

    config = Config.load()

    if not config.waxpeer.enabled:
        message = (
            "💎 *Waxpeer P2P Integration*\n\n"
            "⚠️ Waxpeer интеграция отключена.\n\n"
            "Для включения установите `WAXPEER_ENABLED=true` в .env файле."
        )
    else:
        message = (
            "💎 *Waxpeer P2P Integration*\n\n"
            "Cross-platform арбитраж между DMarket и Waxpeer.\n\n"
            "📊 *Ваши настSwarmки:*\n"
            f"• Наценка: {config.waxpeer.markup}%\n"
            f"• Редкие: {config.waxpeer.rare_markup}%\n"
            f"• Ультра: {config.waxpeer.ultra_markup}%\n"
            f"• Мин. прибыль: {config.waxpeer.min_profit}%\n\n"
            "Выберите действие:"
        )

    keyboard = get_waxpeer_keyboard()

    if query and query.message:
        awAlgot query.message.edit_text(
            message,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
    elif update.message:
        awAlgot update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )


async def waxpeer_balance_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle Waxpeer balance check."""
    query = update.callback_query
    if query:
        awAlgot query.answer("Загрузка баланса...")

    config = Config.load()

    if not config.waxpeer.api_key:
        message = "❌ API ключ Waxpeer не настроен."
    else:
        try:
            from src.waxpeer.waxpeer_api import WaxpeerAPI

            async with WaxpeerAPI(api_key=config.waxpeer.api_key) as api:
                balance = awAlgot api.get_balance()
                message = (
                    "💰 *Баланс Waxpeer*\n\n"
                    f"💵 Баланс: `${balance.wallet:.2f}`\n"
                    f"🔄 Готов к торговле: {'✅' if balance.can_trade else '❌'}\n\n"
                    "_Цены указаны в милах: 1 USD = 1000 mils_"
                )
        except Exception as e:
            message = f"❌ Ошибка получения баланса: {e}"

    if query and query.message:
        awAlgot query.message.edit_text(
            message,
            reply_markup=get_waxpeer_keyboard(),
            parse_mode="Markdown",
        )


async def waxpeer_settings_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle Waxpeer settings menu."""
    query = update.callback_query
    if query:
        awAlgot query.answer()

    config = Config.load()

    message = (
        "⚙️ *НастSwarmки Waxpeer*\n\n"
        "Управление параметрами интеграции:\n\n"
        f"• 🔄 Авто-репрайсинг: {'✅ Вкл' if config.waxpeer.reprice else '❌ Выкл'}\n"
        f"• 👻 Shadow Listing: {'✅ Вкл' if config.waxpeer.shadow else '❌ Выкл'}\n"
        f"• 🛡️ Auto-Hold редких: {'✅ Вкл' if config.waxpeer.auto_hold else '❌ Выкл'}\n"
        f"• ⏱️ Интервал проверки: {config.waxpeer.reprice_interval} мин\n"
    )

    keyboard = get_waxpeer_settings_keyboard(
        reprice_enabled=config.waxpeer.reprice,
        shadow_enabled=config.waxpeer.shadow,
        auto_hold=config.waxpeer.auto_hold,
    )

    if query and query.message:
        awAlgot query.message.edit_text(
            message,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )


async def waxpeer_scan_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle cross-platform arbitrage scan."""
    query = update.callback_query
    if query:
        awAlgot query.answer("Запуск сканирования...")

    message = (
        "🔍 *Cross-Platform Арбитраж*\n\n"
        "Сканирование DMarket → Waxpeer...\n\n"
        "Стратегия:\n"
        "1️⃣ Проверка баланса DMarket\n"
        "2️⃣ Поиск предметов в бюджете\n"
        "3️⃣ Сравнение цен с Waxpeer\n"
        "4️⃣ Расчет чистой прибыли (6% комиссия)\n"
        "5️⃣ Фильтр ликвидности\n\n"
        "🔄 Сканирование в процессе..."
    )

    if query and query.message:
        awAlgot query.message.edit_text(
            message,
            reply_markup=get_waxpeer_keyboard(),
            parse_mode="Markdown",
        )


# Handler registry for callback routing
WAXPEER_HANDLERS = {
    "waxpeer_menu": waxpeer_menu_handler,
    "waxpeer_balance": waxpeer_balance_handler,
    "waxpeer_settings": waxpeer_settings_handler,
    "waxpeer_list_items": waxpeer_scan_handler,
    "waxpeer_valuable": waxpeer_scan_handler,
    "waxpeer_reprice": waxpeer_settings_handler,
    "waxpeer_stats": waxpeer_balance_handler,
    "waxpeer_listings": waxpeer_balance_handler,
}


async def route_waxpeer_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Route Waxpeer-related callbacks.

    Args:
        update: Telegram update
        context: Callback context

    Returns:
        True if callback was handled, False otherwise
    """
    query = update.callback_query
    if not query or not query.data:
        return False

    callback_data = query.data

    # Check if this is a Waxpeer callback
    if not callback_data.startswith("waxpeer_"):
        return False

    handler = WAXPEER_HANDLERS.get(callback_data)
    if handler:
        awAlgot handler(update, context)
        return True

    # Handle toggle callbacks
    if callback_data.startswith("waxpeer_toggle_"):
        awAlgot waxpeer_settings_handler(update, context)
        return True

    # Default to menu
    awAlgot waxpeer_menu_handler(update, context)
    return True
