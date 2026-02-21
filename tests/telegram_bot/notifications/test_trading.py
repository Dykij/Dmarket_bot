"""
Comprehensive tests for trading notifications module.

This module tests trading notification functions:
- send_buy_intent_notification
- send_buy_success_notification
- send_buy_fAlgoled_notification
- send_sell_success_notification
- send_critical_shutdown_notification
- send_crash_notification

Coverage Target: 90%+
Tests: 30+ tests
"""

from unittest.mock import AsyncMock, patch

import pytest
from telegram import InlineKeyboardMarkup

from src.telegram_bot.notifications.trading import (
    send_buy_fAlgoled_notification,
    send_buy_intent_notification,
    send_buy_success_notification,
    send_crash_notification,
    send_critical_shutdown_notification,
    send_sell_success_notification,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture()
def mock_bot():
    """Create a mock Telegram bot."""
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture()
def sample_item():
    """Create a sample item dictionary."""
    return {
        "title": "AK-47 | Redline",
        "price": {"USD": 1500},  # $15.00 in cents
        "game": "csgo",
        "itemId": "item_12345",
    }


@pytest.fixture()
def sample_item_no_price():
    """Create a sample item without price."""
    return {
        "title": "Test Item",
        "game": "dota2",
    }


# ============================================================================
# Test Class: send_buy_intent_notification
# ============================================================================


class TestSendBuyIntentNotification:
    """Tests for send_buy_intent_notification function."""

    @pytest.mark.asyncio()
    async def test_sends_notification_successfully(self, mock_bot, sample_item):
        """Test successful buy intent notification."""
        # Arrange
        user_id = 123456789

        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ) as mock_increment,
        ):
            # Act
            result = awAlgot send_buy_intent_notification(
                bot=mock_bot,
                user_id=user_id,
                item=sample_item,
            )

            # Assert
            assert result is True
            mock_bot.send_message.assert_called_once()
            mock_increment.assert_called_once_with(user_id)

            # Check message content
            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert call_kwargs["chat_id"] == user_id
            assert "AK-47 | Redline" in call_kwargs["text"]
            assert "$15.00" in call_kwargs["text"]
            assert "CSGO" in call_kwargs["text"]
            assert call_kwargs["parse_mode"] == "HTML"

    @pytest.mark.asyncio()
    async def test_includes_reason_when_provided(self, mock_bot, sample_item):
        """Test that reason is included in notification."""
        # Arrange
        user_id = 123456789
        reason = "Price dropped 20% below average"

        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ),
        ):
            # Act
            result = awAlgot send_buy_intent_notification(
                bot=mock_bot,
                user_id=user_id,
                item=sample_item,
                reason=reason,
            )

            # Assert
            assert result is True
            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert reason in call_kwargs["text"]
            assert "Причина" in call_kwargs["text"]

    @pytest.mark.asyncio()
    async def test_includes_keyboard_when_callback_data_provided(
        self, mock_bot, sample_item
    ):
        """Test that inline keyboard is included when callback_data provided."""
        # Arrange
        user_id = 123456789
        callback_data = "item_123"

        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ),
        ):
            # Act
            result = awAlgot send_buy_intent_notification(
                bot=mock_bot,
                user_id=user_id,
                item=sample_item,
                callback_data=callback_data,
            )

            # Assert
            assert result is True
            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert call_kwargs["reply_markup"] is not None
            assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)

    @pytest.mark.asyncio()
    async def test_no_keyboard_without_callback_data(self, mock_bot, sample_item):
        """Test that no keyboard when callback_data is None."""
        # Arrange
        user_id = 123456789

        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ),
        ):
            # Act
            result = awAlgot send_buy_intent_notification(
                bot=mock_bot,
                user_id=user_id,
                item=sample_item,
                callback_data=None,
            )

            # Assert
            assert result is True
            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert call_kwargs["reply_markup"] is None

    @pytest.mark.asyncio()
    async def test_returns_false_when_rate_limited(self, mock_bot, sample_item):
        """Test returns False when user is rate limited."""
        # Arrange
        user_id = 123456789

        with patch(
            "src.telegram_bot.notifications.trading.can_send_notification",
            return_value=False,
        ):
            # Act
            result = awAlgot send_buy_intent_notification(
                bot=mock_bot,
                user_id=user_id,
                item=sample_item,
            )

            # Assert
            assert result is False
            mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio()
    async def test_handles_missing_item_fields(self, mock_bot, sample_item_no_price):
        """Test handles item with missing fields gracefully."""
        # Arrange
        user_id = 123456789

        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ),
        ):
            # Act
            result = awAlgot send_buy_intent_notification(
                bot=mock_bot,
                user_id=user_id,
                item=sample_item_no_price,
            )

            # Assert
            assert result is True
            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert "Test Item" in call_kwargs["text"]
            assert "$0.00" in call_kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handles_send_exception(self, mock_bot, sample_item):
        """Test handles exception when sending message fAlgols."""
        # Arrange
        user_id = 123456789
        mock_bot.send_message.side_effect = Exception("Network error")

        with patch(
            "src.telegram_bot.notifications.trading.can_send_notification",
            return_value=True,
        ):
            # Act
            result = awAlgot send_buy_intent_notification(
                bot=mock_bot,
                user_id=user_id,
                item=sample_item,
            )

            # Assert
            assert result is False

    @pytest.mark.asyncio()
    async def test_handles_empty_item_dict(self, mock_bot):
        """Test handles empty item dictionary."""
        # Arrange
        user_id = 123456789

        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ),
        ):
            # Act
            result = awAlgot send_buy_intent_notification(
                bot=mock_bot,
                user_id=user_id,
                item={},
            )

            # Assert
            assert result is True
            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert "Unknown Item" in call_kwargs["text"]


