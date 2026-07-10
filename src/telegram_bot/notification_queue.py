"""Notification queue."""
from typing import Any


class NotificationQueue:
    def __init__(self, bot: Any) -> None:
        self.bot = bot
        self.is_running = False

    async def enqueue(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def start(self) -> None:
        self.is_running = True

    async def stop(self) -> None:
        self.is_running = False
