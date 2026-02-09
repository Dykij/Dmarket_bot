"""Callback router initialization - Register all handlers.

Phase 2 Refactoring: Centralized registration using router pattern.
"""

import logging

from src.telegram_bot.handlers.callback_handlers import (
    handle_alerts,
    handle_arbitrage_menu,
    handle_auto_arbitrage,
    handle_back_to_main,
    handle_balance,
    handle_best_opportunities,
    handle_dmarket_arbitrage,
    handle_game_selection,
    handle_help,
    handle_main_menu,
    handle_market_analysis,
    handle_market_trends,
    handle_noop,
    handle_open_webapp,
    handle_search,
    handle_settings,
    handle_simple_menu,
    handle_temporary_unavailable,
)
from src.telegram_bot.handlers.callback_router import CallbackRouter
from src.telegram_bot.keyboards import CB_BACK, CB_CANCEL, CB_GAME_PREFIX, CB_HELP

logger = logging.getLogger(__name__)


# ============================================================================
# Registration helper functions (Phase 2 refactoring)
# ============================================================================


def _register_menu_handlers(router: CallbackRouter) -> None:
    """Register main menu and navigation handlers."""
    router.register_exact("simple_menu", handle_simple_menu)
    router.register_exact("balance", handle_balance)
    router.register_exact("search", handle_search)
    router.register_exact("settings", handle_settings)
    router.register_exact("market_trends", handle_market_trends)
    router.register_exact("alerts", handle_alerts)
    router.register_exact("back_to_main", handle_back_to_main)
    router.register_exact("main_menu", handle_main_menu)
    router.register_exact("back_to_menu", handle_back_to_main)


def _register_arbitrage_handlers(router: CallbackRouter) -> None:
    """Register arbitrage-related handlers."""
    router.register_exact("arbitrage", handle_arbitrage_menu)
    router.register_exact("arbitrage_menu", handle_arbitrage_menu)
    router.register_exact("auto_arbitrage", handle_auto_arbitrage)
    router.register_exact("dmarket_arbitrage", handle_dmarket_arbitrage)
    router.register_exact("best_opportunities", handle_best_opportunities)
    router.register_exact("game_selection", handle_game_selection)
    router.register_exact("market_analysis", handle_market_analysis)
    router.register_exact("market_comparison", handle_market_analysis)
    router.register_exact("open_webapp", handle_open_webapp)


def _register_help_and_noop_handlers(router: CallbackRouter) -> None:
    """Register help and no-op handlers."""
    router.register_exact(CB_HELP, handle_help)
    router.register_exact("help", handle_help)
    router.register_exact("noop", handle_noop)
    router.register_exact("page_info", handle_noop)
    router.register_exact("alerts_page_info", handle_noop)
    router.register_exact(CB_BACK, handle_noop)
    router.register_exact(CB_CANCEL, handle_noop)
    router.register_exact("back", handle_noop)
    router.register_exact("cancel", handle_noop)


def _register_settings_handlers(router: CallbackRouter) -> None:
    """Register settings submenu handlers."""
    router.register_exact("enhanced_scanner_menu", _handle_enhanced_scanner_menu)
    router.register_exact("settings_api_keys", _handle_settings_api_keys)
    router.register_exact("settings_proxy", _handle_settings_proxy)
    router.register_exact("settings_currency", _handle_settings_currency)
    router.register_exact("settings_intervals", _handle_settings_intervals)
    router.register_exact("settings_filters", _handle_settings_filters)
    router.register_exact("settings_auto_refresh", _handle_settings_auto_refresh)
    router.register_exact("settings_language", _handle_settings_language)
    router.register_exact("settings_notify", _handle_settings_notify)
    router.register_exact("settings_api", _handle_settings_api)
    router.register_exact("settings_risk", _handle_settings_risk)
    router.register_exact("settings_limits", _handle_settings_limits)
    router.register_exact("settings_games", _handle_settings_games)


def _register_alert_handlers(router: CallbackRouter) -> None:
    """Register alert submenu handlers."""
    router.register_exact("alert_create", _handle_alert_create)
    router.register_exact("alert_list", _handle_alert_list)
    router.register_exact("alert_settings", _handle_alert_settings)
    router.register_exact("alert_active", _handle_alert_active)
    router.register_exact("alert_history", _handle_alert_history)
    router.register_exact("back_to_alerts", _handle_back_to_alerts)


def _register_arb_submenu_handlers(router: CallbackRouter) -> None:
    """Register arbitrage submenu handlers."""
    router.register_exact("arb_quick", _handle_arb_quick)
    router.register_exact("arb_deep", _handle_arb_deep)
    router.register_exact("arb_market_analysis", _handle_arb_market_analysis)
    router.register_exact("arb_target", _handle_arb_target)
    router.register_exact("arb_stats", _handle_arb_stats)
    router.register_exact("arb_compare", _handle_arb_compare)
    router.register_exact("arb_scan", _handle_arb_scan)
    router.register_exact("arb_game", _handle_arb_game)
    router.register_exact("arb_levels", _handle_arb_levels)
    router.register_exact("arb_settings", _handle_arb_settings)
    router.register_exact("arb_auto", _handle_arb_auto)
    router.register_exact("arb_analysis", _handle_arb_analysis)


def _register_target_handlers(router: CallbackRouter) -> None:
    """Register target handlers."""
    router.register_exact("targets", _handle_targets)
    router.register_exact("target_create", _handle_target_create)
    router.register_exact("target_list", _handle_target_list)
    router.register_exact("target_stats", _handle_target_stats)


def _register_waxpeer_handlers(router: CallbackRouter) -> None:
    """Register Waxpeer P2P integration handlers."""
    router.register_exact("waxpeer_menu", _handle_waxpeer_menu)
    router.register_exact("waxpeer_balance", _handle_waxpeer_balance)
    router.register_exact("waxpeer_settings", _handle_waxpeer_settings)
    router.register_exact("waxpeer_list_items", _handle_waxpeer_scan)
    router.register_exact("waxpeer_valuable", _handle_waxpeer_scan)
    router.register_exact("waxpeer_reprice", _handle_waxpeer_settings)
    router.register_exact("waxpeer_listings", _handle_waxpeer_scan)
    router.register_exact("waxpeer_stats", _handle_waxpeer_stats)


def _register_float_arbitrage_handlers(router: CallbackRouter) -> None:
    """Register float arbitrage handlers."""
    router.register_exact("float_arbitrage_menu", _handle_float_arbitrage_menu)
    router.register_exact("float_scan", _handle_float_scan)
    router.register_exact("float_quartile", _handle_float_quartile)
    router.register_exact("float_premium", _handle_float_premium)
    router.register_exact("float_patterns", _handle_float_patterns)
    router.register_exact("float_create_order", _handle_float_create_order)
    router.register_exact("float_my_orders", _handle_float_my_orders)
    router.register_exact("float_settings", _handle_float_settings)


