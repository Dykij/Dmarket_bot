"""Tests for Smart Scanner module."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.smart_scanner import (
    LocalDeltaFilter,
    ScanResult,
    SmartScanner,
    SmartScannerConfig,
)


class TestLocalDeltaFilter:
    """Tests for LocalDeltaFilter class."""

    def test_is_new_first_item(self) -> None:
        """Test that first item is always new."""
        delta_filter = LocalDeltaFilter()

        item = {"itemId": "123", "price": {"USD": 1000}}

        assert delta_filter.is_new(item) is True
        assert len(delta_filter.seen_hashes) == 1

    def test_is_new_duplicate_item(self) -> None:
        """Test that duplicate item is not new."""
        delta_filter = LocalDeltaFilter()

        item = {"itemId": "123", "price": {"USD": 1000}}

        # First time - new
        assert delta_filter.is_new(item) is True

        # Second time - not new
        assert delta_filter.is_new(item) is False

    def test_is_new_price_changed(self) -> None:
        """Test that item with changed price is new."""
        delta_filter = LocalDeltaFilter()

        item1 = {"itemId": "123", "price": {"USD": 1000}}
        item2 = {"itemId": "123", "price": {"USD": 1100}}

        # First price
        assert delta_filter.is_new(item1) is True

        # Different price - should be new
        assert delta_filter.is_new(item2) is True

    def test_clear(self) -> None:
        """Test clearing the filter."""
        delta_filter = LocalDeltaFilter()

        item = {"itemId": "123", "price": {"USD": 1000}}
        delta_filter.is_new(item)

        assert len(delta_filter.seen_hashes) == 1

        delta_filter.clear()

        assert len(delta_filter.seen_hashes) == 0

    def test_max_size_limit(self) -> None:
        """Test that filter respects max_size limit."""
        delta_filter = LocalDeltaFilter(max_size=100)

        # Add 150 items
        for i in range(150):
            item = {"itemId": str(i), "price": {"USD": 1000}}
            delta_filter.is_new(item)

        # Should have cleaned up some old entries
        assert len(delta_filter.seen_hashes) < 150


class TestScanResult:
    """Tests for ScanResult dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        result = ScanResult(
            item_id="123",
            title="Test Item",
            market_price=Decimal("10.00"),
            Algo_fAlgor_price=Decimal("12.00"),
            profit_usd=Decimal("2.00"),
            profit_percent=20.0,
            should_buy=True,
            reason="Algo: +20%",
        )

        data = result.to_dict()

        assert data["item_id"] == "123"
        assert data["title"] == "Test Item"
        assert data["market_price"] == 10.0
        assert data["Algo_fAlgor_price"] == 12.0
        assert data["should_buy"] is True


