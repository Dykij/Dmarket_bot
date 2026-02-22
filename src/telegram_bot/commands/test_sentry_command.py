"""Команда для тестирования интеграции с Sentry.

Эта команда позволяет администраторам тестировать различные сценарии ошибок
и проверять корректность отправки breadcrumbs в Sentry.

ВАЖНО: Эта команда доступна только в режиме DEBUG или для администраторов.
"""

import logging

import sentry_sdk
from telegram import Update
from telegram.ext import ContextTypes

from src.utils.canonical_logging import BotLogger
from src.utils.config import Config
from src.utils.sentry_breadcrumbs import (
    add_api_breadcrumb,
    add_command_breadcrumb,
    add_error_breadcrumb,
    add_trading_breadcrumb,
    set_user_context,
)

logger = logging.getLogger(__name__)
bot_logger = BotLogger(__name__)


async def test_sentry_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Тестирование интеграции с Sentry.

    Команда: /test_sentry [тип_теста]

    Доступные тесты:
    - breadcrumbs: Тест breadcrumbs
    - error: Тест отправки ошибки
    - api_error: Тест ошибки API
    - division: Тест деления на ноль
    - all: Все тесты

    Args:
        update: Telegram Update объект
        context: Telegram Context объект

    """
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    username = update.effective_user.username

    # Проверка прав доступа
    config = Config.load()
    if not config.debug and user_id not in config.security.admin_users:
        await update.message.reply_text(
            "❌ Эта команда доступна только администраторам в production режиме"
        )
        return

    # Добавить breadcrumb для команды
    add_command_breadcrumb(
        command="test_sentry",
        user_id=user_id,
        username=username,
        chat_id=update.effective_chat.id if update.effective_chat else None,
    )

    # Установить контекст пользователя
    set_user_context(user_id=user_id, username=username, role="tester")

    # Получить тип теста
    test_type = "all"
    if context.args and len(context.args) > 0:
        test_type = context.args[0].lower()

    await update.message.reply_text(f"🧪 Запуск Sentry тестов: {test_type}")

    try:
        if test_type in {"breadcrumbs", "all"}:
            await _test_breadcrumbs(update, user_id)

        if test_type in {"error", "all"}:
            await _test_simple_error(update)

        if test_type in {"api_error", "all"}:
            await _test_api_error(update, user_id)

        if test_type in {"division", "all"}:
            await _test_division_error(update)

        if test_type == "all":
            await update.message.reply_text(
                "✅ Все тесты Sentry выполнены!\n\n"
                "Проверьте Sentry dashboard:\n"
                "https://sentry.io/issues/\n\n"
                "В разделе Breadcrumbs должны быть:\n"
                "• telegram: Bot command\n"
                "• trading: Trading action\n"
                "• http: API request\n"
                "• error: Error details"
            )

    except Exception as e:
        logger.exception("Error during Sentry test")
        await update.message.reply_text(f"❌ Ошибка теста: {e}")


async def _test_breadcrumbs(update: Update, user_id: int) -> None:
    """Тест различных типов breadcrumbs.

    Args:
        update: Telegram Update объект
        user_id: ID пользователя

    """
    # 1. Trading breadcrumb
    add_trading_breadcrumb(
        action="arbitrage_scan_started",
        game="csgo",
        level="standard",
        user_id=user_id,
        balance=100.50,
        item_count=50,
    )

    # 2. API breadcrumb - начало запроса
    add_api_breadcrumb(
        endpoint="/marketplace-api/v1/items",
        method="GET",
        retry=0,
        game="csgo",
    )

    # Симуляция задержки API
    import asyncio

    await asyncio.sleep(0.5)

    # 3. API breadcrumb - успешный ответ
    add_api_breadcrumb(
        endpoint="/marketplace-api/v1/items",
        method="GET",
        status_code=200,
        response_time_ms=450.5,
    )

    # 4. Trading breadcrumb - результаты сканирования
    add_trading_breadcrumb(
        action="arbitrage_scan_completed",
        game="csgo",
        level="standard",
        user_id=user_id,
        opportunities_found=5,
        scan_duration_ms=1250,
    )

    if update.message:
        await update.message.reply_text("✅ Breadcrumbs тест выполнен")


async def _test_simple_error(update: Update) -> None:
    """Тест простой ошибки.

    Args:
        update: Telegram Update объект

    """
    add_error_breadcrumb(
        error_type="TestError",
        error_message="This is a test error for Sentry",
        severity="error",
        test_type="simple_error",
    )

    try:
        raise ValueError("Test error: This is intentional for Sentry testing")
    except ValueError as e:
        # Захват ошибки в Sentry
        sentry_sdk.capture_exception(e)
        logger.exception("Test error captured: %s", e)

    if update.message:
        await update.message.reply_text("✅ Simple error тест выполнен")


async def _test_api_error(update: Update, user_id: int) -> None:
    """Тест ошибки API с breadcrumbs.

    Args:
        update: Telegram Update объект
        user_id: ID пользователя

    """
    # Breadcrumbs для контекста
    add_trading_breadcrumb(
        action="buying_item",
        game="csgo",
        user_id=user_id,
        item_title="AK-47 | Redline (FT)",
        price_usd=10.50,
    )

    add_api_breadcrumb(
        endpoint="/exchange/v1/offers-buy",
        method="PATCH",
        retry=0,
    )

    # Симуляция ошибки rate limit
    add_error_breadcrumb(
        error_type="RateLimitError",
        error_message="Too many requests - rate limit exceeded",
        severity="warning",
        retry_after=60,
        endpoint="/exchange/v1/offers-buy",
    )

    try:
        raise RuntimeError("API Rate Limit: Too many requests (429)")
    except RuntimeError as e:
        sentry_sdk.capture_exception(e)
        logger.exception("API error captured: %s", e)

    if update.message:
        await update.message.reply_text("✅ API error тест выполнен")


async def _test_division_error(update: Update) -> None:
    """Тест деления на ноль.

    Args:
        update: Telegram Update объект

    """
    add_error_breadcrumb(
        error_type="ZeroDivisionError",
        error_message="Division by zero test",
        severity="error",
    )

    try:
        _ = 10 / 0
    except ZeroDivisionError as e:
        sentry_sdk.capture_exception(e)
        logger.exception("Division error captured: %s", e)

    if update.message:
        await update.message.reply_text("✅ Division error тест выполнен")


async def test_sentry_info(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,  # noqa: ARG001
) -> None:
    """Показать информацию о Sentry интеграции.

    Args:
        update: Telegram Update объект
        context: Telegram Context объект

    """
    if not update.message:
        return

    is_initialized = sentry_sdk.is_initialized()

    info_text = "📊 **Sentry Integration Status**\n\n"

    if is_initialized:
        info_text += "✅ Sentry инициализирован\n\n"
        info_text += "**Доступные тесты:**\n"
        info_text += "• `/test_sentry breadcrumbs` - Тест breadcrumbs\n"
        info_text += "• `/test_sentry error` - Тест простой ошибки\n"
        info_text += "• `/test_sentry api_error` - Тест API ошибки\n"
        info_text += "• `/test_sentry division` - Тест деления на ноль\n"
        info_text += "• `/test_sentry all` - Все тесты\n\n"
        info_text += "После выполнения тестов проверьте:\n"
        info_text += "https://sentry.io/issues/"
    else:
        info_text += "❌ Sentry НЕ инициализирован\n\n"
        info_text += "Установите SENTRY_DSN в .env файле:\n"
        info_text += "`SENTRY_DSN=https://your-key@sentry.io/your-project`"

    await update.message.reply_text(info_text, parse_mode="Markdown")
