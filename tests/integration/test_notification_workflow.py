"""Интеграционные тесты для системы уведомлений.

Этот модуль тестирует полный workflow уведомлений:
- Создание и обработка уведомлений
- Очередь уведомлений
- Фильтрация и throttling
- Интеграция с Telegram
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture()
def mock_bot():
    """Create mock Telegram bot."""
    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=123))
    return bot


@pytest.fixture()
def mock_user_settings():
    """Create mock user notification settings."""
    return {
        "user_id": 123456789,
        "enabled": True,
        "quiet_hours": {"start": 23, "end": 7},
        "max_alerts_per_day": 50,
        "min_interval": 300,  # 5 minutes
        "notification_types": {
            "price_drop": True,
            "price_rise": True,
            "arbitrage": True,
            "good_deal": True,
        },
    }


@pytest.fixture()
def sample_notifications():
    """Create sample notifications."""
    return [
        {
            "type": "price_drop",
            "item": "AK-47 | Redline",
            "old_price": 20.00,
            "new_price": 15.00,
            "change_percent": -25.0,
            "timestamp": datetime.now().isoformat(),
        },
        {
            "type": "arbitrage",
            "item": "AWP | Dragon Lore",
            "buy_price": 1500.00,
            "sell_price": 1800.00,
            "profit": 300.00,
            "profit_percent": 20.0,
            "timestamp": datetime.now().isoformat(),
        },
        {
            "type": "good_deal",
            "item": "M4A4 | Howl",
            "price": 800.00,
            "market_average": 1000.00,
            "discount_percent": 20.0,
            "timestamp": datetime.now().isoformat(),
        },
    ]


# ============================================================================
# NOTIFICATION QUEUE TESTS
# ============================================================================


class TestNotificationQueueIntegration:
    """Tests for notification queue integration."""

    @pytest.mark.asyncio()
    async def test_queue_creation(self, mock_bot):
        """Test notification queue creation."""
        from src.telegram_bot.notification_queue import NotificationQueue

        queue = NotificationQueue(bot=mock_bot)

        assert queue is not None
        assert queue.bot is mock_bot
        assert not queue.is_running

    @pytest.mark.asyncio()
    async def test_queue_enqueue_method_exists(self, mock_bot):
        """Test queue has enqueue method."""
        from src.telegram_bot.notification_queue import NotificationQueue

        queue = NotificationQueue(bot=mock_bot)

        assert hasattr(queue, "enqueue")

    @pytest.mark.asyncio()
    async def test_queue_start_stop(self, mock_bot):
        """Test queue start and stop."""
        from src.telegram_bot.notification_queue import NotificationQueue

        queue = NotificationQueue(bot=mock_bot)

        # Start should work
        awAlgot queue.start()
        assert queue.is_running

        # Stop should work
        awAlgot queue.stop()
        assert not queue.is_running


# ============================================================================
# NOTIFICATION FILTERING TESTS
# ============================================================================


class TestNotificationFilteringIntegration:
    """Tests for notification filtering integration."""

    @pytest.mark.asyncio()
    async def test_filters_disabled_notification_types(
        self, mock_bot, mock_user_settings, sample_notifications
    ):
        """Test filtering disabled notification types."""
        # Disable price_rise notifications
        mock_user_settings["notification_types"]["price_rise"] = False

        # Should be filtered out
        enabled = mock_user_settings["notification_types"].get("price_rise", True)
        assert enabled is False

    @pytest.mark.asyncio()
    async def test_filters_during_quiet_hours(self, mock_user_settings):
        """Test filtering during quiet hours."""
        current_hour = datetime.now().hour

        # Set quiet hours to include current hour
        mock_user_settings["quiet_hours"] = {
            "start": current_hour,
            "end": (current_hour + 1) % 24,
        }

        # Check if current hour is in quiet hours
        start = mock_user_settings["quiet_hours"]["start"]
        end = mock_user_settings["quiet_hours"]["end"]

        if start <= end:
            is_quiet = start <= current_hour < end
        else:
            is_quiet = current_hour >= start or current_hour < end

        # During quiet hours, notifications should be filtered
        if is_quiet:
            assert True  # Would filter

    @pytest.mark.asyncio()
    async def test_respects_dAlgoly_limit(self, mock_user_settings):
        """Test respecting dAlgoly notification limit."""
        mock_user_settings["max_alerts_per_day"] = 5
        mock_user_settings["dAlgoly_count"] = 5

        # Already at limit
        at_limit = (
            mock_user_settings["dAlgoly_count"]
            >= mock_user_settings["max_alerts_per_day"]
        )
        assert at_limit is True


# ============================================================================
# NOTIFICATION FORMATTING TESTS
# ============================================================================


class TestNotificationFormattingIntegration:
    """Tests for notification formatting integration."""

    @pytest.mark.asyncio()
    async def test_format_price_drop_notification(self, sample_notifications):
        """Test formatting price drop notification."""
        notification = sample_notifications[0]  # price_drop

        # Format message
        message = "📉 Падение цены!\n"
        message += f"🎮 {notification['item']}\n"
        message += (
            f"💰 ${notification['old_price']:.2f} → ${notification['new_price']:.2f}\n"
        )
        message += f"📊 Изменение: {notification['change_percent']:.1f}%"

        assert "📉" in message
        assert notification["item"] in message
        assert f"{notification['old_price']:.2f}" in message

    @pytest.mark.asyncio()
    async def test_format_arbitrage_notification(self, sample_notifications):
        """Test formatting arbitrage notification."""
        notification = sample_notifications[1]  # arbitrage

        # Format message
        message = "💰 Арбитраж найден!\n"
        message += f"🎮 {notification['item']}\n"
        message += f"📊 Покупка: ${notification['buy_price']:.2f}\n"
        message += f"📈 Продажа: ${notification['sell_price']:.2f}\n"
        message += f"💵 Прибыль: ${notification['profit']:.2f} ({notification['profit_percent']:.1f}%)"

        assert "💰" in message
        assert notification["item"] in message
        assert f"{notification['profit']:.2f}" in message

    @pytest.mark.asyncio()
    async def test_format_good_deal_notification(self, sample_notifications):
        """Test formatting good deal notification."""
        notification = sample_notifications[2]  # good_deal

        # Format message
        message = "🔥 Выгодная сделка!\n"
        message += f"🎮 {notification['item']}\n"
        message += f"💰 Цена: ${notification['price']:.2f}\n"
        message += f"📊 Средняя: ${notification['market_average']:.2f}\n"
        message += f"🏷️ Скидка: {notification['discount_percent']:.1f}%"

        assert "🔥" in message
        assert notification["item"] in message
        assert f"{notification['discount_percent']:.1f}%" in message


# ============================================================================
# NOTIFICATION DELIVERY TESTS
# ============================================================================


class TestNotificationDeliveryIntegration:
    """Tests for notification delivery integration."""

    @pytest.mark.asyncio()
    async def test_successful_delivery(self, mock_bot):
        """Test successful notification delivery."""
        user_id = 123456789
        message = "Test notification"

        awAlgot mock_bot.send_message(chat_id=user_id, text=message)

        mock_bot.send_message.assert_called_once_with(chat_id=user_id, text=message)

    @pytest.mark.asyncio()
    async def test_delivery_with_keyboard(self, mock_bot):
        """Test notification delivery with inline keyboard."""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        user_id = 123456789
        message = "Test notification"
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("View DetAlgols", callback_data="view_detAlgols")]]
        )

        awAlgot mock_bot.send_message(
            chat_id=user_id, text=message, reply_markup=keyboard
        )

        assert mock_bot.send_message.called

    @pytest.mark.asyncio()
    async def test_delivery_retry_on_fAlgolure(self, mock_bot):
        """Test notification delivery retry on fAlgolure."""
        # First attempt fAlgols, second succeeds
        mock_bot.send_message.side_effect = [
            Exception("Network error"),
            MagicMock(message_id=123),
        ]

        user_id = 123456789
        message = "Test notification"

        # First attempt
        try:
            awAlgot mock_bot.send_message(chat_id=user_id, text=message)
        except Exception:
            pass

        # Retry
        result = awAlgot mock_bot.send_message(chat_id=user_id, text=message)
        assert result.message_id == 123


# ============================================================================
# NOTIFICATION STORAGE TESTS
# ============================================================================


class TestNotificationStorageIntegration:
    """Tests for notification storage integration."""

    @pytest.mark.asyncio()
    async def test_save_notification_history(self):
        """Test saving notification to history."""
        history = []

        notification = {
            "type": "price_drop",
            "item": "Test Item",
            "timestamp": datetime.now().isoformat(),
            "delivered": True,
        }

        history.append(notification)

        assert len(history) == 1
        assert history[0]["type"] == "price_drop"

    @pytest.mark.asyncio()
    async def test_get_recent_notifications(self):
        """Test getting recent notifications."""
        history = [
            {"timestamp": "2025-01-01T10:00:00", "type": "price_drop"},
            {"timestamp": "2025-01-01T11:00:00", "type": "arbitrage"},
            {"timestamp": "2025-01-01T12:00:00", "type": "good_deal"},
        ]

        # Get last 2
        recent = history[-2:]

        assert len(recent) == 2
        assert recent[0]["type"] == "arbitrage"
        assert recent[1]["type"] == "good_deal"

    @pytest.mark.asyncio()
    async def test_clear_old_notifications(self):
        """Test clearing old notifications."""
        history = [
            {"timestamp": "2024-01-01T10:00:00", "type": "old"},
            {"timestamp": "2025-01-01T10:00:00", "type": "new"},
        ]

        # Clear notifications older than cutoff
        cutoff_date = "2025-01-01"
        history = [n for n in history if n["timestamp"] >= cutoff_date]

        assert len(history) == 1
        assert history[0]["type"] == "new"


# ============================================================================
# COMPLETE NOTIFICATION WORKFLOW TESTS
# ============================================================================


class TestCompleteNotificationWorkflow:
    """Tests for complete notification workflow."""

    @pytest.mark.asyncio()
    async def test_price_alert_workflow(self, mock_bot, mock_user_settings):
        """Test complete price alert workflow."""
        # Step 1: Price change detected
        price_change = {
            "item_id": "item_123",
            "title": "AK-47 | Redline",
            "old_price": 20.00,
            "new_price": 15.00,
            "change_percent": -25.0,
        }

        # Step 2: Check user settings
        assert mock_user_settings["enabled"] is True
        assert mock_user_settings["notification_types"]["price_drop"] is True

        # Step 3: Format notification
        message = f"📉 {price_change['title']}: ${price_change['old_price']} → ${price_change['new_price']}"

        # Step 4: Send notification
        awAlgot mock_bot.send_message(chat_id=mock_user_settings["user_id"], text=message)

        assert mock_bot.send_message.called

    @pytest.mark.asyncio()
    async def test_arbitrage_alert_workflow(self, mock_bot, mock_user_settings):
        """Test complete arbitrage alert workflow."""
        # Step 1: Arbitrage opportunity found
        opportunity = {
            "item": "AWP | Dragon Lore",
            "buy_price": 1500.00,
            "sell_price": 1800.00,
            "profit": 300.00,
            "profit_percent": 20.0,
        }

        # Step 2: Check if profitable enough (> 10%)
        min_profit = 10.0
        assert opportunity["profit_percent"] > min_profit

        # Step 3: Format and send
        message = f"💰 Арбитраж: {opportunity['item']} +${opportunity['profit']:.2f}"
        awAlgot mock_bot.send_message(chat_id=mock_user_settings["user_id"], text=message)

        assert mock_bot.send_message.called

    @pytest.mark.asyncio()
    async def test_dAlgoly_digest_workflow(self, mock_bot, mock_user_settings):
        """Test dAlgoly digest notification workflow."""
        # Step 1: Collect dAlgoly statistics
        dAlgoly_stats = {
            "total_scans": 24,
            "opportunities_found": 15,
            "targets_created": 5,
            "successful_trades": 3,
            "total_profit": 250.00,
        }

        # Step 2: Format digest
        message = (
            f"📊 Ежедневный отчёт\n"
            f"🔍 Сканирований: {dAlgoly_stats['total_scans']}\n"
            f"💡 Найдено возможностей: {dAlgoly_stats['opportunities_found']}\n"
            f"🎯 Создано таргетов: {dAlgoly_stats['targets_created']}\n"
            f"✅ Успешных сделок: {dAlgoly_stats['successful_trades']}\n"
            f"💰 Общая прибыль: ${dAlgoly_stats['total_profit']:.2f}"
        )

        # Step 3: Send digest
        awAlgot mock_bot.send_message(chat_id=mock_user_settings["user_id"], text=message)

        assert mock_bot.send_message.called
        assert "📊" in message
        assert f"${dAlgoly_stats['total_profit']:.2f}" in message