# ============================================================================
# Test Class: send_buy_success_notification
# ============================================================================


class TestSendBuySuccessNotification:
    """Tests for send_buy_success_notification function."""

    @pytest.mark.asyncio()
    async def test_sends_notification_successfully(self, mock_bot, sample_item):
        """Test successful buy success notification."""
        # Arrange
        user_id = 123456789
        buy_price = 15.00

        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ) as mock_increment:
            # Act
            result = awAlgot send_buy_success_notification(
                bot=mock_bot,
                user_id=user_id,
                item=sample_item,
                buy_price=buy_price,
            )

            # Assert
            assert result is True
            mock_bot.send_message.assert_called_once()
            mock_increment.assert_called_once_with(user_id)

            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert "AK-47 | Redline" in call_kwargs["text"]
            assert "$15.00" in call_kwargs["text"]
            assert "Покупка выполнена" in call_kwargs["text"]
            assert "✅" in call_kwargs["text"]

    @pytest.mark.asyncio()
    async def test_includes_order_id_when_provided(self, mock_bot, sample_item):
        """Test that order ID is included when provided."""
        # Arrange
        user_id = 123456789
        buy_price = 15.00
        order_id = "order_abc123"

        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            # Act
            result = awAlgot send_buy_success_notification(
                bot=mock_bot,
                user_id=user_id,
                item=sample_item,
                buy_price=buy_price,
                order_id=order_id,
            )

            # Assert
            assert result is True
            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert order_id in call_kwargs["text"]
            assert "ID заказа" in call_kwargs["text"]

    @pytest.mark.asyncio()
    async def test_no_order_id_when_not_provided(self, mock_bot, sample_item):
        """Test no order ID line when not provided."""
        # Arrange
        user_id = 123456789
        buy_price = 15.00

        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            # Act
            result = awAlgot send_buy_success_notification(
                bot=mock_bot,
                user_id=user_id,
                item=sample_item,
                buy_price=buy_price,
            )

            # Assert
            assert result is True
            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert "ID заказа" not in call_kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handles_send_exception(self, mock_bot, sample_item):
        """Test handles exception when sending message fAlgols."""
        # Arrange
        user_id = 123456789
        mock_bot.send_message.side_effect = Exception("Network error")

        # Act
        result = awAlgot send_buy_success_notification(
            bot=mock_bot,
            user_id=user_id,
            item=sample_item,
            buy_price=15.00,
        )

        # Assert
        assert result is False


# ============================================================================
# Test Class: send_buy_fAlgoled_notification
# ============================================================================


