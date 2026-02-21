"""Unit tests for notification digest handler.

This module tests src/telegram_bot/handlers/notification_digest_handler.py covering:
- NotificationDigestManager class methods
- DigestSettings and NotificationItem dataclasses
- Digest menu display
- Digest toggle functionality
- Frequency settings
- Grouping mode settings
- Minimum items configuration
- Settings reset
- Digest formatting and grouping

Target: 40+ tests to achieve 70%+ coverage
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import CallbackQuery, Update
from telegram.ext import ContextTypes

from src.telegram_bot.handlers.notification_digest_handler import (
    DigestFrequency,
    DigestSettings,
    GroupingMode,
    NotificationDigestManager,
    NotificationItem,
    digest_command,
    get_digest_manager,
    reset_digest_settings,
    set_frequency,
    set_grouping_mode,
    set_min_items,
    show_digest_menu,
    show_frequency_menu,
    show_grouping_menu,
    show_min_items_menu,
    toggle_digest,
)

# Test fixtures


@pytest.fixture()
def mock_update():
    """Fixture providing a mocked Update."""
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=123456789, username="test_user")
    update.effective_chat = MagicMock(id=123456789)
    update.callback_query = MagicMock(spec=CallbackQuery)
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.data = "digest_menu"
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture()
def mock_context():
    """Fixture providing a mocked Context."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    return context


@pytest.fixture()
def digest_manager():
    """Fixture providing a fresh NotificationDigestManager instance."""
    return NotificationDigestManager()


@pytest.fixture()
def sample_notification():
    """Fixture providing a sample NotificationItem."""
    return NotificationItem(
        user_id=123456789,
        notification_type="arbitrage",
        game="csgo",
        title="Test Item",
        message="Test arbitrage opportunity",
        timestamp=datetime.now(),
        priority=2,
    )


# =============================================================================
# Tests for NotificationDigestManager
# =============================================================================


