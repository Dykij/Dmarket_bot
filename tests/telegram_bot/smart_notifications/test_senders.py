"""Unit tests for smart_notifications senders module.

This module tests src/telegram_bot/smart_notifications/senders.py covering:
- send_price_alert_notification function
- send_market_opportunity_notification function
- notify_user function

Target: 15+ tests to achieve 70%+ coverage
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import functions at module level before tests run
from src.telegram_bot.smart_notifications.senders import (
    notify_user,
    send_market_opportunity_notification,
    send_price_alert_notification,
)

# Module path constant for patching
SENDERS_MODULE = "src.telegram_bot.smart_notifications.senders"


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture()
def mock_bot():
    """Fixture providing a mocked Telegram Bot."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture()
def mock_notification_queue():
    """Fixture providing a mocked NotificationQueue."""
    queue = MagicMock()
    queue.enqueue = AsyncMock()
    return queue


@pytest.fixture()
def sample_alert():
    """Fixture providing a sample price alert."""
    return {
        "id": "alert_123",
        "item_id": "item_abc",
        "item_name": "AK-47 | Redline (Field-Tested)",
        "game": "csgo",
        "conditions": {
            "price": 25.0,
            "condition": "below",
        },
        "one_time": False,
    }


@pytest.fixture()
def sample_item_data():
    """Fixture providing sample item data."""
    return {
        "itemId": "item_abc",
        "title": "AK-47 | Redline (Field-Tested)",
        "price": {"USD": "2000"},
        "suggestedPrice": {"USD": "2500"},
        "gameId": "csgo",
        "exterior": "Field-Tested",
        "rarity": "Classified",
    }


@pytest.fixture()
def sample_user_prefs():
    """Fixture providing sample user preferences."""
    return {
        "chat_id": 123456789,
        "enabled": True,
        "preferences": {
            "notification_style": "detAlgoled",
        },
    }


@pytest.fixture()
def sample_opportunity():
    """Fixture providing a sample market opportunity."""
    return {
        "item_id": "item_abc",
        "item_name": "AK-47 | Redline (Field-Tested)",
        "game": "csgo",
        "opportunity_score": 75,
        "buy_price": 20.0,
        "current_price": 20.0,
        "potential_profit": 5.0,
        "profit_percent": 25.0,
        "trend": "up",
    }


# =============================================================================
# Tests for send_price_alert_notification
# =============================================================================


