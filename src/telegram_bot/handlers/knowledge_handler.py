"""Knowledge handler."""
from typing import Any


async def knowledge_command(update: Any, context: Any) -> Any:
    await update.message.reply_text("Knowledge base feature coming soon.")


def register_handlers(app: Any) -> None:
    try:
        from telegram.ext import CommandHandler
        app.add_handler(CommandHandler("knowledge", knowledge_command))
        app.add_handler(CommandHandler("learn", knowledge_command))
        app.add_handler(CommandHandler("patterns", knowledge_command))
    except ImportError:
        pass
