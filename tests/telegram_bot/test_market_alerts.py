"""Unit tests for src/telegram_bot/market_alerts.py.

Tests for MarketAlertsManager including:
- Initialization
- Subscriber management
- Alert thresholds
- Monitoring control
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMarketAlertsManagerInit:
    """Tests for MarketAlertsManager initialization."""

    def test_init_with_bot_and_api(self):
        """Test initialization with bot and API instances."""
        from src.telegram_bot.market_alerts import MarketAlertsManager

        mock_bot = MagicMock()
        mock_api = MagicMock()

        manager = MarketAlertsManager(mock_bot, mock_api)

        assert manager.bot is mock_bot
        assert manager.dmarket_api is mock_api

    def test_init_creates_subscriber_categories(self):
        """Test initialization creates subscriber categories."""
        from src.telegram_bot.market_alerts import MarketAlertsManager

        manager = MarketAlertsManager(MagicMock(), MagicMock())

        assert "price_changes" in manager.subscribers
        assert "trending" in manager.subscribers
        assert "volatility" in manager.subscribers
        assert "arbitrage" in manager.subscribers

    def test_init_subscriber_categories_are_empty_sets(self):
        """Test subscriber categories are empty sets."""
        from src.telegram_bot.market_alerts import MarketAlertsManager

        manager = MarketAlertsManager(MagicMock(), MagicMock())

        for category in manager.subscribers.values():
            assert isinstance(category, set)
            assert len(category) == 0

    def test_init_creates_active_alerts_dict(self):
        """Test initialization creates active alerts dictionary."""
        from src.telegram_bot.market_alerts import MarketAlertsManager

        manager = MarketAlertsManager(MagicMock(), MagicMock())

        assert "price_changes" in manager.active_alerts
        assert "trending" in manager.active_alerts
        assert "volatility" in manager.active_alerts
        assert "arbitrage" in manager.active_alerts

    def test_init_sets_default_thresholds(self):
        """Test initialization sets default alert thresholds."""
        from src.telegram_bot.market_alerts import MarketAlertsManager

        manager = MarketAlertsManager(MagicMock(), MagicMock())

        assert manager.alert_thresholds["price_change_percent"] == 15.0
        assert manager.alert_thresholds["trending_popularity"] == 50.0
        assert manager.alert_thresholds["volatility_threshold"] == 25.0
        assert manager.alert_thresholds["arbitrage_profit_percent"] == 10.0

    def test_init_sets_last_check_times_to_zero(self):
        """Test initialization sets last check times to zero."""
        from src.telegram_bot.market_alerts import MarketAlertsManager

        manager = MarketAlertsManager(MagicMock(), MagicMock())

        for check_time in manager.last_check_time.values():
            assert check_time == 0

    def test_init_sets_check_intervals(self):
        """Test initialization sets check intervals."""
        from src.telegram_bot.market_alerts import MarketAlertsManager

        manager = MarketAlertsManager(MagicMock(), MagicMock())

        assert manager.check_intervals["price_changes"] == 3600  # 1 hour
        assert manager.check_intervals["trending"] == 7200  # 2 hours
        assert manager.check_intervals["volatility"] == 14400  # 4 hours
        assert manager.check_intervals["arbitrage"] == 1800  # 30 minutes

    def test_init_running_flag_is_false(self):
        """Test initialization sets running flag to False."""
        from src.telegram_bot.market_alerts import MarketAlertsManager

        manager = MarketAlertsManager(MagicMock(), MagicMock())

        assert manager.running is False

    def test_init_background_task_is_none(self):
        """Test initialization sets background task to None."""
        from src.telegram_bot.market_alerts import MarketAlertsManager

        manager = MarketAlertsManager(MagicMock(), MagicMock())

        assert manager.background_task is None


class TestMarketAlertsManagerSubscribers:
    """Tests for subscriber management."""

    @pytest.fixture()
    def manager(self):
        """Create MarketAlertsManager instance."""
        from src.telegram_bot.market_alerts import MarketAlertsManager

        return MarketAlertsManager(MagicMock(), MagicMock())

    def test_subscribe_to_price_changes(self, manager):
        """Test subscribing user to price changes."""
        user_id = 123456

        manager.subscribers["price_changes"].add(user_id)

        assert user_id in manager.subscribers["price_changes"]

    def test_subscribe_to_multiple_categories(self, manager):
        """Test subscribing user to multiple categories."""
        user_id = 123456

        manager.subscribers["price_changes"].add(user_id)
        manager.subscribers["trending"].add(user_id)
        manager.subscribers["arbitrage"].add(user_id)

        assert user_id in manager.subscribers["price_changes"]
        assert user_id in manager.subscribers["trending"]
        assert user_id in manager.subscribers["arbitrage"]

    def test_unsubscribe_from_category(self, manager):
        """Test unsubscribing user from category."""
        user_id = 123456

        manager.subscribers["price_changes"].add(user_id)
        manager.subscribers["price_changes"].discard(user_id)

        assert user_id not in manager.subscribers["price_changes"]

    def test_multiple_users_in_same_category(self, manager):
        """Test multiple users in same category."""
        user_ids = [111, 222, 333]

        for user_id in user_ids:
            manager.subscribers["price_changes"].add(user_id)

        assert len(manager.subscribers["price_changes"]) == 3
        for user_id in user_ids:
            assert user_id in manager.subscribers["price_changes"]


class TestMarketAlertsManagerMonitoring:
    """Tests for monitoring control."""

    @pytest.fixture()
    def manager(self):
        """Create MarketAlertsManager instance."""
        from src.telegram_bot.market_alerts import MarketAlertsManager

        return MarketAlertsManager(MagicMock(), MagicMock())

    @pytest.mark.asyncio()
    async def test_start_monitoring_sets_running_flag(self, manager):
        """Test start_monitoring sets running flag."""
        with patch.object(manager, "_monitor_market", return_value=AsyncMock()):
            await manager.start_monitoring()

            assert manager.running is True

    @pytest.mark.asyncio()
    async def test_start_monitoring_when_already_running(self, manager):
        """Test start_monitoring when already running."""
        manager.running = True

        # Should return early without error
        await manager.start_monitoring()

        # Still running
        assert manager.running is True


class TestMarketAlertsManagerAlerts:
    """Tests for alert management."""

    @pytest.fixture()
    def manager(self):
        """Create MarketAlertsManager instance."""
        from src.telegram_bot.market_alerts import MarketAlertsManager

        return MarketAlertsManager(MagicMock(), MagicMock())

    def test_active_alerts_structure(self, manager):
        """Test active alerts has correct structure."""
        user_id = 123456

        # Add an alert
        manager.active_alerts["price_changes"][user_id] = [
            {"item_id": "item_1", "threshold": 10.0}
        ]

        assert user_id in manager.active_alerts["price_changes"]
        assert len(manager.active_alerts["price_changes"][user_id]) == 1

    def test_sent_alerts_tracking(self, manager):
        """Test sent alerts tracking structure."""
        user_id = 123456
        alert_key = "item_1_price_drop"

        # Initialize user's sent alerts
        manager.sent_alerts["price_changes"][user_id] = {alert_key: time.time()}

        assert alert_key in manager.sent_alerts["price_changes"][user_id]


class TestMarketAlertsManagerThresholds:
    """Tests for alert threshold configuration."""

    @pytest.fixture()
    def manager(self):
        """Create MarketAlertsManager instance."""
        from src.telegram_bot.market_alerts import MarketAlertsManager

        return MarketAlertsManager(MagicMock(), MagicMock())

    def test_modify_price_change_threshold(self, manager):
        """Test modifying price change threshold."""
        manager.alert_thresholds["price_change_percent"] = 20.0

        assert manager.alert_thresholds["price_change_percent"] == 20.0

    def test_modify_arbitrage_threshold(self, manager):
        """Test modifying arbitrage profit threshold."""
        manager.alert_thresholds["arbitrage_profit_percent"] = 15.0

        assert manager.alert_thresholds["arbitrage_profit_percent"] == 15.0

    def test_threshold_used_for_filtering(self, manager):
        """Test thresholds can be used for alert filtering."""
        price_change = 18.0
        threshold = manager.alert_thresholds["price_change_percent"]

        should_alert = price_change >= threshold

        assert should_alert is True

    def test_threshold_below_limit_no_alert(self, manager):
        """Test price below threshold doesn't trigger alert."""
        price_change = 10.0
        threshold = manager.alert_thresholds["price_change_percent"]

        should_alert = price_change >= threshold

        assert should_alert is False


