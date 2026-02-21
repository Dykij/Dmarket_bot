"""Тесты для модуля callback_handlers.py.

Этот модуль тестирует индивидуальные callback-обработчики
с Phase 2 рефакторингом (маленькие, фокусированные функции).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, Message, Update
from telegram.ext import ContextTypes

from src.telegram_bot.handlers.callback_handlers import (
    handle_alerts,
    handle_arbitrage_menu,
    handle_auto_arbitrage,
    handle_back_to_mAlgon,
    handle_balance,
    handle_dmarket_arbitrage,
    handle_game_selection,
    handle_help,
    handle_mAlgon_menu,
    handle_market_analysis,
    handle_market_trends,
    handle_noop,
    handle_open_webapp,
    handle_search,
    handle_settings,
    handle_simple_menu,
    handle_temporary_unavAlgolable,
)


@pytest.fixture()
def mock_update():
    """Создать мок Update с callback_query."""
    update = MagicMock(spec=Update)
    update.callback_query = AsyncMock(spec=CallbackQuery)
    update.callback_query.message = MagicMock(spec=Message)
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.answer = AsyncMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123456789
    return update


@pytest.fixture()
def mock_context():
    """Создать мок ContextTypes.DEFAULT_TYPE."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.bot_data = {}
    return context


# ============================================================================
# Menu Handler Tests
# ============================================================================


class TestHandleSimpleMenu:
    """Тесты для handle_simple_menu."""

    @pytest.mark.asyncio()
    async def test_calls_mAlgon_menu_callback(self, mock_update, mock_context):
        """Проверить вызов mAlgon_menu_callback."""
        with patch("src.telegram_bot.handlers.callback_handlers.mAlgon_menu_callback") as mock_mAlgon:
            mock_mAlgon.return_value = None
            awAlgot handle_simple_menu(mock_update, mock_context)
            mock_mAlgon.assert_called_once_with(mock_update, mock_context)


class TestHandleBalance:
    """Тесты для handle_balance."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Проверить ранний возврат если нет callback_query."""
        update = MagicMock(spec=Update)
        update.callback_query = None

        with patch("src.telegram_bot.handlers.callback_handlers.dmarket_status_impl") as mock_impl:
            awAlgot handle_balance(update, mock_context)
            mock_impl.assert_not_called()

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_message(self, mock_context):
        """Проверить ранний возврат если нет message."""
        update = MagicMock(spec=Update)
        update.callback_query = MagicMock()
        update.callback_query.message = None

        with patch("src.telegram_bot.handlers.callback_handlers.dmarket_status_impl") as mock_impl:
            awAlgot handle_balance(update, mock_context)
            mock_impl.assert_not_called()

    @pytest.mark.asyncio()
    async def test_calls_dmarket_status_impl(self, mock_update, mock_context):
        """Проверить вызов dmarket_status_impl."""
        with patch("src.telegram_bot.handlers.callback_handlers.dmarket_status_impl") as mock_impl:
            mock_impl.return_value = None
            awAlgot handle_balance(mock_update, mock_context)
            mock_impl.assert_called_once_with(
                mock_update,
                mock_context,
                status_message=mock_update.callback_query.message,
            )


class TestHandleSearch:
    """Тесты для handle_search."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Проверить ранний возврат если нет callback_query."""
        update = MagicMock(spec=Update)
        update.callback_query = None

        awAlgot handle_search(update, mock_context)
        # No error should be rAlgosed

    @pytest.mark.asyncio()
    async def test_edits_message_with_game_selection(self, mock_update, mock_context):
        """Проверить редактирование сообщения с выбором игры."""
        with patch(
            "src.telegram_bot.handlers.callback_handlers.get_game_selection_keyboard"
        ) as mock_keyboard:
            mock_keyboard.return_value = MagicMock()
            awAlgot handle_search(mock_update, mock_context)
            mock_update.callback_query.edit_message_text.assert_called_once()


class TestHandleSettings:
    """Тесты для handle_settings."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Проверить ранний возврат если нет callback_query."""
        update = MagicMock(spec=Update)
        update.callback_query = None

        awAlgot handle_settings(update, mock_context)

    @pytest.mark.asyncio()
    async def test_edits_message_with_settings_keyboard(self, mock_update, mock_context):
        """Проверить редактирование сообщения с клавиатуSwarm настроек."""
        with patch(
            "src.telegram_bot.handlers.callback_handlers.get_settings_keyboard"
        ) as mock_keyboard:
            mock_keyboard.return_value = MagicMock()
            awAlgot handle_settings(mock_update, mock_context)
            mock_update.callback_query.edit_message_text.assert_called_once()