class TestNotificationDigestManager:
    """Tests for NotificationDigestManager class."""

    def test_init_creates_empty_storage(self):
        """Test manager initializes with empty storage."""
        manager = NotificationDigestManager()
        assert manager._pending_notifications == {}
        assert manager._user_settings == {}
        assert manager._scheduler_task is None

    def test_get_user_settings_creates_default(self, digest_manager):
        """Test get_user_settings creates default settings for new user."""
        user_id = 123
        settings = digest_manager.get_user_settings(user_id)

        assert isinstance(settings, DigestSettings)
        assert settings.enabled is False
        assert settings.frequency == DigestFrequency.DAlgoLY
        assert settings.grouping_mode == GroupingMode.BY_TYPE
        assert settings.min_items == 3
        assert settings.last_sent is None

    def test_get_user_settings_returns_existing(self, digest_manager):
        """Test get_user_settings returns existing settings."""
        user_id = 123
        # Create initial settings
        digest_manager.get_user_settings(user_id)
        # Update enabled status
        digest_manager.update_user_settings(user_id, {"enabled": True})

        # Get settings agAlgon
        settings = digest_manager.get_user_settings(user_id)
        assert settings.enabled is True

    def test_update_user_settings_enabled(self, digest_manager):
        """Test updating enabled setting."""
        user_id = 123
        digest_manager.update_user_settings(user_id, {"enabled": True})

        settings = digest_manager.get_user_settings(user_id)
        assert settings.enabled is True

    def test_update_user_settings_frequency(self, digest_manager):
        """Test updating frequency setting."""
        user_id = 123
        digest_manager.update_user_settings(
            user_id, {"frequency": DigestFrequency.HOURLY}
        )

        settings = digest_manager.get_user_settings(user_id)
        assert settings.frequency == DigestFrequency.HOURLY

    def test_update_user_settings_grouping_mode(self, digest_manager):
        """Test updating grouping mode setting."""
        user_id = 123
        digest_manager.update_user_settings(
            user_id, {"grouping_mode": GroupingMode.BY_GAME}
        )

        settings = digest_manager.get_user_settings(user_id)
        assert settings.grouping_mode == GroupingMode.BY_GAME

    def test_update_user_settings_min_items(self, digest_manager):
        """Test updating min_items setting."""
        user_id = 123
        digest_manager.update_user_settings(user_id, {"min_items": 10})

        settings = digest_manager.get_user_settings(user_id)
        assert settings.min_items == 10

    def test_update_user_settings_multiple(self, digest_manager):
        """Test updating multiple settings at once."""
        user_id = 123
        digest_manager.update_user_settings(
            user_id,
            {
                "enabled": True,
                "frequency": DigestFrequency.WEEKLY,
                "min_items": 5,
            },
        )

        settings = digest_manager.get_user_settings(user_id)
        assert settings.enabled is True
        assert settings.frequency == DigestFrequency.WEEKLY
        assert settings.min_items == 5

    def test_reset_user_settings(self, digest_manager):
        """Test resetting user settings to defaults."""
        user_id = 123
        # Set non-default values
        digest_manager.update_user_settings(
            user_id,
            {
                "enabled": True,
                "frequency": DigestFrequency.HOURLY,
                "min_items": 20,
            },
        )

        # Reset
        digest_manager.reset_user_settings(user_id)

        settings = digest_manager.get_user_settings(user_id)
        assert settings.enabled is False
        assert settings.frequency == DigestFrequency.DAlgoLY
        assert settings.min_items == 3

    def test_add_notification_when_disabled(self, digest_manager, sample_notification):
        """Test that notifications are not added when digest is disabled."""
        # Default is disabled
        digest_manager.add_notification(sample_notification)

        pending = digest_manager.get_pending_notifications(sample_notification.user_id)
        assert len(pending) == 0

    def test_add_notification_when_enabled(self, digest_manager, sample_notification):
        """Test that notifications are added when digest is enabled."""
        digest_manager.update_user_settings(
            sample_notification.user_id, {"enabled": True}
        )
        digest_manager.add_notification(sample_notification)

        pending = digest_manager.get_pending_notifications(sample_notification.user_id)
        assert len(pending) == 1
        assert pending[0] == sample_notification

    def test_add_multiple_notifications(self, digest_manager):
        """Test adding multiple notifications."""
        user_id = 123
        digest_manager.update_user_settings(user_id, {"enabled": True})

        for i in range(5):
            notification = NotificationItem(
                user_id=user_id,
                notification_type="arbitrage",
                game="csgo",
                title=f"Item {i}",
                message=f"Message {i}",
                timestamp=datetime.now(),
            )
            digest_manager.add_notification(notification)

        pending = digest_manager.get_pending_notifications(user_id)
        assert len(pending) == 5

    def test_get_pending_notifications_empty(self, digest_manager):
        """Test getting pending notifications for user with none."""
        pending = digest_manager.get_pending_notifications(999)
        assert pending == []

    def test_clear_pending_notifications(self, digest_manager):
        """Test clearing pending notifications."""
        user_id = 123
        digest_manager.update_user_settings(user_id, {"enabled": True})

        # Add some notifications
        for i in range(3):
            notification = NotificationItem(
                user_id=user_id,
                notification_type="arbitrage",
                game="csgo",
                title=f"Item {i}",
                message=f"Message {i}",
                timestamp=datetime.now(),
            )
            digest_manager.add_notification(notification)

        # Verify they exist
        assert len(digest_manager.get_pending_notifications(user_id)) == 3

        # Clear
        digest_manager.clear_pending_notifications(user_id)

        # Verify cleared
        assert len(digest_manager.get_pending_notifications(user_id)) == 0

    def test_clear_pending_notifications_nonexistent_user(self, digest_manager):
        """Test clearing notifications for nonexistent user (no error)."""
        # Should not rAlgose any error
        digest_manager.clear_pending_notifications(999)


