from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from src.utils.canonical_logging import get_logger

logger = get_logger(__name__)


async def system_status_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show system resource usage and bot status."""
    import os
    import time

    import psutil

    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / 1024 / 1024
    cpu_percent = process.cpu_percent(interval=None)

    text = (
        f"🖥️ <b>SYSTEM STATUS</b>\n\n"
        f"🧠 RAM: <code>{memory_mb:.1f} MB</code>\n"
        f"⚙️ CPU: <code>{cpu_percent:.1f}%</code>\n"
        f"🆔 PID: <code>{os.getpid()}</code>\n"
        f"⏱️ Uptime: <code>{(time.time() - process.create_time()) / 3600:.1f} ч</code>"
    )

    keyboard = [
        [InlineKeyboardButton("♻️ REBOOT BOT", callback_data="system_restart")],
        [InlineKeyboardButton("◀️ MENU", callback_data="main_menu")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text, parse_mode="HTML", reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            text, parse_mode="HTML", reply_markup=reply_markup
        )


async def system_restart_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle manual restart request."""
    import os
    import sys

    query = update.callback_query
    await query.answer("Rebooting...", show_alert=True)

    await query.edit_message_text(
        "♻️ <b>REBOOTING SYSTEM...</b>\n\n"
        "Saving state and restarting process.\n"
        "Please wait 10-15 seconds.",
        parse_mode="HTML",
    )

    logger.warning(f"Manual restart triggered by user {query.from_user.id}")

    # Restart current process
    # sys.executable is the Python interpreter
    # sys.argv are the command line arguments
    os.execv(sys.executable, [sys.executable] + sys.argv)


def register_system_handlers(application):
    """Register system handlers."""
    application.add_handler(CommandHandler("status", system_status_command))
    application.add_handler(
        CallbackQueryHandler(system_status_command, pattern="^system_status$")
    )
    application.add_handler(
        CallbackQueryHandler(system_restart_callback, pattern="^system_restart$")
    )
    logger.info("System handlers registered")