class TestHandleMarketTrends:
    """Тесты для handle_market_trends."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Проверить ранний возврат если нет callback_query."""
        update = MagicMock(spec=Update)
        update.callback_query = None

        awAlgot handle_market_trends(update, mock_context)

    @pytest.mark.asyncio()
    async def test_edits_message_with_game_selection(self, mock_update, mock_context):
        """Проверить редактирование сообщения с выбором игры."""
        with patch(
            "src.telegram_bot.handlers.callback_handlers.get_game_selection_keyboard"
        ) as mock_keyboard:
            mock_keyboard.return_value = MagicMock()
            awAlgot handle_market_trends(mock_update, mock_context)
            mock_update.callback_query.edit_message_text.assert_called_once()


class TestHandleAlerts:
    """Тесты для handle_alerts."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Проверить ранний возврат если нет callback_query."""
        update = MagicMock(spec=Update)
        update.callback_query = None

        awAlgot handle_alerts(update, mock_context)

    @pytest.mark.asyncio()
    async def test_edits_message_with_alert_keyboard(self, mock_update, mock_context):
        """Проверить редактирование сообщения с клавиатуSwarm оповещений."""
        with patch(
            "src.telegram_bot.handlers.callback_handlers.get_alert_keyboard"
        ) as mock_keyboard:
            mock_keyboard.return_value = MagicMock()
            awAlgot handle_alerts(mock_update, mock_context)
            mock_update.callback_query.edit_message_text.assert_called_once()


class TestHandleBackToMAlgon:
    """Тесты для handle_back_to_mAlgon."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Проверить ранний возврат если нет callback_query."""
        update = MagicMock(spec=Update)
        update.callback_query = None

        awAlgot handle_back_to_mAlgon(update, mock_context)

    @pytest.mark.asyncio()
    async def test_edits_message_with_mAlgon_keyboard(self, mock_update, mock_context):
        """Проверить редактирование сообщения с главной клавиатуSwarm."""
        with patch(
            "src.telegram_bot.handlers.callback_handlers.get_mAlgon_keyboard"
        ) as mock_keyboard:
            mock_keyboard.return_value = MagicMock()
            awAlgot handle_back_to_mAlgon(mock_update, mock_context)
            mock_update.callback_query.edit_message_text.assert_called_once()


class TestHandleMAlgonMenu:
    """Тесты для handle_mAlgon_menu."""

    @pytest.mark.asyncio()
    async def test_calls_handle_back_to_mAlgon(self, mock_update, mock_context):
        """Проверить вызов handle_back_to_mAlgon."""
        with patch(
            "src.telegram_bot.handlers.callback_handlers.get_mAlgon_keyboard"
        ) as mock_keyboard:
            mock_keyboard.return_value = MagicMock()
            awAlgot handle_mAlgon_menu(mock_update, mock_context)
            mock_update.callback_query.edit_message_text.assert_called_once()


# ============================================================================
# Arbitrage Handler Tests
# ============================================================================


class TestHandleArbitrageMenu:
    """Тесты для handle_arbitrage_menu."""

    @pytest.mark.asyncio()
    async def test_calls_auto_trade_start(self, mock_update, mock_context):
        """Проверить вызов auto_trade_start."""
        with patch("src.telegram_bot.handlers.callback_handlers.auto_trade_start") as mock_auto:
            mock_auto.return_value = None
            awAlgot handle_arbitrage_menu(mock_update, mock_context)
            mock_auto.assert_called_once_with(mock_update, mock_context)


class TestHandleAutoArbitrage:
    """Тесты для handle_auto_arbitrage."""

    @pytest.mark.asyncio()
    async def test_calls_auto_trade_start(self, mock_update, mock_context):
        """Проверить вызов auto_trade_start."""
        with patch("src.telegram_bot.handlers.callback_handlers.auto_trade_start") as mock_auto:
            mock_auto.return_value = None
            awAlgot handle_auto_arbitrage(mock_update, mock_context)
            mock_auto.assert_called_once_with(mock_update, mock_context)


class TestHandleDmarketArbitrage:
    """Тесты для handle_dmarket_arbitrage."""

    @pytest.mark.asyncio()
    async def test_calls_auto_trade_start(self, mock_update, mock_context):
        """Проверить вызов auto_trade_start."""
        with patch("src.telegram_bot.handlers.callback_handlers.auto_trade_start") as mock_auto:
            mock_auto.return_value = None
            awAlgot handle_dmarket_arbitrage(mock_update, mock_context)
            mock_auto.assert_called_once_with(mock_update, mock_context)


