import logging
import asyncio
from typing import Optional
from aiogram import Bot

logger = logging.getLogger("Notifier")


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.bot = Bot(token=token) if token else None
        self.chat_id = chat_id

    async def send_message(self, text: str):
        if not self.bot or not self.chat_id:
            return
        try:
            await self.bot.send_message(
                chat_id=self.chat_id, text=text, parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send TG notification: {e}")

    async def close(self):
        if self.bot:
            await self.bot.session.close()


# Global notifier instance mapping
_notifier: Optional[TelegramNotifier] = None


def init_notifier(token: str, chat_id: str):
    global _notifier
    _notifier = TelegramNotifier(token, chat_id)


def get_notifier() -> TelegramNotifier:
    global _notifier
    if not _notifier:
        return TelegramNotifier("", "")
    return _notifier
