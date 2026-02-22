"""Tests for trading notifications module.

Comprehensive tests for trading notification functions:
- send_buy_intent_notification
- send_buy_success_notification
- send_buy_failed_notification
- send_sell_success_notification
- send_critical_shutdown_notification
- send_crash_notification
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.telegram_bot.notifications.trading import (
    send_buy_failed_notification,
    send_buy_intent_notification,
    send_buy_success_notification,
    send_crash_notification,
    send_critical_shutdown_notification,
    send_sell_success_notification,
)


@pytest.fixture()
def mock_bot():
    """Create mock Telegram bot."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture()
def sample_item():
    """Create sample item data."""
    return {
        "title": "AK-47 | Redline (Field-Tested)",
        "price": {"USD": 1550},  # $15.50 in cents
        "game": "csgo",
        "itemId": "item-123",
    }


class TestSendBuyIntentNotification:
    """Tests for send_buy_intent_notification function."""

    @pytest.mark.asyncio()
    async def test_send_buy_intent_success(self, mock_bot, sample_item):
        """Test successful buy intent notification."""
        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ) as mock_increment,
        ):
            result = await send_buy_intent_notification(
                bot=mock_bot,
                user_id=123456,
                item=sample_item,
                reason="High profit opportunity",
                callback_data="item-123",
            )

            assert result is True
            mock_bot.send_message.assert_called_once()
            mock_increment.assert_called_once_with(123456)

    @pytest.mark.asyncio()
    async def test_send_buy_intent_rate_limited(self, mock_bot, sample_item):
        """Test buy intent when rate limited."""
        with patch(
            "src.telegram_bot.notifications.trading.can_send_notification",
            return_value=False,
        ):
            result = await send_buy_intent_notification(
                bot=mock_bot, user_id=123456, item=sample_item
            )

            assert result is False
            mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio()
    async def test_send_buy_intent_message_format(self, mock_bot, sample_item):
        """Test buy intent message formatting."""
        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ),
        ):
            await send_buy_intent_notification(
                bot=mock_bot, user_id=123456, item=sample_item, reason="Test reason"
            )

            call_args = mock_bot.send_message.call_args
            message = call_args.kwargs["text"]

            assert "Рекомендация к покупке" in message
            assert "AK-47 | Redline" in message
            assert "$15.50" in message
            assert "CSGO" in message
            assert "Test reason" in message

    @pytest.mark.asyncio()
    async def test_send_buy_intent_with_callback_data(self, mock_bot, sample_item):
        """Test buy intent with callback data creates keyboard."""
        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ),
        ):
            await send_buy_intent_notification(
                bot=mock_bot,
                user_id=123456,
                item=sample_item,
                callback_data="item-123",
            )

            call_args = mock_bot.send_message.call_args
            reply_markup = call_args.kwargs.get("reply_markup")

            assert reply_markup is not None

    @pytest.mark.asyncio()
    async def test_send_buy_intent_without_callback_data(self, mock_bot, sample_item):
        """Test buy intent without callback data has no keyboard."""
        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ),
        ):
            await send_buy_intent_notification(
                bot=mock_bot, user_id=123456, item=sample_item, callback_data=None
            )

            call_args = mock_bot.send_message.call_args
            reply_markup = call_args.kwargs.get("reply_markup")

            assert reply_markup is None

    @pytest.mark.asyncio()
    async def test_send_buy_intent_error_handling(self, mock_bot, sample_item):
        """Test buy intent handles send errors."""
        mock_bot.send_message.side_effect = Exception("Network error")

        with patch(
            "src.telegram_bot.notifications.trading.can_send_notification",
            return_value=True,
        ):
            result = await send_buy_intent_notification(
                bot=mock_bot, user_id=123456, item=sample_item
            )

            assert result is False

    @pytest.mark.asyncio()
    async def test_send_buy_intent_unknown_title(self, mock_bot):
        """Test buy intent with missing title."""
        item = {"price": {"USD": 1000}, "game": "csgo"}

        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ),
        ):
            await send_buy_intent_notification(bot=mock_bot, user_id=123456, item=item)

            call_args = mock_bot.send_message.call_args
            message = call_args.kwargs["text"]

            assert "Unknown Item" in message