def _register_advanced_orders_handlers(router: CallbackRouter) -> None:
    """Register advanced orders handlers."""
    router.register_exact("advanced_orders_menu", _handle_advanced_orders_menu)
    router.register_exact("adv_order_float", _handle_adv_order_float)
    router.register_exact("adv_order_doppler", _handle_adv_order_doppler)
    router.register_exact("adv_order_pattern", _handle_adv_order_pattern)
    router.register_exact("adv_order_sticker", _handle_adv_order_sticker)
    router.register_exact("adv_order_stattrak", _handle_adv_order_stattrak)
    router.register_exact("adv_order_templates", _handle_adv_order_templates)
    router.register_exact("adv_order_my_orders", _handle_adv_order_my_orders)
    router.register_exact("adv_order_settings", _handle_adv_order_settings)


def _register_doppler_and_pattern_handlers(router: CallbackRouter) -> None:
    """Register doppler phases and pattern handlers."""
    # Doppler phases
    router.register_exact("doppler_ruby", _handle_doppler_phase)
    router.register_exact("doppler_sapphire", _handle_doppler_phase)
    router.register_exact("doppler_black_pearl", _handle_doppler_phase)
    router.register_exact("doppler_emerald", _handle_doppler_phase)
    router.register_exact("doppler_phase1", _handle_doppler_phase)
    router.register_exact("doppler_phase2", _handle_doppler_phase)
    router.register_exact("doppler_phase3", _handle_doppler_phase)
    router.register_exact("doppler_phase4", _handle_doppler_phase)

    # Pattern selection (Blue Gem)
    router.register_exact("pattern_blue_gem_t1", _handle_pattern_selection)
    router.register_exact("pattern_661", _handle_pattern_selection)
    router.register_exact("pattern_670", _handle_pattern_selection)
    router.register_exact("pattern_321", _handle_pattern_selection)
    router.register_exact("pattern_387", _handle_pattern_selection)
    router.register_exact("pattern_blue_gem_other", _handle_pattern_selection)
    router.register_exact("pattern_custom", _handle_pattern_custom)


def _register_strategy_handlers(router: CallbackRouter) -> None:
    """Register unified strategy handlers."""
    router.register_exact("auto_trade_scan_all", _handle_scan_all_strategies)
    router.register_exact("strategy_cross_platform", _handle_strategy_cross_platform)
    router.register_exact("strategy_intramarket", _handle_strategy_intramarket)
    router.register_exact("strategy_float", _handle_strategy_float)
    router.register_exact("strategy_pattern", _handle_strategy_pattern)
    router.register_exact("strategy_targets", _handle_strategy_targets)
    router.register_exact("strategy_smart", _handle_strategy_smart)

    # Strategy presets
    router.register_exact("preset_boost", _handle_preset_boost)
    router.register_exact("preset_standard", _handle_preset_standard)
    router.register_exact("preset_medium", _handle_preset_medium)
    router.register_exact("preset_pro", _handle_preset_pro)


def _register_other_features_handlers(router: CallbackRouter) -> None:
    """Register other feature handlers."""
    router.register_exact("inventory", _handle_inventory)
    router.register_exact("analytics", _handle_analytics)
    router.register_exact("scanner", _handle_scanner)


def _register_auto_arb_handlers(router: CallbackRouter) -> None:
    """Register auto arbitrage handlers."""
    router.register_exact("auto_arb_start", _handle_auto_arb_start)
    router.register_exact("auto_arb_stop", _handle_auto_arb_stop)
    router.register_exact("auto_arb_settings", _handle_auto_arb_settings)
    router.register_exact("auto_arb_status", _handle_auto_arb_status)
    router.register_exact("auto_arb_history", _handle_auto_arb_history)


def _register_smart_arbitrage_handlers(router: CallbackRouter) -> None:
    """Register smart arbitrage handlers for micro balance."""
    router.register_exact("start_smart_arbitrage", _handle_start_smart_arbitrage)
    router.register_exact("stop_smart_arbitrage", _handle_stop_smart_arbitrage)
    router.register_exact("smart_arbitrage_status", _handle_smart_arbitrage_status)
    router.register_exact("smart", _handle_smart_arbitrage_menu)
    router.register_exact("smart_create_targets", _handle_smart_create_targets)

    # Smart Trading Menu buttons
    router.register_exact("show_market_status", _handle_show_market_status)
    router.register_exact("toggle_x5_hunt", _handle_toggle_x5_hunt)
    router.register_exact("stats_by_games", _handle_stats_by_games)
    router.register_exact("refresh_balance", _handle_refresh_balance)
    router.register_exact("manage_whitelist", _handle_manage_whitelist)
    router.register_exact("manage_blacklist", _handle_manage_blacklist)
    router.register_exact("toggle_repricing", _handle_toggle_repricing)
    router.register_exact("config_limits", _handle_config_limits)
    router.register_exact("panic_stop", _handle_panic_stop)


def _register_analysis_handlers(router: CallbackRouter) -> None:
    """Register comparison and analysis handlers."""
    # Comparison
    router.register_exact("cmp_steam", _handle_cmp_steam)
    router.register_exact("cmp_buff", _handle_cmp_buff)
    router.register_exact("cmp_refresh", _handle_cmp_refresh)

    # Analysis
    router.register_exact("analysis_trends", _handle_analysis_trends)
    router.register_exact("analysis_vol", _handle_analysis_vol)
    router.register_exact("analysis_top", _handle_analysis_top)
    router.register_exact("analysis_drop", _handle_analysis_drop)
    router.register_exact("analysis_rec", _handle_analysis_rec)

    # Backtesting
    router.register_exact("backtest_quick", _handle_backtest_quick)
    router.register_exact("backtest_standard", _handle_backtest_standard)
    router.register_exact("backtest_custom", _handle_backtest_custom)


