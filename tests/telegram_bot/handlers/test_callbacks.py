"""Тесты для модуля callbacks.py.

Этот модуль тестирует обработчики callback-запросов от inline-кнопок.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.telegram_bot.handlers.callbacks import (
    arbitrage_callback_impl,
    handle_arbitrage_pagination,
    handle_best_opportunities_impl,
    handle_dmarket_arbitrage_impl,
    handle_game_selected_impl,
    handle_game_selection_impl,
    handle_market_comparison_impl,
    show_arbitrage_opportunities,
)


@pytest.fixture()
def mock_update():
    """Создать мок Update с callback_query."""
    update = MagicMock(spec=Update)
    update.callback_query = AsyncMock(spec=CallbackQuery)
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.answer = AsyncMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123456789
    update.effective_user.username = "test_user"
    # Also mock message for error handling
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture()
def mock_context():
    """Создать мок ContextTypes.DEFAULT_TYPE."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.bot_data = {}  # Empty dict so router is None and we use legacy callbacks
    return context


@pytest.fixture()
def sample_opportunities():
    """Создать примеры арбитражных возможностей."""
    return [
        {
            "item_name": "AK-47 | Redline (FT)",
            "buy_price": 10.50,
            "sell_price": 12.00,
            "profit": 1.11,
            "profit_percent": 10.57,
            "game": "csgo",
        },
        {
            "item_name": "AWP | Asiimov (FT)",
            "buy_price": 50.00,
            "sell_price": 55.00,
            "profit": 4.11,
            "profit_percent": 8.22,
            "game": "csgo",
        },
        {
            "item_name": "M4A4 | Howl (FT)",
            "buy_price": 500.00,
            "sell_price": 550.00,
            "profit": 41.15,
            "profit_percent": 8.23,
            "game": "csgo",
        },
    ]


@pytest.fixture()
def extended_opportunities():
    """Создать расширенный список для тестирования пагинации (2 страницы)."""
    return [
        {
            "item_name": "AK-47 | Redline (FT)",
            "buy_price": 10.50,
            "sell_price": 12.00,
            "profit": 1.11,
            "profit_percent": 10.57,
            "game": "csgo",
        },
        {
            "item_name": "AWP | Asiimov (FT)",
            "buy_price": 50.00,
            "sell_price": 55.00,
            "profit": 4.11,
            "profit_percent": 8.22,
            "game": "csgo",
        },
        {
            "item_name": "M4A4 | Howl (FT)",
            "buy_price": 500.00,
            "sell_price": 550.00,
            "profit": 41.15,
            "profit_percent": 8.23,
            "game": "csgo",
        },
        {
            "item_name": "Desert Eagle | Blaze (FT)",
            "buy_price": 75.00,
            "sell_price": 82.00,
            "profit": 6.26,
            "profit_percent": 8.35,
            "game": "csgo",
        },
        {
            "item_name": "Glock-18 | Fade (FN)",
            "buy_price": 300.00,
            "sell_price": 330.00,
            "profit": 27.10,
            "profit_percent": 9.03,
            "game": "csgo",
        },
        {
            "item_name": "USP-S | Kill Confirmed (MW)",
            "buy_price": 100.00,
            "sell_price": 110.00,
            "profit": 9.23,
            "profit_percent": 9.23,
            "game": "csgo",
        },
    ]


class TestArbitrageCallbackImpl:
    """Тесты для arbitrage_callback_impl."""

    @pytest.mark.asyncio
    @patch("src.telegram_bot.handlers.callbacks.auto_trade_start")
    async def test_arbitrage_callback_redirects_to_auto_trade(
        self,
        mock_auto_trade_start,
        mock_update,
        mock_context,
    ):
        """Тест редиректа на auto_trade меню."""
        # Arrange
        mock_auto_trade_start.return_value = None

        # Act
        await arbitrage_callback_impl(mock_update, mock_context)

        # Assert
        mock_auto_trade_start.assert_called_once_with(mock_update, mock_context)

    @pytest.mark.asyncio
    @patch("src.telegram_bot.handlers.callbacks.auto_trade_start")
    async def test_arbitrage_callback_calls_auto_trade(
        self,
        mock_auto_trade_start,
        mock_update,
        mock_context,
    ):
        """Тест вызова auto_trade_start."""
        # Arrange
        mock_auto_trade_start.return_value = None

        # Act
        await arbitrage_callback_impl(mock_update, mock_context)

        # Assert
        mock_auto_trade_start.assert_called_once()


