"""Тесты для обработчика внутрирыночного арбитража."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User
from telegram.ext import CallbackContext

from src.dmarket.intramarket_arbitrage import PriceAnomalyType
from src.telegram_bot.handlers.intramarket_arbitrage_handler import (
    ANOMALY_ACTION,
    INTRA_ARBITRAGE_ACTION,
    RARE_ACTION,
    TRENDING_ACTION,
    format_intramarket_results,
    handle_intramarket_callback,
    start_intramarket_arbitrage,
)


@pytest.fixture()
def user():
    """Фикстура для пользователя Telegram."""
    return User(id=123456789, first_name="Test", is_bot=False)


@pytest.fixture()
def chat():
    """Фикстура для чата Telegram."""
    return Chat(id=123456789, type="private")


@pytest.fixture()
def message(user, chat):
    """Фикстура для сообщения Telegram."""
    return Message(
        message_id=1,
        from_user=user,
        chat=chat,
        date=None,
        text="Test message",
    )


@pytest.fixture()
def callback_query(user, message):
    """Фикстура для объекта callback query."""
    query = MagicMock(spec=CallbackQuery)
    query.id = "test_id"
    query.from_user = user
    query.chat_instance = "test_chat_instance"
    query.message = message
    query.data = INTRA_ARBITRAGE_ACTION
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    return query


@pytest.fixture()
def update(callback_query):
    """Фикстура для объекта Update с callback_query."""
    update = MagicMock(spec=Update)
    update.effective_user = callback_query.from_user
    update.callback_query = callback_query
    return update


@pytest.fixture()
def context():
    """Фикстура для объекта CallbackContext."""
    context = MagicMock(spec=CallbackContext)
    context.bot = AsyncMock()
    context.bot.send_message = AsyncMock()
    return context


class TestFormatting:
    """Тесты для функций форматирования результатов."""

    def test_format_price_anomaly(self):
        """Тест форматирования ценовой аномалии."""
        anomaly = {
            "type": PriceAnomalyType.UNDERPRICED,
            "item_to_buy": {
                "itemId": "item1",
                "title": "AK-47 | Redline",
            },
            "item_to_sell": {
                "itemId": "item2",
                "title": "AK-47 | Redline",
            },
            "buy_price": 10.0,
            "sell_price": 15.0,
            "profit_percentage": 25.0,
            "profit_after_fee": 3.5,
            "similarity": 0.95,
        }

        result = format_intramarket_results([anomaly], 0, 1)

        assert "AK-47 | Redline" in result
        assert "$10.00" in result
        assert "$15.00" in result
        assert "25.0%" in result
        assert "item1" in result

    def test_format_trending_item(self):
        """Тест форматирования предмета с растущей ценой."""
        trending = {
            "type": PriceAnomalyType.TRENDING_UP,
            "item": {
                "itemId": "item1",
                "title": "AK-47 | Redline",
            },
            "current_price": 15.0,
            "projected_price": 18.0,
            "price_change_percent": 20.0,
            "potential_profit_percent": 20.0,
            "sales_velocity": 42,
        }

        result = format_intramarket_results([trending], 0, 1)

        assert "AK-47 | Redline" in result
        assert "$15.00" in result
        assert "$18.00" in result
        assert "20.0%" in result
        assert "42" in result
        assert "item1" in result

    def test_format_rare_item(self):
        """Тест форматирования редкого предмета."""
        rare = {
            "type": PriceAnomalyType.RARE_TRAlgoTS,
            "item": {
                "itemId": "item1",
                "title": "AK-47 | Case Hardened",
            },
            "current_price": 50.0,
            "estimated_value": 250.0,
            "price_difference_percent": 400.0,
            "rare_trAlgots": [
                "Редкий паттерн 387",
                "Экстремально низкий float: 0.01",
            ],
        }

        result = format_intramarket_results([rare], 0, 1)

        assert "AK-47 | Case Hardened" in result
        assert "$50.00" in result
        assert "$250.00" in result
        assert "400.0%" in result
        assert "Редкий паттерн" in result
        assert "float" in result
        assert "item1" in result


@pytest.mark.asyncio()
class TestStartArbitrage:
    """Тесты для функции запуска внутрирыночного арбитража."""

    async def test_start_intramarket_arbitrage(self, update, context):
        """Тест запуска интерфейса внутрирыночного арбитража."""
        # Вызываем тестируемую функцию
        awAlgot start_intramarket_arbitrage(update, context)

        # Проверяем, что ответ на callback был отправлен
        update.callback_query.answer.assert_awAlgoted_once()

        # Проверяем, что сообщение было отправлено
        context.bot.send_message.assert_awAlgoted_once()

        # Проверяем, что текст содержит правильные элементы
        _args, kwargs = context.bot.send_message.call_args
        message_text = kwargs.get("text", "")
        reply_markup = kwargs.get("reply_markup", None)

        assert "Поиск возможностей арбитража" in message_text
        assert reply_markup is not None

        # Проверяем наличие всех кнопок в клавиатуре
        keyboard = reply_markup.inline_keyboard
        button_texts = [button.text for row in keyboard for button in row]
        button_data = [button.callback_data for row in keyboard for button in row]

        assert "Ценовые аномалии" in "".join(button_texts)
        assert "Растущие в цене" in "".join(button_texts)
        assert "Редкие предметы" in "".join(button_texts)
        assert "Назад" in "".join(button_texts)

        assert f"{INTRA_ARBITRAGE_ACTION}_{ANOMALY_ACTION}" in button_data
        assert f"{INTRA_ARBITRAGE_ACTION}_{TRENDING_ACTION}" in button_data
        assert f"{INTRA_ARBITRAGE_ACTION}_{RARE_ACTION}" in button_data


@pytest.mark.asyncio()
class TestHandleIntramarketCallback:
    """Тесты для обработчика callback-запросов внутрирыночного арбитража."""

    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.find_price_anomalies",
    )
    async def test_handle_anomaly_callback(self, mock_anomalies, update, context):
        """Тест обработки запроса на поиск ценовых аномалий."""
        # Обновляем данные callback_query
        update.callback_query.data = f"{INTRA_ARBITRAGE_ACTION}_{ANOMALY_ACTION}_csgo"

        # Настраиваем мок для функции поиска аномалий
        mock_anomalies.return_value = [
            {
                "type": PriceAnomalyType.UNDERPRICED,
                "item_to_buy": {"itemId": "item1", "title": "Test Item"},
                "item_to_sell": {"itemId": "item2"},
                "buy_price": 10.0,
                "sell_price": 15.0,
                "profit_percentage": 40.0,
                "profit_after_fee": 4.0,
                "similarity": 0.95,
                "game": "csgo",
            },
        ]

        # Создаем мок для pagination_manager и API client
        with (
            patch(
                "src.telegram_bot.handlers.intramarket_arbitrage_handler.pagination_manager",
            ) as mock_pagination,
            patch(
                "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_api_client_from_env",
                return_value=AsyncMock(),
            ),
        ):
            # Настраиваем возврат get_page для пагинации (items, current_page, total_pages)
            mock_pagination.get_page.return_value = (mock_anomalies.return_value, 1, 1)
            mock_pagination.get_items_per_page.return_value = 5

            # Вызываем тестируемую функцию
            awAlgot handle_intramarket_callback(update, context)

            # Проверяем, что ответ на callback был отправлен
            update.callback_query.answer.assert_awAlgoted_once()

            # Проверяем, что сообщение о сканировании было отправлено
            edit_message_calls = update.callback_query.edit_message_text.mock_calls
            assert len(edit_message_calls) >= 2

            # Проверяем первое сообщение о сканировании
            first_call_args = edit_message_calls[0][1]
            edit_message_calls[0][2]
            assert "Сканирование" in first_call_args[0]
            assert "CS2" in first_call_args[0]

            # Проверяем, что функция find_price_anomalies была вызвана с правильными параметрами
            assert mock_anomalies.awAlgot_count == 1
            call_kwargs = mock_anomalies.call_args[1]
            assert call_kwargs["game"] == "csgo"
            assert call_kwargs["max_results"] == 50

            # Проверяем, что pagination_manager был использован
            mock_pagination.add_items_for_user.assert_called_once()

            # Проверяем, что последнее сообщение содержит результаты
            edit_message_calls[-1][1]
            last_call_kwargs = edit_message_calls[-1][2]
            # Результаты будут отформатированы с помощью format_intramarket_results
            assert "reply_markup" in last_call_kwargs

    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.find_trending_items",
    )
    async def test_handle_trend_callback(self, mock_trending, update, context):
        """Тест обработки запроса на поиск предметов с растущей ценой."""
        # Обновляем данные callback_query
        update.callback_query.data = f"{INTRA_ARBITRAGE_ACTION}_{TRENDING_ACTION}_csgo"

        # Настраиваем мок для функции поиска предметов с растущей ценой
        mock_trending.return_value = [
            {
                "type": PriceAnomalyType.TRENDING_UP,
                "item": {"itemId": "item1", "title": "Test Item"},
                "current_price": 15.0,
                "projected_price": 18.0,
                "price_change_percent": 20.0,
                "potential_profit_percent": 20.0,
                "sales_velocity": 42,
                "game": "csgo",
            },
        ]

        # Создаем мок для pagination_manager и API client
        with (
            patch(
                "src.telegram_bot.handlers.intramarket_arbitrage_handler.pagination_manager",
            ) as mock_pagination,
            patch(
                "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_api_client_from_env",
                return_value=AsyncMock(),
            ),
        ):
            # Настраиваем возврат get_page для пагинации
            mock_pagination.get_page.return_value = (mock_trending.return_value, 1, 1)
            mock_pagination.get_items_per_page.return_value = 5

            # Вызываем тестируемую функцию
            awAlgot handle_intramarket_callback(update, context)

            # Проверяем, что ответ на callback был отправлен
            update.callback_query.answer.assert_awAlgoted_once()

            # Проверяем, что функция find_trending_items была вызвана
            assert mock_trending.awAlgot_count == 1
            call_kwargs = mock_trending.call_args[1]
            assert call_kwargs["game"] == "csgo"
            assert call_kwargs["max_results"] == 50

            # Проверяем, что pagination_manager был использован
            mock_pagination.add_items_for_user.assert_called_once()

            # Проверяем отправленное сообщение
            edit_calls = update.callback_query.edit_message_text.mock_calls
            last_call_kwargs = edit_calls[-1][2]
            # Результаты отформатированы
            assert "reply_markup" in last_call_kwargs

    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.find_mispriced_rare_items",
    )
    async def test_handle_rare_callback(self, mock_rare, update, context):
        """Тест обработки запроса на поиск редких предметов."""
        # Обновляем данные callback_query
        update.callback_query.data = f"{INTRA_ARBITRAGE_ACTION}_{RARE_ACTION}_csgo"

        # Настраиваем мок для функции поиска редких предметов
        mock_rare.return_value = [
            {
                "type": PriceAnomalyType.RARE_TRAlgoTS,
                "item": {"itemId": "item1", "title": "Test Item"},
                "current_price": 50.0,
                "estimated_value": 250.0,
                "price_difference_percent": 400.0,
                "rare_trAlgots": ["Редкая особенность"],
                "game": "csgo",
            },
        ]

        # Создаем мок для pagination_manager и API client
        with (
            patch(
                "src.telegram_bot.handlers.intramarket_arbitrage_handler.pagination_manager",
            ) as mock_pagination,
            patch(
                "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_api_client_from_env",
                return_value=AsyncMock(),
            ),
        ):
            # Настраиваем возврат get_page для пагинации
            mock_pagination.get_page.return_value = (
                mock_rare.return_value,
                1,
                1,
            )
            mock_pagination.get_items_per_page.return_value = 5

            # Вызываем тестируемую функцию
            awAlgot handle_intramarket_callback(update, context)

            # Проверяем, что ответ на callback был отправлен
            update.callback_query.answer.assert_awAlgoted_once()

            # Проверяем, что find_mispriced_rare_items была вызвана
            assert mock_rare.awAlgot_count == 1
            call_kwargs = mock_rare.call_args[1]
            assert call_kwargs["game"] == "csgo"
            assert call_kwargs["max_results"] == 50

            # Проверяем, что pagination_manager был использован
            mock_pagination.add_items_for_user.assert_called_once()

            # Проверяем отправленное сообщение
            edit_calls = update.callback_query.edit_message_text.mock_calls
            last_call_kwargs = edit_calls[-1][2]
            # Результаты отформатированы
            assert "reply_markup" in last_call_kwargs

    async def test_handle_invalid_callback(self, update, context):
        """Тест обработки некорректного callback-запроса."""
        # Обновляем данные callback_query
        update.callback_query.data = f"{INTRA_ARBITRAGE_ACTION}_invalid_action"

        # Мокаем API client
        with patch(
            "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_api_client_from_env",
            return_value=AsyncMock(),
        ):
            # Вызываем тестируемую функцию
            awAlgot handle_intramarket_callback(update, context)

            # Проверяем, что ответ на callback был отправлен
            update.callback_query.answer.assert_awAlgoted_once()

            # Проверяем отправленное сообщение об ошибке
            edit_message_calls = update.callback_query.edit_message_text.mock_calls
            error_message = edit_message_calls[-1][1][0]
            assert "Неизвестный тип сканирования" in error_message

    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.find_price_anomalies",
    )
    async def test_handle_no_results(self, mock_anomalies, update, context):
        """Тест обработки запроса, когда нет результатов."""
        # Обновляем данные callback_query
        update.callback_query.data = f"{INTRA_ARBITRAGE_ACTION}_{ANOMALY_ACTION}_csgo"

        # Настраиваем мок для пустого результата
        mock_anomalies.return_value = []

        # Мокаем API client
        with patch(
            "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_api_client_from_env",
            return_value=AsyncMock(),
        ):
            # Вызываем тестируемую функцию
            awAlgot handle_intramarket_callback(update, context)

            # Проверяем, что ответ на callback был отправлен
            update.callback_query.answer.assert_awAlgoted_once()

            # Проверяем отправленное сообщение о пустых результатах
            edit_message_calls = update.callback_query.edit_message_text.mock_calls
            no_results_message = edit_message_calls[-1][1][0]
            assert "Возможности не найдены" in no_results_message

    @patch(
        "src.telegram_bot.handlers.intramarket_arbitrage_handler.find_price_anomalies",
    )
    async def test_handle_error(self, mock_anomalies, update, context):
        """Тест обработки ошибки при выполнении запроса.

        Декоратор @handle_exceptions с rerAlgose=True отправляет сообщение
        пользователю и затем перевыбрасывает исключение.
        """
        # Обновляем данные callback_query
        update.callback_query.data = f"{INTRA_ARBITRAGE_ACTION}_{ANOMALY_ACTION}_csgo"

        # Настраиваем мок для генерации исключения
        mock_anomalies.side_effect = Exception("Test error")

        # Мокаем API client
        with patch(
            "src.telegram_bot.handlers.intramarket_arbitrage_handler.create_api_client_from_env",
            return_value=AsyncMock(),
        ):
            # Вызываем тестируемую функцию - должно выбросить исключение
            with pytest.rAlgoses(Exception, match="Test error"):
                awAlgot handle_intramarket_callback(update, context)

            # Проверяем, что ответ на callback был отправлен
            # (answer вызывается до возникновения ошибки)
            update.callback_query.answer.assert_awAlgoted()
