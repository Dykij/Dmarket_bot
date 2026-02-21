"""Telegram handler for Market Regime Detection.

Provides commands for analyzing market trends:
- /regime [game] - Analyze current market regime
- Callback handlers for regime analysis

Usage:
    handler = MarketRegimeHandler()
    app.add_handler(CommandHandler("regime", handler.handle_regime_command))
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from src.trading.regime_detector import (
    REGIME_STRATEGIES,
    AdaptiveTrader,
    MarketRegime,
    RegimeAnalysis,
    RegimeDetector,
)

if TYPE_CHECKING:
    from src.interfaces import IDMarketAPI


logger = logging.getLogger(__name__)


# Emoji mapping for regimes
REGIME_EMOJI: dict[MarketRegime, str] = {
    MarketRegime.TRENDING_UP: "📈",
    MarketRegime.TRENDING_DOWN: "📉",
    MarketRegime.RANGING: "📊",
    MarketRegime.VOLATILE: "⚡",
    MarketRegime.UNKNOWN: "❓",
}

# Russian names for regimes
REGIME_NAMES_RU: dict[MarketRegime, str] = {
    MarketRegime.TRENDING_UP: "Восходящий тренд",
    MarketRegime.TRENDING_DOWN: "Нисходящий тренд",
    MarketRegime.RANGING: "Боковой рынок",
    MarketRegime.VOLATILE: "Высокая волатильность",
    MarketRegime.UNKNOWN: "Неопределённо",
}

# Strategy descriptions in Russian
STRATEGY_DESCRIPTIONS_RU: dict[str, str] = {
    "momentum_long": "Покупай на росте, держи победителей",
    "defensive": "Защитная позиция, сократи объёмы",
    "mean_reversion": "Покупай на поддержке, продавай на сопротивлении",
    "volatility_play": "Малые позиции, широкие стопы",
    "cautious": "Ожидай ясности, наблюдай",
}


class MarketRegimeHandler:
    """Handler for market regime analysis commands.

    Analyzes price data to detect current market regime
    and provides trading recommendations.
    """

    def __init__(
        self,
        api: IDMarketAPI | None = None,
        detector: RegimeDetector | None = None,
    ) -> None:
        """Initialize handler.

        Args:
            api: DMarket API client
            detector: Regime detector instance
        """
        self._api = api
        self._detector = detector or RegimeDetector(window=20)
        self._adaptive_trader = AdaptiveTrader(detector=self._detector)

        # Cache for recent analyses
        self._cache: dict[str, tuple[RegimeAnalysis, float]] = {}
        self._cache_ttl = 300  # 5 minutes

    def set_api(self, api: IDMarketAPI) -> None:
        """Set the API client."""
        self._api = api

    async def handle_regime_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /regime command.

        Usage: /regime [game]
        Example: /regime csgo
        """
        if not update.message:
            return

        # Parse game argument
        args = context.args or []
        game = args[0].lower() if args else "csgo"

        if game not in ("csgo", "dota2", "tf2", "rust"):
            game = "csgo"

        keyboard = self._create_regime_keyboard(game)

        await update.message.reply_text(
            f"📊 *Анализ рыночного режима*\n\n"
            f"Выберите тип анализа для *{game.upper()}*:\n\n"
            f"• *Текущий режим* — определение текущего состояния рынка\n"
            f"• *Multi-TF анализ* — анализ на нескольких временных периодах\n"
            f"• *Торговые параметры* — рекомендуемые настройки для текущего режима",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def handle_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle regime callback queries."""
        query = update.callback_query
        if not query or not query.data:
            return

        await query.answer()

        data = query.data
        parts = data.split(":")

        if len(parts) < 3:
            return

        action = parts[1]
        game = parts[2]

        if action == "current":
            await self._show_current_regime(query, game)
        elif action == "multi_tf":
            await self._show_multi_timeframe(query, game)
        elif action == "params":
            await self._show_trading_params(query, game)
        elif action == "back":
            keyboard = self._create_regime_keyboard(game)
            await query.edit_message_text(
                f"📊 *Анализ рыночного режима*\n\nВыберите тип анализа для *{game.upper()}*:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

    async def _get_price_data(self, game: str, item_name: str = "") -> list[float]:
        """Get price data for analysis.

        In production, this would fetch from API.
        For now, returns sample data for demonstration.
        """
        # TODO: Integrate with actual API
        # if self._api:
        #     prices = await self._api.get_price_history(game, item_name)
        #     return [p.price for p in prices]

        # Sample data for demonstration
        import random

        base = 100.0
        prices = []
        for _ in range(50):
            base += random.uniform(-2, 2.5)  # noqa: S311
            prices.append(max(10, base))
        return prices

    async def _show_current_regime(self, query: Any, game: str) -> None:
        """Show current market regime analysis."""
        await query.edit_message_text("⏳ Анализирую рыночный режим...")

        try:
            # Get price data
            prices = await self._get_price_data(game)

            # Detect regime
            analysis = self._detector.detect_regime(prices)

            # Format response
            emoji = REGIME_EMOJI.get(analysis.regime, "📊")
            regime_name = REGIME_NAMES_RU.get(analysis.regime, str(analysis.regime))
            strategy_info = REGIME_STRATEGIES.get(analysis.regime, {})
            strategy_desc = STRATEGY_DESCRIPTIONS_RU.get(
                analysis.suggested_strategy, strategy_info.get("description", "")
            )

            # Confidence bar
            conf_bars = int(analysis.confidence * 10)
            confidence_visual = "🟢" * conf_bars + "⚫" * (10 - conf_bars)

            text = (
                f"{emoji} *Текущий режим: {regime_name}*\n\n"
                f"*Уверенность:* {analysis.confidence:.0%}\n"
                f"{confidence_visual}\n\n"
                f"*Метрики:*\n"
                f"├ Сила тренда: `{analysis.trend_strength:.3f}`\n"
                f"├ Волатильность: `{analysis.volatility:.2%}`\n"
                f"├ Моментум: `{analysis.momentum:+.2%}`\n"
                f"└ Изменение цены: `{analysis.price_change_pct:+.1f}%`\n\n"
                f"*Рекомендуемая стратегия:*\n"
                f"🎯 _{strategy_desc}_\n\n"
                f"*Действия:*\n"
            )

            actions = strategy_info.get("actions", [])
            for action in actions[:3]:
                action_ru = self._translate_action(action)
                text += f"• {action_ru}\n"

            text += f"\n*Уровень риска:* {strategy_info.get('risk_level', 'medium')}"

            keyboard = [
                [
                    InlineKeyboardButton(
                        "📊 Multi-TF анализ",
                        callback_data=f"regime:multi_tf:{game}",
                    ),
                    InlineKeyboardButton(
                        "⚙️ Параметры",
                        callback_data=f"regime:params:{game}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔄 Обновить",
                        callback_data=f"regime:current:{game}",
                    ),
                    InlineKeyboardButton(
                        "◀️ Назад",
                        callback_data=f"regime:back:{game}",
                    ),
                ],
            ]

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

        except Exception as e:
            logger.exception(f"Regime analysis error: {e}")
            await query.edit_message_text(
                f"❌ Ошибка анализа: {e}",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "◀️ Назад", callback_data=f"regime:back:{game}"
                            )
                        ]
                    ]
                ),
            )

    async def _show_multi_timeframe(self, query: Any, game: str) -> None:
        """Show multi-timeframe regime analysis."""
        await query.edit_message_text("⏳ Анализирую несколько временных периодов...")

        try:
            prices = await self._get_price_data(game)

            # Analyze multiple timeframes
            multi_analysis = self._detector.analyze_multi_timeframe(
                prices,
                windows=[5, 10, 20, 50],
            )

            # Get summary
            summary = self._detector.get_regime_summary(multi_analysis)

            dominant = summary["dominant_regime"]
            emoji = REGIME_EMOJI.get(dominant, "📊")
            regime_name = REGIME_NAMES_RU.get(dominant, str(dominant))

            text = (
                f"📊 *Multi-Timeframe Анализ*\n\n"
                f"*Доминирующий режим:* {emoji} {regime_name}\n"
                f"*Согласованность:* {summary['agreement']:.0%}\n\n"
                f"*По периодам:*\n"
            )

            for window_key, analysis in multi_analysis.items():
                window = window_key.replace("window_", "")
                emoji_tf = REGIME_EMOJI.get(analysis.regime, "📊")
                name_tf = REGIME_NAMES_RU.get(analysis.regime, "?")
                text += (
                    f"├ {window}p: {emoji_tf} {name_tf} ({analysis.confidence:.0%})\n"
                )

            text += (
                f"\n*Рекомендация:* `{summary['recommendation']}`\n"
                f"*Уровень риска:* `{summary['risk_level']}`"
            )

            keyboard = [
                [
                    InlineKeyboardButton(
                        "📈 Текущий режим",
                        callback_data=f"regime:current:{game}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔄 Обновить",
                        callback_data=f"regime:multi_tf:{game}",
                    ),
                    InlineKeyboardButton(
                        "◀️ Назад",
                        callback_data=f"regime:back:{game}",
                    ),
                ],
            ]

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

        except Exception as e:
            logger.exception(f"Multi-TF analysis error: {e}")
            await query.edit_message_text(f"❌ Ошибка: {e}")

    async def _show_trading_params(self, query: Any, game: str) -> None:
        """Show adapted trading parameters."""
        try:
            prices = await self._get_price_data(game)

            # Get adapted parameters
            params = self._adaptive_trader.get_adapted_params(prices, balance=100.0)

            regime = params["regime"]
            emoji = REGIME_EMOJI.get(MarketRegime(regime), "📊")

            text = (
                f"⚙️ *Адаптивные торговые параметры*\n\n"
                f"*Текущий режим:* {emoji} {regime}\n"
                f"*Уверенность:* {params['confidence']:.0%}\n\n"
                f"*Рекомендуемые параметры:*\n"
                f"├ 💰 Размер позиции: `${params['position_size']:.2f}`\n"
                f"├ 🛑 Stop-Loss: `{params['stop_loss_pct']:.1f}%`\n"
                f"├ 🎯 Take-Profit: `{params['take_profit_pct']:.1f}%`\n"
                f"├ ⏱️ Удержание: `{params['hold_duration']}`\n"
                f"└ ⚠️ Риск: `{params['risk_level']}`\n\n"
                f"*Стратегия:* `{params['strategy']}`\n\n"
                f"*Рекомендуемые действия:*\n"
            )

            for action in params.get("actions", [])[:3]:
                action_ru = self._translate_action(action)
                text += f"• {action_ru}\n"

            # Check if should trade
            should_trade, reason = self._adaptive_trader.should_trade(prices)
            trade_emoji = "✅" if should_trade else "⚠️"
            text += f"\n{trade_emoji} *Торговать сейчас:* {reason}"

            keyboard = [
                [
                    InlineKeyboardButton(
                        "🔄 Обновить",
                        callback_data=f"regime:params:{game}",
                    ),
                    InlineKeyboardButton(
                        "◀️ Назад",
                        callback_data=f"regime:back:{game}",
                    ),
                ],
            ]

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

        except Exception as e:
            logger.exception(f"Trading params error: {e}")
            await query.edit_message_text(f"❌ Ошибка: {e}")

    def _create_regime_keyboard(self, game: str) -> list[list[InlineKeyboardButton]]:
        """Create regime analysis keyboard."""
        return [
            [
                InlineKeyboardButton(
                    "📈 Текущий режим",
                    callback_data=f"regime:current:{game}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📊 Multi-TF анализ",
                    callback_data=f"regime:multi_tf:{game}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⚙️ Торговые параметры",
                    callback_data=f"regime:params:{game}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "◀️ Главное меню",
                    callback_data="main_menu",
                ),
            ],
        ]

    def _translate_action(self, action: str) -> str:
        """Translate action to Russian."""
        translations = {
            "buy_breakouts": "Покупай на пробоях",
            "trail_stops": "Используй трейлинг-стопы",
            "scale_in": "Постепенно наращивай позицию",
            "reduce_positions": "Сокращай позиции",
            "tight_stops": "Жёсткие стоп-лоссы",
            "wait_reversal": "Жди разворота",
            "buy_support": "Покупай на поддержке",
            "sell_resistance": "Продавай на сопротивлении",
            "quick_profits": "Фиксируй прибыль быстро",
            "reduce_size": "Уменьши размер позиций",
            "wide_stops": "Широкие стопы",
            "scalp_moves": "Скальпинг на движениях",
            "observe": "Наблюдай",
            "paper_trade": "Торгуй на бумаге",
            "small_test": "Малые тестовые позиции",
        }
        return translations.get(action, action)

    def get_handlers(self) -> list:
        """Get list of handlers for registration."""
        return [
            CommandHandler("regime", self.handle_regime_command),
            CallbackQueryHandler(
                self.handle_callback,
                pattern=r"^regime:",
            ),
        ]


__all__ = ["MarketRegimeHandler"]
