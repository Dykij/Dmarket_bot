"""Tests for High-Frequency Trading (HFT) module.

Tests cover:
- HFT configuration
- Balance-stop mechanism
- Trading loop behavior
- Statistics tracking
- Circuit breaker
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from src.dmarket.hft_mode import (
    HFTConfig,
    HFTStatistics,
    HFTStatus,
    HighFrequencyTrader,
    TradeRecord,
    load_hft_config_from_dict,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture()
def hft_config():
    """Default HFT configuration for tests."""
    return HFTConfig(
        enabled=True,
        scan_interval_minutes=1,  # Short interval for tests
        auto_buy_threshold_percent=15.0,
        max_concurrent_orders=3,
        orders_base=20.0,
        stop_orders_balance=10.0,
        max_consecutive_errors=3,
        rate_limit_pause_seconds=1,
        dry_run=True,
        games=["csgo"],
        arbitrage_level="standard",
    )


@pytest.fixture()
def mock_api():
    """Mock DMarket API client."""
    api = AsyncMock()
    api.get_balance = AsyncMock(
        return_value={
            "balance": 100.0,
            "available_balance": 100.0,
            "error": False,
        }
    )
    api.buy_item = AsyncMock(
        return_value={
            "success": True,
            "dry_run": True,
        }
    )
    return api


@pytest.fixture()
def mock_scanner():
    """Mock ArbitrageScanner."""
    scanner = AsyncMock()
    scanner.scan = AsyncMock(
        return_value=[
            {
                "item_id": "item_1",
                "title": "AK-47 | Redline",
                "game": "csgo",
                "buy_price": 10.0,
                "sell_price": 12.5,
                "profit": 1.5,
                "profit_percent": 15.0,
            },
            {
                "item_id": "item_2",
                "title": "AWP | Asiimov",
                "game": "csgo",
                "buy_price": 15.0,
                "sell_price": 19.0,
                "profit": 2.5,
                "profit_percent": 16.7,
            },
        ]
    )
    return scanner


# ============================================================================
# CONFIG TESTS
# ============================================================================


class TestHFTConfig:
    """Tests for HFT configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = HFTConfig()

        assert config.enabled is False
        assert config.scan_interval_minutes == 10
        assert config.auto_buy_threshold_percent == 15.0
        assert config.max_concurrent_orders == 5
        assert config.orders_base == 20.0
        assert config.stop_orders_balance == 10.0
        assert config.dry_run is True

    def test_custom_config(self, hft_config):
        """Test custom configuration."""
        assert hft_config.enabled is True
        assert hft_config.scan_interval_minutes == 1
        assert hft_config.games == ["csgo"]

    def test_load_from_dict(self):
        """Test loading config from dictionary."""
        config_dict = {
            "hft_mode": {
                "enabled": True,
                "scan_interval_minutes": 5,
                "auto_buy_threshold_percent": 20.0,
                "max_concurrent_orders": 10,
                "orders_base": 50.0,
                "stop_orders_balance": 25.0,
                "dry_run": False,
                "games": ["csgo", "dota2", "tf2"],
                "arbitrage_level": "medium",
            }
        }

        config = load_hft_config_from_dict(config_dict)

        assert config.enabled is True
        assert config.scan_interval_minutes == 5
        assert config.auto_buy_threshold_percent == 20.0
        assert config.max_concurrent_orders == 10
        assert config.orders_base == 50.0
        assert config.stop_orders_balance == 25.0
        assert config.dry_run is False
        assert config.games == ["csgo", "dota2", "tf2"]
        assert config.arbitrage_level == "medium"

    def test_load_from_empty_dict(self):
        """Test loading config from empty dictionary uses defaults."""
        config = load_hft_config_from_dict({})

        assert config.enabled is False
        assert config.scan_interval_minutes == 10


# ============================================================================
# STATISTICS TESTS
# ============================================================================