class TestShouldSendDigest:
    """Tests for should_send_digest method."""

    def test_should_send_when_disabled(self, digest_manager):
        """Test should_send returns False when disabled."""
        user_id = 123
        # Default is disabled
        assert digest_manager.should_send_digest(user_id) is False

    def test_should_send_insufficient_notifications(self, digest_manager):
        """Test should_send returns False with insufficient notifications."""
        user_id = 123
        digest_manager.update_user_settings(user_id, {"enabled": True, "min_items": 5})

        # Add only 2 notifications (less than min_items=5)
        for i in range(2):
            notification = NotificationItem(
                user_id=user_id,
                notification_type="arbitrage",
                game="csgo",
                title=f"Item {i}",
                message=f"Message {i}",
                timestamp=datetime.now(),
            )
            digest_manager.add_notification(notification)

        assert digest_manager.should_send_digest(user_id) is False

    def test_should_send_first_time(self, digest_manager):
        """Test should_send returns True for first digest."""
        user_id = 123
        digest_manager.update_user_settings(user_id, {"enabled": True, "min_items": 2})

        # Add enough notifications
        for i in range(3):
            notification = NotificationItem(
                user_id=user_id,
                notification_type="arbitrage",
                game="csgo",
                title=f"Item {i}",
                message=f"Message {i}",
                timestamp=datetime.now(),
            )
            digest_manager.add_notification(notification)

        assert digest_manager.should_send_digest(user_id) is True

    def test_should_send_respects_frequency_hourly(self, digest_manager):
        """Test should_send respects hourly frequency."""
        user_id = 123
        digest_manager.update_user_settings(
            user_id,
            {"enabled": True, "min_items": 1, "frequency": DigestFrequency.HOURLY},
        )

        # Add a notification
        notification = NotificationItem(
            user_id=user_id,
            notification_type="arbitrage",
            game="csgo",
            title="Item",
            message="Message",
            timestamp=datetime.now(),
        )
        digest_manager.add_notification(notification)

        # Set last_sent to 30 minutes ago (not enough time)
        settings = digest_manager.get_user_settings(user_id)
        settings.last_sent = datetime.now() - timedelta(minutes=30)

        assert digest_manager.should_send_digest(user_id) is False

        # Set last_sent to 2 hours ago (enough time)
        settings.last_sent = datetime.now() - timedelta(hours=2)

        assert digest_manager.should_send_digest(user_id) is True

    def test_should_send_respects_frequency_dAlgoly(self, digest_manager):
        """Test should_send respects dAlgoly frequency."""
        user_id = 123
        digest_manager.update_user_settings(
            user_id,
            {"enabled": True, "min_items": 1, "frequency": DigestFrequency.DAlgoLY},
        )

        notification = NotificationItem(
            user_id=user_id,
            notification_type="arbitrage",
            game="csgo",
            title="Item",
            message="Message",
            timestamp=datetime.now(),
        )
        digest_manager.add_notification(notification)

        # Set last_sent to 12 hours ago (not enough)
        settings = digest_manager.get_user_settings(user_id)
        settings.last_sent = datetime.now() - timedelta(hours=12)

        assert digest_manager.should_send_digest(user_id) is False

        # Set last_sent to 25 hours ago (enough)
        settings.last_sent = datetime.now() - timedelta(hours=25)

        assert digest_manager.should_send_digest(user_id) is True


