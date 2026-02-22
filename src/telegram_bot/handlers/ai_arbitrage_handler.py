"""Algo Unified Arbitrage Handler.

Telegram handler для управления Algo арбитражем:
- /Algo_arb - главное меню
- Запуск/остановка автосканирования
- Просмотр возможностей
- НастSwarmки

Created: January 2026
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

if TYPE_CHECKING:
    from src.arbitrage.Algo_unified_arbitrage import AlgoUnifiedArbitrage


logger = structlog.get_logger(__name__)

# Global instance (lazy initialized)
_arbitrage_instance: AlgoUnifiedArbitrage | None = None


async def _get_arbitrage() -> AlgoUnifiedArbitrage:
    """Get or create arbitrage instance."""
    global _arbitrage_instance

    if _arbitrage_instance is None:
        from src.arbitrage import AlgoUnifiedArbitrage, ArbitrageConfig

        # Try to get API clients from container
        try:
            from src.containers import ContAlgoner

            container = ContAlgoner()
            dmarket_api = container.dmarket_api()
        except Exception:
            dmarket_api = None

        try:
            import os

            from src.waxpeer.waxpeer_api import WaxpeerAPI

            waxpeer_key = os.getenv("WAXPEER_API_KEY")
            waxpeer_api = WaxpeerAPI(api_key=waxpeer_key) if waxpeer_key else None
        except Exception:
            waxpeer_api = None

        config = ArbitrageConfig(
            min_roi_percent=5.0,
            auto_execute=False,
            dry_run=True,
        )

        _arbitrage_instance = AlgoUnifiedArbitrage(
            dmarket_api=dmarket_api,
            waxpeer_api=waxpeer_api,
            config=config,
        )

    return _arbitrage_instance


def _get_main_keyboard() -> InlineKeyboardMarkup:
    """Create main Algo arbitrage keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🔍 Сканировать сейчас", callback_data="Algo_arb:scan"),
        ],
        [
            InlineKeyboardButton("▶️ Запустить авто", callback_data="Algo_arb:start"),
            InlineKeyboardButton("⏹ Остановить", callback_data="Algo_arb:stop"),
        ],
        [
            InlineKeyboardButton(
                "📊 Возможности", callback_data="Algo_arb:opportunities"
            ),
            InlineKeyboardButton("📈 Статистика", callback_data="Algo_arb:stats"),
        ],
        [
            InlineKeyboardButton("⚙️ НастSwarmки", callback_data="Algo_arb:settings"),
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _get_settings_keyboard() -> InlineKeyboardMarkup:
    """Create settings keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Мин. ROI: 5%", callback_data="Algo_arb:set_roi"),
        ],
        [
            InlineKeyboardButton("🎮 CS:GO", callback_data="Algo_arb:game:csgo"),
            InlineKeyboardButton("🎮 Dota 2", callback_data="Algo_arb:game:dota2"),
        ],
        [
            InlineKeyboardButton("🎮 Rust", callback_data="Algo_arb:game:rust"),
            InlineKeyboardButton("🎮 TF2", callback_data="Algo_arb:game:tf2"),
        ],
        [
            InlineKeyboardButton(
                "⚡ Авто-покупка: OFF", callback_data="Algo_arb:toggle_auto"
            ),
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="Algo_arb:menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def Algo_arb_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /Algo_arb command - main Algo arbitrage menu."""
    arbitrage = await _get_arbitrage()
    stats = arbitrage.get_stats()

    status_emoji = "🟢" if stats["is_running"] else "🔴"

    text = (
        f"🤖 <b>Algo Unified Arbitrage</b>\n\n"
        f"Статус: {status_emoji} {'Активен' if stats['is_running'] else 'Остановлен'}\n"
        f"⏱ Аптайм: {stats['uptime_minutes']} мин\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Сканов: {stats['scans_completed']}\n"
        f"• Найдено: {stats['opportunities_found']}\n"
        f"• Выполнено: {stats['opportunities_executed']}\n"
        f"• Прибыль: ${stats['total_profit_usd']:.2f}\n\n"
        f"<i>Algo анализирует DMarket, Waxpeer и Steam\n"
        f"для поиска лучших арбитражных возможностей.</i>"
    )

    # Set Telegram for notifications
    if update.effective_chat:
        arbitrage.set_telegram(context.bot, update.effective_chat.id)

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=_get_main_keyboard(),
    )


