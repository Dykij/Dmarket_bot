"""Basic commands."""
from typing import Any


async def start_command(update: Any, context: Any) -> None:
    await update.message.reply_text("Welcome to DMarket Bot!")


async def help_command(update: Any, context: Any) -> None:
    await update.message.reply_text("Commands: /start, /help, /balance, /scan")
