"""Клавиатуры фильтров.

Содержит клавиатуры для настройки фильтров цен, редкостей,
экстерьеров CS:GO и пагинации.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.telegram_bot.keyboards.utils import (
    CB_BACK,
    CB_CANCEL,
    CB_NEXT_PAGE,
    CB_PREV_PAGE,
)


def get_filter_keyboard(game: str = "csgo") -> InlineKeyboardMarkup:
    """Создать клавиатуру фильтров.

    Args:
        game: Код игры для специфичных фильтров

    Returns:
        InlineKeyboardMarkup с опциями фильтров
    """
    keyboard = [
        [
            InlineKeyboardButton(text="💰 Цена", callback_data="filter_price"),
            InlineKeyboardButton(text="⭐ Редкость", callback_data="filter_rarity"),
        ],
        [
            InlineKeyboardButton(text="🎯 Экстерьер", callback_data="filter_exterior"),
            InlineKeyboardButton(text="🔫 Тип оружия", callback_data="filter_weapon"),
        ],
        [
            InlineKeyboardButton(text="📊 StatTrak", callback_data="filter_stattrak"),
            InlineKeyboardButton(text="🏷️ Наклейки", callback_data="filter_stickers"),
        ],
        [
            InlineKeyboardButton(text="🔄 Сбросить все", callback_data="filter_reset"),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_price_range_keyboard(
    min_price: float | None = None,
    max_price: float | None = None,
) -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора ценового диапазона.

    Args:
        min_price: Минимальная цена (для отображения текущего диапазона)
        max_price: Максимальная цена (для отображения текущего диапазона)

    Returns:
        InlineKeyboardMarkup с диапазонами цен
    """
    ranges = [
        ("$0 - $5", "price_0_5"),
        ("$5 - $10", "price_5_10"),
        ("$10 - $25", "price_10_25"),
        ("$25 - $50", "price_25_50"),
        ("$50 - $100", "price_50_100"),
        ("$100 - $500", "price_100_500"),
        ("$500+", "price_500_plus"),
        ("📝 Свой диапазон", "price_custom"),
    ]

    keyboard = []
    # По 2 кнопки в ряд
    for i in range(0, len(ranges), 2):
        row = []
        for j in range(2):
            if i + j < len(ranges):
                text, data = ranges[i + j]
                row.append(InlineKeyboardButton(text=text, callback_data=data))
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="filters")])

    return InlineKeyboardMarkup(keyboard)


def get_csgo_exterior_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора экстерьера CS:GO.

    Returns:
        InlineKeyboardMarkup с экстерьерами
    """
    exteriors = [
        ("Factory New", "ext_fn"),
        ("Minimal Wear", "ext_mw"),
        ("Field-Tested", "ext_ft"),
        ("Well-Worn", "ext_ww"),
        ("Battle-Scarred", "ext_bs"),
    ]

    keyboard = []
    for text, data in exteriors:
        keyboard.append([InlineKeyboardButton(text=text, callback_data=data)])

    keyboard.extend(
        (
            [InlineKeyboardButton(text="🔄 Все", callback_data="ext_all")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="filters")],
        )
    )

    return InlineKeyboardMarkup(keyboard)


def get_rarity_keyboard(game: str = "csgo") -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора редкости.

    Args:
        game: Код игры для определения редкостей

    Returns:
        InlineKeyboardMarkup с редкостями
    """
    # CS:GO редкости
    if game == "csgo":
        rarities = [
            ("🔵 Consumer", "rarity_consumer"),
            ("🟢 Industrial", "rarity_industrial"),
            ("🔷 Mil-Spec", "rarity_milspec"),
            ("🟣 Restricted", "rarity_restricted"),
            ("💜 Classified", "rarity_classified"),
            ("🔴 Covert", "rarity_covert"),
            ("⭐ Contraband", "rarity_contraband"),
            ("🌟 Extraordinary", "rarity_extraordinary"),
        ]
    elif game == "dota2":
        rarities = [
            ("⬜ Common", "rarity_common"),
            ("🟢 Uncommon", "rarity_uncommon"),
            ("🔵 Rare", "rarity_rare"),
            ("🟣 Mythical", "rarity_mythical"),
            ("🟠 Legendary", "rarity_legendary"),
            ("🔴 Immortal", "rarity_immortal"),
            ("⭐ Arcana", "rarity_arcana"),
        ]
    else:
        rarities = [
            ("⬜ Common", "rarity_common"),
            ("🟢 Uncommon", "rarity_uncommon"),
            ("🔵 Rare", "rarity_rare"),
            ("🟣 Epic", "rarity_epic"),
            ("🟠 Legendary", "rarity_legendary"),
        ]

    keyboard = []
    for text, data in rarities:
        keyboard.append([InlineKeyboardButton(text=text, callback_data=data)])

    keyboard.extend(
        (
            [InlineKeyboardButton(text="🔄 Все", callback_data="rarity_all")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="filters")],
        )
    )

    return InlineKeyboardMarkup(keyboard)


