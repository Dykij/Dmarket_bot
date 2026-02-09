"""Knowledge Base Telegram Handler.

This module provides Telegram bot commands for interacting with
the user's knowledge base system.

Commands:
    /knowledge - Show knowledge base summary
    /knowledge_list - List recent knowledge entries
    /knowledge_clear - Clear all knowledge

Created: January 2026
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from src.utils.knowledge_base import (
    KnowledgeType,
    get_knowledge_base,
)

if TYPE_CHECKING:
    from telegram.ext import Application

logger = structlog.get_logger(__name__)


# ============================================================================
# Command Handlers
# ============================================================================


async def knowledge_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /knowledge command - show knowledge base summary.

    Args:
        update: Telegram update
        context: Bot context
    """
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    logger.info("knowledge_command", user_id=user_id)

    try:
        kb = get_knowledge_base(user_id)
        summary = await kb.get_summary()

        # Build summary message
        type_lines = []
        for ktype, count in summary.get("by_type", {}).items():
            emoji = _get_type_emoji(ktype)
            type_lines.append(f"  {emoji} {ktype}: {count}")

        type_text = "\n".join(type_lines) if type_lines else "  📭 No entries yet"

        message = (
            "📚 **Your Knowledge Base**\n\n"
            f"📊 **Summary**\n"
            f"  • Total entries: {summary['total_entries']}\n"
            f"  • Average relevance: {summary['avg_relevance']:.1%}\n"
            f"  • Total queries: {summary['total_queries']}\n\n"
            f"📁 **By Type:**\n{type_text}\n\n"
            "_Your knowledge base automatically learns from your trades "
            "and helps personalize recommendations._"
        )

        keyboard = _build_knowledge_keyboard()

        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.exception("knowledge_command_failed", user_id=user_id, error=str(e))
        await update.message.reply_text(
            "❌ Failed to load knowledge base. Please try again later."
        )