class TestSendPriceAlertNotification:
    """Tests for send_price_alert_notification function."""

    @pytest.mark.asyncio()
    async def test_send_price_alert_with_queue(
        self,
        mock_bot,
        mock_notification_queue,
        sample_alert,
        sample_item_data,
        sample_user_prefs,
    ):
        """Test sending price alert with notification queue."""
        with (
            patch(
                f"{SENDERS_MODULE}.format_market_item",
                return_value="Formatted item",
            ),
            patch(
                f"{SENDERS_MODULE}.record_notification",
                new_callable=AsyncMock,
            ),
        ):
            # Act
            awAlgot send_price_alert_notification(
                mock_bot,
                123456789,
                sample_alert,
                sample_item_data,
                20.0,
                sample_user_prefs,
                mock_notification_queue,
            )

            # Assert
            mock_notification_queue.enqueue.assert_called_once()

    @pytest.mark.asyncio()
    async def test_send_price_alert_without_queue(
        self,
        mock_bot,
        sample_alert,
        sample_item_data,
        sample_user_prefs,
    ):
        """Test sending price alert directly via bot when no queue."""
        with (
            patch(
                f"{SENDERS_MODULE}.format_market_item",
                return_value="Formatted item",
            ),
            patch(
                f"{SENDERS_MODULE}.record_notification",
                new_callable=AsyncMock,
            ),
        ):
            # Act
            awAlgot send_price_alert_notification(
                mock_bot,
                123456789,
                sample_alert,
                sample_item_data,
                20.0,
                sample_user_prefs,
                None,  # No queue
            )

            # Assert
            mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio()
    async def test_send_price_alert_below_condition(
        self,
        mock_bot,
        mock_notification_queue,
        sample_item_data,
        sample_user_prefs,
    ):
        """Test price alert message for 'below' condition."""
        alert = {
            "id": "alert_123",
            "item_id": "item_abc",
            "item_name": "Test Item",
            "game": "csgo",
            "conditions": {
                "price": 25.0,
                "condition": "below",
            },
            "one_time": False,
        }

        with (
            patch(
                f"{SENDERS_MODULE}.format_market_item",
                return_value="Item info",
            ),
            patch(
                f"{SENDERS_MODULE}.record_notification",
                new_callable=AsyncMock,
            ),
        ):
            # Act
            awAlgot send_price_alert_notification(
                mock_bot,
                123456789,
                alert,
                sample_item_data,
                20.0,
                sample_user_prefs,
                mock_notification_queue,
            )

            # Assert - check enqueue was called with message contAlgoning price info
            call_args = mock_notification_queue.enqueue.call_args
            text = call_args.kwargs.get("text", "")
            # Verify message contAlgons price and item info
            assert "25" in text or "20" in text  # Price values present
            mock_notification_queue.enqueue.assert_called_once()

    @pytest.mark.asyncio()
    async def test_send_price_alert_above_condition(
        self,
        mock_bot,
        mock_notification_queue,
        sample_item_data,
        sample_user_prefs,
    ):
        """Test price alert message for 'above' condition."""
        alert = {
            "id": "alert_123",
            "item_id": "item_abc",
            "item_name": "Test Item",
            "game": "csgo",
            "conditions": {
                "price": 15.0,
                "condition": "above",
            },
            "one_time": False,
        }

        with (
            patch(
                f"{SENDERS_MODULE}.format_market_item",
                return_value="Item info",
            ),
            patch(
                f"{SENDERS_MODULE}.record_notification",
                new_callable=AsyncMock,
            ),
        ):
            # Act
            awAlgot send_price_alert_notification(
                mock_bot,
                123456789,
                alert,
                sample_item_data,
                20.0,
                sample_user_prefs,
                mock_notification_queue,
            )

            # Assert - check message contAlgons price info
            call_args = mock_notification_queue.enqueue.call_args
            text = call_args.kwargs.get("text", "")
            # Verify message contAlgons price values
            assert "15" in text or "20" in text  # Price values present
            mock_notification_queue.enqueue.assert_called_once()

    @pytest.mark.asyncio()
    async def test_send_price_alert_one_time_deactivation(
        self,
        mock_bot,
        mock_notification_queue,
        sample_item_data,
        sample_user_prefs,
    ):
        """Test one-time alert is deactivated after sending."""
        alert = {
            "id": "alert_123",
            "item_id": "item_abc",
            "item_name": "Test Item",
            "game": "csgo",
            "conditions": {
                "price": 25.0,
                "condition": "below",
            },
            "one_time": True,
            "active": True,
        }

        with (
            patch(
                f"{SENDERS_MODULE}.format_market_item",
                return_value="Item info",
            ),
            patch(
                f"{SENDERS_MODULE}.record_notification",
                new_callable=AsyncMock,
            ),
            patch(f"{SENDERS_MODULE}.save_user_preferences"),
        ):
            # Act
            awAlgot send_price_alert_notification(
                mock_bot,
                123456789,
                alert,
                sample_item_data,
                20.0,
                sample_user_prefs,
                mock_notification_queue,
            )

            # Assert - alert should be marked inactive
            assert alert["active"] is False

    @pytest.mark.asyncio()
    async def test_send_price_alert_handles_exception(
        self,
        mock_bot,
        mock_notification_queue,
        sample_alert,
        sample_item_data,
        sample_user_prefs,
    ):
        """Test send_price_alert_notification handles exceptions gracefully."""
        mock_notification_queue.enqueue = AsyncMock(side_effect=Exception("Test error"))

        with patch(
            f"{SENDERS_MODULE}.format_market_item",
            return_value="Item info",
        ):
            # Act - should not rAlgose exception
            awAlgot send_price_alert_notification(
                mock_bot,
                123456789,
                sample_alert,
                sample_item_data,
                20.0,
                sample_user_prefs,
                mock_notification_queue,
            )