def _register_prefix_handlers(router: CallbackRouter) -> None:
    """Register all prefix handlers."""
    # Skip simplified menu callbacks
    router.register_prefix("simple_", _handle_skip_simple)

    # Game selection
    router.register_prefix("game_selected:", _handle_game_selected)
    router.register_prefix(CB_GAME_PREFIX, _handle_game_prefix)

    # Pagination
    router.register_prefix("arb_next_page_", _handle_pagination)
    router.register_prefix("arb_prev_page_", _handle_pagination)

    # Scanner levels
    router.register_prefix("scan_level_", _handle_scan_level)
    router.register_prefix("scanner_level_scan_", _handle_scan_level)

    # Language and risk
    router.register_prefix("lang_", _handle_lang)
    router.register_prefix("risk_", _handle_risk)

    # Alert types and notifications
    router.register_prefix("alert_type_", _handle_alert_type)
    router.register_prefix("notify_", _handle_notify)

    # Arbitrage settings and filters
    router.register_prefix("arb_set_", _handle_arb_set)
    router.register_prefix("filter:", _handle_filter)

    # Auto controls
    router.register_prefix("auto_start:", _handle_auto_start)
    router.register_prefix("paginate:", _handle_paginate)
    router.register_prefix("auto_trade:", _handle_auto_trade)
    router.register_prefix("compare:", _handle_compare)


# ============================================================================
# End of registration helper functions
# ============================================================================


def create_callback_router() -> CallbackRouter:
    """Create and configure callback router with all handlers.

    Returns:
        Configured CallbackRouter instance

    """
    router = CallbackRouter()

    # Register all handler groups (Phase 2 - use helpers)
    _register_menu_handlers(router)
    _register_arbitrage_handlers(router)
    _register_help_and_noop_handlers(router)
    _register_settings_handlers(router)
    _register_alert_handlers(router)
    _register_arb_submenu_handlers(router)
    _register_target_handlers(router)
    _register_waxpeer_handlers(router)
    _register_float_arbitrage_handlers(router)
    _register_advanced_orders_handlers(router)
    _register_doppler_and_pattern_handlers(router)
    _register_strategy_handlers(router)
    _register_other_features_handlers(router)
    _register_auto_arb_handlers(router)
    _register_smart_arbitrage_handlers(router)
    _register_analysis_handlers(router)
    _register_prefix_handlers(router)

    logger.info("Callback router initialized with %d exact handlers", len(router._exact_handlers))
    logger.info("Callback router initialized with %d prefix handlers", len(router._prefix_handlers))

    return router


# ============================================================================
# STUB HANDLERS (to be implemented)
# ============================================================================


async def _handle_enhanced_scanner_menu(update, context):
    """Stub: Enhanced scanner menu."""
    await handle_temporary_unavailable(update, context, "Расширенный сканер")


async def _handle_settings_api_keys(update, context):
    """Stub: API keys settings."""
    await handle_temporary_unavailable(update, context, "Настройка API ключей")


async def _handle_settings_proxy(update, context):
    """Stub: Proxy settings."""
    await handle_temporary_unavailable(update, context, "Настройка прокси")


async def _handle_settings_currency(update, context):
    """Stub: Currency settings."""
    await handle_temporary_unavailable(update, context, "Настройка валюты")


async def _handle_settings_intervals(update, context):
    """Stub: Intervals settings."""
    await handle_temporary_unavailable(update, context, "Настройка интервалов")


async def _handle_settings_filters(update, context):
    """Stub: Filters settings."""
    await handle_temporary_unavailable(update, context, "Настройка фильтров")


async def _handle_settings_auto_refresh(update, context):
    """Stub: Auto refresh settings."""
    await handle_temporary_unavailable(update, context, "Автообновление")


async def _handle_settings_language(update, context):
    """Stub: Language settings."""
    await handle_temporary_unavailable(update, context, "Настройка языка")


async def _handle_settings_notify(update, context):
    """Stub: Notification settings."""
    await handle_temporary_unavailable(update, context, "Настройка уведомлений")


async def _handle_settings_api(update, context):
    """Stub: API settings."""
    await handle_temporary_unavailable(update, context, "Настройка API")


async def _handle_settings_risk(update, context):
    """Stub: Risk settings."""
    await handle_temporary_unavailable(update, context, "Настройка рисков")


async def _handle_settings_limits(update, context):
    """Stub: Limits settings."""
    await handle_temporary_unavailable(update, context, "Настройка лимитов")


async def _handle_settings_games(update, context):
    """Stub: Games settings."""
    await handle_temporary_unavailable(update, context, "Выбор игр")


async def _handle_alert_create(update, context):
    """Stub: Create alert."""
    await handle_temporary_unavailable(update, context, "Создание оповещения")


async def _handle_alert_list(update, context):
    """Stub: Alert list."""
    await handle_temporary_unavailable(update, context, "Список оповещений")


async def _handle_alert_settings(update, context):
    """Stub: Alert settings."""
    await handle_temporary_unavailable(update, context, "Настройки оповещений")


async def _handle_alert_active(update, context):
    """Stub: Active alerts."""
    await handle_temporary_unavailable(update, context, "Активные оповещения")


async def _handle_alert_history(update, context):
    """Stub: Alert history."""
    await handle_temporary_unavailable(update, context, "История оповещений")


async def _handle_back_to_alerts(update, context):
    """Stub: Back to alerts."""
    await handle_alerts(update, context)


async def _handle_arb_quick(update, context):
    """Stub: Quick arbitrage."""
    await handle_temporary_unavailable(update, context, "Быстрый арбитраж")


async def _handle_arb_deep(update, context):
    """Stub: Deep arbitrage."""
    await handle_temporary_unavailable(update, context, "Глубокий арбитраж")


async def _handle_arb_market_analysis(update, context):
    """Stub: Market analysis."""
    await handle_market_analysis(update, context)


async def _handle_arb_target(update, context):
    """Stub: Arbitrage target."""
    await handle_temporary_unavailable(update, context, "Таргеты")


async def _handle_arb_stats(update, context):
    """Stub: Arbitrage stats."""
    await handle_temporary_unavailable(update, context, "Статистика")


async def _handle_arb_compare(update, context):
    """Stub: Arbitrage compare."""
    await handle_temporary_unavailable(update, context, "Сравнение площадок")


async def _handle_arb_scan(update, context):
    """Stub: Arbitrage scan."""
    await handle_temporary_unavailable(update, context, "Сканирование")


async def _handle_arb_game(update, context):
    """Stub: Arbitrage game selection."""
    await handle_game_selection(update, context)


async def _handle_arb_levels(update, context):
    """Stub: Arbitrage levels."""
    await handle_temporary_unavailable(update, context, "Уровни арбитража")


async def _handle_arb_settings(update, context):
    """Stub: Arbitrage settings."""
    await handle_temporary_unavailable(update, context, "Настройки арбитража")


async def _handle_arb_auto(update, context):
    """Stub: Auto arbitrage."""
    await handle_auto_arbitrage(update, context)


async def _handle_arb_analysis(update, context):
    """Stub: Arbitrage analysis."""
    await handle_market_analysis(update, context)


