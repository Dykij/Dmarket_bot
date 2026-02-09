"""Утилиты и билдеры для клавиатур.

Содержит константы callback_data и вспомогательные функции
для построения клавиатур Telegram бота.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import (
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)

# Реэкспорт GAMES из arbitrage для обратной совместимости
from src.dmarket.arbitrage import GAMES

if TYPE_CHECKING:
    from collections.abc import Sequence

# Экспорт GAMES для использования в других модулях
__all__ = ["GAMES"]

# ============================================================================
# Константы для callback_data
# ============================================================================

CB_CANCEL = "cancel"
CB_BACK = "back"
CB_NEXT_PAGE = "next_page"
CB_PREV_PAGE = "prev_page"
CB_GAME_PREFIX = "game_"
CB_HELP = "help"
CB_SETTINGS = "settings"


# ============================================================================
# Функции-утилиты
# ============================================================================


def force_reply() -> ForceReply:
    """Создать объект ForceReply для принудительного ответа.

    Returns:
        ForceReply объект для использования в reply_markup
    """
    return ForceReply(selective=True)


def remove_keyboard() -> ReplyKeyboardRemove:
    """Создать объект для удаления клавиатуры.

    Returns:
        ReplyKeyboardRemove объект для удаления reply клавиатуры
    """
    return ReplyKeyboardRemove()


def extract_callback_data(callback_data: str, prefix: str) -> str:
    """Извлечь данные из callback_data по префиксу.

    Args:
        callback_data: Полная строка callback_data
        prefix: Префикс для удаления

    Returns:
        Данные без префикса
    """
    if callback_data.startswith(prefix):
        return callback_data[len(prefix) :]
    return callback_data


def build_menu(
    buttons: Sequence[InlineKeyboardButton],
    n_cols: int = 2,
    header_buttons: Sequence[InlineKeyboardButton] | None = None,
    footer_buttons: Sequence[InlineKeyboardButton] | None = None,
) -> list[list[InlineKeyboardButton]]:
    """Построить меню из списка кнопок.

    Args:
        buttons: Список кнопок для распределения по колонкам
        n_cols: Количество колонок (по умолчанию 2)
        header_buttons: Кнопки для верхнего ряда (опционально)
        footer_buttons: Кнопки для нижнего ряда (опционально)

    Returns:
        Двумерный список кнопок для InlineKeyboardMarkup
    """
    menu = [list(buttons[i : i + n_cols]) for i in range(0, len(buttons), n_cols)]

    if header_buttons:
        menu.insert(0, list(header_buttons))
    if footer_buttons:
        menu.append(list(footer_buttons))

    return menu


def create_pagination_keyboard(
    current_page: int,
    total_pages: int,
    prefix: str = "page_",
    *,
    show_first_last: bool = False,
    extra_buttons: list[InlineKeyboardButton] | None = None,
) -> InlineKeyboardMarkup:
    """Создать унифицированную клавиатуру пагинации.

    Args:
        current_page: Текущая страница (1-based)
        total_pages: Общее количество страниц
        prefix: Префикс для callback_data (по умолчанию "page_")
        show_first_last: Показывать кнопки "В начало"/"В конец"
        extra_buttons: Дополнительные кнопки для нижнего ряда

    Returns:
        InlineKeyboardMarkup с кнопками пагинации
    """
    buttons: list[InlineKeyboardButton] = []

    # Кнопка "В начало"
    if show_first_last and current_page > 2:
        buttons.append(InlineKeyboardButton(text="⏮️", callback_data=f"{prefix}1"))

    # Кнопка "Назад"
    if current_page > 1:
        buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"{prefix}{current_page - 1}"))

    # Индикатор текущей страницы
    buttons.append(InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="noop"))

    # Кнопка "Вперёд"
    if current_page < total_pages:
        buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"{prefix}{current_page + 1}"))

    # Кнопка "В конец"
    if show_first_last and current_page < total_pages - 1:
        buttons.append(InlineKeyboardButton(text="⏭️", callback_data=f"{prefix}{total_pages}"))

    rows = [buttons]

    # Добавить дополнительные кнопки
    if extra_buttons:
        rows.append(extra_buttons)

    return InlineKeyboardMarkup(rows)
