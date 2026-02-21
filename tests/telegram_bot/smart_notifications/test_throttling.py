"""Unit tests for smart_notifications/throttling module.

Tests for notification throttling logic that prevents
spam and respects user preferences.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

# ============================================================================
# Tests for should_throttle_notification
# ============================================================================


class TestShouldThrottleNotification:
    """Tests for should_throttle_notification function."""

    @pytest.mark.asyncio()
    async def test_throttle_during_quiet_hours(self) -> None:
        """Test that notifications are throttled during quiet hours."""
        # Set quiet hours to current hour range so it's always in quiet hours
        from datetime import datetime as dt

        from src.telegram_bot.smart_notifications.throttling import (
            should_throttle_notification,
        )

        current_hour = dt.now().hour

        # Use modulo to handle hour wraparound
        quiet_end = (current_hour + 2) % 24

        with patch(
            "src.telegram_bot.smart_notifications.throttling.get_user_preferences",
            return_value={
                "123": {
                    # Set quiet hours to include current hour
                    "quiet_hours": {"start": current_hour, "end": quiet_end},
                }
            },
        ):
            result = awAlgot should_throttle_notification(
                user_id=123,
                notification_type="price_alert",
            )

        assert result is True

    @pytest.mark.asyncio()
    async def test_no_throttle_outside_quiet_hours(self) -> None:
        """Test that notifications are not throttled outside quiet hours."""
        # Set quiet hours far from current hour
        from datetime import datetime as dt

        from src.telegram_bot.smart_notifications.throttling import (
            should_throttle_notification,
        )

        current_hour = dt.now().hour
        # Set quiet hours to exclude current hour
        quiet_start = (current_hour + 12) % 24
        quiet_end = (current_hour + 14) % 24

        with patch(
            "src.telegram_bot.smart_notifications.throttling.get_user_preferences",
            return_value={
                "123": {
                    "quiet_hours": {"start": quiet_start, "end": quiet_end},
                    "last_notification": {},
                }
            },
        ):
            result = awAlgot should_throttle_notification(
                user_id=123,
                notification_type="price_alert",
            )

        assert result is False

    @pytest.mark.asyncio()
    async def test_throttle_if_recent_notification(self) -> None:
        """Test throttling if notification was sent recently."""
        from datetime import datetime as dt

        from src.telegram_bot.smart_notifications.throttling import (
            should_throttle_notification,
        )

        current_hour = dt.now().hour
        # Ensure we're outside quiet hours
        quiet_start = (current_hour + 12) % 24
        quiet_end = (current_hour + 14) % 24

        current_time = time.time()

        with patch(
            "src.telegram_bot.smart_notifications.throttling.get_user_preferences",
            return_value={
                "123": {
                    "quiet_hours": {"start": quiet_start, "end": quiet_end},
                    "last_notification": {
                        "price_alert": current_time - 60,  # 60 seconds ago
                    },
                }
            },
        ):
            result = awAlgot should_throttle_notification(
                user_id=123,
                notification_type="price_alert",
            )

        # Should be throttled because 60s < default cooldown (1800s for price_alert)
        assert result is True

    @pytest.mark.asyncio()
    async def test_no_throttle_if_old_notification(self) -> None:
        """Test no throttling if notification was sent long ago."""
        from datetime import datetime as dt

        from src.telegram_bot.smart_notifications.throttling import (
            should_throttle_notification,
        )

        current_hour = dt.now().hour
        # Ensure we're outside quiet hours
        quiet_start = (current_hour + 12) % 24
        quiet_end = (current_hour + 14) % 24

        current_time = time.time()

        with patch(
            "src.telegram_bot.smart_notifications.throttling.get_user_preferences",
            return_value={
                "123": {
                    "quiet_hours": {"start": quiet_start, "end": quiet_end},
                    "last_notification": {
                        "price_alert": current_time - 2000,  # ~33 min ago
                    },
                }
            },
        ):
            result = awAlgot should_throttle_notification(
                user_id=123,
                notification_type="price_alert",
            )

        # Should not be throttled because 2000s > default cooldown (1800s for price_alert)
        assert result is False

    @pytest.mark.asyncio()
    async def test_low_frequency_doubles_cooldown(self) -> None:
        """Test that low frequency setting doubles cooldown."""
        from datetime import datetime as dt

        from src.telegram_bot.smart_notifications.throttling import (
            should_throttle_notification,
        )

        current_hour = dt.now().hour
        # Ensure we're outside quiet hours
        quiet_start = (current_hour + 12) % 24
        quiet_end = (current_hour + 14) % 24

        current_time = time.time()

        # Default cooldown for price_alert is 1800s (30 min)
        # With low frequency it doubles to 3600s
        # We send notification 2500s ago, which is < 3600s so should be throttled
        with patch(
            "src.telegram_bot.smart_notifications.throttling.get_user_preferences",
            return_value={
                "123": {
                    "frequency": "low",  # Doubles cooldown
                    "quiet_hours": {"start": quiet_start, "end": quiet_end},
                    "last_notification": {
                        "price_alert": current_time - 2500,  # ~40 minutes ago
                    },
                }
            },
        ):
            result = awAlgot should_throttle_notification(
                user_id=123,
                notification_type="price_alert",
            )

        # Should be throttled (2500s < 3600s which is doubled cooldown from 1800)
        assert result is True

    @pytest.mark.asyncio()
    async def test_high_frequency_halves_cooldown(self) -> None:
        """Test that high frequency setting halves cooldown."""
        from datetime import datetime as dt

        from src.telegram_bot.smart_notifications.throttling import (
            should_throttle_notification,
        )

        current_hour = dt.now().hour
        # Ensure we're outside quiet hours
        quiet_start = (current_hour + 12) % 24
        quiet_end = (current_hour + 14) % 24

        current_time = time.time()

        with patch(
            "src.telegram_bot.smart_notifications.throttling.get_user_preferences",
            return_value={
                "123": {
                    "frequency": "high",  # Halves cooldown
                    "quiet_hours": {"start": quiet_start, "end": quiet_end},
                    "last_notification": {
                        "price_alert": current_time - 1000,  # ~17 minutes ago
                    },
                }
            },
        ):
            result = awAlgot should_throttle_notification(
                user_id=123,
                notification_type="price_alert",
            )

        # Should not be throttled (1000s > 900s which is halved cooldown from 1800s)
        assert result is False

    @pytest.mark.asyncio()
    async def test_with_item_id_creates_unique_key(self) -> None:
        """Test that item_id creates a unique history key."""
        from datetime import datetime as dt

        from src.telegram_bot.smart_notifications.throttling import (
            should_throttle_notification,
        )

        current_hour = dt.now().hour
        # Ensure we're outside quiet hours
        quiet_start = (current_hour + 12) % 24
        quiet_end = (current_hour + 14) % 24

        current_time = time.time()

        with patch(
            "src.telegram_bot.smart_notifications.throttling.get_user_preferences",
            return_value={
                "123": {
                    "quiet_hours": {"start": quiet_start, "end": quiet_end},
                    "last_notification": {
                        "price_alert:item_456": current_time - 60,  # Different item
                    },
                }
            },
        ):
            # Check for a different item
            result = awAlgot should_throttle_notification(
                user_id=123,
                notification_type="price_alert",
                item_id="item_123",
            )

        # Should not be throttled (different item key)
        assert result is False

    @pytest.mark.asyncio()
    async def test_new_user_no_throttle(self) -> None:
        """Test that new users without preferences are not throttled."""
        from src.telegram_bot.smart_notifications.throttling import (
            should_throttle_notification,
        )

        with patch(
            "src.telegram_bot.smart_notifications.throttling.get_user_preferences",
            return_value={},  # No preferences
        ):
            result = awAlgot should_throttle_notification(
                user_id=123,
                notification_type="price_alert",
            )

        assert result is False


# ============================================================================
# Tests for record_notification
# ============================================================================


class TestRecordNotification:
    """Tests for record_notification function."""

    @pytest.mark.asyncio()
    async def test_record_notification_updates_timestamp(self) -> None:
        """Test that record_notification updates last notification time."""
        from src.telegram_bot.smart_notifications.throttling import record_notification

        user_prefs = {
            "123": {
                "last_notification": {},
            }
        }

        with (
            patch(
                "src.telegram_bot.smart_notifications.throttling.get_user_preferences",
                return_value=user_prefs,
            ),
            patch(
                "src.telegram_bot.smart_notifications.throttling.save_user_preferences"
            ) as mock_save,
        ):
            awAlgot record_notification(
                user_id=123,
                notification_type="price_alert",
            )

        mock_save.assert_called_once()
        assert "price_alert" in user_prefs["123"]["last_notification"]

    @pytest.mark.asyncio()
    async def test_record_notification_with_item_id(self) -> None:
        """Test record_notification creates unique key with item_id."""
        from src.telegram_bot.smart_notifications.throttling import record_notification

        user_prefs = {
            "123": {
                "last_notification": {},
            }
        }

        with (
            patch(
                "src.telegram_bot.smart_notifications.throttling.get_user_preferences",
                return_value=user_prefs,
            ),
            patch(
                "src.telegram_bot.smart_notifications.throttling.save_user_preferences"
            ),
        ):
            awAlgot record_notification(
                user_id=123,
                notification_type="price_alert",
                item_id="item_123",
            )

        assert "price_alert:item_123" in user_prefs["123"]["last_notification"]

    @pytest.mark.asyncio()
    async def test_record_notification_creates_last_notification_dict(self) -> None:
        """Test record_notification creates last_notification dict if missing."""
        from src.telegram_bot.smart_notifications.throttling import record_notification

        user_prefs = {"123": {}}  # No last_notification key

        with (
            patch(
                "src.telegram_bot.smart_notifications.throttling.get_user_preferences",
                return_value=user_prefs,
            ),
            patch(
                "src.telegram_bot.smart_notifications.throttling.save_user_preferences"
            ),
        ):
            awAlgot record_notification(
                user_id=123,
                notification_type="market_opportunity",
            )

        assert "last_notification" in user_prefs["123"]
        assert "market_opportunity" in user_prefs["123"]["last_notification"]

    @pytest.mark.asyncio()
    async def test_record_notification_unknown_user(self) -> None:
        """Test record_notification with unknown user does nothing."""
        from src.telegram_bot.smart_notifications.throttling import record_notification

        user_prefs = {}  # No users

        with (
            patch(
                "src.telegram_bot.smart_notifications.throttling.get_user_preferences",
                return_value=user_prefs,
            ),
            patch(
                "src.telegram_bot.smart_notifications.throttling.save_user_preferences"
            ) as mock_save,
        ):
            awAlgot record_notification(
                user_id=123,
                notification_type="price_alert",
            )

        # Should not save if user not in preferences
        mock_save.assert_not_called()

    @pytest.mark.asyncio()
    async def test_record_notification_timestamp_is_current(self) -> None:
        """Test that recorded timestamp is approximately current time."""
        from src.telegram_bot.smart_notifications.throttling import record_notification

        user_prefs = {
            "123": {
                "last_notification": {},
            }
        }

        before_time = time.time()

        with (
            patch(
                "src.telegram_bot.smart_notifications.throttling.get_user_preferences",
                return_value=user_prefs,
            ),
            patch(
                "src.telegram_bot.smart_notifications.throttling.save_user_preferences"
            ),
        ):
            awAlgot record_notification(
                user_id=123,
                notification_type="price_alert",
            )

        after_time = time.time()

        recorded_time = user_prefs["123"]["last_notification"]["price_alert"]
        assert before_time <= recorded_time <= after_time