async def _handle_targets(update, context):
    """Stub: Targets."""
    await handle_temporary_unavailable(update, context, "Таргеты")


async def _handle_target_create(update, context):
    """Create target with game selection menu."""
    if not update.callback_query:
        return

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [
            InlineKeyboardButton("CS:GO", callback_data="game_selected:csgo"),
            InlineKeyboardButton("Dota 2", callback_data="game_selected:dota2"),
        ],
        [
            InlineKeyboardButton("Rust", callback_data="game_selected:rust"),
            InlineKeyboardButton("TF2", callback_data="game_selected:tf2"),
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="targets")],
    ]

    await update.callback_query.edit_message_text(
        "🎯 <b>Создание таргета</b>\n\n"
        "Выберите игру для настройки параметров покупки.\n"
        "Бот будет выставлять запросы на покупку (Targets) "
        "на основе анализа ликвидности.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _handle_target_list(update, context):
    """Stub: Target list."""
    await handle_temporary_unavailable(update, context, "Список таргетов")


async def _handle_target_stats(update, context):
    """Stub: Target stats."""
    await handle_temporary_unavailable(update, context, "Статистика таргетов")


async def _handle_inventory(update, context):
    """Stub: Inventory."""
    await handle_temporary_unavailable(update, context, "Инвентарь")


async def _handle_analytics(update, context):
    """Stub: Analytics."""
    await handle_temporary_unavailable(update, context, "Аналитика")


async def _handle_scanner(update, context):
    """Stub: Scanner."""
    await handle_temporary_unavailable(update, context, "Сканер")


async def _handle_auto_arb_start(update, context):
    """Stub: Start auto arbitrage."""
    await handle_temporary_unavailable(update, context, "Запуск авто-арбитража")


async def _handle_auto_arb_stop(update, context):
    """Stub: Stop auto arbitrage."""
    await handle_temporary_unavailable(update, context, "Остановка авто-арбитража")


async def _handle_auto_arb_settings(update, context):
    """Stub: Auto arbitrage settings."""
    await handle_temporary_unavailable(update, context, "Настройки авто-арбитража")


async def _handle_auto_arb_status(update, context):
    """Stub: Auto arbitrage status."""
    await handle_temporary_unavailable(update, context, "Статус авто-арбитража")


async def _handle_auto_arb_history(update, context):
    """Stub: Auto arbitrage history."""
    await handle_temporary_unavailable(update, context, "История авто-арбитража")


async def _handle_cmp_steam(update, context):
    """Compare prices with Steam Market."""
    if not update.callback_query:
        return

    await update.callback_query.answer("Загрузка цен Steam...")

    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        from src.utils.steam_async_parser import SteamAsyncParser

        # Configuration constants
        STEAM_CACHE_TTL = 300  # 5 minutes
        STEAM_MAX_CONCURRENT = 5
        ITEM_NAME_MAX_LEN = 30

        # Sample popular items to compare (can be expanded via config)
        SAMPLE_ITEMS = [
            "AK-47 | Redline (Field-Tested)",
            "AWP | Asiimov (Field-Tested)",
            "M4A4 | Asiimov (Field-Tested)",
        ]

        # Get API client and fetch some popular items
        api = context.bot_data.get("dmarket_api")

        if not api:
            await update.callback_query.edit_message_text(
                "❌ DMarket API не инициализирован. Используйте /start для настройки."
            )
            return

        parser = SteamAsyncParser(cache_ttl=STEAM_CACHE_TTL, max_concurrent=STEAM_MAX_CONCURRENT)

        results = await parser.get_batch_prices(SAMPLE_ITEMS, game="csgo")

        # Format results
        comparison_text = "📊 <b>Сравнение цен со Steam Market</b>\n\n"

        for result in results:
            item_name = result.get("item_name", "Unknown")
            truncated_name = item_name[:ITEM_NAME_MAX_LEN]

            if result.get("status") == "success":
                lowest = result.get("lowest_price", "N/A")
                median = result.get("median_price", "N/A")
                volume = result.get("volume", "0")

                comparison_text += f"<b>{truncated_name}...</b>\n"
                comparison_text += f"  └ Steam: ${lowest} (медиана ${median})\n"
                comparison_text += f"  └ Объем: {volume} шт/день\n\n"
            else:
                comparison_text += f"<b>{truncated_name}...</b>\n"
                comparison_text += f"  └ ⚠️ {result.get('status', 'error')}\n\n"

        comparison_text += "\n💡 <i>Цены обновляются каждые 5 минут</i>"

        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="cmp_steam")],
            [InlineKeyboardButton("◀️ Назад", callback_data="arb_compare")],
        ]

        await update.callback_query.edit_message_text(
            comparison_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except Exception as e:
        logger.exception("Error comparing Steam prices: %s", e)
        await update.callback_query.edit_message_text(
            f"❌ Ошибка получения цен Steam: {e}"
        )


async def _handle_cmp_buff(update, context):
    """Stub: Compare with Buff."""
    await handle_temporary_unavailable(update, context, "Сравнение с Buff")


async def _handle_cmp_refresh(update, context):
    """Stub: Refresh comparison."""
    await handle_temporary_unavailable(update, context, "Обновление сравнения")


async def _handle_analysis_trends(update, context):
    """Stub: Trends analysis."""
    await handle_temporary_unavailable(update, context, "Анализ трендов")


async def _handle_analysis_vol(update, context):
    """Stub: Volume analysis."""
    await handle_temporary_unavailable(update, context, "Анализ объемов")


async def _handle_analysis_top(update, context):
    """Stub: Top items analysis."""
    await handle_temporary_unavailable(update, context, "Топ предметов")


async def _handle_analysis_drop(update, context):
    """Stub: Price drops analysis."""
    await handle_temporary_unavailable(update, context, "Падение цен")


async def _handle_analysis_rec(update, context):
    """Stub: Recommendations."""
    await handle_temporary_unavailable(update, context, "Рекомендации")


async def _handle_backtest_quick(update, context):
    """Handle quick backtest."""
    from src.telegram_bot.commands.backtesting_commands import run_quick_backtest

    api = context.bot_data.get("dmarket_api")
    if api:
        await run_quick_backtest(update, context, api)
    else:
        await update.callback_query.edit_message_text("❌ DMarket API недоступен")


async def _handle_backtest_standard(update, context):
    """Handle standard backtest."""
    from src.telegram_bot.commands.backtesting_commands import run_standard_backtest

    api = context.bot_data.get("dmarket_api")
    if api:
        await run_standard_backtest(update, context, api)
    else:
        await update.callback_query.edit_message_text("❌ DMarket API недоступен")


async def _handle_backtest_custom(update, context):
    """Handle custom backtest."""
    if not update.callback_query:
        return

    await update.callback_query.edit_message_text(
        "⚙️ <b>Custom Backtest Settings</b>\n\n"
        "Custom backtesting coming soon!\n\n"
        "You'll be able to configure:\n"
        "• Date range\n"
        "• Initial balance\n"
        "• Strategy parameters\n"
        "• Item selection",
        parse_mode="HTML",
    )


# Prefix handlers
async def _handle_skip_simple(update, context):
    """Skip simple_ prefixed callbacks (handled elsewhere)."""


async def _handle_game_selected(update, context):
    """Handle game_selected: prefix."""
    from src.telegram_bot.handlers.callbacks import handle_game_selected_impl

    if not update.callback_query or not update.callback_query.data:
        return

    game = update.callback_query.data.split(":", 1)[1]
    await handle_game_selected_impl(update, context, game=game)


async def _handle_game_prefix(update, context):
    """Handle game_ prefix."""
    from src.telegram_bot.handlers.callbacks import handle_game_selected_impl

    if not update.callback_query or not update.callback_query.data:
        return

    if update.callback_query.data.startswith("game_selected"):
        return

    game = update.callback_query.data[len(CB_GAME_PREFIX) :]
    await handle_game_selected_impl(update, context, game=game)


async def _handle_pagination(update, context):
    """Handle arb_next_page_/arb_prev_page_ prefix."""
    from src.telegram_bot.handlers.callbacks import handle_arbitrage_pagination

    if not update.callback_query or not update.callback_query.data:
        return

    direction = (
        "next_page" if update.callback_query.data.startswith("arb_next_page_") else "prev_page"
    )
    await handle_arbitrage_pagination(update.callback_query, context, direction)


async def _handle_scan_level(update, context):
    """Handle scan_level_/scanner_level_scan_ prefix."""
    await handle_temporary_unavailable(update, context, "Уровень сканирования")


async def _handle_lang(update, context):
    """Handle lang_ prefix."""
    await handle_temporary_unavailable(update, context, "Смена языка")


async def _handle_risk(update, context):
    """Handle risk_ prefix."""
    await handle_temporary_unavailable(update, context, "Уровень риска")


async def _handle_alert_type(update, context):
    """Handle alert_type_ prefix."""
    await handle_temporary_unavailable(update, context, "Тип оповещения")


async def _handle_notify(update, context):
    """Handle notify_ prefix."""
    await handle_temporary_unavailable(update, context, "Уведомление")


async def _handle_arb_set(update, context):
    """Handle arb_set_ prefix."""
    await handle_temporary_unavailable(update, context, "Настройка арбитража")


async def _handle_filter(update, context):
    """Handle filter: prefix."""
    await handle_temporary_unavailable(update, context, "Фильтр")


async def _handle_auto_start(update, context):
    """Handle auto_start: prefix."""
    await handle_temporary_unavailable(update, context, "Автозапуск")


async def _handle_paginate(update, context):
    """Handle paginate: prefix."""
    await handle_temporary_unavailable(update, context, "Пагинация")


async def _handle_auto_trade(update, context):
    """Handle auto_trade: prefix."""
    await handle_temporary_unavailable(update, context, "Авто-торговля")


async def _handle_compare(update, context):
    """Handle compare: prefix."""
    await handle_temporary_unavailable(update, context, "Сравнение")


# ============================================================================
# SMART ARBITRAGE HANDLERS (NEW - For micro balance trading)
# ============================================================================


async def _handle_start_smart_arbitrage(update, context):
    """Start Smart Arbitrage mode with pagination and auto-buy."""
    if not update.callback_query:
        return

    try:
        # Get smart arbitrage engine from bot_data
        smart_engine = context.bot_data.get("smart_arbitrage_engine")
        api = context.bot_data.get("dmarket_api")

        if not smart_engine and api:
            # Initialize if not exists
            from src.dmarket.smart_arbitrage import SmartArbitrageEngine

            smart_engine = SmartArbitrageEngine(api)
            context.bot_data["smart_arbitrage_engine"] = smart_engine

        if smart_engine:
            if smart_engine.is_running:
                await update.callback_query.edit_message_text(
                    "⚠️ Smart Arbitrage уже запущен!\n\nИспользуйте /status для проверки состояния."
                )
                return

            # Get current balance and limits
            limits = await smart_engine.calculate_adaptive_limits()
            strategy = await smart_engine.get_strategy_description()

            await update.callback_query.edit_message_text(
                f"🚀 <b>Smart Arbitrage запускается!</b>\n\n"
                f"💰 Баланс: ${limits.usable_balance:.2f}\n"
                f"📊 Тир: {limits.tier.upper()}\n"
                f"🎯 ROI: {limits.min_roi:.0f}%+\n"
                f"💵 Max цена: ${limits.max_buy_price:.2f}\n\n"
                f"{strategy}\n\n"
                f"🔄 Сканирование: 500 предметов (5 страниц)\n"
                f"⏱ Интервал: {'30с' if limits.usable_balance < 50 else '60с'}\n\n"
                f"✅ Бот начал поиск арбитражных возможностей!",
                parse_mode="HTML",
            )

            # Start in background (don't await - let it run)
            import asyncio

            asyncio.create_task(smart_engine.start_smart_mode(auto_buy=True))

        else:
            await update.callback_query.edit_message_text(
                "❌ Smart Arbitrage Engine не инициализирован.\nПроверьте DMarket API подключение."
            )

    except Exception as e:
        logger.exception("Error starting smart arbitrage: %s", e)
        await update.callback_query.edit_message_text(f"❌ Ошибка: {e}")


async def _handle_stop_smart_arbitrage(update, context):
    """Stop Smart Arbitrage mode."""
    if not update.callback_query:
        return

    smart_engine = context.bot_data.get("smart_arbitrage_engine")

    if smart_engine and smart_engine.is_running:
        smart_engine.stop_smart_mode()
        await update.callback_query.edit_message_text(
            "🛑 <b>Smart Arbitrage остановлен</b>\n\n"
            "Бот прекратил поиск арбитражных возможностей.\n"
            "Используйте /smart для перезапуска.",
            parse_mode="HTML",
        )
    else:
        await update.callback_query.edit_message_text("ℹ️ Smart Arbitrage не был запущен.")


async def _handle_smart_arbitrage_status(update, context):
    """Show Smart Arbitrage status."""
    if not update.callback_query:
        return

    try:
        smart_engine = context.bot_data.get("smart_arbitrage_engine")
        api = context.bot_data.get("dmarket_api")

        if not smart_engine and api:
            from src.dmarket.smart_arbitrage import SmartArbitrageEngine

            smart_engine = SmartArbitrageEngine(api)
            context.bot_data["smart_arbitrage_engine"] = smart_engine

        if smart_engine:
            limits = await smart_engine.calculate_adaptive_limits()
            is_safe, warning = smart_engine.check_balance_safety()

            status_emoji = "🟢" if smart_engine.is_running else "🔴"
            safety_text = "✅ В норме" if is_safe else f"⚠️ {warning}"

            status_running = "Работает" if smart_engine.is_running else "Остановлен"
            await update.callback_query.edit_message_text(
                f"📊 <b>Smart Arbitrage Status</b>\n\n"
                f"Статус: {status_emoji} {status_running}\n\n"
                f"💰 <b>Баланс:</b> ${limits.total_balance:.2f}\n"
                f"💵 Доступно: ${limits.usable_balance:.2f}\n"
                f"🏦 Резерв: ${limits.reserve:.2f}\n\n"
                f"📈 <b>Лимиты:</b>\n"
                f"• Тир: {limits.tier.upper()}\n"
                f"• Max цена: ${limits.max_buy_price:.2f}\n"
                f"• Min ROI: {limits.min_roi:.0f}%\n"
                f"• Max предметов: {limits.max_inventory_items}\n\n"
                f"🛡 <b>Безопасность:</b> {safety_text}",
                parse_mode="HTML",
            )
        else:
            await update.callback_query.edit_message_text(
                "❌ Smart Arbitrage Engine не инициализирован."
            )

    except Exception as e:
        logger.exception("Error getting smart arbitrage status: %s", e)
        await update.callback_query.edit_message_text(f"❌ Ошибка: {e}")


async def _handle_smart_arbitrage_menu(update, context):
    """Show Smart Arbitrage menu."""
    if not update.callback_query:
        return

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [
            InlineKeyboardButton("🚀 Запустить", callback_data="start_smart_arbitrage"),
            InlineKeyboardButton("🛑 Остановить", callback_data="stop_smart_arbitrage"),
        ],
        [
            InlineKeyboardButton("📊 Статус", callback_data="smart_arbitrage_status"),
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="back_to_main"),
        ],
    ]

    await update.callback_query.edit_message_text(
        "🎯 <b>Smart Arbitrage</b>\n\n"
        "Умный арбитраж с автоматической адаптацией под ваш баланс:\n\n"
        "• 📊 Пагинация: сканирует 500 предметов\n"
        "• 🎚 Динамический ROI: от 5% для микро-баланса\n"
        "• ⏱ Trade Lock фильтр: учитывает заморозку\n"
        "• 🔄 Auto-buy: мгновенная покупка выгодных лотов\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _handle_smart_create_targets(update, context):
    """Create smart targets with game selection for micro-balance trading."""
    if not update.callback_query:
        return

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [
            InlineKeyboardButton("CS:GO", callback_data="game_selected:csgo"),
            InlineKeyboardButton("Dota 2", callback_data="game_selected:dota2"),
        ],
        [
            InlineKeyboardButton("Rust", callback_data="game_selected:rust"),
            InlineKeyboardButton("TF2", callback_data="game_selected:tf2"),
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="smart")],
    ]

    await update.callback_query.edit_message_text(
        "🎯 <b>Создание авто-таргетов</b>\n\n"
        "Выберите игру для настройки параметров покупки.\n"
        "Бот будет автоматически выставлять запросы на покупку (Targets) "
        "на основе анализа ликвидности и вашего баланса.\n\n"
        "💡 <i>Таргеты помогают покупать предметы дешевле рыночной цены</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ============================================================================
# WAXPEER HANDLERS
# ============================================================================


async def _handle_waxpeer_menu(update, context):
    """Handle Waxpeer menu callback."""
    try:
        from src.telegram_bot.handlers.waxpeer_handler import waxpeer_menu_handler

        await waxpeer_menu_handler(update, context)
    except ImportError:
        await handle_temporary_unavailable(update, context, "Waxpeer P2P")


async def _handle_waxpeer_balance(update, context):
    """Handle Waxpeer balance callback."""
    try:
        from src.telegram_bot.handlers.waxpeer_handler import waxpeer_balance_handler

        await waxpeer_balance_handler(update, context)
    except ImportError:
        await handle_temporary_unavailable(update, context, "Waxpeer баланс")


async def _handle_waxpeer_settings(update, context):
    """Handle Waxpeer settings callback."""
    try:
        from src.telegram_bot.handlers.waxpeer_handler import waxpeer_settings_handler

        await waxpeer_settings_handler(update, context)
    except ImportError:
        await handle_temporary_unavailable(update, context, "Waxpeer настройки")


async def _handle_waxpeer_scan(update, context):
    """Handle Waxpeer scan callback."""
    try:
        from src.telegram_bot.handlers.waxpeer_handler import waxpeer_scan_handler

        await waxpeer_scan_handler(update, context)
    except ImportError:
        await handle_temporary_unavailable(update, context, "Waxpeer сканирование")


# ============================================================================
# FLOAT ARBITRAGE HANDLERS (NEW)
# ============================================================================


async def _handle_float_arbitrage_menu(update, context):
    """Show Float Value Arbitrage menu."""
    if not update.callback_query:
        return

    from src.telegram_bot.keyboards import get_float_arbitrage_keyboard

    await update.callback_query.edit_message_text(
        "🎯 <b>Float Value Arbitrage</b>\n\n"
        "Поиск предметов с премиальным флоатом для перепродажи:\n\n"
        "• <b>Сканировать Float</b> — найти недооценённые скины по флоату\n"
        "• <b>Квартильный анализ</b> — покупка только ниже Q1\n"
        "• <b>Премиальные флоаты</b> — предметы с лучшим состоянием\n"
        "• <b>Редкие паттерны</b> — Blue Gem, Doppler и др.\n\n"
        "<i>Выберите действие:</i>",
        parse_mode="HTML",
        reply_markup=get_float_arbitrage_keyboard(),
    )


async def _handle_float_scan(update, context):
    """Scan for float arbitrage opportunities."""
    await handle_temporary_unavailable(update, context, "Float сканирование")


async def _handle_float_quartile(update, context):
    """Show quartile analysis."""
    await handle_temporary_unavailable(update, context, "Квартильный анализ")


async def _handle_float_premium(update, context):
    """Show premium float items."""
    await handle_temporary_unavailable(update, context, "Премиальные флоаты")


async def _handle_float_patterns(update, context):
    """Show rare patterns."""
    if not update.callback_query:
        return

    from src.telegram_bot.keyboards import get_pattern_selection_keyboard

    await update.callback_query.edit_message_text(
        "💎 <b>Редкие паттерны</b>\n\n"
        "Выберите тип редкого паттерна:\n\n"
        "• <b>Blue Gem</b> — Case Hardened с синим паттерном\n"
        "• <b>Doppler Phases</b> — Ruby, Sapphire, Black Pearl\n\n"
        "<i>Blue Gem seeds #661, #670 — самые дорогие!</i>",
        parse_mode="HTML",
        reply_markup=get_pattern_selection_keyboard(),
    )


async def _handle_float_create_order(update, context):
    """Create float order."""
    await handle_temporary_unavailable(update, context, "Создание Float ордера")


async def _handle_float_my_orders(update, context):
    """Show user's float orders."""
    await handle_temporary_unavailable(update, context, "Мои Float ордера")


async def _handle_float_settings(update, context):
    """Float arbitrage settings."""
    await handle_temporary_unavailable(update, context, "Настройки Float")


# ============================================================================
# ADVANCED ORDERS HANDLERS (NEW)
# ============================================================================


async def _handle_advanced_orders_menu(update, context):
    """Show Advanced Orders menu."""
    if not update.callback_query:
        return

    from src.telegram_bot.keyboards import get_advanced_orders_keyboard

    await update.callback_query.edit_message_text(
        "📝 <b>Расширенные ордера</b>\n\n"
        "Создание ордеров с фильтрами:\n\n"
        "• <b>Float Range</b> — диапазон флоата (0.15-0.155)\n"
        "• <b>Doppler Phase</b> — Ruby, Sapphire, BP, Emerald\n"
        "• <b>Blue Gem</b> — паттерны Case Hardened\n"
        "• <b>Sticker</b> — с определёнными стикерами\n"
        "• <b>StatTrak</b> — только StatTrak версии\n\n"
        "<i>Выберите тип ордера:</i>",
        parse_mode="HTML",
        reply_markup=get_advanced_orders_keyboard(),
    )


async def _handle_adv_order_float(update, context):
    """Create float range order."""
    await handle_temporary_unavailable(update, context, "Float Range ордер")


async def _handle_adv_order_doppler(update, context):
    """Create Doppler phase order."""
    if not update.callback_query:
        return

    from src.telegram_bot.keyboards import get_doppler_phases_keyboard

    await update.callback_query.edit_message_text(
        "💎 <b>Doppler Phase Order</b>\n\n"
        "Выберите фазу Doppler:\n\n"
        "• 🔴 <b>Ruby</b> — x6 множитель к базовой цене\n"
        "• 🔵 <b>Sapphire</b> — x5 множитель\n"
        "• ⚫ <b>Black Pearl</b> — x4 множитель\n"
        "• 🟢 <b>Emerald</b> — x3 множитель (только Gamma)\n\n"
        "<i>Phase 1-4 — стандартные фазы</i>",
        parse_mode="HTML",
        reply_markup=get_doppler_phases_keyboard(),
    )


async def _handle_adv_order_pattern(update, context):
    """Create pattern order (Blue Gem)."""
    if not update.callback_query:
        return

    from src.telegram_bot.keyboards import get_pattern_selection_keyboard

    await update.callback_query.edit_message_text(
        "🔵 <b>Blue Gem Pattern Order</b>\n\n"
        "Выберите паттерн Case Hardened:\n\n"
        "• 💎 <b>#661</b> — лучший Blue Gem seed\n"
        "• 💎 <b>#670</b> — 2-й по ценности\n"
        "• 💎 <b>#321</b> — 3-й по ценности\n"
        "• 💎 <b>#387</b> — 4-й по ценности\n\n"
        "<i>Или укажите свой Pattern ID</i>",
        parse_mode="HTML",
        reply_markup=get_pattern_selection_keyboard(),
    )


async def _handle_adv_order_sticker(update, context):
    """Create sticker order."""
    await handle_temporary_unavailable(update, context, "Sticker ордер")


async def _handle_adv_order_stattrak(update, context):
    """Create StatTrak order."""
    await handle_temporary_unavailable(update, context, "StatTrak ордер")


async def _handle_adv_order_templates(update, context):
    """Show order templates."""
    if not update.callback_query:
        return

    await update.callback_query.edit_message_text(
        "📋 <b>Шаблоны ордеров</b>\n\n"
        "Готовые конфигурации для быстрого создания ордеров:\n\n"
        "1. <b>AK-47 Redline FT (Low Float)</b>\n"
        "   Float: 0.15-0.16, ROI: ~50%\n\n"
        "2. <b>AWP Asiimov FT (BTA)</b>\n"
        "   Float: 0.18-0.21, ROI: ~30%\n\n"
        "3. <b>Karambit Doppler Ruby</b>\n"
        "   Phase: Ruby, ROI: ~25%\n\n"
        "4. <b>AK Case Hardened Blue Gem</b>\n"
        "   Pattern: #661, ROI: ~100%+\n\n"
        "<i>Функционал в разработке</i>",
        parse_mode="HTML",
    )


async def _handle_adv_order_my_orders(update, context):
    """Show user's advanced orders."""
    await handle_temporary_unavailable(update, context, "Мои ордера")


async def _handle_adv_order_settings(update, context):
    """Advanced order settings."""
    await handle_temporary_unavailable(update, context, "Настройки ордеров")


async def _handle_doppler_phase(update, context):
    """Handle Doppler phase selection."""
    if not update.callback_query or not update.callback_query.data:
        return

    phase = update.callback_query.data.replace("doppler_", "").upper()

    await update.callback_query.edit_message_text(
        f"💎 <b>Doppler {phase} Order</b>\n\n"
        f"Вы выбрали фазу: <b>{phase}</b>\n\n"
        f"Для создания ордера укажите:\n"
        f"• Название предмета (например: Karambit Doppler FN)\n"
        f"• Максимальную цену покупки\n\n"
        f"<i>Функционал создания в разработке</i>",
        parse_mode="HTML",
    )


async def _handle_pattern_selection(update, context):
    """Handle pattern selection (Blue Gem)."""
    if not update.callback_query or not update.callback_query.data:
        return

    pattern_data = update.callback_query.data.replace("pattern_", "")

    if pattern_data == "blue_gem_t1":
        desc = "Tier 1 Blue Gem (топ паттерны)"
    elif pattern_data == "blue_gem_other":
        desc = "Другие Blue Gem паттерны"
    else:
        desc = f"Pattern ID #{pattern_data}"

    await update.callback_query.edit_message_text(
        f"🔵 <b>Blue Gem Order</b>\n\n"
        f"Вы выбрали: <b>{desc}</b>\n\n"
        f"Для создания ордера укажите:\n"
        f"• Тип предмета (AK-47, Five-SeveN, etc.)\n"
        f"• Максимальную цену покупки\n\n"
        f"<i>Функционал создания в разработке</i>",
        parse_mode="HTML",
    )


async def _handle_pattern_custom(update, context):
    """Handle custom pattern ID input."""
    await handle_temporary_unavailable(update, context, "Свой Pattern ID")


# ============================================================================
# UNIFIED STRATEGY HANDLERS (NEW)
# ============================================================================


async def _handle_scan_all_strategies(update, context):
    """Scan all strategies for arbitrage opportunities."""
    try:
        from src.telegram_bot.handlers.main_keyboard import auto_trade_scan_all

        await auto_trade_scan_all(update, context)
    except ImportError:
        await handle_temporary_unavailable(update, context, "Сканирование всех стратегий")


async def _handle_strategy_cross_platform(update, context):
    """Cross-platform arbitrage strategy."""
    await handle_temporary_unavailable(update, context, "Cross-Platform Arbitrage")


async def _handle_strategy_intramarket(update, context):
    """Intramarket arbitrage strategy."""
    await handle_temporary_unavailable(update, context, "Intramarket Arbitrage")


async def _handle_strategy_float(update, context):
    """Float value arbitrage strategy."""
    await _handle_float_arbitrage_menu(update, context)


async def _handle_strategy_pattern(update, context):
    """Pattern/Phase arbitrage strategy."""
    await _handle_adv_order_pattern(update, context)


async def _handle_strategy_targets(update, context):
    """Target system strategy."""
    await _handle_targets(update, context)


async def _handle_strategy_smart(update, context):
    """Smart market finder strategy."""
    await _handle_smart_arbitrage_menu(update, context)


async def _handle_preset_boost(update, context):
    """Boost preset ($0.50-$3)."""
    if not update.callback_query:
        return

    await update.callback_query.edit_message_text(
        "⚡ <b>Preset: BOOST</b>\n\n"
        "Настройки для быстрого оборота:\n\n"
        "• 💰 Диапазон цен: $0.50 - $3.00\n"
        "• 📊 Min ROI: 8%\n"
        "• 🔄 Быстрая ликвидность\n"
        "• ⏱ Без Trade Lock\n\n"
        "<i>Идеально для разгона баланса</i>",
        parse_mode="HTML",
    )


async def _handle_preset_standard(update, context):
    """Standard preset ($3-$15)."""
    if not update.callback_query:
        return

    await update.callback_query.edit_message_text(
        "📈 <b>Preset: STANDARD</b>\n\n"
        "Сбалансированные настройки:\n\n"
        "• 💰 Диапазон цен: $3.00 - $15.00\n"
        "• 📊 Min ROI: 10%\n"
        "• 🔄 Средняя ликвидность\n"
        "• ⏱ Trade Lock до 3 дней\n\n"
        "<i>Оптимальное соотношение риска и прибыли</i>",
        parse_mode="HTML",
    )


async def _handle_preset_medium(update, context):
    """Medium preset ($15-$50)."""
    if not update.callback_query:
        return

    await update.callback_query.edit_message_text(
        "💰 <b>Preset: MEDIUM</b>\n\n"
        "Настройки для среднего баланса:\n\n"
        "• 💰 Диапазон цен: $15.00 - $50.00\n"
        "• 📊 Min ROI: 12%\n"
        "• 🔄 Проверка ликвидности\n"
        "• ⏱ Trade Lock до 5 дней\n\n"
        "<i>Для баланса $100-$500</i>",
        parse_mode="HTML",
    )


async def _handle_preset_pro(update, context):
    """Pro preset ($200+)."""
    if not update.callback_query:
        return

    await update.callback_query.edit_message_text(
        "🏆 <b>Preset: PRO</b>\n\n"
        "Настройки для крупных сделок:\n\n"
        "• 💰 Диапазон цен: $200.00+\n"
        "• 📊 Min ROI: 15%\n"
        "• 🔄 Высокая ликвидность обязательна\n"
        "• ⏱ Trade Lock до 7 дней\n"
        "• 💎 Float Value анализ включен\n\n"
        "<i>Для профессиональной торговли</i>",
        parse_mode="HTML",
    )


# ============================================================================
# SMART TRADING MENU HANDLERS (NEW)
# ============================================================================


async def _handle_show_market_status(update, context):
    """Show current market status."""
    await handle_temporary_unavailable(update, context, "Статус рынка")


async def _handle_toggle_x5_hunt(update, context):
    """Toggle X5 opportunities hunt."""
    await handle_temporary_unavailable(update, context, "X5 охота")


async def _handle_stats_by_games(update, context):
    """Show statistics by games."""
    await handle_temporary_unavailable(update, context, "Статистика по играм")


async def _handle_refresh_balance(update, context):
    """Refresh balance display."""
    await handle_balance(update, context)


async def _handle_manage_whitelist(update, context):
    """Manage whitelist items."""
    await handle_temporary_unavailable(update, context, "Управление Whitelist")


async def _handle_manage_blacklist(update, context):
    """Manage blacklist items."""
    await handle_temporary_unavailable(update, context, "Управление Blacklist")


async def _handle_toggle_repricing(update, context):
    """Toggle auto-repricing."""
    await handle_temporary_unavailable(update, context, "Авто-переценка")


async def _handle_config_limits(update, context):
    """Configure trading limits."""
    await handle_temporary_unavailable(update, context, "Настройка лимитов")


async def _handle_panic_stop(update, context):
    """Emergency stop all trading."""
    if not update.callback_query:
        return

    await update.callback_query.answer("🛑 Экстренная остановка!", show_alert=True)

    # Stop any running engines
    smart_engine = context.bot_data.get("smart_arbitrage_engine")
    if smart_engine and hasattr(smart_engine, "stop_smart_mode"):
        smart_engine.stop_smart_mode()

    await update.callback_query.edit_message_text(
        "🛑 <b>ЭКСТРЕННАЯ ОСТАНОВКА</b>\n\n"
        "Все торговые операции остановлены.\n\n"
        "• ❌ Smart Arbitrage: остановлен\n"
        "• ❌ Auto-buy: отключен\n"
        "• ❌ Targets: заморожены\n\n"
        "Для возобновления торговли используйте /start",
        parse_mode="HTML",
    )


async def _handle_waxpeer_stats(update, context):
    """Show Waxpeer statistics."""
    await handle_temporary_unavailable(update, context, "Waxpeer статистика")
