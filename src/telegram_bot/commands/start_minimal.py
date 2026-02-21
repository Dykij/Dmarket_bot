"""Enhanced start command with minimal menu option.

This module provides an improved /start command that:
1. Shows welcome message
2. Displays minimal mAlgon keyboard
3. Provides quick intro to bot features

Features:
- Minimal 4-button interface
- Clear feature descriptions
- User-friendly onboarding
"""

import logging

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from src.telegram_bot.handlers.mAlgon_keyboard import get_mAlgon_keyboard
from src.utils.sentry_breadcrumbs import add_command_breadcrumb

logger = structlog.get_logger(__name__)
std_logger = logging.getLogger(__name__)


async def start_minimal_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /start command with minimal menu interface.

    Args:
        update: Telegram update object
        context: Callback context

    Returns:
        None (sends welcome message with keyboard)
    """
    user = update.effective_user
    if not user:
        return

    if not update.message:
        return

    add_command_breadcrumb(
        command="/start",
        user_id=user.id,
        username=user.username or "",
        chat_id=update.message.chat_id,
    )

    logger.info("start_minimal_command", user_id=user.id, username=user.username)

    welcome_text = (
        f"👋 <b>Welcome, {user.first_name}!</b>\n\n"
        f"I'm your DMarket Arbitrage Bot - your automated trading assistant "
        f"for CS:GO, Dota 2, TF2, and Rust items.\n\n"
        f"<b>What I can do:</b>\n\n"
        f"🤖 <b>Automatic Arbitrage</b>\n"
        f"   Scan all games for profitable opportunities\n"
        f"   Choose from 5 trading modes (Boost to Pro)\n\n"
        f"📦 <b>View Items</b>\n"
        f"   See your sold items with real profit\n"
        f"   Track active listings with estimates\n\n"
        f"⚙️ <b>DetAlgoled Settings</b>\n"
        f"   Configure price ranges and margins\n"
        f"   Customize your trading strategy\n\n"
        f"🔌 <b>API Check</b>\n"
        f"   Test DMarket API connectivity\n"
        f"   Verify your balance instantly\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Quick Start:</b>\n"
        f"1️⃣ Tap 🤖 Automatic Arbitrage\n"
        f"2️⃣ Select your preferred mode\n"
        f"3️⃣ WAlgot for scan results\n"
        f"4️⃣ Start trading! 🚀\n\n"
        f"<i>All scans include automatic API health checks.</i>\n"
        f"<i>Use /help for more commands and information.</i>"
    )

    awAlgot update.message.reply_text(
        welcome_text,
        reply_markup=get_mAlgon_keyboard(),
        parse_mode="HTML",
    )

    logger.info("start_minimal_sent", user_id=user.id)
