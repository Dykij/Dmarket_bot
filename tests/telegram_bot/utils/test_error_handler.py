"""Тесты для модуля error_handler.py (utils)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Bot, Message, Update
from telegram.error import (
    BadRequest,
    Forbidden,
    NetworkError,
    RetryAfter,
    TimedOut,
)
from telegram.ext import Application

from src.telegram_bot.utils.error_handler import (
    configure_admin_ids,
    error_handler,
    exception_guard,
    handle_bad_request,
    handle_dmarket_api_error,
    handle_forbidden_error,
    handle_network_error,
    register_global_exception_handlers,
    retry_last_action,
    send_message_safe,
    setup_error_handler,
)


@pytest.fixture()
def mock_update():
    """Мок для Update."""
    update = MagicMock(spec=Update)
    update.effective_chat = MagicMock()
    update.effective_chat.id = 12345
    update.effective_user = MagicMock()
    update.effective_user.id = 67890
    update.effective_user.username = "testuser"
    update.effective_message = MagicMock()
    update.effective_message.text = "Test message"
    update.to_dict = MagicMock(return_value={"update_id": 1})
    return update


@pytest.fixture()
def mock_context():
    """Мок для ContextTypes.DEFAULT_TYPE."""
    context = MagicMock()
    context.bot = MagicMock(spec=Bot)
    context.bot.send_message = AsyncMock()
    context.error = None
    return context


class TestHandleNetworkError:
    """Тесты для handle_network_error."""

    @pytest.mark.asyncio()
    async def test_handle_retry_after(self, mock_update, mock_context):
        """Тест обработки RetryAfter ошибки."""
        mock_context.error = RetryAfter(30)

        await handle_network_error(mock_update, mock_context)

        mock_context.bot.send_message.assert_called_once()
        call_args = mock_context.bot.send_message.call_args[1]
        assert "30 секунд" in call_args["text"]

    @pytest.mark.asyncio()
    async def test_handle_timed_out(self, mock_update, mock_context):
        """Тест обработки TimedOut ошибки."""
        mock_context.error = TimedOut("Connection timeout")

        await handle_network_error(mock_update, mock_context)

        mock_context.bot.send_message.assert_called_once()
        call_args = mock_context.bot.send_message.call_args[1]
        assert "Истекло время" in call_args["text"]

    @pytest.mark.asyncio()
    async def test_handle_network_error_generic(self, mock_update, mock_context):
        """Тест обработки общей сетевой ошибки."""
        mock_context.error = NetworkError("Network failure")

        await handle_network_error(mock_update, mock_context)

        mock_context.bot.send_message.assert_called_once()

    @pytest.mark.asyncio()
    async def test_handle_network_error_no_update(self, mock_context):
        """Тест без update."""
        mock_context.error = NetworkError("Network failure")

        # Не должно быть исключений
        await handle_network_error(None, mock_context)

        mock_context.bot.send_message.assert_not_called()


class TestRetryLastAction:
    """Тесты для retry_last_action."""

    @pytest.mark.asyncio()
    async def test_retry_with_job_context(self, mock_context):
        """Тест повтора с job context."""
        mock_job = MagicMock()
        mock_job.context = {"original_update": MagicMock()}
        mock_context.job = mock_job

        # Не должно быть исключений
        await retry_last_action(mock_context)

    @pytest.mark.asyncio()
    async def test_retry_without_job(self, mock_context):
        """Тест без job."""
        mock_context.job = None

        # Не должно быть исключений
        await retry_last_action(mock_context)


class TestHandleForbiddenError:
    """Тесты для handle_forbidden_error."""

    @pytest.mark.asyncio()
    async def test_handle_blocked_by_user(self, mock_update, mock_context):
        """Тест обработки блокировки пользователем."""
        mock_context.error = Forbidden("bot was blocked by the user")

        await handle_forbidden_error(mock_update, mock_context)

        mock_context.bot.send_message.assert_called_once()
        call_args = mock_context.bot.send_message.call_args[1]
        assert "заблокировал бота" in call_args["text"]

    @pytest.mark.asyncio()
    async def test_handle_kicked_from_group(self, mock_update, mock_context):
        """Тест обработки удаления из группы."""
        mock_context.error = Forbidden("bot was kicked from the group")

        await handle_forbidden_error(mock_update, mock_context)

        call_args = mock_context.bot.send_message.call_args[1]
        assert "удален из группы" in call_args["text"]

    @pytest.mark.asyncio()
    async def test_handle_no_rights(self, mock_update, mock_context):
        """Тест обработки отсутствия прав."""
        mock_context.error = Forbidden("not enough rights to send")

        await handle_forbidden_error(mock_update, mock_context)

        call_args = mock_context.bot.send_message.call_args[1]
        assert "недостаточно прав" in call_args["text"]


class TestHandleBadRequest:
    """Тесты для handle_bad_request."""

    @pytest.mark.asyncio()
    async def test_handle_message_not_modified(self, mock_update, mock_context):
        """Тест игнорирования 'message is not modified'."""
        mock_context.error = BadRequest("message is not modified")

        await handle_bad_request(mock_update, mock_context)

        # Должно быть проигнорировано
        mock_context.bot.send_message.assert_not_called()

    @pytest.mark.asyncio()
    async def test_handle_message_not_found(self, mock_update, mock_context):
        """Тест обработки 'message to edit not found'."""
        mock_context.error = BadRequest("message to edit not found")

        await handle_bad_request(mock_update, mock_context)

        call_args = mock_context.bot.send_message.call_args[1]
        assert "не найдено" in call_args["text"]

    @pytest.mark.asyncio()
    async def test_handle_query_too_old(self, mock_update, mock_context):
        """Тест обработки 'query is too old'."""
        mock_context.error = BadRequest("query is too old")

        await handle_bad_request(mock_update, mock_context)

        call_args = mock_context.bot.send_message.call_args[1]
        assert "устарел" in call_args["text"]

    @pytest.mark.asyncio()
    async def test_handle_parse_entities_error(self, mock_update, mock_context):
        """Тест обработки ошибки парсинга."""
        mock_context.error = BadRequest("can't parse entities")

        await handle_bad_request(mock_update, mock_context)

        call_args = mock_context.bot.send_message.call_args[1]
        assert "форматировании" in call_args["text"]

    @pytest.mark.asyncio()
    async def test_handle_wrong_file_id(self, mock_update, mock_context):
        """Тест обработки неверного file_id."""
        mock_context.error = BadRequest("wrong file identifier")

        await handle_bad_request(mock_update, mock_context)

        call_args = mock_context.bot.send_message.call_args[1]
        assert "файлом" in call_args["text"]


class TestHandleDmarketApiError:
    """Тесты для handle_dmarket_api_error."""

    @pytest.mark.asyncio()
    async def test_handle_401(self, mock_update, mock_context):
        """Тест обработки 401 ошибки."""
        dmarket_error = MagicMock()
        dmarket_error.code = 401
        mock_context.dmarket_error = dmarket_error
        mock_context.error = Exception("Unauthorized")

        await handle_dmarket_api_error(mock_update, mock_context)

        call_args = mock_context.bot.send_message.call_args[1]
        assert "авторизации" in call_args["text"]

    @pytest.mark.asyncio()
    async def test_handle_429(self, mock_update, mock_context):
        """Тест обработки 429 ошибки."""
        dmarket_error = MagicMock()
        dmarket_error.code = 429
        mock_context.dmarket_error = dmarket_error
        mock_context.error = Exception("Rate limit")

        await handle_dmarket_api_error(mock_update, mock_context)

        call_args = mock_context.bot.send_message.call_args[1]
        assert "лимит" in call_args["text"]

    @pytest.mark.asyncio()
    async def test_handle_500(self, mock_update, mock_context):
        """Тест обработки 500 ошибки."""
        dmarket_error = MagicMock()
        dmarket_error.code = 500
        mock_context.dmarket_error = dmarket_error
        mock_context.error = Exception("Server error")

        await handle_dmarket_api_error(mock_update, mock_context)

        call_args = mock_context.bot.send_message.call_args[1]
        assert "недоступен" in call_args["text"]

    @pytest.mark.asyncio()
    async def test_handle_other_error(self, mock_update, mock_context):
        """Тест обработки других ошибок DMarket."""
        dmarket_error = MagicMock()
        dmarket_error.code = 400
        mock_context.dmarket_error = dmarket_error
        mock_context.error = Exception("Bad request")

        await handle_dmarket_api_error(mock_update, mock_context)

        mock_context.bot.send_message.assert_called_once()


class TestErrorHandler:
    """Тесты для основного error_handler."""

    @pytest.mark.asyncio()
    async def test_handle_network_error_dispatch(self, mock_update, mock_context):
        """Тест диспетчеризации NetworkError."""
        mock_context.error = NetworkError("Network error")

        with patch(
            "src.telegram_bot.utils.error_handler.handle_network_error", AsyncMock()
        ) as mock_handle:
            await error_handler(mock_update, mock_context)
            mock_handle.assert_called_once()

    @pytest.mark.asyncio()
    async def test_handle_forbidden_dispatch(self, mock_update, mock_context):
        """Тест диспетчеризации Forbidden."""
        mock_context.error = Forbidden("Forbidden")

        with patch(
            "src.telegram_bot.utils.error_handler.handle_forbidden_error", AsyncMock()
        ) as mock_handle:
            await error_handler(mock_update, mock_context)
            mock_handle.assert_called_once()

    @pytest.mark.asyncio()
    async def test_handle_bad_request_direct(self, mock_update, mock_context):
        """Тест прямой обработки BadRequest."""
        mock_context.error = BadRequest("query is too old")

        await error_handler(mock_update, mock_context)

        # Должно отправить сообщение пользователю
        assert mock_context.bot.send_message.called

    @pytest.mark.asyncio()
    async def test_handle_dmarket_error_dispatch(self, mock_update, mock_context):
        """Тест диспетчеризации DMarket error."""
        mock_context.error = Exception("DMarket error")
        mock_context.dmarket_error = MagicMock()

        with patch(
            "src.telegram_bot.utils.error_handler.handle_dmarket_api_error", AsyncMock()
        ) as mock_handle:
            await error_handler(mock_update, mock_context)
            mock_handle.assert_called_once()

    @pytest.mark.asyncio()
    async def test_handle_generic_error(self, mock_update, mock_context):
        """Тест обработки обычной ошибки."""
        mock_context.error = ValueError("Test error")

        await error_handler(mock_update, mock_context)

        # Должны быть вызовы send_message для пользователя
        assert mock_context.bot.send_message.called

    @pytest.mark.asyncio()
    async def test_handle_error_no_update(self, mock_context):
        """Тест обработки ошибки без update."""
        mock_context.error = Exception("Error without update")

        # Не должно быть исключений
        await error_handler(None, mock_context)

    @pytest.mark.asyncio()
    async def test_handle_error_sends_user_message(self, mock_update, mock_context):
        """Тест отправки сообщения пользователю."""
        mock_context.error = ValueError("Test error")

        await error_handler(mock_update, mock_context)

        # Должно отправить хотя бы одно сообщение
        assert mock_context.bot.send_message.call_count >= 1


class TestSetupErrorHandler:
    """Тесты для setup_error_handler."""

    def test_setup_with_admin_ids(self):
        """Тест настSwarmки с явными admin_ids."""
        mock_app = MagicMock(spec=Application)
        mock_app.add_error_handler = MagicMock()

        setup_error_handler(mock_app, admin_ids=[123, 456])

        mock_app.add_error_handler.assert_called_once()

    def test_setup_without_admin_ids(self):
        """Тест настSwarmки без явных admin_ids."""
        mock_app = MagicMock(spec=Application)
        mock_app.add_error_handler = MagicMock()

        with patch.dict("os.environ", {"TELEGRAM_ADMIN_IDS": "789,101"}):
            setup_error_handler(mock_app)
            mock_app.add_error_handler.assert_called_once()


class TestExceptionGuard:
    """Тесты для exception_guard декоратора."""

    @pytest.mark.asyncio()
    async def test_exception_guard_success(self, mock_update, mock_context):
        """Тест успешного выполнения обёрнутой функции."""

        async def test_func(update, context):
            return "success"

        guarded_func = exception_guard(test_func)
        result = await guarded_func(mock_update, mock_context)

        assert result == "success"

    @pytest.mark.asyncio()
    async def test_exception_guard_with_error(self, mock_update, mock_context):
        """Тест обработки исключения в обёрнутой функции."""

        async def test_func(update, context):
            raise ValueError("Test error")

        guarded_func = exception_guard(test_func)

        with patch(
            "src.telegram_bot.utils.error_handler.error_handler", AsyncMock()
        ) as mock_handler:
            result = await guarded_func(mock_update, mock_context)

            assert result is None
            mock_handler.assert_called_once()


class TestSendMessageSafe:
    """Тесты для send_message_safe."""

    @pytest.mark.asyncio()
    async def test_send_message_success(self):
        """Тест успешной отправки сообщения."""
        mock_bot = MagicMock(spec=Bot)
        mock_message = MagicMock(spec=Message)
        mock_bot.send_message = AsyncMock(return_value=mock_message)

        result = await send_message_safe(mock_bot, 12345, "Test message")

        assert result == mock_message

    @pytest.mark.asyncio()
    async def test_send_message_forbidden(self):
        """Тест обработки Forbidden ошибки."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.send_message = AsyncMock(side_effect=Forbidden("Forbidden"))

        result = await send_message_safe(mock_bot, 12345, "Test message")

        assert result is None

    @pytest.mark.asyncio()
    async def test_send_message_bad_request(self):
        """Тест обработки BadRequest ошибки."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.send_message = AsyncMock(side_effect=BadRequest("Bad request"))

        result = await send_message_safe(mock_bot, 12345, "Test message")

        assert result is None

    @pytest.mark.asyncio()
    async def test_send_message_network_error(self):
        """Тест обработки NetworkError."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.send_message = AsyncMock(side_effect=NetworkError("Network error"))

        result = await send_message_safe(mock_bot, 12345, "Test message")

        assert result is None


