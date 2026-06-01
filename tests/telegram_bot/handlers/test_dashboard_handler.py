"""Tests for ScannerDashboard and dashboard_handler.

This module provides comprehensive tests for the dashboard Telegram handler.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.telegram_bot.handlers.dashboard_handler import (
    DASHBOARD_STATS,
    ScannerDashboard,
    format_stats_message,
    get_dashboard_keyboard,
    get_scanner_control_keyboard,
)


# ============================================================================
# ScannerDashboard Tests
# ============================================================================
class TestScannerDashboardInit:
    """Tests for ScannerDashboard initialization."""

    def test_init_defaults(self):
        """Test default initialization."""
        dashboard = ScannerDashboard()
        assert dashboard.active_scans == {}
        assert dashboard.scan_history == []
        assert dashboard.max_history == 50

    def test_init_empty_state(self):
        """Test initial state is empty."""
        dashboard = ScannerDashboard()
        assert len(dashboard.active_scans) == 0
        assert len(dashboard.scan_history) == 0


class TestAddScanResult:
    """Tests for add_scan_result method."""

    def test_add_single_result(self):
        """Test adding a single scan result."""
        dashboard = ScannerDashboard()
        scan_data = {"opportunities": [{"profit": 10.0}], "level": "boost"}

        dashboard.add_scan_result(user_id=123, scan_data=scan_data)

        assert len(dashboard.scan_history) == 1
        assert dashboard.scan_history[0]["user_id"] == 123
        assert dashboard.scan_history[0]["data"] == scan_data

    def test_add_multiple_results(self):
        """Test adding multiple scan results."""
        dashboard = ScannerDashboard()

        for i in range(5):
            dashboard.add_scan_result(user_id=i, scan_data={"index": i})

        assert len(dashboard.scan_history) == 5

    def test_results_inserted_at_start(self):
        """Test newest results are at the start."""
        dashboard = ScannerDashboard()

        dashboard.add_scan_result(user_id=1, scan_data={"index": "first"})
        dashboard.add_scan_result(user_id=2, scan_data={"index": "second"})

        assert dashboard.scan_history[0]["data"]["index"] == "second"
        assert dashboard.scan_history[1]["data"]["index"] == "first"

    def test_history_limit_enforced(self):
        """Test history limit is enforced."""
        dashboard = ScannerDashboard()
        dashboard.max_history = 10

        for i in range(15):
            dashboard.add_scan_result(user_id=i, scan_data={"index": i})

        assert len(dashboard.scan_history) == 10

    def test_timestamp_added(self):
        """Test timestamp is added to scan result."""
        dashboard = ScannerDashboard()
        dashboard.add_scan_result(user_id=123, scan_data={})

        assert "timestamp" in dashboard.scan_history[0]
        assert isinstance(dashboard.scan_history[0]["timestamp"], datetime)


class TestGetUserStats:
    """Tests for get_user_stats method."""

    def test_empty_stats(self):
        """Test stats for user with no scans."""
        dashboard = ScannerDashboard()
        stats = dashboard.get_user_stats(user_id=999)

        assert stats["total_scans"] == 0
        assert stats["total_opportunities"] == 0
        assert stats["avg_profit"] == 0.0
        assert stats["max_profit"] == 0.0
        assert stats["last_scan_time"] is None

    def test_single_scan_stats(self):
        """Test stats with single scan."""
        dashboard = ScannerDashboard()
        dashboard.add_scan_result(
            user_id=123, scan_data={"opportunities": [{"profit": 15.0}]}
        )

        stats = dashboard.get_user_stats(user_id=123)

        assert stats["total_scans"] == 1
        assert stats["total_opportunities"] == 1
        assert stats["avg_profit"] == 15.0
        assert stats["max_profit"] == 15.0

    def test_multiple_scans_stats(self):
        """Test stats with multiple scans."""
        dashboard = ScannerDashboard()

        dashboard.add_scan_result(
            user_id=123,
            scan_data={"opportunities": [{"profit": 10.0}, {"profit": 20.0}]},
        )
        dashboard.add_scan_result(
            user_id=123, scan_data={"opportunities": [{"profit": 30.0}]}
        )

        stats = dashboard.get_user_stats(user_id=123)

        assert stats["total_scans"] == 2
        assert stats["total_opportunities"] == 3
        assert stats["avg_profit"] == 20.0  # (10+20+30)/3
        assert stats["max_profit"] == 30.0

    def test_stats_filters_by_user(self):
        """Test stats only include user's scans."""
        dashboard = ScannerDashboard()

        dashboard.add_scan_result(
            user_id=123, scan_data={"opportunities": [{"profit": 10.0}]}
        )
        dashboard.add_scan_result(
            user_id=456, scan_data={"opportunities": [{"profit": 50.0}]}
        )

        stats = dashboard.get_user_stats(user_id=123)

        assert stats["total_scans"] == 1
        assert stats["max_profit"] == 10.0

    def test_last_scan_time(self):
        """Test last scan time is recorded."""
        dashboard = ScannerDashboard()
        dashboard.add_scan_result(user_id=123, scan_data={})

        stats = dashboard.get_user_stats(user_id=123)

        assert stats["last_scan_time"] is not None
        assert isinstance(stats["last_scan_time"], datetime)