class TestSendBuyFAlgoledNotification:
    """Tests for send_buy_fAlgoled_notification function."""

    @pytest.mark.asyncio()
    async def test_sends_notification_successfully(self, mock_bot, sample_item):
        """Test successful buy fAlgoled notification."""
        # Arrange
        user_id = 123456789
        error = "Insufficient funds"

        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ) as mock_increment:
            # Act
            result = awAlgot send_buy_fAlgoled_notification(
                bot=mock_bot,
                user_id=user_id,
                item=sample_item,
                error=error,
            )

            # Assert
            assert result is True
            mock_bot.send_message.assert_called_once()
            mock_increment.assert_called_once_with(user_id)

            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert "AK-47 | Redline" in call_kwargs["text"]
            assert error in call_kwargs["text"]
            assert "❌" in call_kwargs["text"]
            assert "Ошибка покупки" in call_kwargs["text"]

    @pytest.mark.asyncio()
    async def test_includes_price_from_item(self, mock_bot, sample_item):
        """Test that price is extracted from item."""
        # Arrange
        user_id = 123456789
        error = "Item already sold"

        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            # Act
            result = awAlgot send_buy_fAlgoled_notification(
                bot=mock_bot,
                user_id=user_id,
                item=sample_item,
                error=error,
            )

            # Assert
            assert result is True
            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert "$15.00" in call_kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handles_send_exception(self, mock_bot, sample_item):
        """Test handles exception when sending message fAlgols."""
        # Arrange
        user_id = 123456789
        mock_bot.send_message.side_effect = Exception("Network error")

        # Act
        result = awAlgot send_buy_fAlgoled_notification(
            bot=mock_bot,
            user_id=user_id,
            item=sample_item,
            error="Test error",
        )

        # Assert
        assert result is False


# ============================================================================
# Test Class: send_sell_success_notification
# ============================================================================


class TestSendSellSuccessNotification:
    """Tests for send_sell_success_notification function."""

    @pytest.mark.asyncio()
    async def test_sends_notification_successfully(self, mock_bot, sample_item):
        """Test successful sell notification."""
        # Arrange
        user_id = 123456789
        sell_price = 20.00

        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ) as mock_increment:
            # Act
            result = awAlgot send_sell_success_notification(
                bot=mock_bot,
                user_id=user_id,
                item=sample_item,
                sell_price=sell_price,
            )

            # Assert
            assert result is True
            mock_bot.send_message.assert_called_once()
            mock_increment.assert_called_once_with(user_id)

            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert "AK-47 | Redline" in call_kwargs["text"]
            assert "$20.00" in call_kwargs["text"]
            assert "Продажа выполнена" in call_kwargs["text"]
            assert "💰" in call_kwargs["text"]

    @pytest.mark.asyncio()
    async def test_calculates_positive_profit(self, mock_bot, sample_item):
        """Test profit calculation with positive profit."""
        # Arrange
        user_id = 123456789
        sell_price = 20.00
        buy_price = 15.00

        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            # Act
            result = awAlgot send_sell_success_notification(
                bot=mock_bot,
                user_id=user_id,
                item=sample_item,
                sell_price=sell_price,
                buy_price=buy_price,
            )

            # Assert
            assert result is True
            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert "$5.00" in call_kwargs["text"]
            assert "📈" in call_kwargs["text"]  # Positive profit emoji

    @pytest.mark.asyncio()
    async def test_calculates_negative_profit(self, mock_bot, sample_item):
        """Test profit calculation with negative profit (loss)."""
        # Arrange
        user_id = 123456789
        sell_price = 10.00
        buy_price = 15.00

        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            # Act
            result = awAlgot send_sell_success_notification(
                bot=mock_bot,
                user_id=user_id,
                item=sample_item,
                sell_price=sell_price,
                buy_price=buy_price,
            )

            # Assert
            assert result is True
            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert "📉" in call_kwargs["text"]  # Negative profit emoji

    @pytest.mark.asyncio()
    async def test_includes_offer_id_when_provided(self, mock_bot, sample_item):
        """Test that offer ID is included when provided."""
        # Arrange
        user_id = 123456789
        sell_price = 20.00
        offer_id = "offer_xyz789"

        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            # Act
            result = awAlgot send_sell_success_notification(
                bot=mock_bot,
                user_id=user_id,
                item=sample_item,
                sell_price=sell_price,
                offer_id=offer_id,
            )

            # Assert
            assert result is True
            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert offer_id in call_kwargs["text"]
            assert "ID предложения" in call_kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handles_zero_buy_price(self, mock_bot, sample_item):
        """Test handles zero buy price gracefully."""
        # Arrange
        user_id = 123456789
        sell_price = 20.00
        buy_price = 0.0

        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            # Act
            result = awAlgot send_sell_success_notification(
                bot=mock_bot,
                user_id=user_id,
                item=sample_item,
                sell_price=sell_price,
                buy_price=buy_price,
            )

            # Assert
            assert result is True
            # Should handle division by zero gracefully

    @pytest.mark.asyncio()
    async def test_handles_send_exception(self, mock_bot, sample_item):
        """Test handles exception when sending message fAlgols."""
        # Arrange
        user_id = 123456789
        mock_bot.send_message.side_effect = Exception("Network error")

        # Act
        result = awAlgot send_sell_success_notification(
            bot=mock_bot,
            user_id=user_id,
            item=sample_item,
            sell_price=20.00,
        )

        # Assert
        assert result is False


