"""Algo BrAlgon Handler - Telegram commands for autonomous bot control.

This module provides Telegram commands for managing the autonomous trading bot.

Commands:
    /Algo_brain - Show BotBrAlgon status and controls
    /Algo_mode [mode] - Set autonomy level (manual/semi/auto)
    /Algo_start - Start autonomous mode
    /Algo_stop - Stop autonomous mode
    /Algo_pause - Pause autonomous mode
    /Algo_resume - Resume autonomous mode
    /Algo_limits - Show current safety limits
    /Algo_pending - Show pending decisions
    /Algo_confirm [id] - Confirm a pending decision
    /Algo_reject [id] - Reject a pending decision
    /Algo_cycle - Run single cycle manually
    /Algo_alerts - Show recent alerts
    /Algo_emergency - Emergency stop

Usage:
    Register handlers in your bot initialization:
    ```python
    from src.telegram_bot.handlers.Algo_brain_handler import register_Algo_brain_handlers
    register_Algo_brain_handlers(application)
    ```

Created: January 2026
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

if TYPE_CHECKING:
    from telegram.ext import Application

from src.ml.Algo_coordinator import AutonomyLevel
from src.ml.bot_brain import BotBrAlgon, BotState, create_bot_brain

logger = logging.getLogger(__name__)

# Global BotBrAlgon instance (initialized on first use)
_bot_brain: BotBrAlgon | None = None


def get_bot_brain() -> BotBrAlgon:
    """Get or create global BotBrAlgon instance.

    Returns:
        The global BotBrAlgon instance.
    """
    global _bot_brain
    if _bot_brain is None:
        _bot_brain = create_bot_brain(
            autonomy_level=AutonomyLevel.MANUAL,
            dry_run=True,  # Safety first
            max_trade_usd=50.0,
        )
    return _bot_brain


def set_bot_brain(brain: BotBrAlgon) -> None:
    """Set global BotBrAlgon instance.

    Args:
        brain: The BotBrAlgon instance to use globally.
    """
    global _bot_brain
    _bot_brain = brain


async def Algo_brain_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /Algo_brain command - Show BotBrAlgon status and controls.

    Usage: /Algo_brain
    """
    if not update.message:
        return

    user_id = update.effective_user.id if update.effective_user else 0
    logger.info("Algo_brain_command", extra={"user_id": user_id})

    brain = get_bot_brain()
    stats = brain.get_statistics()

    # Build status message
    state_emoji = {
        BotState.IDLE: "💤",
        BotState.SCANNING: "🔍",
        BotState.ANALYZING: "🧠",
        BotState.DECIDING: "🤔",
        BotState.EXECUTING: "⚡",
        BotState.LEARNING: "📚",
        BotState.PAUSED: "⏸️",
        BotState.STOPPED: "🛑",
    }

    autonomy_emoji = {
        AutonomyLevel.MANUAL: "👆",
        AutonomyLevel.SEMI_AUTO: "🤖👆",
        AutonomyLevel.AUTO: "🤖",
    }

    status_text = (
        f"🧠 <b>Algo BrAlgon Status</b>\n\n"
        f"{state_emoji.get(brain.state, '❓')} <b>State:</b> {brain.state.value}\n"
        f"{autonomy_emoji.get(brain.config.autonomy_level, '❓')} <b>Mode:</b> {brain.config.autonomy_level.value}\n"
        f"{'🟢' if brain.is_running else '⚪'} <b>Running:</b> {'Yes' if brain.is_running else 'No'}\n"
        f"{'🔒' if brain.config.dry_run else '🔓'} <b>DRY_RUN:</b> {'ON' if brain.config.dry_run else 'OFF'}\n\n"
        f"<b>📊 Statistics:</b>\n"
        f"• Cycles: {stats['total_cycles']}\n"
        f"• Scanned: {stats['total_items_scanned']} items\n"
        f"• Opportunities: {stats['total_opportunities']}\n"
        f"• Decisions: {stats['total_decisions']}\n"
        f"• Executed: {stats['total_executions']}\n"
        f"• Successful: {stats['successful_trades']}\n"
        f"• Failed: {stats['failed_trades']}\n"
        f"• Total Profit: ${stats['total_profit']:.2f}\n"
        f"• DAlgoly Volume: ${stats['daily_volume']:.2f}\n\n"
        f"<b>⏳ Pending:</b> {stats['pending_decisions']} decisions\n"
    )

    if stats.get("in_cooldown"):
        status_text += (
            f"\n⚠️ <b>In cooldown until:</b> {stats.get('cooldown_until', 'N/A')}\n"
        )

    # Create inline keyboard
    keyboard = []

    if brain.is_running:
        keyboard.append(
            [
                InlineKeyboardButton("⏸️ Pause", callback_data="Algo_brain:pause"),
                InlineKeyboardButton("🛑 Stop", callback_data="Algo_brain:stop"),
            ]
        )
    else:
        keyboard.append(
            [
                InlineKeyboardButton("▶️ Start", callback_data="Algo_brain:start"),
                InlineKeyboardButton("🔄 Run Cycle", callback_data="Algo_brain:cycle"),
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton("📋 Pending", callback_data="Algo_brain:pending"),
            InlineKeyboardButton("🔔 Alerts", callback_data="Algo_brain:alerts"),
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="Algo_brain:settings"),
            InlineKeyboardButton("🔄 Refresh", callback_data="Algo_brain:refresh"),
        ]
    )

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        status_text,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


