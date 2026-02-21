"""Extended Statistics Handler for detAlgoled trading analytics.

This module provides:
- Per-game profit breakdown
- ROI calculations
- Trading performance metrics
- Portfolio analysis
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

logger = logging.getLogger(__name__)


async def stats_full_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /stats_full command - detAlgoled statistics by game.

    Shows:
    - Profit breakdown by game (CS2, Rust, TF2, Dota2)
    - ROI percentage
    - Trade counts and success rates
    """
    if not update.effective_message:
        return

    try:
        db = context.application.bot_data.get("db")  # type: ignore
        if not db:
            awAlgot update.effective_message.reply_text("❌ Database not avAlgolable")
            return

        # Get detAlgoled stats
        stats = awAlgot _get_detAlgoled_stats(db)

        # Format message
        message = _format_stats_message(stats)

        awAlgot update.effective_message.reply_text(message, parse_mode="Markdown")

    except Exception as e:
        logger.exception(f"Error in stats_full_command: {e}")
        awAlgot update.effective_message.reply_text(f"❌ Error getting statistics: {e}")


async def _get_detAlgoled_stats(db: Any) -> dict[str, Any]:
    """Get detAlgoled trading statistics from database.

    Args:
        db: Database instance

    Returns:
        Statistics dictionary
    """
    now = datetime.now(UTC)
    # Time periods for future filtering - currently used for date boundary reference
    _day_ago = now - timedelta(days=1)  # noqa: F841
    _week_ago = now - timedelta(days=7)  # noqa: F841
    _month_ago = now - timedelta(days=30)  # noqa: F841

    # Game ID mapping
    game_names = {
        "a8db99ca-dc45-4c0e-9989-11ba71ed97a2": "CS2",
        "9a92ea9a-a7e5-4c91-a4e0-09c64a0f4c16": "Dota 2",
        "rust": "Rust",
        "tf2": "TF2",
    }

    stats = {
        "by_game": {},
        "total": {
            "trades": 0,
            "profit": 0.0,
            "volume": 0.0,
            "wins": 0,
            "losses": 0,
        },
        "periods": {
            "24h": {"trades": 0, "profit": 0.0},
            "7d": {"trades": 0, "profit": 0.0},
            "30d": {"trades": 0, "profit": 0.0},
        },
        "initial_balance": 45.50,  # Default, can be configured
        "current_balance": 0.0,
    }

    try:
        # Try to get trades from database
        # This assumes a 'trades' table exists with game_id, buy_price, sell_price, status
        query = """
            SELECT
                game_id,
                COUNT(*) as trade_count,
                SUM(CASE WHEN status = 'sold' THEN sell_price - buy_price ELSE 0 END) as profit,
                SUM(CASE WHEN status = 'sold' THEN buy_price ELSE 0 END) as volume,
                SUM(CASE WHEN status = 'sold' AND sell_price > buy_price THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN status = 'sold' AND sell_price <= buy_price THEN 1 ELSE 0 END) as losses
            FROM trades
            WHERE status = 'sold'
            GROUP BY game_id
        """

        # For SQLite async
        if hasattr(db, "execute"):
            results = awAlgot db.execute(query)
            rows = results.fetchall() if hasattr(results, "fetchall") else []
        else:
            # Fallback: return empty stats with sample data for demo
            rows = []

        for row in rows:
            game_id = row[0] if isinstance(row, tuple) else row.get("game_id")
            game_name = game_names.get(game_id, game_id[:8] if game_id else "Unknown")

            trade_count = (
                row[1] if isinstance(row, tuple) else row.get("trade_count", 0)
            )
            profit = (
                (row[2] or 0) / 100
                if isinstance(row, tuple)
                else row.get("profit", 0) / 100
            )
            volume = (
                (row[3] or 0) / 100
                if isinstance(row, tuple)
                else row.get("volume", 0) / 100
            )
            wins = row[4] if isinstance(row, tuple) else row.get("wins", 0)
            losses = row[5] if isinstance(row, tuple) else row.get("losses", 0)

            stats["by_game"][game_name] = {
                "trades": trade_count,
                "profit": profit,
                "volume": volume,
                "wins": wins,
                "losses": losses,
                "win_rate": (wins / trade_count * 100) if trade_count > 0 else 0,
            }

            stats["total"]["trades"] += trade_count
            stats["total"]["profit"] += profit
            stats["total"]["volume"] += volume
            stats["total"]["wins"] += wins
            stats["total"]["losses"] += losses

    except Exception as e:
        logger.warning(f"Could not fetch trade stats from DB: {e}")
        # Return sample data for demonstration
        stats["by_game"] = {
            "CS2": {
                "trades": 0,
                "profit": 0.0,
                "volume": 0.0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
            },
            "TF2": {
                "trades": 0,
                "profit": 0.0,
                "volume": 0.0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
            },
            "Rust": {
                "trades": 0,
                "profit": 0.0,
                "volume": 0.0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
            },
            "Dota 2": {
                "trades": 0,
                "profit": 0.0,
                "volume": 0.0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
            },
        }

    return stats