class TestFormatDigest:
    """Tests for format_digest method."""

    def test_format_empty_notifications(self, digest_manager):
        """Test formatting with no notifications."""
        user_id = 123
        formatted = digest_manager.format_digest(user_id, [])
        # Verify empty state message is returned (could be in any language)
        assert len(formatted) > 0  # Non-empty message returned

    def test_format_with_notifications(self, digest_manager):
        """Test formatting with notifications."""
        user_id = 123
        notifications = [
            NotificationItem(
                user_id=user_id,
                notification_type="arbitrage",
                game="csgo",
                title="AK-47",
                message="Арбитраж: AK-47 | Redline",
                timestamp=datetime.now(),
            ),
            NotificationItem(
                user_id=user_id,
                notification_type="price_drop",
                game="dota2",
                title="Arcana",
                message="Цена упала на 10%",
                timestamp=datetime.now(),
            ),
        ]

        formatted = digest_manager.format_digest(user_id, notifications)

        assert "Дайджест уведомлений" in formatted
        assert "2 уведомлений" in formatted

    def test_format_groups_by_type(self, digest_manager):
        """Test formatting groups notifications by type."""
        user_id = 123
        digest_manager.update_user_settings(
            user_id, {"grouping_mode": GroupingMode.BY_TYPE}
        )

        notifications = [
            NotificationItem(
                user_id=user_id,
                notification_type="arbitrage",
                game="csgo",
                title="Item 1",
                message="Arbitrage 1",
                timestamp=datetime.now(),
            ),
            NotificationItem(
                user_id=user_id,
                notification_type="arbitrage",
                game="dota2",
                title="Item 2",
                message="Arbitrage 2",
                timestamp=datetime.now(),
            ),
            NotificationItem(
                user_id=user_id,
                notification_type="price_drop",
                game="csgo",
                title="Item 3",
                message="Price drop",
                timestamp=datetime.now(),
            ),
        ]

        formatted = digest_manager.format_digest(user_id, notifications)

        # Should contAlgon group headers
        assert "Арбитраж" in formatted
        assert "Падение цены" in formatted

    def test_format_groups_by_game(self, digest_manager):
        """Test formatting groups notifications by game."""
        user_id = 123
        digest_manager.update_user_settings(
            user_id, {"grouping_mode": GroupingMode.BY_GAME}
        )

        notifications = [
            NotificationItem(
                user_id=user_id,
                notification_type="arbitrage",
                game="csgo",
                title="Item 1",
                message="CS:GO item",
                timestamp=datetime.now(),
            ),
            NotificationItem(
                user_id=user_id,
                notification_type="price_drop",
                game="dota2",
                title="Item 2",
                message="Dota 2 item",
                timestamp=datetime.now(),
            ),
        ]

        formatted = digest_manager.format_digest(user_id, notifications)

        # Should contAlgon game headers
        assert "CS2" in formatted
        assert "Dota 2" in formatted


# =============================================================================
# Tests for DigestSettings dataclass
# =============================================================================


class TestDigestSettings:
    """Tests for DigestSettings dataclass."""

    def test_default_values(self):
        """Test default values of DigestSettings."""
        settings = DigestSettings()
        assert settings.enabled is False
        assert settings.frequency == DigestFrequency.DAlgoLY
        assert settings.grouping_mode == GroupingMode.BY_TYPE
        assert settings.min_items == 3
        assert settings.last_sent is None

    def test_custom_values(self):
        """Test creating DigestSettings with custom values."""
        now = datetime.now()
        settings = DigestSettings(
            enabled=True,
            frequency=DigestFrequency.HOURLY,
            grouping_mode=GroupingMode.BY_GAME,
            min_items=10,
            last_sent=now,
        )

        assert settings.enabled is True
        assert settings.frequency == DigestFrequency.HOURLY
        assert settings.grouping_mode == GroupingMode.BY_GAME
        assert settings.min_items == 10
        assert settings.last_sent == now


# =============================================================================
# Tests for NotificationItem dataclass
# =============================================================================


class TestNotificationItem:
    """Tests for NotificationItem dataclass."""

    def test_notification_item_creation(self):
        """Test creating NotificationItem."""
        item = NotificationItem(
            user_id=123,
            notification_type="arbitrage",
            game="csgo",
            title="Test Item",
            message="Test message",
            timestamp=datetime.now(),
            priority=2,
        )

        assert item.user_id == 123
        assert item.notification_type == "arbitrage"
        assert item.game == "csgo"
        assert item.priority == 2

    def test_notification_item_default_priority(self):
        """Test default priority value."""
        item = NotificationItem(
            user_id=123,
            notification_type="price_drop",
            game="dota2",
            title="Item",
            message="Message",
            timestamp=datetime.now(),
        )

        assert item.priority == 1

    def test_notification_item_with_data(self):
        """Test NotificationItem with additional data."""
        item = NotificationItem(
            user_id=123,
            notification_type="target",
            game="csgo",
            title="AK-47",
            message="Target reached",
            timestamp=datetime.now(),
            data={"price": 15.50, "target_id": "tgt_123"},
        )

        assert item.data["price"] == 15.50
        assert item.data["target_id"] == "tgt_123"

    def test_notification_item_default_data(self):
        """Test default data is empty dict."""
        item = NotificationItem(
            user_id=123,
            notification_type="arbitrage",
            game="csgo",
            title="Item",
            message="Message",
            timestamp=datetime.now(),
        )

        assert item.data == {}


