"""Тесты для модуля error_handlers.py.

Этот модуль содержит тесты для обработчиков ошибок в src.telegram_bot.handlers.error_handlers.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Message, Update
from telegram.ext import CallbackContext

from src.telegram_bot.handlers.error_handlers import error_handler
from src.utils.api_error_handling import APIError


@pytest.fixture()
def mock_update():
    """Создает мок объекта Update для тестирования."""
    update = MagicMock(spec=Update)
    update.effective_message = MagicMock(spec=Message)
    update.effective_message.reply_text = AsyncMock()
    return update


@pytest.fixture()
def mock_context():
    """Создает мок объекта CallbackContext для тестирования."""
    return MagicMock(spec=CallbackContext)


@pytest.mark.asyncio()
async def test_error_handler_rate_limit_error(mock_update, mock_context):
    """Тестирует обработку ошибки превышения лимита запросов (429)."""
    # Настраиваем ошибку в контексте
    mock_context.error = APIError("Rate limit exceeded", status_code=429)

    # Вызываем тестируемую функцию
    await error_handler(mock_update, mock_context)

    # Проверяем, что был вызван reply_text с правильным сообщением
    mock_update.effective_message.reply_text.assert_called_once()

    # Проверяем содержимое сообщения
    args, _kwargs = mock_update.effective_message.reply_text.call_args
    message_text = args[0]
    assert "Превышен лимит запросов" in message_text
    assert "подождите" in message_text


@pytest.mark.asyncio()
async def test_error_handler_auth_error(mock_update, mock_context):
    """Тестирует обработку ошибки авторизации (401)."""
    # Настраиваем ошибку в контексте
    mock_context.error = APIError("Unauthorized", status_code=401)

    # Вызываем тестируемую функцию
    await error_handler(mock_update, mock_context)

    # Проверяем содержимое сообщения
    args, _kwargs = mock_update.effective_message.reply_text.call_args
    message_text = args[0]
    assert "Ошибка авторизации" in message_text
    assert "Проверьте API-ключи" in message_text


@pytest.mark.asyncio()
async def test_error_handler_not_found_error(mock_update, mock_context):
    """Тестирует обработку ошибки "не найдено" (404)."""
    # Настраиваем ошибку в контексте
    mock_context.error = APIError("Resource not found", status_code=404)

    # Вызываем тестируемую функцию
    await error_handler(mock_update, mock_context)

    # Проверяем содержимое сообщения
    args, _kwargs = mock_update.effective_message.reply_text.call_args
    message_text = args[0]
    assert "не найден" in message_text


@pytest.mark.asyncio()
async def test_error_handler_server_error(mock_update, mock_context):
    """Тестирует обработку серверной ошибки (5xx)."""
    # Настраиваем ошибку в контексте
    mock_context.error = APIError("Internal server error", status_code=500)

    # Вызываем тестируемую функцию
    await error_handler(mock_update, mock_context)

    # Проверяем содержимое сообщения
    args, _kwargs = mock_update.effective_message.reply_text.call_args
    message_text = args[0]
    assert "Серверная ошибка" in message_text
    assert "попробуйте позже" in message_text.lower()


@pytest.mark.asyncio()
async def test_error_handler_other_api_error(mock_update, mock_context):
    """Тестирует обработку других ошибок API."""
    # Настраиваем ошибку в контексте
    error_message = "Bad request parameters"
    mock_context.error = APIError(error_message, status_code=400)

    # Вызываем тестируемую функцию
    await error_handler(mock_update, mock_context)

    # Проверяем содержимое сообщения
    args, _kwargs = mock_update.effective_message.reply_text.call_args
    message_text = args[0]
    assert "Ошибка DMarket API" in message_text
    assert error_message in message_text


@pytest.mark.asyncio()
async def test_error_handler_generic_error(mock_update, mock_context):
    """Тестирует обработку обычной ошибки (не APIError)."""
    # Настраиваем обычную ошибку в контексте
    mock_context.error = Exception("Generic error")

    # Вызываем тестируемую функцию
    await error_handler(mock_update, mock_context)

    # Проверяем содержимое сообщения
    args, _kwargs = mock_update.effective_message.reply_text.call_args
    message_text = args[0]
    assert "Произошла ошибка" in message_text
    assert "Попробуйте позже" in message_text


@pytest.mark.asyncio()
async def test_error_handler_no_update(mock_context):
    """Тестирует обработку ошибки без объекта update."""
    # Настраиваем ошибку в контексте
    mock_context.error = Exception("Error without update")

    # Вызываем тестируемую функцию с update=None
    await error_handler(None, mock_context)

    # Убеждаемся, что обработчик отработал без ошибок
    # В этом случае сообщение не отправляется, поэтому нет assert для reply_text


@pytest.mark.asyncio()
async def test_error_handler_no_effective_message(mock_update, mock_context):
    """Тестирует обработку ошибки без effective_message."""
    # Настраиваем ошибку в контексте
    mock_context.error = Exception("Error without effective_message")

    # Удаляем effective_message из update
    mock_update.effective_message = None

    # Вызываем тестируемую функцию
    await error_handler(mock_update, mock_context)

    # Убеждаемся, что обработчик отработал без ошибок
