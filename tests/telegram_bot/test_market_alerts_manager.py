"""Comprehensive tests for MarketAlertsManager class.

Tests for src/telegram_bot/market_alerts.py covering:
- Initialization
- Subscription management (subscribe, unsubscribe, unsubscribe_all)
- Alert thresholds and intervals
- Background monitoring (start, stop)
- Alert checks (price_changes, trending, volatility, arbitrage)
- Sent alerts management
- Edge cases and error handling

Target: 50+ tests to achieve 70%+ coverage
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.telegram_bot.market_alerts import (
    MarketAlertsManager,
    get_alerts_manager,
)


@pytest.fixture()
def mock_bot():
    """Create mock Telegram bot."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture()
def mock_dmarket_api():
    """Create mock DMarket API client."""
    api = MagicMock()
    api._request = AsyncMock(return_value={})
    return api


@pytest.fixture()
def manager(mock_bot, mock_dmarket_api):
    """Create MarketAlertsManager instance."""
    return MarketAlertsManager(bot=mock_bot, dmarket_api=mock_dmarket_api)


class TestMarketAlertsManagerInit:
    """Tests for MarketAlertsManager initialization."""

    def test_init_creates_subscribers_dict(self, mock_bot, mock_dmarket_api):
        """Test that initialization creates subscribers dictionary."""
        manager = MarketAlertsManager(bot=mock_bot, dmarket_api=mock_dmarket_api)

        assert "price_changes" in manager.subscribers
        assert "trending" in manager.subscribers
        assert "volatility" in manager.subscribers
        assert "arbitrage" in manager.subscribers

    def test_init_creates_empty_subscriber_sets(self, mock_bot, mock_dmarket_api):
        """Test that subscriber sets are initially empty."""
        manager = MarketAlertsManager(bot=mock_bot, dmarket_api=mock_dmarket_api)

        for alert_type in manager.subscribers:
            assert isinstance(manager.subscribers[alert_type], set)
            assert len(manager.subscribers[alert_type]) == 0

    def test_init_sets_default_thresholds(self, mock_bot, mock_dmarket_api):
        """Test that default alert thresholds are set."""
        manager = MarketAlertsManager(bot=mock_bot, dmarket_api=mock_dmarket_api)

        assert manager.alert_thresholds["price_change_percent"] == 15.0
        assert manager.alert_thresholds["trending_popularity"] == 50.0
        assert manager.alert_thresholds["volatility_threshold"] == 25.0
        assert manager.alert_thresholds["arbitrage_profit_percent"] == 10.0

    def test_init_sets_default_check_intervals(self, mock_bot, mock_dmarket_api):
        """Test that default check intervals are set."""
        manager = MarketAlertsManager(bot=mock_bot, dmarket_api=mock_dmarket_api)

        assert manager.check_intervals["price_changes"] == 3600
        assert manager.check_intervals["trending"] == 7200
        assert manager.check_intervals["volatility"] == 14400
        assert manager.check_intervals["arbitrage"] == 1800

    def test_init_sets_running_to_false(self, mock_bot, mock_dmarket_api):
        """Test that running flag is initially false."""
        manager = MarketAlertsManager(bot=mock_bot, dmarket_api=mock_dmarket_api)

        assert manager.running is False
        assert manager.background_task is None

    def test_init_stores_bot_and_api(self, mock_bot, mock_dmarket_api):
        """Test that bot and API are stored correctly."""
        manager = MarketAlertsManager(bot=mock_bot, dmarket_api=mock_dmarket_api)

        assert manager.bot is mock_bot
        assert manager.dmarket_api is mock_dmarket_api


class TestMarketAlertsManagerSubscribe:
    """Tests for subscribe method."""

    def test_subscribe_adds_user(self, manager):
        """Test that subscribe adds user to set."""
        result = manager.subscribe(user_id=123456, alert_type="price_changes")

        assert result is True
        assert 123456 in manager.subscribers["price_changes"]

    def test_subscribe_returns_true_for_valid_type(self, manager):
        """Test that subscribe returns True for valid alert type."""
        result = manager.subscribe(user_id=123, alert_type="trending")

        assert result is True

    def test_subscribe_returns_false_for_invalid_type(self, manager):
        """Test that subscribe returns False for invalid alert type."""
        result = manager.subscribe(user_id=123, alert_type="invalid_type")

        assert result is False
        assert 123 not in manager.subscribers.get("invalid_type", set())

    def test_subscribe_multiple_users(self, manager):
        """Test subscribing multiple users."""
        manager.subscribe(123, "price_changes")
        manager.subscribe(456, "price_changes")
        manager.subscribe(789, "price_changes")

        assert len(manager.subscribers["price_changes"]) == 3

    def test_subscribe_same_user_twice(self, manager):
        """Test that subscribing same user twice doesn't duplicate."""
        manager.subscribe(123, "price_changes")
        manager.subscribe(123, "price_changes")

        assert len(manager.subscribers["price_changes"]) == 1

    def test_subscribe_to_all_types(self, manager):
        """Test subscribing to all alert types."""
        user_id = 12345
        for alert_type in ["price_changes", "trending", "volatility", "arbitrage"]:
            result = manager.subscribe(user_id, alert_type)
            assert result is True
            assert user_id in manager.subscribers[alert_type]