class TestMarkScanActive:
    """Tests for mark_scan_active method."""

    def test_mark_active(self):
        """Test marking scan as active."""
        dashboard = ScannerDashboard()

        dashboard.mark_scan_active(
            user_id=123, scan_id="scan_001", level="boost", game="csgo"
        )

        assert 123 in dashboard.active_scans
        assert dashboard.active_scans[123]["scan_id"] == "scan_001"
        assert dashboard.active_scans[123]["level"] == "boost"
        assert dashboard.active_scans[123]["game"] == "csgo"
        assert dashboard.active_scans[123]["status"] == "running"

    def test_mark_active_includes_timestamp(self):
        """Test active scan includes timestamp."""
        dashboard = ScannerDashboard()

        dashboard.mark_scan_active(
            user_id=123, scan_id="scan_001", level="boost", game="csgo"
        )

        assert "started_at" in dashboard.active_scans[123]
        assert isinstance(dashboard.active_scans[123]["started_at"], datetime)

    def test_mark_active_replaces_previous(self):
        """Test marking active replaces previous scan."""
        dashboard = ScannerDashboard()

        dashboard.mark_scan_active(
            user_id=123, scan_id="first", level="boost", game="csgo"
        )
        dashboard.mark_scan_active(
            user_id=123, scan_id="second", level="standard", game="dota2"
        )

        assert dashboard.active_scans[123]["scan_id"] == "second"
        assert dashboard.active_scans[123]["level"] == "standard"


class TestMarkScanComplete:
    """Tests for mark_scan_complete method."""

    def test_mark_complete(self):
        """Test marking scan as complete."""
        dashboard = ScannerDashboard()
        dashboard.mark_scan_active(
            user_id=123, scan_id="scan_001", level="boost", game="csgo"
        )

        dashboard.mark_scan_complete(user_id=123)

        assert dashboard.active_scans[123]["status"] == "completed"
        assert "completed_at" in dashboard.active_scans[123]

    def test_mark_complete_nonexistent(self):
        """Test marking complete for nonexistent scan."""
        dashboard = ScannerDashboard()

        # Should not raise
        dashboard.mark_scan_complete(user_id=999)

        assert 999 not in dashboard.active_scans


class TestGetActiveScan:
    """Tests for get_active_scan method."""

    def test_get_active_scan(self):
        """Test getting active scan."""
        dashboard = ScannerDashboard()
        dashboard.mark_scan_active(
            user_id=123, scan_id="scan_001", level="boost", game="csgo"
        )

        active = dashboard.get_active_scan(user_id=123)

        assert active is not None
        assert active["scan_id"] == "scan_001"

    def test_get_active_scan_none(self):
        """Test getting active scan when none exists."""
        dashboard = ScannerDashboard()

        active = dashboard.get_active_scan(user_id=999)

        assert active is None


