"""Automatic Arbitrage handler with mode selection.

This module handles the "Automatic Arbitrage" button functionality:
1. Mode selection (Boost, Standard, Medium, Advanced, Pro)
2. API health check before scanning
3. Integration with ScannerManager
4. Multi-game scanning
5. Results notification

Features:
- Interactive mode selection via inline keyboard
- Pre-scan API validation
- Utilizes ScannerManager for efficient scanning
- Supports all games simultaneously
- Progress updates during scanning
"""

import logging
from typing import TYPE_CHECKING

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.utils.sentry_breadcrumbs import add_command_breadcrumb

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI


logger = structlog.get_logger(__name__)
std_logger = logging.getLogger(__name__)


def get_mode_selection_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for arbitrage mode selection.

    Modes correspond to scanner_manager levels:
    - Boost: Low-price items ($0.50 - $3), quick turnover
    - Standard: Mid-range items ($3 - $10), balanced
    - Medium: Higher value ($10 - $30), better margins
    - Advanced: Premium items ($30 - $100), high margins
    - Pro: Top-tier items ($100+), best margins

    Returns:
        InlineKeyboardMarkup with mode selection buttons
    """
    keyboard = [
        [InlineKeyboardButton("🚀 Boost (Разгон)", callback_data="mode_boost")],
        [InlineKeyboardButton("📊 Standard (Стандарт)", callback_data="mode_standard")],
        [InlineKeyboardButton("💎 Medium (Средний)", callback_data="mode_medium")],
        [InlineKeyboardButton("⭐ Advanced (Продвинутый)", callback_data="mode_advanced")],
        [InlineKeyboardButton("👑 Pro (Профессионал)", callback_data="mode_pro")],
    ]
    return InlineKeyboardMarkup(keyboard)


# Mode to level mapping (corresponds to scanner levels)
MODE_LEVEL_MAP = {
    "boost": "boost",
    "standard": "standard",
    "medium": "medium",
    "advanced": "advanced",
    "pro": "pro",
}

# Mode descriptions for user
MODE_DESCRIPTIONS = {
    "boost": "🚀 Boost: $0.50-$3, quick turnover, 10%+ margin",
    "standard": "📊 Standard: $3-$10, balanced, 12%+ margin",
    "medium": "💎 Medium: $10-$30, good margins, 15%+ margin",
    "advanced": "⭐ Advanced: $30-$100, high value, 18%+ margin",
    "pro": "👑 Pro: $100+, premium items, 20%+ margin",
}


async def handle_automatic_arbitrage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Automatic Arbitrage button - initiate mode selection.

    Args:
        update: Telegram update object
        context: Callback context

    Returns:
        None (sends mode selection keyboard)
    """
    user = update.effective_user
    if not user:
        return

    message = update.message or (update.callback_query.message if update.callback_query else None)
    if not message:
        return

    add_command_breadcrumb(
        command="automatic_arbitrage",
        user_id=user.id,
        username=user.username or "",
        chat_id=message.chat_id,
    )

    logger.info("automatic_arbitrage_started", user_id=user.id)

    # Send mode selection keyboard
    await message.reply_text(
        "🤖 <b>Automatic Arbitrage</b>\n\n"
        "Select your trading mode:\n\n"
        f"{MODE_DESCRIPTIONS['boost']}\n"
        f"{MODE_DESCRIPTIONS['standard']}\n"
        f"{MODE_DESCRIPTIONS['medium']}\n"
        f"{MODE_DESCRIPTIONS['advanced']}\n"
        f"{MODE_DESCRIPTIONS['pro']}\n\n"
        "Each mode scans all supported games simultaneously.",
        reply_markup=get_mode_selection_keyboard(),
        parse_mode="HTML",
    )


# ============================================================================
# Helper functions for handle_mode_selection_callback (Phase 2 refactoring)
# ============================================================================


async def _check_api_health(api_client: "DMarketAPI") -> tuple[bool, str | None]:
    """Check API health before scanning.

    Returns:
        Tuple of (is_healthy, error_message)
    """
    try:
        balance_result = await api_client.get_balance()
        if balance_result.get("error"):
            return False, balance_result.get("error_message", "Unknown error")
        return True, None
    except Exception as e:
        return False, str(e)


async def _run_fallback_scan(
    api_client: "DMarketAPI",
    level: str,
) -> tuple[list, str | None]:
    """Run fallback scan using ArbitrageScanner (single game).

    Returns:
        Tuple of (results_list, error_message)
    """
    from src.dmarket.scanner.engine import ArbitrageScanner

    scanner = ArbitrageScanner(api_client=api_client)
    try:
        results = await scanner.scan_level(
            level=level,
            game="csgo",
            max_results=10,
        )
        return results, None
    except Exception as e:
        return [], str(e)


async def _run_parallel_scan(
    scanner_manager,
    level: str,
) -> tuple[dict, str | None]:
    """Run parallel scan using ScannerManager.

    Returns:
        Tuple of (results_dict, error_message)
    """
    games = ["csgo", "dota2", "rust", "tf2"]
    try:
        results = await scanner_manager.scan_multiple_games(
            games=games,
            level=level,
            max_items_per_game=10,
        )
        return results, None
    except Exception as e:
        return {}, str(e)