class TestHandleDmarketArbitrageImpl:
    """Тесты для handle_dmarket_arbitrage_impl."""

    @pytest.mark.asyncio
    @patch("src.telegram_bot.handlers.callbacks.auto_trade_start")
    async def test_dmarket_arbitrage_redirects_to_auto_trade(
        self,
        mock_auto_trade_start,
        mock_update,
        mock_context,
    ):
        """Тест редиректа на auto_trade меню."""
        # Arrange
        mock_auto_trade_start.return_value = None

        # Act
        await handle_dmarket_arbitrage_impl(mock_update, mock_context, mode="normal")

        # Assert
        mock_auto_trade_start.assert_called_once_with(mock_update, mock_context)

    @pytest.mark.asyncio
    @patch("src.telegram_bot.handlers.callbacks.auto_trade_start")
    async def test_dmarket_arbitrage_ignores_mode_parameter(
        self,
        mock_auto_trade_start,
        mock_update,
        mock_context,
    ):
        """Тест что параметр mode игнорируется (редирект)."""
        # Arrange
        mock_auto_trade_start.return_value = None

        # Act
        await handle_dmarket_arbitrage_impl(mock_update, mock_context, mode="aggressive")

        # Assert
        mock_auto_trade_start.assert_called_once_with(mock_update, mock_context)

    @pytest.mark.asyncio
    @patch("src.telegram_bot.handlers.callbacks.auto_trade_start")
    async def test_dmarket_arbitrage_with_default_mode(
        self,
        mock_auto_trade_start,
        mock_update,
        mock_context,
    ):
        """Тест с режимом по умолчанию."""
        # Arrange
        mock_auto_trade_start.return_value = None

        # Act
        await handle_dmarket_arbitrage_impl(mock_update, mock_context)

        # Assert
        mock_auto_trade_start.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.telegram_bot.handlers.callbacks.auto_trade_start")
    async def test_dmarket_arbitrage_with_conservative_mode(
        self,
        mock_auto_trade_start,
        mock_update,
        mock_context,
    ):
        """Тест с консервативным режимом (игнорируется)."""
        # Arrange
        mock_auto_trade_start.return_value = None

        # Act
        await handle_dmarket_arbitrage_impl(mock_update, mock_context, mode="conservative")

        # Assert
        mock_auto_trade_start.assert_called_once()


class TestShowArbitrageOpportunities:
    """Тесты для show_arbitrage_opportunities."""

    @pytest.mark.asyncio()
    @patch("src.telegram_bot.handlers.callbacks.format_opportunities")
    @patch("src.telegram_bot.handlers.callbacks.create_pagination_keyboard")
    async def test_show_opportunities_with_pagination(
        self,
        mock_create_keyboard,
        mock_format_opps,
        mock_context,
        sample_opportunities,
    ):
        """Тест отображения возможностей с пагинацией."""
        # Arrange
        mock_query = AsyncMock(spec=CallbackQuery)
        mock_query.edit_message_text = AsyncMock()
        mock_context.user_data["arbitrage_opportunities"] = sample_opportunities
        mock_context.user_data["arbitrage_page"] = 0
        mock_context.user_data["arbitrage_mode"] = "normal"

        mock_format_opps.return_value = "Formatted opportunities"
        mock_keyboard = MagicMock(spec=InlineKeyboardMarkup)
        mock_create_keyboard.return_value = mock_keyboard

        # Act
        await show_arbitrage_opportunities(mock_query, mock_context)

        # Assert
        mock_format_opps.assert_called_once_with(sample_opportunities, 0, 3)
        mock_create_keyboard.assert_called_once()
        mock_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    @patch("src.telegram_bot.handlers.callbacks.format_opportunities")
    @patch("src.telegram_bot.handlers.callbacks.create_pagination_keyboard")
    async def test_show_opportunities_custom_page(
        self,
        mock_create_keyboard,
        mock_format_opps,
        mock_context,
        sample_opportunities,
    ):
        """Тест отображения конкретной страницы."""
        # Arrange
        mock_query = AsyncMock(spec=CallbackQuery)
        mock_query.edit_message_text = AsyncMock()
        mock_context.user_data["arbitrage_opportunities"] = sample_opportunities
        mock_context.user_data["arbitrage_page"] = 0

        mock_format_opps.return_value = "Formatted page 1"
        mock_keyboard = MagicMock(spec=InlineKeyboardMarkup)
        mock_create_keyboard.return_value = mock_keyboard

        # Act - передаем page=1, но функция пересчитывает до 0
        # (только 1 страница)
        await show_arbitrage_opportunities(mock_query, mock_context, page=1)

        # Assert - функция сбрасывает на 0 т.к. 3 предмета = 1 страница
        mock_format_opps.assert_called_once_with(sample_opportunities, 0, 3)
        assert mock_context.user_data["arbitrage_page"] == 0