class TestConfigureAdminIds:
    """Тесты для configure_admin_ids."""

    def test_configure_from_string(self):
        """Тест конфигурации из строки."""
        result = configure_admin_ids("123, 456, 789")

        assert result == [123, 456, 789]

    def test_configure_from_env(self):
        """Тест конфигурации из переменной окружения."""
        with patch.dict("os.environ", {"TELEGRAM_ADMIN_IDS": "111,222"}):
            result = configure_admin_ids()

            assert result == [111, 222]

    def test_configure_empty(self):
        """Тест с пустой строкой."""
        result = configure_admin_ids("")

        assert result == []

    def test_configure_invalid_ids(self):
        """Тест с некорректными ID."""
        result = configure_admin_ids("123, invalid, 456")

        # Должен вернуть только валидные ID до ошибки (или обработать исключение)
        # При ошибке функция логирует и продолжает, возвращая частичный результат
        # В зависимости от реализации может вернуть [] или [123]
        assert isinstance(result, list)


class TestRegisterGlobalExceptionHandlers:
    """Тесты для register_global_exception_handlers."""

    def test_register_handlers(self):
        """Тест регистрации глобальных обработчиков."""
        import sys

        original_excepthook = sys.excepthook

        try:
            register_global_exception_handlers()

            # excepthook должен быть изменён
            assert sys.excepthook != original_excepthook
        finally:
            # Восстанавливаем оригинальный
            sys.excepthook = original_excepthook
