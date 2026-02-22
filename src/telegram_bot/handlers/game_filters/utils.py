"""Утилиты для работы с фильтрами игровых предметов.

Предоставляет функции для:
- Получения и обновления фильтров из контекста пользователя
- Создания клавиатур для выбора фильтров
- Получения описания фильтров
- Построения параметров API
"""

from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.dmarket.game_filters import FilterFactory

from .constants import DEFAULT_FILTERS


def get_current_filters(
    context: ContextTypes.DEFAULT_TYPE, game: str
) -> dict[str, Any]:
    """Получает текущие фильтры для игры из контекста пользователя.

    Args:
        context: Контекст обратного вызова
        game: Код игры (csgo, dota2, tf2, rust)

    Returns:
        Словарь с текущими фильтрами

    """
    user_data = context.user_data
    if not user_data:
        default: dict[str, Any] = DEFAULT_FILTERS.get(game, {})
        return default.copy()

    filters = user_data.get("filters", {})
    game_filters: dict[str, Any] = filters.get(game, {})

    if not game_filters:
        default = DEFAULT_FILTERS.get(game, {})
        return dict(default)

    result: dict[str, Any] = dict(game_filters)
    return result


def update_filters(
    context: ContextTypes.DEFAULT_TYPE,
    game: str,
    new_filters: dict[str, Any],
) -> None:
    """Обновляет фильтры для игры в контексте пользователя.

    Args:
        context: Контекст обратного вызова
        game: Код игры (csgo, dota2, tf2, rust)
        new_filters: Новые значения фильтров

    """
    user_data = context.user_data
    if not user_data:
        user_data = {}
        context.user_data = user_data

    filters = user_data.get("filters", {})

    if not filters:
        filters = {}
        user_data["filters"] = filters

    filters[game] = new_filters


def get_game_filter_keyboard(game: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора фильтров игры.

    Args:
        game: Код игры (csgo, dota2, tf2, rust)

    Returns:
        Клавиатура с кнопками выбора фильтров

    """
    keyboard = []

    # Общие фильтры для всех игр
    keyboard.append(
        [
            InlineKeyboardButton(
                "💰 Диапазон цен",
                callback_data=f"price_range:{game}",
            ),
        ],
    )

    # Специфические фильтры для каждой игры
    if game == "csgo":
        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        "🔢 Диапазон Float",
                        callback_data=f"float_range:{game}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔫 Категория",
                        callback_data=f"set_category:{game}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "⭐ Редкость",
                        callback_data=f"set_rarity:{game}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🧩 Внешний вид",
                        callback_data=f"set_exterior:{game}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔢 StatTrak™",
                        callback_data=f"filter:stattrak:{game}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🏆 Сувенир",
                        callback_data=f"filter:souvenir:{game}",
                    ),
                ],
            ],
        )
    elif game == "dota2":
        keyboard.extend(
            [
                [InlineKeyboardButton("🦸 ГеSwarm", callback_data=f"set_hero:{game}")],
                [
                    InlineKeyboardButton(
                        "⭐ Редкость",
                        callback_data=f"set_rarity:{game}",
                    ),
                ],
                [InlineKeyboardButton("🧩 Слот", callback_data=f"set_slot:{game}")],
                [
                    InlineKeyboardButton(
                        "🏆 Качество",
                        callback_data=f"filter:quality:{game}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔄 Обмениваемость",
                        callback_data=f"filter:tradable:{game}",
                    ),
                ],
            ],
        )
    elif game == "tf2":
        keyboard.extend(
            [
                [InlineKeyboardButton("👤 Класс", callback_data=f"set_class:{game}")],
                [
                    InlineKeyboardButton(
                        "⭐ Качество",
                        callback_data=f"filter:quality:{game}",
                    ),
                ],
                [InlineKeyboardButton("🔫 Тип", callback_data=f"set_type:{game}")],
                [
                    InlineKeyboardButton(
                        "✨ Эффект",
                        callback_data=f"filter:effect:{game}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔢 Killstreak",
                        callback_data=f"filter:killstreak:{game}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔶 Australium",
                        callback_data=f"filter:australium:{game}",
                    ),
                ],
            ],
        )
    elif game == "rust":
        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        "🔫 Категория",
                        callback_data=f"set_category:{game}",
                    ),
                ],
                [InlineKeyboardButton("🧩 Тип", callback_data=f"set_type:{game}")],
                [
                    InlineKeyboardButton(
                        "⭐ Редкость",
                        callback_data=f"set_rarity:{game}",
                    ),
                ],
            ],
        )

    # Кнопки сброса и возврата
    keyboard.extend(
        [
            [
                InlineKeyboardButton(
                    "🔄 Сбросить фильтры",
                    callback_data=f"filter:reset:{game}",
                ),
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_filters:main")],
        ],
    )

    return InlineKeyboardMarkup(keyboard)


def get_filter_description(game: str, filters: dict[str, Any]) -> str:
    """Получает человекочитаемое описание фильтров.

    Args:
        game: Код игры (csgo, dota2, tf2, rust)
        filters: Словарь с фильтрами

    Returns:
        Строка с описанием фильтров

    """
    game_filter = FilterFactory.get_filter(game)
    return game_filter.get_filter_description(filters)


def build_api_params_for_game(game: str, filters: dict[str, Any]) -> dict[str, Any]:
    """Строит параметры для DMarket API на основе фильтров.

    Args:
        game: Код игры (csgo, dota2, tf2, rust)
        filters: Словарь с фильтрами

    Returns:
        Словарь с параметрами для API

    """
    game_filter = FilterFactory.get_filter(game)
    return game_filter.build_api_params(filters)


__all__ = [
    "build_api_params_for_game",
    "get_current_filters",
    "get_filter_description",
    "get_game_filter_keyboard",
    "update_filters",
]
