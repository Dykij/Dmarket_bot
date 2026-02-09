"""Обработчики Telegram для фильтров игровых предметов.

Содержит обработчики команд и callback'ов для настройки фильтров.
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .constants import (
    CS2_CATEGORIES,
    CS2_EXTERIORS,
    CS2_RARITIES,
    DEFAULT_FILTERS,
    DOTA2_HEROES,
    DOTA2_RARITIES,
    DOTA2_SLOTS,
    GAME_NAMES,
    RUST_CATEGORIES,
    RUST_RARITIES,
    RUST_TYPES,
    TF2_CLASSES,
    TF2_QUALITIES,
    TF2_TYPES,
)
from .utils import (
    get_current_filters,
    get_filter_description,
    get_game_filter_keyboard,
    update_filters,
)

logger = logging.getLogger(__name__)


async def handle_game_filters(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /filters - показывает выбор игры для фильтрации.

    Args:
        update: Объект обновления
        context: Контекст обратного вызова

    """
    if not update.message:
        return

    keyboard = [
        [
            InlineKeyboardButton("🎮 CS2", callback_data="select_game_filter:csgo"),
            InlineKeyboardButton("🎮 Dota 2", callback_data="select_game_filter:dota2"),
        ],
        [
            InlineKeyboardButton("🎮 TF2", callback_data="select_game_filter:tf2"),
            InlineKeyboardButton("🎮 Rust", callback_data="select_game_filter:rust"),
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data="arbitrage")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Выберите игру для настройки фильтров:",
        reply_markup=reply_markup,
    )


async def handle_select_game_filter_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обработчик выбора игры для фильтрации.

    Args:
        update: Объект обновления
        context: Контекст обратного вызова

    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    data = query.data.split(":")
    game = data[1] if len(data) > 1 else "csgo"

    filters = get_current_filters(context, game)
    description = get_filter_description(game, filters)
    reply_markup = get_game_filter_keyboard(game)

    game_name = GAME_NAMES.get(game, game)

    message_text = f"🎮 Настройка фильтров для {game_name}:\n\n"

    if description:
        message_text += f"📋 Текущие фильтры:\n{description}\n"
    else:
        message_text += "📋 Текущие фильтры: не настроены\n"

    await query.edit_message_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )


