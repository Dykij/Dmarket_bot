"""Конфигурация pytest для модуля telegram_bot.

Этот файл содержит фикстуры для тестирования модулей в директории src/telegram_bot.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture()
def mock_update():
    """Создает мок объекта Update из библиотеки python-telegram-bot."""
    update = MagicMock()
    update.effective_chat = MagicMock(id=12345678)
    update.effective_user = MagicMock(
        id=87654321,
        first_name="Test",
        username="test_user",
    )
    update.effective_message = MagicMock(message_id=1, text="Test message")

    # Создание callback_query для тестирования обработчиков обратного вызова
    update.callback_query = MagicMock(
        data="test_data",
        message=update.effective_message,
        from_user=update.effective_user,
    )

    return update


@pytest.fixture()
def mock_context():
    """Создает мок объекта Context из библиотеки python-telegram-bot."""
    context = MagicMock()
    context.bot = AsyncMock()
    context.bot.send_message = AsyncMock(return_value=MagicMock())
    context.bot.edit_message_text = AsyncMock(return_value=MagicMock())
    context.bot.send_photo = AsyncMock(return_value=MagicMock())
    context.bot.answer_callback_query = AsyncMock(return_value=True)

    # Добавляем user_data и chat_data как словари
    context.user_data = {}
    context.chat_data = {}

    # Добавляем args и matches для тестирования командных обработчиков
    context.args = []
    context.matches = []

    return context


@pytest.fixture()
def mock_dmarket_api_for_telegram():
    """Создает мок DMarket API для использования в тестах телеграм бота."""
    api = MagicMock()
    api.get_balance = AsyncMock(return_value={"usd": {"amount": 100.0}})
    api.get_item_offers = AsyncMock(return_value={"objects": []})
    api.get_user_offers = AsyncMock(return_value={"objects": []})
    api.get_last_sales = AsyncMock(return_value={"LastSales": [], "Total": 0})

    return api


@pytest.fixture()
def mock_keyboards():
    """Создает мок клавиатур для интерфейса Telegram."""
    keyboards = MagicMock()
    keyboards.get_main_keyboard = MagicMock(return_value=MagicMock())
    keyboards.get_game_selection_keyboard = MagicMock(return_value=MagicMock())
    keyboards.get_back_keyboard = MagicMock(return_value=MagicMock())
    keyboards.get_pagination_keyboard = MagicMock(return_value=MagicMock())

    return keyboards
