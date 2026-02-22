"""
Юнит-тесты для модуля dmarket_status.py

Покрытие основных сценариев:
- Успешная проверка с ключами из профиля
- Проверка с ключами из env переменных
- Обработка ошибок (401, APIError, общие исключения)
- Проверка без ключей API
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Chat, Message, Update, User
from telegram.ext import CallbackContext

from src.telegram_bot.handlers.dmarket_status import dmarket_status_impl
from src.utils.exceptions import APIError


@pytest.fixture()
def mock_update():
    """Создать мок Update."""
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 123456789
    update.effective_chat = MagicMock(spec=Chat)
    update.effective_chat.send_action = AsyncMock()
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture()
def mock_context():
    """Создать мок CallbackContext."""
    return MagicMock(spec=CallbackContext)


class TestDMarketStatusBasic:
    """Базовые тесты проверки статуса."""

    @pytest.mark.asyncio()
    async def test_with_profile_keys(self, mock_update, mock_context):
        """Тест с ключами из профиля."""
        with (
            patch(
                "src.telegram_bot.handlers.dmarket_status.get_user_profile"
            ) as mock_profile,
            patch(
                "src.telegram_bot.handlers.dmarket_status.get_localized_text"
            ) as mock_text,
            patch("src.dmarket.dmarket_api.DMarketAPI") as mock_api,
            patch(
                "src.telegram_bot.handlers.dmarket_status.check_user_balance"
            ) as mock_balance,
        ):
            mock_profile.return_value = {"api_key": "key", "api_secret": "secret"}
            mock_text.return_value = "Checking..."

            status_msg = AsyncMock(spec=Message)
            status_msg.edit_text = AsyncMock()
            mock_update.message.reply_text.return_value = status_msg

            api_instance = MagicMock()
            api_instance._close_client = AsyncMock()
            mock_api.return_value = api_instance

            mock_balance.return_value = {
                "error": False,
                "balance": 100.0,
                "has_funds": True,
            }

            await dmarket_status_impl(mock_update, mock_context)

            status_msg.edit_text.assert_called_once()
            call_text = status_msg.edit_text.call_args[0][0]
            assert "✅" in call_text
            assert "$100.00" in call_text

    @pytest.mark.asyncio()
    async def test_with_env_keys(self, mock_update, mock_context):
        """Тест с ключами из переменных окружения."""
        with (
            patch(
                "src.telegram_bot.handlers.dmarket_status.get_user_profile"
            ) as mock_profile,
            patch(
                "src.telegram_bot.handlers.dmarket_status.get_localized_text"
            ) as mock_text,
            patch("os.getenv") as mock_getenv,
            patch("src.dmarket.dmarket_api.DMarketAPI") as mock_api,
            patch(
                "src.telegram_bot.handlers.dmarket_status.check_user_balance"
            ) as mock_balance,
        ):
            mock_profile.return_value = {}
            mock_text.return_value = "Checking..."

            def getenv_mock(key, default=""):
                return "env_key" if "KEY" in key else default

            mock_getenv.side_effect = getenv_mock

            status_msg = AsyncMock(spec=Message)
            status_msg.edit_text = AsyncMock()
            mock_update.message.reply_text.return_value = status_msg

            api_instance = MagicMock()
            api_instance._close_client = AsyncMock()
            mock_api.return_value = api_instance

            mock_balance.return_value = {
                "error": False,
                "balance": 50.0,
                "has_funds": True,
            }

            await dmarket_status_impl(mock_update, mock_context)

            status_msg.edit_text.assert_called_once()
            call_text = status_msg.edit_text.call_args[0][0]
            assert "✅" in call_text

    @pytest.mark.asyncio()
    async def test_without_keys(self, mock_update, mock_context):
        """Тест без API ключей."""
        with (
            patch(
                "src.telegram_bot.handlers.dmarket_status.get_user_profile"
            ) as mock_profile,
            patch(
                "src.telegram_bot.handlers.dmarket_status.get_localized_text"
            ) as mock_text,
            patch("os.getenv") as mock_getenv,
            patch("src.dmarket.dmarket_api.DMarketAPI") as mock_api,
        ):
            mock_profile.return_value = {}
            mock_text.return_value = "Checking..."
            mock_getenv.return_value = ""

            status_msg = AsyncMock(spec=Message)
            status_msg.edit_text = AsyncMock()
            mock_update.message.reply_text.return_value = status_msg

            api_instance = MagicMock()
            api_instance._close_client = AsyncMock()
            mock_api.return_value = api_instance

            await dmarket_status_impl(mock_update, mock_context)

            status_msg.edit_text.assert_called_once()
            call_text = status_msg.edit_text.call_args[0][0]
            assert "❌" in call_text


class TestDMarketStatusErrors:
    """Тесты обработки ошибок."""

    @pytest.mark.asyncio()
    async def test_401_error(self, mock_update, mock_context):
        """Тест обработки 401 ошибки."""
        with (
            patch(
                "src.telegram_bot.handlers.dmarket_status.get_user_profile"
            ) as mock_profile,
            patch(
                "src.telegram_bot.handlers.dmarket_status.get_localized_text"
            ) as mock_text,
            patch("src.dmarket.dmarket_api.DMarketAPI") as mock_api,
            patch(
                "src.telegram_bot.handlers.dmarket_status.check_user_balance"
            ) as mock_balance,
        ):
            mock_profile.return_value = {"api_key": "wrong", "api_secret": "wrong"}
            mock_text.return_value = "Checking..."

            status_msg = AsyncMock(spec=Message)
            status_msg.edit_text = AsyncMock()
            mock_update.message.reply_text.return_value = status_msg

            api_instance = MagicMock()
            api_instance._close_client = AsyncMock()
            mock_api.return_value = api_instance

            # APIError требует status_code, а не response
            mock_balance.side_effect = APIError("Unauthorized", status_code=401)

            await dmarket_status_impl(mock_update, mock_context)

            status_msg.edit_text.assert_called_once()
            call_text = status_msg.edit_text.call_args[0][0]
            assert "❌" in call_text
            assert (
                "авторизации" in call_text.lower()
                or "unauthorized" in call_text.lower()
            )

    @pytest.mark.asyncio()
    async def test_api_error(self, mock_update, mock_context):
        """Тест обработки APIError."""
        with (
            patch(
                "src.telegram_bot.handlers.dmarket_status.get_user_profile"
            ) as mock_profile,
            patch(
                "src.telegram_bot.handlers.dmarket_status.get_localized_text"
            ) as mock_text,
            patch("src.dmarket.dmarket_api.DMarketAPI") as mock_api,
            patch(
                "src.telegram_bot.handlers.dmarket_status.check_user_balance"
            ) as mock_balance,
        ):
            mock_profile.return_value = {"api_key": "key", "api_secret": "secret"}
            mock_text.return_value = "Checking..."

            status_msg = AsyncMock(spec=Message)
            status_msg.edit_text = AsyncMock()
            mock_update.message.reply_text.return_value = status_msg

            api_instance = MagicMock()
            api_instance._close_client = AsyncMock()
            mock_api.return_value = api_instance

            # APIError требует status_code, а не response
            mock_balance.side_effect = APIError("Server Error", status_code=500)

            await dmarket_status_impl(mock_update, mock_context)

            status_msg.edit_text.assert_called_once()
            call_text = status_msg.edit_text.call_args[0][0]
            assert "❌" in call_text or "⚠️" in call_text

    @pytest.mark.asyncio()
    async def test_general_exception(self, mock_update, mock_context):
        """Тест обработки общего исключения."""
        with (
            patch(
                "src.telegram_bot.handlers.dmarket_status.get_user_profile"
            ) as mock_profile,
            patch(
                "src.telegram_bot.handlers.dmarket_status.get_localized_text"
            ) as mock_text,
            patch("src.telegram_bot.handlers.dmarket_status.DMarketAPI") as mock_api,
            patch(
                "src.telegram_bot.handlers.dmarket_status.check_user_balance"
            ) as mock_balance,
        ):
            mock_profile.return_value = {"api_key": "key", "api_secret": "secret"}
            mock_text.return_value = "Checking..."

            status_msg = AsyncMock(spec=Message)
            status_msg.edit_text = AsyncMock()
            mock_update.message.reply_text.return_value = status_msg

            api_instance = MagicMock()
            api_instance._close_client = AsyncMock()
            api_instance.__aenter__ = AsyncMock(return_value=api_instance)
            # Don't suppress exception
            api_instance.__aexit__ = AsyncMock(return_value=False)
            mock_api.return_value = api_instance

            mock_balance.side_effect = ValueError("Unexpected error")

            await dmarket_status_impl(mock_update, mock_context)

            status_msg.edit_text.assert_called_once()
            # __aexit__ вызывается даже при exception
            api_instance.__aexit__.assert_called_once()


class TestDMarketStatusIntegration:
    """Интеграционные тесты."""

    @pytest.mark.asyncio()
    async def test_custom_status_message(self, mock_update, mock_context):
        """Тест с кастомным status_message."""
        with (
            patch(
                "src.telegram_bot.handlers.dmarket_status.get_user_profile"
            ) as mock_profile,
            patch("src.dmarket.dmarket_api.DMarketAPI") as mock_api,
            patch(
                "src.telegram_bot.handlers.dmarket_status.check_user_balance"
            ) as mock_balance,
        ):
            mock_profile.return_value = {"api_key": "key", "api_secret": "secret"}

            custom_msg = AsyncMock(spec=Message)
            custom_msg.edit_text = AsyncMock()

            api_instance = MagicMock()
            api_instance._close_client = AsyncMock()
            mock_api.return_value = api_instance

            mock_balance.return_value = {
                "error": False,
                "balance": 50.0,
                "has_funds": True,
            }

            await dmarket_status_impl(
                mock_update, mock_context, status_message=custom_msg
            )

            mock_update.message.reply_text.assert_not_called()
            custom_msg.edit_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_client_always_closed(self, mock_update, mock_context):
        """Тест что клиент всегда закрывается."""
        with (
            patch(
                "src.telegram_bot.handlers.dmarket_status.get_user_profile"
            ) as mock_profile,
            patch(
                "src.telegram_bot.handlers.dmarket_status.get_localized_text"
            ) as mock_text,
            patch("src.telegram_bot.handlers.dmarket_status.DMarketAPI") as mock_api,
            patch(
                "src.telegram_bot.handlers.dmarket_status.check_user_balance"
            ) as mock_balance,
        ):
            mock_profile.return_value = {"api_key": "key", "api_secret": "secret"}
            mock_text.return_value = "Checking..."

            status_msg = AsyncMock(spec=Message)
            status_msg.edit_text = AsyncMock()
            mock_update.message.reply_text.return_value = status_msg

            api_instance = MagicMock()
            api_instance._close_client = AsyncMock()
            api_instance.__aenter__ = AsyncMock(return_value=api_instance)
            # Don't suppress exception
            api_instance.__aexit__ = AsyncMock(return_value=False)
            mock_api.return_value = api_instance

            mock_balance.side_effect = RuntimeError("Error")

            await dmarket_status_impl(mock_update, mock_context)

            # __aexit__ вызывается даже при exception
            api_instance.__aexit__.assert_called_once()
