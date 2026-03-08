"""Обработчики ошибок Telegram бота.

Этот модуль содержит функции обработки различных ошибок,
возникающих в процессе работы бота.
"""

import logging
import traceback

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.telegram_bot.keyboards import get_back_to_arbitrage_keyboard
from src.utils.exceptions import APIError

logger = logging.getLogger(__name__)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ошибки, возникающие при работе бота.

    Args:
        update: Объект Update от Telegram
        context: Контекст взаимодействия с ботом

    """
    error = context.error

    # Логируем ошибку
    logger.error(f"Exception while handling an update: {error}")
    logger.error(traceback.format_exc())

    # Отправляем сообщение пользователю в зависимости от типа ошибки
    if isinstance(error, APIError):
        # Определяем сообщение на основе кода ошибки
        if error.status_code == 429:
            error_message = (
                "⏱️ <b>Превышен лимит запросов к DMarket API.</b>\n\n"
                "Пожалуйста, подождите немного перед следующим запросом."
            )
        elif error.status_code == 401:
            error_message = "🔐 <b>Ошибка авторизации DMarket API.</b>\n\nПроверьте API-ключи в настSwarmках."
        elif error.status_code == 404:
            error_message = "🔍 <b>Ресурс не найден.</b>\n\nЗапрашиваемый объект не найден на DMarket."
        elif error.status_code >= 500:
            error_message = (
                "🔧 <b>Серверная ошибка DMarket.</b>\n\n"
                "Попробуйте позже - проблемы на стороне DMarket."
            )
        else:
            # Для остальных кодов (400, и т.д.)
            error_message = f"❌ <b>Ошибка DMarket API</b>\n\nКод: {error.status_code}\nСообщение: {error!s}"
    else:
        error_message = (
            "⚠️ <b>Произошла ошибка при выполнении команды.</b>\n\n"
            "Детали были записаны в журнал для анализа разработчиками.\n"
            "Попробуйте позже или свяжитесь с администратором."
        )

    # Отправляем сообщение, если это возможно
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                error_message,
                parse_mode=ParseMode.HTML,
                reply_markup=(
                    get_back_to_arbitrage_keyboard()
                    if isinstance(error, APIError)
                    else None
                ),
            )
        except Exception as e:
            logger.exception(f"Ошибка при отправке сообщения об ошибке: {e}")


# Экспортируем обработчик ошибок
__all__ = ["error_handler"]