class TestHandleArbitragePagination:
    """Тесты для handle_arbitrage_pagination."""

    @pytest.mark.asyncio()
    @patch("src.telegram_bot.handlers.callbacks.show_arbitrage_opportunities")
    async def test_pagination_next_page(
        self,
        mock_show_opps,
        mock_context,
        extended_opportunities,
    ):
        """Тест перехода на следующую страницу (используем 6 элементов)."""
        # Arrange
        mock_query = AsyncMock(spec=CallbackQuery)
        mock_context.user_data["arbitrage_page"] = 0
        mock_context.user_data["arbitrage_opportunities"] = extended_opportunities

        # Act
        await handle_arbitrage_pagination(mock_query, mock_context, "next_page")

        # Assert
        assert mock_context.user_data["arbitrage_page"] == 1
        mock_show_opps.assert_called_once_with(mock_query, mock_context, 1)

    @pytest.mark.asyncio()
    @patch("src.telegram_bot.handlers.callbacks.show_arbitrage_opportunities")
    async def test_pagination_prev_page(
        self,
        mock_show_opps,
        mock_context,
        sample_opportunities,
    ):
        """Тест перехода на предыдущую страницу."""
        # Arrange
        mock_query = AsyncMock(spec=CallbackQuery)
        mock_context.user_data["arbitrage_page"] = 1
        mock_context.user_data["arbitrage_opportunities"] = sample_opportunities

        # Act
        await handle_arbitrage_pagination(mock_query, mock_context, "prev_page")

        # Assert
        assert mock_context.user_data["arbitrage_page"] == 0
        mock_show_opps.assert_called_once_with(mock_query, mock_context, 0)

    @pytest.mark.asyncio()
    @patch("src.telegram_bot.handlers.callbacks.show_arbitrage_opportunities")
    async def test_pagination_stays_at_first_page(
        self,
        mock_show_opps,
        mock_context,
        sample_opportunities,
    ):
        """Тест что не переходим за первую страницу."""
        # Arrange
        mock_query = AsyncMock(spec=CallbackQuery)
        mock_context.user_data["arbitrage_page"] = 0
        mock_context.user_data["arbitrage_opportunities"] = sample_opportunities

        # Act
        await handle_arbitrage_pagination(mock_query, mock_context, "prev_page")

        # Assert
        assert mock_context.user_data["arbitrage_page"] == 0

    @pytest.mark.asyncio()
    @patch("src.telegram_bot.handlers.callbacks.show_arbitrage_opportunities")
    async def test_pagination_stays_at_last_page(
        self,
        mock_show_opps,
        mock_context,
        sample_opportunities,
    ):
        """Тест что не переходим за последнюю страницу."""
        # Arrange
        mock_query = AsyncMock(spec=CallbackQuery)
        # 3 возможности = 1 страница (0-indexed)
        mock_context.user_data["arbitrage_page"] = 0
        mock_context.user_data["arbitrage_opportunities"] = sample_opportunities

        # Act
        await handle_arbitrage_pagination(mock_query, mock_context, "next_page")

        # Assert - 3 итема дают ровно 1 страницу, не можем перейти дальше
        assert mock_context.user_data["arbitrage_page"] == 0