# ============================================================================
# get_dashboard_keyboard Tests
# ============================================================================
class TestGetDashboardKeyboard:
    """Tests for get_dashboard_keyboard function."""

    def test_returns_markup(self):
        """Test returns InlineKeyboardMarkup."""
        from telegram import InlineKeyboardMarkup

        keyboard = get_dashboard_keyboard()

        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_has_stats_button(self):
        """Test keyboard has stats button."""
        keyboard = get_dashboard_keyboard()

        # Check that keyboard has buttons
        found = False
        for row in keyboard.inline_keyboard:
            for button in row:
                if "Статистика" in button.text:
                    found = True
                    assert DASHBOARD_STATS in button.callback_data
        assert found

    def test_has_scanner_button(self):
        """Test keyboard has scanner button."""
        keyboard = get_dashboard_keyboard()

        found = False
        for row in keyboard.inline_keyboard:
            for button in row:
                if "Сканер" in button.text:
                    found = True
        assert found


# ============================================================================
# format_stats_message Tests
# ============================================================================
class TestFormatStatsMessage:
    """Tests for format_stats_message function."""

    def test_format_zero_stats(self):
        """Test formatting with zero stats."""
        stats = {
            "total_scans": 0,
            "total_opportunities": 0,
            "avg_profit": 0.0,
            "max_profit": 0.0,
            "last_scan_time": None,
        }

        message = format_stats_message(stats)

        assert "Всего сканирований: *0*" in message
        assert "Найдено возможностей: *0*" in message
        assert "Никогда" in message

    def test_format_with_stats(self):
        """Test formatting with actual stats."""
        stats = {
            "total_scans": 10,
            "total_opportunities": 25,
            "avg_profit": 15.50,
            "max_profit": 45.00,
            "last_scan_time": datetime.now(),
        }

        message = format_stats_message(stats)

        assert "Всего сканирований: *10*" in message
        assert "Найдено возможностей: *25*" in message
        assert "$15.50" in message
        assert "$45.00" in message

    def test_format_recent_scan(self):
        """Test formatting with recent scan time."""
        stats = {
            "total_scans": 1,
            "total_opportunities": 1,
            "avg_profit": 10.0,
            "max_profit": 10.0,
            "last_scan_time": datetime.now() - timedelta(seconds=30),
        }

        message = format_stats_message(stats)

        assert "Только что" in message

    def test_format_minutes_ago(self):
        """Test formatting with scan minutes ago."""
        stats = {
            "total_scans": 1,
            "total_opportunities": 1,
            "avg_profit": 10.0,
            "max_profit": 10.0,
            "last_scan_time": datetime.now() - timedelta(minutes=15),
        }

        message = format_stats_message(stats)

        assert "мин. назад" in message

    def test_format_hours_ago(self):
        """Test formatting with scan hours ago."""
        stats = {
            "total_scans": 1,
            "total_opportunities": 1,
            "avg_profit": 10.0,
            "max_profit": 10.0,
            "last_scan_time": datetime.now() - timedelta(hours=5),
        }

        message = format_stats_message(stats)

        assert "ч. назад" in message

    def test_format_days_ago(self):
        """Test formatting with scan days ago."""
        stats = {
            "total_scans": 1,
            "total_opportunities": 1,
            "avg_profit": 10.0,
            "max_profit": 10.0,
            "last_scan_time": datetime.now() - timedelta(days=3),
        }

        message = format_stats_message(stats)

        assert "дн. назад" in message