def _format_fallback_results(results: list, mode: str) -> str:
    """Format fallback scan results for display."""
    if not results:
        return (
            f"ℹ️ <b>No opportunities found</b>\n\n"
            f"Mode: {mode.capitalize()}\n"
            f"Game: CS:GO\n\n"
            f"Try a different mode or check back later."
        )

    results_text = f"✅ <b>Found {len(results)} opportunities!</b>\n\n"
    for i, opp in enumerate(results[:5], 1):
        results_text += (
            f"{i}. {opp.get('item_name', 'Unknown')}\n"
            f"   💰 Price: ${opp.get('price', 0):.2f}\n"
            f"   📈 Profit: {opp.get('profit_margin', 0):.1f}%\n\n"
        )

    if len(results) > 5:
        results_text += f"...and {len(results) - 5} more opportunities.\n"

    return results_text


def _format_parallel_results(results: dict, mode: str) -> str:
    """Format parallel scan results for display."""
    total_opportunities = sum(len(v) for v in results.values())

    if total_opportunities == 0:
        return (
            f"ℹ️ <b>No opportunities found</b>\n\n"
            f"Mode: {mode.capitalize()}\n"
            f"Games: All supported\n\n"
            f"Market conditions may not be favorable right now.\n"
            f"Try again in a few minutes or select a different mode."
        )

    results_text = (
        f"✅ <b>Scan Complete!</b>\n\n"
        f"Found <b>{total_opportunities}</b> opportunities across all games:\n\n"
    )

    for game, opps in results.items():
        if opps:
            results_text += f"🎮 <b>{game.upper()}</b>: {len(opps)} items\n"

    results_text += f"\n📊 Mode: {mode.capitalize()}\n"
    results_text += "⏱️ Scan completed successfully!\n\n"
    results_text += "Use /arbitrage command for detailed view\nor check specific game results."

    return results_text


# ============================================================================
# End of helper functions
# ============================================================================


async def handle_mode_selection_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle mode selection callback and start scanning.

    Phase 2 Refactoring: Logic split into helper functions.
    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    user = update.effective_user
    if not user:
        return

    # Extract mode from callback data
    mode = query.data.replace("mode_", "")
    level = MODE_LEVEL_MAP.get(mode, "standard")

    logger.info("mode_selected", user_id=user.id, mode=mode, level=level)

    if query.message:
        await query.message.edit_text(
            f"✅ Selected: <b>{mode.capitalize()}</b>\n\n"
            f"{MODE_DESCRIPTIONS[mode]}\n\n"
            f"🔍 Checking API...",
            parse_mode="HTML",
        )

    # Step 1: API Check (Phase 2 - use helper)
    api_client = context.bot_data.get("dmarket_api")
    if not api_client:
        if query.message:
            await query.message.edit_text(
                "❌ <b>Error</b>\n\nAPI client not initialized.", parse_mode="HTML"
            )
        logger.error("mode_scan_failed", reason="no_api_client", user_id=user.id)
        return

    is_healthy, error_msg = await _check_api_health(api_client)
    if not is_healthy:
        if query.message:
            await query.message.edit_text(
                f"❌ <b>API Check Failed</b>\n\nError: {error_msg}", parse_mode="HTML"
            )
        logger.error("mode_scan_api_check_failed", error=error_msg, user_id=user.id)
        return

    # Step 2: Start scanning
    if query.message:
        await query.message.edit_text(
            f"✅ API OK!\n\n🔍 <b>Starting {mode.capitalize()} scan...</b>\n\n"
            f"Scanning all games (30-60 seconds)...",
            parse_mode="HTML",
        )

    scanner_manager = context.bot_data.get("scanner_manager")

    if not scanner_manager:
        # Fallback scan (Phase 2 - use helper)
        if query.message:
            await query.message.edit_text(
                "⚠️ Using fallback scanning (may be slower)...", parse_mode="HTML"
            )
        logger.warning("scanner_manager_not_available", user_id=user.id)

        results, error = await _run_fallback_scan(api_client, level)
        if error:
            if query.message:
                await query.message.edit_text(
                    f"❌ <b>Scan Failed</b>\n\nError: {error}", parse_mode="HTML"
                )
            logger.error("fallback_scan_failed", error=error, user_id=user.id)
            return

        results_text = _format_fallback_results(results, mode)
        if query.message:
            await query.message.edit_text(results_text, parse_mode="HTML")
        logger.info("fallback_scan_completed", user_id=user.id, opportunities=len(results))
        return

    # Parallel scan (Phase 2 - use helper)
    results, error = await _run_parallel_scan(scanner_manager, level)
    if error:
        if query.message:
            await query.message.edit_text(
                f"❌ <b>Scan Failed</b>\n\nError: {error}\n\n"
                f"Please try again in a few minutes.",
                parse_mode="HTML",
            )
        logger.error("parallel_scan_failed", error=error, user_id=user.id, mode=mode)
        return

    total = sum(len(v) for v in results.values())
    results_text = _format_parallel_results(results, mode)
    if query.message:
        await query.message.edit_text(results_text, parse_mode="HTML")
    logger.info("parallel_scan_success", user_id=user.id, mode=mode, total=total)
