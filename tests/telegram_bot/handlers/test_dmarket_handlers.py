"""Тесты для модуля dmarket_handlers.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Update
from telegram.ext import CallbackContext

from src.telegram_bot.handlers.dmarket_handlers import (
    DMarketHandler,
    register_dmarket_handlers,
)

# =============== Фикстуры ===============


@pytest.fixture()
def mock_update():
    """Фикстура мока объекта Update."""
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.callback_query = None  # Явно устанавливаем None для message updates
    return update


@pytest.fixture()
def mock_context():
    """Фикстура мока контекста."""
    return MagicMock(spec=CallbackContext)


@pytest.fixture()
def mock_balance():
    """Фикстура мока баланса."""
    return {
        "balance": 100.50,  # $100.50 in dollars
        "available_balance": 90.25,  # $90.25 in dollars
        "error": False,
    }


# =============== Тесты DMarketHandler ===============


class TestDMarketHandlerInit:
    """Тесты инициализации DMarketHandler."""

    def test_init_with_keys(self):
        """Тест инициализации с API ключами."""
        with patch("src.telegram_bot.handlers.dmarket_handlers.DMarketAPI"):
            handler = DMarketHandler(
                public_key="test_public",
                secret_key="test_secret",
                api_url="https://api.dmarket.com",
            )

            assert handler.public_key == "test_public"
            assert handler.secret_key == "test_secret"
            assert handler.api_url == "https://api.dmarket.com"
            assert handler.api is not None

    def test_init_without_keys(self):
        """Тест инициализации без API ключей."""
        handler = DMarketHandler(
            public_key="",
            secret_key="",
            api_url="https://api.dmarket.com",
        )

        assert handler.public_key == ""
        assert handler.secret_key == ""
        assert handler.api is None

    @patch("src.telegram_bot.handlers.dmarket_handlers.DMarketAPI")
    def test_initialize_api_success(self, mock_api_class):
        """Тест успешной инициализации API."""
        handler = DMarketHandler(
            public_key="test_public",
            secret_key="test_secret",
            api_url="https://api.dmarket.com",
        )

        mock_api_class.assert_called_once_with(
            public_key="test_public",
            secret_key="test_secret",
            api_url="https://api.dmarket.com",
        )
        assert handler.api is not None

    @patch("src.telegram_bot.handlers.dmarket_handlers.DMarketAPI")
    def test_initialize_api_failure(self, mock_api_class):
        """Тест обработки ошибки при инициализации API."""
        mock_api_class.side_effect = Exception("API Error")

        handler = DMarketHandler.__new__(DMarketHandler)
        handler.public_key = "test_public"
        handler.secret_key = "test_secret"
        handler.api_url = "https://api.dmarket.com"
        handler.api = None

        # Декоратор с reraise=False перехватывает ошибку
        # Проверяем, что метод выполняется без exception
        handler.initialize_api()

        # API не должен быть инициализирован из-за ошибки
        assert handler.api is None


class TestStatusCommand:
    """Тесты команды /dmarket (status_command)."""

    @pytest.mark.asyncio()
    async def test_status_command_with_keys(self, mock_update, mock_context):
        """Тест команды /dmarket с настроенными ключами."""
        with patch("src.telegram_bot.handlers.dmarket_handlers.DMarketAPI"):
            handler = DMarketHandler(
                public_key="test_public",
                secret_key="test_secret",
                api_url="https://api.dmarket.com",
            )

            await handler.status_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            text = (
                call_args.args[0]
                if call_args.args
                else call_args.kwargs.get("text", "")
            )
            assert "настроены" in text
            assert "https://api.dmarket.com" in text

    @pytest.mark.asyncio()
    async def test_status_command_without_keys(self, mock_update, mock_context):
        """Тест команды /dmarket без настроенных ключей."""
        handler = DMarketHandler(
            public_key="",
            secret_key="",
            api_url="https://api.dmarket.com",
        )

        await handler.status_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
        assert "не настроены" in text


class TestBalanceCommand:
    """Тесты команды /balance (balance_command)."""

    @pytest.mark.asyncio()
    async def test_balance_command_without_api(self, mock_update, mock_context):
        """Тест команды /balance без инициализированного API."""
        handler = DMarketHandler(
            public_key="",
            secret_key="",
            api_url="https://api.dmarket.com",
        )

        await handler.balance_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
        assert "не инициализирован" in text

    @pytest.mark.asyncio()
    async def test_balance_command_success(
        self, mock_update, mock_context, mock_balance
    ):
        """Тест успешного получения баланса."""
        with patch(
            "src.telegram_bot.handlers.dmarket_handlers.DMarketAPI"
        ) as mock_api_class:
            mock_api_instance = MagicMock()
            # Make get_balance an AsyncMock to support await
            mock_api_instance.get_balance = AsyncMock(return_value=mock_balance)
            mock_api_class.return_value = mock_api_instance

            handler = DMarketHandler(
                public_key="test_public",
                secret_key="test_secret",
                api_url="https://api.dmarket.com",
            )

            await handler.balance_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            text = (
                call_args.args[0]
                if call_args.args
                else call_args.kwargs.get("text", "")
            )
            assert "100.50" in text  # totalBalance ($100.50)
            assert "90.25" in text  # available ($90.25)

    @pytest.mark.asyncio()
    async def test_balance_command_exception(self, mock_update, mock_context):
        """Тест обработки ошибки при получении баланса."""
        with patch(
            "src.telegram_bot.handlers.dmarket_handlers.DMarketAPI"
        ) as mock_api_class:
            mock_api_instance = MagicMock()
            # Make get_balance an AsyncMock to support await
            mock_api_instance.get_balance = AsyncMock(
                side_effect=Exception("API Error")
            )
            mock_api_class.return_value = mock_api_instance

            handler = DMarketHandler(
                public_key="test_public",
                secret_key="test_secret",
                api_url="https://api.dmarket.com",
            )

            # Декоратор с reraise=False перехватывает ошибку и отправляет сообщение
            await handler.balance_command(mock_update, mock_context)

            # Проверяем, что ошибка отправлена пользователю
            mock_update.message.reply_text.assert_called()
            call_text = mock_update.message.reply_text.call_args.args[0]
            assert "❌" in call_text or "ошибка" in call_text.lower()


class TestRegisterDMarketHandlers:
    """Тесты регистрации обработчиков."""

    def test_register_dmarket_handlers(self):
        """Тест регистрации обработчиков команд DMarket."""
        mock_app = MagicMock()

        with patch("src.telegram_bot.handlers.dmarket_handlers.DMarketAPI"):
            register_dmarket_handlers(
                app=mock_app,
                public_key="test_public",
                secret_key="test_secret",
                api_url="https://api.dmarket.com",
            )

            # Проверяем, что add_handler был вызван минимум 2 раза
            # (для /dmarket и /balance)
            assert mock_app.add_handler.call_count >= 2