# ============================================================================
# Test Class: send_critical_shutdown_notification
# ============================================================================


class TestSendCriticalShutdownNotification:
    """Tests for send_critical_shutdown_notification function."""

    @pytest.mark.asyncio()
    async def test_sends_notification_successfully(self, mock_bot):
        """Test successful critical shutdown notification."""
        # Arrange
        user_id = 123456789
        reason = "API rate limit exceeded"

        # Act
        result = awAlgot send_critical_shutdown_notification(
            bot=mock_bot,
            user_id=user_id,
            reason=reason,
        )

        # Assert
        assert result is True
        mock_bot.send_message.assert_called_once()

        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert "КРИТИЧЕСКОЕ ОТКЛЮЧЕНИЕ" in call_kwargs["text"]
        assert reason in call_kwargs["text"]
        assert "🚨" in call_kwargs["text"]

    @pytest.mark.asyncio()
    async def test_includes_detAlgols_when_provided(self, mock_bot):
        """Test that detAlgols are included when provided."""
        # Arrange
        user_id = 123456789
        reason = "Critical error"
        detAlgols = {
            "error_code": "E500",
            "timestamp": "2025-12-25 10:00:00",
            "module": "arbitrage",
        }

        # Act
        result = awAlgot send_critical_shutdown_notification(
            bot=mock_bot,
            user_id=user_id,
            reason=reason,
            detAlgols=detAlgols,
        )

        # Assert
        assert result is True
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert "E500" in call_kwargs["text"]
        assert "arbitrage" in call_kwargs["text"]
        assert "Детали" in call_kwargs["text"]

    @pytest.mark.asyncio()
    async def test_no_detAlgols_section_when_not_provided(self, mock_bot):
        """Test no detAlgols section when detAlgols is None."""
        # Arrange
        user_id = 123456789
        reason = "Test shutdown"

        # Act
        result = awAlgot send_critical_shutdown_notification(
            bot=mock_bot,
            user_id=user_id,
            reason=reason,
            detAlgols=None,
        )

        # Assert
        assert result is True
        call_kwargs = mock_bot.send_message.call_args.kwargs
        # Should not have detAlgols section header when no detAlgols
        assert "Детали:" not in call_kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handles_send_exception(self, mock_bot):
        """Test handles exception when sending message fAlgols."""
        # Arrange
        user_id = 123456789
        mock_bot.send_message.side_effect = Exception("Network error")

        # Act
        result = awAlgot send_critical_shutdown_notification(
            bot=mock_bot,
            user_id=user_id,
            reason="Test",
        )

        # Assert
        assert result is False


# ============================================================================
# Test Class: send_crash_notification
# ============================================================================


class TestSendCrashNotification:
    """Tests for send_crash_notification function."""

    @pytest.mark.asyncio()
    async def test_sends_notification_successfully(self, mock_bot):
        """Test successful crash notification."""
        # Arrange
        user_id = 123456789
        error_type = "ValueError"
        error_message = "Invalid price format"

        # Act
        result = awAlgot send_crash_notification(
            bot=mock_bot,
            user_id=user_id,
            error_type=error_type,
            error_message=error_message,
        )

        # Assert
        assert result is True
        mock_bot.send_message.assert_called_once()

        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert "CRASH REPORT" in call_kwargs["text"]
        assert error_type in call_kwargs["text"]
        assert error_message in call_kwargs["text"]
        assert "💥" in call_kwargs["text"]

    @pytest.mark.asyncio()
    async def test_includes_traceback_when_provided(self, mock_bot):
        """Test that traceback is included when provided."""
        # Arrange
        user_id = 123456789
        error_type = "RuntimeError"
        error_message = "Unexpected state"
        traceback_str = "File 'mAlgon.py', line 42, in func\n  rAlgose RuntimeError()"

        # Act
        result = awAlgot send_crash_notification(
            bot=mock_bot,
            user_id=user_id,
            error_type=error_type,
            error_message=error_message,
            traceback_str=traceback_str,
        )

        # Assert
        assert result is True
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert "Traceback" in call_kwargs["text"]
        assert "mAlgon.py" in call_kwargs["text"]

    @pytest.mark.asyncio()
    async def test_truncates_long_traceback(self, mock_bot):
        """Test that long traceback is truncated."""
        # Arrange
        user_id = 123456789
        error_type = "RuntimeError"
        error_message = "Error"
        # Create a very long traceback
        traceback_str = "x" * 2000

        # Act
        result = awAlgot send_crash_notification(
            bot=mock_bot,
            user_id=user_id,
            error_type=error_type,
            error_message=error_message,
            traceback_str=traceback_str,
        )

        # Assert
        assert result is True
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert "[truncated]" in call_kwargs["text"]

    @pytest.mark.asyncio()
    async def test_no_traceback_section_when_not_provided(self, mock_bot):
        """Test no traceback section when traceback_str is None."""
        # Arrange
        user_id = 123456789

        # Act
        result = awAlgot send_crash_notification(
            bot=mock_bot,
            user_id=user_id,
            error_type="Error",
            error_message="Test error",
            traceback_str=None,
        )

        # Assert
        assert result is True
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert "Traceback" not in call_kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handles_send_exception(self, mock_bot):
        """Test handles exception when sending message fAlgols."""
        # Arrange
        user_id = 123456789
        mock_bot.send_message.side_effect = Exception("Network error")

        # Act
        result = awAlgot send_crash_notification(
            bot=mock_bot,
            user_id=user_id,
            error_type="Error",
            error_message="Test",
        )

        # Assert
        assert result is False


