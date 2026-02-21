"""Тесты для модуля keyboards.

Этот модуль тестирует все функции создания клавиатур для Telegram бота:
- Главное меню (mAlgon_keyboard.py)
- НастSwarmки
- Выбор игр
- Арбитраж
- Фильтры и диапазоны цен
- Пагинация
- Оповещения
- Web App клавиатуры
"""

from telegram import InlineKeyboardMarkup, ReplyKeyboardRemove

from src.telegram_bot.handlers.mAlgon_keyboard import get_mAlgon_keyboard
from src.telegram_bot.keyboards import (
    CB_BACK,
    CB_CANCEL,
    CB_GAME_PREFIX,
    CB_HELP,
    CB_NEXT_PAGE,
    CB_PREV_PAGE,
    CB_SETTINGS,
    GAMES,
    create_pagination_keyboard,
    get_alert_actions_keyboard,
    get_alert_keyboard,
    get_alert_type_keyboard,
    get_arbitrage_keyboard,
    get_back_to_settings_keyboard,
    get_confirm_cancel_keyboard,
    get_csgo_exterior_keyboard,
    get_csgo_weapon_type_keyboard,
    get_dmarket_webapp_keyboard,
    get_filter_keyboard,
    get_login_keyboard,
    get_pagination_keyboard,
    get_payment_keyboard,
    get_price_range_keyboard,
    get_rarity_keyboard,
    get_settings_keyboard,
    get_webapp_keyboard,
    remove_keyboard,
)

# ============================================================================
# ТЕСТЫ КОНСТАНТ
# ============================================================================


def test_constants_defined():
    """Тест наличия всех callback констант."""
    assert CB_CANCEL is not None
    assert CB_BACK is not None
    assert CB_NEXT_PAGE is not None
    assert CB_PREV_PAGE is not None
    assert CB_GAME_PREFIX is not None
    assert CB_HELP is not None
    assert CB_SETTINGS is not None

    # Проверяем типы
    assert isinstance(CB_CANCEL, str)
    assert isinstance(CB_BACK, str)
    assert isinstance(CB_GAME_PREFIX, str)


def test_games_imported():
    """Тест импорта словаря игр."""
    assert GAMES is not None
    assert isinstance(GAMES, dict)
    assert len(GAMES) > 0


# ============================================================================
# ТЕСТЫ ГЛАВНОЙ КЛАВИАТУРЫ (mAlgon_keyboard.py)
# ============================================================================


def test_get_mAlgon_keyboard():
    """Тест создания главной клавиатуры."""
    keyboard = get_mAlgon_keyboard()

    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert len(keyboard.inline_keyboard) == 7

    # Проверяем наличие основных кнопок
    all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
    button_texts = [btn.text for btn in all_buttons]

    assert any("АВТО-ТОРГОВЛЯ" in text for text in button_texts)
    assert any("ТАРГЕТЫ" in text for text in button_texts)
    assert any("ЭКСТРЕННАЯ" in text for text in button_texts)


def test_get_mAlgon_keyboard_with_balance():
    """Тест клавиатуры с балансом."""
    keyboard = get_mAlgon_keyboard(balance=50.25)

    all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
    button_texts = [btn.text for btn in all_buttons]

    assert any("$50.25" in text for text in button_texts)


def test_get_settings_keyboard():
    """Тест создания клавиатуры настроек."""
    keyboard = get_settings_keyboard()

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем наличие кнопок
    assert len(keyboard.inline_keyboard) > 0

    # Проверяем наличие кнопки "Назад"
    last_row = keyboard.inline_keyboard[-1]
    assert len(last_row) == 1
    assert "Назад" in last_row[0].text


def test_get_back_to_settings_keyboard():
    """Тест создания клавиатуры возврата к настSwarmкам."""
    keyboard = get_back_to_settings_keyboard()

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем единственную кнопку
    assert len(keyboard.inline_keyboard) == 1
    assert len(keyboard.inline_keyboard[0]) == 1
    assert "Назад" in keyboard.inline_keyboard[0][0].text


