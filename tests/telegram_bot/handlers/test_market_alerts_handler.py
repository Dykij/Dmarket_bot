"""Тесты для обработчиков управления уведомлениями о рынке."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Update
from telegram.ext import CallbackContext

from src.telegram_bot.handlers.market_alerts_handler import (
    alerts_callback,
    alerts_command,
    initialize_alerts_manager,
    register_alerts_handlers,
)


@pytest.fixture()
def mock_update():
    """Создать мок объекта Update."""
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock()
    update.effective_user.id = 123456789
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.callback_query = MagicMock()
    update.callback_query.from_user = MagicMock()
    update.callback_query.from_user.id = 123456789
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.data = "alerts:toggle:price_changes"
    return update


@pytest.fixture()
def mock_context():
    """Создать мок объекта CallbackContext."""
    return MagicMock(spec=CallbackContext)


@pytest.fixture()
def mock_alerts_manager():
    """Создать мок менеджера уведомлений."""
    manager = MagicMock()
    manager.get_user_subscriptions = MagicMock(return_value=[])
    manager.subscribe = MagicMock(return_value=True)
    manager.unsubscribe = MagicMock(return_value=True)
    manager.unsubscribe_all = MagicMock(return_value=True)
    manager.update_alert_threshold = MagicMock(return_value=True)
    manager.update_check_interval = MagicMock(return_value=True)
    manager.alert_thresholds = {
        "price_change_percent": 15.0,
        "trending_popularity": 50.0,
        "volatility_threshold": 25.0,
        "arbitrage_profit_percent": 10.0,
    }
    manager.check_intervals = {
        "price_changes": 3600,
        "trending": 3600,
        "volatility": 3600,
        "arbitrage": 3600,
    }
    return manager


class TestAlertsCommand:
    """Тесты для команды /alerts."""

    @pytest.mark.asyncio()
    async def test_alerts_command_no_subscriptions(
        self, mock_update, mock_context, mock_alerts_manager
    ):
        """Тест команды /alerts без подписок."""
        with (
            patch(
                "src.telegram_bot.handlers.market_alerts_handler.get_alerts_manager",
                return_value=mock_alerts_manager,
            ),
            patch(
                "src.telegram_bot.handlers.market_alerts_handler.get_user_alerts",
                new=AsyncMock(return_value=[]),
            ),
        ):
            await alerts_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            text = (
                call_args.args[0]
                if call_args.args
                else call_args.kwargs.get("text", "")
            )
            assert "🔔" in text

    @pytest.mark.asyncio()
    async def test_alerts_command_with_subscriptions(
        self, mock_update, mock_context, mock_alerts_manager
    ):
        """Тест команды /alerts с активными подписками."""
        mock_alerts_manager.get_user_subscriptions.return_value = [
            "price_changes",
            "trending",
        ]

        with (
            patch(
                "src.telegram_bot.handlers.market_alerts_handler.get_alerts_manager",
                return_value=mock_alerts_manager,
            ),
            patch(
                "src.telegram_bot.handlers.market_alerts_handler.get_user_alerts",
                new=AsyncMock(return_value=[]),
            ),
        ):
            await alerts_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_alerts_command_exception_handling(self, mock_update, mock_context):
        """Тест обработки исключений в команде /alerts."""
        with patch(
            "src.telegram_bot.handlers.market_alerts_handler.get_alerts_manager",
            side_effect=Exception("Test error"),
        ):
            await alerts_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            text = call_args.kwargs.get("text") or call_args.args[0]
            assert "❌" in text or "ошибка" in text.lower()


class TestAlertsCallback:
    """Тесты для обработчика callback запросов."""

    @pytest.mark.asyncio()
    async def test_alerts_callback_toggle_subscribe(
        self, mock_update, mock_context, mock_alerts_manager
    ):
        """Тест переключения подписки."""
        mock_update.callback_query.data = "alerts:toggle:price_changes"

        with patch(
            "src.telegram_bot.handlers.market_alerts_handler.get_alerts_manager",
            return_value=mock_alerts_manager,
        ):
            await alerts_callback(mock_update, mock_context)

            # Проверяем что был вызов answer (обязателен для callback query)
            mock_update.callback_query.answer.assert_called()

    @pytest.mark.asyncio()
    async def test_alerts_callback_subscribe_all(
        self, mock_update, mock_context, mock_alerts_manager
    ):
        """Тест подписки на все уведомления."""
        mock_update.callback_query.data = "alerts:subscribe_all"

        with (
            patch(
                "src.telegram_bot.handlers.market_alerts_handler.get_alerts_manager",
                return_value=mock_alerts_manager,
            ),
            patch(
                "src.telegram_bot.handlers.market_alerts_handler.get_user_alerts",
                new=AsyncMock(return_value=[]),
            ),
        ):
            await alerts_callback(mock_update, mock_context)

            # Должны были подписать на все типы
            assert mock_alerts_manager.subscribe.called

    @pytest.mark.asyncio()
    async def test_alerts_callback_unsubscribe_all(
        self, mock_update, mock_context, mock_alerts_manager
    ):
        """Тест отписки от всех уведомлений."""
        mock_update.callback_query.data = "alerts:unsubscribe_all"

        with (
            patch(
                "src.telegram_bot.handlers.market_alerts_handler.get_alerts_manager",
                return_value=mock_alerts_manager,
            ),
            patch(
                "src.telegram_bot.handlers.market_alerts_handler.get_user_alerts",
                new=AsyncMock(return_value=[]),
            ),
        ):
            await alerts_callback(mock_update, mock_context)

            mock_alerts_manager.unsubscribe_all.assert_called_once_with(123456789)

    @pytest.mark.asyncio()
    async def test_alerts_callback_my_alerts(self, mock_update, mock_context):
        """Тест показа списка оповещений."""
        mock_update.callback_query.data = "alerts:my_alerts"

        sample_alerts = [
            {
                "id": "alert_1",
                "type": "price_drop",
                "title": "AK-47 | Redline (FT)",
                "threshold": 10.50,
            },
        ]

        with (
            patch(
                "src.telegram_bot.handlers.market_alerts_handler.get_alerts_manager"
            ) as mock_get_manager,
            patch(
                "src.telegram_bot.handlers.market_alerts_handler.get_user_alerts",
                new=AsyncMock(return_value=sample_alerts),
            ),
        ):
            mock_manager = MagicMock()
            mock_manager.get_user_subscriptions = MagicMock(return_value=[])
            mock_get_manager.return_value = mock_manager

            await alerts_callback(mock_update, mock_context)

            mock_update.callback_query.edit_message_text.assert_called()

    @pytest.mark.asyncio()
    async def test_alerts_callback_exception_handling(self, mock_update, mock_context):
        """Тест обработки исключений в callback."""
        mock_update.callback_query.data = "alerts:toggle:price_changes"

        with patch(
            "src.telegram_bot.handlers.market_alerts_handler.get_alerts_manager",
            side_effect=Exception("Test error"),
        ):
            await alerts_callback(mock_update, mock_context)

            # Должен быть вызван answer даже при ошибке
            mock_update.callback_query.answer.assert_called()


class TestRegisterAlertsHandlers:
    """Тесты для функции регистрации обработчиков."""

    def test_register_alerts_handlers(self):
        """Тест регистрации обработчиков уведомлений."""
        mock_application = MagicMock()
        mock_application.bot = MagicMock()

        with patch("src.telegram_bot.handlers.market_alerts_handler.load_user_alerts"):
            with patch(
                "src.telegram_bot.handlers.market_alerts_handler.register_notification_handlers"
            ):
                register_alerts_handlers(mock_application)

                # Должны были зарегистрировать обработчики команд и callback
                assert mock_application.add_handler.call_count >= 2


class TestInitializeAlertsManager:
    """Тесты для функции инициализации менеджера."""

    @pytest.mark.asyncio()
    async def test_initialize_alerts_manager(self):
        """Тест инициализации менеджера уведомлений."""
        mock_application = MagicMock()
        result = await initialize_alerts_manager(mock_application)

        # Функция-заглушка возвращает None
        assert result is None


class TestUpdateAlertsKeyboard:
    """Тесты для функции update_alerts_keyboard."""

    @pytest.mark.asyncio()
    async def test_update_alerts_keyboard_no_subscriptions(
        self, mock_update, mock_alerts_manager
    ):
        """Тест обновления клавиатуры без подписок."""
        from src.telegram_bot.handlers.market_alerts_handler import (
            update_alerts_keyboard,
        )

        query = mock_update.callback_query

        with patch(
            "src.telegram_bot.handlers.market_alerts_handler.get_user_alerts",
            new=AsyncMock(return_value=[]),
        ):
            await update_alerts_keyboard(query, mock_alerts_manager, 123456789)

            query.edit_message_text.assert_called_once()
            call_kwargs = query.edit_message_text.call_args.kwargs
            assert "reply_markup" in call_kwargs

    @pytest.mark.asyncio()
    async def test_update_alerts_keyboard_with_subscriptions(
        self, mock_update, mock_alerts_manager
    ):
        """Тест обновления клавиатуры с активными подписками."""
        from src.telegram_bot.handlers.market_alerts_handler import (
            update_alerts_keyboard,
        )

        mock_alerts_manager.get_user_subscriptions.return_value = [
            "price_changes",
            "trending",
        ]
        query = mock_update.callback_query

        with patch(
            "src.telegram_bot.handlers.market_alerts_handler.get_user_alerts",
            new=AsyncMock(return_value=[]),
        ):
            await update_alerts_keyboard(query, mock_alerts_manager, 123456789)

            query.edit_message_text.assert_called_once()
            # Проверяем вызов - текст может быть в args[0] или kwargs['text']
            assert query.edit_message_text.called


class TestShowUserAlertsList:
    """Тесты для функции show_user_alerts_list."""

    @pytest.mark.asyncio()
    async def test_show_user_alerts_list_empty(self, mock_update):
        """Тест показа пустого списка оповещений."""
        from src.telegram_bot.handlers.market_alerts_handler import (
            show_user_alerts_list,
        )

        query = mock_update.callback_query

        with patch(
            "src.telegram_bot.handlers.market_alerts_handler.get_user_alerts",
            new=AsyncMock(return_value=[]),
        ):
            await show_user_alerts_list(query, 123456789)

            query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_show_user_alerts_list_with_alerts(self, mock_update):
        """Тест показа списка с оповещениями."""
        from src.telegram_bot.handlers.market_alerts_handler import (
            show_user_alerts_list,
        )

        sample_alerts = [
            {
                "id": "alert_1",
                "type": "price_drop",
                "title": "AK-47 | Redline (FT)",
                "threshold": 10.50,
            },
            {
                "id": "alert_2",
                "type": "price_rise",
                "title": "AWP | Asiimov (FT)",
                "threshold": 25.00,
            },
        ]
        query = mock_update.callback_query

        with patch(
            "src.telegram_bot.handlers.market_alerts_handler.get_user_alerts",
            new=AsyncMock(return_value=sample_alerts),
        ):
            await show_user_alerts_list(query, 123456789)

            query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_show_user_alerts_list_various_types(self, mock_update):
        """Тест показа оповещений разных типов."""
        from src.telegram_bot.handlers.market_alerts_handler import (
            show_user_alerts_list,
        )

        sample_alerts = [
            {
                "id": "1",
                "type": "volume_increase",
                "title": "Item 1",
                "threshold": 100,
            },
            {
                "id": "2",
                "type": "good_deal",
                "title": "Item 2",
                "threshold": 15.5,
            },
            {
                "id": "3",
                "type": "trend_change",
                "title": "Item 3",
                "threshold": 20.0,
            },
        ]
        query = mock_update.callback_query

        with patch(
            "src.telegram_bot.handlers.market_alerts_handler.get_user_alerts",
            new=AsyncMock(return_value=sample_alerts),
        ):
            await show_user_alerts_list(query, 123456789)

            query.edit_message_text.assert_called_once()


class TestShowCreateAlertForm:
    """Тесты для функции show_create_alert_form."""

    @pytest.mark.asyncio()
    async def test_show_create_alert_form(self, mock_update):
        """Тест показа формы создания оповещения."""
        from src.telegram_bot.handlers.market_alerts_handler import (
            show_create_alert_form,
        )

        query = mock_update.callback_query

        await show_create_alert_form(query, 123456789)

        query.edit_message_text.assert_called_once()


class TestShowAlertsSettings:
    """Тесты для функции show_alerts_settings."""

    @pytest.mark.asyncio()
    async def test_show_alerts_settings_with_subscriptions(
        self, mock_update, mock_alerts_manager
    ):
        """Тест показа настроек с активными подписками."""
        from src.telegram_bot.handlers.market_alerts_handler import show_alerts_settings

        mock_alerts_manager.get_user_subscriptions.return_value = ["price_changes"]
        query = mock_update.callback_query

        await show_alerts_settings(query, mock_alerts_manager, 123456789)

        query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_show_alerts_settings_no_subscriptions(
        self, mock_update, mock_alerts_manager
    ):
        """Тест показа настроек без подписок."""
        from src.telegram_bot.handlers.market_alerts_handler import show_alerts_settings

        mock_alerts_manager.get_user_subscriptions.return_value = []
        query = mock_update.callback_query

        await show_alerts_settings(query, mock_alerts_manager, 123456789)

        query.edit_message_text.assert_called_once()


class TestAlertsCallbackAdditional:
    """Дополнительные тесты для alerts_callback."""

    @pytest.mark.asyncio()
    async def test_alerts_callback_settings(
        self, mock_update, mock_context, mock_alerts_manager
    ):
        """Тест перехода к настSwarmкам."""
        mock_update.callback_query.data = "alerts:settings"

        with patch(
            "src.telegram_bot.handlers.market_alerts_handler.get_alerts_manager",
            return_value=mock_alerts_manager,
        ):
            await alerts_callback(mock_update, mock_context)

            mock_update.callback_query.edit_message_text.assert_called()

    @pytest.mark.asyncio()
    async def test_alerts_callback_create_alert(self, mock_update, mock_context):
        """Тест перехода к форме создания оповещения."""
        mock_update.callback_query.data = "alerts:create_alert"

        with patch(
            "src.telegram_bot.handlers.market_alerts_handler.get_alerts_manager"
        ):
            await alerts_callback(mock_update, mock_context)

            mock_update.callback_query.edit_message_text.assert_called()

    @pytest.mark.asyncio()
    async def test_alerts_callback_remove_alert_success(
        self, mock_update, mock_context
    ):
        """Тест успешного удаления оповещения."""
        mock_update.callback_query.data = "alerts:remove_alert:alert_123"

        with (
            patch("src.telegram_bot.handlers.market_alerts_handler.get_alerts_manager"),
            patch(
                "src.telegram_bot.handlers.market_alerts_handler.remove_price_alert",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "src.telegram_bot.handlers.market_alerts_handler.get_user_alerts",
                new=AsyncMock(return_value=[]),
            ),
        ):
            await alerts_callback(mock_update, mock_context)

            mock_update.callback_query.answer.assert_called()

    @pytest.mark.asyncio()
    async def test_alerts_callback_remove_alert_failure(
        self, mock_update, mock_context
    ):
        """Тест неудачного удаления оповещения."""
        mock_update.callback_query.data = "alerts:remove_alert:alert_123"

        with (
            patch("src.telegram_bot.handlers.market_alerts_handler.get_alerts_manager"),
            patch(
                "src.telegram_bot.handlers.market_alerts_handler.remove_price_alert",
                new=AsyncMock(return_value=False),
            ),
        ):
            await alerts_callback(mock_update, mock_context)

            mock_update.callback_query.answer.assert_called()
            call_args = mock_update.callback_query.answer.call_args.args[0]
            assert "ошибка" in call_args.lower() or "Ошибка" in call_args

    @pytest.mark.asyncio()
    async def test_alerts_callback_invalid_format(self, mock_update, mock_context):
        """Тест обработки неверного формата данных."""
        mock_update.callback_query.data = "alerts"  # Нет разделителя

        await alerts_callback(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_with("Неверный формат данных")

    @pytest.mark.asyncio()
    async def test_alerts_callback_toggle_invalid_format(
        self, mock_update, mock_context
    ):
        """Тест toggle без указания типа оповещения."""
        mock_update.callback_query.data = "alerts:toggle"  # Нет типа

        with patch(
            "src.telegram_bot.handlers.market_alerts_handler.get_alerts_manager"
        ):
            await alerts_callback(mock_update, mock_context)

            mock_update.callback_query.answer.assert_called_with(
                "Неверный формат данных"
            )
        with patch(
            "src.telegram_bot.handlers.market_alerts_handler.get_alerts_manager"
        ):
            await alerts_callback(mock_update, mock_context)

            mock_update.callback_query.answer.assert_called_with(
                "Неверный формат данных"
            )
        with patch(
            "src.telegram_bot.handlers.market_alerts_handler.get_alerts_manager"
        ):
            await alerts_callback(mock_update, mock_context)

            mock_update.callback_query.answer.assert_called_with(
                "Неверный формат данных"
            )