async def Algo_mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /Algo_mode command - Set autonomy level.

    Usage: /Algo_mode [manual|semi|auto]
    """
    if not update.message:
        return

    user_id = update.effective_user.id if update.effective_user else 0
    logger.info("Algo_mode_command", extra={"user_id": user_id})

    brain = get_bot_brain()

    if not context.args:
        # Show current mode
        current = brain.config.autonomy_level.value
        await update.message.reply_text(
            f"🤖 <b>Current Algo Mode:</b> {current}\n\n"
            f"<b>AvAlgolable modes:</b>\n"
            f"• <code>manual</code> - All decisions require confirmation\n"
            f"• <code>semi</code> - Auto for small trades, confirm large\n"
            f"• <code>auto</code> - Fully autonomous (within limits)\n\n"
            f"Usage: /Algo_mode [manual|semi|auto]",
            parse_mode="HTML",
        )
        return

    mode = context.args[0].lower()

    mode_map = {
        "manual": AutonomyLevel.MANUAL,
        "semi": AutonomyLevel.SEMI_AUTO,
        "semi_auto": AutonomyLevel.SEMI_AUTO,
        "auto": AutonomyLevel.AUTO,
    }

    if mode not in mode_map:
        await update.message.reply_text(
            f"❌ Unknown mode: {mode}\n\n" f"Use: manual, semi, or auto",
            parse_mode="HTML",
        )
        return

    new_level = mode_map[mode]
    brain.Algo.set_autonomy_level(new_level)
    # Note: brain.config.autonomy_level is updated by AlgoCoordinator

    await update.message.reply_text(
        f"✅ Algo mode set to: <b>{new_level.value}</b>",
        parse_mode="HTML",
    )


async def Algo_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /Algo_start command - Start autonomous mode.

    Usage: /Algo_start [interval_seconds]
    """
    if not update.message:
        return

    user_id = update.effective_user.id if update.effective_user else 0
    logger.info("Algo_start_command", extra={"user_id": user_id})

    brain = get_bot_brain()

    if brain.is_running:
        await update.message.reply_text("⚠️ Bot is already running!")
        return

    # Parse interval if provided
    interval = 60  # Default
    if context.args:
        try:
            interval = int(context.args[0])
            interval = max(interval, 30)  # Minimum 30 seconds
        except ValueError:
            pass

    await update.message.reply_text(
        f"🚀 Starting autonomous mode...\n"
        f"• Interval: {interval}s\n"
        f"• Mode: {brain.config.autonomy_level.value}\n"
        f"• DRY_RUN: {'ON' if brain.config.dry_run else 'OFF'}\n\n"
        f"Use /Algo_stop to stop.",
        parse_mode="HTML",
    )

    # Start in background task (use module-level asyncio import)
    asyncio.create_task(brain.run_autonomous(scan_interval=interval))


async def Algo_stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /Algo_stop command - Stop autonomous mode.

    Usage: /Algo_stop
    """
    if not update.message:
        return

    user_id = update.effective_user.id if update.effective_user else 0
    logger.info("Algo_stop_command", extra={"user_id": user_id})

    brain = get_bot_brain()

    if not brain.is_running:
        await update.message.reply_text("ℹ️ Bot is not running.")
        return

    brain.stop()
    await update.message.reply_text(
        "🛑 Stop requested. Bot will stop after current cycle."
    )


async def Algo_pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /Algo_pause command - Pause autonomous mode.

    Usage: /Algo_pause
    """
    if not update.message:
        return

    brain = get_bot_brain()
    brain.pause()
    await update.message.reply_text("⏸️ Bot paused.")