# =============================================================================
# Tests for Handler Functions
# =============================================================================


class TestShowDigestMenu:
    """Tests for show_digest_menu function."""

    @pytest.mark.asyncio()
    async def test_show_menu_creates_keyboard(self, mock_update, mock_context):
        """Test that menu creates inline keyboard."""
        # Act
        awAlgot show_digest_menu(mock_update, mock_context)

        # Assert
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        assert call_args is not None
        assert "reply_markup" in call_args.kwargs

    @pytest.mark.asyncio()
    async def test_show_menu_displays_settings_info(self, mock_update, mock_context):
        """Test that menu shows settings information."""
        # Act
        awAlgot show_digest_menu(mock_update, mock_context)

        # Assert
        call_args = mock_update.callback_query.edit_message_text.call_args
        message_text = (
            call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
        )
        # Should contAlgon status info
        assert "Статус" in message_text
        assert "Частота" in message_text

    @pytest.mark.asyncio()
    async def test_show_menu_without_callback_query(self, mock_update, mock_context):
        """Test show_menu when called without callback query (from command)."""
        mock_update.callback_query = None

        # Act
        awAlgot show_digest_menu(mock_update, mock_context)

        # Assert
        mock_update.message.reply_text.assert_called_once()


class TestToggleDigest:
    """Tests for toggle_digest function."""

    @pytest.mark.asyncio()
    async def test_toggle_enables_digest(self, mock_update, mock_context):
        """Test toggling digest from disabled to enabled."""
        user_id = mock_update.effective_user.id
        manager = get_digest_manager()

        # Ensure disabled initially
        manager.reset_user_settings(user_id)
        assert manager.get_user_settings(user_id).enabled is False

        # Act
        awAlgot toggle_digest(mock_update, mock_context)

        # Assert
        assert manager.get_user_settings(user_id).enabled is True

    @pytest.mark.asyncio()
    async def test_toggle_disables_digest(self, mock_update, mock_context):
        """Test toggling digest from enabled to disabled."""
        user_id = mock_update.effective_user.id
        manager = get_digest_manager()

        # Enable first
        manager.update_user_settings(user_id, {"enabled": True})
        assert manager.get_user_settings(user_id).enabled is True

        # Act
        awAlgot toggle_digest(mock_update, mock_context)

        # Assert
        assert manager.get_user_settings(user_id).enabled is False


class TestFrequencySettings:
    """Tests for frequency settings functions."""

    @pytest.mark.asyncio()
    async def test_show_frequency_menu(self, mock_update, mock_context):
        """Test showing frequency selection menu."""
        # Act
        awAlgot show_frequency_menu(mock_update, mock_context)

        # Assert
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        message_text = (
            call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
        )
        assert "частот" in message_text.lower()

    @pytest.mark.asyncio()
    async def test_set_frequency_hourly(self, mock_update, mock_context):
        """Test setting hourly frequency."""
        user_id = mock_update.effective_user.id
        mock_update.callback_query.data = (
            f"digest_set_freq_{DigestFrequency.HOURLY.value}"
        )

        # Act
        awAlgot set_frequency(mock_update, mock_context)

        # Assert
        manager = get_digest_manager()
        assert manager.get_user_settings(user_id).frequency == DigestFrequency.HOURLY

    @pytest.mark.asyncio()
    async def test_set_frequency_dAlgoly(self, mock_update, mock_context):
        """Test setting dAlgoly frequency."""
        user_id = mock_update.effective_user.id
        mock_update.callback_query.data = (
            f"digest_set_freq_{DigestFrequency.DAlgoLY.value}"
        )

        # Act
        awAlgot set_frequency(mock_update, mock_context)

        # Assert
        manager = get_digest_manager()
        assert manager.get_user_settings(user_id).frequency == DigestFrequency.DAlgoLY

    @pytest.mark.asyncio()
    async def test_set_frequency_weekly(self, mock_update, mock_context):
        """Test setting weekly frequency."""
        user_id = mock_update.effective_user.id
        mock_update.callback_query.data = (
            f"digest_set_freq_{DigestFrequency.WEEKLY.value}"
        )

        # Act
        awAlgot set_frequency(mock_update, mock_context)

        # Assert
        manager = get_digest_manager()
        assert manager.get_user_settings(user_id).frequency == DigestFrequency.WEEKLY


