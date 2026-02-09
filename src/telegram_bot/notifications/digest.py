"""Notification Digest module for grouping and batching notifications.

Reduces notification spam by grouping multiple notifications into a single digest.

Features:
- Configurable buffering (time-based and size-based)
- Automatic flush on critical notifications
- Grouping by category (Arbitrage, Targets, Alerts)
- Markdown formatting with priorities
- Background task for periodic flush

Examples:
    >>> from src.telegram_bot.notifications.digest import NotificationDigest
    >>> digest = NotificationDigest(interval_minutes=15, max_buffer_size=10)
    >>>
    >>> # Add notifications
    >>> await digest.add(notification1)
    >>> await digest.add(notification2)
    >>>
    >>> # Manual flush
    >>> await digest.flush()
    >>>
    >>> # Start background flushing
    >>> await digest.start()
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class NotificationPriority(StrEnum):
    """Notification priority levels."""

    CRITICAL = "critical"  # Instant send
    HIGH = "high"  # Buffer but send soon
    NORMAL = "normal"  # Normal buffering
    LOW = "low"  # Aggressive buffering


class NotificationCategory(StrEnum):
    """Notification categories for grouping."""

    ARBITRAGE = "arbitrage"
    TARGETS = "targets"
    ALERTS = "alerts"
    SYSTEM = "system"
    TRADES = "trades"


class Notification:
    """Single notification object.

    Attributes:
        category: Notification category
        priority: Notification priority
        message: Notification text
        data: Additional data (profit, item_id, etc.)
        timestamp: When notification was created
    """

    def __init__(
        self,
        category: NotificationCategory,
        priority: NotificationPriority,
        message: str,
        data: dict[str, Any] | None = None,
    ):
        """Initialize notification.

        Args:
            category: Notification category
            priority: Priority level
            message: Notification text
            data: Additional metadata
        """
        self.category = category
        self.priority = priority
        self.message = message
        self.data = data or {}
        self.timestamp = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "priority": self.priority.value,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


class NotificationDigest:
    """Notification digest manager with buffering and grouping.

    Reduces spam by grouping multiple notifications into digests.

    Attributes:
        interval_minutes: Flush interval in minutes
        max_buffer_size: Max notifications before auto-flush
        buffer: Current notification buffer
        last_flush: Last flush timestamp
        running: Background task status
    """

    def __init__(
        self,
        interval_minutes: int = 15,
        max_buffer_size: int = 10,
        flush_on_critical: bool = True,
    ):
        """Initialize notification digest.

        Args:
            interval_minutes: Time interval for flush (default: 15)
            max_buffer_size: Max buffer size before flush (default: 10)
            flush_on_critical: Send critical notifications immediately (default: True)
        """
        self.interval_minutes = interval_minutes
        self.max_buffer_size = max_buffer_size
        self.flush_on_critical = flush_on_critical

        self.buffer: list[Notification] = []
        self.last_flush = datetime.now()
        self.running = False
        self._task: asyncio.Task | None = None
        self._send_callback: Any = None

        logger.info(
            "notification_digest_initialized",
            interval_minutes=interval_minutes,
            max_buffer_size=max_buffer_size,
        )

    def set_send_callback(self, callback: Any) -> None:
        """Set callback function for sending digests.

        Args:
            callback: Async function(user_id, message) to send digest
        """
        self._send_callback = callback

    async def add(self, notification: Notification, user_id: int) -> bool:
        """Add notification to buffer.

        Args:
            notification: Notification to add
            user_id: Target user ID

        Returns:
            True if added to buffer, False if sent immediately
        """
        # Critical notifications bypass buffer
        if self.flush_on_critical and notification.priority == NotificationPriority.CRITICAL:
            if self._send_callback:
                await self._send_callback(user_id, notification.message)
                logger.info(
                    "critical_notification_sent_immediately",
                    user_id=user_id,
                    category=notification.category.value,
                )
            return False

        # Add to buffer
        self.buffer.append(notification)
        logger.debug(
            "notification_added_to_buffer",
            buffer_size=len(self.buffer),
            category=notification.category.value,
        )

        # Check if buffer is full
        if len(self.buffer) >= self.max_buffer_size:
            await self.flush(user_id)
            return True

        return True

    async def flush(self, user_id: int) -> int:
        """Flush buffer and send digest.

        Args:
            user_id: Target user ID

        Returns:
            Number of notifications flushed
        """
        if not self.buffer:
            return 0

        # Group notifications by category
        grouped = self._group_by_category()

        # Format digest message
        digest_message = self._format_digest(grouped)

        # Send digest
        if self._send_callback:
            await self._send_callback(user_id, digest_message)

        # Clear buffer
        count = len(self.buffer)
        self.buffer.clear()
        self.last_flush = datetime.now()

        logger.info(
            "digest_flushed",
            user_id=user_id,
            notification_count=count,
            categories=list(grouped.keys()),
        )

        return count

    def _group_by_category(self) -> dict[str, list[Notification]]:
        """Group notifications by category.

        Returns:
            Dictionary of category -> [notifications]
        """
        grouped: dict[str, list[Notification]] = defaultdict(list)

        for notification in self.buffer:
            grouped[notification.category.value].append(notification)

        return grouped

    def _format_digest(self, grouped: dict[str, list[Notification]]) -> str:
        """Format digest message in Markdown.

        Args:
            grouped: Grouped notifications

        Returns:
            Formatted Markdown message
        """
        lines = ["📬 **Дайджест уведомлений**\n"]

        # Arbitrage section
        if "arbitrage" in grouped:
            arb_notifs = grouped["arbitrage"]
            lines.append(f"💰 **Арбитраж** ({len(arb_notifs)} возможностей):")

            # Show top 3 by profit
            sorted_arb = sorted(
                arb_notifs,
                key=lambda n: n.data.get("profit", 0),
                reverse=True,
            )[:3]

            for notif in sorted_arb:
                profit = notif.data.get("profit", 0)
                item = notif.data.get("item", "Unknown")
                lines.append(f"  • {item}: +${profit:.2f}")

            if len(arb_notifs) > 3:
                lines.append(f"  ... и ещё {len(arb_notifs) - 3}")

            lines.append("")

        # Targets section
        if "targets" in grouped:
            target_notifs = grouped["targets"]
            lines.append(f"🎯 **Таргеты** ({len(target_notifs)} событий):")

            for notif in target_notifs[:5]:  # Show max 5
                lines.append(f"  • {notif.message}")

            if len(target_notifs) > 5:
                lines.append(f"  ... и ещё {len(target_notifs) - 5}")

            lines.append("")

        # Alerts section
        if "alerts" in grouped:
            alert_notifs = grouped["alerts"]
            lines.append(f"⚠️ **Алерты** ({len(alert_notifs)}):")

            for notif in alert_notifs:
                lines.append(f"  • {notif.message}")

            lines.append("")

        # System section
        if "system" in grouped:
            system_notifs = grouped["system"]
            lines.append(f"🔔 **Система** ({len(system_notifs)}):")

            for notif in system_notifs:
                lines.append(f"  • {notif.message}")

            lines.append("")

        # Footer
        lines.extend((
            f"_Всего: {len(self.buffer)} уведомлений_",
            f"_Период: {self.interval_minutes} минут_",
        ))

        return "\n".join(lines)

    async def start(self, user_id: int) -> None:
        """Start background flush task.

        Args:
            user_id: Target user ID
        """
        if self.running:
            logger.warning("digest_already_running")
            return

        self.running = True
        self._task = asyncio.create_task(self._background_flush(user_id))

        logger.info(
            "digest_background_task_started",
            interval_minutes=self.interval_minutes,
        )

    async def stop(self) -> None:
        """Stop background flush task."""
        self.running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("digest_background_task_stopped")

    async def _background_flush(self, user_id: int) -> None:
        """Background task for periodic flush.

        Args:
            user_id: Target user ID
        """
        while self.running:
            await asyncio.sleep(self.interval_minutes * 60)

            if self.buffer:
                await self.flush(user_id)

    def should_flush(self) -> bool:
        """Check if digest should be flushed.

        Returns:
            True if flush is needed
        """
        # Check buffer size
        if len(self.buffer) >= self.max_buffer_size:
            return True

        # Check time interval
        elapsed = datetime.now() - self.last_flush
        return elapsed >= timedelta(minutes=self.interval_minutes)

    def get_stats(self) -> dict[str, Any]:
        """Get digest statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "buffer_size": len(self.buffer),
            "interval_minutes": self.interval_minutes,
            "max_buffer_size": self.max_buffer_size,
            "last_flush": self.last_flush.isoformat(),
            "running": self.running,
            "time_since_flush": (datetime.now() - self.last_flush).total_seconds(),
        }