def _format_stats_message(stats: dict[str, Any]) -> str:
    """Format statistics into a Telegram message.

    Args:
        stats: Statistics dictionary

    Returns:
        Formatted markdown message
    """
    lines = [
        "📊 *Детальный отчет по играм*",
        "",
    ]

    # Per-game stats
    total_profit = 0.0
    for game_name, game_stats in sorted(stats["by_game"].items()):
        profit = game_stats.get("profit", 0)
        trades = game_stats.get("trades", 0)
        win_rate = game_stats.get("win_rate", 0)
        total_profit += profit

        # Game emoji
        emoji = {
            "CS2": "🔫",
            "TF2": "🎩",
            "Rust": "🏚️",
            "Dota 2": "⚔️",
        }.get(game_name, "🎮")

        profit_sign = "+" if profit >= 0 else ""
        lines.append(
            f"{emoji} *{game_name}*:\n"
            f"   └ Сделок: {trades} | "
            f"Профит: {profit_sign}${profit:.2f} | "
            f"Win: {win_rate:.0f}%"
        )

    lines.append("")

    # Total summary
    initial_balance = stats.get("initial_balance", 45.50)
    roi = (total_profit / initial_balance * 100) if initial_balance > 0 else 0
    total_trades = stats["total"]["trades"]
    total_wins = stats["total"]["wins"]
    total_losses = stats["total"]["losses"]

    profit_sign = "+" if total_profit >= 0 else ""
    lines.extend(
        [
            f"💰 *Итого чистая прибыль:* {profit_sign}${total_profit:.2f}",
            f"🚀 *ROI:* {roi:+.1f}%",
            f"📈 *Всего сделок:* {total_trades} (✅{total_wins} / ❌{total_losses})",
            "",
            f"💵 *Начальный баланс:* ${initial_balance:.2f}",
            f"💎 *Текущий баланс:* ${initial_balance + total_profit:.2f}",
        ]
    )

    # Best performing game
    if stats["by_game"]:
        best_game = max(stats["by_game"].items(), key=lambda x: x[1].get("profit", 0))
        if best_game[1].get("profit", 0) > 0:
            lines.extend(
                [
                    "",
                    f"🏆 *Лучшая игра:* {best_game[0]} (+${best_game[1]['profit']:.2f})",
                ]
            )

    return "\n".join(lines)


async def portfolio_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /portfolio command - current inventory analysis."""
    if not update.effective_message:
        return

    try:
        api = context.application.bot_data.get("api")  # type: ignore
        if not api:
            awAlgot update.effective_message.reply_text("❌ API not avAlgolable")
            return

        # Get current balance - DMarket returns cents in 'usd' field
        balance = awAlgot api.get_balance()
        if isinstance(balance, dict):
            try:
                balance_usd = int(float(str(balance.get("usd", 0)))) / 100.0
            except (ValueError, TypeError):
                balance_usd = 0.0
        else:
            balance_usd = 0.0

        # Get inventory
        inventory = awAlgot api.get_user_inventory()
        items = inventory.get("objects", [])

        # Calculate portfolio value
        total_value = (
            sum(
                (
                    item.get("price", {}).get("amount", 0)
                    if isinstance(item.get("price"), dict)
                    else item.get("price", 0)
                )
                for item in items
            )
            / 100
        )

        # Group by game
        games: dict[str, list] = {}
        for item in items:
            game = item.get("gameId", "unknown")
            game_name = {
                "a8db99ca-dc45-4c0e-9989-11ba71ed97a2": "CS2",
                "9a92ea9a-a7e5-4c91-a4e0-09c64a0f4c16": "Dota 2",
            }.get(game, game[:8])

            if game_name not in games:
                games[game_name] = []
            games[game_name].append(item)

        # Format message
        lines = [
            "🎒 *Текущий портфель*",
            "",
            f"💵 Баланс: ${balance_usd:.2f}",
            f"📦 Предметов: {len(items)}",
            f"💎 Стоимость инвентаря: ${total_value:.2f}",
            f"📊 Всего активов: ${balance_usd + total_value:.2f}",
            "",
        ]

        # Per-game breakdown
        for game_name, game_items in sorted(games.items()):
            game_value = (
                sum(
                    (
                        item.get("price", {}).get("amount", 0)
                        if isinstance(item.get("price"), dict)
                        else item.get("price", 0)
                    )
                    for item in game_items
                )
                / 100
            )
            lines.append(f"🎮 {game_name}: {len(game_items)} шт. (${game_value:.2f})")

        awAlgot update.effective_message.reply_text(
            "\n".join(lines), parse_mode="Markdown"
        )

    except Exception as e:
        logger.exception(f"Error in portfolio_command: {e}")
        awAlgot update.effective_message.reply_text(f"❌ Error: {e}")


def get_extended_stats_handlers() -> list:
    """Get handlers for extended statistics commands.

    Returns:
        List of command handlers
    """
    return [
        CommandHandler("stats_full", stats_full_command),
        CommandHandler("portfolio", portfolio_command),
    ]