async def knowledge_list_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /knowledge_list command - list recent knowledge entries.

    Args:
        update: Telegram update
        context: Bot context
    """
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    logger.info("knowledge_list_command", user_id=user_id)

    try:
        kb = get_knowledge_base(user_id)

        # Get recent entries
        entries = await kb.query_relevant(
            context={},  # Empty context to get all
            min_relevance=0.0,
            limit=10,
        )

        if not entries:
            await update.message.reply_text(
                "📭 Your knowledge base is empty.\n\n"
                "Complete some trades to start building your trading knowledge!"
            )
            return

        # Build list message
        lines = ["📋 **Recent Knowledge Entries**\n"]

        for i, entry in enumerate(entries, 1):
            emoji = _get_type_emoji(entry.knowledge_type.value)
            relevance = f"{entry.relevance_score:.0%}"
            game = f" [{entry.game}]" if entry.game else ""

            lines.append(
                f"{i}. {emoji} **{entry.title[:40]}**{game}\n"
                f"   Relevance: {relevance} | Uses: {entry.use_count}"
            )

        message = "\n".join(lines)

        await update.message.reply_text(
            message,
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.exception("knowledge_list_failed", user_id=user_id, error=str(e))
        await update.message.reply_text(
            "❌ Failed to list knowledge entries. Please try again later."
        )


async def knowledge_clear_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /knowledge_clear command - confirm before clearing.

    Args:
        update: Telegram update
        context: Bot context
    """
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    logger.info("knowledge_clear_command", user_id=user_id)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, clear all", callback_data="kb_clear_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="kb_clear_cancel"),
        ]
    ])

    await update.message.reply_text(
        "⚠️ **Are you sure you want to clear your knowledge base?**\n\n"
        "This will remove all accumulated trading knowledge, patterns, "
        "and lessons learned. This action cannot be undone.",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ============================================================================
# Callback Handlers
# ============================================================================


async def knowledge_callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle knowledge base callbacks.

    Args:
        update: Telegram update
        context: Bot context
    """
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return

    await query.answer()

    user_id = update.effective_user.id
    data = query.data

    logger.info("knowledge_callback", user_id=user_id, data=data)

    try:
        if data == "kb_clear_ask":
            await _handle_clear_ask(query)

        elif data == "kb_clear_confirm":
            await _handle_clear_confirm(query, user_id)

        elif data == "kb_clear_cancel":
            await query.edit_message_text("❌ Operation cancelled.")

        elif data == "kb_view_patterns":
            await _handle_view_patterns(query, user_id)

        elif data == "kb_view_lessons":
            await _handle_view_lessons(query, user_id)

        elif data == "kb_decay":
            await _handle_decay(query, user_id)

        elif data == "kb_back":
            await _handle_back_to_summary(query, user_id)

    except Exception as e:
        logger.exception("knowledge_callback_failed", user_id=user_id, error=str(e))
        await query.edit_message_text(
            "❌ An error occurred. Please try again."
        )


async def _handle_clear_ask(query) -> None:
    """Handle clear confirmation request."""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, clear all", callback_data="kb_clear_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="kb_clear_cancel"),
        ]
    ])

    await query.edit_message_text(
        "⚠️ **Are you sure you want to clear your knowledge base?**\n\n"
        "This will remove all accumulated trading knowledge, patterns, "
        "and lessons learned. This action cannot be undone.",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def _handle_clear_confirm(query, user_id: int) -> None:
    """Handle clear confirmation."""
    kb = get_knowledge_base(user_id)
    count = await kb.clear()

    await query.edit_message_text(
        f"✅ Knowledge base cleared.\n\n"
        f"Removed {count} entries."
    )


async def _handle_view_patterns(query, user_id: int) -> None:
    """Handle view patterns callback."""
    kb = get_knowledge_base(user_id)

    entries = await kb.query_relevant(
        context={},
        min_relevance=0.0,
        limit=10,
        knowledge_types=[KnowledgeType.TRADING_PATTERN],
    )

    if not entries:
        await query.edit_message_text(
            "📭 No trading patterns recorded yet.\n\n"
            "Complete profitable trades to start building patterns!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Back", callback_data="kb_back")
            ]]),
        )
        return

    lines = ["📈 **Trading Patterns**\n"]

    for entry in entries:
        content = entry.content
        profit = content.get("profit_percent", 0)
        item = content.get("item_name", "Unknown")

        lines.append(
            f"• **{item[:30]}**\n"
            f"  Profit: {profit:.1f}% | Relevance: {entry.relevance_score:.0%}"
        )

    message = "\n".join(lines)

    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Back", callback_data="kb_back")
        ]]),
    )


async def _handle_view_lessons(query, user_id: int) -> None:
    """Handle view lessons callback."""
    kb = get_knowledge_base(user_id)

    entries = await kb.query_relevant(
        context={},
        min_relevance=0.0,
        limit=10,
        knowledge_types=[KnowledgeType.LESSON_LEARNED],
    )

    if not entries:
        await query.edit_message_text(
            "📭 No lessons recorded yet.\n\n"
            "Lessons are learned from unsuccessful trades to help avoid future mistakes.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Back", callback_data="kb_back")
            ]]),
        )
        return

    lines = ["📝 **Lessons Learned**\n"]

    for entry in entries:
        content = entry.content
        item = content.get("item_name", "Unknown")
        severity = content.get("severity", "medium")
        loss = content.get("loss_percent", 0)

        severity_emoji = {"low": "🟡", "medium": "🟠", "high": "🔴"}.get(severity, "⚪")

        lines.append(
            f"{severity_emoji} **{item[:30]}**\n"
            f"  Loss: {loss:.1f}% | {content.get('lesson', 'N/A')[:40]}"
        )

    message = "\n".join(lines)

    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Back", callback_data="kb_back")
        ]]),
    )


async def _handle_decay(query, user_id: int) -> None:
    """Handle decay callback - apply relevance decay."""
    kb = get_knowledge_base(user_id)
    removed = await kb.decay_relevance()

    await query.edit_message_text(
        f"✅ Relevance decay applied.\n\n"
        f"Removed {removed} stale entries.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Back", callback_data="kb_back")
        ]]),
    )


async def _handle_back_to_summary(query, user_id: int) -> None:
    """Handle back to summary callback."""
    kb = get_knowledge_base(user_id)
    summary = await kb.get_summary()

    type_lines = []
    for ktype, count in summary.get("by_type", {}).items():
        emoji = _get_type_emoji(ktype)
        type_lines.append(f"  {emoji} {ktype}: {count}")

    type_text = "\n".join(type_lines) if type_lines else "  📭 No entries yet"

    message = (
        "📚 **Your Knowledge Base**\n\n"
        f"📊 **Summary**\n"
        f"  • Total entries: {summary['total_entries']}\n"
        f"  • Average relevance: {summary['avg_relevance']:.1%}\n"
        f"  • Total queries: {summary['total_queries']}\n\n"
        f"📁 **By Type:**\n{type_text}"
    )

    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=_build_knowledge_keyboard(),
    )


# ============================================================================
# Helper Functions
# ============================================================================


def _get_type_emoji(knowledge_type: str) -> str:
    """Get emoji for knowledge type."""
    emoji_map = {
        "user_preference": "⚙️",
        "trading_pattern": "📈",
        "lesson_learned": "📝",
        "market_insight": "💡",
        "price_anomaly": "⚠️",
        "item_knowledge": "📦",
        "timing_pattern": "⏰",
    }
    return emoji_map.get(knowledge_type, "📌")


def _build_knowledge_keyboard() -> InlineKeyboardMarkup:
    """Build knowledge base keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📈 Patterns", callback_data="kb_view_patterns"),
            InlineKeyboardButton("📝 Lessons", callback_data="kb_view_lessons"),
        ],
        [
            InlineKeyboardButton("🧹 Apply Decay", callback_data="kb_decay"),
            InlineKeyboardButton("🗑️ Clear All", callback_data="kb_clear_ask"),
        ],
    ])


# ============================================================================
# Registration
# ============================================================================


def register_handlers(application: Application) -> None:
    """Register knowledge base handlers.

    Args:
        application: Telegram bot application
    """
    # Command handlers
    application.add_handler(CommandHandler("knowledge", knowledge_command))
    application.add_handler(CommandHandler("knowledge_list", knowledge_list_command))
    application.add_handler(CommandHandler("knowledge_clear", knowledge_clear_command))

    # Callback handler
    application.add_handler(
        CallbackQueryHandler(knowledge_callback_handler, pattern=r"^kb_")
    )

    logger.info("knowledge_handlers_registered")