async def handle_price_range_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора диапазона цен.

    Args:
        update: Объект обновления
        context: Контекст обратного вызова

    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    data = query.data.split(":")
    game = data[1] if len(data) > 1 else "csgo"

    filters = get_current_filters(context, game)

    keyboard = [
        [
            InlineKeyboardButton(
                "$1-10",
                callback_data=f"filter:price_range:1:10:{game}",
            ),
            InlineKeyboardButton(
                "$10-50",
                callback_data=f"filter:price_range:10:50:{game}",
            ),
        ],
        [
            InlineKeyboardButton(
                "$50-100",
                callback_data=f"filter:price_range:50:100:{game}",
            ),
            InlineKeyboardButton(
                "$100-500",
                callback_data=f"filter:price_range:100:500:{game}",
            ),
        ],
        [
            InlineKeyboardButton(
                "$500+",
                callback_data=f"filter:price_range:500:10000:{game}",
            ),
            InlineKeyboardButton(
                "Сбросить",
                callback_data=f"filter:price_range:reset:{game}",
            ),
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"select_game_filter:{game}")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    min_price = filters.get("min_price", DEFAULT_FILTERS[game]["min_price"])
    max_price = filters.get("max_price", DEFAULT_FILTERS[game]["max_price"])

    await query.edit_message_text(
        text=f"💰 Настройка диапазона цен:\n\nТекущий диапазон: ${min_price:.2f} - ${max_price:.2f}\n\nВыберите новый диапазон цен:",
        reply_markup=reply_markup,
    )


async def handle_float_range_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора диапазона Float (для CS2).

    Args:
        update: Объект обновления
        context: Контекст обратного вызова

    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    data = query.data.split(":")
    game = data[1] if len(data) > 1 else "csgo"

    if game != "csgo":
        await query.edit_message_text(
            text="Диапазон Float доступен только для CS2.",
            reply_markup=get_game_filter_keyboard(game),
        )
        return

    filters = get_current_filters(context, game)

    keyboard = [
        [
            InlineKeyboardButton(
                "Factory New (0.00-0.07)",
                callback_data=f"filter:float_range:0.00:0.07:{game}",
            ),
            InlineKeyboardButton(
                "Minimal Wear (0.07-0.15)",
                callback_data=f"filter:float_range:0.07:0.15:{game}",
            ),
        ],
        [
            InlineKeyboardButton(
                "Field-Tested (0.15-0.38)",
                callback_data=f"filter:float_range:0.15:0.38:{game}",
            ),
            InlineKeyboardButton(
                "Well-Worn (0.38-0.45)",
                callback_data=f"filter:float_range:0.38:0.45:{game}",
            ),
        ],
        [
            InlineKeyboardButton(
                "Battle-Scarred (0.45-1.00)",
                callback_data=f"filter:float_range:0.45:1.00:{game}",
            ),
            InlineKeyboardButton(
                "Сбросить",
                callback_data=f"filter:float_range:reset:{game}",
            ),
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"select_game_filter:{game}")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    float_min = filters.get("float_min", DEFAULT_FILTERS[game]["float_min"])
    float_max = filters.get("float_max", DEFAULT_FILTERS[game]["float_max"])

    await query.edit_message_text(
        text=f"🔢 Настройка диапазона Float:\n\nТекущий диапазон: {float_min:.2f} - {float_max:.2f}\n\nВыберите новый диапазон Float:",
        reply_markup=reply_markup,
    )


async def handle_set_category_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обработчик выбора категории (для CS2 и Rust).

    Args:
        update: Объект обновления
        context: Контекст обратного вызова

    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    data = query.data.split(":")
    game = data[1] if len(data) > 1 else "csgo"

    filters = get_current_filters(context, game)

    keyboard = []
    categories = []

    if game == "csgo":
        categories = CS2_CATEGORIES
    elif game == "rust":
        categories = RUST_CATEGORIES

    row = []
    for i, category in enumerate(categories):
        row.append(
            InlineKeyboardButton(
                category,
                callback_data=f"filter:category:{category}:{game}",
            ),
        )

        if len(row) == 2 or i == len(categories) - 1:
            keyboard.append(row.copy())
            row = []

    keyboard.extend((
        [InlineKeyboardButton("Сбросить", callback_data=f"filter:category:reset:{game}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"select_game_filter:{game}")],
    ))

    reply_markup = InlineKeyboardMarkup(keyboard)

    current_category = filters.get("category", "Не выбрано")

    await query.edit_message_text(
        text=f"🔫 Выбор категории:\n\nТекущая категория: {current_category}\n\nВыберите категорию:",
        reply_markup=reply_markup,
    )


async def handle_set_rarity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора редкости.

    Args:
        update: Объект обновления
        context: Контекст обратного вызова

    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    data = query.data.split(":")
    game = data[1] if len(data) > 1 else "csgo"

    filters = get_current_filters(context, game)

    if game == "csgo":
        rarities = CS2_RARITIES
    elif game == "dota2":
        rarities = DOTA2_RARITIES
    elif game == "rust":
        rarities = RUST_RARITIES
    else:
        rarities = []

    keyboard = []
    row = []

    for i, rarity in enumerate(rarities):
        row.append(
            InlineKeyboardButton(
                rarity,
                callback_data=f"filter:rarity:{rarity}:{game}",
            ),
        )

        if len(row) == 2 or i == len(rarities) - 1:
            keyboard.append(row.copy())
            row = []

    keyboard.extend((
        [InlineKeyboardButton("Сбросить", callback_data=f"filter:rarity:reset:{game}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"select_game_filter:{game}")],
    ))

    reply_markup = InlineKeyboardMarkup(keyboard)

    current_rarity = filters.get("rarity", "Не выбрано")

    await query.edit_message_text(
        text=f"⭐ Выбор редкости:\n\nТекущая редкость: {current_rarity}\n\nВыберите редкость:",
        reply_markup=reply_markup,
    )


async def handle_set_exterior_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обработчик выбора внешнего вида (для CS2).

    Args:
        update: Объект обновления
        context: Контекст обратного вызова

    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    data = query.data.split(":")
    game = data[1] if len(data) > 1 else "csgo"

    if game != "csgo":
        await query.edit_message_text(
            text="Выбор внешнего вида доступен только для CS2.",
            reply_markup=get_game_filter_keyboard(game),
        )
        return

    filters = get_current_filters(context, game)

    keyboard = []

    for exterior in CS2_EXTERIORS:
        keyboard.append(
            [
                InlineKeyboardButton(
                    exterior,
                    callback_data=f"filter:exterior:{exterior}:{game}",
                ),
            ],
        )

    keyboard.extend((
        [InlineKeyboardButton("Сбросить", callback_data=f"filter:exterior:reset:{game}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"select_game_filter:{game}")],
    ))

    reply_markup = InlineKeyboardMarkup(keyboard)

    current_exterior = filters.get("exterior", "Не выбрано")

    await query.edit_message_text(
        text=f"🧩 Выбор внешнего вида:\n\nТекущий внешний вид: {current_exterior}\n\nВыберите внешний вид:",
        reply_markup=reply_markup,
    )


async def handle_set_hero_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора героя (для Dota 2).

    Args:
        update: Объект обновления
        context: Контекст обратного вызова

    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    data = query.data.split(":")
    game = data[1] if len(data) > 1 else "dota2"

    if game != "dota2":
        await query.edit_message_text(
            text="Выбор героя доступен только для Dota 2.",
            reply_markup=get_game_filter_keyboard(game),
        )
        return

    filters = get_current_filters(context, game)

    keyboard = []
    row = []

    for i, hero in enumerate(DOTA2_HEROES):
        row.append(
            InlineKeyboardButton(hero, callback_data=f"filter:hero:{hero}:{game}"),
        )

        if len(row) == 2 or i == len(DOTA2_HEROES) - 1:
            keyboard.append(row.copy())
            row = []

    keyboard.extend((
        [InlineKeyboardButton("Сбросить", callback_data=f"filter:hero:reset:{game}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"select_game_filter:{game}")],
    ))

    reply_markup = InlineKeyboardMarkup(keyboard)

    current_hero = filters.get("hero", "Не выбрано")

    await query.edit_message_text(
        text=f"🦸 Выбор героя:\n\nТекущий герой: {current_hero}\n\nВыберите героя:",
        reply_markup=reply_markup,
    )


async def handle_set_slot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора слота (для Dota 2).

    Args:
        update: Объект обновления
        context: Контекст обратного вызова

    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    data = query.data.split(":")
    game = data[1] if len(data) > 1 else "dota2"

    if game != "dota2":
        await query.edit_message_text(
            text="Выбор слота доступен только для Dota 2.",
            reply_markup=get_game_filter_keyboard(game),
        )
        return

    filters = get_current_filters(context, game)

    keyboard = []
    row = []

    for i, slot in enumerate(DOTA2_SLOTS):
        row.append(
            InlineKeyboardButton(slot, callback_data=f"filter:slot:{slot}:{game}"),
        )

        if len(row) == 2 or i == len(DOTA2_SLOTS) - 1:
            keyboard.append(row.copy())
            row = []

    keyboard.extend((
        [InlineKeyboardButton("Сбросить", callback_data=f"filter:slot:reset:{game}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"select_game_filter:{game}")],
    ))

    reply_markup = InlineKeyboardMarkup(keyboard)

    current_slot = filters.get("slot", "Не выбрано")

    await query.edit_message_text(
        text=f"🧩 Выбор слота:\n\nТекущий слот: {current_slot}\n\nВыберите слот:",
        reply_markup=reply_markup,
    )


async def handle_set_class_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора класса (для TF2).

    Args:
        update: Объект обновления
        context: Контекст обратного вызова

    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    data = query.data.split(":")
    game = data[1] if len(data) > 1 else "tf2"

    if game != "tf2":
        await query.edit_message_text(
            text="Выбор класса доступен только для Team Fortress 2.",
            reply_markup=get_game_filter_keyboard(game),
        )
        return

    filters = get_current_filters(context, game)

    keyboard = []

    for tf_class in TF2_CLASSES:
        keyboard.append(
            [
                InlineKeyboardButton(
                    tf_class,
                    callback_data=f"filter:class:{tf_class}:{game}",
                ),
            ],
        )

    keyboard.extend((
        [InlineKeyboardButton("Сбросить", callback_data=f"filter:class:reset:{game}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"select_game_filter:{game}")],
    ))

    reply_markup = InlineKeyboardMarkup(keyboard)

    current_class = filters.get("class", "Не выбрано")

    await query.edit_message_text(
        text=f"👤 Выбор класса:\n\nТекущий класс: {current_class}\n\nВыберите класс:",
        reply_markup=reply_markup,
    )


async def handle_set_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора типа (для TF2 и Rust).

    Args:
        update: Объект обновления
        context: Контекст обратного вызова

    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    data = query.data.split(":")
    game = data[1] if len(data) > 1 else "tf2"

    filters = get_current_filters(context, game)

    if game == "tf2":
        types = TF2_TYPES
    elif game == "rust":
        types = RUST_TYPES
    else:
        types = []

    keyboard = []
    row = []

    for i, item_type in enumerate(types):
        row.append(
            InlineKeyboardButton(
                item_type,
                callback_data=f"filter:type:{item_type}:{game}",
            ),
        )

        if len(row) == 2 or i == len(types) - 1:
            keyboard.append(row.copy())
            row = []

    keyboard.extend((
        [InlineKeyboardButton("Сбросить", callback_data=f"filter:type:reset:{game}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"select_game_filter:{game}")],
    ))

    reply_markup = InlineKeyboardMarkup(keyboard)

    current_type = filters.get("type", "Не выбрано")

    await query.edit_message_text(
        text=f"🔫 Выбор типа:\n\nТекущий тип: {current_type}\n\nВыберите тип:",
        reply_markup=reply_markup,
    )


async def handle_set_quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора качества (для TF2).

    Args:
        update: Объект обновления
        context: Контекст обратного вызова

    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    data = query.data.split(":")
    game = data[1] if len(data) > 1 else "tf2"

    if game != "tf2":
        await query.edit_message_text(
            text="Выбор качества доступен только для Team Fortress 2.",
            reply_markup=get_game_filter_keyboard(game),
        )
        return

    filters = get_current_filters(context, game)

    keyboard = []

    for quality in TF2_QUALITIES:
        keyboard.append(
            [
                InlineKeyboardButton(
                    quality,
                    callback_data=f"filter:quality:{quality}:{game}",
                ),
            ],
        )

    keyboard.extend((
        [InlineKeyboardButton("Сбросить", callback_data=f"filter:quality:reset:{game}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"select_game_filter:{game}")],
    ))

    reply_markup = InlineKeyboardMarkup(keyboard)

    current_quality = filters.get("quality", "Не выбрано")

    await query.edit_message_text(
        text=f"⭐ Выбор качества:\n\nТекущее качество: {current_quality}\n\nВыберите качество:",
        reply_markup=reply_markup,
    )


async def handle_filter_value_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик установки значения фильтра.

    Args:
        update: Объект обновления
        context: Контекст обратного вызова

    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    # Парсим callback_data: filter:<filter_type>:<value>:<game>
    data = query.data.split(":")
    if len(data) < 4:
        return

    filter_type = data[1]
    value = data[2]
    game = data[3] if len(data) > 3 else "csgo"

    filters = get_current_filters(context, game)

    # Обработка разных типов фильтров
    if filter_type == "price_range":
        if value == "reset":
            filters["min_price"] = DEFAULT_FILTERS[game]["min_price"]
            filters["max_price"] = DEFAULT_FILTERS[game]["max_price"]
        else:
            min_price = float(data[2])
            max_price = float(data[3])
            game = data[4] if len(data) > 4 else "csgo"
            filters["min_price"] = min_price
            filters["max_price"] = max_price

    elif filter_type == "float_range":
        if value == "reset":
            filters["float_min"] = DEFAULT_FILTERS[game].get("float_min", 0.0)
            filters["float_max"] = DEFAULT_FILTERS[game].get("float_max", 1.0)
        else:
            float_min = float(data[2])
            float_max = float(data[3])
            game = data[4] if len(data) > 4 else "csgo"
            filters["float_min"] = float_min
            filters["float_max"] = float_max

    elif filter_type == "reset":
        # Сброс всех фильтров
        filters = DEFAULT_FILTERS.get(game, {}).copy()

    elif filter_type in {
        "category",
        "rarity",
        "exterior",
        "hero",
        "slot",
        "class",
        "type",
        "quality",
    }:
        if value == "reset":
            filters[filter_type] = None
        else:
            filters[filter_type] = value

    elif filter_type in {"stattrak", "souvenir", "tradable", "australium"}:
        # Toggle boolean filters
        current = filters.get(filter_type, False)
        filters[filter_type] = not current

    # Сохраняем обновленные фильтры
    update_filters(context, game, filters)

    # Возвращаемся к меню фильтров
    description = get_filter_description(game, filters)
    reply_markup = get_game_filter_keyboard(game)

    game_name = GAME_NAMES.get(game, game)

    message_text = f"🎮 Настройка фильтров для {game_name}:\n\n"

    if description:
        message_text += f"📋 Текущие фильтры:\n{description}\n"
    else:
        message_text += "📋 Текущие фильтры: не настроены\n"

    await query.edit_message_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )


__all__ = [
    "handle_filter_value_callback",
    "handle_float_range_callback",
    "handle_game_filters",
    "handle_price_range_callback",
    "handle_select_game_filter_callback",
    "handle_set_category_callback",
    "handle_set_class_callback",
    "handle_set_exterior_callback",
    "handle_set_hero_callback",
    "handle_set_quality_callback",
    "handle_set_rarity_callback",
    "handle_set_slot_callback",
    "handle_set_type_callback",
]
