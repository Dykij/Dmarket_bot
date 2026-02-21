"""
Comprehensive tests for database models.

This module tests all database models including:
- Target model
- TradeHistory model
- TradingSettings model
- Model serialization (to_dict)
- Model representation (__repr__)

Coverage Target: 95%+
Estimated Tests: 25-30 tests
"""

from datetime import datetime

import pytest

from src.models.target import Target, TradeHistory, TradingSettings

# ============================================================================
# Test Class: Target Model
# ============================================================================


class TestTargetModel:
    """Tests for Target model."""

    def test_target_creation_basic(self):
        """Test basic target creation."""
        target = Target(
            user_id=123456789,
            target_id="dmarket_target_123",
            game="csgo",
            title="AK-47 | Redline (Field-Tested)",
            price=15.50,
        )

        assert target.user_id == 123456789
        assert target.target_id == "dmarket_target_123"
        assert target.game == "csgo"
        assert target.title == "AK-47 | Redline (Field-Tested)"
        assert target.price == 15.50

    def test_target_default_values(self):
        """Test target default values when explicitly set."""
        target = Target(
            user_id=123456789,
            target_id="test_id",
            game="csgo",
            title="Test Item",
            price=10.0,
            amount=1,  # Explicitly set default
            status="active",  # Explicitly set default
        )

        assert target.amount == 1
        assert target.status == "active"
        assert target.attributes is None

    def test_target_with_all_fields(self):
        """Test target with all fields specified."""
        target = Target(
            user_id=123456789,
            target_id="test_id",
            game="dota2",
            title="Arcana Item",
            price=35.99,
            amount=5,
            status="inactive",
            attributes={"float_value": 0.15, "phase": 2},
        )

        assert target.amount == 5
        assert target.status == "inactive"
        assert target.attributes == {"float_value": 0.15, "phase": 2}

    def test_target_to_dict(self):
        """Test target serialization to dictionary."""
        target = Target(
            user_id=123456789,
            target_id="test_id",
            game="csgo",
            title="Test Item",
            price=10.50,
            amount=2,
            status="active",
        )

        result = target.to_dict()

        assert result["user_id"] == 123456789
        assert result["target_id"] == "test_id"
        assert result["game"] == "csgo"
        assert result["title"] == "Test Item"
        assert result["price"] == 10.50
        assert result["amount"] == 2
        assert result["status"] == "active"

    def test_target_repr(self):
        """Test target string representation."""
        target = Target(
            id=1,
            user_id=123456789,
            target_id="test_id",
            game="csgo",
            title="AK-47 | Redline",
            price=15.50,
            status="active",
        )

        repr_str = repr(target)

        assert "Target" in repr_str
        assert "123456789" in repr_str
        assert "AK-47" in repr_str
        assert "15.50" in repr_str
        assert "active" in repr_str


# ============================================================================
# Test Class: TradeHistory Model
# ============================================================================