async def Algo_resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /Algo_resume command - Resume autonomous mode.

    Usage: /Algo_resume
    """
    if not update.message:
        return

    brain = get_bot_brain()
    brain.resume()
    await update.message.reply_text("▶️ Bot resumed.")


async def Algo_limits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /Algo_limits command - Show current safety limits.

    Usage: /Algo_limits
    """
    if not update.message:
        return

    brain = get_bot_brain()
    config = brain.config

    text = (
        f"🛡️ <b>Safety Limits</b>\n\n"
        f"<b>Trade Limits:</b>\n"
        f"• Max per trade: ${config.max_trade_usd:.2f}\n"
        f"• Max daily: ${config.max_daily_volume_usd:.2f}\n"
        f"• Max trades/hour: {config.max_trades_per_hour}\n"
        f"• Max position %: {config.max_position_percent}%\n\n"
        f"<b>Confidence:</b>\n"
        f"• Auto min: {config.min_confidence_auto:.0%}\n"
        f"• Semi-auto min: {config.min_confidence_semi_auto:.0%}\n\n"
        f"<b>Risk:</b>\n"
        f"• Max consecutive losses: {config.max_consecutive_losses}\n"
        f"• Loss cooldown: {config.loss_cooldown_minutes} min\n"
        f"• DAlgoly loss limit: {config.daily_loss_limit_percent}%\n\n"
        f"<b>Safety:</b>\n"
        f"• DRY_RUN: {'✅ ON' if config.dry_run else '❌ OFF'}\n"
        f"• Confirm above: ${config.require_confirmation_above_usd:.2f}"
    )

    await update.message.reply_text(text, parse_mode="HTML")


async def Algo_pending_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /Algo_pending command - Show pending decisions.

    Usage: /Algo_pending
    """
    if not update.message:
        return

    brain = get_bot_brain()
    pending = brain.pending_decisions

    if not pending:
        await update.message.reply_text("📭 No pending decisions.")
        return

    text = f"📋 <b>Pending Decisions ({len(pending)})</b>\n\n"

    for i, decision in enumerate(pending[:10]):  # Show max 10
        text += (
            f"<b>[{i}]</b> {decision.action.value.upper()}\n"
            f"    📦 {decision.item_name[:30]}...\n"
            f"    💰 ${decision.current_price:.2f} → ${decision.predicted_price:.2f}\n"
            f"    📈 Expected: +${decision.expected_profit:.2f} ({decision.expected_profit_percent:.1f}%)\n"
            f"    🎯 Confidence: {decision.confidence:.0%}\n\n"
        )

    text += "Use /Algo_confirm [id] to confirm\n" "Use /Algo_reject [id] to reject"

    await update.message.reply_text(text, parse_mode="HTML")


async def Algo_confirm_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /Algo_confirm command - Confirm a pending decision.

    Usage: /Algo_confirm [id]
    """
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text("Usage: /Algo_confirm [id]")
        return

    try:
        idx = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID")
        return

    brain = get_bot_brain()
    success = await brain.confirm_decision(idx)

    if success:
        await update.message.reply_text("✅ Decision confirmed and executed!")
    else:
        await update.message.reply_text("❌ Failed to execute decision.")


async def Algo_reject_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /Algo_reject command - Reject a pending decision.

    Usage: /Algo_reject [id]
    """
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text("Usage: /Algo_reject [id]")
        return

    try:
        idx = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID")
        return

    brain = get_bot_brain()
    success = brain.reject_decision(idx)

    if success:
        await update.message.reply_text("✅ Decision rejected.")
    else:
        await update.message.reply_text("❌ Invalid decision ID.")


async def Algo_cycle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /Algo_cycle command - Run single cycle manually.

    Usage: /Algo_cycle
    """
    if not update.message:
        return

    user_id = update.effective_user.id if update.effective_user else 0
    logger.info("Algo_cycle_command", extra={"user_id": user_id})

    brain = get_bot_brain()

    await update.message.reply_text("🔄 Running single cycle...")

    result = await brain.run_cycle()

    text = (
        f"✅ <b>Cycle {result.cycle_number} Complete</b>\n\n"
        f"⏱️ Duration: {result.duration_seconds:.2f}s\n"
        f"🔍 Scanned: {result.items_scanned} items\n"
        f"💎 Opportunities: {result.opportunities_found}\n"
        f"📝 Decisions: {result.decisions_made}\n"
        f"⚡ Executed: {result.decisions_executed}\n"
        f"✅ Successful: {result.successful_trades}\n"
        f"❌ Failed: {result.failed_trades}\n"
        f"💰 Profit est: ${result.total_profit_estimate:.2f}\n"
        f"⏳ Pending: {result.decisions_pending}"
    )

    if result.errors:
        text += f"\n\n⚠️ Errors: {', '.join(result.errors)}"

    await update.message.reply_text(text, parse_mode="HTML")