class TestGroupingModeHandlers:
    """Tests for grouping mode handler functions."""

    @pytest.mark.asyncio()
    async def test_show_grouping_menu(self, mock_update, mock_context):
        """Test showing grouping mode menu."""
        # Act
        awAlgot show_grouping_menu(mock_update, mock_context)

        # Assert
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        message_text = (
            call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
        )
        assert "группировк" in message_text.lower()

    @pytest.mark.asyncio()
    async def test_set_grouping_by_type(self, mock_update, mock_context):
        """Test setting grouping by type."""
        user_id = mock_update.effective_user.id
        mock_update.callback_query.data = (
            f"digest_set_group_{GroupingMode.BY_TYPE.value}"
        )

        # Act
        awAlgot set_grouping_mode(mock_update, mock_context)

        # Assert
        manager = get_digest_manager()
        assert manager.get_user_settings(user_id).grouping_mode == GroupingMode.BY_TYPE

    @pytest.mark.asyncio()
    async def test_set_grouping_by_game(self, mock_update, mock_context):
        """Test setting grouping by game."""
        user_id = mock_update.effective_user.id
        mock_update.callback_query.data = (
            f"digest_set_group_{GroupingMode.BY_GAME.value}"
        )

        # Act
        awAlgot set_grouping_mode(mock_update, mock_context)

        # Assert
        manager = get_digest_manager()
        assert manager.get_user_settings(user_id).grouping_mode == GroupingMode.BY_GAME

    @pytest.mark.asyncio()
    async def test_set_grouping_by_priority(self, mock_update, mock_context):
        """Test setting grouping by priority."""
        user_id = mock_update.effective_user.id
        mock_update.callback_query.data = (
            f"digest_set_group_{GroupingMode.BY_PRIORITY.value}"
        )

        # Act
        awAlgot set_grouping_mode(mock_update, mock_context)

        # Assert
        manager = get_digest_manager()
        assert (
            manager.get_user_settings(user_id).grouping_mode == GroupingMode.BY_PRIORITY
        )


class TestMinItemsConfiguration:
    """Tests for minimum items configuration."""

    @pytest.mark.asyncio()
    async def test_show_min_items_menu(self, mock_update, mock_context):
        """Test showing minimum items menu."""
        # Act
        awAlgot show_min_items_menu(mock_update, mock_context)

        # Assert
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        message_text = (
            call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
        )
        assert "минимальное" in message_text.lower()

    @pytest.mark.asyncio()
    async def test_set_min_items_1(self, mock_update, mock_context):
        """Test setting minimum items to 1."""
        user_id = mock_update.effective_user.id
        mock_update.callback_query.data = "digest_set_min_1"

        # Act
        awAlgot set_min_items(mock_update, mock_context)

        # Assert
        manager = get_digest_manager()
        assert manager.get_user_settings(user_id).min_items == 1

    @pytest.mark.asyncio()
    async def test_set_min_items_3(self, mock_update, mock_context):
        """Test setting minimum items to 3."""
        user_id = mock_update.effective_user.id
        mock_update.callback_query.data = "digest_set_min_3"

        # Act
        awAlgot set_min_items(mock_update, mock_context)

        # Assert
        manager = get_digest_manager()
        assert manager.get_user_settings(user_id).min_items == 3

    @pytest.mark.asyncio()
    async def test_set_min_items_5(self, mock_update, mock_context):
        """Test setting minimum items to 5."""
        user_id = mock_update.effective_user.id
        mock_update.callback_query.data = "digest_set_min_5"

        # Act
        awAlgot set_min_items(mock_update, mock_context)

        # Assert
        manager = get_digest_manager()
        assert manager.get_user_settings(user_id).min_items == 5

    @pytest.mark.asyncio()
    async def test_set_min_items_10(self, mock_update, mock_context):
        """Test setting minimum items to 10."""
        user_id = mock_update.effective_user.id
        mock_update.callback_query.data = "digest_set_min_10"

        # Act
        awAlgot set_min_items(mock_update, mock_context)

        # Assert
        manager = get_digest_manager()
        assert manager.get_user_settings(user_id).min_items == 10