class TestMarketAlertsManagerUnsubscribe:
    """Tests for unsubscribe method."""

    def test_unsubscribe_removes_user(self, manager):
        """Test that unsubscribe removes user from set."""
        manager.subscribe(123, "price_changes")
        result = manager.unsubscribe(123, "price_changes")

        assert result is True
        assert 123 not in manager.subscribers["price_changes"]

    def test_unsubscribe_returns_false_for_non_subscribed_user(self, manager):
        """Test that unsubscribe returns False for non-subscribed user."""
        result = manager.unsubscribe(999, "price_changes")

        assert result is False

    def test_unsubscribe_returns_false_for_invalid_type(self, manager):
        """Test that unsubscribe returns False for invalid alert type."""
        result = manager.unsubscribe(123, "invalid_type")

        assert result is False

    def test_unsubscribe_does_not_affect_other_users(self, manager):
        """Test that unsubscribe doesn't affect other users."""
        manager.subscribe(123, "price_changes")
        manager.subscribe(456, "price_changes")
        manager.unsubscribe(123, "price_changes")

        assert 123 not in manager.subscribers["price_changes"]
        assert 456 in manager.subscribers["price_changes"]


class TestMarketAlertsManagerUnsubscribeAll:
    """Tests for unsubscribe_all method."""

    def test_unsubscribe_all_removes_from_all_types(self, manager):
        """Test that unsubscribe_all removes user from all types."""
        user_id = 123
        for alert_type in manager.subscribers:
            manager.subscribe(user_id, alert_type)

        result = manager.unsubscribe_all(user_id)

        assert result is True
        for alert_type in manager.subscribers:
            assert user_id not in manager.subscribers[alert_type]

    def test_unsubscribe_all_returns_false_if_not_subscribed(self, manager):
        """Test that unsubscribe_all returns False if user wasn't subscribed."""
        result = manager.unsubscribe_all(999)

        assert result is False

    def test_unsubscribe_all_returns_true_if_subscribed_to_any(self, manager):
        """Test that unsubscribe_all returns True if subscribed to any type."""
        manager.subscribe(123, "arbitrage")
        result = manager.unsubscribe_all(123)

        assert result is True


class TestMarketAlertsManagerGetUserSubscriptions:
    """Tests for get_user_subscriptions method."""

    def test_get_user_subscriptions_returns_empty_list(self, manager):
        """Test that get_user_subscriptions returns empty list for non-subscriber."""
        result = manager.get_user_subscriptions(999)

        assert result == []

    def test_get_user_subscriptions_returns_subscribed_types(self, manager):
        """Test that get_user_subscriptions returns all subscribed types."""
        manager.subscribe(123, "price_changes")
        manager.subscribe(123, "trending")

        result = manager.get_user_subscriptions(123)

        assert "price_changes" in result
        assert "trending" in result
        assert len(result) == 2

    def test_get_user_subscriptions_returns_all_types_when_subscribed(self, manager):
        """Test get_user_subscriptions when user subscribes to all types."""
        user_id = 123
        for alert_type in manager.subscribers:
            manager.subscribe(user_id, alert_type)

        result = manager.get_user_subscriptions(user_id)

        assert len(result) == 4