def get_csgo_weapon_type_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора типа оружия CS:GO.

    Returns:
        InlineKeyboardMarkup с типами оружия
    """
    weapon_types = [
        ("🔫 Винтовки", "weapon_rifle"),
        ("💥 SMG", "weapon_smg"),
        ("🎯 Снайперки", "weapon_sniper"),
        ("🔪 Ножи", "weapon_knife"),
        ("🧤 Перчатки", "weapon_gloves"),
        ("🔫 Пистолеты", "weapon_pistol"),
        ("💣 Тяжелое", "weapon_heavy"),
        ("🎨 Наклейки", "weapon_stickers"),
        ("📦 Контейнеры", "weapon_containers"),
    ]

    keyboard = []
    # По 2 кнопки в ряд
    for i in range(0, len(weapon_types), 2):
        row = []
        for j in range(2):
            if i + j < len(weapon_types):
                text, data = weapon_types[i + j]
                row.append(InlineKeyboardButton(text=text, callback_data=data))
        keyboard.append(row)

    keyboard.extend(
        (
            [InlineKeyboardButton(text="🔄 Все", callback_data="weapon_all")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="filters")],
        )
    )

    return InlineKeyboardMarkup(keyboard)


def get_confirm_cancel_keyboard(
    confirm_data: str = "confirm",
    cancel_data: str = CB_CANCEL,
) -> InlineKeyboardMarkup:
    """Создать клавиатуру подтверждения/отмены.

    Args:
        confirm_data: callback_data для подтверждения
        cancel_data: callback_data для отмены

    Returns:
        InlineKeyboardMarkup с кнопками
    """
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=confirm_data),
            InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_data),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_pagination_keyboard(
    current_page: int,
    total_pages: int,
    base_callback: str = "page",
) -> InlineKeyboardMarkup:
    """Создать клавиатуру пагинации.

    Args:
        current_page: Текущая страница (1-indexed)
        total_pages: Всего страниц
        base_callback: Базовый callback для страниц

    Returns:
        InlineKeyboardMarkup с навигацией по страницам
    """
    keyboard = []
    nav_row = []

    # Кнопка "Первая"
    if current_page > 2:
        nav_row.append(
            InlineKeyboardButton(text="⏮️", callback_data=f"{base_callback}_1")
        )

    # Кнопка "Назад"
    if current_page > 1:
        nav_row.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=f"{CB_PREV_PAGE}_{base_callback}_{current_page - 1}",
            )
        )

    # Индикатор текущей страницы
    nav_row.append(
        InlineKeyboardButton(
            text=f"📄 {current_page}/{total_pages}",
            callback_data="page_info",
        )
    )

    # Кнопка "Вперед"
    if current_page < total_pages:
        nav_row.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=f"{CB_NEXT_PAGE}_{base_callback}_{current_page + 1}",
            )
        )

    # Кнопка "Последняя"
    if current_page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(
                text="⏭️",
                callback_data=f"{base_callback}_{total_pages}",
            )
        )

    if nav_row:
        keyboard.append(nav_row)

    # Кнопка "Назад"
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)])

    return InlineKeyboardMarkup(keyboard)
