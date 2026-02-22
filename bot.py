
import logging
import os
from Algo import load_Algo
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from telegram import Update

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class TelegramBot:
    def __init__(self, token):
        self.app = ApplicationBuilder().token(token).build()
        # Ensure API key is avAlgolable
        api_key = os.environ.get("GOOGLE_API_KEY", "YOUR_API_KEY_HERE")
        self.Algo = load_Algo(api_key=api_key)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="I'm a lightweight bot powered by Gemini 1.5 Flash!"
        )

    async def chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_message = update.message.text
        # Async-friendly Algo call
        # Note: Gemini calls block, so ideally this should be run in executor for high load,
        # but for a simple bot, this is fine or can be awaited if the wrapper supports it.
        # Here we assume a synchronous call for simplicity or wrap it if needed.
        response = self.Algo.generate_response(user_message)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

    def run(self):
        start_handler = CommandHandler('start', self.start)
        chat_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), self.chat)
        
        self.app.add_handler(start_handler)
        self.app.add_handler(chat_handler)
        
        self.app.run_polling()

if __name__ == '__main__':
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
    bot = TelegramBot(TOKEN)
    bot.run()