class TestSendBuySuccessNotification:
    """Tests for send_buy_success_notification function."""

    @pytest.mark.asyncio()
    async def test_send_buy_success_basic(self, mock_bot, sample_item):
        """Test basic buy success notification."""
        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            result = await send_buy_success_notification(
                bot=mock_bot, user_id=123456, item=sample_item, buy_price=15.50
            )

            assert result is True
            mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio()
    async def test_send_buy_success_with_order_id(self, mock_bot, sample_item):
        """Test buy success with order ID."""
        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            await send_buy_success_notification(
                bot=mock_bot,
                user_id=123456,
                item=sample_item,
                buy_price=15.50,
                order_id="order-abc-123",
            )

            call_args = mock_bot.send_message.call_args
            message = call_args.kwargs["text"]

            assert "order-abc-123" in message

    @pytest.mark.asyncio()
    async def test_send_buy_success_message_format(self, mock_bot, sample_item):
        """Test buy success message formatting."""
        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            await send_buy_success_notification(
                bot=mock_bot, user_id=123456, item=sample_item, buy_price=15.50
            )

            call_args = mock_bot.send_message.call_args
            message = call_args.kwargs["text"]

            assert "Покупка выполнена" in message
            assert "$15.50" in message
            assert "инвентарь" in message

    @pytest.mark.asyncio()
    async def test_send_buy_success_error_handling(self, mock_bot, sample_item):
        """Test buy success handles send errors."""
        mock_bot.send_message.side_effect = Exception("Network error")

        result = await send_buy_success_notification(
            bot=mock_bot, user_id=123456, item=sample_item, buy_price=15.50
        )

        assert result is False


class TestSendBuyFailedNotification:
    """Tests for send_buy_failed_notification function."""

    @pytest.mark.asyncio()
    async def test_send_buy_failed_basic(self, mock_bot, sample_item):
        """Test basic buy failed notification."""
        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            result = await send_buy_failed_notification(
                bot=mock_bot,
                user_id=123456,
                item=sample_item,
                error="Insufficient balance",
            )

            assert result is True
            mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio()
    async def test_send_buy_failed_message_format(self, mock_bot, sample_item):
        """Test buy failed message formatting."""
        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            await send_buy_failed_notification(
                bot=mock_bot,
                user_id=123456,
                item=sample_item,
                error="Item already sold",
            )

            call_args = mock_bot.send_message.call_args
            message = call_args.kwargs["text"]

            assert "Ошибка покупки" in message
            assert "Item already sold" in message
            assert "AK-47 | Redline" in message

    @pytest.mark.asyncio()
    async def test_send_buy_failed_error_handling(self, mock_bot, sample_item):
        """Test buy failed handles send errors."""
        mock_bot.send_message.side_effect = Exception("Network error")

        result = await send_buy_failed_notification(
            bot=mock_bot,
            user_id=123456,
            item=sample_item,
            error="Test error",
        )

        assert result is False