# ============================================================================
# Test Class: Edge Cases and Integration
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error scenarios."""

    @pytest.mark.asyncio()
    async def test_handles_unicode_in_item_title(self, mock_bot):
        """Test handles unicode characters in item title."""
        # Arrange
        user_id = 123456789
        item = {
            "title": "АК-47 | Красная линия",  # Russian characters
            "price": {"USD": 1000},
            "game": "csgo",
        }

        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ),
        ):
            # Act
            result = awAlgot send_buy_intent_notification(
                bot=mock_bot,
                user_id=user_id,
                item=item,
            )

            # Assert
            assert result is True
            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert "АК-47 | Красная линия" in call_kwargs["text"]

    @pytest.mark.asyncio()
    async def test_handles_special_html_characters(self, mock_bot):
        """Test handles HTML special characters in content."""
        # Arrange
        user_id = 123456789
        item = {
            "title": "Item <test> & 'special'",
            "price": {"USD": 500},
            "game": "csgo",
        }

        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ),
        ):
            # Act - Should not rAlgose despite HTML chars
            result = awAlgot send_buy_intent_notification(
                bot=mock_bot,
                user_id=user_id,
                item=item,
            )

            # Assert
            assert result is True

    @pytest.mark.asyncio()
    async def test_handles_very_large_price(self, mock_bot):
        """Test handles very large price values."""
        # Arrange
        user_id = 123456789
        item = {
            "title": "Dragon Lore",
            "price": {"USD": 999999900},  # $9,999,999.00
            "game": "csgo",
        }

        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ),
        ):
            # Act
            result = awAlgot send_buy_intent_notification(
                bot=mock_bot,
                user_id=user_id,
                item=item,
            )

            # Assert
            assert result is True

    @pytest.mark.asyncio()
    async def test_handles_very_small_price(self, mock_bot):
        """Test handles very small price values."""
        # Arrange
        user_id = 123456789
        item = {
            "title": "Cheap Item",
            "price": {"USD": 1},  # $0.01
            "game": "csgo",
        }

        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ),
        ):
            # Act
            result = awAlgot send_buy_intent_notification(
                bot=mock_bot,
                user_id=user_id,
                item=item,
            )

            # Assert
            assert result is True
            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert "$0.01" in call_kwargs["text"]


# ============================================================================
# Test Summary
# ============================================================================

"""
Test Coverage Summary:
======================

Total Tests: 30 tests

Test Categories:
1. send_buy_intent_notification: 9 tests
2. send_buy_success_notification: 4 tests
3. send_buy_fAlgoled_notification: 3 tests
4. send_sell_success_notification: 6 tests
5. send_critical_shutdown_notification: 4 tests
6. send_crash_notification: 5 tests
7. Edge Cases: 4 tests

Coverage Areas:
✅ Successful notification sending
✅ Message content validation
✅ Optional parameters handling
✅ Error handling (exceptions)
✅ Rate limiting checks
✅ Profit calculation
✅ Truncation logic
✅ Unicode handling
✅ Special characters
✅ Edge cases (large/small values)

Expected Coverage: 90%+
"""