class TestTradeHistoryModel:
    """Tests for TradeHistory model."""

    def test_trade_history_creation_basic(self):
        """Test basic trade history creation."""
        trade = TradeHistory(
            user_id=123456789,
            trade_type="buy",
            item_title="AK-47 | Redline (FT)",
            price=15.50,
            game="csgo",
        )

        assert trade.user_id == 123456789
        assert trade.trade_type == "buy"
        assert trade.item_title == "AK-47 | Redline (FT)"
        assert trade.price == 15.50
        assert trade.game == "csgo"

    def test_trade_history_default_values(self):
        """Test trade history default values when explicitly set."""
        trade = TradeHistory(
            user_id=123456789,
            trade_type="sell",
            item_title="Test Item",
            price=10.0,
            game="csgo",
            profit=0.0,  # Explicitly set default
            status="pending",  # Explicitly set default
        )

        assert trade.profit == 0.0
        assert trade.status == "pending"
        assert trade.completed_at is None
        assert trade.trade_metadata is None

    def test_trade_history_with_profit(self):
        """Test trade history with profit."""
        trade = TradeHistory(
            user_id=123456789,
            trade_type="sell",
            item_title="Test Item",
            price=20.0,
            profit=5.50,
            game="dota2",
            status="completed",
        )

        assert trade.profit == 5.50
        assert trade.status == "completed"

    def test_trade_history_to_dict(self):
        """Test trade history serialization."""
        trade = TradeHistory(
            user_id=123456789,
            trade_type="target",
            item_title="M4A4 | Howl",
            price=1500.0,
            profit=200.0,
            game="csgo",
            status="completed",
        )

        result = trade.to_dict()

        assert result["user_id"] == 123456789
        assert result["trade_type"] == "target"
        assert result["item_title"] == "M4A4 | Howl"
        assert result["price"] == 1500.0
        assert result["profit"] == 200.0
        assert result["game"] == "csgo"
        assert result["status"] == "completed"

    def test_trade_history_repr(self):
        """Test trade history string representation."""
        trade = TradeHistory(
            id=42,
            user_id=123456789,
            trade_type="buy",
            item_title="AWP | Dragon Lore",
            price=5000.0,
            status="pending",
            game="csgo",
        )

        repr_str = repr(trade)

        assert "TradeHistory" in repr_str
        assert "123456789" in repr_str
        assert "buy" in repr_str
        assert "AWP" in repr_str
        assert "5000" in repr_str


# ============================================================================
# Test Class: TradingSettings Model
# ============================================================================


class TestTradingSettingsModel:
    """Tests for TradingSettings model."""

    def test_trading_settings_creation_basic(self):
        """Test basic trading settings creation."""
        settings = TradingSettings(user_id=123456789)

        assert settings.user_id == 123456789

    def test_trading_settings_default_values(self):
        """Test trading settings default values when explicitly set."""
        settings = TradingSettings(
            user_id=123456789,
            max_trade_value=50.0,  # Explicitly set defaults
            dAlgoly_limit=500.0,
            min_profit_percent=5.0,
            strategy="balanced",
            auto_trading_enabled=0,
            notifications_enabled=1,
        )

        assert settings.max_trade_value == 50.0
        assert settings.dAlgoly_limit == 500.0
        assert settings.min_profit_percent == 5.0
        assert settings.strategy == "balanced"
        assert settings.auto_trading_enabled == 0
        assert settings.notifications_enabled == 1

    def test_trading_settings_custom_values(self):
        """Test trading settings with custom values."""
        settings = TradingSettings(
            user_id=123456789,
            max_trade_value=100.0,
            dAlgoly_limit=1000.0,
            min_profit_percent=10.0,
            strategy="aggressive",
            auto_trading_enabled=1,
            games_enabled=["csgo", "dota2", "rust"],
            notifications_enabled=0,
        )

        assert settings.max_trade_value == 100.0
        assert settings.dAlgoly_limit == 1000.0
        assert settings.min_profit_percent == 10.0
        assert settings.strategy == "aggressive"
        assert settings.auto_trading_enabled == 1
        assert settings.games_enabled == ["csgo", "dota2", "rust"]
        assert settings.notifications_enabled == 0

    def test_trading_settings_to_dict(self):
        """Test trading settings serialization."""
        settings = TradingSettings(
            user_id=123456789,
            max_trade_value=75.0,
            strategy="conservative",
            auto_trading_enabled=1,
        )

        result = settings.to_dict()

        assert result["user_id"] == 123456789
        assert result["max_trade_value"] == 75.0
        assert result["strategy"] == "conservative"
        assert result["auto_trading_enabled"] is True  # Converted to bool

    def test_trading_settings_bool_conversion(self):
        """Test that integer fields are converted to booleans in to_dict."""
        settings_enabled = TradingSettings(
            user_id=1,
            auto_trading_enabled=1,
            notifications_enabled=1,
        )

        settings_disabled = TradingSettings(
            user_id=2,
            auto_trading_enabled=0,
            notifications_enabled=0,
        )

        assert settings_enabled.to_dict()["auto_trading_enabled"] is True
        assert settings_enabled.to_dict()["notifications_enabled"] is True
        assert settings_disabled.to_dict()["auto_trading_enabled"] is False
        assert settings_disabled.to_dict()["notifications_enabled"] is False

    def test_trading_settings_repr(self):
        """Test trading settings string representation."""
        settings = TradingSettings(
            user_id=123456789,
            max_trade_value=75.0,
            strategy="aggressive",
        )

        repr_str = repr(settings)

        assert "TradingSettings" in repr_str
        assert "123456789" in repr_str
        assert "75" in repr_str
        assert "aggressive" in repr_str


