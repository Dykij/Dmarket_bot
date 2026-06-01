"""Основные фикстуры для функциональных групп тестов.
Этот файл улучшает организацию тестов путем группирования
связанных фикстур в одном месте.
"""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, Message, Update, User
from telegram.ext import CallbackContext


# Группа фикстур для Telegram-бота
@pytest.fixture()
def mock_telegram_update() -> MagicMock:
    """Создает мок объекта Update для команд сообщений."""
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.message.from_user = MagicMock(spec=User)
    update.message.from_user.id = 12345
    update.message.chat_id = 12345

    # Эти атрибуты нужны только для callback_queries
    update.callback_query = None

    return update


@pytest.fixture()
def mock_telegram_callback_query() -> MagicMock:
    """Создает мок объекта Update с CallbackQuery для коллбэков кнопок."""
    update = MagicMock(spec=Update)
    update.message = None

    query = MagicMock(spec=CallbackQuery)
    query.data = "test_callback"
    query.from_user = MagicMock(spec=User)
    query.from_user.id = 12345
    query.message = MagicMock(spec=Message)
    query.message.chat_id = 12345
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()

    update.callback_query = query

    return update


@pytest.fixture()
def mock_telegram_context() -> MagicMock:
    """Создает мок объекта Context."""
    context = MagicMock(spec=CallbackContext)
    context.user_data = {}
    return context


# Группа фикстур для DMarket API
@pytest.fixture()
def mock_dmarket_api() -> Generator[MagicMock, None, None]:
    """Создает мок DMarket API."""
    with patch("src.dmarket.dmarket_api.DMarketAPI") as mock_api:
        # НастSwarmка мока для типичных методов API
        instance = mock_api.return_value
        instance._generate_signature.return_value = {"X-Sign": "test_signature"}
        instance.get_balance = AsyncMock(return_value={"dmc": 1000, "usd": 100})
        yield instance


# Группа фикстур для тестирования арбитража
@pytest.fixture()
def mock_arbitrage_data() -> dict[str, Any]:
    """Предоставляет тестовые данные для арбитража."""
    return {
        "cs": [
            {
                "title": "Тестовый предмет CS:GO",
                "price": {"DMC": "100"},
                "suggestedPrice": {"DMC": "120"},
                "itemId": "test_item_id_1",
            },
            {
                "title": "ВтоSwarm тестовый предмет",
                "price": {"DMC": "200"},
                "suggestedPrice": {"DMC": "240"},
                "itemId": "test_item_id_2",
            },
        ],
    }


# Вспомогательная функция для всех тестов
@pytest.fixture()
def helper_setup_test_environment() -> bool:
    """НастSwarmка тестового окружения для многократного использования."""
    # Здесь можно добавить общие настSwarmки для тестов
    return True
