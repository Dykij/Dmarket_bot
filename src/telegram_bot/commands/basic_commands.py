"""Базовые команды для Telegram бота.

Этот модуль содержит основные команды для взаимодействия
пользователя с Telegram ботом.
"""

import logging
from typing import Any

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.utils.sentry_breadcrumbs import add_command_breadcrumb

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение при команде /start."""
    user = update.effective_user
    if not user:
        return

    logger.info("Пользователь %s использовал команду /start", user.id)

    # Добавляем breadcrumb о команде
    add_command_breadcrumb(
        command="/start",
        user_id=user.id,
        username=user.username or "",
        chat_id=update.effective_chat.id if update.effective_chat else 0,
    )

    if update.message:
        await update.message.reply_text(
            "Привет! Я бот для работы с DMarket. Используй /help, чтобы увидеть доступные команды.",
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет список доступных команд при команде /help."""
    user = update.effective_user
    if not user:
        return

    logger.info("Пользователь %s использовал команду /help", user.id)

    # Добавляем breadcrumb о команде
    add_command_breadcrumb(
        command="/help",
        user_id=user.id,
        username=user.username or "",
        chat_id=update.effective_chat.id if update.effective_chat else 0,
    )

    if update.message:
        await update.message.reply_text(
            "Доступные команды:\n"
            "/start — приветствие\n"
            "/help — показать это сообщение\n"
            "/dmarket — проверить статус API DMarket\n"
            "/balance — проверить баланс на DMarket\n"
            "/arbitrage — поиск арбитражных возможностей",
        )


def register_basic_commands(app: Application[Any, Any, Any, Any, Any, Any]) -> None:
    """Регистрирует базовые команды в приложении Telegram."""
    logger.info("Регистрация базовых команд")

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