class TestMarketAlertsManagerGetSubscriptionCount:
    """Tests for get_subscription_count method."""

    def test_get_subscription_count_returns_zero_initially(self, manager):
        """Test that subscription count is zero initially."""
        result = manager.get_subscription_count("price_changes")

        assert result == 0

    def test_get_subscription_count_returns_correct_count(self, manager):
        """Test that subscription count returns correct number."""
        manager.subscribe(123, "price_changes")
        manager.subscribe(456, "price_changes")
        manager.subscribe(789, "price_changes")

        result = manager.get_subscription_count("price_changes")

        assert result == 3

    def test_get_subscription_count_returns_zero_for_invalid_type(self, manager):
        """Test that subscription count returns zero for invalid type."""
        result = manager.get_subscription_count("invalid_type")

        assert result == 0

    def test_get_subscription_count_total_unique_subscribers(self, manager):
        """Test total unique subscribers count."""
        manager.subscribe(123, "price_changes")
        manager.subscribe(123, "trending")  # Same user
        manager.subscribe(456, "arbitrage")

        result = manager.get_subscription_count()  # No type = all unique

        assert result == 2  # 123 and 456


class TestMarketAlertsManagerUpdateAlertThreshold:
    """Tests for update_alert_threshold method."""

    def test_update_alert_threshold_success(self, manager):
        """Test successful alert threshold update."""
        result = manager.update_alert_threshold("price_changes", 20.0)

        assert result is True
        assert manager.alert_thresholds["price_change_percent"] == 20.0

    def test_update_alert_threshold_invalid_type(self, manager):
        """Test update_alert_threshold with invalid type."""
        result = manager.update_alert_threshold("invalid_type", 20.0)

        assert result is False

    def test_update_alert_threshold_negative_value(self, manager):
        """Test update_alert_threshold with negative value."""
        result = manager.update_alert_threshold("price_changes", -5.0)

        assert result is False

    def test_update_alert_threshold_zero_value(self, manager):
        """Test update_alert_threshold with zero value."""
        result = manager.update_alert_threshold("price_changes", 0)

        assert result is False

    def test_update_all_alert_types(self, manager):
        """Test updating all alert type thresholds."""
        assert manager.update_alert_threshold("price_changes", 25.0) is True
        assert manager.update_alert_threshold("trending", 60.0) is True
        assert manager.update_alert_threshold("volatility", 30.0) is True
        assert manager.update_alert_threshold("arbitrage", 15.0) is True


class TestMarketAlertsManagerUpdateCheckInterval:
    """Tests for update_check_interval method."""

    def test_update_check_interval_success(self, manager):
        """Test successful check interval update."""
        result = manager.update_check_interval("price_changes", 7200)

        assert result is True
        assert manager.check_intervals["price_changes"] == 7200

    def test_update_check_interval_invalid_type(self, manager):
        """Test update_check_interval with invalid type."""
        result = manager.update_check_interval("invalid_type", 7200)

        assert result is False

    def test_update_check_interval_too_short(self, manager):
        """Test update_check_interval with interval less than 5 minutes."""
        result = manager.update_check_interval("price_changes", 60)  # 1 minute

        assert result is False

    def test_update_check_interval_minimum_allowed(self, manager):
        """Test update_check_interval with minimum allowed (5 minutes)."""
        result = manager.update_check_interval("price_changes", 300)

        assert result is True
        assert manager.check_intervals["price_changes"] == 300


class TestMarketAlertsManagerClearSentAlerts:
    """Tests for clear_sent_alerts method."""

    def test_clear_sent_alerts_clears_all(self, manager):
        """Test clear_sent_alerts clears all sent alerts."""
        # Add some sent alerts
        manager.sent_alerts["price_changes"][123] = {
            "alert1": time.time(),
            "alert2": time.time(),
        }
        manager.sent_alerts["trending"][456] = {"alert3": time.time()}

        manager.clear_sent_alerts()

        for alert_type in manager.sent_alerts:
            assert len(manager.sent_alerts[alert_type]) == 0

    def test_clear_sent_alerts_specific_type(self, manager):
        """Test clear_sent_alerts for specific alert type."""
        manager.sent_alerts["price_changes"][123] = {"alert1": time.time()}
        manager.sent_alerts["trending"][123] = {"alert2": time.time()}

        manager.clear_sent_alerts(alert_type="price_changes")

        assert len(manager.sent_alerts["price_changes"]) == 0
        assert 123 in manager.sent_alerts["trending"]

    def test_clear_sent_alerts_specific_user(self, manager):
        """Test clear_sent_alerts for specific user."""
        manager.sent_alerts["price_changes"][123] = {"alert1": time.time()}
        manager.sent_alerts["price_changes"][456] = {"alert2": time.time()}

        manager.clear_sent_alerts(user_id=123)

        assert manager.sent_alerts["price_changes"].get(123, {}) == {}
        assert "alert2" in manager.sent_alerts["price_changes"][456]

    def test_clear_sent_alerts_specific_type_and_user(self, manager):
        """Test clear_sent_alerts for specific type and user."""
        manager.sent_alerts["price_changes"][123] = {"alert1": time.time()}
        manager.sent_alerts["trending"][123] = {"alert2": time.time()}

        manager.clear_sent_alerts(alert_type="price_changes", user_id=123)

        assert manager.sent_alerts["price_changes"].get(123, {}) == {}
        assert "alert2" in manager.sent_alerts["trending"][123]