class TestMarketAlertsManagerCheckIntervals:
    """Tests for check interval configuration."""

    @pytest.fixture()
    def manager(self):
        """Create MarketAlertsManager instance."""
        from src.telegram_bot.market_alerts import MarketAlertsManager

        return MarketAlertsManager(MagicMock(), MagicMock())

    def test_should_check_after_interval(self, manager):
        """Test check should occur after interval passes."""
        import time

        alert_type = "price_changes"
        interval = manager.check_intervals[alert_type]

        # Set last check to past
        manager.last_check_time[alert_type] = time.time() - interval - 1

        should_check = (time.time() - manager.last_check_time[alert_type]) >= interval

        assert should_check is True

    def test_should_not_check_before_interval(self, manager):
        """Test check should not occur before interval passes."""
        import time

        alert_type = "price_changes"
        interval = manager.check_intervals[alert_type]

        # Set last check to recent time
        manager.last_check_time[alert_type] = time.time()

        should_check = (time.time() - manager.last_check_time[alert_type]) >= interval

        assert should_check is False


class TestMarketAlertsManagerIntegration:
    """Integration tests for MarketAlertsManager."""

    def test_full_subscription_workflow(self):
        """Test complete subscription workflow."""
        from src.telegram_bot.market_alerts import MarketAlertsManager

        manager = MarketAlertsManager(MagicMock(), MagicMock())
        user_id = 123456

        # Subscribe to multiple categories
        manager.subscribers["price_changes"].add(user_id)
        manager.subscribers["arbitrage"].add(user_id)

        # Verify subscriptions
        assert user_id in manager.subscribers["price_changes"]
        assert user_id in manager.subscribers["arbitrage"]
        assert user_id not in manager.subscribers["trending"]

        # Unsubscribe from one
        manager.subscribers["price_changes"].discard(user_id)

        # Verify partial unsubscription
        assert user_id not in manager.subscribers["price_changes"]
        assert user_id in manager.subscribers["arbitrage"]

    def test_alert_creation_and_tracking(self):
        """Test creating and tracking alerts."""
        from src.telegram_bot.market_alerts import MarketAlertsManager

        manager = MarketAlertsManager(MagicMock(), MagicMock())
        user_id = 123456

        # Create alert
        alert = {
            "item_id": "csgo_item_001",
            "item_name": "AK-47 | Redline",
            "target_price": 25.0,
            "current_price": 30.0,
        }

        manager.active_alerts["price_changes"][user_id] = [alert]

        # Verify alert
        user_alerts = manager.active_alerts["price_changes"].get(user_id, [])
        assert len(user_alerts) == 1
        assert user_alerts[0]["item_id"] == "csgo_item_001"