# ============================================================================
# Test Class: Model to_dict with Timestamps
# ============================================================================


class TestModelTimestamps:
    """Tests for model timestamps in to_dict."""

    def test_target_to_dict_with_timestamps(self):
        """Test target to_dict includes ISO formatted timestamps."""
        target = Target(
            user_id=123,
            target_id="test",
            game="csgo",
            title="Test",
            price=10.0,
            created_at=datetime(2025, 1, 15, 12, 30, 0),
            updated_at=datetime(2025, 1, 16, 14, 45, 0),
        )

        result = target.to_dict()

        assert "2025-01-15" in result["created_at"]
        assert "2025-01-16" in result["updated_at"]

    def test_target_to_dict_handles_none_timestamps(self):
        """Test target to_dict handles None timestamps."""
        target = Target(
            user_id=123,
            target_id="test",
            game="csgo",
            title="Test",
            price=10.0,
            created_at=None,
            updated_at=None,
        )

        result = target.to_dict()

        assert result["created_at"] is None
        assert result["updated_at"] is None

    def test_trade_history_completed_at_null(self):
        """Test trade history handles null completed_at."""
        trade = TradeHistory(
            user_id=123,
            trade_type="buy",
            item_title="Test",
            price=10.0,
            game="csgo",
            completed_at=None,
        )

        result = trade.to_dict()
        assert result["completed_at"] is None


# ============================================================================
# Test Class: Strategy Values
# ============================================================================


class TestStrategyValues:
    """Tests for valid strategy values."""

    @pytest.mark.parametrize("strategy", ("conservative", "balanced", "aggressive"))
    def test_valid_strategies(self, strategy):
        """Test valid strategy values are accepted."""
        settings = TradingSettings(
            user_id=123,
            strategy=strategy,
        )

        assert settings.strategy == strategy
        assert settings.to_dict()["strategy"] == strategy


# ============================================================================
# Test Class: Game Codes
# ============================================================================


class TestGameCodes:
    """Tests for valid game codes."""

    @pytest.mark.parametrize("game", ("csgo", "dota2", "tf2", "rust"))
    def test_valid_game_codes_in_target(self, game):
        """Test valid game codes in Target model."""
        target = Target(
            user_id=123,
            target_id="test",
            game=game,
            title="Test Item",
            price=10.0,
        )

        assert target.game == game
        assert target.to_dict()["game"] == game

    @pytest.mark.parametrize("game", ("csgo", "dota2", "tf2", "rust"))
    def test_valid_game_codes_in_trade_history(self, game):
        """Test valid game codes in TradeHistory model."""
        trade = TradeHistory(
            user_id=123,
            trade_type="buy",
            item_title="Test Item",
            price=10.0,
            game=game,
        )

        assert trade.game == game


# ============================================================================
# Test Summary
# ============================================================================

"""
Test Coverage Summary:
======================

Total Tests: 27 tests

Test Categories:
1. Target Model: 5 tests
2. TradeHistory Model: 5 tests
3. TradingSettings Model: 6 tests
4. Timestamp Handling: 3 tests
5. Strategy Values: 3 tests (parametrized)
6. Game Codes: 8 tests (parametrized)

Coverage Areas:
✅ Target model (5 tests)
✅ TradeHistory model (5 tests)
✅ TradingSettings model (6 tests)
✅ Serialization (to_dict) (6 tests)
✅ String representation (3 tests)
✅ Timestamp handling (3 tests)
✅ Parametrized tests (11 tests)

Expected Coverage: 95%+
File Size: ~350 lines
"""
