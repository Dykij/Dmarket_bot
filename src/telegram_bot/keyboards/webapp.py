"""Клавиатуры WebApp.

Содержит клавиатуры для WebApp интеграций, платежей,
авторизации и запросов контактов/локации.
"""

from __future__ import annotations

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    LoginUrl,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from src.telegram_bot.keyboards.utils import CB_BACK, CB_CANCEL


def get_webapp_keyboard(
    title: str,
    webapp_url: str,
) -> InlineKeyboardMarkup:
    """Создать клавиатуру с WebApp кнопкой.

    Args:
        title: Текст кнопки
        webapp_url: URL WebApp

    Returns:
        InlineKeyboardMarkup с WebApp кнопкой
    """
    keyboard = [
        [
            InlineKeyboardButton(
                title,
                web_app=WebAppInfo(url=webapp_url),
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_dmarket_webapp_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру DMarket WebApp.

    Returns:
        InlineKeyboardMarkup с ссылками на DMarket
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="🌐 DMarket",
                web_app=WebAppInfo(url="https://dmarket.com"),
            ),
        ],
        [
            InlineKeyboardButton(
                text="📊 Маркет CS2",
                url="https://dmarket.com/ingame-items/item-list/csgo-skins",
            ),
            InlineKeyboardButton(
                text="📊 Маркет Dota 2",
                url="https://dmarket.com/ingame-items/item-list/dota2",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📦 Инвентарь",
                url="https://dmarket.com/inventory",
            ),
            InlineKeyboardButton(
                text="💰 Баланс",
                url="https://dmarket.com/wallet",
            ),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_webapp_button(
    url: str,
    text: str = "🌐 Открыть",
) -> InlineKeyboardButton:
    """Создать отдельную WebApp кнопку.

    Args:
        url: URL WebApp
        text: Текст кнопки

    Returns:
        InlineKeyboardButton с WebApp
    """
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))


def get_combined_web_app_keyboard(
    webapp_url: str,
    webapp_text: str = "🌐 Открыть WebApp",
    additional_buttons: list[list[InlineKeyboardButton]] | None = None,
) -> InlineKeyboardMarkup:
    """Создать комбинированную клавиатуру с WebApp и дополнительными кнопками.

    Args:
        webapp_url: URL WebApp
        webapp_text: Текст WebApp кнопки
        additional_buttons: Дополнительные ряды кнопок

    Returns:
        InlineKeyboardMarkup
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text=webapp_text,
                web_app=WebAppInfo(url=webapp_url),
            )
        ]
    ]

    if additional_buttons:
        keyboard.extend(additional_buttons)

    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)])

    return InlineKeyboardMarkup(keyboard)


def get_payment_keyboard(
    title: str,
    payment_provider_token: str,
) -> InlineKeyboardMarkup:
    """Создать клавиатуру с кнопкой оплаты.

    Args:
        title: Текст кнопки оплаты
        payment_provider_token: Токен платежного провайдера (сохранен для будущего использования)

    Returns:
        InlineKeyboardMarkup с кнопкой оплаты
    """
    _ = payment_provider_token  # Reserved for future payment integration
    keyboard = [
        [InlineKeyboardButton(title, pay=True)],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_login_keyboard(
    title: str,
    login_url: str,
    forward_text: str | None = None,
) -> InlineKeyboardMarkup:
    """Создать клавиатуру с кнопкой для входа через Telegram Login Widget.

    Args:
        title: Текст кнопки
        login_url: URL для авторизации
        forward_text: Текст после авторизации (опционально)

    Returns:
        InlineKeyboardMarkup с кнопкой входа
    """
    login_info = LoginUrl(
        url=login_url,
        forward_text=forward_text,
        bot_username=None,
    )
    keyboard = [
        [InlineKeyboardButton(title, login_url=login_info)],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_request_contact_keyboard(
    button_text: str = "📱 Отправить контакт",
) -> ReplyKeyboardMarkup:
    """Создать клавиатуру запроса контакта.

    Args:
        button_text: Текст кнопки

    Returns:
        ReplyKeyboardMarkup с кнопкой запроса контакта
    """
    keyboard = [
        [KeyboardButton(text=button_text, request_contact=True)],
        [KeyboardButton(text="❌ Отмена")],
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def get_request_location_keyboard(
    button_text: str = "📍 Отправить геолокацию",
) -> ReplyKeyboardMarkup:
    """Создать клавиатуру запроса геолокации.

    Args:
        button_text: Текст кнопки

    Returns:
        ReplyKeyboardMarkup с кнопкой запроса локации
    """
    keyboard = [
        [KeyboardButton(text=button_text, request_location=True)],
        [KeyboardButton(text="❌ Отмена")],
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def get_api_key_input_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру для ввода API ключей.

    Returns:
        InlineKeyboardMarkup
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="📋 Вставить из буфера",
                callback_data="api_paste",
            ),
        ],
        [
            InlineKeyboardButton(
                text="❓ Где найти ключи?",
                url="https://dmarket.com/profile/api",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📖 Инструкция",
                callback_data="api_help",
            ),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data=CB_CANCEL),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