class TestSendSellSuccessNotification:
    """Tests for send_sell_success_notification function."""

    @pytest.mark.asyncio()
    async def test_send_sell_success_basic(self, mock_bot, sample_item):
        """Test basic sell success notification."""
        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            result = await send_sell_success_notification(
                bot=mock_bot,
                user_id=123456,
                item=sample_item,
                sell_price=20.00,
            )

            assert result is True
            mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio()
    async def test_send_sell_success_with_profit(self, mock_bot, sample_item):
        """Test sell success with profit calculation."""
        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            await send_sell_success_notification(
                bot=mock_bot,
                user_id=123456,
                item=sample_item,
                sell_price=20.00,
                buy_price=15.00,  # $5 profit
            )

            call_args = mock_bot.send_message.call_args
            message = call_args.kwargs["text"]

            assert "Прибыль" in message
            assert "$5.00" in message
            assert "+33.3%" in message

    @pytest.mark.asyncio()
    async def test_send_sell_success_with_loss(self, mock_bot, sample_item):
        """Test sell success with loss (negative profit)."""
        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            await send_sell_success_notification(
                bot=mock_bot,
                user_id=123456,
                item=sample_item,
                sell_price=12.00,
                buy_price=15.00,  # -$3 loss
            )

            call_args = mock_bot.send_message.call_args
            message = call_args.kwargs["text"]

            assert "Прибыль" in message
            assert "$-3.00" in message

    @pytest.mark.asyncio()
    async def test_send_sell_success_with_offer_id(self, mock_bot, sample_item):
        """Test sell success with offer ID."""
        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            await send_sell_success_notification(
                bot=mock_bot,
                user_id=123456,
                item=sample_item,
                sell_price=20.00,
                offer_id="offer-xyz-789",
            )

            call_args = mock_bot.send_message.call_args
            message = call_args.kwargs["text"]

            assert "offer-xyz-789" in message

    @pytest.mark.asyncio()
    async def test_send_sell_success_message_format(self, mock_bot, sample_item):
        """Test sell success message formatting."""
        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            await send_sell_success_notification(
                bot=mock_bot,
                user_id=123456,
                item=sample_item,
                sell_price=20.00,
            )

            call_args = mock_bot.send_message.call_args
            message = call_args.kwargs["text"]

            assert "Продажа выполнена" in message
            assert "$20.00" in message

    @pytest.mark.asyncio()
    async def test_send_sell_success_error_handling(self, mock_bot, sample_item):
        """Test sell success handles send errors."""
        mock_bot.send_message.side_effect = Exception("Network error")

        result = await send_sell_success_notification(
            bot=mock_bot,
            user_id=123456,
            item=sample_item,
            sell_price=20.00,
        )

        assert result is False


class TestSendCriticalShutdownNotification:
    """Tests for send_critical_shutdown_notification function."""

    @pytest.mark.asyncio()
    async def test_send_critical_shutdown_basic(self, mock_bot):
        """Test basic critical shutdown notification."""
        result = await send_critical_shutdown_notification(
            bot=mock_bot,
            user_id=123456,
            reason="API connection failed",
        )

        assert result is True
        mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio()
    async def test_send_critical_shutdown_with_details(self, mock_bot):
        """Test critical shutdown with details."""
        await send_critical_shutdown_notification(
            bot=mock_bot,
            user_id=123456,
            reason="API connection failed",
            details={"last_error": "timeout", "retries": 3},
        )

        call_args = mock_bot.send_message.call_args
        message = call_args.kwargs["text"]

        assert "last_error" in message
        assert "timeout" in message
        assert "retries" in message

    @pytest.mark.asyncio()
    async def test_send_critical_shutdown_message_format(self, mock_bot):
        """Test critical shutdown message formatting."""
        await send_critical_shutdown_notification(
            bot=mock_bot,
            user_id=123456,
            reason="Maximum losses exceeded",
        )

        call_args = mock_bot.send_message.call_args
        message = call_args.kwargs["text"]

        assert "КРИТИЧЕСКОЕ ОТКЛЮЧЕНИЕ" in message
        assert "Maximum losses exceeded" in message
        assert "предотвращения потерь" in message

    @pytest.mark.asyncio()
    async def test_send_critical_shutdown_error_handling(self, mock_bot):
        """Test critical shutdown handles send errors."""
        mock_bot.send_message.side_effect = Exception("Network error")

        result = await send_critical_shutdown_notification(
            bot=mock_bot,
            user_id=123456,
            reason="Test reason",
        )

        assert result is False