class TestHFTStatistics:
    """Tests for HFT statistics."""

    def test_win_rate_calculation(self):
        """Test win rate calculation."""
        stats = HFTStatistics(
            total_trades=10,
            successful_trades=8,
            failed_trades=2,
        )

        assert stats.win_rate == 80.0

    def test_win_rate_zero_trades(self):
        """Test win rate with zero trades."""
        stats = HFTStatistics()

        assert stats.win_rate == 0.0

    def test_average_profit(self):
        """Test average profit calculation."""
        stats = HFTStatistics(
            successful_trades=5,
            total_profit=50.0,
        )

        assert stats.average_profit == 10.0

    def test_balance_change(self):
        """Test balance change calculation."""
        stats = HFTStatistics(
            start_balance=100.0,
            current_balance=120.0,
        )

        assert stats.balance_change == 20.0

    def test_runtime_hours(self):
        """Test runtime calculation."""
        stats = HFTStatistics()
        stats.start_time = datetime.now() - timedelta(hours=2)

        # Should be approximately 2 hours
        assert 1.9 <= stats.runtime_hours <= 2.1

    def test_get_trades_in_period(self):
        """Test filtering trades by period."""
        now = datetime.now()
        stats = HFTStatistics(
            trades=[
                TradeRecord(
                    timestamp=now - timedelta(hours=1),
                    item_id="1",
                    item_name="Item 1",
                    game="csgo",
                    buy_price=10,
                    expected_sell_price=12,
                    expected_profit=1.5,
                    profit_percent=15,
                    status="completed",
                ),
                TradeRecord(
                    timestamp=now - timedelta(hours=25),
                    item_id="2",
                    item_name="Item 2",
                    game="csgo",
                    buy_price=10,
                    expected_sell_price=12,
                    expected_profit=1.5,
                    profit_percent=15,
                    status="completed",
                ),
            ]
        )

        trades_24h = stats.get_trades_in_period(24)

        assert len(trades_24h) == 1
        assert trades_24h[0].item_id == "1"


# ============================================================================
# TRADER TESTS
# ============================================================================


