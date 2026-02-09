"""Тесты для обработчика таргетов (buy orders)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, InlineKeyboardMarkup, Update, User
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler

from src.telegram_bot.handlers.target_handler import (
    TARGET_ACTION,
    TARGET_CREATE_ACTION,
    TARGET_DELETE_ACTION,
    TARGET_LIST_ACTION,
    TARGET_SMART_ACTION,
    TARGET_STATS_ACTION,
    handle_target_callback,
    register_target_handlers,
    start_targets_menu,
)

# ============================================
# Фикстуры
# ============================================


@pytest.fixture()
def mock_user():
    """Создать mock объект User."""
    user = MagicMock(spec=User)
    user.id = 123456789
    user.username = "testuser"
    user.first_name = "Test"
    return user


@pytest.fixture()
def mock_callback_query(mock_user):
    """Создать mock объект CallbackQuery."""
    query = MagicMock(spec=CallbackQuery)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = TARGET_ACTION
    query.from_user = mock_user
    return query


@pytest.fixture()
def mock_update(mock_user, mock_callback_query):
    """Создать mock объект Update."""
    update = MagicMock(spec=Update)
    update.callback_query = mock_callback_query
    update.effective_user = mock_user
    update.message = None
    return update


@pytest.fixture()
def mock_context():
    """Создать mock объект CallbackContext."""
    context = MagicMock(spec=CallbackContext)
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}
    context.chat_data = {}
    return context


# ============================================
# Тесты start_targets_menu
# ============================================


@pytest.mark.asyncio()
async def test_start_targets_menu_with_callback_query(
    mock_update,
    mock_context,
    mock_callback_query,
):
    """Тест: start_targets_menu с callback query."""
    await start_targets_menu(mock_update, mock_context)

    # Проверяем, что callback query отвечен
    mock_callback_query.answer.assert_called_once()

    # Проверяем, что сообщение отредактировано
    mock_callback_query.edit_message_text.assert_called_once()

    # Проверяем содержимое сообщения (text передается как позиционный аргумент)
    call_args = mock_callback_query.edit_message_text.call_args
    assert call_args is not None
    assert len(call_args.args) > 0
    text = call_args.args[0]
    assert text is not None
    assert "Таргеты (Buy Orders)" in text
    assert "Создавайте заявки на покупку" in text

    # Проверяем parse_mode
    assert call_args.kwargs.get("parse_mode") == "Markdown"

    # Проверяем наличие клавиатуры
    reply_markup = call_args.kwargs.get("reply_markup")
    assert isinstance(reply_markup, InlineKeyboardMarkup)


@pytest.mark.asyncio()
async def test_start_targets_menu_without_callback_query(
    mock_update,
    mock_context,
    mock_user,
):
    """Тест: start_targets_menu без callback query (прямой вызов)."""
    mock_update.callback_query = None

    await start_targets_menu(mock_update, mock_context)

    # Проверяем, что сообщение отправлено через bot
    mock_context.bot.send_message.assert_called_once()

    # Проверяем параметры вызова
    call_args = mock_context.bot.send_message.call_args
    assert call_args is not None
    assert call_args.kwargs.get("chat_id") == mock_user.id
    assert "Таргеты (Buy Orders)" in call_args.kwargs.get("text", "")


@pytest.mark.asyncio()
async def test_start_targets_menu_no_effective_user(mock_context):
    """Тест: start_targets_menu без effective_user (edge case)."""
    update = MagicMock(spec=Update)
    update.callback_query = None
    update.effective_user = None

    # Функция должна вернуться раньше без исключений
    await start_targets_menu(update, mock_context)

    # Никаких вызовов не должно быть
    mock_context.bot.send_message.assert_not_called()


@pytest.mark.asyncio()
async def test_start_targets_menu_has_all_buttons(
    mock_update,
    mock_context,
    mock_callback_query,
):
    """Тест: start_targets_menu содержит все кнопки."""
    await start_targets_menu(mock_update, mock_context)

    # Получаем клавиатуру
    call_args = mock_callback_query.edit_message_text.call_args
    assert call_args is not None
    reply_markup = call_args.kwargs.get("reply_markup")
    assert isinstance(reply_markup, InlineKeyboardMarkup)

    # Получаем все кнопки
    buttons_text = []
    for row in reply_markup.inline_keyboard:
        for button in row:
            buttons_text.append(button.text)

    # Проверяем наличие всех ожидаемых кнопок
    expected_buttons = [
        "📝 Создать таргет",
        "📋 Мои таргеты",
        "🤖 Умные таргеты",
        "📊 Статистика",
        "⬅️ Назад",
    ]

    for expected_button in expected_buttons:
        assert expected_button in buttons_text


@pytest.mark.asyncio()
async def test_start_targets_menu_button_callbacks(
    mock_update,
    mock_context,
    mock_callback_query,
):
    """Тест: кнопки start_targets_menu имеют правильные callback_data."""
    await start_targets_menu(mock_update, mock_context)

    # Получаем клавиатуру
    call_args = mock_callback_query.edit_message_text.call_args
    assert call_args is not None
    reply_markup = call_args.kwargs.get("reply_markup")
    assert isinstance(reply_markup, InlineKeyboardMarkup)

    # Собираем все callback_data
    callback_data_list = []
    for row in reply_markup.inline_keyboard:
        for button in row:
            callback_data_list.append(button.callback_data)

    # Проверяем конкретные callback_data
    assert f"{TARGET_ACTION}_{TARGET_CREATE_ACTION}" in callback_data_list
    assert f"{TARGET_ACTION}_{TARGET_LIST_ACTION}" in callback_data_list
    assert f"{TARGET_ACTION}_{TARGET_SMART_ACTION}" in callback_data_list
    assert f"{TARGET_ACTION}_{TARGET_STATS_ACTION}" in callback_data_list
    assert "main_menu" in callback_data_list


# ============================================
# Тесты handle_target_callback
# ============================================


@pytest.mark.asyncio()
async def test_handle_target_callback_main_menu(
    mock_update,
    mock_context,
    mock_callback_query,
):
    """Тест: handle_target_callback открывает главное меню."""
    mock_callback_query.data = TARGET_ACTION

    await handle_target_callback(mock_update, mock_context)

    # Проверяем, что меню открылось (text как позиционный аргумент)
    mock_callback_query.edit_message_text.assert_called_once()
    call_args = mock_callback_query.edit_message_text.call_args
    assert call_args is not None
    assert len(call_args.args) > 0
    assert "Таргеты (Buy Orders)" in call_args.args[0]


@pytest.mark.asyncio()
async def test_handle_target_callback_create_action(
    mock_update,
    mock_context,
    mock_callback_query,
):
    """Тест: handle_target_callback для создания таргета (заглушка)."""
    mock_callback_query.data = f"{TARGET_ACTION}_{TARGET_CREATE_ACTION}"

    await handle_target_callback(mock_update, mock_context)

    # Проверяем, что заглушка сработала
    mock_callback_query.answer.assert_called()
    call_args = mock_callback_query.answer.call_args
    assert call_args is not None
    assert (
        "будет реализована в следующей версии" in call_args.args[0]
        if call_args.args
        else call_args.kwargs.get("text", "")
    )


@pytest.mark.asyncio()
async def test_handle_target_callback_list_action(
    mock_update,
    mock_context,
    mock_callback_query,
):
    """Тест: handle_target_callback для списка таргетов (заглушка)."""
    mock_callback_query.data = f"{TARGET_ACTION}_{TARGET_LIST_ACTION}"

    await handle_target_callback(mock_update, mock_context)

    # Проверяем заглушку
    mock_callback_query.answer.assert_called()


@pytest.mark.asyncio()
@patch("src.telegram_bot.handlers.target_handler.create_api_client_from_env")
@patch("src.telegram_bot.handlers.target_handler.TargetManager")
async def test_handle_target_callback_smart_action(
    mock_target_manager_class,
    mock_api_client,
    mock_update,
    mock_context,
    mock_callback_query,
):
    """Тест: handle_target_callback для умных таргетов."""
    mock_callback_query.data = f"{TARGET_ACTION}_{TARGET_SMART_ACTION}"

    # Настраиваем моки
    mock_api_client.return_value = MagicMock()
    mock_target_manager = MagicMock()
    mock_target_manager.create_smart_targets = AsyncMock(
        return_value={
            "created": [
                {"target_id": "t1", "title": "AK-47", "price": 10.0},
                {"target_id": "t2", "title": "AWP", "price": 20.0},
            ],
            "failed": [],
        }
    )
    mock_target_manager_class.return_value = mock_target_manager

    await handle_target_callback(mock_update, mock_context)

    # Проверяем вызовы
    mock_callback_query.answer.assert_called()
    mock_target_manager.create_smart_targets.assert_called_once()


@pytest.mark.asyncio()
async def test_handle_target_callback_stats_action(
    mock_update,
    mock_context,
    mock_callback_query,
):
    """Тест: handle_target_callback для статистики (заглушка)."""
    mock_callback_query.data = f"{TARGET_ACTION}_{TARGET_STATS_ACTION}"

    await handle_target_callback(mock_update, mock_context)

    # Проверяем заглушку
    mock_callback_query.answer.assert_called()


@pytest.mark.asyncio()
async def test_handle_target_callback_delete_action(
    mock_update,
    mock_context,
    mock_callback_query,
):
    """Тест: handle_target_callback для удаления таргета (заглушка)."""
    mock_callback_query.data = f"{TARGET_ACTION}_{TARGET_DELETE_ACTION}"

    await handle_target_callback(mock_update, mock_context)

    # Проверяем заглушку
    mock_callback_query.answer.assert_called()


@pytest.mark.asyncio()
async def test_handle_target_callback_no_callback_query(mock_context):
    """Тест: handle_target_callback без callback query (edge case)."""
    update = MagicMock(spec=Update)
    update.callback_query = None

    # Функция должна вернуться раньше без исключений
    await handle_target_callback(update, mock_context)

    # Никаких действий не должно быть
    # (проверка, что не упало с исключением, достаточна)


# ============================================
# Тесты register_target_handlers
# ============================================


def test_register_target_handlers():
    """Тест: register_target_handlers регистрирует обработчики."""
    mock_dispatcher = MagicMock()

    register_target_handlers(mock_dispatcher)

    # Проверяем, что add_handler был вызван
    assert mock_dispatcher.add_handler.call_count == 2

    # Проверяем типы зарегистрированных обработчиков
    calls = mock_dispatcher.add_handler.call_args_list

    # Первый должен быть CommandHandler
    assert isinstance(calls[0].args[0], CommandHandler)

    # Второй должен быть CallbackQueryHandler
    assert isinstance(calls[1].args[0], CallbackQueryHandler)


def test_register_target_handlers_command_handler():
    """Тест: register_target_handlers регистрирует CommandHandler для /targets."""
    mock_dispatcher = MagicMock()

    register_target_handlers(mock_dispatcher)

    # Получаем первый вызов (CommandHandler)
    calls = mock_dispatcher.add_handler.call_args_list
    command_handler = calls[0].args[0]

    # Проверяем, что это CommandHandler для /targets
    assert isinstance(command_handler, CommandHandler)
    # CommandHandler.commands - это список команд
    assert "targets" in command_handler.commands


def test_register_target_handlers_callback_handler():
    """Тест: register_target_handlers регистрирует CallbackQueryHandler."""
    mock_dispatcher = MagicMock()

    register_target_handlers(mock_dispatcher)

    # Получаем второй вызов (CallbackQueryHandler)
    calls = mock_dispatcher.add_handler.call_args_list
    callback_handler = calls[1].args[0]

    # Проверяем, что это CallbackQueryHandler
    assert isinstance(callback_handler, CallbackQueryHandler)


# ============================================
# Интеграционные тесты
# ============================================


@pytest.mark.asyncio()
async def test_integration_full_target_workflow(
    mock_update,
    mock_context,
    mock_callback_query,
):
    """Интеграционный тест: полный workflow таргетов.

    1. Открыть меню таргетов
    2. Выбрать действие (например, создание)
    """
    # Шаг 1: Открыть главное меню
    mock_callback_query.data = TARGET_ACTION
    await handle_target_callback(mock_update, mock_context)

    # Проверяем, что меню открылось (text как позиционный аргумент)
    assert mock_callback_query.edit_message_text.call_count == 1
    call_args = mock_callback_query.edit_message_text.call_args
    assert len(call_args.args) > 0
    assert "Таргеты (Buy Orders)" in call_args.args[0]

    # Шаг 2: Выбрать создание таргета
    mock_callback_query.data = f"{TARGET_ACTION}_{TARGET_CREATE_ACTION}"
    await handle_target_callback(mock_update, mock_context)

    # Проверяем, что заглушка сработала
    assert mock_callback_query.answer.call_count >= 1


@pytest.mark.asyncio()
async def test_integration_all_menu_buttons_work(
    mock_update,
    mock_context,
    mock_callback_query,
):
    """Интеграционный тест: все кнопки меню работают."""
    # Открываем меню
    await start_targets_menu(mock_update, mock_context)

    # Получаем клавиатуру
    call_args = mock_callback_query.edit_message_text.call_args
    assert call_args is not None
    reply_markup = call_args.kwargs.get("reply_markup")
    assert isinstance(reply_markup, InlineKeyboardMarkup)

    # Проверяем, что все кнопки имеют callback_data
    for row in reply_markup.inline_keyboard:
        for button in row:
            assert button.callback_data is not None
            assert len(button.callback_data) > 0


# ============================================
# Edge Cases
# ============================================


@pytest.mark.asyncio()
async def test_edge_case_multiple_menu_opens(
    mock_update,
    mock_context,
    mock_callback_query,
):
    """Edge case: множественное открытие меню."""
    # Открываем меню несколько раз
    for _ in range(3):
        await start_targets_menu(mock_update, mock_context)

    # Проверяем, что меню открывалось каждый раз
    assert mock_callback_query.edit_message_text.call_count == 3


@pytest.mark.asyncio()
async def test_edge_case_rapid_callback_queries(
    mock_update,
    mock_context,
    mock_callback_query,
):
    """Edge case: быстрые последовательные callback queries."""
    # Быстро отправляем несколько callback queries
    actions = [
        TARGET_ACTION,
        f"{TARGET_ACTION}_{TARGET_CREATE_ACTION}",
        f"{TARGET_ACTION}_{TARGET_LIST_ACTION}",
        TARGET_ACTION,
    ]

    for action in actions:
        mock_callback_query.data = action
        await handle_target_callback(mock_update, mock_context)

    # Проверяем, что все вызовы обработаны
    # (каждый callback должен вызвать answer)
    assert mock_callback_query.answer.call_count >= len(actions)


@pytest.mark.asyncio()
async def test_edge_case_unknown_callback_data(
    mock_update,
    mock_context,
    mock_callback_query,
):
    """Edge case: неизвестный callback_data."""
    mock_callback_query.data = f"{TARGET_ACTION}_unknown_action"

    await handle_target_callback(mock_update, mock_context)

    # Проверяем, что заглушка сработала
    mock_callback_query.answer.assert_called()
    call_args = mock_callback_query.answer.call_args
    assert call_args is not None
    assert "будет реализована" in str(call_args)


# ============================================
# Тесты новой функциональности API v1.1.0
# ============================================


@pytest.mark.asyncio()
@patch("src.telegram_bot.handlers.target_handler.create_api_client_from_env")
@patch("src.telegram_bot.handlers.target_handler.TargetManager")
async def test_handle_smart_targets_success(
    mock_target_manager_class,
    mock_api_client,
    mock_update,
    mock_context,
):
    """Тест успешного создания умных таргетов."""
    # Настраиваем моки
    mock_api_client.return_value = MagicMock()
    mock_target_manager = MagicMock()
    mock_target_manager.create_smart_targets = AsyncMock(
        return_value=[
            {"Title": "AK-47 | Redline (FT)", "Price": {"Amount": 1000}},
            {"Title": "AWP | Asimov (FT)", "Price": {"Amount": 2000}},
        ]
    )
    mock_target_manager_class.return_value = mock_target_manager

    # Импортируем функцию
    from src.telegram_bot.handlers.target_handler import handle_smart_targets

    # Настраиваем update
    mock_update.callback_query = MagicMock()
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.edit_message_text = AsyncMock()
    mock_update.effective_user = MagicMock()
    mock_update.effective_user.id = 123456789

    await handle_smart_targets(mock_update, mock_context)

    # Проверяем вызовы
    mock_target_manager.create_smart_targets.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called()

    # Проверяем текст сообщения
    call_args = mock_update.callback_query.edit_message_text.call_args
    text = call_args[0][0]
    assert "Создано таргетов: 2" in text


@pytest.mark.asyncio()
@patch("src.telegram_bot.handlers.target_handler.create_api_client_from_env")
@patch("src.telegram_bot.handlers.target_handler.TargetManager")
async def test_handle_smart_targets_no_items(
    mock_target_manager_class,
    mock_api_client,
    mock_update,
    mock_context,
):
    """Тест создания умных таргетов без результатов."""
    # Настраиваем моки
    mock_api_client.return_value = MagicMock()
    mock_target_manager = MagicMock()
    mock_target_manager.create_smart_targets = AsyncMock(return_value=[])
    mock_target_manager_class.return_value = mock_target_manager

    from src.telegram_bot.handlers.target_handler import handle_smart_targets

    mock_update.callback_query = MagicMock()
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.edit_message_text = AsyncMock()
    mock_update.effective_user = MagicMock()
    mock_update.effective_user.id = 123456789

    await handle_smart_targets(mock_update, mock_context)

    # Проверяем сообщение о пустых результатах
    call_args = mock_update.callback_query.edit_message_text.call_args
    text = call_args[0][0]
    assert "Не удалось создать умные таргеты" in text


@pytest.mark.asyncio()
@patch("src.telegram_bot.handlers.target_handler.format_target_competition_analysis")
@patch("src.telegram_bot.handlers.target_handler.create_api_client_from_env")
@patch("src.telegram_bot.handlers.target_handler.TargetManager")
async def test_handle_competition_analysis_success(
    mock_target_manager_class,
    mock_api_client,
    mock_format_func,
    mock_update,
    mock_context,
):
    """Тест успешного анализа конкуренции."""
    # Настраиваем моки
    mock_api_client.return_value = MagicMock()
    mock_format_func.return_value = (
        "🎯 *Анализ конкуренции*\n\nAK-47 | Redline (Field-Tested)\nУровень: medium"
    )
    mock_target_manager = MagicMock()
    mock_target_manager.analyze_target_competition = AsyncMock(
        return_value={
            "title": "AK-47 | Redline (Field-Tested)",
            "existing_orders": [
                {"amount": 10, "price": 12.0},
                {"amount": 5, "price": 12.5},
            ],
            "competition_level": "medium",
            "recommended_price": 11.8,
            "strategy": "aggressive",
        }
    )
    mock_target_manager_class.return_value = mock_target_manager

    from src.telegram_bot.handlers.target_handler import handle_competition_analysis

    mock_update.callback_query = MagicMock()
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.edit_message_text = AsyncMock()
    mock_update.effective_user = MagicMock()
    mock_update.effective_user.id = 123456789

    await handle_competition_analysis(mock_update, mock_context, "AK-47")

    # Проверяем вызовы
    mock_target_manager.analyze_target_competition.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called()

    # Проверяем текст
    call_args = mock_update.callback_query.edit_message_text.call_args
    text = call_args[0][0] if call_args and call_args[0] else ""
    assert "Анализ конкуренции" in text
    assert "AK-47 | Redline" in text


@pytest.mark.asyncio()
@patch("src.telegram_bot.handlers.target_handler.format_target_competition_analysis")
@patch("src.telegram_bot.handlers.target_handler.create_api_client_from_env")
async def test_handle_competition_analysis_no_api_client(
    mock_api_client,
    mock_format_func,
    mock_update,
    mock_context,
):
    """Тест анализа конкуренции без API клиента."""
    mock_api_client.return_value = None

    from src.telegram_bot.handlers.target_handler import handle_competition_analysis

    mock_update.callback_query = MagicMock()
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.edit_message_text = AsyncMock()

    await handle_competition_analysis(mock_update, mock_context, "AK-47")

    # Проверяем сообщение об ошибке
    call_args = mock_update.callback_query.edit_message_text.call_args
    text = call_args[0][0] if call_args and call_args[0] else ""
    assert "Не удалось создать API клиент" in text
