"""Клавиатуры для арбитража.

Содержит клавиатуры для работы с арбитражным сканером,
автоматическим арбитражем и анализом рынка.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.dmarket.arbitrage import GAMES
from src.telegram_bot.keyboards.utils import CB_BACK, CB_GAME_PREFIX


def get_arbitrage_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру арбитражного меню.

    Returns:
        InlineKeyboardMarkup с опциями арбитража

    Telegram UI:
        ┌─────────────────────────────────┐
        │ Меню арбитража                  │
        ├─────────────────────────────────┤
        │ [🔍 Сканировать] [🎮 Выбор игры]│
        │ [📊 Уровни] [⚙️ НастSwarmки]      │
        │ [🤖 Авто-арбитраж]              │
        │ [◀️ Назад]                      │
        └─────────────────────────────────┘
    """
    keyboard = [
        [
            InlineKeyboardButton(text="🔍 Сканировать", callback_data="arb_scan"),
            InlineKeyboardButton(text="🎮 Выбор игры", callback_data="arb_game"),
        ],
        [
            InlineKeyboardButton(text="📊 Уровни", callback_data="arb_levels"),
            InlineKeyboardButton(text="⚙️ НастSwarmки", callback_data="arb_settings"),
        ],
        [
            InlineKeyboardButton(text="🤖 Авто-арбитраж", callback_data="arb_auto"),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_modern_arbitrage_keyboard() -> InlineKeyboardMarkup:
    """Создать современную клавиатуру арбитража с упрощенным меню.

    Обновленная версия с ссылкой на /simple и новыми стратегиями.

    Returns:
        InlineKeyboardMarkup с расширенными опциями

    Telegram UI:
        ┌─────────────────────────────────────┐
        │ Расширенное меню арбитража          │
        ├─────────────────────────────────────┤
        │ [⚡ Упрощенное меню]                │
        │ [🔎 ВСЕ СТРАТЕГИИ]                  │
        │ [🚀 Быстрый скан] [🔬 Глубокий скан]│
        │ [📈 Анализ рынка] [🔍 Многоуровневый]│
        │ [🎯 Float арбитраж] [📝 Расширенные]│
        │ [⚡ Enhanced Scanner] [📊 Статистика]│
        │ [📊 Режим рынка] [🔬 Backtest]      │
        │ [🎯 Создать таргет] [🔄 Сравнить]  │
        │ [💎 Waxpeer P2P] [📡 Мониторинг]   │
        │ [◀️ Главное меню]                   │
        └─────────────────────────────────────┘
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="⚡ Упрощенное меню", callback_data="simple_menu"
            ),
        ],
        # Новая секция: Unified Strategy System
        [
            InlineKeyboardButton(
                text="🔎 ВСЕ СТРАТЕГИИ",
                callback_data="auto_trade_scan_all",
            ),
        ],
        [
            InlineKeyboardButton(text="🚀 Быстрый скан", callback_data="arb_quick"),
            InlineKeyboardButton(text="🔬 Глубокий скан", callback_data="arb_deep"),
        ],
        [
            InlineKeyboardButton(
                text="📈 Анализ рынка", callback_data="arb_market_analysis"
            ),
            InlineKeyboardButton(
                text="🔍 Многоуровневый скан", callback_data="scanner"
            ),
        ],
        # Новые стратегии
        [
            InlineKeyboardButton(
                text="🎯 Float арбитраж", callback_data="float_arbitrage_menu"
            ),
            InlineKeyboardButton(
                text="📝 Расширенные ордера", callback_data="advanced_orders_menu"
            ),
        ],
        [
            InlineKeyboardButton(
                text="⚡ Enhanced Scanner", callback_data="enhanced_scanner_menu"
            ),
            InlineKeyboardButton(text="📊 Статистика", callback_data="arb_stats"),
        ],
        # NEW: Algo Arbitrage (main feature)
        [
            InlineKeyboardButton(text="🤖 Algo АРБИТРАЖ", callback_data="Algo_arb:menu"),
        ],
        # NEW: Regime & Backtest
        [
            InlineKeyboardButton(
                text="📊 Режим рынка", callback_data="regime:current:csgo"
            ),
            InlineKeyboardButton(text="🔬 Backtest", callback_data="backtest:back"),
        ],
        [
            InlineKeyboardButton(text="🎯 Создать таргет", callback_data="arb_target"),
            InlineKeyboardButton(
                text="🔄 Сравнить площадки", callback_data="arb_compare"
            ),
        ],
        # NEW: Waxpeer + Monitor
        [
            InlineKeyboardButton(text="💎 Waxpeer P2P", callback_data="waxpeer_menu"),
            InlineKeyboardButton(text="📡 Мониторинг", callback_data="monitor:status"),
        ],
        [
            InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_auto_arbitrage_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру авто-арбитража.

    Returns:
        InlineKeyboardMarkup с настSwarmками авто-арбитража

    Telegram UI:
        ┌─────────────────────────────────┐
        │ Авто-арбитраж                   │
        ├─────────────────────────────────┤
        │ [▶️ Запустить] [⏹️ Остановить]  │
        │ [⚙️ НастSwarmки] [📊 Статистика]  │
        │ [◀️ Назад]                      │
        └─────────────────────────────────┘
    """
    keyboard = [
        [
            InlineKeyboardButton(text="▶️ Запустить", callback_data="auto_arb_start"),
            InlineKeyboardButton(text="⏹️ Остановить", callback_data="auto_arb_stop"),
        ],
        [
            InlineKeyboardButton(
                text="⚙️ НастSwarmки", callback_data="auto_arb_settings"
            ),
            InlineKeyboardButton(text="📊 Статус", callback_data="auto_arb_status"),
        ],
        [
            InlineKeyboardButton(text="📜 История", callback_data="auto_arb_history"),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="arbitrage"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def create_arbitrage_keyboard(
    *,
    include_auto: bool = True,
    include_analysis: bool = True,
) -> InlineKeyboardMarkup:
    """Создать клавиатуру арбитража с настраиваемыми опциями.

    Args:
        include_auto: Включить кнопку авто-арбитража
        include_analysis: Включить кнопку анализа

    Returns:
        InlineKeyboardMarkup с выбранными опциями
    """
    keyboard = [
        [
            InlineKeyboardButton(text="🔍 Сканировать", callback_data="arb_scan"),
            InlineKeyboardButton(text="🎮 Игра", callback_data="arb_game"),
        ],
    ]

    if include_analysis:
        keyboard.append(
            [
                InlineKeyboardButton(text="📈 Анализ", callback_data="arb_analysis"),
                InlineKeyboardButton(text="📊 Уровни", callback_data="arb_levels"),
            ]
        )

    if include_auto:
        keyboard.append(
            [InlineKeyboardButton(text="🤖 Авто", callback_data="arb_auto")]
        )

    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data=CB_BACK)])

    return InlineKeyboardMarkup(keyboard)


def get_back_to_arbitrage_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру возврата к арбитражу.

    Returns:
        InlineKeyboardMarkup с кнопкой возврата
    """
    keyboard = [
        [InlineKeyboardButton(text="◀️ К арбитражу", callback_data="arbitrage")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_marketplace_comparison_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру сравнения маркетплейсов.

    Returns:
        InlineKeyboardMarkup с опциями сравнения
    """
    keyboard = [
        [
            InlineKeyboardButton(text="DMarket ↔️ Steam", callback_data="cmp_steam"),
            InlineKeyboardButton(text="DMarket ↔️ Buff", callback_data="cmp_buff"),
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="cmp_refresh"),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="arbitrage"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_game_selection_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора игры для арбитража.

    Returns:
        InlineKeyboardMarkup с играми
    """
    game_emojis = {
        "csgo": "🔫 CS2",
        "dota2": "⚔️ Dota 2",
        "tf2": "🎩 TF2",
        "rust": "🏠 Rust",
    }

    buttons = []
    row: list[InlineKeyboardButton] = []

    for game_id in GAMES:
        label = game_emojis.get(game_id, f"🎮 {game_id}")
        button = InlineKeyboardButton(
            text=label,
            callback_data=f"{CB_GAME_PREFIX}{game_id}",
        )
        row.append(button)

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="arbitrage")])

    return InlineKeyboardMarkup(buttons)


def create_market_analysis_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру анализа рынка.

    Returns:
        InlineKeyboardMarkup с опциями анализа
    """
    keyboard = [
        [
            InlineKeyboardButton(text="📊 Тренды", callback_data="analysis_trends"),
            InlineKeyboardButton(text="💹 Волатильность", callback_data="analysis_vol"),
        ],
        [
            InlineKeyboardButton(text="🔥 Топ продаж", callback_data="analysis_top"),
            InlineKeyboardButton(text="📉 Падающие", callback_data="analysis_drop"),
        ],
        [
            InlineKeyboardButton(text="🎯 Рекомендации", callback_data="analysis_rec"),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="arbitrage"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_smart_trading_keyboard(
    balance: float = 0.0,
    hunt_mode: bool = False,
    market_status: str = "Загрузка...",
) -> InlineKeyboardMarkup:
    """Создать умную клавиатуру с адаптивными лимитами.

    Args:
        balance: Текущий баланс пользователя
        hunt_mode: Включен ли режим охоты за X5
        market_status: Текущий статус рынка

    Returns:
        InlineKeyboardMarkup с умными кнопками
    """
    formatted_bal = f"${balance:,.2f}" if balance > 0 else "Загрузка..."
    hunt_status = "ВКЛ" if hunt_mode else "ВЫКЛ"

    keyboard = [
        # Главная кнопка запуска
        [
            InlineKeyboardButton(
                text=f"🚀 SMART START ({formatted_bal})",
                callback_data="start_smart_arbitrage",
            ),
        ],
        # Статус рынка и X5 охота
        [
            InlineKeyboardButton(
                text=f"📊 {market_status}",
                callback_data="show_market_status",
            ),
            InlineKeyboardButton(
                text=f"🔥 X5 Охота: {hunt_status}",
                callback_data="toggle_x5_hunt",
            ),
        ],
        # Статистика и баланс
        [
            InlineKeyboardButton(
                text="📈 Стата по играм", callback_data="stats_by_games"
            ),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_balance"),
        ],
        # Управление листами
        [
            InlineKeyboardButton(text="✅ WhiteList", callback_data="manage_whitelist"),
            InlineKeyboardButton(text="🚫 BlackList", callback_data="manage_blacklist"),
        ],
        # НастSwarmки и репрайсинг
        [
            InlineKeyboardButton(
                text="♻️ Репрайсинг", callback_data="toggle_repricing"
            ),
            InlineKeyboardButton(text="⚙️ Лимиты", callback_data="config_limits"),
        ],
        # Экстренная остановка
        [
            InlineKeyboardButton(
                text="🛑 ЭКСТРЕННАЯ ОСТАНОВКА", callback_data="panic_stop"
            ),
        ],
        # Назад в главное меню
        [
            InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_x5_opportunities_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру X5 возможностей.

    Returns:
        InlineKeyboardMarkup для X5 охоты
    """
    keyboard = [
        [
            InlineKeyboardButton(text="🔍 Сканировать X5", callback_data="scan_x5"),
            InlineKeyboardButton(
                text="📊 Текущие возможности", callback_data="show_x5_opps"
            ),
        ],
        [
            InlineKeyboardButton(text="⚙️ НастSwarmки X5", callback_data="x5_settings"),
            InlineKeyboardButton(text="📈 История X5", callback_data="x5_history"),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="smart_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_market_status_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру статуса рынка.

    Returns:
        InlineKeyboardMarkup для просмотра рыночных данных
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="🔄 Обновить статус", callback_data="refresh_market"
            ),
            InlineKeyboardButton(text="📊 Детали", callback_data="market_details"),
        ],
        [
            InlineKeyboardButton(
                text="📈 Индикаторы", callback_data="market_indicators"
            ),
            InlineKeyboardButton(text="⚠️ Алерты", callback_data="market_alerts"),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="smart_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_waxpeer_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру Waxpeer P2P.

    Returns:
        InlineKeyboardMarkup для управления Waxpeer интеграцией
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="💰 Баланс Waxpeer", callback_data="waxpeer_balance"
            ),
            InlineKeyboardButton(text="📦 Мои лоты", callback_data="waxpeer_listings"),
        ],
        [
            InlineKeyboardButton(
                text="📤 Листинг предметов", callback_data="waxpeer_list_items"
            ),
            InlineKeyboardButton(
                text="💎 Ценные находки", callback_data="waxpeer_valuable"
            ),
        ],
        [
            InlineKeyboardButton(
                text="♻️ Авто-репрайсинг", callback_data="waxpeer_reprice"
            ),
            InlineKeyboardButton(text="📊 Статистика", callback_data="waxpeer_stats"),
        ],
        [
            InlineKeyboardButton(text="⚙️ НастSwarmки", callback_data="waxpeer_settings"),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="arbitrage"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_waxpeer_settings_keyboard(
    reprice_enabled: bool = True,
    shadow_enabled: bool = True,
    auto_hold: bool = True,
) -> InlineKeyboardMarkup:
    """Создать клавиатуру настроек Waxpeer.

    Args:
        reprice_enabled: Включен ли авто-репрайсинг
        shadow_enabled: Включен ли shadow listing
        auto_hold: Включен ли auto-hold для редких

    Returns:
        InlineKeyboardMarkup для настроек Waxpeer
    """
    reprice_status = "✅" if reprice_enabled else "❌"
    shadow_status = "✅" if shadow_enabled else "❌"
    hold_status = "✅" if auto_hold else "❌"

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"{reprice_status} Авто-репрайсинг",
                callback_data="waxpeer_toggle_reprice",
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{shadow_status} Shadow Listing",
                callback_data="waxpeer_toggle_shadow",
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{hold_status} Auto-Hold редких",
                callback_data="waxpeer_toggle_hold",
            ),
        ],
        [
            InlineKeyboardButton(
                text="💵 Наценки", callback_data="waxpeer_markup_settings"
            ),
            InlineKeyboardButton(
                text="⏱️ Интервалы", callback_data="waxpeer_interval_settings"
            ),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="waxpeer_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_waxpeer_listings_keyboard(
    page: int = 1, total_pages: int = 1
) -> InlineKeyboardMarkup:
    """Создать клавиатуру для просмотра лотов Waxpeer.

    Args:
        page: Текущая страница
        total_pages: Всего страниц

    Returns:
        InlineKeyboardMarkup для навигации по лотам
    """
    keyboard = []

    # Навигация по страницам
    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(
                InlineKeyboardButton(
                    text="◀️ Пред.", callback_data=f"waxpeer_page_{page - 1}"
                )
            )
        nav_row.append(
            InlineKeyboardButton(
                text=f"{page}/{total_pages}", callback_data="waxpeer_page_info"
            )
        )
        if page < total_pages:
            nav_row.append(
                InlineKeyboardButton(
                    text="След. ▶️", callback_data=f"waxpeer_page_{page + 1}"
                )
            )
        keyboard.append(nav_row)

    keyboard.extend(
        [
            [
                InlineKeyboardButton(
                    text="🔄 Обновить", callback_data="waxpeer_refresh_listings"
                ),
                InlineKeyboardButton(
                    text="❌ Снять все", callback_data="waxpeer_remove_all"
                ),
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="waxpeer_menu"),
            ],
        ]
    )
    return InlineKeyboardMarkup(keyboard)


def get_float_arbitrage_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру Float Value арбитража.

    Returns:
        InlineKeyboardMarkup для работы с Float арбитражем
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="🔍 Сканировать Float", callback_data="float_scan"
            ),
            InlineKeyboardButton(
                text="📊 Квартильный анализ", callback_data="float_quartile"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🎯 Премиальные флоаты", callback_data="float_premium"
            ),
            InlineKeyboardButton(
                text="💎 Редкие паттерны", callback_data="float_patterns"
            ),
        ],
        [
            InlineKeyboardButton(
                text="📝 Создать Float ордер", callback_data="float_create_order"
            ),
            InlineKeyboardButton(
                text="📋 Мои Float ордера", callback_data="float_my_orders"
            ),
        ],
        [
            InlineKeyboardButton(
                text="⚙️ НастSwarmки Float", callback_data="float_settings"
            ),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="arbitrage"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_advanced_orders_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру расширенных ордеров.

    Returns:
        InlineKeyboardMarkup для работы с расширенными ордерами
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="🎯 Float Range ордер",
                callback_data="adv_order_float",
            ),
        ],
        [
            InlineKeyboardButton(
                text="💎 Doppler Phase", callback_data="adv_order_doppler"
            ),
            InlineKeyboardButton(text="🔵 Blue Gem", callback_data="adv_order_pattern"),
        ],
        [
            InlineKeyboardButton(
                text="🏷️ Sticker ордер", callback_data="adv_order_sticker"
            ),
            InlineKeyboardButton(
                text="📊 StatTrak", callback_data="adv_order_stattrak"
            ),
        ],
        [
            InlineKeyboardButton(
                text="📋 Шаблоны ордеров", callback_data="adv_order_templates"
            ),
            InlineKeyboardButton(
                text="📜 Мои ордера", callback_data="adv_order_my_orders"
            ),
        ],
        [
            InlineKeyboardButton(
                text="⚙️ НастSwarmки", callback_data="adv_order_settings"
            ),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="arbitrage"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_unified_strategies_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру унифицированных стратегий.

    Returns:
        InlineKeyboardMarkup для выбора стратегий поиска
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="🔎 СКАНИРОВАТЬ ВСЕ",
                callback_data="auto_trade_scan_all",
            ),
        ],
        # Индивидуальные стратегии
        [
            InlineKeyboardButton(
                text="🔄 Cross-Platform", callback_data="strategy_cross_platform"
            ),
            InlineKeyboardButton(
                text="📊 Intramarket", callback_data="strategy_intramarket"
            ),
        ],
        [
            InlineKeyboardButton(text="🎯 Float Value", callback_data="strategy_float"),
            InlineKeyboardButton(
                text="💎 Pattern/Phase", callback_data="strategy_pattern"
            ),
        ],
        [
            InlineKeyboardButton(text="🎯 Targets", callback_data="strategy_targets"),
            InlineKeyboardButton(
                text="🧠 Smart Finder", callback_data="strategy_smart"
            ),
        ],
        # Пресеты
        [
            InlineKeyboardButton(
                text="⚡ Boost ($0.5-$3)", callback_data="preset_boost"
            ),
            InlineKeyboardButton(
                text="📈 Standard ($3-$15)", callback_data="preset_standard"
            ),
        ],
        [
            InlineKeyboardButton(
                text="💰 Medium ($15-$50)", callback_data="preset_medium"
            ),
            InlineKeyboardButton(text="🏆 Pro ($200+)", callback_data="preset_pro"),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="arbitrage"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_doppler_phases_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора Doppler фаз.

    Returns:
        InlineKeyboardMarkup для выбора фазы Doppler
    """
    keyboard = [
        [
            InlineKeyboardButton(text="🔴 Ruby (x6)", callback_data="doppler_ruby"),
            InlineKeyboardButton(
                text="🔵 Sapphire (x5)", callback_data="doppler_sapphire"
            ),
        ],
        [
            InlineKeyboardButton(
                text="⚫ Black Pearl (x4)", callback_data="doppler_black_pearl"
            ),
            InlineKeyboardButton(
                text="🟢 Emerald (x3)", callback_data="doppler_emerald"
            ),
        ],
        [
            InlineKeyboardButton(text="Phase 1", callback_data="doppler_phase1"),
            InlineKeyboardButton(text="Phase 2", callback_data="doppler_phase2"),
        ],
        [
            InlineKeyboardButton(text="Phase 3", callback_data="doppler_phase3"),
            InlineKeyboardButton(text="Phase 4", callback_data="doppler_phase4"),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="advanced_orders_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_pattern_selection_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора паттернов (Blue Gem и др.).

    Returns:
        InlineKeyboardMarkup для выбора редких паттернов
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="🔵 Blue Gem Tier 1", callback_data="pattern_blue_gem_t1"
            ),
        ],
        [
            InlineKeyboardButton(text="💎 #661 (Best)", callback_data="pattern_661"),
            InlineKeyboardButton(text="💎 #670 (2nd)", callback_data="pattern_670"),
        ],
        [
            InlineKeyboardButton(text="💎 #321 (3rd)", callback_data="pattern_321"),
            InlineKeyboardButton(text="💎 #387 (4th)", callback_data="pattern_387"),
        ],
        [
            InlineKeyboardButton(
                text="🔷 Другие Blue Gems", callback_data="pattern_blue_gem_other"
            ),
        ],
        [
            InlineKeyboardButton(
                text="⚙️ Свой паттерн ID", callback_data="pattern_custom"
            ),
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="advanced_orders_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
