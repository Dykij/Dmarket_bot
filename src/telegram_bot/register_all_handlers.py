"""Модуль для регистрации всех обработчиков Telegram бота.

Этот модуль объединяет регистрацию всех обработчиков команд, callback-запросов,
и других обработчиков для упрощения инициализации бота.

Refactored: Extracted helper functions for each logical group of handlers.
Each helper function is < 50 lines for better readability and mAlgontAlgonability.
"""

import logging
from typing import TYPE_CHECKING

from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters

from src.telegram_bot.commands.backtesting_commands import (
    backtest_command,
    backtest_help,
)
from src.telegram_bot.commands.dAlgoly_report_command import dAlgoly_report_command
from src.telegram_bot.commands.logs_command import logs_command
from src.telegram_bot.commands.start_minimal import start_minimal_command
from src.telegram_bot.commands.test_sentry_command import (
    test_sentry_command,
    test_sentry_info,
)
from src.telegram_bot.handlers.api_check_handler import handle_api_check_callback
from src.telegram_bot.handlers.automatic_arbitrage_handler import (
    handle_mode_selection_callback,
)
from src.telegram_bot.handlers.callback_registry import create_callback_router
from src.telegram_bot.handlers.callback_router import button_callback_handler_v2
from src.telegram_bot.handlers.callbacks import button_callback_handler
from src.telegram_bot.handlers.commands import (
    arbitrage_command,
    dashboard_command,
    dmarket_status_command,
    help_command,
    markets_command,
    start_command,
    webapp_command,
)
from src.telegram_bot.handlers.minimal_menu_router import minimal_menu_router
from src.telegram_bot.handlers.view_items_handler import handle_view_items_callback

if TYPE_CHECKING:
    from telegram.ext import Application


logger = logging.getLogger(__name__)


def _register_basic_commands(application: "Application") -> None:
    """Register basic bot commands: start, help, dashboard, etc.

    Args:
        application: Telegram bot application instance
    """
    application.add_handler(CommandHandler("start_minimal", start_minimal_command))
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("dashboard", dashboard_command))
    application.add_handler(CommandHandler("arbitrage", arbitrage_command))
    application.add_handler(CommandHandler("dmarket", dmarket_status_command))
    application.add_handler(CommandHandler("status", dmarket_status_command))
    application.add_handler(CommandHandler("markets", markets_command))
    application.add_handler(CommandHandler("webapp", webapp_command))
    application.add_handler(CommandHandler("logs", logs_command))
    application.add_handler(CommandHandler("dAlgolyreport", dAlgoly_report_command))

    try:
        from src.telegram_bot.handlers.mAlgon_keyboard import (
            register_mAlgon_keyboard_handlers,
        )

        register_mAlgon_keyboard_handlers(application)
        logger.info("✅ MAlgon Keyboard Handler зарегистрирован")

        from src.telegram_bot.handlers.system_handler import register_system_handlers

        register_system_handlers(application)
        logger.info("✅ System Handler зарегистрирован")
    except ImportError as e:
        logger.warning(
            "Не удалось импортировать mAlgon_keyboard или system_handler: %s", e
        )

    logger.info("Базовые команды зарегистрированы")


def _register_sentry_and_backtest_commands(application: "Application") -> None:
    """Register Sentry testing and backtesting commands.

    Args:
        application: Telegram bot application instance
    """
    application.add_handler(CommandHandler("test_sentry", test_sentry_command))
    application.add_handler(CommandHandler("sentry_info", test_sentry_info))
    application.add_handler(CommandHandler("backtest", backtest_command))
    application.add_handler(CommandHandler("backtest_help", backtest_help))


def _register_auto_buy_commands(application: "Application") -> None:
    """Register auto-buy command handlers.

    Args:
        application: Telegram bot application instance
    """
    try:
        from src.telegram_bot.handlers.auto_buy_handler import autobuy_command

        application.add_handler(CommandHandler("autobuy", autobuy_command))
        logger.info("Auto-buy команда зарегистрирована")
    except ImportError as e:
        logger.warning("Не удалось импортировать auto-buy handler: %s", e)


