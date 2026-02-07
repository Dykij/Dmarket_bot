from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from src.ai.router import AIRouter
from .tools.gemini_wrapper import get_gemini

async def ai_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle regular text messages using the AI Router.
    """
    if not update.message or not update.message.text:
        return

    user_text = update.message.text
    
    # Initialize AI Router with Gemini (wrapper handles Gatekeeper)
    gemini = get_gemini()
    router = AIRouter(gemini)
    
    # Process through AI
    await update.message.reply_chat_action("typing")
    response = await router.process_user_message(user_text)
    
    await update.message.reply_text(response)

# Filter out commands, only handle plain text
ai_router_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), ai_message_handler)