class TestMarketAlertsManagerClearOldAlerts:
    """Tests for clear_old_alerts method."""

    def test_clear_old_alerts_returns_count(self, manager):
        """Test that clear_old_alerts returns cleared count."""
        old_time = time.time() - (8 * 86400)
        manager.sent_alerts["price_changes"][123] = {
            "alert1": old_time,
            "alert2": old_time,
        }
        manager.sent_alerts["trending"][456] = {"alert3": old_time}

        result = manager.clear_old_alerts()

        assert result == 3

    def test_clear_old_alerts_clears_all_alerts(self, manager):
        """Test that clear_old_alerts clears all alerts."""
        old_time = time.time() - (8 * 86400)
        manager.sent_alerts["price_changes"][123] = {"alert1": old_time}

        manager.clear_old_alerts()

        assert len(manager.sent_alerts["price_changes"].get(123, {})) == 0


class TestMarketAlertsManagerStartStopMonitoring:
    """Tests for start_monitoring and stop_monitoring methods."""

    @pytest.mark.asyncio()
    async def test_start_monitoring_sets_running_flag(self, manager):
        """Test that start_monitoring sets running flag."""
        # Start and immediately stop to avoid infinite loop
        task = asyncio.create_task(manager.start_monitoring())
        await asyncio.sleep(0.1)
        await manager.stop_monitoring()
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # After stopping, running should be False
        assert manager.running is False

    @pytest.mark.asyncio()
    async def test_start_monitoring_when_already_running(self, manager):
        """Test that start_monitoring does nothing when already running."""
        manager.running = True

        # Should return immediately without creating new task
        await manager.start_monitoring()

        # running should still be True
        assert manager.running is True

    @pytest.mark.asyncio()
    async def test_stop_monitoring_sets_running_flag_false(self, manager):
        """Test that stop_monitoring sets running flag to False."""
        manager.running = True
        manager.background_task = None

        await manager.stop_monitoring()

        assert manager.running is False

    @pytest.mark.asyncio()
    async def test_stop_monitoring_when_not_running(self, manager):
        """Test that stop_monitoring does nothing when not running."""
        manager.running = False

        await manager.stop_monitoring()

        assert manager.running is False


class TestMarketAlertsManagerCheckPriceChanges:
    """Tests for _check_price_changes method."""

    @pytest.mark.asyncio()
    async def test_check_price_changes_no_subscribers(self, manager):
        """Test _check_price_changes with no subscribers."""
        # Should complete without error
        await manager._check_price_changes()

    @pytest.mark.asyncio()
    async def test_check_price_changes_with_no_changes(self, manager, mock_bot):
        """Test _check_price_changes when no price changes found."""
        manager.subscribe(123, "price_changes")

        with patch(
            "src.telegram_bot.market_alerts.analyze_price_changes",
            new_callable=AsyncMock,
            return_value=[],
        ):
            await manager._check_price_changes()

        # No messages should be sent
        mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio()
    async def test_check_price_changes_sends_notification(self, manager, mock_bot):
        """Test _check_price_changes sends notification for changes."""
        manager.subscribe(123, "price_changes")

        price_changes = [
            {
                "market_hash_name": "AK-47 | Redline",
                "change_percent": 20.0,
                "direction": "up",
                "current_price": 15.50,
                "old_price": 12.90,
                "change_amount": 2.60,
                "item_url": "https://dmarket.com/item/123",
            }
        ]

        with patch(
            "src.telegram_bot.market_alerts.analyze_price_changes",
            new_callable=AsyncMock,
            return_value=price_changes,
        ):
            await manager._check_price_changes()

        mock_bot.send_message.assert_called()

    @pytest.mark.asyncio()
    async def test_check_price_changes_handles_exception(self, manager):
        """Test _check_price_changes handles exceptions gracefully."""
        manager.subscribe(123, "price_changes")

        with patch(
            "src.telegram_bot.market_alerts.analyze_price_changes",
            new_callable=AsyncMock,
            side_effect=Exception("API Error"),
        ):
            # Should not raise exception
            await manager._check_price_changes()