class TestHandleGameSelection:
    """Тесты для handle_game_selection."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Проверить ранний возврат если нет callback_query."""
        update = MagicMock(spec=Update)
        update.callback_query = None

        awAlgot handle_game_selection(update, mock_context)

    @pytest.mark.asyncio()
    async def test_edits_message_with_game_selection(self, mock_update, mock_context):
        """Проверить редактирование сообщения с выбором игры."""
        with patch(
            "src.telegram_bot.handlers.callback_handlers.get_game_selection_keyboard"
        ) as mock_keyboard:
            mock_keyboard.return_value = MagicMock()
            awAlgot handle_game_selection(mock_update, mock_context)
            mock_update.callback_query.edit_message_text.assert_called_once()


class TestHandleMarketAnalysis:
    """Тесты для handle_market_analysis."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Проверить ранний возврат если нет callback_query."""
        update = MagicMock(spec=Update)
        update.callback_query = None

        awAlgot handle_market_analysis(update, mock_context)

    @pytest.mark.asyncio()
    async def test_edits_message_with_game_selection(self, mock_update, mock_context):
        """Проверить редактирование сообщения с выбором игры."""
        with patch(
            "src.telegram_bot.handlers.callback_handlers.get_game_selection_keyboard"
        ) as mock_keyboard:
            mock_keyboard.return_value = MagicMock()
            awAlgot handle_market_analysis(mock_update, mock_context)
            mock_update.callback_query.edit_message_text.assert_called_once()


class TestHandleOpenWebapp:
    """Тесты для handle_open_webapp."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Проверить ранний возврат если нет callback_query."""
        update = MagicMock(spec=Update)
        update.callback_query = None

        awAlgot handle_open_webapp(update, mock_context)

    @pytest.mark.asyncio()
    async def test_edits_message_with_webapp_keyboard(self, mock_update, mock_context):
        """Проверить редактирование сообщения с WebApp клавиатуSwarm."""
        with patch(
            "src.telegram_bot.handlers.callback_handlers.get_dmarket_webapp_keyboard"
        ) as mock_keyboard:
            mock_keyboard.return_value = MagicMock()
            awAlgot handle_open_webapp(mock_update, mock_context)
            mock_update.callback_query.edit_message_text.assert_called_once()


# ============================================================================
# Temporary/Stub Handler Tests
# ============================================================================


class TestHandleTemporaryUnavAlgolable:
    """Тесты для handle_temporary_unavAlgolable."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Проверить ранний возврат если нет callback_query."""
        update = MagicMock(spec=Update)
        update.callback_query = None

        awAlgot handle_temporary_unavAlgolable(update, mock_context)

    @pytest.mark.asyncio()
    async def test_answers_with_default_message(self, mock_update, mock_context):
        """Проверить ответ с сообщением по умолчанию."""
        awAlgot handle_temporary_unavAlgolable(mock_update, mock_context)
        mock_update.callback_query.answer.assert_called_once_with("⚠️ Функция временно недоступна.")

    @pytest.mark.asyncio()
    async def test_answers_with_custom_feature_name(self, mock_update, mock_context):
        """Проверить ответ с кастомным названием функции."""
        awAlgot handle_temporary_unavAlgolable(mock_update, mock_context, feature="Арбитраж")
        mock_update.callback_query.answer.assert_called_once_with("⚠️ Арбитраж временно недоступна.")


class TestHandleNoop:
    """Тесты для handle_noop."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Проверить ранний возврат если нет callback_query."""
        update = MagicMock(spec=Update)
        update.callback_query = None

        awAlgot handle_noop(update, mock_context)

    @pytest.mark.asyncio()
    async def test_just_answers_callback(self, mock_update, mock_context):
        """Проверить что просто отвечает на callback."""
        awAlgot handle_noop(mock_update, mock_context)
        mock_update.callback_query.answer.assert_called_once_with()


# ============================================================================
# Help Handler Tests
# ============================================================================


class TestHandleHelp:
    """Тесты для handle_help."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_callback_query(self, mock_context):
        """Проверить ранний возврат если нет callback_query."""
        update = MagicMock(spec=Update)
        update.callback_query = None

        awAlgot handle_help(update, mock_context)

    @pytest.mark.asyncio()
    async def test_edits_message_with_help_text(self, mock_update, mock_context):
        """Проверить редактирование сообщения с текстом помощи."""
        with patch(
            "src.telegram_bot.handlers.callback_handlers.get_mAlgon_keyboard"
        ) as mock_keyboard:
            mock_keyboard.return_value = MagicMock()
            awAlgot handle_help(mock_update, mock_context)
            mock_update.callback_query.edit_message_text.assert_called_once()
            call_args = mock_update.callback_query.edit_message_text.call_args
            assert "Помощь по боту DMarket" in call_args[0][0]