def _register_smart_and_autopilot_commands(application: "Application") -> None:
    """Register smart arbitrage and autopilot command handlers.

    Args:
        application: Telegram bot application instance
    """
    try:
        from src.telegram_bot.handlers.smart_arbitrage_handler import (
            smart_arbitrage_command,
        )

        application.add_handler(CommandHandler("smart", smart_arbitrage_command))
        logger.info("Smart Arbitrage команда зарегистрирована")
    except ImportError as e:
        logger.warning("Не удалось импортировать smart arbitrage handler: %s", e)

    try:
        from src.telegram_bot.handlers.autopilot_handler import (
            autopilot_command,
            autopilot_stats_command,
            autopilot_status_command,
            autopilot_stop_command,
        )

        application.add_handler(CommandHandler("autopilot", autopilot_command))
        application.add_handler(
            CommandHandler("autopilot_stop", autopilot_stop_command)
        )
        application.add_handler(
            CommandHandler("autopilot_status", autopilot_status_command)
        )
        application.add_handler(
            CommandHandler("autopilot_stats", autopilot_stats_command)
        )
        logger.info("Autopilot команды зарегистрированы")
    except ImportError as e:
        logger.warning("Не удалось импортировать autopilot handler: %s", e)


def _register_panic_and_websocket_commands(application: "Application") -> None:
    """Register panic button and websocket command handlers.

    Args:
        application: Telegram bot application instance
    """
    try:
        from src.telegram_bot.handlers.panic_handler import (
            panic_button_command,
            panic_status_command,
        )

        application.add_handler(CommandHandler("panic", panic_button_command))
        application.add_handler(CommandHandler("panic_status", panic_status_command))
        logger.info("Panic Button команды зарегистрированы")
    except ImportError as e:
        logger.warning("Не удалось импортировать panic handler: %s", e)

    try:
        from src.telegram_bot.handlers.websocket_handler import (
            websocket_restart_command,
            websocket_stats_command,
            websocket_status_command,
        )

        application.add_handler(
            CommandHandler("websocket_status", websocket_status_command)
        )
        application.add_handler(
            CommandHandler("websocket_stats", websocket_stats_command)
        )
        application.add_handler(
            CommandHandler("websocket_restart", websocket_restart_command)
        )
        logger.info("WebSocket команды зарегистрированы")
    except ImportError as e:
        logger.warning("Не удалось импортировать websocket handler: %s", e)


def _register_health_check_commands(application: "Application") -> None:
    """Register health check command handlers.

    Args:
        application: Telegram bot application instance
    """
    try:
        from src.telegram_bot.handlers.health_handler import (
            health_ping_command,
            health_status_command,
            health_summary_command,
        )

        application.add_handler(CommandHandler("health_status", health_status_command))
        application.add_handler(
            CommandHandler("health_summary", health_summary_command)
        )
        application.add_handler(CommandHandler("health_ping", health_ping_command))
        logger.info("Health Check команды зарегистрированы")
    except ImportError as e:
        logger.warning("Не удалось импортировать health handler: %s", e)


