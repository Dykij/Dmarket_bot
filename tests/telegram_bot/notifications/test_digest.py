"""Tests for notification digest module.

Tests buffering, grouping, and flushing of notifications.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from src.telegram_bot.notifications.digest import (
    Notification,
    NotificationCategory,
    NotificationDigest,
    NotificationPriority,
)


class TestNotification:
    """Tests for Notification class."""

    def test_notification_initialization(self):
        """Test notification creation."""
        # Arrange & Act
        notif = Notification(
            category=NotificationCategory.ARBITRAGE,
            priority=NotificationPriority.NORMAL,
            message="Test arbitrage opportunity",
            data={"profit": 5.50, "item": "AK-47"},
        )

        # Assert
        assert notif.category == NotificationCategory.ARBITRAGE
        assert notif.priority == NotificationPriority.NORMAL
        assert notif.message == "Test arbitrage opportunity"
        assert notif.data["profit"] == 5.50
        assert notif.data["item"] == "AK-47"
        assert isinstance(notif.timestamp, datetime)

    def test_notification_to_dict(self):
        """Test notification serialization."""
        # Arrange
        notif = Notification(
            category=NotificationCategory.TARGETS,
            priority=NotificationPriority.HIGH,
            message="Target filled",
        )

        # Act
        result = notif.to_dict()

        # Assert
        assert result["category"] == "targets"
        assert result["priority"] == "high"
        assert result["message"] == "Target filled"
        assert "timestamp" in result


class TestNotificationDigest:
    """Tests for NotificationDigest class."""

    def test_digest_initialization(self):
        """Test digest initialization with default parameters."""
        # Arrange & Act
        digest = NotificationDigest(interval_minutes=15, max_buffer_size=10)

        # Assert
        assert digest.interval_minutes == 15
        assert digest.max_buffer_size == 10
        assert len(digest.buffer) == 0
        assert digest.running is False

    @pytest.mark.asyncio()
    async def test_add_normal_notification_to_buffer(self):
        """Test adding normal priority notification to buffer."""
        # Arrange
        digest = NotificationDigest()
        notif = Notification(
            category=NotificationCategory.ARBITRAGE,
            priority=NotificationPriority.NORMAL,
            message="Normal notification",
        )

        # Act
        result = await digest.add(notif, user_id=123)

        # Assert
        assert result is True  # Added to buffer
        assert len(digest.buffer) == 1
        assert digest.buffer[0] == notif

    @pytest.mark.asyncio()
    async def test_critical_notification_sent_immediately(self):
        """Test critical notifications bypass buffer."""
        # Arrange
        digest = NotificationDigest(flush_on_critical=True)
        send_callback = AsyncMock()
        digest.set_send_callback(send_callback)

        notif = Notification(
            category=NotificationCategory.ALERTS,
            priority=NotificationPriority.CRITICAL,
            message="Critical alert!",
        )

        # Act
        result = await digest.add(notif, user_id=123)

        # Assert
        assert result is False  # Not added to buffer
        assert len(digest.buffer) == 0
        send_callback.assert_called_once_with(123, "Critical alert!")

    @pytest.mark.asyncio()
    async def test_buffer_flush_when_full(self):
        """Test automatic flush when buffer reaches max size."""
        # Arrange
        digest = NotificationDigest(max_buffer_size=3)
        send_callback = AsyncMock()
        digest.set_send_callback(send_callback)

        # Act: Add 3 notifications (triggers flush)
        for i in range(3):
            notif = Notification(
                category=NotificationCategory.ARBITRAGE,
                priority=NotificationPriority.NORMAL,
                message=f"Notification {i}",
            )
            await digest.add(notif, user_id=123)

        # Assert
        assert len(digest.buffer) == 0  # Buffer cleared
        send_callback.assert_called_once()  # Digest sent

    @pytest.mark.asyncio()
    async def test_flush_groups_by_category(self):
        """Test flush groups notifications by category."""
        # Arrange
        digest = NotificationDigest()
        send_callback = AsyncMock()
        digest.set_send_callback(send_callback)

        # Add notifications from different categories
        await digest.add(
            Notification(
                NotificationCategory.ARBITRAGE,
                NotificationPriority.NORMAL,
                "Arb 1",
                data={"profit": 5.0},
            ),
            user_id=123,
        )
        await digest.add(
            Notification(
                NotificationCategory.ARBITRAGE,
                NotificationPriority.NORMAL,
                "Arb 2",
                data={"profit": 10.0},
            ),
            user_id=123,
        )
        await digest.add(
            Notification(
                NotificationCategory.TARGETS,
                NotificationPriority.NORMAL,
                "Target filled",
            ),
            user_id=123,
        )

        # Act
        count = await digest.flush(user_id=123)

        # Assert
        assert count == 3
        assert len(digest.buffer) == 0
        send_callback.assert_called_once()

        # Check formatted message contains both categories
        call_args = send_callback.call_args[0]
        message = call_args[1]
        assert "Арбитраж" in message
        assert "Таргеты" in message

    @pytest.mark.asyncio()
    async def test_flush_shows_top_arbitrage_by_profit(self):
        """Test digest shows top arbitrage opportunities by profit."""
        # Arrange
        digest = NotificationDigest()
        send_callback = AsyncMock()
        digest.set_send_callback(send_callback)

        # Add 5 arbitrage notifications with different profits
        profits = [5.0, 15.0, 8.0, 20.0, 3.0]
        for i, profit in enumerate(profits):
            await digest.add(
                Notification(
                    NotificationCategory.ARBITRAGE,
                    NotificationPriority.NORMAL,
                    f"Arb {i}",
                    data={"profit": profit, "item": f"Item {i}"},
                ),
                user_id=123,
            )

        # Act
        await digest.flush(user_id=123)

        # Assert
        message = send_callback.call_args[0][1]
        # Should show top 3: 20.0, 15.0, 8.0
        assert "20.00" in message
        assert "15.00" in message
        assert "8.00" in message
        # Should show "и ещё 2" for remaining
        assert "ещё 2" in message

    @pytest.mark.asyncio()
    async def test_empty_buffer_flush_returns_zero(self):
        """Test flushing empty buffer returns 0."""
        # Arrange
        digest = NotificationDigest()

        # Act
        count = await digest.flush(user_id=123)

        # Assert
        assert count == 0

    @pytest.mark.asyncio()
    async def test_should_flush_checks_buffer_size(self):
        """Test should_flush returns True when buffer is full."""
        # Arrange
        digest = NotificationDigest(max_buffer_size=3)

        # Act: Add 3 notifications (but prevent auto-flush by not setting callback)
        for i in range(3):
            digest.buffer.append(
                Notification(
                    NotificationCategory.ARBITRAGE,
                    NotificationPriority.NORMAL,
                    f"Test {i}",
                )
            )

        # Assert
        assert digest.should_flush() is True

    def test_should_flush_checks_time_interval(self):
        """Test should_flush returns True after interval passed."""
        # Arrange
        digest = NotificationDigest(interval_minutes=1)

        # Manually set last_flush to past
        digest.last_flush = datetime.now() - timedelta(minutes=2)

        # Act & Assert
        assert digest.should_flush() is True

    def test_get_stats_returns_digest_info(self):
        """Test get_stats returns comprehensive digest statistics."""
        # Arrange
        digest = NotificationDigest(interval_minutes=15, max_buffer_size=10)

        # Add one notification
        notif = Notification(
            NotificationCategory.ARBITRAGE,
            NotificationPriority.NORMAL,
            "Test",
        )
        digest.buffer.append(notif)

        # Act
        stats = digest.get_stats()

        # Assert
        assert stats["buffer_size"] == 1
        assert stats["interval_minutes"] == 15
        assert stats["max_buffer_size"] == 10
        assert stats["running"] is False
        assert "last_flush" in stats
        assert "time_since_flush" in stats

    @pytest.mark.asyncio()
    async def test_background_flush_task(self):
        """Test background flush task periodically flushes buffer."""
        # Arrange
        digest = NotificationDigest(interval_minutes=1)  # 1 minute for fast test
        send_callback = AsyncMock()
        digest.set_send_callback(send_callback)

        # Add notification
        await digest.add(
            Notification(
                NotificationCategory.ARBITRAGE,
                NotificationPriority.NORMAL,
                "Test",
            ),
            user_id=123,
        )

        # Act: Start background task (but don't wait for interval)
        await digest.start(user_id=123)

        # Assert
        assert digest.running is True
        assert digest._task is not None

        # Cleanup
        await digest.stop()
        assert digest.running is False

    @pytest.mark.asyncio()
    async def test_format_digest_with_multiple_categories(self):
        """Test digest formatting with all categories."""
        # Arrange
        digest = NotificationDigest()

        # Add notifications from all categories
        await digest.add(
            Notification(
                NotificationCategory.ARBITRAGE,
                NotificationPriority.NORMAL,
                "Arb 1",
                data={"profit": 5.0, "item": "Item 1"},
            ),
            user_id=123,
        )
        await digest.add(
            Notification(
                NotificationCategory.TARGETS,
                NotificationPriority.NORMAL,
                "Target filled",
            ),
            user_id=123,
        )
        await digest.add(
            Notification(
                NotificationCategory.ALERTS,
                NotificationPriority.HIGH,
                "Price alert triggered",
            ),
            user_id=123,
        )
        await digest.add(
            Notification(
                NotificationCategory.SYSTEM,
                NotificationPriority.NORMAL,
                "System update",
            ),
            user_id=123,
        )

        # Act
        grouped = digest._group_by_category()
        message = digest._format_digest(grouped)

        # Assert
        assert "Дайджест уведомлений" in message
        assert "Арбитраж" in message
        assert "Таргеты" in message
        assert "Алерты" in message
        assert "Система" in message
        assert "Всего: 4 уведомлений" in message

    @pytest.mark.asyncio()
    async def test_stop_cancels_running_task(self):
        """Test stop method cancels background task."""
        # Arrange
        digest = NotificationDigest()
        await digest.start(user_id=123)
        assert digest.running is True

        # Act
        await digest.stop()

        # Assert
        assert digest.running is False
        # Task should be cancelled (don't check _task directly as it may be None)
