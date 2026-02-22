"""Unified Strategy Handler - обработчик для унифицированной системы стратегий.

Предоставляет Telegram интерфейс для работы со всеми стратегиями:
- Выбор и настSwarmка стратегий
- Сканирование по одной или нескольким стратегиям
- Комбинированный поиск лучших возможностей
- Пресеты конфигураций (boost, standard, medium, advanced, pro)

Commands:
- /strategies - Меню выбора стратегии
- /scan_all - Сканировать всеми стратегиями
- /best_deals - Найти лучшие возможности

Author: DMarket Telegram Bot
Created: January 2026
"""

import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

from src.dmarket.unified_strategy_system import (
    ActionType,
    RiskLevel,
    StrategyConfig,
    StrategyType,
    UnifiedOpportunity,
    UnifiedStrategyManager,
    create_strategy_manager,
    get_strategy_config_preset,
)

logger = logging.getLogger(__name__)

# Conversation states
SELECTING_STRATEGY = 0
SELECTING_PRESET = 1
SCANNING = 2

# Callback data prefixes
CB_STRATEGY = "strategy_"
CB_PRESET = "preset_"
CB_SCAN = "scan_"
CB_BACK = "back_to_strategies"


class UnifiedStrategyHandler:
    """Обработчик для унифицированной системы стратегий."""

    def __init__(self, strategy_manager: UnifiedStrategyManager | None = None) -> None:
        """Инициализация обработчика.

        Args:
            strategy_manager: Менеджер стратегий (если None - создается при первом использовании)
        """
        self._manager = strategy_manager
        self._user_configs: dict[int, StrategyConfig] = {}
        self._user_strategy: dict[int, StrategyType] = {}

    def _get_manager(
        self, context: ContextTypes.DEFAULT_TYPE
    ) -> UnifiedStrategyManager:
        """Получить или создать менеджер стратегий."""
        if self._manager:
            return self._manager

        # Пытаемся получить API клиенты из контекста
        dmarket_api = context.bot_data.get("dmarket_api")
        waxpeer_api = context.bot_data.get("waxpeer_api")

        if dmarket_api:
            self._manager = create_strategy_manager(
                dmarket_api=dmarket_api,
                waxpeer_api=waxpeer_api,
            )
            return self._manager

        # Fallback - создаем с дефолтным API
        from src.dmarket.dmarket_api import DMarketAPI

        self._manager = create_strategy_manager(
            dmarket_api=DMarketAPI(),
            waxpeer_api=None,
        )
        return self._manager

    # ========================================================================
    # Keyboards
    # ========================================================================

    def _get_strategies_keyboard(self) -> InlineKeyboardMarkup:
        """Создать клавиатуру выбора стратегии."""
        buttons = [
            [
                InlineKeyboardButton(
                    "🔄 Cross-Platform",
                    callback_data=f"{CB_STRATEGY}{StrategyType.CROSS_PLATFORM_ARBITRAGE.value}",
                ),
                InlineKeyboardButton(
                    "📊 Intramarket",
                    callback_data=f"{CB_STRATEGY}{StrategyType.INTRAMARKET_ARBITRAGE.value}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🎯 Float Value",
                    callback_data=f"{CB_STRATEGY}{StrategyType.FLOAT_VALUE_ARBITRAGE.value}",
                ),
                InlineKeyboardButton(
                    "🧠 Smart Finder",
                    callback_data=f"{CB_STRATEGY}{StrategyType.SMART_MARKET_FINDER.value}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⚡ Scan ALL Strategies",
                    callback_data="scan_all_strategies",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🏆 Best Deals Combined",
                    callback_data="best_deals_combined",
                ),
            ],
            [
                InlineKeyboardButton("❌ Close", callback_data="close_strategies"),
            ],
        ]
        return InlineKeyboardMarkup(buttons)

    def _get_presets_keyboard(
        self, strategy_type: StrategyType
    ) -> InlineKeyboardMarkup:
        """Создать клавиатуру выбора пресета."""
        buttons = [
            [
                InlineKeyboardButton(
                    "🚀 Boost ($0.5-$3)",
                    callback_data=f"{CB_PRESET}boost",
                ),
                InlineKeyboardButton(
                    "📈 Standard ($3-$15)",
                    callback_data=f"{CB_PRESET}standard",
                ),
            ],
            [
                InlineKeyboardButton(
                    "💰 Medium ($15-$50)",
                    callback_data=f"{CB_PRESET}medium",
                ),
                InlineKeyboardButton(
                    "💎 Advanced ($50-$200)",
                    callback_data=f"{CB_PRESET}advanced",
                ),
            ],
            [
                InlineKeyboardButton(
                    "👑 Pro ($200+)",
                    callback_data=f"{CB_PRESET}pro",
                ),
            ],
        ]

        # Добавляем специфичные пресеты для стратегии
        if strategy_type == StrategyType.FLOAT_VALUE_ARBITRAGE:
            buttons.append(
                [
                    InlineKeyboardButton(
                        "🎯 Float Premium",
                        callback_data=f"{CB_PRESET}float_premium",
                    ),
                ]
            )
        elif strategy_type == StrategyType.CROSS_PLATFORM_ARBITRAGE:
            buttons.append(
                [
                    InlineKeyboardButton(
                        "⚡ Instant Arb (no lock)",
                        callback_data=f"{CB_PRESET}instant_arb",
                    ),
                    InlineKeyboardButton(
                        "📊 Investment",
                        callback_data=f"{CB_PRESET}investment",
                    ),
                ]
            )

        buttons.append(
            [
                InlineKeyboardButton("◀️ Back", callback_data=CB_BACK),
            ]
        )

        return InlineKeyboardMarkup(buttons)

    def _get_results_keyboard(self, has_more: bool = False) -> InlineKeyboardMarkup:
        """Создать клавиатуру для результатов."""
        buttons = [
            [
                InlineKeyboardButton("🔄 Scan AgAlgon", callback_data="scan_agAlgon"),
                InlineKeyboardButton("⚙️ Change Preset", callback_data=CB_BACK),
            ],
        ]
        if has_more:
            buttons.insert(
                0,
                [
                    InlineKeyboardButton(
                        "📄 Show More", callback_data="show_more_results"
                    ),
                ],
            )
        buttons.append(
            [
                InlineKeyboardButton("❌ Close", callback_data="close_strategies"),
            ]
        )
        return InlineKeyboardMarkup(buttons)

    # ========================================================================
    # Formatters
    # ========================================================================

    def _format_opportunity(self, opp: UnifiedOpportunity, index: int = 1) -> str:
        """Форматировать возможность для отображения."""
        # Эмодзи для типа действия
        action_emoji = {
            ActionType.BUY_NOW: "🟢",
            ActionType.CREATE_TARGET: "🎯",
            ActionType.WATCH: "👀",
            ActionType.CREATE_ADVANCED_ORDER: "📝",
            ActionType.SKIP: "⏭️",
        }

        # Эмодзи для уровня риска
        risk_emoji = {
            RiskLevel.VERY_LOW: "🟢",
            RiskLevel.LOW: "🟡",
            RiskLevel.MEDIUM: "🟠",
            RiskLevel.HIGH: "🔴",
            RiskLevel.VERY_HIGH: "⚫",
        }

        emoji = action_emoji.get(opp.action_type, "•")
        risk = risk_emoji.get(opp.risk_level, "•")

        lines = [
            f"{index}. {emoji} **{opp.title}**",
            f"   💵 Buy: ${float(opp.buy_price):.2f} → Sell: ${float(opp.sell_price):.2f}",
            f"   📈 Profit: ${float(opp.profit_usd):.2f} ({float(opp.profit_percent):.1f}%)",
            f"   🎯 Score: {opp.score.total_score:.1f}/100 {risk} Risk: {opp.risk_level.value}",
        ]

        # Добавляем специфичную информацию
        if opp.float_value is not None:
            lines.append(f"   🎲 Float: {opp.float_value:.6f}")
        if opp.trade_lock_days > 0:
            lines.append(f"   🔒 Lock: {opp.trade_lock_days} days")
        if opp.target_platform:
            lines.append(f"   🔄 {opp.source_platform} → {opp.target_platform}")

        # Заметки
        if opp.notes:
            lines.append(f"   📝 {'; '.join(opp.notes[:2])}")

        return "\n".join(lines)

    def _format_results(
        self,
        opportunities: list[UnifiedOpportunity],
        strategy_name: str = "Combined",
        max_show: int = 10,
    ) -> str:
        """Форматировать результаты сканирования."""
        if not opportunities:
            return f"❌ **{strategy_name}**: No opportunities found\n\nTry different preset or strategy."

        header = (
            f"🔍 **{strategy_name}** - Found {len(opportunities)} opportunities\n\n"
        )

        items = []
        for i, opp in enumerate(opportunities[:max_show], 1):
            items.append(self._format_opportunity(opp, i))

        footer = ""
        if len(opportunities) > max_show:
            footer = f"\n\n... and {len(opportunities) - max_show} more"

        return header + "\n\n".join(items) + footer

    def _get_strategy_description(self, strategy_type: StrategyType) -> str:
        """Получить описание стратегии."""
        descriptions = {
            StrategyType.CROSS_PLATFORM_ARBITRAGE: (
                "🔄 **Cross-Platform Arbitrage**\n"
                "Buy on DMarket, sell on Waxpeer.\n"
                "• Instant arbitrage (no lock)\n"
                "• Trade lock investments\n"
                "• 6% Waxpeer commission"
            ),
            StrategyType.INTRAMARKET_ARBITRAGE: (
                "📊 **Intramarket Arbitrage**\n"
                "Find mispriced items within DMarket.\n"
                "• Price anomaly detection\n"
                "• Trending items\n"
                "• 7% DMarket commission"
            ),
            StrategyType.FLOAT_VALUE_ARBITRAGE: (
                "🎯 **Float Value Arbitrage**\n"
                "Find premium float items for collectors.\n"
                "• Low float (0.00-0.07) premiums\n"
                "• High float (0.90+) collectibles\n"
                "• 50-200% potential profit"
            ),
            StrategyType.SMART_MARKET_FINDER: (
                "🧠 **Smart Market Finder**\n"
                "Algo-powered opportunity discovery.\n"
                "• Multi-factor analysis\n"
                "• Liquidity scoring\n"
                "• Risk assessment"
            ),
        }
        return descriptions.get(strategy_type, "Strategy description not avAlgolable")

    # ========================================================================
    # Command Handlers
    # ========================================================================

    async def strategies_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Обработчик команды /strategies."""
        if not update.message:
            return ConversationHandler.END

        text = (
            "🎯 **Unified Strategy System**\n\n"
            "Select a strategy to find arbitrage opportunities:\n\n"
            "• **Cross-Platform** - DMarket → Waxpeer\n"
            "• **Intramarket** - Price anomalies on DMarket\n"
            "• **Float Value** - Premium float items\n"
            "• **Smart Finder** - Algo-powered search\n\n"
            "Or scan with ALL strategies at once!"
        )

        await update.message.reply_text(
            text,
            reply_markup=self._get_strategies_keyboard(),
            parse_mode="Markdown",
        )
        return SELECTING_STRATEGY

    async def scan_all_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Обработчик команды /scan_all."""
        if not update.message:
            return

        await update.message.reply_text("🔄 Scanning with all strategies...")

        manager = self._get_manager(context)
        config = get_strategy_config_preset("standard")

        all_results = await manager.scan_all_strategies(config)

        text_parts = []
        for strategy_type, opportunities in all_results.items():
            strategy = manager.get_strategy(strategy_type)
            name = strategy.name if strategy else strategy_type.value
            text_parts.append(self._format_results(opportunities, name, max_show=5))

        await update.message.reply_text(
            "\n\n---\n\n".join(text_parts) if text_parts else "No results found",
            parse_mode="Markdown",
        )

    async def best_deals_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Обработчик команды /best_deals."""
        if not update.message:
            return

        await update.message.reply_text(
            "🏆 Finding best deals across all strategies..."
        )

        manager = self._get_manager(context)
        config = get_strategy_config_preset("standard")

        opportunities = await manager.find_best_opportunities_combined(config, top_n=15)

        text = self._format_results(
            opportunities, "🏆 Best Deals Combined", max_show=15
        )

        await update.message.reply_text(
            text,
            reply_markup=self._get_results_keyboard(has_more=len(opportunities) > 15),
            parse_mode="Markdown",
        )

    # ========================================================================
    # Callback Handlers
    # ========================================================================

    async def strategy_selected(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Обработка выбора стратегии."""
        query = update.callback_query
        if not query:
            return ConversationHandler.END

        await query.answer()

        user_id = query.from_user.id if query.from_user else 0
        data = query.data or ""

        # Обработка специальных действий
        if data == "scan_all_strategies":
            await query.edit_message_text("🔄 Scanning with all strategies...")
            manager = self._get_manager(context)
            config = get_strategy_config_preset("standard")
            best = await manager.find_best_opportunities_combined(config, top_n=10)
            text = self._format_results(best, "All Strategies Combined", max_show=10)
            await query.edit_message_text(
                text,
                reply_markup=self._get_results_keyboard(),
                parse_mode="Markdown",
            )
            return ConversationHandler.END

        if data == "best_deals_combined":
            await query.edit_message_text("🏆 Finding best deals...")
            manager = self._get_manager(context)
            config = get_strategy_config_preset("standard")
            best = await manager.find_best_opportunities_combined(config, top_n=15)
            text = self._format_results(best, "🏆 Best Deals", max_show=15)
            await query.edit_message_text(
                text,
                reply_markup=self._get_results_keyboard(),
                parse_mode="Markdown",
            )
            return ConversationHandler.END

        if data == "close_strategies":
            await query.edit_message_text("Strategy menu closed.")
            return ConversationHandler.END

        # Выбор стратегии
        if data.startswith(CB_STRATEGY):
            strategy_value = data[len(CB_STRATEGY) :]
            try:
                strategy_type = StrategyType(strategy_value)
                self._user_strategy[user_id] = strategy_type

                text = self._get_strategy_description(strategy_type)
                text += "\n\n**Select price preset:**"

                await query.edit_message_text(
                    text,
                    reply_markup=self._get_presets_keyboard(strategy_type),
                    parse_mode="Markdown",
                )
                return SELECTING_PRESET

            except ValueError:
                await query.edit_message_text("Invalid strategy selected.")
                return ConversationHandler.END

        return SELECTING_STRATEGY

    async def preset_selected(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Обработка выбора пресета."""
        query = update.callback_query
        if not query:
            return ConversationHandler.END

        await query.answer()

        user_id = query.from_user.id if query.from_user else 0
        data = query.data or ""

        if data == CB_BACK:
            await query.edit_message_text(
                "🎯 **Unified Strategy System**\n\nSelect a strategy:",
                reply_markup=self._get_strategies_keyboard(),
                parse_mode="Markdown",
            )
            return SELECTING_STRATEGY

        if data.startswith(CB_PRESET):
            preset_name = data[len(CB_PRESET) :]
            config = get_strategy_config_preset(preset_name)
            self._user_configs[user_id] = config

            strategy_type = self._user_strategy.get(user_id)
            if not strategy_type:
                await query.edit_message_text("Error: No strategy selected.")
                return ConversationHandler.END

            await query.edit_message_text(
                f"🔄 Scanning with **{strategy_type.value}** ({preset_name} preset)...",
                parse_mode="Markdown",
            )

            # Выполняем сканирование
            manager = self._get_manager(context)
            opportunities = await manager.scan_with_strategy(strategy_type, config)

            strategy = manager.get_strategy(strategy_type)
            name = strategy.name if strategy else strategy_type.value
            text = self._format_results(opportunities, name, max_show=10)

            await query.edit_message_text(
                text,
                reply_markup=self._get_results_keyboard(
                    has_more=len(opportunities) > 10
                ),
                parse_mode="Markdown",
            )
            return ConversationHandler.END

        return SELECTING_PRESET

    async def handle_scan_agAlgon(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Обработка повторного сканирования."""
        query = update.callback_query
        if not query:
            return ConversationHandler.END

        await query.answer()

        user_id = query.from_user.id if query.from_user else 0
        strategy_type = self._user_strategy.get(user_id)
        config = self._user_configs.get(user_id)

        if not strategy_type or not config:
            await query.edit_message_text(
                "🎯 **Unified Strategy System**\n\nSelect a strategy:",
                reply_markup=self._get_strategies_keyboard(),
                parse_mode="Markdown",
            )
            return SELECTING_STRATEGY

        await query.edit_message_text("🔄 Rescanning...")

        manager = self._get_manager(context)
        opportunities = await manager.scan_with_strategy(strategy_type, config)

        strategy = manager.get_strategy(strategy_type)
        name = strategy.name if strategy else strategy_type.value
        text = self._format_results(opportunities, name, max_show=10)

        await query.edit_message_text(
            text,
            reply_markup=self._get_results_keyboard(has_more=len(opportunities) > 10),
            parse_mode="Markdown",
        )
        return ConversationHandler.END


def register_unified_strategy_handlers(application: Any) -> None:
    """Зарегистрировать обработчики унифицированной системы стратегий.

    Args:
        application: Telegram Application instance
    """
    handler_instance = UnifiedStrategyHandler()

    # Conversation handler для /strategies
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("strategies", handler_instance.strategies_command),
        ],
        states={
            SELECTING_STRATEGY: [
                CallbackQueryHandler(
                    handler_instance.strategy_selected,
                    pattern="^(strategy_|scan_all_|best_deals_|close_)",
                ),
            ],
            SELECTING_PRESET: [
                CallbackQueryHandler(
                    handler_instance.preset_selected,
                    pattern="^(preset_|back_to_)",
                ),
            ],
        },
        fallbacks=[
            CommandHandler("strategies", handler_instance.strategies_command),
        ],
    )
    application.add_handler(conv_handler)

    # Standalone commands
    application.add_handler(
        CommandHandler("scan_all", handler_instance.scan_all_command)
    )
    application.add_handler(
        CommandHandler("best_deals", handler_instance.best_deals_command)
    )

    # Callback handlers for results
    application.add_handler(
        CallbackQueryHandler(
            handler_instance.handle_scan_agAlgon,
            pattern="^scan_agAlgon$",
        )
    )

    logger.info("Unified strategy handlers registered")


__all__ = [
    "UnifiedStrategyHandler",
    "register_unified_strategy_handlers",
]
