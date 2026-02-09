"""Модуль клавиатур для Telegram бота.

Данный пакет содержит функции для создания клавиатур
различных типов (стандартные и инлайн) для Telegram бота,
согласно официальным рекомендациям Telegram Bot API.

Структура пакета:
- main.py: Главные меню и основные клавиатуры
- arbitrage.py: Клавиатуры для арбитража
- settings.py: Клавиатуры настроек и языка
- filters.py: Клавиатуры фильтров по играм
- alerts.py: Клавиатуры оповещений
- utils.py: Утилиты и билдеры клавиатур
"""

# Константы callback_data
# Alert keyboards
from src.telegram_bot.keyboards.alerts import (
    create_price_alerts_keyboard,
    get_alert_actions_keyboard,
    get_alert_keyboard,
    get_alert_type_keyboard,
)

# Arbitrage keyboards
from src.telegram_bot.keyboards.arbitrage import (
    create_arbitrage_keyboard,
    create_market_analysis_keyboard,
    get_advanced_orders_keyboard,
    get_arbitrage_keyboard,
    get_auto_arbitrage_keyboard,
    get_back_to_arbitrage_keyboard,
    get_doppler_phases_keyboard,
    get_float_arbitrage_keyboard,
    get_game_selection_keyboard,
    get_market_status_keyboard,
    get_marketplace_comparison_keyboard,
    get_modern_arbitrage_keyboard,
    get_pattern_selection_keyboard,
    get_smart_trading_keyboard,
    get_unified_strategies_keyboard,
    get_waxpeer_keyboard,
    get_waxpeer_listings_keyboard,
    get_waxpeer_settings_keyboard,
    get_x5_opportunities_keyboard,
)

# Filter keyboards
from src.telegram_bot.keyboards.filters import (
    get_confirm_cancel_keyboard,
    get_csgo_exterior_keyboard,
    get_csgo_weapon_type_keyboard,
    get_filter_keyboard,
    get_pagination_keyboard,
    get_price_range_keyboard,
    get_rarity_keyboard,
)

# Main keyboard is in src.telegram_bot.handlers.main_keyboard
# Settings keyboards
from src.telegram_bot.keyboards.settings import (
    create_confirm_keyboard,
    create_game_selection_keyboard,
    create_settings_keyboard,
    get_back_to_settings_keyboard,
    get_language_keyboard,
    get_risk_profile_keyboard,
    get_settings_keyboard,
)

# Утилиты
from src.telegram_bot.keyboards.utils import (
    CB_BACK,
    CB_CANCEL,
    CB_GAME_PREFIX,
    CB_HELP,
    CB_NEXT_PAGE,
    CB_PREV_PAGE,
    CB_SETTINGS,
    GAMES,
    build_menu,
    create_pagination_keyboard,
    extract_callback_data,
    force_reply,
    remove_keyboard,
)

# WebApp and special keyboards
from src.telegram_bot.keyboards.webapp import (
    get_combined_web_app_keyboard,
    get_dmarket_webapp_keyboard,
    get_login_keyboard,
    get_payment_keyboard,
    get_request_contact_keyboard,
    get_request_location_keyboard,
    get_webapp_button,
    get_webapp_keyboard,
)

__all__ = [
    # Constants
    "CB_BACK",
    "CB_CANCEL",
    "CB_GAME_PREFIX",
    "CB_HELP",
    "CB_NEXT_PAGE",
    "CB_PREV_PAGE",
    "CB_SETTINGS",
    "GAMES",
    # Utils
    "build_menu",
    # Arbitrage
    "create_arbitrage_keyboard",
    # Settings
    "create_confirm_keyboard",
    "create_game_selection_keyboard",
    # Main keyboard is in src.telegram_bot.handlers.main_keyboard
    "create_market_analysis_keyboard",
    "create_pagination_keyboard",
    # Alerts
    "create_price_alerts_keyboard",
    "create_settings_keyboard",
    "extract_callback_data",
    "force_reply",
    "get_advanced_orders_keyboard",
    "get_alert_actions_keyboard",
    "get_alert_keyboard",
    "get_alert_type_keyboard",
    "get_arbitrage_keyboard",
    "get_auto_arbitrage_keyboard",
    "get_back_to_arbitrage_keyboard",
    "get_back_to_settings_keyboard",
    # WebApp
    "get_combined_web_app_keyboard",
    # Filters
    "get_confirm_cancel_keyboard",
    "get_csgo_exterior_keyboard",
    "get_csgo_weapon_type_keyboard",
    "get_dmarket_webapp_keyboard",
    "get_doppler_phases_keyboard",
    "get_filter_keyboard",
    "get_float_arbitrage_keyboard",
    "get_game_selection_keyboard",
    "get_language_keyboard",
    "get_login_keyboard",
    "get_market_status_keyboard",
    "get_marketplace_comparison_keyboard",
    "get_modern_arbitrage_keyboard",
    "get_pagination_keyboard",
    "get_pattern_selection_keyboard",
    "get_payment_keyboard",
    "get_price_range_keyboard",
    "get_rarity_keyboard",
    "get_request_contact_keyboard",
    "get_request_location_keyboard",
    "get_risk_profile_keyboard",
    "get_settings_keyboard",
    "get_smart_trading_keyboard",
    "get_unified_strategies_keyboard",
    # Waxpeer
    "get_waxpeer_keyboard",
    "get_waxpeer_listings_keyboard",
    "get_waxpeer_settings_keyboard",
    "get_webapp_button",
    "get_webapp_keyboard",
    "get_x5_opportunities_keyboard",
    "remove_keyboard",
]
