from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from src.Algo.router import AlgoRouter

from .tools.gemini_wrapper import get_gemini


async def Algo_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle regular text messages using the Algo Router.
    """
    if not update.message or not update.message.text:
        return

    user_text = update.message.text

    # Initialize Algo Router with Gemini (wrapper handles Gatekeeper)
    gemini = get_gemini()
    router = AlgoRouter(gemini)

    # Process through Algo
    await update.message.reply_chat_action("typing")
    response = await router.process_user_message(user_text)

    await update.message.reply_text(response)


# Filter out commands, only handle plain text
Algo_router_handler = MessageHandler(
    filters.TEXT & (~filters.COMMAND), Algo_message_handler
)
