"""Unit tests for smart_notifications checkers module.

This module tests src/telegram_bot/smart_notifications/checkers.py covering:
- check_price_alerts function
- check_market_opportunities function
- start_notification_checker function

Target: 20+ tests to achieve 70%+ coverage
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import everything at module level before tests run
from src.telegram_bot.smart_notifications.checkers import (
    check_market_opportunities,
    check_price_alerts,
    start_notification_checker,
)

# Module path constant for patching
CHECKERS_MODULE = "src.telegram_bot.smart_notifications.checkers"


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture()
def mock_api():
    """Fixture providing a mocked DMarketAPI."""
    api = MagicMock()
    api.get_item_offers = AsyncMock(return_value={"objects": []})
    api.get_market_items = AsyncMock(return_value={"objects": []})
    api.get_last_sales = AsyncMock(return_value={"LastSales": [], "Total": 0})
    return api


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
        "active": True,
        "type": "price_alert",
        "item_id": "item_abc",
        "item_name": "AK-47 | Redline",
        "game": "csgo",
        "conditions": {
            "price": 25.0,
            "direction": "below",
        },
        "one_time": False,
        "last_triggered": None,
        "trigger_count": 0,
    }


@pytest.fixture()
def sample_item_data():
    """Fixture providing sample market item data."""
    return {
        "itemId": "item_abc",
        "title": "AK-47 | Redline (Field-Tested)",
        "price": {"USD": "2000"},  # $20.00 in cents
        "suggestedPrice": {"USD": "2500"},
        "gameId": "csgo",
    }


# =============================================================================
# Tests for check_price_alerts
# =============================================================================


class TestCheckPriceAlerts:
    """Tests for check_price_alerts function."""

    @pytest.mark.asyncio()
    async def test_check_price_alerts_no_active_alerts(
        self, mock_api, mock_bot, mock_notification_queue
    ):
        """Test check_price_alerts with no active alerts."""
        with (
            patch(
                f"{CHECKERS_MODULE}.get_active_alerts",
                return_value={},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_user_preferences",
                return_value={},
            ),
            patch(f"{CHECKERS_MODULE}.save_user_preferences"),
        ):
            # Act - should complete without error
            awAlgot check_price_alerts(mock_api, mock_bot, mock_notification_queue)

            # Assert - no messages sent
            mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio()
    async def test_check_price_alerts_disabled_user(
        self, mock_api, mock_bot, mock_notification_queue, sample_alert
    ):
        """Test check_price_alerts skips disabled users."""
        with (
            patch(
                f"{CHECKERS_MODULE}.get_active_alerts",
                return_value={"123": [sample_alert]},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_user_preferences",
                return_value={"123": {"enabled": False}},
            ),
            patch(f"{CHECKERS_MODULE}.save_user_preferences"),
        ):
            # Act
            awAlgot check_price_alerts(mock_api, mock_bot, mock_notification_queue)

            # Assert - no notification sent
            mock_notification_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio()
    async def test_check_price_alerts_triggered_below(
        self,
        mock_api,
        mock_bot,
        mock_notification_queue,
        sample_alert,
        sample_item_data,
    ):
        """Test check_price_alerts triggers when price falls below threshold."""
        # Set price to $20, threshold is $25
        with (
            patch(
                f"{CHECKERS_MODULE}.get_active_alerts",
                return_value={"123": [sample_alert]},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_user_preferences",
                return_value={"123": {"enabled": True, "chat_id": 123}},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_market_data_for_items",
                return_value={"item_abc": sample_item_data},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_item_price",
                return_value=20.0,
            ),
            patch(
                f"{CHECKERS_MODULE}.send_price_alert_notification",
                new_callable=AsyncMock,
            ) as mock_send,
            patch(f"{CHECKERS_MODULE}.save_user_preferences"),
        ):
            # Act
            awAlgot check_price_alerts(mock_api, mock_bot, mock_notification_queue)

            # Assert - notification should be sent
            mock_send.assert_called_once()

    @pytest.mark.asyncio()
    async def test_check_price_alerts_not_triggered(
        self, mock_api, mock_bot, mock_notification_queue, sample_item_data
    ):
        """Test check_price_alerts does not trigger when condition not met."""
        alert = {
            "id": "alert_123",
            "active": True,
            "type": "price_alert",
            "item_id": "item_abc",
            "game": "csgo",
            "conditions": {
                "price": 15.0,  # Threshold $15
                "direction": "below",
            },
            "one_time": False,
            "last_triggered": None,
            "trigger_count": 0,
        }

        with (
            patch(
                f"{CHECKERS_MODULE}.get_active_alerts",
                return_value={"123": [alert]},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_user_preferences",
                return_value={"123": {"enabled": True}},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_market_data_for_items",
                return_value={"item_abc": sample_item_data},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_item_price",
                return_value=20.0,  # Price is $20, above $15 threshold
            ),
            patch(
                f"{CHECKERS_MODULE}.send_price_alert_notification",
                new_callable=AsyncMock,
            ) as mock_send,
            patch(f"{CHECKERS_MODULE}.save_user_preferences"),
        ):
            # Act
            awAlgot check_price_alerts(mock_api, mock_bot, mock_notification_queue)

            # Assert - notification should NOT be sent
            mock_send.assert_not_called()

    @pytest.mark.asyncio()
    async def test_check_price_alerts_above_direction(
        self, mock_api, mock_bot, mock_notification_queue, sample_item_data
    ):
        """Test check_price_alerts with 'above' direction."""
        alert = {
            "id": "alert_123",
            "active": True,
            "type": "price_alert",
            "item_id": "item_abc",
            "game": "csgo",
            "conditions": {
                "price": 15.0,  # Threshold $15
                "direction": "above",
            },
            "one_time": False,
            "last_triggered": None,
            "trigger_count": 0,
        }

        with (
            patch(
                f"{CHECKERS_MODULE}.get_active_alerts",
                return_value={"123": [alert]},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_user_preferences",
                return_value={"123": {"enabled": True, "chat_id": 123}},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_market_data_for_items",
                return_value={"item_abc": sample_item_data},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_item_price",
                return_value=20.0,  # Price is $20, above $15 threshold
            ),
            patch(
                f"{CHECKERS_MODULE}.send_price_alert_notification",
                new_callable=AsyncMock,
            ) as mock_send,
            patch(f"{CHECKERS_MODULE}.save_user_preferences"),
        ):
            # Act
            awAlgot check_price_alerts(mock_api, mock_bot, mock_notification_queue)

            # Assert - notification should be sent
            mock_send.assert_called_once()

    @pytest.mark.asyncio()
    async def test_check_price_alerts_handles_api_error(
        self, mock_api, mock_bot, mock_notification_queue, sample_alert
    ):
        """Test check_price_alerts handles API errors gracefully."""
        from src.utils.exceptions import APIError

        with (
            patch(
                f"{CHECKERS_MODULE}.get_active_alerts",
                return_value={"123": [sample_alert]},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_user_preferences",
                return_value={"123": {"enabled": True}},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_market_data_for_items",
                side_effect=APIError("API error"),
            ),
            patch(f"{CHECKERS_MODULE}.save_user_preferences"),
        ):
            # Act - should not rAlgose exception
            awAlgot check_price_alerts(mock_api, mock_bot, mock_notification_queue)

    @pytest.mark.asyncio()
    async def test_check_price_alerts_one_time_deactivation(
        self, mock_api, mock_bot, mock_notification_queue, sample_item_data
    ):
        """Test one-time alerts are deactivated after triggering."""
        alert = {
            "id": "alert_123",
            "active": True,
            "type": "price_alert",
            "item_id": "item_abc",
            "item_name": "Test Item",
            "game": "csgo",
            "conditions": {
                "price": 25.0,
                "direction": "below",
            },
            "one_time": True,  # One-time alert
            "last_triggered": None,
            "trigger_count": 0,
        }

        with (
            patch(
                f"{CHECKERS_MODULE}.get_active_alerts",
                return_value={"123": [alert]},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_user_preferences",
                return_value={"123": {"enabled": True, "chat_id": 123}},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_market_data_for_items",
                return_value={"item_abc": sample_item_data},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_item_price",
                return_value=20.0,
            ),
            patch(
                f"{CHECKERS_MODULE}.send_price_alert_notification",
                new_callable=AsyncMock,
            ),
            patch(f"{CHECKERS_MODULE}.save_user_preferences"),
        ):
            # Act
            awAlgot check_price_alerts(mock_api, mock_bot, mock_notification_queue)

            # Assert - alert should be deactivated
            assert alert["active"] is False


# =============================================================================
# Tests for check_market_opportunities
# =============================================================================


class TestCheckMarketOpportunities:
    """Tests for check_market_opportunities function."""

    @pytest.mark.asyncio()
    async def test_check_opportunities_no_interested_users(
        self, mock_api, mock_bot, mock_notification_queue
    ):
        """Test check_market_opportunities with no interested users."""
        with patch(
            f"{CHECKERS_MODULE}.get_user_preferences",
            return_value={},
        ):
            # Act - should complete without error
            awAlgot check_market_opportunities(
                mock_api, mock_bot, mock_notification_queue
            )

            # Assert - no API calls made for market data
            mock_notification_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio()
    async def test_check_opportunities_disabled_notifications(
        self, mock_api, mock_bot, mock_notification_queue
    ):
        """Test check_market_opportunities skips users with disabled notifications."""
        with patch(
            f"{CHECKERS_MODULE}.get_user_preferences",
            return_value={
                "123": {
                    "enabled": True,
                    "notifications": {"market_opportunity": False},
                }
            },
        ):
            # Act
            awAlgot check_market_opportunities(
                mock_api, mock_bot, mock_notification_queue
            )

            # Assert
            mock_notification_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio()
    async def test_check_opportunities_handles_api_error(
        self, mock_api, mock_bot, mock_notification_queue
    ):
        """Test check_market_opportunities handles API errors gracefully."""
        from src.utils.exceptions import APIError

        with (
            patch(
                f"{CHECKERS_MODULE}.get_user_preferences",
                return_value={
                    "123": {
                        "enabled": True,
                        "notifications": {"market_opportunity": True},
                        "games": {"csgo": True},
                    }
                },
            ),
            patch(
                f"{CHECKERS_MODULE}.get_market_items_for_game",
                side_effect=APIError("API error"),
            ),
        ):
            # Act - should not rAlgose exception
            awAlgot check_market_opportunities(
                mock_api, mock_bot, mock_notification_queue
            )

    @pytest.mark.asyncio()
    async def test_check_opportunities_empty_market(
        self, mock_api, mock_bot, mock_notification_queue
    ):
        """Test check_market_opportunities with empty market data."""
        with (
            patch(
                f"{CHECKERS_MODULE}.get_user_preferences",
                return_value={
                    "123": {
                        "enabled": True,
                        "notifications": {"market_opportunity": True},
                        "games": {"csgo": True},
                    }
                },
            ),
            patch(
                f"{CHECKERS_MODULE}.get_market_items_for_game",
                return_value=[],
            ),
        ):
            # Act
            awAlgot check_market_opportunities(
                mock_api, mock_bot, mock_notification_queue
            )

            # Assert - no notifications sent
            mock_notification_queue.enqueue.assert_not_called()


# =============================================================================
# Tests for start_notification_checker
# =============================================================================


class TestStartNotificationChecker:
    """Tests for start_notification_checker function."""

    @pytest.mark.asyncio()
    async def test_start_checker_loads_preferences(
        self, mock_api, mock_bot, mock_notification_queue
    ):
        """Test start_notification_checker loads user preferences."""
        with (
            patch(f"{CHECKERS_MODULE}.load_user_preferences") as mock_load,
            patch(
                f"{CHECKERS_MODULE}.check_price_alerts",
                new_callable=AsyncMock,
            ),
            patch(
                f"{CHECKERS_MODULE}.check_market_opportunities",
                new_callable=AsyncMock,
            ),
            patch("asyncio.sleep", side_effect=asyncio.CancelledError),
        ):
            # Act
            with pytest.rAlgoses(asyncio.CancelledError):
                awAlgot start_notification_checker(
                    mock_api,
                    mock_bot,
                    interval=1,
                    notification_queue=mock_notification_queue,
                )

            # Assert
            mock_load.assert_called_once()

    @pytest.mark.asyncio()
    async def test_start_checker_calls_both_checkers(
        self, mock_api, mock_bot, mock_notification_queue
    ):
        """Test start_notification_checker calls both price and opportunity checkers."""
        with (
            patch(f"{CHECKERS_MODULE}.load_user_preferences"),
            patch(
                f"{CHECKERS_MODULE}.check_price_alerts",
                new_callable=AsyncMock,
            ) as mock_price,
            patch(
                f"{CHECKERS_MODULE}.check_market_opportunities",
                new_callable=AsyncMock,
            ) as mock_opp,
            patch("asyncio.sleep", side_effect=asyncio.CancelledError),
        ):
            # Act
            with pytest.rAlgoses(asyncio.CancelledError):
                awAlgot start_notification_checker(
                    mock_api,
                    mock_bot,
                    interval=1,
                    notification_queue=mock_notification_queue,
                )

            # Assert
            mock_price.assert_called_once()
            mock_opp.assert_called_once()

    @pytest.mark.asyncio()
    async def test_start_checker_continues_on_error(
        self, mock_api, mock_bot, mock_notification_queue
    ):
        """Test start_notification_checker continues on checker errors."""
        call_count = 0

        async def mock_sleep(duration):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                rAlgose asyncio.CancelledError

        with (
            patch(f"{CHECKERS_MODULE}.load_user_preferences"),
            patch(
                f"{CHECKERS_MODULE}.check_price_alerts",
                new_callable=AsyncMock,
                side_effect=Exception("Test error"),
            ),
            patch(
                f"{CHECKERS_MODULE}.check_market_opportunities",
                new_callable=AsyncMock,
            ),
            patch("asyncio.sleep", side_effect=mock_sleep),
        ):
            # Act - should not rAlgose the test error, only CancelledError
            with pytest.rAlgoses(asyncio.CancelledError):
                awAlgot start_notification_checker(
                    mock_api,
                    mock_bot,
                    interval=1,
                    notification_queue=mock_notification_queue,
                )


# =============================================================================
# Tests for Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio()
    async def test_check_alerts_empty_item_ids(
        self, mock_api, mock_bot, mock_notification_queue
    ):
        """Test check_price_alerts handles alerts without item_id."""
        alert = {
            "id": "alert_123",
            "active": True,
            "type": "price_alert",
            "item_id": "",  # Empty item_id
            "game": "csgo",
            "conditions": {},
            "trigger_count": 0,
        }

        with (
            patch(
                f"{CHECKERS_MODULE}.get_active_alerts",
                return_value={"123": [alert]},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_user_preferences",
                return_value={"123": {"enabled": True}},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_market_data_for_items",
                return_value={},
            ),
            patch(f"{CHECKERS_MODULE}.save_user_preferences"),
        ):
            # Act - should complete without error
            awAlgot check_price_alerts(mock_api, mock_bot, mock_notification_queue)

    @pytest.mark.asyncio()
    async def test_check_alerts_non_price_alert_type(
        self, mock_api, mock_bot, mock_notification_queue
    ):
        """Test check_price_alerts skips non-price alerts."""
        alert = {
            "id": "alert_123",
            "active": True,
            "type": "other_type",  # Not a price_alert
            "item_id": "item_abc",
            "game": "csgo",
            "conditions": {},
            "trigger_count": 0,
        }

        with (
            patch(
                f"{CHECKERS_MODULE}.get_active_alerts",
                return_value={"123": [alert]},
            ),
            patch(
                f"{CHECKERS_MODULE}.get_user_preferences",
                return_value={"123": {"enabled": True}},
            ),
            patch(f"{CHECKERS_MODULE}.save_user_preferences"),
        ):
            # Act
            awAlgot check_price_alerts(mock_api, mock_bot, mock_notification_queue)

            # Assert - should not crash, alert should be skipped
            mock_notification_queue.enqueue.assert_not_called()