class TestMarketAlertsManagerCheckTrendingItems:
    """Tests for _check_trending_items method."""

    @pytest.mark.asyncio()
    async def test_check_trending_items_no_subscribers(self, manager):
        """Test _check_trending_items with no subscribers."""
        await manager._check_trending_items()

    @pytest.mark.asyncio()
    async def test_check_trending_items_with_no_trends(self, manager, mock_bot):
        """Test _check_trending_items when no trending items found."""
        manager.subscribe(123, "trending")

        with patch(
            "src.telegram_bot.market_alerts.find_trending_items",
            new_callable=AsyncMock,
            return_value=[],
        ):
            await manager._check_trending_items()

        mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio()
    async def test_check_trending_items_sends_notification(self, manager, mock_bot):
        """Test _check_trending_items sends notification for trending items."""
        manager.subscribe(123, "trending")

        trending_items = [
            {
                "market_hash_name": "AWP | Dragon Lore",
                "popularity_score": 75.0,
                "price": 1500.00,
                "sales_volume": 50,
                "offers_count": 100,
                "item_url": "https://dmarket.com/item/456",
            }
        ]

        with patch(
            "src.telegram_bot.market_alerts.find_trending_items",
            new_callable=AsyncMock,
            return_value=trending_items,
        ):
            await manager._check_trending_items()

        mock_bot.send_message.assert_called()


class TestMarketAlertsManagerCheckVolatility:
    """Tests for _check_volatility method."""

    @pytest.mark.asyncio()
    async def test_check_volatility_no_subscribers(self, manager):
        """Test _check_volatility with no subscribers."""
        await manager._check_volatility()

    @pytest.mark.asyncio()
    async def test_check_volatility_with_no_volatile_items(self, manager, mock_bot):
        """Test _check_volatility when no volatile items found."""
        manager.subscribe(123, "volatility")

        with patch(
            "src.telegram_bot.market_alerts.analyze_market_volatility",
            new_callable=AsyncMock,
            return_value=[],
        ):
            await manager._check_volatility()

        mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio()
    async def test_check_volatility_sends_notification(self, manager, mock_bot):
        """Test _check_volatility sends notification for volatile items."""
        manager.subscribe(123, "volatility")

        volatile_items = [
            {
                "market_hash_name": "M4A1-S | Hyper Beast",
                "volatility_score": 35.0,
                "current_price": 25.00,
            }
        ]

        with patch(
            "src.telegram_bot.market_alerts.analyze_market_volatility",
            new_callable=AsyncMock,
            return_value=volatile_items,
        ):
            await manager._check_volatility()

        mock_bot.send_message.assert_called()


class TestMarketAlertsManagerCheckArbitrage:
    """Tests for _check_arbitrage method."""

    @pytest.mark.asyncio()
    async def test_check_arbitrage_no_subscribers(self, manager):
        """Test _check_arbitrage with no subscribers."""
        await manager._check_arbitrage()

    @pytest.mark.asyncio()
    async def test_check_arbitrage_handles_exception(self, manager):
        """Test _check_arbitrage handles exceptions gracefully."""
        manager.subscribe(123, "arbitrage")

        with (
            patch("src.dmarket.dmarket_api.DMarketAPI"),
            patch(
                "src.dmarket.arbitrage_scanner.ArbitrageScanner",
                side_effect=Exception("Scanner Error"),
            ),
        ):
            # Should not raise exception
            await manager._check_arbitrage()


class TestGetAlertsManager:
    """Tests for get_alerts_manager function."""

    def test_get_alerts_manager_requires_bot(self):
        """Test that get_alerts_manager requires bot parameter."""
        # Reset global manager
        import src.telegram_bot.market_alerts as market_alerts_module

        market_alerts_module._alerts_manager = None

        with pytest.raises(ValueError, match="требуется bot"):
            get_alerts_manager(bot=None)

    def test_get_alerts_manager_returns_manager(self):
        """Test that get_alerts_manager returns manager instance."""
        import src.telegram_bot.market_alerts as market_alerts_module

        market_alerts_module._alerts_manager = None

        mock_bot = MagicMock()
        mock_api = MagicMock()

        with patch(
            "src.telegram_bot.utils.api_helper.create_dmarket_api_client",
            return_value=mock_api,
        ):
            manager = get_alerts_manager(bot=mock_bot)

        assert isinstance(manager, MarketAlertsManager)

        # Cleanup
        market_alerts_module._alerts_manager = None

    def test_get_alerts_manager_returns_same_instance(self):
        """Test that get_alerts_manager returns same instance on subsequent calls."""
        import src.telegram_bot.market_alerts as market_alerts_module

        market_alerts_module._alerts_manager = None

        mock_bot = MagicMock()
        mock_api = MagicMock()

        with patch(
            "src.telegram_bot.utils.api_helper.create_dmarket_api_client",
            return_value=mock_api,
        ):
            manager1 = get_alerts_manager(bot=mock_bot)
            manager2 = get_alerts_manager()

        assert manager1 is manager2

        # Cleanup
        market_alerts_module._alerts_manager = None


