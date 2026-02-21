"""Tests for Custom Alerts Module."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.telegram_bot.notifications.custom_alerts import (
    Alert,
    AlertCondition,
    AlertManager,
    AlertPriority,
    AlertStatus,
    AlertType,
    TriggeredAlert,
    get_alert_manager,
    init_alert_manager,
)


class TestAlertCondition:
    """Tests for alert conditions."""

    def test_above_condition(self):
        """Test ABOVE condition."""
        alert = Alert(
            alert_id="test1",
            user_id=123,
            alert_type=AlertType.PRICE_THRESHOLD,
            item_name="Test",
            condition=AlertCondition.ABOVE,
            target_value=Decimal("100.0"),
        )

        assert alert.check_condition(Decimal("101.0")) is True
        assert alert.check_condition(Decimal("100.0")) is False
        assert alert.check_condition(Decimal("99.0")) is False

    def test_below_condition(self):
        """Test BELOW condition."""
        alert = Alert(
            alert_id="test1",
            user_id=123,
            alert_type=AlertType.PRICE_THRESHOLD,
            item_name="Test",
            condition=AlertCondition.BELOW,
            target_value=Decimal("100.0"),
        )

        assert alert.check_condition(Decimal("99.0")) is True
        assert alert.check_condition(Decimal("100.0")) is False
        assert alert.check_condition(Decimal("101.0")) is False

    def test_equals_condition(self):
        """Test EQUALS condition."""
        alert = Alert(
            alert_id="test1",
            user_id=123,
            alert_type=AlertType.PRICE_THRESHOLD,
            item_name="Test",
            condition=AlertCondition.EQUALS,
            target_value=Decimal("100.0"),
        )

        assert alert.check_condition(Decimal("100.0")) is True
        assert alert.check_condition(Decimal("100.005")) is True  # Within 0.01
        assert alert.check_condition(Decimal("101.0")) is False

    def test_change_percent_condition(self):
        """Test CHANGE_PERCENT condition."""
        alert = Alert(
            alert_id="test1",
            user_id=123,
            alert_type=AlertType.PRICE_CHANGE,
            item_name="Test",
            condition=AlertCondition.CHANGE_PERCENT,
            target_value=Decimal("10.0"),  # 10% change
            reference_price=Decimal("100.0"),
        )

        # 10% change
        assert alert.check_condition(Decimal("110.0")) is True
        assert alert.check_condition(Decimal("90.0")) is True
        # 5% change (below threshold)
        assert alert.check_condition(Decimal("105.0")) is False


class TestAlert:
    """Tests for Alert dataclass."""

    def test_alert_creation(self):
        """Test alert creation."""
        alert = Alert(
            alert_id="test1",
            user_id=123,
            alert_type=AlertType.PRICE_THRESHOLD,
            item_name="AK-47 | Redline",
            condition=AlertCondition.BELOW,
            target_value=Decimal("50.0"),
        )

        assert alert.alert_id == "test1"
        assert alert.status == AlertStatus.ACTIVE
        assert alert.trigger_count == 0

    def test_alert_expiry(self):
        """Test alert expiry check."""
        # Not expired
        alert = Alert(
            alert_id="test1",
            user_id=123,
            alert_type=AlertType.PRICE_THRESHOLD,
            item_name="Test",
            condition=AlertCondition.BELOW,
            target_value=Decimal("50.0"),
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        assert alert.is_expired() is False

        # Expired
        alert.expires_at = datetime.now(UTC) - timedelta(days=1)
        assert alert.is_expired() is True

    def test_can_trigger(self):
        """Test can trigger check."""
        alert = Alert(
            alert_id="test1",
            user_id=123,
            alert_type=AlertType.PRICE_THRESHOLD,
            item_name="Test",
            condition=AlertCondition.BELOW,
            target_value=Decimal("50.0"),
        )

        assert alert.can_trigger() is True

        # Paused alert can't trigger
        alert.status = AlertStatus.PAUSED
        assert alert.can_trigger() is False

        # Recently triggered can't trigger agAlgon
        alert.status = AlertStatus.ACTIVE
        alert.last_triggered = datetime.now(UTC)
        assert alert.can_trigger(min_interval_seconds=60) is False

    def test_to_dict(self):
        """Test to dict conversion."""
        alert = Alert(
            alert_id="test1",
            user_id=123,
            alert_type=AlertType.PRICE_THRESHOLD,
            item_name="Test",
            condition=AlertCondition.BELOW,
            target_value=Decimal("50.0"),
        )

        data = alert.to_dict()
        assert "alert_id" in data
        assert "type" in data
        assert "condition" in data


class TestAlertManager:
    """Tests for AlertManager."""

    @pytest.fixture
    def manager(self):
        """Create test manager."""
        return AlertManager(user_id=123)

    def test_create_alert(self, manager):
        """Test creating alert."""
        alert = manager.create_alert(
            item_name="AK-47 | Redline",
            alert_type=AlertType.PRICE_THRESHOLD,
            condition=AlertCondition.BELOW,
            target_value=50.0,
        )

        assert alert is not None
        assert alert.item_name == "AK-47 | Redline"
        assert alert.user_id == 123

    def test_create_price_alert(self, manager):
        """Test creating price alert."""
        alert = manager.create_price_alert(
            item_name="Test Item",
            target_price=100.0,
            condition="below",
        )

        assert alert is not None
        assert alert.alert_type == AlertType.PRICE_THRESHOLD
        assert alert.condition == AlertCondition.BELOW

    def test_create_change_alert(self, manager):
        """Test creating change alert."""
        alert = manager.create_change_alert(
            item_name="Test Item",
            change_percent=10.0,
            reference_price=100.0,
        )

        assert alert is not None
        assert alert.alert_type == AlertType.PRICE_CHANGE
        assert alert.condition == AlertCondition.CHANGE_PERCENT

    def test_create_arbitrage_alert(self, manager):
        """Test creating arbitrage alert."""
        alert = manager.create_arbitrage_alert(
            item_name="Test Item",
            min_profit_percent=5.0,
        )

        assert alert is not None
        assert alert.alert_type == AlertType.ARBITRAGE
        assert alert.priority == AlertPriority.HIGH

    def test_get_alert(self, manager):
        """Test getting alert by ID."""
        alert = manager.create_price_alert("Test", 100.0)
        assert alert is not None

        retrieved = manager.get_alert(alert.alert_id)
        assert retrieved is not None
        assert retrieved.alert_id == alert.alert_id

    def test_get_user_alerts(self, manager):
        """Test getting user alerts."""
        manager.create_price_alert("Item1", 50.0)
        manager.create_price_alert("Item2", 100.0)

        alerts = manager.get_user_alerts()
        assert len(alerts) == 2

    def test_alert_limit(self, manager):
        """Test alert limit enforcement."""
        manager.config.max_alerts_per_user = 2

        alert1 = manager.create_price_alert("Item1", 50.0)
        alert2 = manager.create_price_alert("Item2", 100.0)
        alert3 = manager.create_price_alert("Item3", 150.0)

        assert alert1 is not None
        assert alert2 is not None
        assert alert3 is None  # Limit reached

    def test_update_alert(self, manager):
        """Test updating alert."""
        alert = manager.create_price_alert("Test", 100.0)
        assert alert is not None

        success = manager.update_alert(
            alert.alert_id,
            target_value=150.0,
            priority=AlertPriority.HIGH,
        )

        assert success is True
        updated = manager.get_alert(alert.alert_id)
        assert updated is not None
        assert updated.target_value == Decimal("150.0")
        assert updated.priority == AlertPriority.HIGH

    def test_delete_alert(self, manager):
        """Test deleting alert."""
        alert = manager.create_price_alert("Test", 100.0)
        assert alert is not None

        success = manager.delete_alert(alert.alert_id)
        assert success is True

        retrieved = manager.get_alert(alert.alert_id)
        assert retrieved is None

    def test_pause_resume_alert(self, manager):
        """Test pausing and resuming alert."""
        alert = manager.create_price_alert("Test", 100.0)
        assert alert is not None

        # Pause
        manager.pause_alert(alert.alert_id)
        paused = manager.get_alert(alert.alert_id)
        assert paused is not None
        assert paused.status == AlertStatus.PAUSED

        # Resume
        manager.resume_alert(alert.alert_id)
        resumed = manager.get_alert(alert.alert_id)
        assert resumed is not None
        assert resumed.status == AlertStatus.ACTIVE


class TestAlertChecking:
    """Tests for alert checking."""

    @pytest.fixture
    def manager(self):
        """Create test manager."""
        return AlertManager(user_id=123)

    @pytest.mark.asyncio
    async def test_check_alerts_triggers(self, manager):
        """Test alert checking triggers correctly."""
        manager.create_price_alert(
            item_name="Test Item",
            target_price=100.0,
            condition="below",
        )

        prices = {"Test Item": Decimal("90.0")}  # Below target
        triggered = awAlgot manager.check_alerts(prices)

        assert len(triggered) == 1
        assert triggered[0].current_value == Decimal("90.0")

    @pytest.mark.asyncio
    async def test_check_alerts_no_trigger(self, manager):
        """Test alert checking doesn't trigger when condition not met."""
        manager.create_price_alert(
            item_name="Test Item",
            target_price=100.0,
            condition="below",
        )

        prices = {"Test Item": Decimal("110.0")}  # Above target
        triggered = awAlgot manager.check_alerts(prices)

        assert len(triggered) == 0

    @pytest.mark.asyncio
    async def test_rate_limiting(self, manager):
        """Test rate limiting of triggers."""
        manager.config.min_trigger_interval_seconds = 60

        alert = manager.create_price_alert("Test", 100.0, condition="below")
        assert alert is not None

        prices = {"Test": Decimal("90.0")}

        # First trigger
        triggered1 = awAlgot manager.check_alerts(prices)
        assert len(triggered1) == 1

        # Second trigger (should be rate limited)
        triggered2 = awAlgot manager.check_alerts(prices)
        assert len(triggered2) == 0  # Rate limited


