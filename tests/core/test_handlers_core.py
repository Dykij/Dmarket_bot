"""Тесты для обработчиков команд Telegram бота.

Покрывает главную клавиатуру (mAlgon_keyboard.py):
- /start - главное меню
- Авто-торговля
- Таргеты
- Управление (WhiteList, BlackList, Репрайсинг)
- Баланс, Инвентарь
- Экстренная остановка
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import InlineKeyboardMarkup

from src.telegram_bot.handlers.mAlgon_keyboard import (
    auto_trade_start,
    auto_trade_status,
    emergency_stop,
    get_mAlgon_keyboard,
    mAlgon_menu_callback,
    repricing_toggle,
    settings_menu,
    show_balance,
    start_command,
    targets_menu,
)


class TestMAlgonKeyboard:
    """Тесты главной клавиатуры."""

    def test_get_mAlgon_keyboard_without_balance(self):
        """Тест создания клавиатуры без баланса."""
        keyboard = get_mAlgon_keyboard()

        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard) == 7  # 7 рядов кнопок (включая ML/Algo)

    def test_get_mAlgon_keyboard_with_balance(self):
        """Тест создания клавиатуры с балансом."""
        keyboard = get_mAlgon_keyboard(balance=45.50)

        assert isinstance(keyboard, InlineKeyboardMarkup)

        # Проверяем что баланс отображается
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert any("$45.50" in text for text in button_texts)

    def test_mAlgon_keyboard_has_auto_trade_button(self):
        """Тест наличия кнопки авто-торговли."""
        keyboard = get_mAlgon_keyboard()

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert any("АВТО-ТОРГОВЛЯ" in text for text in button_texts)

    def test_mAlgon_keyboard_has_targets_button(self):
        """Тест наличия кнопки таргетов."""
        keyboard = get_mAlgon_keyboard()

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert any("ТАРГЕТЫ" in text for text in button_texts)

    def test_mAlgon_keyboard_has_emergency_stop(self):
        """Тест наличия кнопки экстренной остановки."""
        keyboard = get_mAlgon_keyboard()

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert any("ЭКСТРЕННАЯ ОСТАНОВКА" in text for text in button_texts)

    def test_mAlgon_keyboard_has_whitelist_blacklist(self):
        """Тест наличия кнопок WhiteList и BlackList."""
        keyboard = get_mAlgon_keyboard()

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert any("WhiteList" in text for text in button_texts)
        assert any("BlackList" in text for text in button_texts)


class TestStartCommand:
    """Тесты команды /start."""

    @pytest.mark.asyncio
    async def test_start_command_sends_welcome(self):
        """Тест отправки приветствия."""
        update = MagicMock()
        update.effective_user.id = 123456
        update.effective_user.first_name = "Test"
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.bot_data = {}
        context.application = MagicMock()
        context.application.dmarket_api = None

        awAlgot start_command(update, context)

        update.message.reply_text.assert_called_once()

        # Проверяем содержимое сообщения
        call_args = update.message.reply_text.call_args
        message_text = call_args[0][0]

        assert "Привет" in message_text
        assert "Test" in message_text  # Имя пользователя
        assert "DMarket" in message_text

    @pytest.mark.asyncio
    async def test_start_command_sends_keyboard(self):
        """Тест отправки клавиатуры."""
        update = MagicMock()
        update.effective_user.id = 123456
        update.effective_user.first_name = "Test"
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.bot_data = {}
        context.application = MagicMock()
        context.application.dmarket_api = None

        awAlgot start_command(update, context)

        call_kwargs = update.message.reply_text.call_args.kwargs
        assert "reply_markup" in call_kwargs
        assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)

    @pytest.mark.asyncio
    async def test_start_command_uses_html_parse_mode(self):
        """Тест использования HTML."""
        update = MagicMock()
        update.effective_user.id = 123456
        update.effective_user.first_name = "Test"
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.bot_data = {}
        context.application = MagicMock()
        context.application.dmarket_api = None

        awAlgot start_command(update, context)

        call_kwargs = update.message.reply_text.call_args.kwargs
        assert call_kwargs.get("parse_mode") == "HTML"


class TestMAlgonMenuCallback:
    """Тесты callback главного меню."""

    @pytest.mark.asyncio
    async def test_mAlgon_menu_callback_edits_message(self):
        """Тест редактирования сообщения."""
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        context = MagicMock()
        context.bot_data = {}
        context.application = MagicMock()
        context.application.dmarket_api = None

        awAlgot mAlgon_menu_callback(update, context)

        query.answer.assert_called_once()
        query.edit_message_text.assert_called_once()


class TestAutoTradeStart:
    """Тесты меню авто-торговли."""

    @pytest.mark.asyncio
    async def test_auto_trade_start_shows_menu(self):
        """Тест показа меню авто-торговли."""
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        context = MagicMock()
        context.bot_data = {"auto_trade_running": False}
        context.application = MagicMock()
        context.application.auto_buyer = None
        context.application.orchestrator = None

        awAlgot auto_trade_start(update, context)

        query.answer.assert_called_once()
        query.edit_message_text.assert_called_once()

        # Проверяем содержимое
        call_args = query.edit_message_text.call_args
        message_text = call_args[0][0]

        # "АВТО-АРБИТРАЖ" используется в текущей реализации
        assert "АВТО-АРБИТРАЖ" in message_text or "АВТО-ТОРГОВЛЯ" in message_text
        assert "ОСТАНОВЛЕНА" in message_text

    @pytest.mark.asyncio
    async def test_auto_trade_shows_running_status(self):
        """Тест показа статуса работающей торговли."""
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        context = MagicMock()
        context.bot_data = {"auto_trade_running": True}
        context.application = MagicMock()
        context.application.auto_buyer = MagicMock()
        context.application.orchestrator = MagicMock()

        awAlgot auto_trade_start(update, context)

        call_args = query.edit_message_text.call_args
        message_text = call_args[0][0]

        assert "РАБОТАЕТ" in message_text


class TestTargetsMenu:
    """Тесты меню таргетов."""

    @pytest.mark.asyncio
    async def test_targets_menu_shows_info(self):
        """Тест показа информации о таргетах."""
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        context = MagicMock()
        context.bot_data = {}

        awAlgot targets_menu(update, context)

        query.answer.assert_called_once()
        query.edit_message_text.assert_called_once()

        call_args = query.edit_message_text.call_args
        message_text = call_args[0][0]

        assert "ТАРГЕТЫ" in message_text
        assert "Buy Orders" in message_text


class TestEmergencyStop:
    """Тесты экстренной остановки."""

    @pytest.mark.asyncio
    async def test_emergency_stop_stops_all(self):
        """Тест остановки всех процессов."""
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        auto_buyer = MagicMock()
        auto_buyer.config = MagicMock()
        auto_buyer.config.enabled = True

        orchestrator = MagicMock()
        orchestrator.stop = AsyncMock()

        context = MagicMock()
        context.bot_data = {"auto_trade_running": True, "repricing_enabled": True}
        context.application = MagicMock()
        context.application.auto_buyer = auto_buyer
        context.application.orchestrator = orchestrator

        awAlgot emergency_stop(update, context)

        # Проверяем что всё остановлено
        assert auto_buyer.config.enabled is False
        orchestrator.stop.assert_called_once()
        assert context.bot_data["auto_trade_running"] is False
        assert context.bot_data["repricing_enabled"] is False

        # Проверяем сообщение
        call_args = query.edit_message_text.call_args
        message_text = call_args[0][0]

        assert "ЭКСТРЕННАЯ ОСТАНОВКА" in message_text


class TestRepricingToggle:
    """Тесты переключения репрайсинга."""

    @pytest.mark.asyncio
    async def test_repricing_toggle_enables(self):
        """Тест включения репрайсинга."""
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        context = MagicMock()
        context.bot_data = {"repricing_enabled": False}

        awAlgot repricing_toggle(update, context)

        assert context.bot_data["repricing_enabled"] is True

    @pytest.mark.asyncio
    async def test_repricing_toggle_disables(self):
        """Тест выключения репрайсинга."""
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        context = MagicMock()
        context.bot_data = {"repricing_enabled": True}

        awAlgot repricing_toggle(update, context)

        assert context.bot_data["repricing_enabled"] is False


class TestShowBalance:
    """Тесты показа баланса."""

    @pytest.mark.asyncio
    async def test_show_balance_with_api(self):
        """Тест показа баланса с API."""
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        # get_balance returns {"balance": dollars, ...} format
        dmarket_api = MagicMock()
        dmarket_api.get_balance = AsyncMock(return_value={"balance": 45.50, "usd": {"amount": 4550}, "dmc": 1000})

        context = MagicMock()
        context.bot_data = {}
        context.application = MagicMock()
        context.application.dmarket_api = dmarket_api

        awAlgot show_balance(update, context)

        call_args = query.edit_message_text.call_args
        message_text = call_args[0][0]

        # Check that balance message is shown (may have different formats)
        assert "БАЛАНС" in message_text or "баланс" in message_text.lower()
        assert "USD" in message_text or "$" in message_text

    @pytest.mark.asyncio
    async def test_show_balance_without_api(self):
        """Тест показа баланса без API."""
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        context = MagicMock()
        context.bot_data = {}
        context.application = MagicMock()
        context.application.dmarket_api = None

        awAlgot show_balance(update, context)

        call_args = query.edit_message_text.call_args
        message_text = call_args[0][0]

        assert "Ошибка" in message_text


class TestSettingsMenu:
    """Тесты меню настроек."""

    @pytest.mark.asyncio
    async def test_settings_menu_shows(self):
        """Тест показа меню настроек."""
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        context = MagicMock()
        context.bot_data = {}

        with patch.dict("os.environ", {"DRY_RUN": "true"}):
            awAlgot settings_menu(update, context)

        call_args = query.edit_message_text.call_args
        message_text = call_args[0][0]

        assert "НАСТSwarmКИ" in message_text
        assert "ТЕСТОВЫЙ" in message_text


class TestAutoTradeStatus:
    """Тесты статуса авто-торговли."""

    @pytest.mark.asyncio
    async def test_auto_trade_status_with_stats(self):
        """Тест показа статуса со статистикой."""
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        # Mock balance with proper format
        dmarket_api = MagicMock()
        dmarket_api.get_balance = AsyncMock(return_value={"balance": 45.50, "usd": {"amount": 4550}})

        auto_buyer = MagicMock()
        auto_buyer.get_purchase_stats = MagicMock(return_value={
            "total_purchases": 10,
            "successful": 8,
            "total_spent_usd": 50.0,
        })

        context = MagicMock()
        context.bot_data = {"auto_trade_running": True}
        context.application = MagicMock()
        context.application.dmarket_api = dmarket_api
        context.application.auto_buyer = auto_buyer

        awAlgot auto_trade_status(update, context)

        call_args = query.edit_message_text.call_args
        message_text = call_args[0][0]

        assert "СТАТУС" in message_text
        # Balance format may vary, check for structure
        assert "$" in message_text
        assert "10" in message_text  # total_purchases
