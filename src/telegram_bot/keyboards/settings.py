"""Клавиатуры настроек.

Содержит клавиатуры для меню настроек, выбора языка,
профиля риска и подтверждений.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.dmarket.arbitrage import GAMES
from src.telegram_bot.keyboards.utils import CB_BACK, CB_CANCEL, CB_GAME_PREFIX


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру настроек.

    Returns:
        InlineKeyboardMarkup с опциями настроек

    Telegram UI:
        ┌─────────────────────────────────┐
        │ ⚙️ Настройки                    │
        ├─────────────────────────────────┤
        │ [🌐 Язык] [🔔 Уведомления]      │
        │ [🔑 API ключи] [⚠️ Профиль риска]│
        │ [💰 Лимиты] [🎮 Игры]           │
        │ [◀️ Назад]                      │
        └─────────────────────────────────┘
    """
    keyboard = [
        [
            InlineKeyboardButton(text="🌐 Язык", callback_data="settings_language"),
            InlineKeyboardButton(
                text="🔔 Уведомления", callback_data="settings_notify"
            ),
        ],
        [
            InlineKeyboardButton(text="🔑 API ключи", callback_data="settings_api"),
            InlineKeyboardButton(
                text="⚠️ Профиль риска", callback_data="settings_risk"
            ),
        ],
        [
            InlineKeyboardButton(text="💰 Лимиты", callback_data="settings_limits"),
            InlineKeyboardButton(text="🎮 Игры", callback_data="settings_games"),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_to_settings_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру возврата к настройкам.

    Returns:
        InlineKeyboardMarkup с кнопкой возврата
    """
    keyboard = [[InlineKeyboardButton(text="◀️ Назад", callback_data="settings")]]
    return InlineKeyboardMarkup(keyboard)


def create_settings_keyboard() -> InlineKeyboardMarkup:
    """Создать альтернативную клавиатуру настроек.

    Returns:
        InlineKeyboardMarkup с опциями настроек
    """
    keyboard = [
        [
            InlineKeyboardButton(text="🌐 Язык", callback_data="set_language"),
            InlineKeyboardButton(
                text="🔔 Уведомления", callback_data="set_notifications"
            ),
        ],
        [
            InlineKeyboardButton(text="🔑 API", callback_data="set_api"),
            InlineKeyboardButton(text="⚠️ Риск", callback_data="set_risk"),
        ],
        [
            InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_language_keyboard(current_language: str = "ru") -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора языка.

    Args:
        current_language: Текущий язык (для выделения)

    Returns:
        InlineKeyboardMarkup с доступными языками

    Telegram UI:
        ┌─────────────────────────────────┐
        │ Выберите язык / Choose language │
        ├─────────────────────────────────┤
        │ [🇷🇺 Русский] [🇬🇧 English]     │
        │ [🇪🇸 Español] [🇩🇪 Deutsch]     │
        │ [◀️ Назад]                      │
        └─────────────────────────────────┘
    """
    languages = {
        "ru": "🇷🇺 Русский",
        "en": "🇬🇧 English",
        "es": "🇪🇸 Español",
        "de": "🇩🇪 Deutsch",
    }

    buttons = []
    for lang_code, lang_name in languages.items():
        # Добавить галочку для текущего языка
        mark = " ✓" if lang_code == current_language else ""
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{lang_name}{mark}",
                    callback_data=f"lang_{lang_code}",
                )
            ]
        )

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings")])

    return InlineKeyboardMarkup(buttons)


def get_risk_profile_keyboard(current_risk: str = "medium") -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора профиля риска.

    Args:
        current_risk: Текущий профиль риска (для выделения)

    Returns:
        InlineKeyboardMarkup с профилями риска
    """
    profiles = {
        "low": "🟢 Низкий",
        "medium": "🟡 Средний",
        "high": "🔴 Высокий",
        "aggressive": "⚫ Агрессивный",
    }

    buttons = []
    for risk_code, risk_name in profiles.items():
        mark = " ✓" if risk_code == current_risk else ""
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{risk_name}{mark}",
                    callback_data=f"risk_{risk_code}",
                )
            ]
        )

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings")])

    return InlineKeyboardMarkup(buttons)


def create_confirm_keyboard(
    confirm_text: str = "✅ Подтвердить",
    cancel_text: str = "❌ Отмена",
    confirm_data: str = "confirm",
    cancel_data: str = CB_CANCEL,
) -> InlineKeyboardMarkup:
    """Создать клавиатуру подтверждения.

    Args:
        confirm_text: Текст кнопки подтверждения
        cancel_text: Текст кнопки отмены
        confirm_data: callback_data для подтверждения
        cancel_data: callback_data для отмены

    Returns:
        InlineKeyboardMarkup с кнопками подтверждения и отмены
    """
    keyboard = [
        [
            InlineKeyboardButton(text=confirm_text, callback_data=confirm_data),
            InlineKeyboardButton(text=cancel_text, callback_data=cancel_data),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_game_selection_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора игры для настроек.

    Returns:
        InlineKeyboardMarkup с играми
    """
    game_labels = {
        "csgo": "🔫 CS2/CS:GO",
        "dota2": "⚔️ Dota 2",
        "tf2": "🎩 Team Fortress 2",
        "rust": "🏠 Rust",
    }

    buttons = []
    for game_id, game_name in GAMES.items():
        label = game_labels.get(game_id, f"🎮 {game_name}")
        buttons.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"{CB_GAME_PREFIX}{game_id}",
                )
            ]
        )

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings")])

    return InlineKeyboardMarkup(buttons)