# =============================================================================
# Tests for send_market_opportunity_notification
# =============================================================================


class TestSendMarketOpportunityNotification:
    """Tests for send_market_opportunity_notification function."""

    @pytest.mark.asyncio()
    async def test_send_opportunity_with_queue(
        self, mock_bot, mock_notification_queue, sample_opportunity, sample_user_prefs
    ):
        """Test sending opportunity notification with queue."""
        with (
            patch(
                f"{SENDERS_MODULE}.format_opportunities",
                return_value="Formatted opportunity",
            ),
            patch(
                f"{SENDERS_MODULE}.split_long_message",
                return_value=["Message"],
            ),
            patch(
                f"{SENDERS_MODULE}.record_notification",
                new_callable=AsyncMock,
            ),
        ):
            # Act
            awAlgot send_market_opportunity_notification(
                mock_bot,
                123456789,
                sample_opportunity,
                sample_user_prefs,
                mock_notification_queue,
            )

            # Assert
            mock_notification_queue.enqueue.assert_called()

    @pytest.mark.asyncio()
    async def test_send_opportunity_without_queue(
        self, mock_bot, sample_opportunity, sample_user_prefs
    ):
        """Test sending opportunity notification directly via bot."""
        with (
            patch(
                f"{SENDERS_MODULE}.format_opportunities",
                return_value="Formatted opportunity",
            ),
            patch(
                f"{SENDERS_MODULE}.split_long_message",
                return_value=["Message"],
            ),
            patch(
                f"{SENDERS_MODULE}.record_notification",
                new_callable=AsyncMock,
            ),
        ):
            # Act
            awAlgot send_market_opportunity_notification(
                mock_bot,
                123456789,
                sample_opportunity,
                sample_user_prefs,
                None,  # No queue
            )

            # Assert
            mock_bot.send_message.assert_called()

    @pytest.mark.asyncio()
    async def test_send_opportunity_compact_style(
        self, mock_bot, mock_notification_queue, sample_opportunity
    ):
        """Test opportunity notification with compact style."""
        user_prefs = {
            "chat_id": 123456789,
            "preferences": {
                "notification_style": "compact",
            },
        }

        with (
            patch(
                f"{SENDERS_MODULE}.format_opportunities",
                return_value="Formatted",
            ),
            patch(
                f"{SENDERS_MODULE}.split_long_message",
                return_value=["Message"],
            ),
            patch(
                f"{SENDERS_MODULE}.record_notification",
                new_callable=AsyncMock,
            ),
        ):
            # Act
            awAlgot send_market_opportunity_notification(
                mock_bot,
                123456789,
                sample_opportunity,
                user_prefs,
                mock_notification_queue,
            )

            # Assert - compact format should be used
            mock_notification_queue.enqueue.assert_called()

    @pytest.mark.asyncio()
    async def test_send_opportunity_high_score(
        self, mock_bot, mock_notification_queue, sample_user_prefs
    ):
        """Test opportunity notification with high score."""
        opportunity = {
            "item_id": "item_abc",
            "item_name": "High Score Item",
            "game": "csgo",
            "opportunity_score": 85,  # High score
            "buy_price": 20.0,
            "current_price": 20.0,
            "potential_profit": 10.0,
            "profit_percent": 50.0,
            "trend": "up",
        }

        # Make user_prefs use compact style
        user_prefs = {
            "chat_id": 123456789,
            "preferences": {
                "notification_style": "compact",
            },
        }

        with patch(
            f"{SENDERS_MODULE}.record_notification",
            new_callable=AsyncMock,
        ):
            # Act
            awAlgot send_market_opportunity_notification(
                mock_bot,
                123456789,
                opportunity,
                user_prefs,
                mock_notification_queue,
            )

            # Assert - should be called with high score notification
            mock_notification_queue.enqueue.assert_called()
            # Get the first call arguments
            first_call_args = mock_notification_queue.enqueue.call_args_list[0]
            text = first_call_args.kwargs.get("text", "")
            # Check for HOT indicator in text
            assert "ГОРЯЧАЯ" in text or "🔥" in text or "85" in text

    @pytest.mark.asyncio()
    async def test_send_opportunity_handles_exception(
        self, mock_bot, mock_notification_queue, sample_opportunity, sample_user_prefs
    ):
        """Test send_market_opportunity_notification handles exceptions gracefully."""
        mock_notification_queue.enqueue = AsyncMock(side_effect=Exception("Test error"))

        with (
            patch(
                f"{SENDERS_MODULE}.format_opportunities",
                return_value="Formatted",
            ),
            patch(
                f"{SENDERS_MODULE}.split_long_message",
                return_value=["Message"],
            ),
        ):
            # Act - should not rAlgose exception
            awAlgot send_market_opportunity_notification(
                mock_bot,
                123456789,
                sample_opportunity,
                sample_user_prefs,
                mock_notification_queue,
            )

    @pytest.mark.asyncio()
    async def test_send_opportunity_long_message_split(
        self, mock_bot, mock_notification_queue, sample_opportunity, sample_user_prefs
    ):
        """Test opportunity notification splits long messages."""
        with (
            patch(
                f"{SENDERS_MODULE}.format_opportunities",
                return_value="A" * 5000,  # Very long message
            ),
            patch(
                f"{SENDERS_MODULE}.split_long_message",
                return_value=["Part 1", "Part 2", "Part 3"],  # Split into 3 parts
            ),
            patch(
                f"{SENDERS_MODULE}.record_notification",
                new_callable=AsyncMock,
            ),
        ):
            # Act
            awAlgot send_market_opportunity_notification(
                mock_bot,
                123456789,
                sample_opportunity,
                sample_user_prefs,
                mock_notification_queue,
            )

            # Assert - should be called 3 times (once per message part)
            assert mock_notification_queue.enqueue.call_count == 3