class TestHandleBestOpportunitiesImpl:
    """Тесты для handle_best_opportunities_impl."""

    @pytest.mark.asyncio()
    @patch("src.telegram_bot.handlers.callbacks.handle_dmarket_arbitrage_impl")
    async def test_calls_arbitrage_with_best_mode(
        self,
        mock_handle_arbitrage,
        mock_update,
        mock_context,
    ):
        """Тест вызова с режимом 'best'."""
        # Act
        await handle_best_opportunities_impl(mock_update, mock_context)

        # Assert
        mock_handle_arbitrage.assert_called_once_with(
            mock_update,
            mock_context,
            mode="best",
        )


class TestHandleGameSelectionImpl:
    """Тесты для handle_game_selection_impl."""

    @pytest.mark.asyncio()
    @patch("src.telegram_bot.handlers.callbacks.get_game_selection_keyboard")
    async def test_shows_game_selection_menu(
        self,
        mock_get_keyboard,
        mock_update,
        mock_context,
    ):
        """Тест отображения меню выбора игры."""
        # Arrange
        mock_keyboard = MagicMock(spec=InlineKeyboardMarkup)
        mock_get_keyboard.return_value = mock_keyboard

        # Act
        await handle_game_selection_impl(mock_update, mock_context)

        # Assert
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Выберите игру" in call_args.args[0]
        assert call_args.kwargs["reply_markup"] == mock_keyboard


class TestHandleGameSelectedImpl:
    """Тесты для handle_game_selected_impl."""

    @pytest.mark.asyncio
    @patch("src.telegram_bot.handlers.callbacks.handle_dmarket_arbitrage_impl")
    async def test_successful_game_selection(
        self,
        mock_dmarket_impl,
        mock_update,
        mock_context,
    ):
        """Тест успешного выбора игры."""
        # Arrange
        mock_update.callback_query.data = "game_selected:csgo"
        mock_dmarket_impl.return_value = None

        # Act
        await handle_game_selected_impl(mock_update, mock_context, game="csgo")

        # Assert
        assert mock_context.user_data.get("selected_game") == "csgo"
        mock_update.callback_query.edit_message_text.assert_called_once()
        mock_dmarket_impl.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.telegram_bot.handlers.callbacks.handle_dmarket_arbitrage_impl")
    async def test_game_selection_with_dota2(
        self,
        mock_dmarket_impl,
        mock_update,
        mock_context,
    ):
        """Тест выбора Dota 2."""
        # Arrange
        mock_dmarket_impl.return_value = None

        # Act
        await handle_game_selected_impl(mock_update, mock_context, game="dota2")

        # Assert
        assert mock_context.user_data.get("selected_game") == "dota2"

    @pytest.mark.asyncio
    @patch("src.telegram_bot.handlers.callbacks.handle_dmarket_arbitrage_impl")
    async def test_game_selection_extracts_from_callback_data(
        self,
        mock_dmarket_impl,
        mock_update,
        mock_context,
    ):
        """Тест извлечения игры из callback_data."""
        # Arrange
        mock_update.callback_query.data = "game_selected:rust"
        mock_dmarket_impl.return_value = None

        # Act
        await handle_game_selected_impl(mock_update, mock_context)

        # Assert
        assert mock_context.user_data.get("selected_game") == "rust"

    @pytest.mark.asyncio
    async def test_returns_early_without_callback_query(self, mock_context):
        """Тест раннего выхода без callback_query."""
        # Arrange
        update = MagicMock(spec=Update)
        update.callback_query = None

        # Act
        await handle_game_selected_impl(update, mock_context, game="csgo")

        # Assert - no error should be raised

    @pytest.mark.asyncio
    async def test_returns_early_without_game(
        self,
        mock_update,
        mock_context,
    ):
        """Тест раннего выхода без игры."""
        # Arrange
        mock_update.callback_query.data = "other_callback"

        # Act
        await handle_game_selected_impl(mock_update, mock_context)

        # Assert - no edit_message_text should be called
        mock_update.callback_query.edit_message_text.assert_not_called()


