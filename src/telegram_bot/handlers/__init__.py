"""Knowledge handler for Telegram bot."""
from typing import Any


async def knowledge_command(update: Any, context: Any) -> Any:
    """Handle /knowledge command."""
    await update.message.reply_text("Knowledge base feature coming soon.")


def register_handlers(app: Any) -> None:
    """Register knowledge-related handlers."""
    from telegram.ext import CommandHandler
    app.add_handler(CommandHandler("knowledge", knowledge_command))
    app.add_handler(CommandHandler("learn", knowledge_command))
    app.add_handler(CommandHandler("patterns", knowledge_command))