class TestTriggeredAlert:
    """Tests for TriggeredAlert."""

    def test_triggered_alert_creation(self):
        """Test triggered alert creation."""
        alert = Alert(
            alert_id="test1",
            user_id=123,
            alert_type=AlertType.PRICE_THRESHOLD,
            item_name="Test",
            condition=AlertCondition.BELOW,
            target_value=Decimal("50.0"),
        )

        triggered = TriggeredAlert(
            alert=alert,
            triggered_at=datetime.now(UTC),
            current_value=Decimal("45.0"),
            message="Price dropped!",
        )

        assert triggered.alert.alert_id == "test1"
        assert triggered.current_value == Decimal("45.0")

    def test_to_dict(self):
        """Test to dict conversion."""
        alert = Alert(
            alert_id="test1",
            user_id=123,
            alert_type=AlertType.PRICE_THRESHOLD,
            item_name="Test",
            condition=AlertCondition.BELOW,
            target_value=Decimal("50.0"),
        )

        triggered = TriggeredAlert(
            alert=alert,
            triggered_at=datetime.now(UTC),
            current_value=Decimal("45.0"),
            message="Price dropped!",
        )

        data = triggered.to_dict()
        assert "alert_id" in data
        assert "current_value" in data
        assert "message" in data


class TestMessageGeneration:
    """Tests for message generation."""

    @pytest.fixture
    def manager(self):
        """Create test manager."""
        return AlertManager(user_id=123)

    def test_below_message(self, manager):
        """Test message for BELOW condition."""
        alert = Alert(
            alert_id="test1",
            user_id=123,
            alert_type=AlertType.PRICE_THRESHOLD,
            item_name="AK-47",
            condition=AlertCondition.BELOW,
            target_value=Decimal("50.0"),
            priority=AlertPriority.HIGH,
        )

        message = manager._generate_message(alert, Decimal("45.0"))
        assert "AK-47" in message
        assert "45" in message

    def test_custom_template(self, manager):
        """Test custom message template."""
        alert = Alert(
            alert_id="test1",
            user_id=123,
            alert_type=AlertType.PRICE_THRESHOLD,
            item_name="Test",
            condition=AlertCondition.BELOW,
            target_value=Decimal("50.0"),
            message_template="Custom: {item_name} at ${current}",
        )

        message = manager._generate_message(alert, Decimal("45.0"))
        assert message == "Custom: Test at $45.0"


class TestAlertStats:
    """Tests for alert statistics."""

    @pytest.fixture
    def manager(self):
        """Create test manager."""
        return AlertManager(user_id=123)

    def test_get_stats(self, manager):
        """Test getting statistics."""
        manager.create_price_alert("Item1", 50.0)
        manager.create_price_alert("Item2", 100.0)
        manager.create_arbitrage_alert("Item3", 5.0)

        stats = manager.get_stats()

        assert stats["total_alerts"] == 3
        assert stats["active_alerts"] == 3
        assert "by_type" in stats
        assert "by_priority" in stats


class TestGlobalFunctions:
    """Tests for global functions."""

    def test_init_alert_manager(self):
        """Test initializing global manager."""
        manager = init_alert_manager(user_id=456)
        assert manager.default_user_id == 456

    def test_get_alert_manager(self):
        """Test getting global manager."""
        init_alert_manager(user_id=789)
        manager = get_alert_manager()
        assert manager is not None
