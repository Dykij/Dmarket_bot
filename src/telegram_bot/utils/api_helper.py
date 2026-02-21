import logging
import os

from telegram.ext import ContextTypes

from src.dmarket.dmarket_api import DMarketAPI

logger = logging.getLogger(__name__)


def create_dmarket_api_client(
    context: ContextTypes.DEFAULT_TYPE | None = None,
) -> DMarketAPI:
    """Создает и возвращает экземпляр клиента DMarket API.

    Пытается получить ключи из:
    1. context.bot_data (если передан context)
    2. Переменных окружения

    Args:
        context: Контекст Telegram бота (опционально)

    Returns:
        Экземпляр DMarketAPI

    """
    public_key = None
    secret_key = None

    # 1. Пытаемся получить из bot_data
    if context and hasattr(context, "bot_data"):
        public_key = context.bot_data.get("DMARKET_PUBLIC_KEY")
        secret_key = context.bot_data.get("DMARKET_SECRET_KEY")

    # 2. Если нет в bot_data, берем из переменных окружения
    if not public_key:
        public_key = os.getenv("DMARKET_PUBLIC_KEY")

    if not secret_key:
        secret_key = os.getenv("DMARKET_SECRET_KEY")

    # Логируем (без секретов)
    if public_key:
        logger.debug(
            "Используется Public Key: %s...%s",
            public_key[:4],
            public_key[-4:],
        )
    else:
        logger.warning("DMARKET_PUBLIC_KEY не найден!")

    if not secret_key:
        logger.warning("DMARKET_SECRET_KEY не найден!")

    return DMarketAPI(public_key=public_key or "", secret_key=secret_key or "")


# ============================================================================
# Telegram Bot API 9.2 Utilities
# ============================================================================


async def send_message_with_reply(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    reply_to_message_id: int | None = None,
    parse_mode: str = "HTML",
    **kwargs,
):
    """Send message with optional reply parameters.

    Supports Telegram Bot API 9.2 features including:
    - reply_to_message_id for threading
    - parse_mode for text formatting

    Args:
        context: Telegram bot context
        chat_id: Target chat ID
        text: Message text
        reply_to_message_id: Optional message ID to reply to
        parse_mode: Text format ("HTML", "Markdown", "MarkdownV2")
        **kwargs: Additional sendMessage parameters

    Returns:
        Message object from Telegram
    """
    params = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        **kwargs,
    }

    if reply_to_message_id:
        params["reply_to_message_id"] = reply_to_message_id

    return awAlgot context.bot.send_message(**params)