class TestMarketAlertsManagerActiveAlerts:
    """Tests for active_alerts management."""

    def test_active_alerts_initialized(self, manager):
        """Test that active_alerts dictionary is initialized."""
        assert "price_changes" in manager.active_alerts
        assert "trending" in manager.active_alerts
        assert "volatility" in manager.active_alerts
        assert "arbitrage" in manager.active_alerts

    def test_active_alerts_are_empty_initially(self, manager):
        """Test that active_alerts are empty initially."""
        for alert_type in manager.active_alerts:
            assert len(manager.active_alerts[alert_type]) == 0


class TestMarketAlertsManagerLastCheckTime:
    """Tests for last_check_time management."""

    def test_last_check_time_initialized(self, manager):
        """Test that last_check_time dictionary is initialized."""
        assert "price_changes" in manager.last_check_time
        assert "trending" in manager.last_check_time
        assert "volatility" in manager.last_check_time
        assert "arbitrage" in manager.last_check_time

    def test_last_check_time_starts_at_zero(self, manager):
        """Test that last_check_time starts at zero."""
        for alert_type in manager.last_check_time:
            assert manager.last_check_time[alert_type] == 0


class TestMarketAlertsManagerEdgeCases:
    """Edge case tests for MarketAlertsManager."""

    def test_subscribe_with_negative_user_id(self, manager):
        """Test subscribing with negative user ID."""
        # Should still work - Telegram IDs can be negative for groups
        result = manager.subscribe(-123456, "price_changes")
        assert result is True
        assert -123456 in manager.subscribers["price_changes"]

    def test_subscribe_with_zero_user_id(self, manager):
        """Test subscribing with zero user ID."""
        result = manager.subscribe(0, "price_changes")
        assert result is True
        assert 0 in manager.subscribers["price_changes"]

    def test_subscribe_with_large_user_id(self, manager):
        """Test subscribing with very large user ID."""
        large_id = 999999999999
        result = manager.subscribe(large_id, "price_changes")
        assert result is True
        assert large_id in manager.subscribers["price_changes"]

    def test_update_threshold_with_float_precision(self, manager):
        """Test updating threshold with float precision."""
        result = manager.update_alert_threshold("price_changes", 15.555)
        assert result is True
        assert manager.alert_thresholds["price_change_percent"] == 15.555

    def test_update_interval_with_exact_minimum(self, manager):
        """Test updating interval with exact minimum value."""
        result = manager.update_check_interval("price_changes", 300)
        assert result is True

    def test_update_interval_just_below_minimum(self, manager):
        """Test updating interval just below minimum."""
        result = manager.update_check_interval("price_changes", 299)
        assert result is False

    def test_get_subscription_count_with_no_type_empty(self, manager):
        """Test get_subscription_count with no type when empty."""
        result = manager.get_subscription_count()
        assert result == 0

    @pytest.mark.asyncio()
    async def test_check_price_changes_limits_notifications(self, manager, mock_bot):
        """Test that _check_price_changes limits notifications to 3 per user."""
        manager.subscribe(123, "price_changes")

        # Create 5 price changes
        price_changes = [
            {
                "market_hash_name": f"Item {i}",
                "change_percent": 20.0 + i,
                "direction": "up",
                "current_price": 15.50,
                "old_price": 12.90,
                "change_amount": 2.60,
                "item_url": f"https://dmarket.com/item/{i}",
            }
            for i in range(5)
        ]

        with patch(
            "src.telegram_bot.market_alerts.analyze_price_changes",
            new_callable=AsyncMock,
            return_value=price_changes,
        ):
            await manager._check_price_changes()

        # Should be called at most 3 times (limit per user)
        assert mock_bot.send_message.call_count <= 3