# ============================================================================
# get_scanner_control_keyboard Tests
# ============================================================================
class TestGetScannerControlKeyboard:
    """Tests for get_scanner_control_keyboard function."""

    def test_without_level(self):
        """Test keyboard without level selected."""
        keyboard = get_scanner_control_keyboard(level=None)

        # Should show level selection
        # Check for level buttons
        found_level_button = False
        for row in keyboard.inline_keyboard:
            for button in row:
                if "scanner_level_" in (button.callback_data or ""):
                    found_level_button = True
        assert found_level_button

    def test_with_level(self):
        """Test keyboard with level selected."""
        keyboard = get_scanner_control_keyboard(level="boost")

        # Should show scan controls
        found_start_button = False
        for row in keyboard.inline_keyboard:
            for button in row:
                if "Запустить" in button.text:
                    found_start_button = True
        assert found_start_button

    def test_back_button_present(self):
        """Test back button is always present."""
        keyboard = get_scanner_control_keyboard(level=None)

        found_back = False
        for row in keyboard.inline_keyboard:
            for button in row:
                if "Назад" in button.text:
                    found_back = True
        assert found_back


# ============================================================================
# Dashboard Callbacks Tests
# ============================================================================
class TestDashboardCallbacks:
    """Tests for dashboard callback handling."""

    @pytest.fixture()
    def mock_update(self):
        """Create mock update."""
        update = MagicMock()
        update.callback_query = MagicMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 123
        return update

    @pytest.fixture()
    def mock_context(self):
        """Create mock context."""
        return MagicMock()

    @pytest.mark.asyncio()
    async def test_show_dashboard_with_query(self, mock_update, mock_context):
        """Test show_dashboard with callback query."""
        from src.telegram_bot.handlers.dashboard_handler import show_dashboard

        await show_dashboard(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    async def test_show_dashboard_with_message(self, mock_context):
        """Test show_dashboard with message."""
        from src.telegram_bot.handlers.dashboard_handler import show_dashboard

        update = MagicMock()
        update.callback_query = None
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 123

        await show_dashboard(update, mock_context)

        update.message.reply_text.assert_called_once()


# ============================================================================
# Edge Cases Tests
# ============================================================================
class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_opportunities_list(self):
        """Test with empty opportunities list."""
        dashboard = ScannerDashboard()
        dashboard.add_scan_result(user_id=123, scan_data={"opportunities": []})

        stats = dashboard.get_user_stats(user_id=123)

        assert stats["total_opportunities"] == 0
        assert stats["avg_profit"] == 0.0

    def test_missing_profit_key(self):
        """Test with missing profit key in opportunities."""
        dashboard = ScannerDashboard()
        dashboard.add_scan_result(
            user_id=123,
            scan_data={"opportunities": [{"name": "item"}, {"profit": 10.0}]},
        )

        stats = dashboard.get_user_stats(user_id=123)

        # Should handle missing key gracefully
        assert stats["total_opportunities"] == 2

    def test_negative_profit(self):
        """Test with negative profit."""
        dashboard = ScannerDashboard()
        dashboard.add_scan_result(
            user_id=123, scan_data={"opportunities": [{"profit": -5.0}]}
        )

        stats = dashboard.get_user_stats(user_id=123)

        assert stats["avg_profit"] == -5.0

    def test_very_large_history(self):
        """Test with very large history."""
        dashboard = ScannerDashboard()
        dashboard.max_history = 5

        for i in range(100):
            dashboard.add_scan_result(user_id=123, scan_data={"index": i})

        assert len(dashboard.scan_history) == 5
        # Most recent should be last added
        assert dashboard.scan_history[0]["data"]["index"] == 99

    def test_concurrent_users(self):
        """Test with concurrent users."""
        dashboard = ScannerDashboard()

        for user_id in range(10):
            dashboard.mark_scan_active(
                user_id=user_id, scan_id=f"scan_{user_id}", level="boost", game="csgo"
            )

        assert len(dashboard.active_scans) == 10
        for user_id in range(10):
            assert dashboard.active_scans[user_id]["scan_id"] == f"scan_{user_id}"

    def test_stats_message_empty_dict(self):
        """Test stats message with empty dict."""
        message = format_stats_message({})

        assert "Всего сканирований: *0*" in message
        assert "Никогда" in message