class TestHighFrequencyTrader:
    """Tests for HighFrequencyTrader."""

    def test_initialization(self, mock_api, hft_config):
        """Test trader initialization."""
        trader = HighFrequencyTrader(mock_api, hft_config)

        assert trader.status == HFTStatus.STOPPED
        assert trader.consecutive_errors == 0
        assert trader.config == hft_config

    @pytest.mark.asyncio()
    async def test_start_disabled(self, mock_api):
        """Test starting with disabled config."""
        config = HFTConfig(enabled=False)
        trader = HighFrequencyTrader(mock_api, config)

        result = await trader.start()

        assert result is False
        assert trader.status == HFTStatus.STOPPED

    @pytest.mark.asyncio()
    async def test_start_balance_below_threshold(self, mock_api, hft_config):
        """Test starting with balance below threshold."""
        mock_api.get_balance = AsyncMock(
            return_value={
                "balance": 5.0,  # Below threshold of 10.0
                "error": False,
            }
        )

        trader = HighFrequencyTrader(mock_api, hft_config)
        result = await trader.start()

        assert result is False

    @pytest.mark.asyncio()
    async def test_check_balance_sufficient(self, mock_api, hft_config):
        """Test balance check with sufficient balance."""
        # Mock API to return balance in DMarket format (usd key in cents)
        mock_api.get_balance = AsyncMock(
            return_value={
                "usd": "5000",  # $50 in cents
                "error": False,
            }
        )

        trader = HighFrequencyTrader(mock_api, hft_config)
        result = await trader._check_balance()

        assert result is True

    @pytest.mark.asyncio()
    async def test_check_balance_insufficient(self, mock_api, hft_config):
        """Test balance check with insufficient balance."""
        mock_api.get_balance = AsyncMock(
            return_value={
                "balance": 5.0,
                "error": False,
            }
        )

        trader = HighFrequencyTrader(mock_api, hft_config)
        result = await trader._check_balance()

        assert result is False

    @pytest.mark.asyncio()
    async def test_execute_trade_success(self, mock_api, hft_config):
        """Test successful trade execution."""
        trader = HighFrequencyTrader(mock_api, hft_config)

        item = {
            "item_id": "item_1",
            "title": "AK-47 | Redline",
            "game": "csgo",
            "buy_price": 10.0,
            "sell_price": 12.5,
            "profit": 1.5,
            "profit_percent": 15.0,
        }

        result = await trader._execute_trade(item)

        assert result is True
        assert trader.stats.total_trades == 1
        assert trader.stats.successful_trades == 1
        assert trader.stats.total_profit == 1.5
        mock_api.buy_item.assert_called_once()

    @pytest.mark.asyncio()
    async def test_execute_trade_failure(self, mock_api, hft_config):
        """Test failed trade execution."""
        mock_api.buy_item = AsyncMock(
            return_value={
                "success": False,
                "error": "Insufficient funds",
            }
        )

        trader = HighFrequencyTrader(mock_api, hft_config)

        item = {
            "item_id": "item_1",
            "title": "AK-47 | Redline",
            "game": "csgo",
            "buy_price": 10.0,
            "sell_price": 12.5,
            "profit": 1.5,
            "profit_percent": 15.0,
        }

        result = await trader._execute_trade(item)

        assert result is False
        assert trader.stats.total_trades == 1
        assert trader.stats.failed_trades == 1

    def test_get_status(self, mock_api, hft_config):
        """Test getting trader status."""
        trader = HighFrequencyTrader(mock_api, hft_config)
        trader.stats.current_balance = 100.0
        trader.stats.total_trades = 5

        status = trader.get_status()

        assert status["status"] == "stopped"
        assert status["enabled"] is True
        assert status["dry_run"] is True
        assert status["current_balance"] == 100.0
        assert status["total_trades"] == 5

    def test_get_statistics(self, mock_api, hft_config):
        """Test getting trading statistics."""
        trader = HighFrequencyTrader(mock_api, hft_config)
        trader.stats.total_trades = 10
        trader.stats.successful_trades = 8
        trader.stats.total_profit = 50.0

        stats = trader.get_statistics()

        assert stats["total_trades"] == 10
        assert stats["successful_trades"] == 8
        assert stats["win_rate"] == 80.0
        assert stats["total_profit"] == 50.0

    @pytest.mark.asyncio()
    async def test_stop(self, mock_api, hft_config):
        """Test stopping trader."""
        trader = HighFrequencyTrader(mock_api, hft_config)
        trader.status = HFTStatus.RUNNING

        await trader.stop()

        assert trader.status == HFTStatus.STOPPED

    @pytest.mark.asyncio()
    async def test_pause_resume(self, mock_api, hft_config):
        """Test pausing and resuming trader."""
        trader = HighFrequencyTrader(mock_api, hft_config)
        trader.status = HFTStatus.RUNNING

        await trader.pause()
        assert trader.status == HFTStatus.PAUSED

        await trader.resume()
        assert trader.status == HFTStatus.RUNNING


# ============================================================================
# TRADE RECORD TESTS
# ============================================================================


class TestTradeRecord:
    """Tests for TradeRecord."""

    def test_create_trade_record(self):
        """Test creating a trade record."""
        record = TradeRecord(
            timestamp=datetime.now(),
            item_id="item_1",
            item_name="AK-47 | Redline",
            game="csgo",
            buy_price=10.0,
            expected_sell_price=12.5,
            expected_profit=1.5,
            profit_percent=15.0,
            status="completed",
            dry_run=True,
        )

        assert record.item_id == "item_1"
        assert record.buy_price == 10.0
        assert record.profit_percent == 15.0
        assert record.dry_run is True


# ============================================================================
# HFT STATUS TESTS
# ============================================================================


class TestHFTStatus:
    """Tests for HFT status enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert HFTStatus.STOPPED.value == "stopped"
        assert HFTStatus.RUNNING.value == "running"
        assert HFTStatus.PAUSED.value == "paused"
        assert HFTStatus.BALANCE_STOP.value == "balance_stop"
        assert HFTStatus.ERROR_STOP.value == "error_stop"
        assert HFTStatus.RATE_LIMITED.value == "rate_limited"