async def Algo_arb_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Algo arbitrage callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("Algo_arb:"):
        return

    action = data.split(":")[1] if ":" in data else ""

    arbitrage = await _get_arbitrage()

    # Set Telegram for notifications
    if update.effective_chat:
        arbitrage.set_telegram(context.bot, update.effective_chat.id)

    if action == "menu":
        stats = arbitrage.get_stats()
        status_emoji = "🟢" if stats["is_running"] else "🔴"

        text = (
            f"🤖 <b>Algo Unified Arbitrage</b>\n\n"
            f"Статус: {status_emoji} {'Активен' if stats['is_running'] else 'Остановлен'}\n"
            f"⏱ Аптайм: {stats['uptime_minutes']} мин\n\n"
            f"📊 Сканов: {stats['scans_completed']} | "
            f"Найдено: {stats['opportunities_found']}"
        )

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=_get_main_keyboard(),
        )

    elif action == "scan":
        await query.edit_message_text(
            "🔍 <b>Сканирование...</b>\n\nПроверяю DMarket, Waxpeer и Steam цены...",
            parse_mode="HTML",
        )

        try:
            opportunities = await arbitrage.scan_all()

            if opportunities:
                text = f"✅ <b>Найдено {len(opportunities)} возможностей!</b>\n\n"

                for i, opp in enumerate(opportunities[:10], 1):
                    platform_info = (
                        f"{opp.buy_platform.value}→{opp.sell_platform.value}"
                    )
                    steam_info = (
                        f" (Steam: ${opp.steam_price:.2f})" if opp.steam_price else ""
                    )

                    text += (
                        f"<b>{i}. {opp.item_name[:35]}</b>\n"
                        f"   💰 ROI: <b>{opp.roi_percent:.1f}%</b> | "
                        f"Прибыль: ${float(opp.net_profit):.2f}\n"
                        f"   📍 {platform_info} | Algo: {opp.Algo_confidence:.0%}{steam_info}\n\n"
                    )

                if len(opportunities) > 10:
                    text += f"\n<i>...и ещё {len(opportunities) - 10} возможностей</i>"
            else:
                text = (
                    "😔 <b>Возможности не найдены</b>\n\n"
                    "Попробуйте:\n"
                    "• Снизить минимальный ROI\n"
                    "• Добавить больше игр\n"
                    "• Подождать изменения рынка"
                )

            await query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=_get_main_keyboard(),
            )

        except Exception as e:
            logger.error("scan_error", error=str(e))
            await query.edit_message_text(
                f"❌ <b>Ошибка сканирования</b>\n\n{str(e)[:200]}",
                parse_mode="HTML",
                reply_markup=_get_main_keyboard(),
            )

    elif action == "start":
        if arbitrage._running:
            await query.edit_message_text(
                "⚠️ <b>Автосканирование уже запущено!</b>",
                parse_mode="HTML",
                reply_markup=_get_main_keyboard(),
            )
        else:
            asyncio.create_task(arbitrage.start_auto_scan())
            await query.edit_message_text(
                "✅ <b>Автосканирование запущено!</b>\n\n"
                f"⏱ Интервал: {arbitrage.config.scan_interval_seconds} сек\n"
                f"📊 Игры: {', '.join(arbitrage.config.games)}\n"
                f"💰 Мин. ROI: {arbitrage.config.min_roi_percent}%\n\n"
                "<i>Вы будете получать уведомления о найденных возможностях.</i>",
                parse_mode="HTML",
                reply_markup=_get_main_keyboard(),
            )

    elif action == "stop":
        if not arbitrage._running:
            await query.edit_message_text(
                "⚠️ <b>Автосканирование не запущено!</b>",
                parse_mode="HTML",
                reply_markup=_get_main_keyboard(),
            )
        else:
            await arbitrage.stop_auto_scan()
            stats = arbitrage.get_stats()

            await query.edit_message_text(
                "⏹ <b>Автосканирование остановлено</b>\n\n"
                f"📊 Сканов выполнено: {stats['scans_completed']}\n"
                f"🔍 Найдено возможностей: {stats['opportunities_found']}\n"
                f"✅ Выполнено сделок: {stats['opportunities_executed']}\n"
                f"💰 Общая прибыль: ${stats['total_profit_usd']:.2f}",
                parse_mode="HTML",
                reply_markup=_get_main_keyboard(),
            )

    elif action == "opportunities":
        opportunities = arbitrage.get_opportunities()

        if opportunities:
            text = f"📊 <b>Текущие возможности ({len(opportunities)})</b>\n\n"

            for i, opp in enumerate(opportunities[:15], 1):
                type_emoji = {
                    "dmarket_internal": "🔄",
                    "dmarket_to_waxpeer": "➡️",
                    "waxpeer_to_dmarket": "⬅️",
                    "steam_underpriced": "💎",
                }.get(opp.arb_type.value, "📦")

                text += (
                    f"{type_emoji} <b>{opp.item_name[:30]}</b>\n"
                    f"   {opp.buy_platform.value} ${float(opp.buy_price):.2f} → "
                    f"{opp.sell_platform.value} ${float(opp.sell_price):.2f}\n"
                    f"   📈 ROI: {opp.roi_percent:.1f}% | "
                    f"💵 ${float(opp.net_profit):.2f}\n\n"
                )
        else:
            text = "📊 <b>Нет сохранённых возможностей</b>\n\nВыполните сканирование для поиска."

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=_get_main_keyboard(),
        )

    elif action == "stats":
        stats = arbitrage.get_stats()

        text = (
            "📈 <b>Статистика Algo Arbitrage</b>\n\n"
            f"⏱ Время работы: {stats['uptime_minutes']} мин\n"
            f"🔄 Сканов: {stats['scans_completed']}\n\n"
            f"<b>Возможности:</b>\n"
            f"• Найдено: {stats['opportunities_found']}\n"
            f"• В ожидании: {stats['pending_opportunities']}\n"
            f"• Выполнено: {stats['opportunities_executed']}\n\n"
            f"<b>Финансы:</b>\n"
            f"• Прибыль: ${stats['total_profit_usd']:.2f}\n\n"
            f"<b>Конфигурация:</b>\n"
            f"• Мин. ROI: {arbitrage.config.min_roi_percent}%\n"
            f"• Авто-покупка: {'Да' if arbitrage.config.auto_execute else 'Нет'}\n"
            f"• Dry Run: {'Да' if arbitrage.config.dry_run else 'Нет'}"
        )

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=_get_main_keyboard(),
        )

    elif action == "settings":
        config = arbitrage.config

        text = (
            "⚙️ <b>НастSwarmки Algo Arbitrage</b>\n\n"
            f"📊 Мин. ROI: {config.min_roi_percent}%\n"
            f"💰 Макс. цена: ${config.max_buy_price_usd}\n"
            f"🎮 Игры: {', '.join(config.games)}\n"
            f"⏱ Интервал: {config.scan_interval_seconds} сек\n\n"
            f"⚡ Авто-покупка: {'✅ Вкл' if config.auto_execute else '❌ Выкл'}\n"
            f"🧪 Dry Run: {'✅ Вкл' if config.dry_run else '❌ Выкл'}"
        )

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=_get_settings_keyboard(),
        )

    elif action == "toggle_auto":
        arbitrage.config.auto_execute = not arbitrage.config.auto_execute
        status = "включена" if arbitrage.config.auto_execute else "выключена"

        await query.edit_message_text(
            f"⚡ <b>Авто-покупка {status}!</b>\n\n"
            f"{'⚠️ Внимание: бот будет автоматически покупать предметы!' if arbitrage.config.auto_execute else '✅ Бот только показывает возможности.'}",
            parse_mode="HTML",
            reply_markup=_get_settings_keyboard(),
        )

    elif action.startswith("game:"):
        game = action.split(":")[1]
        if game in arbitrage.config.games:
            arbitrage.config.games.remove(game)
            status = "удалена"
        else:
            arbitrage.config.games.append(game)
            status = "добавлена"

        await query.edit_message_text(
            f"🎮 <b>Игра {game.upper()} {status}!</b>\n\n"
            f"Текущие игры: {', '.join(arbitrage.config.games)}",
            parse_mode="HTML",
            reply_markup=_get_settings_keyboard(),
        )


class AlgoArbitrageHandler:
    """Handler class for Algo Arbitrage."""

    def get_handlers(self) -> list:
        """Return list of handlers."""
        return [
            CommandHandler("Algo_arb", Algo_arb_command),
            CallbackQueryHandler(Algo_arb_callback, pattern=r"^Algo_arb:"),
        ]


def get_handlers() -> list:
    """Get all handlers for registration."""
    return AlgoArbitrageHandler().get_handlers()