class TestSendCrashNotification:
    """Tests for send_crash_notification function."""

    @pytest.mark.asyncio()
    async def test_send_crash_basic(self, mock_bot):
        """Test basic crash notification."""
        result = await send_crash_notification(
            bot=mock_bot,
            user_id=123456,
            error_type="ValueError",
            error_message="Invalid input",
        )

        assert result is True
        mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio()
    async def test_send_crash_with_traceback(self, mock_bot):
        """Test crash notification with traceback."""
        traceback_str = (
            "Traceback (most recent call last):\n"
            '  File "main.py", line 10, in <module>\n'
            "    raise ValueError('test')\n"
            "ValueError: test"
        )

        await send_crash_notification(
            bot=mock_bot,
            user_id=123456,
            error_type="ValueError",
            error_message="test",
            traceback_str=traceback_str,
        )

        call_args = mock_bot.send_message.call_args
        message = call_args.kwargs["text"]

        assert "Traceback" in message

    @pytest.mark.asyncio()
    async def test_send_crash_truncates_long_traceback(self, mock_bot):
        """Test crash notification truncates long traceback."""
        long_traceback = "x" * 2000  # Very long traceback

        await send_crash_notification(
            bot=mock_bot,
            user_id=123456,
            error_type="ValueError",
            error_message="test",
            traceback_str=long_traceback,
        )

        call_args = mock_bot.send_message.call_args
        message = call_args.kwargs["text"]

        assert "[truncated]" in message

    @pytest.mark.asyncio()
    async def test_send_crash_message_format(self, mock_bot):
        """Test crash notification message formatting."""
        await send_crash_notification(
            bot=mock_bot,
            user_id=123456,
            error_type="RuntimeError",
            error_message="Something went wrong",
        )

        call_args = mock_bot.send_message.call_args
        message = call_args.kwargs["text"]

        assert "CRASH REPORT" in message
        assert "RuntimeError" in message
        assert "Something went wrong" in message

    @pytest.mark.asyncio()
    async def test_send_crash_error_handling(self, mock_bot):
        """Test crash notification handles send errors."""
        mock_bot.send_message.side_effect = Exception("Network error")

        result = await send_crash_notification(
            bot=mock_bot,
            user_id=123456,
            error_type="ValueError",
            error_message="test",
        )

        assert result is False


class TestHTMLParsing:
    """Tests for HTML parsing in notifications."""

    @pytest.mark.asyncio()
    async def test_notifications_use_html_parse_mode(self, mock_bot, sample_item):
        """Test that all notifications use HTML parse mode."""
        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ),
        ):
            await send_buy_intent_notification(
                bot=mock_bot, user_id=123456, item=sample_item
            )

            call_args = mock_bot.send_message.call_args
            assert call_args.kwargs["parse_mode"] == "HTML"

    @pytest.mark.asyncio()
    async def test_buy_success_html_format(self, mock_bot, sample_item):
        """Test buy success uses HTML formatting."""
        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            await send_buy_success_notification(
                bot=mock_bot, user_id=123456, item=sample_item, buy_price=15.50
            )

            call_args = mock_bot.send_message.call_args
            assert call_args.kwargs["parse_mode"] == "HTML"


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio()
    async def test_item_with_zero_price(self, mock_bot):
        """Test handling of item with zero price."""
        item = {"title": "Free Item", "price": {"USD": 0}, "game": "csgo"}

        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ),
        ):
            await send_buy_intent_notification(bot=mock_bot, user_id=123456, item=item)

            call_args = mock_bot.send_message.call_args
            message = call_args.kwargs["text"]

            assert "$0.00" in message

    @pytest.mark.asyncio()
    async def test_item_with_missing_price(self, mock_bot):
        """Test handling of item with missing price."""
        item = {"title": "Item", "game": "csgo"}  # No price field

        with (
            patch(
                "src.telegram_bot.notifications.trading.can_send_notification",
                return_value=True,
            ),
            patch(
                "src.telegram_bot.notifications.trading.increment_notification_count"
            ),
        ):
            await send_buy_intent_notification(bot=mock_bot, user_id=123456, item=item)

            call_args = mock_bot.send_message.call_args
            message = call_args.kwargs["text"]

            assert "$0.00" in message

    @pytest.mark.asyncio()
    async def test_sell_with_zero_buy_price(self, mock_bot, sample_item):
        """Test sell success with zero buy price (no profit calculation)."""
        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            await send_sell_success_notification(
                bot=mock_bot,
                user_id=123456,
                item=sample_item,
                sell_price=20.00,
                buy_price=0.0,  # Zero buy price
            )

            # Should not raise division by zero
            mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio()
    async def test_empty_error_message(self, mock_bot, sample_item):
        """Test buy failed with empty error message."""
        with patch(
            "src.telegram_bot.notifications.trading.increment_notification_count"
        ):
            await send_buy_failed_notification(
                bot=mock_bot, user_id=123456, item=sample_item, error=""
            )

            call_args = mock_bot.send_message.call_args
            message = call_args.kwargs["text"]

            assert "Ошибка:" in message