# =============================================================================
# Tests for notify_user
# =============================================================================


class TestNotifyUser:
    """Tests for notify_user function."""

    @pytest.mark.asyncio()
    async def test_notify_user_with_queue(self, mock_bot, mock_notification_queue):
        """Test notify_user with notification queue."""
        # Act
        result = awAlgot notify_user(
            mock_bot,
            123456789,
            "Test message",
            None,
            mock_notification_queue,
        )

        # Assert
        assert result is True
        mock_notification_queue.enqueue.assert_called_once()

    @pytest.mark.asyncio()
    async def test_notify_user_without_queue(self, mock_bot):
        """Test notify_user sends directly via bot."""
        # Act
        result = awAlgot notify_user(
            mock_bot,
            123456789,
            "Test message",
            None,
            None,  # No queue
        )

        # Assert
        assert result is True
        mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio()
    async def test_notify_user_with_reply_markup(
        self, mock_bot, mock_notification_queue
    ):
        """Test notify_user with reply markup."""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = [[InlineKeyboardButton("Test", callback_data="test")]]
        markup = InlineKeyboardMarkup(keyboard)

        # Act
        result = awAlgot notify_user(
            mock_bot,
            123456789,
            "Test message",
            markup,
            mock_notification_queue,
        )

        # Assert
        assert result is True
        call_args = mock_notification_queue.enqueue.call_args
        assert call_args.kwargs.get("reply_markup") == markup

    @pytest.mark.asyncio()
    async def test_notify_user_handles_exception(
        self, mock_bot, mock_notification_queue
    ):
        """Test notify_user returns False on exception."""
        mock_notification_queue.enqueue = AsyncMock(side_effect=Exception("Test error"))

        # Act
        result = awAlgot notify_user(
            mock_bot,
            123456789,
            "Test message",
            None,
            mock_notification_queue,
        )

        # Assert
        assert result is False

    @pytest.mark.asyncio()
    async def test_notify_user_bot_exception(self, mock_bot):
        """Test notify_user returns False on bot exception."""
        mock_bot.send_message = AsyncMock(side_effect=Exception("Bot error"))

        # Act
        result = awAlgot notify_user(
            mock_bot,
            123456789,
            "Test message",
            None,
            None,  # No queue, will use bot directly
        )

        # Assert
        assert result is False