def _register_minimal_ui_callbacks(application: "Application") -> None:
    """Register minimal UI callback handlers.

    Args:
        application: Telegram bot application instance
    """
    application.add_handler(
        CallbackQueryHandler(handle_mode_selection_callback, pattern="^mode_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_api_check_callback, pattern="^api_check")
    )
    application.add_handler(
        CallbackQueryHandler(handle_view_items_callback, pattern="^view_items")
    )

    try:
        from src.telegram_bot.handlers.auto_buy_handler import (
            buy_now_callback,
            skip_item_callback,
        )

        application.add_handler(
            CallbackQueryHandler(buy_now_callback, pattern="^buy_now_")
        )
        application.add_handler(
            CallbackQueryHandler(skip_item_callback, pattern="^skip_item$")
        )
        logger.info("Auto-buy callback handlers зарегистрированы")
    except ImportError as e:
        logger.warning("Не удалось импортировать auto-buy callbacks: %s", e)

    try:
        from src.telegram_bot.handlers.autopilot_handler import (
            autopilot_start_confirmed_callback,
        )

        application.add_handler(
            CallbackQueryHandler(
                autopilot_start_confirmed_callback,
                pattern="^autopilot_start_confirmed$",
            )
        )
        logger.info("Autopilot callback handlers зарегистрированы")
    except ImportError as e:
        logger.warning("Не удалось импортировать autopilot callbacks: %s", e)


def _register_enhanced_scanner_handlers(application: "Application") -> None:
    """Register enhanced scanner callback handlers.

    Args:
        application: Telegram bot application instance
    """
    try:
        from src.telegram_bot.handlers.enhanced_scanner_handler import (
            handle_enhanced_scan,
            handle_enhanced_scan_help,
            handle_enhanced_scan_settings,
            show_enhanced_scanner_menu,
        )

        application.add_handler(
            CallbackQueryHandler(
                show_enhanced_scanner_menu, pattern="^enhanced_scanner_menu$"
            )
        )
        application.add_handler(
            CallbackQueryHandler(
                handle_enhanced_scan, pattern="^enhanced_scan_(csgo|dota2|rust|tf2)$"
            )
        )
        application.add_handler(
            CallbackQueryHandler(
                handle_enhanced_scan_settings, pattern="^enhanced_scan_settings$"
            )
        )
        application.add_handler(
            CallbackQueryHandler(
                handle_enhanced_scan_help, pattern="^enhanced_scan_help$"
            )
        )
        logger.info("✅ Enhanced Scanner handlers registered")
    except Exception as e:
        logger.warning("Не удалось зарегистрировать Enhanced Scanner handlers: %s", e)


def _register_callback_router(application: "Application") -> None:
    """Register Phase 2 callback router with fallback to legacy handler.

    Args:
        application: Telegram bot application instance
    """
    logger.info("Initializing Phase 2 callback router...")
    try:
        callback_router = create_callback_router()
        application.bot_data["callback_router"] = callback_router
        logger.info(
            "✅ Callback router initialized with %d handlers",
            len(callback_router._exact_handlers),
        )
        application.add_handler(CallbackQueryHandler(button_callback_handler_v2))
        logger.info("✅ Router-based callback handler registered")
    except Exception as e:
        logger.exception(
            "FAlgoled to initialize callback router, falling back to old handler: %s", e
        )
        application.add_handler(CallbackQueryHandler(button_callback_handler))
        logger.warning("⚠️ Using legacy callback handler (973 lines)")

    logger.info("Callback-обработчики зарегистрированы")


def _register_message_handlers(application: "Application") -> None:
    """Register message handlers for minimal UI.

    Args:
        application: Telegram bot application instance
    """
    application.add_handler(
        MessageHandler(
            filters.Regex(
                "^(🤖 Automatic Arbitrage|📦 View Items|⚙️ DetAlgoled Settings|🔌 API Check)$"
            ),
            minimal_menu_router,
        ),
    )
    logger.info("Minimal UI message router registered")
    logger.info("Обработчики текстовых сообщений зарегистрированы")


def _register_additional_handlers(application: "Application") -> None:
    """Register scanner, alerts, and analysis handlers.

    Args:
        application: Telegram bot application instance
    """
    try:
        from src.telegram_bot.handlers.scanner_handler import register_scanner_handlers

        register_scanner_handlers(application)
        logger.info("Scanner обработчики зарегистрированы")
    except ImportError as e:
        logger.warning("Не удалось импортировать scanner обработчики: %s", e)

    try:
        from src.telegram_bot.handlers.market_alerts_handler import (
            register_alerts_handlers,
        )

        register_alerts_handlers(application)
        logger.info("Market alerts обработчики зарегистрированы")
    except ImportError as e:
        logger.warning("Не удалось импортировать market_alerts обработчики: %s", e)

    try:
        from src.telegram_bot.handlers.market_analysis_handler import (
            register_market_analysis_handlers,
        )

        register_market_analysis_handlers(application)
        logger.info("Market analysis обработчики зарегистрированы")
    except ImportError as e:
        logger.warning("Не удалось импортировать market_analysis обработчики: %s", e)

    try:
        from src.telegram_bot.handlers.intramarket_arbitrage_handler import (
            register_intramarket_handlers,
        )

        register_intramarket_handlers(application)
        logger.info("Intramarket arbitrage обработчики зарегистрированы")
    except ImportError as e:
        logger.warning(
            "Не удалось импортировать intramarket_arbitrage обработчики: %s", e
        )


def _register_target_and_dashboard_handlers(application: "Application") -> None:
    """Register target and dashboard handlers.

    Args:
        application: Telegram bot application instance
    """
    try:
        from src.telegram_bot.handlers.target_handler import register_target_handlers

        register_target_handlers(application)
        logger.info("Target обработчики зарегистрированы")
    except ImportError as e:
        logger.warning("Не удалось импортировать target обработчики: %s", e)

    try:
        from src.telegram_bot.handlers.dashboard_handler import (
            register_dashboard_handlers,
        )

        register_dashboard_handlers(application)
        logger.info("Dashboard обработчики зарегистрированы")
    except ImportError as e:
        logger.warning("Не удалось импортировать dashboard обработчики: %s", e)

    try:
        from src.telegram_bot.handlers.notification_digest_handler import (
            register_notification_digest_handlers,
        )

        register_notification_digest_handlers(application)
        logger.info("Notification digest обработчики зарегистрированы")
    except ImportError as e:
        logger.warning(
            "Не удалось импортировать notification digest обработчики: %s", e
        )


def _register_dmarket_and_steam_handlers(application: "Application") -> None:
    """Register DMarket and Steam arbitrage handlers.

    Args:
        application: Telegram bot application instance
    """
    try:
        dmarket_api = application.bot_data.get("dmarket_api")
        if dmarket_api:
            from src.telegram_bot.handlers.dmarket_handlers import (
                register_dmarket_handlers,
            )

            register_dmarket_handlers(
                application,
                public_key=dmarket_api.public_key,
                secret_key=dmarket_api.secret_key,
                api_url=dmarket_api.api_url,
            )
            logger.info("DMarket обработчики зарегистрированы")
    except (ImportError, AttributeError) as e:
        logger.warning("Не удалось зарегистрировать DMarket обработчики: %s", e)

    try:
        from src.telegram_bot.commands.steam_arbitrage_commands import (
            steam_arbitrage_start,
            steam_arbitrage_status,
            steam_arbitrage_stop,
        )

        application.add_handler(
            CommandHandler("steam_arbitrage_start", steam_arbitrage_start)
        )
        application.add_handler(
            CommandHandler("steam_arbitrage_stop", steam_arbitrage_stop)
        )
        application.add_handler(
            CommandHandler("steam_arbitrage_status", steam_arbitrage_status)
        )
        logger.info("Steam Arbitrage команды зарегистрированы")
    except ImportError as e:
        logger.warning("Не удалось импортировать Steam Arbitrage команды: %s", e)


def _register_extended_feature_handlers(application: "Application") -> None:
    """Register extended stats, sentiment, and hold handlers.

    Args:
        application: Telegram bot application instance
    """
    try:
        from src.telegram_bot.handlers.extended_stats_handler import (
            get_extended_stats_handlers,
        )

        for handler in get_extended_stats_handlers():
            application.add_handler(handler)
        logger.info("Extended Stats команды зарегистрированы (/stats_full, /portfolio)")
    except ImportError as e:
        logger.warning("Не удалось импортировать Extended Stats команды: %s", e)

    try:
        from src.telegram_bot.handlers.market_sentiment_handler import (
            register_market_sentiment_handlers,
        )

        register_market_sentiment_handlers(application)
        logger.info("Market Sentiment команды зарегистрированы (/market, /smart, /x5)")
    except ImportError as e:
        logger.warning("Не удалось импортировать Market Sentiment команды: %s", e)

    try:
        from src.telegram_bot.handlers.intelligent_hold_handler import (
            register_intelligent_hold_handlers,
        )

        register_intelligent_hold_handlers(application)
        logger.info("Intelligent Hold команды зарегистрированы (/hold)")
    except ImportError as e:
        logger.warning("Не удалось импортировать Intelligent Hold команды: %s", e)


def _register_Algo_and_improvements_handlers(application: "Application") -> None:
    """Register Algo and bot improvements handlers.

    Args:
        application: Telegram bot application instance
    """
    try:
        from src.telegram_bot.handlers.Algo_handler import register_Algo_handlers

        register_Algo_handlers(application)
        logger.info(
            "Algo Price Predictor команды зарегистрированы (/Algo_trAlgon, /Algo_status, /Algo_scan)"
        )
    except ImportError as e:
        logger.warning("Не удалось импортировать Algo handler команды: %s", e)

    try:
        from src.telegram_bot.handlers.improvements_handler import (
            register_improvements_handlers,
        )

        register_improvements_handlers(application)
        logger.info(
            "Bot Improvements команды зарегистрированы "
            "(/improvements, /analytics, /portfolio, /alerts, /watchlist, /automation, /reports, /security)"
        )
    except ImportError as e:
        logger.warning("Не удалось импортировать Bot Improvements команды: %s", e)


def _register_knowledge_and_incident_handlers(application: "Application") -> None:
    """Register Knowledge Base and Incident Management handlers.

    Args:
        application: Telegram bot application instance
    """
    # Knowledge Base handlers
    try:
        from src.telegram_bot.handlers.knowledge_handler import (
            register_handlers as register_knowledge_handlers,
        )

        register_knowledge_handlers(application)
        logger.info(
            "Knowledge Base команды зарегистрированы (/knowledge, /knowledge_list, /knowledge_clear)"
        )
    except ImportError as e:
        logger.warning("Не удалось импортировать Knowledge Base команды: %s", e)

    # Initialize Incident Manager with alert channel
    try:
        from src.utils.incident_manager import get_incident_manager

        incident_manager = get_incident_manager()
        application.bot_data["incident_manager"] = incident_manager
        logger.info(
            "Incident Manager инициализирован с %d митигациями",
            len(incident_manager._mitigation_handlers),
        )
    except ImportError as e:
        logger.warning("Не удалось инициализировать Incident Manager: %s", e)


def _register_trading_analysis_handlers(application: "Application") -> None:
    """Register Market Regime, Monitor, and Auth handlers.

    Args:
        application: Telegram bot application instance
    """
    # Market Regime handler
    try:
        from src.telegram_bot.handlers.market_regime_handler import MarketRegimeHandler

        regime_handler = MarketRegimeHandler()
        for handler in regime_handler.get_handlers():
            application.add_handler(handler)
        logger.info("Market Regime команды зарегистрированы (/regime)")
    except ImportError as e:
        logger.warning("Не удалось импортировать Market Regime команды: %s", e)

    # Telethon Monitor handler
    try:
        from src.telegram_bot.handlers.monitor_handler import MonitorHandler

        monitor_handler = MonitorHandler()
        for handler in monitor_handler.get_handlers():
            application.add_handler(handler)
        logger.info("Monitor команды зарегистрированы (/monitor)")
    except ImportError as e:
        logger.warning("Не удалось импортировать Monitor команды: %s", e)

    # Auth handler
    try:
        from src.telegram_bot.handlers.auth_handler import AuthHandler

        auth_handler = AuthHandler()
        for handler in auth_handler.get_handlers():
            application.add_handler(handler)
        logger.info("Auth команды зарегистрированы (/auth, /2fa, /security)")
    except ImportError as e:
        logger.warning("Не удалось импортировать Auth команды: %s", e)

    # Algo Unified Arbitrage handler
    try:
        from src.telegram_bot.handlers.Algo_arbitrage_handler import AlgoArbitrageHandler

        Algo_arb_handler = AlgoArbitrageHandler()
        for handler in Algo_arb_handler.get_handlers():
            application.add_handler(handler)
        logger.info("Algo Arbitrage команды зарегистрированы (/Algo_arb)")
    except ImportError as e:
        logger.warning("Не удалось импортировать Algo Arbitrage команды: %s", e)


def register_all_handlers(application: "Application") -> None:
    """Register all command and callback handlers for the bot.

    This is the mAlgon entry point that orchestrates registration of all handlers
    by delegating to specialized helper functions for each handler group.

    Args:
        application: Telegram bot application instance
    """
    logger.info("Начало регистрации обработчиков бота...")

    # Register handler groups in order of priority
    _register_basic_commands(application)
    _register_sentry_and_backtest_commands(application)
    _register_auto_buy_commands(application)
    _register_smart_and_autopilot_commands(application)
    _register_panic_and_websocket_commands(application)
    _register_health_check_commands(application)

    # Callback handlers (registered before general callback handler)
    _register_minimal_ui_callbacks(application)
    _register_enhanced_scanner_handlers(application)
    _register_callback_router(application)

    # Message handlers
    _register_message_handlers(application)

    # Additional feature handlers
    _register_additional_handlers(application)
    _register_target_and_dashboard_handlers(application)
    _register_dmarket_and_steam_handlers(application)
    _register_extended_feature_handlers(application)
    _register_Algo_and_improvements_handlers(application)

    # Knowledge Base and Incident Management (Phase 1-2 improvements)
    _register_knowledge_and_incident_handlers(application)

    # Trading Analysis: Market Regime, Monitor, Auth (Phase 3 improvements)
    _register_trading_analysis_handlers(application)

    logger.info("Все обработчики успешно зарегистрированы")


__all__ = ["register_all_handlers"]