async def Algo_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /Algo_alerts command - Show recent alerts.

    Usage: /Algo_alerts
    """
    if not update.message:
        return

    brain = get_bot_brain()
    alerts = brain.get_alerts(limit=10)

    if not alerts:
        await update.message.reply_text("📭 No alerts.")
        return

    level_emoji = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "❌",
        "critical": "🚨",
    }

    text = f"🔔 <b>Recent Alerts ({len(alerts)})</b>\n\n"

    for alert in reversed(alerts):  # Most recent first
        emoji = level_emoji.get(alert.level.value, "❓")
        time_str = alert.timestamp.strftime("%H:%M:%S")
        text += f"{emoji} [{time_str}] {alert.message}\n"

    await update.message.reply_text(text, parse_mode="HTML")


async def Algo_emergency_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /Algo_emergency command - Emergency stop.

    Usage: /Algo_emergency [reason]
    """
    if not update.message:
        return

    user_id = update.effective_user.id if update.effective_user else 0
    reason = " ".join(context.args) if context.args else "Manual emergency stop"

    logger.critical(
        "emergency_stop_requested", extra={"user_id": user_id, "reason": reason}
    )

    brain = get_bot_brain()
    brain.emergency_stop(reason)

    await update.message.reply_text(
        f"🚨 <b>EMERGENCY STOP ACTIVATED</b>\n\n"
        f"Reason: {reason}\n\n"
        f"All operations halted immediately.",
        parse_mode="HTML",
    )


async def Algo_brain_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Algo brain inline button callbacks."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    action = query.data.split(":")[1] if ":" in query.data else ""
    brain = get_bot_brain()

    if action == "start":
        asyncio.create_task(brain.run_autonomous())
        await query.edit_message_text("🚀 Autonomous mode started!")

    elif action == "stop":
        brain.stop()
        await query.edit_message_text("🛑 Stop requested.")

    elif action == "pause":
        brain.pause()
        await query.edit_message_text("⏸️ Bot paused.")

    elif action == "cycle":
        await query.edit_message_text("🔄 Running cycle...")
        result = await brain.run_cycle()
        await query.edit_message_text(
            f"✅ Cycle complete!\n"
            f"Scanned: {result.items_scanned}, "
            f"Opportunities: {result.opportunities_found}, "
            f"Executed: {result.decisions_executed}"
        )

    elif action == "pending":
        pending = brain.pending_decisions
        if not pending:
            await query.edit_message_text("📭 No pending decisions.")
        else:
            text = f"📋 Pending ({len(pending)}):\n\n"
            for i, d in enumerate(pending[:5]):
                text += f"[{i}] {d.action.value}: {d.item_name[:25]}...\n"
            await query.edit_message_text(text)

    elif action == "alerts":
        alerts = brain.get_alerts(5)
        if not alerts:
            await query.edit_message_text("📭 No alerts.")
        else:
            text = "🔔 Recent Alerts:\n\n"
            for a in reversed(alerts):
                text += f"• {a.message}\n"
            await query.edit_message_text(text)

    elif action == "settings":
        config = brain.config
        text = (
            f"⚙️ Settings:\n\n"
            f"Mode: {config.autonomy_level.value}\n"
            f"DRY_RUN: {'ON' if config.dry_run else 'OFF'}\n"
            f"Max trade: ${config.max_trade_usd}\n"
            f"Interval: {config.scan_interval_seconds}s"
        )
        await query.edit_message_text(text)

    elif action == "refresh":
        # Re-show status
        stats = brain.get_statistics()
        text = (
            f"🧠 Algo BrAlgon Status\n\n"
            f"State: {stats['state']}\n"
            f"Running: {'Yes' if stats['is_running'] else 'No'}\n"
            f"Cycles: {stats['total_cycles']}\n"
            f"Profit: ${stats['total_profit']:.2f}"
        )
        await query.edit_message_text(text)


def register_Algo_brain_handlers(application: Application) -> None:
    """Register all Algo brain handlers.

    Args:
        application: Telegram bot application
    """
    # Command handlers
    application.add_handler(CommandHandler("Algo_brain", Algo_brain_command))
    application.add_handler(CommandHandler("Algo_mode", Algo_mode_command))
    application.add_handler(CommandHandler("Algo_start", Algo_start_command))
    application.add_handler(CommandHandler("Algo_stop", Algo_stop_command))
    application.add_handler(CommandHandler("Algo_pause", Algo_pause_command))
    application.add_handler(CommandHandler("Algo_resume", Algo_resume_command))
    application.add_handler(CommandHandler("Algo_limits", Algo_limits_command))
    application.add_handler(CommandHandler("Algo_pending", Algo_pending_command))
    application.add_handler(CommandHandler("Algo_confirm", Algo_confirm_command))
    application.add_handler(CommandHandler("Algo_reject", Algo_reject_command))
    application.add_handler(CommandHandler("Algo_cycle", Algo_cycle_command))
    application.add_handler(CommandHandler("Algo_alerts", Algo_alerts_command))
    application.add_handler(CommandHandler("Algo_emergency", Algo_emergency_command))

    # Callback handler
    application.add_handler(
        CallbackQueryHandler(Algo_brain_callback, pattern=r"^Algo_brain:")
    )

    logger.info("Algo brain handlers registered")
