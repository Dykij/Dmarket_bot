"""Пакет для обработки фильтров игровых предметов.

Предоставляет обработчики для настSwarmки и применения фильтров для разных игр:
- CS2/CSGO: качество, редкость, внешний вид, диапазоны float и цены
- Dota 2: геSwarm, редкость, слот, качество
- Team Fortress 2: класс, качество, тип, эффект
- Rust: категория, тип, редкость

Рефакторинг выполнен 14.12.2025 в рамках задачи R-7.
"""

# Constants
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

# Handlers
from .handlers import (
    handle_filter_value_callback,
    handle_float_range_callback,
    handle_game_filters,
    handle_price_range_callback,
    handle_select_game_filter_callback,
    handle_set_category_callback,
    handle_set_class_callback,
    handle_set_exterior_callback,
    handle_set_hero_callback,
    handle_set_quality_callback,
    handle_set_rarity_callback,
    handle_set_slot_callback,
    handle_set_type_callback,
)

# Utils
from .utils import (
    build_api_params_for_game,
    get_current_filters,
    get_filter_description,
    get_game_filter_keyboard,
    update_filters,
)

__all__ = [
    "CS2_CATEGORIES",
    "CS2_EXTERIORS",
    "CS2_RARITIES",
    "DEFAULT_FILTERS",
    "DOTA2_HEROES",
    "DOTA2_RARITIES",
    "DOTA2_SLOTS",
    "GAME_NAMES",
    "RUST_CATEGORIES",
    "RUST_RARITIES",
    "RUST_TYPES",
    "TF2_CLASSES",
    "TF2_QUALITIES",
    "TF2_TYPES",
    "build_api_params_for_game",
    "get_current_filters",
    "get_filter_description",
    "get_game_filter_keyboard",
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
    "update_filters",
]