class TestHandleMarketComparisonImpl:
    """Тесты для handle_market_comparison_impl."""

    @pytest.mark.asyncio()
    async def test_shows_market_comparison_placeholder(
        self,
        mock_update,
        mock_context,
    ):
        """Тест отображения заглушки сравнения рынков."""
        # Act
        await handle_market_comparison_impl(mock_update, mock_context)

        # Assert
        mock_update.callback_query.edit_message_text.assert_called_once()
        # Проверяем что вызов был сделан (заглушка может содержать любой текст)


class TestButtonCallbackHandler:
    """Тесты для button_callback_handler - основного роутера callbacks."""

    @pytest.mark.asyncio()
    async def test_handles_none_query(self, mock_context):
        """Тест обработки update без callback_query."""
        # Arrange
        from src.telegram_bot.handlers.callbacks import button_callback_handler

        update = MagicMock(spec=Update)
        update.callback_query = None

        # Act
        await button_callback_handler(update, mock_context)

        # Assert - функция должна вернуться без ошибок
        # Ничего не вызывается, т.к. query = None

    @pytest.mark.asyncio()
    async def test_handles_none_callback_data(self, mock_context):
        """Тест обработки callback_query без данных."""
        # Arrange
        from src.telegram_bot.handlers.callbacks import button_callback_handler

        update = MagicMock(spec=Update)
        update.callback_query = AsyncMock(spec=CallbackQuery)
        update.callback_query.data = None

        # Act
        await button_callback_handler(update, mock_context)

        # Assert - функция должна вернуться без ошибок
        update.callback_query.answer.assert_not_called()

    @pytest.mark.asyncio()
    @patch("src.telegram_bot.handlers.callbacks.get_game_selection_keyboard")
    async def test_routes_search_callback(
        self, mock_get_keyboard, mock_update, mock_context
    ):
        """Тест маршрутизации callback_data='search'."""
        # Arrange
        from src.telegram_bot.handlers.callbacks import button_callback_handler

        mock_update.callback_query.data = "search"
        mock_keyboard = MagicMock()
        mock_get_keyboard.return_value = mock_keyboard

        # Act
        await button_callback_handler(mock_update, mock_context)

        # Assert
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        # Текст может быть в args[0] или kwargs['text']
        text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
        assert "Поиск предметов" in text

    @pytest.mark.asyncio
    @patch("src.telegram_bot.handlers.callbacks.auto_trade_start")
    async def test_routes_arbitrage_callback(
        self, mock_auto_trade_start, mock_update, mock_context
    ):
        """Тест маршрутизации callback_data='arbitrage'."""
        # Arrange
        from src.telegram_bot.handlers.callbacks import button_callback_handler

        mock_update.callback_query.data = "arbitrage"
        mock_auto_trade_start.return_value = None

        # Act
        await button_callback_handler(mock_update, mock_context)

        # Assert - answer is called at least once (at start of handler)
        assert mock_update.callback_query.answer.call_count >= 1
        mock_auto_trade_start.assert_called_once_with(mock_update, mock_context)

    @pytest.mark.asyncio
    @patch("src.telegram_bot.handlers.callbacks.auto_trade_start")
    async def test_routes_dmarket_arbitrage_callback(
        self, mock_auto_trade_start, mock_update, mock_context
    ):
        """Тест маршрутизации callback_data='dmarket_arbitrage'."""
        # Arrange
        from src.telegram_bot.handlers.callbacks import button_callback_handler

        mock_update.callback_query.data = "dmarket_arbitrage"
        mock_auto_trade_start.return_value = None

        # Act
        await button_callback_handler(mock_update, mock_context)

        # Assert - answer is called at least once (at start of handler)
        assert mock_update.callback_query.answer.call_count >= 1
        mock_auto_trade_start.assert_called_once_with(mock_update, mock_context)

    @pytest.mark.asyncio()
    @patch("src.telegram_bot.handlers.callbacks.handle_game_selected_impl")
    async def test_routes_game_selected_callback(
        self, mock_game_selected, mock_update, mock_context
    ):
        """Тест маршрутизации callback_data='game_selected:csgo'."""
        # Arrange
        from src.telegram_bot.handlers.callbacks import button_callback_handler

        mock_update.callback_query.data = "game_selected:csgo"

        # Act
        await button_callback_handler(mock_update, mock_context)

        # Assert
        mock_update.callback_query.answer.assert_called_once()
        mock_game_selected.assert_called_once_with(
            mock_update, mock_context, game="csgo"
        )

    @pytest.mark.asyncio()
    @patch("src.telegram_bot.handlers.callbacks.handle_arbitrage_pagination")
    async def test_routes_pagination_next_page(
        self, mock_pagination, mock_update, mock_context
    ):
        """Тест маршрутизации пагинации (следующая страница)."""
        # Arrange
        from src.telegram_bot.handlers.callbacks import button_callback_handler

        mock_update.callback_query.data = "arb_next_page_1"

        # Act
        await button_callback_handler(mock_update, mock_context)

        # Assert
        mock_update.callback_query.answer.assert_called_once()
        mock_pagination.assert_called_once_with(
            mock_update.callback_query, mock_context, "next_page"
        )

    @pytest.mark.asyncio()
    @patch("src.telegram_bot.handlers.callbacks.handle_arbitrage_pagination")
    async def test_routes_pagination_prev_page(
        self, mock_pagination, mock_update, mock_context
    ):
        """Тест маршрутизации пагинации (предыдущая страница)."""
        # Arrange
        from src.telegram_bot.handlers.callbacks import button_callback_handler

        mock_update.callback_query.data = "arb_prev_page_0"

        # Act
        await button_callback_handler(mock_update, mock_context)

        # Assert
        mock_update.callback_query.answer.assert_called_once()
        mock_pagination.assert_called_once_with(
            mock_update.callback_query, mock_context, "prev_page"
        )

    @pytest.mark.asyncio
    @patch("src.telegram_bot.handlers.callbacks.get_back_to_arbitrage_keyboard")
    async def test_handles_unknown_callback(
        self, mock_get_keyboard, mock_update, mock_context
    ):
        """Тест обработки неизвестного callback_data."""
        # Arrange
        from src.telegram_bot.handlers.callbacks import button_callback_handler

        mock_update.callback_query.data = "unknown_callback_12345"
        mock_keyboard = MagicMock()
        mock_get_keyboard.return_value = mock_keyboard

        # Act
        await button_callback_handler(mock_update, mock_context)

        # Assert - answer is called at least once
        assert mock_update.callback_query.answer.call_count >= 1
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        # Текст может быть в args[0] или kwargs['text']
        text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
        assert "Неизвестная команда" in text

    @pytest.mark.asyncio
    @patch("src.telegram_bot.handlers.callbacks.get_back_to_arbitrage_keyboard")
    async def test_handles_exception_gracefully(
        self, mock_get_keyboard, mock_update, mock_context
    ):
        """Тест обработки исключений в роутере."""
        # Arrange
        from src.telegram_bot.handlers.callbacks import button_callback_handler

        mock_update.callback_query.data = "arbitrage"
        # Вызываем ошибку при редактировании сообщения
        mock_update.callback_query.edit_message_text.side_effect = [
            Exception("Test error"),
            None,  # ВтоSwarm вызов для сообщения об ошибке
        ]
        mock_keyboard = MagicMock()
        mock_get_keyboard.return_value = mock_keyboard

        # Act
        await button_callback_handler(mock_update, mock_context)

        # Assert - answer is called at least once (at start of handler)
        assert mock_update.callback_query.answer.call_count >= 1
        # Должно быть 2 вызова: первый с ошибкой, втоSwarm - сообщение об ошибке
        assert mock_update.callback_query.edit_message_text.call_count == 2
