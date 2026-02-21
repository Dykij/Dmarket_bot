"""Тесты для модуля constants и basic_commands.

Этот модуль тестирует:
- Константы Telegram бота
- Базовые команды (/start, /help)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Update

from src.telegram_bot.commands.basic_commands import (
    help_command,
    register_basic_commands,
    start_command,
)
from src.telegram_bot.constants import (
    ARBITRAGE_MODES,
    DEFAULT_PAGE_SIZE,
    ENV_PATH,
    LANGUAGES,
    MAX_ITEMS_PER_PAGE,
    MAX_MESSAGE_LENGTH,
    PRICE_ALERT_HISTORY_KEY,
    PRICE_ALERT_STORAGE_KEY,
    USER_PROFILES_FILE,
)

# ============================================================================
# ТЕСТЫ КОНСТАНТ
# ============================================================================


def test_env_path_defined():
    """Тест определения пути к .env файлу."""
    from pathlib import Path

    assert ENV_PATH is not None
    assert isinstance(ENV_PATH, (str, Path))
    assert ".env" in str(ENV_PATH)


def test_user_profiles_file_defined():
    """Тест определения пути к файлу профилей."""
    from pathlib import Path

    assert USER_PROFILES_FILE is not None
    assert isinstance(USER_PROFILES_FILE, (str, Path))
    assert "user_profiles.json" in str(USER_PROFILES_FILE)


def test_languages_defined():
    """Тест определения поддерживаемых языков."""
    assert LANGUAGES is not None
    assert isinstance(LANGUAGES, dict)
    assert len(LANGUAGES) > 0

    # Проверяем наличие основных языков
    assert "ru" in LANGUAGES
    assert "en" in LANGUAGES

    # Проверяем структуру
    for code, name in LANGUAGES.items():
        assert isinstance(code, str)
        assert isinstance(name, str)


def test_arbitrage_modes_defined():
    """Тест определения режимов арбитража."""
    assert ARBITRAGE_MODES is not None
    assert isinstance(ARBITRAGE_MODES, dict)
    assert len(ARBITRAGE_MODES) > 0

    # Проверяем наличие основных режимов
    assert "boost" in ARBITRAGE_MODES
    assert "pro" in ARBITRAGE_MODES
    # auto режим не обязателен


def test_price_alert_keys_defined():
    """Тест определения ключей для ценовых оповещений."""
    assert PRICE_ALERT_STORAGE_KEY is not None
    assert PRICE_ALERT_HISTORY_KEY is not None
    assert isinstance(PRICE_ALERT_STORAGE_KEY, str)
    assert isinstance(PRICE_ALERT_HISTORY_KEY, str)


def test_pagination_constants():
    """Тест констант пагинации."""
    assert DEFAULT_PAGE_SIZE is not None
    assert MAX_ITEMS_PER_PAGE is not None
    assert isinstance(DEFAULT_PAGE_SIZE, int)
    assert isinstance(MAX_ITEMS_PER_PAGE, int)
    assert DEFAULT_PAGE_SIZE > 0
    assert MAX_ITEMS_PER_PAGE > 0
    assert MAX_ITEMS_PER_PAGE >= DEFAULT_PAGE_SIZE


def test_interface_constants():
    """Тест констант интерфейса."""
    assert MAX_MESSAGE_LENGTH is not None
    assert isinstance(MAX_MESSAGE_LENGTH, int)
    assert MAX_MESSAGE_LENGTH == 4096  # Telegram limit


# ============================================================================
# ТЕСТЫ БАЗОВЫХ КОМАНД
# ============================================================================


@pytest.fixture()
def mock_update():
    """Создает мок Update объекта."""
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock()
    update.effective_user.id = 123456
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture()
def mock_context():
    """Создает мок Context объекта."""
    return MagicMock()


@pytest.mark.asyncio()
async def test_start_command(mock_update, mock_context):
    """Тест команды /start."""
    awAlgot start_command(mock_update, mock_context)

    # Проверяем, что было отправлено сообщение
    mock_update.message.reply_text.assert_called_once()

    # Проверяем содержание сообщения
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "Привет" in call_args or "Hello" in call_args or "бот" in call_args.lower()


@pytest.mark.asyncio()
async def test_help_command(mock_update, mock_context):
    """Тест команды /help."""
    awAlgot help_command(mock_update, mock_context)

    # Проверяем, что было отправлено сообщение
    mock_update.message.reply_text.assert_called_once()

    # Проверяем содержание сообщения
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "/start" in call_args
    assert "/help" in call_args
    assert "/balance" in call_args or "/arbitrage" in call_args


@pytest.mark.asyncio()
async def test_start_command_no_message(mock_context):
    """Тест команды /start без сообщения."""
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock()
    update.effective_user.id = 123456
    update.message = None

    # Не должно вызвать ошибку
    awAlgot start_command(update, mock_context)


@pytest.mark.asyncio()
async def test_help_command_no_message(mock_context):
    """Тест команды /help без сообщения."""
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock()
    update.effective_user.id = 123456
    update.message = None

    # Не должно вызвать ошибку
    awAlgot help_command(update, mock_context)


def test_register_basic_commands():
    """Тест регистрации базовых команд."""
    # Создаем мок Application
    mock_app = MagicMock()
    mock_app.add_handler = MagicMock()

    # Регистрируем команды
    register_basic_commands(mock_app)

    # Проверяем, что обработчики были добавлены
    assert mock_app.add_handler.called
    assert mock_app.add_handler.call_count == 2  # start и help