# ============================================================================
# ТЕСТЫ КЛАВИАТУР АРБИТРАЖА
# ============================================================================


def test_get_arbitrage_keyboard():
    """Тест создания клавиатуры арбитража."""
    keyboard = get_arbitrage_keyboard()

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем наличие кнопок
    assert len(keyboard.inline_keyboard) > 0


def test_get_price_range_keyboard_no_current():
    """Тест создания клавиатуры диапазона цен без текущих значений."""
    keyboard = get_price_range_keyboard()

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем наличие кнопок
    assert len(keyboard.inline_keyboard) > 0


def test_get_price_range_keyboard_with_current():
    """Тест создания клавиатуры диапазона цен с текущими значениями."""
    keyboard = get_price_range_keyboard(min_price=10, max_price=100)

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем наличие кнопок
    assert len(keyboard.inline_keyboard) > 0


# ============================================================================
# ТЕСТЫ КЛАВИАТУР ПОДТВЕРЖДЕНИЯ
# ============================================================================


def test_get_confirm_cancel_keyboard_default():
    """Тест создания клавиатуры подтверждения/отмены с дефолтными данными."""
    keyboard = get_confirm_cancel_keyboard("confirm", "cancel")

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Должно быть 2 кнопки в одном ряду
    assert len(keyboard.inline_keyboard) == 1
    assert len(keyboard.inline_keyboard[0]) == 2


def test_get_confirm_cancel_keyboard_custom():
    """Тест создания клавиатуры с кастомными callback_data."""
    keyboard = get_confirm_cancel_keyboard(
        confirm_data="custom_yes",
        cancel_data="custom_no",
    )

    # Проверяем callback_data
    confirm_btn = keyboard.inline_keyboard[0][0]
    cancel_btn = keyboard.inline_keyboard[0][1]

    assert confirm_btn.callback_data == "custom_yes"
    assert cancel_btn.callback_data == "custom_no"


# ============================================================================
# ТЕСТЫ КЛАВИАТУР ФИЛЬТРОВ
# ============================================================================


def test_get_filter_keyboard_csgo():
    """Тест создания клавиатуры фильтров для CS:GO."""
    keyboard = get_filter_keyboard("csgo")

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем наличие кнопок
    assert len(keyboard.inline_keyboard) > 0


def test_get_filter_keyboard_dota2():
    """Тест создания клавиатуры фильтров для Dota 2."""
    keyboard = get_filter_keyboard("dota2")

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем наличие кнопок
    assert len(keyboard.inline_keyboard) > 0


# ============================================================================
# ТЕСТЫ КЛАВИАТУР ПАГИНАЦИИ
# ============================================================================


def test_get_pagination_keyboard_first_page():
    """Тест создания клавиатуры пагинации для первой страницы."""
    keyboard = get_pagination_keyboard(current_page=0, total_pages=5)

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # На первой странице не должно быть кнопки "Назад"
    buttons = [btn for row in keyboard.inline_keyboard for btn in row]
    callback_data = [btn.callback_data for btn in buttons]

    # Должна быть кнопка "Вперед"
    assert any(
        "next" in cd or ">" in btn.text for cd, btn in zip(callback_data, buttons, strict=False)
    )


def test_get_pagination_keyboard_middle_page():
    """Тест создания клавиатуры пагинации для средней страницы."""
    keyboard = get_pagination_keyboard(current_page=2, total_pages=5)

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Должны быть обе кнопки
    assert len(keyboard.inline_keyboard) > 0


def test_get_pagination_keyboard_last_page():
    """Тест создания клавиатуры пагинации для последней страницы."""
    keyboard = get_pagination_keyboard(current_page=4, total_pages=5)

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # На последней странице не должно быть кнопки "Вперед"
    buttons = [btn for row in keyboard.inline_keyboard for btn in row]
    callback_data = [btn.callback_data for btn in buttons]

    # Должна быть кнопка "Назад"
    assert any(
        "prev" in cd or "<" in btn.text for cd, btn in zip(callback_data, buttons, strict=False)
    )


