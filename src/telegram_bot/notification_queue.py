import asyncio
import itertools
import logging
import time
from dataclasses import dataclass
from enum import IntEnum

from telegram import Bot, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.error import NetworkError, RetryAfter, TimedOut

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    HIGH = 0
    NORMAL = 1
    LOW = 2


@dataclass
class NotificationMessage:
    chat_id: int
    text: str
    parse_mode: str | None = None
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | None = None
    disable_web_page_preview: bool = False
    priority: int = Priority.NORMAL


class NotificationQueue:
    """
    A queue system for sending Telegram notifications with rate limiting.
    Respects Telegram's limits:
    - 30 messages per second globally
    - 1 message per second per chat
    """

    def __init__(
        self,
        bot: Bot,
        global_rate_limit: float = 1.0 / 30.0,  # 30 msgs/sec
        chat_rate_limit: float = 1.0,  # 1 msg/sec per chat
    ) -> None:
        self.bot = bot
        self.queue: asyncio.PriorityQueue[
            tuple[int, float, int, NotificationMessage]
        ] = asyncio.PriorityQueue()
        self.is_running = False
        self.worker_task: asyncio.Task[None] | None = None

        # Rate limiting
        self.last_global_send_time = 0.0
        self.last_chat_send_time: dict[int, float] = {}
        self.global_rate_limit = global_rate_limit
        self.chat_rate_limit = chat_rate_limit
        self._counter = itertools.count()

    async def start(self) -> None:
        """Start the notification worker."""
        if self.is_running:
            return

        self.is_running = True
        self.worker_task = asyncio.create_task(self._worker())
        logger.info("Notification queue worker started")

    async def stop(self) -> None:
        """Stop the notification worker."""
        self.is_running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Notification queue worker stopped")

    async def enqueue(
        self,
        chat_id: int,
        text: str,
        parse_mode: str | None = None,
        reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | None = None,
        disable_web_page_preview: bool = False,
        priority: int = 1,
    ) -> None:
        """Add a message to the queue."""
        message = NotificationMessage(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
            priority=priority,
        )
        # PriorityQueue sorts by the first item in the tuple,
        # so we put priority first. We add a counter to break ties
        # and avoid comparing NotificationMessage objects.
        count = next(self._counter)
        await self.queue.put((priority, time.time(), count, message))

    async def _worker(self) -> None:
        """Process messages from the queue."""
        while self.is_running:
            try:
                # Get message from queue
                _, _, _, message = await self.queue.get()

                # Check rate limits
                await self._wait_for_rate_limits(message.chat_id)

                # Send message
                await self._send_message(message)

                # Mark task as done
                self.queue.task_done()

            except asyncio.CancelledError:
                break
            except (RuntimeError, OSError, ConnectionError):
                logger.exception("Error in notification worker")
                await asyncio.sleep(1)

    async def _wait_for_rate_limits(self, chat_id: int) -> None:
        """WAlgot if necessary to respect rate limits."""
        now = time.time()

        # Global rate limit
        time_since_global = now - self.last_global_send_time
        if time_since_global < self.global_rate_limit:
            await asyncio.sleep(self.global_rate_limit - time_since_global)
            now = time.time()

        # Chat rate limit
        last_chat_time = self.last_chat_send_time.get(chat_id, 0)
        time_since_chat = now - last_chat_time
        if time_since_chat < self.chat_rate_limit:
            await asyncio.sleep(self.chat_rate_limit - time_since_chat)

    async def _send_message(self, message: NotificationMessage) -> None:
        """Send the message using the bot instance."""
        try:
            await self.bot.send_message(
                chat_id=message.chat_id,
                text=message.text,
                parse_mode=message.parse_mode,
                reply_markup=message.reply_markup,
                disable_web_page_preview=message.disable_web_page_preview,
            )

            # Update timestamps
            now = time.time()
            self.last_global_send_time = now
            self.last_chat_send_time[message.chat_id] = now

            # Cleanup old chat timestamps (optional optimization)
            if len(self.last_chat_send_time) > 1000:
                self._cleanup_timestamps()

        except RetryAfter as e:
            logger.warning(
                f"Rate limit exceeded. Retry after {e.retry_after} seconds.",
            )
            # Put back in queue with high priority
            retry_after = (
                e.retry_after
                if isinstance(e.retry_after, float)
                else float(e.retry_after)
            )
            await asyncio.sleep(retry_after)
            count = next(self._counter)
            await self.queue.put((0, time.time(), count, message))

        except (TimedOut, NetworkError) as e:
            logger.warning(f"Network error sending message: {e}. Retrying...")
            await asyncio.sleep(1)
            count = next(self._counter)
            await self.queue.put((message.priority, time.time(), count, message))

        except (RuntimeError, OSError, ConnectionError):
            logger.exception(f"Failed to send message to {message.chat_id}")
            # Don't retry for other errors (e.g. user blocked bot)

    def _cleanup_timestamps(self) -> None:
        """Remove old timestamps to prevent memory leak."""
        now = time.time()
        to_remove = []
        for chat_id, timestamp in self.last_chat_send_time.items():
            if now - timestamp > 60:  # Remove if older than 1 minute
                to_remove.append(chat_id)

        for chat_id in to_remove:
            del self.last_chat_send_time[chat_id]