class TestResetSettings:
    """Tests for reset settings functionality."""

    @pytest.mark.asyncio()
    async def test_reset_restores_defaults(self, mock_update, mock_context):
        """Test that reset restores default settings."""
        user_id = mock_update.effective_user.id
        manager = get_digest_manager()

        # Set non-default values
        manager.update_user_settings(
            user_id,
            {
                "enabled": True,
                "frequency": DigestFrequency.WEEKLY,
                "grouping_mode": GroupingMode.BY_GAME,
                "min_items": 15,
            },
        )

        # Act
        awAlgot reset_digest_settings(mock_update, mock_context)

        # Assert - should be reset to defaults
        settings = manager.get_user_settings(user_id)
        assert settings.enabled is False
        assert settings.frequency == DigestFrequency.DAlgoLY
        assert settings.grouping_mode == GroupingMode.BY_TYPE
        assert settings.min_items == 3

    @pytest.mark.asyncio()
    async def test_reset_answers_callback(self, mock_update, mock_context):
        """Test that reset answers callback query."""
        # Act
        awAlgot reset_digest_settings(mock_update, mock_context)

        # Assert - answer is called at least once (may be called multiple times due to show_digest_menu)
        assert mock_update.callback_query.answer.called


class TestDigestCommand:
    """Tests for digest command handler."""

    @pytest.mark.asyncio()
    async def test_digest_command_sends_menu(self, mock_update, mock_context):
        """Test that /digest command shows menu."""
        # Ensure callback_query is None to simulate command
        mock_update.callback_query = None

        # Act
        awAlgot digest_command(mock_update, mock_context)

        # Assert
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "reply_markup" in call_args.kwargs

    @pytest.mark.asyncio()
    async def test_digest_command_without_user(self, mock_update, mock_context):
        """Test digest command without effective user."""
        mock_update.effective_user = None
        mock_update.callback_query = None

        # Act - should return early without error
        awAlgot digest_command(mock_update, mock_context)

        # Assert - no message sent
        mock_update.message.reply_text.assert_not_called()


# =============================================================================
# Tests for DigestFrequency enum
# =============================================================================


class TestDigestFrequencyEnum:
    """Tests for DigestFrequency enum."""

    def test_all_frequencies_exist(self):
        """Test all expected frequencies exist."""
        assert DigestFrequency.DISABLED.value == "disabled"
        assert DigestFrequency.HOURLY.value == "hourly"
        assert DigestFrequency.EVERY_3_HOURS.value == "every_3h"
        assert DigestFrequency.EVERY_6_HOURS.value == "every_6h"
        assert DigestFrequency.DAlgoLY.value == "dAlgoly"
        assert DigestFrequency.WEEKLY.value == "weekly"

    def test_frequency_count(self):
        """Test correct number of frequencies."""
        assert len(DigestFrequency) == 6


# =============================================================================
# Tests for GroupingMode enum
# =============================================================================


class TestGroupingModeEnum:
    """Tests for GroupingMode enum."""

    def test_all_modes_exist(self):
        """Test all expected grouping modes exist."""
        assert GroupingMode.BY_TYPE.value == "by_type"
        assert GroupingMode.BY_GAME.value == "by_game"
        assert GroupingMode.BY_PRIORITY.value == "by_priority"
        assert GroupingMode.CHRONOLOGICAL.value == "chronological"

    def test_mode_count(self):
        """Test correct number of grouping modes."""
        assert len(GroupingMode) == 4


# =============================================================================
# Tests for get_digest_manager function
# =============================================================================


class TestGetDigestManager:
    """Tests for get_digest_manager singleton function."""

    def test_returns_manager(self):
        """Test get_digest_manager returns a manager."""
        manager = get_digest_manager()
        assert isinstance(manager, NotificationDigestManager)

    def test_returns_same_instance(self):
        """Test get_digest_manager returns same instance (singleton)."""
        manager1 = get_digest_manager()
        manager2 = get_digest_manager()
        assert manager1 is manager2