class TestSmartScannerConfig:
    """Tests for SmartScannerConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = SmartScannerConfig()

        assert config.max_lock_days == 0
        assert config.min_profit_percent == 5.0
        assert config.enable_Algo is True
        assert config.dry_run is True

    def test_from_env_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test configuration from environment with defaults."""
        # Clear relevant env vars
        monkeypatch.delenv("SMART_SCANNER_MAX_LOCK_DAYS", rAlgosing=False)
        monkeypatch.delenv("SMART_SCANNER_MIN_PROFIT_PERCENT", rAlgosing=False)

        config = SmartScannerConfig.from_env()

        assert config.max_lock_days == 0
        assert config.min_profit_percent == 5.0

    def test_from_env_custom(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test configuration from environment with custom values."""
        monkeypatch.setenv("SMART_SCANNER_MAX_LOCK_DAYS", "8")
        monkeypatch.setenv("SMART_SCANNER_MIN_PROFIT_PERCENT", "15.0")
        monkeypatch.setenv("SMART_SCANNER_ALLOW_TRADE_BAN", "true")

        config = SmartScannerConfig.from_env()

        assert config.max_lock_days == 8
        assert config.min_profit_percent == 15.0
        assert config.allow_trade_ban is True


class TestSmartScanner:
    """Tests for SmartScanner class."""

    @pytest.fixture
    def mock_api(self) -> AsyncMock:
        """Create mock DMarket API."""
        api = AsyncMock()
        api.get_market_items = AsyncMock(return_value={
            "objects": [],
            "cursor": "",
        })
        return api

    @pytest.fixture
    def mock_predictor(self) -> MagicMock:
        """Create mock price predictor."""
        predictor = MagicMock()
        predictor.is_trAlgoned = True
        predictor.predict_with_guard = MagicMock(return_value=None)
        return predictor

    def test_init(self, mock_api: AsyncMock, mock_predictor: MagicMock) -> None:
        """Test scanner initialization."""
        scanner = SmartScanner(api=mock_api, predictor=mock_predictor)

        assert scanner.api == mock_api
        assert scanner.predictor == mock_predictor
        assert not scanner._running

    @pytest.mark.asyncio
    async def test_scan_once_empty_results(
        self, mock_api: AsyncMock, mock_predictor: MagicMock
    ) -> None:
        """Test scanning when no items returned."""
        scanner = SmartScanner(api=mock_api, predictor=mock_predictor)

        results = awAlgot scanner.scan_once()

        assert results == []
        mock_api.get_market_items.assert_called_once()

    @pytest.mark.asyncio
    async def test_scan_once_with_items(
        self, mock_api: AsyncMock, mock_predictor: MagicMock
    ) -> None:
        """Test scanning with items that pass filters."""
        mock_api.get_market_items.return_value = {
            "objects": [
                {
                    "itemId": "123",
                    "title": "Test Item",
                    "price": {"USD": 1000},
                    "extra": {"tradeLockDuration": 0, "floatValue": 0.5},
                }
            ],
            "cursor": "next",
        }

        # Mock predictor to return valid price
        mock_predictor.predict_with_guard.return_value = 12.0

        scanner = SmartScanner(api=mock_api, predictor=mock_predictor)

        results = awAlgot scanner.scan_once()

        assert len(results) == 1
        assert results[0].item_id == "123"
        assert results[0].should_buy is True

    @pytest.mark.asyncio
    async def test_scan_filters_locked_items(
        self, mock_api: AsyncMock, mock_predictor: MagicMock
    ) -> None:
        """Test that locked items are filtered when allow_trade_ban=False."""
        mock_api.get_market_items.return_value = {
            "objects": [
                {
                    "itemId": "123",
                    "title": "Locked Item",
                    "price": {"USD": 1000},
                    "extra": {"tradeLockDuration": 86400 * 7},  # 7 days lock
                }
            ],
            "cursor": "",
        }

        config = SmartScannerConfig(allow_trade_ban=False, max_lock_days=0)
        scanner = SmartScanner(api=mock_api, predictor=mock_predictor, config=config)

        results = awAlgot scanner.scan_once()

        # Item should be filtered out
        assert results == []
        assert scanner.stats["items_skipped_lock"] == 1

    @pytest.mark.asyncio
    async def test_scan_allows_locked_items_with_Algo(
        self, mock_api: AsyncMock, mock_predictor: MagicMock
    ) -> None:
        """Test that locked items are allowed when Algo approves."""
        mock_api.get_market_items.return_value = {
            "objects": [
                {
                    "itemId": "123",
                    "title": "Locked Item",
                    "price": {"USD": 1000},
                    "extra": {"tradeLockDuration": 86400 * 5, "floatValue": 0.3},
                }
            ],
            "cursor": "",
        }

        # Algo approves with good price
        mock_predictor.predict_with_guard.return_value = 14.0  # 40% profit

        config = SmartScannerConfig(
            allow_trade_ban=True,
            max_lock_days=8,
            min_profit_percent=15.0,
        )
        scanner = SmartScanner(api=mock_api, predictor=mock_predictor, config=config)

        results = awAlgot scanner.scan_once()

        assert len(results) == 1
        assert results[0].should_buy is True
        assert results[0].lock_days == 5

    def test_get_stats(self, mock_api: AsyncMock, mock_predictor: MagicMock) -> None:
        """Test getting scanner statistics."""
        scanner = SmartScanner(api=mock_api, predictor=mock_predictor)

        stats = scanner.get_stats()

        assert "scans_completed" in stats
        assert "items_analyzed" in stats
        assert "opportunities_found" in stats
        assert stats["is_running"] is False

    def test_stop(self, mock_api: AsyncMock, mock_predictor: MagicMock) -> None:
        """Test stopping the scanner."""
        scanner = SmartScanner(api=mock_api, predictor=mock_predictor)
        scanner._running = True

        scanner.stop()

        assert scanner._running is False