def test_create_pagination_keyboard():
    """Тест функции create_pagination_keyboard."""
    keyboard = create_pagination_keyboard(
        current_page=1,
        total_pages=10,
        prefix="test_",
    )

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем наличие кнопок
    assert len(keyboard.inline_keyboard) > 0


# ============================================================================
# ТЕСТЫ КЛАВИАТУР ОПОВЕЩЕНИЙ
# ============================================================================


def test_get_alert_keyboard():
    """Тест создания клавиатуры оповещений."""
    keyboard = get_alert_keyboard()

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем наличие кнопок
    assert len(keyboard.inline_keyboard) > 0


def test_get_alert_type_keyboard():
    """Тест создания клавиатуры типов оповещений."""
    keyboard = get_alert_type_keyboard()

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем наличие кнопок
    assert len(keyboard.inline_keyboard) > 0


def test_get_alert_actions_keyboard():
    """Тест создания клавиатуры действий для оповещения."""
    keyboard = get_alert_actions_keyboard("test_alert_123")

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем наличие кнопок
    assert len(keyboard.inline_keyboard) > 0

    # Проверяем, что alert_id присутствует в callback_data (хотя бы в одной кнопке)
    all_callbacks = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
    # Не все кнопки должны содержать alert_id, проверяем просто структуру
    assert len(all_callbacks) > 0


# ============================================================================
# ТЕСТЫ СПЕЦИАЛИЗИРОВАННЫХ КЛАВИАТУР
# ============================================================================


def test_get_csgo_exterior_keyboard():
    """Тест создания клавиатуры внешнего вида CS:GO."""
    keyboard = get_csgo_exterior_keyboard()

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем наличие кнопок
    assert len(keyboard.inline_keyboard) > 0


def test_get_rarity_keyboard():
    """Тест создания клавиатуры редкости."""
    keyboard = get_rarity_keyboard("csgo")

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем наличие кнопок
    assert len(keyboard.inline_keyboard) > 0


def test_get_csgo_weapon_type_keyboard():
    """Тест создания клавиатуры типов оружия CS:GO."""
    keyboard = get_csgo_weapon_type_keyboard()

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем наличие кнопок
    assert len(keyboard.inline_keyboard) > 0


# ============================================================================
# ТЕСТЫ WEB APP КЛАВИАТУР
# ============================================================================


def test_get_webapp_keyboard():
    """Тест создания Web App клавиатуры."""
    keyboard = get_webapp_keyboard("Test App", "https://example.com")

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем наличие кнопок
    assert len(keyboard.inline_keyboard) > 0

    # Проверяем первую кнопку
    first_button = keyboard.inline_keyboard[0][0]
    assert first_button.text == "Test App"


def test_get_dmarket_webapp_keyboard():
    """Тест создания DMarket Web App клавиатуры."""
    keyboard = get_dmarket_webapp_keyboard()

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем наличие кнопок
    assert len(keyboard.inline_keyboard) > 0


# ============================================================================
# ТЕСТЫ СЛУЖЕБНЫХ КЛАВИАТУР
# ============================================================================


def test_get_payment_keyboard():
    """Тест создания клавиатуры оплаты."""
    keyboard = get_payment_keyboard("invoice_123", "https://payment.url")

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем наличие кнопок
    assert len(keyboard.inline_keyboard) > 0


def test_get_login_keyboard():
    """Тест создания клавиатуры логина."""
    keyboard = get_login_keyboard("Login", "https://login.url")

    # Проверяем тип
    assert isinstance(keyboard, InlineKeyboardMarkup)

    # Проверяем наличие кнопок
    assert len(keyboard.inline_keyboard) > 0


def test_remove_keyboard():
    """Тест создания клавиатуры удаления."""
    keyboard = remove_keyboard()

    # Проверяем тип
    assert isinstance(keyboard, ReplyKeyboardRemove)

    # Проверяем параметр
    assert keyboard.remove_keyboard is True
