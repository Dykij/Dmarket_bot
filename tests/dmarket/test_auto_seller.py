"""Tests for AutoSeller module.

Tests the auto-selling functionality including:
- Sale scheduling
- Price calculation strategies
- Price adjustment
- Stop-loss mechanism
- Statistics tracking
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.dmarket.auto_seller import (
    AutoSeller,
    AutoSellerStats,
    PricingStrategy,
    SaleConfig,
    SaleStatus,
    ScheduledSale,
    load_sale_config,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def mock_api() -> AsyncMock:
    """Create a mock DMarket API client."""
    api = AsyncMock()
    api.dry_run = False

    # Default successful sell response
    api.sell_item = AsyncMock(
        return_value={
            "success": True,
            "offerId": "offer_123",
            "item_id": "item_123",
        }
    )

    # Default best offers response
    api.get_best_offers = AsyncMock(
        return_value={
            "objects": [
                {
                    "price": {"USD": "1200"},  # $12.00
                }
            ]
        }
    )

    # Update and remove offers
    api.update_offer_prices = AsyncMock(return_value={"success": True})
    api.remove_offers = AsyncMock(return_value={"success": True})

    return api


@pytest.fixture()
def sale_config() -> SaleConfig:
    """Create a test sale configuration."""
    return SaleConfig(
        enabled=True,
        min_margin_percent=4.0,
        max_margin_percent=12.0,
        target_margin_percent=8.0,
        undercut_cents=1,
        price_check_interval_minutes=1,  # Short for testing
        stop_loss_hours=48,
        stop_loss_percent=5.0,
        max_active_sales=10,
        delay_before_list_seconds=0,  # No delay for testing
        pricing_strategy=PricingStrategy.UNDERCUT,
        dmarket_fee_percent=7.0,
    )


@pytest.fixture()
def auto_seller(mock_api: AsyncMock, sale_config: SaleConfig) -> AutoSeller:
    """Create an AutoSeller instance with mocked API."""
    return AutoSeller(api=mock_api, config=sale_config)


@pytest.fixture()
def sample_sale() -> ScheduledSale:
    """Create a sample scheduled sale."""
    return ScheduledSale(
        item_id="item_123",
        item_name="AK-47 | Redline (Field-Tested)",
        buy_price=10.00,
        target_margin=0.08,
        game="csgo",
    )


# ============================================================================
# Tests for SaleConfig
# ============================================================================


class TestSaleConfig:
    """Tests for SaleConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = SaleConfig()

        assert config.enabled is True
        assert config.min_margin_percent == 4.0
        assert config.max_margin_percent == 12.0
        assert config.target_margin_percent == 8.0
        assert config.undercut_cents == 1
        assert config.stop_loss_hours == 48
        assert config.stop_loss_percent == 5.0
        assert config.pricing_strategy == PricingStrategy.UNDERCUT
        assert config.dmarket_fee_percent == 7.0

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = SaleConfig(
            min_margin_percent=5.0,
            max_margin_percent=15.0,
            pricing_strategy=PricingStrategy.DYNAMIC,
        )

        assert config.min_margin_percent == 5.0
        assert config.max_margin_percent == 15.0
        assert config.pricing_strategy == PricingStrategy.DYNAMIC


# ============================================================================
# Tests for ScheduledSale
# ============================================================================


class TestScheduledSale:
    """Tests for ScheduledSale dataclass."""

    def test_calculate_profit(self, sample_sale: ScheduledSale) -> None:
        """Test profit calculation."""
        # Buy at $10, sell at $11
        profit, profit_percent = sample_sale.calculate_profit(11.00)

        assert profit == 1.00
        assert profit_percent == 10.0

    def test_calculate_profit_no_price(self, sample_sale: ScheduledSale) -> None:
        """Test profit calculation with no sale price."""
        # No prices set
        profit, profit_percent = sample_sale.calculate_profit()

        assert profit == 0.0
        assert profit_percent == 0.0

    def test_calculate_profit_uses_current_price(
        self, sample_sale: ScheduledSale
    ) -> None:
        """Test that calculate_profit uses current_price when no sale_price given."""
        sample_sale.current_price = 12.00
        profit, profit_percent = sample_sale.calculate_profit()

        assert profit == 2.00
        assert profit_percent == 20.0

    def test_is_stale_not_listed(self, sample_sale: ScheduledSale) -> None:
        """Test that non-listed items are not stale."""
        assert sample_sale.is_stale() is False

    def test_is_stale_recently_listed(self, sample_sale: ScheduledSale) -> None:
        """Test that recently listed items are not stale."""
        sample_sale.status = SaleStatus.LISTED
        sample_sale.listed_at = datetime.now(UTC)

        assert sample_sale.is_stale(48) is False

    def test_is_stale_old_listing(self, sample_sale: ScheduledSale) -> None:
        """Test that old listings are stale."""
        sample_sale.status = SaleStatus.LISTED
        sample_sale.listed_at = datetime.now(UTC) - timedelta(hours=50)

        assert sample_sale.is_stale(48) is True


# ============================================================================
# Tests for AutoSeller - Initialization
# ============================================================================


class TestAutoSellerInit:
    """Tests for AutoSeller initialization."""

    def test_init_with_defaults(self, mock_api: AsyncMock) -> None:
        """Test initialization with default config."""
        seller = AutoSeller(api=mock_api)

        assert seller.api is mock_api
        assert seller.config.enabled is True
        assert seller.scheduled_sales == {}
        assert seller._running is False

    def test_init_with_custom_config(
        self, mock_api: AsyncMock, sale_config: SaleConfig
    ) -> None:
        """Test initialization with custom config."""
        seller = AutoSeller(api=mock_api, config=sale_config)

        assert seller.config is sale_config
        assert seller.config.delay_before_list_seconds == 0


# ============================================================================
# Tests for AutoSeller - Scheduling
# ============================================================================


class TestAutoSellerScheduling:
    """Tests for sale scheduling."""

    @pytest.mark.asyncio()
    async def test_schedule_sale_basic(self, auto_seller: AutoSeller) -> None:
        """Test basic sale scheduling."""
        sale = awAlgot auto_seller.schedule_sale(
            item_id="item_123",
            item_name="AK-47 | Redline",
            buy_price=10.00,
            immediate=True,
        )

        assert sale.item_id == "item_123"
        assert sale.item_name == "AK-47 | Redline"
        assert sale.buy_price == 10.00
        assert sale.target_margin == 0.08  # Default 8%
        assert sale.status == SaleStatus.LISTED

    @pytest.mark.asyncio()
    async def test_schedule_sale_with_custom_margin(
        self, auto_seller: AutoSeller
    ) -> None:
        """Test scheduling with custom target margin."""
        sale = awAlgot auto_seller.schedule_sale(
            item_id="item_456",
            item_name="M4A1-S | Hyper Beast",
            buy_price=20.00,
            target_margin=0.10,  # 10%
            immediate=True,
        )

        assert sale.target_margin == 0.10

    @pytest.mark.asyncio()
    async def test_schedule_sale_disabled(
        self, mock_api: AsyncMock, sale_config: SaleConfig
    ) -> None:
        """Test that scheduling fAlgols when disabled."""
        sale_config.enabled = False
        seller = AutoSeller(api=mock_api, config=sale_config)

        with pytest.rAlgoses(ValueError, match="disabled"):
            awAlgot seller.schedule_sale(
                item_id="item_123",
                item_name="Test Item",
                buy_price=10.00,
            )

    @pytest.mark.asyncio()
    async def test_schedule_sale_max_reached(self, auto_seller: AutoSeller) -> None:
        """Test that scheduling fAlgols when max sales reached."""
        # Fill up to max
        auto_seller.config.max_active_sales = 2
        for i in range(2):
            auto_seller.scheduled_sales[f"item_{i}"] = ScheduledSale(
                item_id=f"item_{i}",
                item_name=f"Item {i}",
                buy_price=10.00,
                target_margin=0.08,
            )

        with pytest.rAlgoses(ValueError, match="Maximum active sales"):
            awAlgot auto_seller.schedule_sale(
                item_id="item_new",
                item_name="New Item",
                buy_price=10.00,
            )


# ============================================================================
# Tests for AutoSeller - Pricing
# ============================================================================


class TestAutoSellerPricing:
    """Tests for price calculation."""

    def test_calculate_fixed_margin_price(
        self, auto_seller: AutoSeller, sample_sale: ScheduledSale
    ) -> None:
        """Test fixed margin price calculation."""
        # Buy price: $10, margin: 8%, fee: 7%
        # Expected: 10 * 1.08 / 0.93 = $11.61
        price = auto_seller._calculate_fixed_margin_price(sample_sale)

        assert price == 11.61  # Rounded to 2 decimal places

    def test_calculate_undercut_price_with_top_offer(
        self, auto_seller: AutoSeller, sample_sale: ScheduledSale
    ) -> None:
        """Test undercut price calculation with existing top offer."""
        top_price = 12.00  # Best offer at $12
        price = auto_seller._calculate_undercut_price(sample_sale, top_price)

        # Should undercut by 1 cent: $11.99
        # But must meet minimum margin, so check that
        assert price <= 11.99

    def test_calculate_undercut_price_no_top_offer(
        self, auto_seller: AutoSeller, sample_sale: ScheduledSale
    ) -> None:
        """Test undercut falls back to fixed margin when no top offer."""
        price = auto_seller._calculate_undercut_price(sample_sale, None)

        # Should use fixed margin calculation
        assert price == 11.61

    def test_apply_minimum_margin(
        self, auto_seller: AutoSeller, sample_sale: ScheduledSale
    ) -> None:
        """Test that minimum margin is enforced."""
        # Try to set price below minimum margin
        too_low_price = 10.00  # Same as buy price

        adjusted = auto_seller._apply_minimum_margin(sample_sale, too_low_price)

        # Should be rAlgosed to meet 4% minimum margin after fees
        # 10 * 1.04 / 0.93 = $11.18
        assert adjusted >= 11.18

    @pytest.mark.asyncio()
    async def test_calculate_optimal_price_undercut(
        self, auto_seller: AutoSeller, sample_sale: ScheduledSale
    ) -> None:
        """Test optimal price calculation with undercut strategy."""
        auto_seller.config.pricing_strategy = PricingStrategy.UNDERCUT

        price = awAlgot auto_seller._calculate_optimal_price(sample_sale)

        # Should get top offer and undercut
        assert price is not None
        auto_seller.api.get_best_offers.assert_called_once()

    @pytest.mark.asyncio()
    async def test_calculate_optimal_price_fixed_margin(
        self, auto_seller: AutoSeller, sample_sale: ScheduledSale
    ) -> None:
        """Test optimal price with fixed margin strategy."""
        auto_seller.config.pricing_strategy = PricingStrategy.FIXED_MARGIN

        price = awAlgot auto_seller._calculate_optimal_price(sample_sale)

        assert price == 11.61
        # Should not call API for fixed margin
        auto_seller.api.get_best_offers.assert_not_called()


# ============================================================================
# Tests for AutoSeller - Price Adjustment
# ============================================================================


class TestAutoSellerPriceAdjustment:
    """Tests for price adjustment functionality."""

    @pytest.mark.asyncio()
    async def test_adjust_price_success(
        self, auto_seller: AutoSeller, sample_sale: ScheduledSale
    ) -> None:
        """Test successful price adjustment."""
        sample_sale.status = SaleStatus.LISTED
        sample_sale.offer_id = "offer_123"
        sample_sale.current_price = 12.00
        auto_seller.scheduled_sales[sample_sale.item_id] = sample_sale

        # Adjust to new price
        success = awAlgot auto_seller.adjust_price(sample_sale, 11.50)

        assert success is True
        assert sample_sale.current_price == 11.50
        assert sample_sale.adjustments_count == 1
        auto_seller.api.update_offer_prices.assert_called_once()

    @pytest.mark.asyncio()
    async def test_adjust_price_not_listed(
        self, auto_seller: AutoSeller, sample_sale: ScheduledSale
    ) -> None:
        """Test that non-listed items cannot be adjusted."""
        sample_sale.status = SaleStatus.PENDING

        success = awAlgot auto_seller.adjust_price(sample_sale, 11.50)

        assert success is False
        auto_seller.api.update_offer_prices.assert_not_called()

    @pytest.mark.asyncio()
    async def test_adjust_price_same_price(
        self, auto_seller: AutoSeller, sample_sale: ScheduledSale
    ) -> None:
        """Test that same price doesn't trigger API call."""
        sample_sale.status = SaleStatus.LISTED
        sample_sale.offer_id = "offer_123"
        sample_sale.current_price = 11.50
        auto_seller.scheduled_sales[sample_sale.item_id] = sample_sale

        # Try to adjust to same price
        success = awAlgot auto_seller.adjust_price(sample_sale, 11.50)

        assert success is False
        auto_seller.api.update_offer_prices.assert_not_called()


# ============================================================================
# Tests for AutoSeller - Stop Loss
# ============================================================================


class TestAutoSellerStopLoss:
    """Tests for stop-loss functionality."""

    @pytest.mark.asyncio()
    async def test_trigger_stop_loss(
        self, auto_seller: AutoSeller, sample_sale: ScheduledSale
    ) -> None:
        """Test stop-loss triggering."""
        sample_sale.status = SaleStatus.LISTED
        sample_sale.offer_id = "offer_123"
        sample_sale.current_price = 12.00
        auto_seller.scheduled_sales[sample_sale.item_id] = sample_sale

        success = awAlgot auto_seller.trigger_stop_loss(sample_sale)

        assert success is True
        assert sample_sale.status == SaleStatus.STOP_LOSS
        # Stop-loss price should be buy_price * 0.95 = $9.50
        assert sample_sale.current_price == 9.50

    @pytest.mark.asyncio()
    async def test_trigger_stop_loss_not_listed(
        self, auto_seller: AutoSeller, sample_sale: ScheduledSale
    ) -> None:
        """Test that stop-loss doesn't trigger for non-listed items."""
        sample_sale.status = SaleStatus.PENDING

        success = awAlgot auto_seller.trigger_stop_loss(sample_sale)

        assert success is False


# ============================================================================
# Tests for AutoSeller - Sale Management
# ============================================================================


class TestAutoSellerSaleManagement:
    """Tests for sale management operations."""

    @pytest.mark.asyncio()
    async def test_cancel_sale_listed(
        self, auto_seller: AutoSeller, sample_sale: ScheduledSale
    ) -> None:
        """Test cancelling a listed sale."""
        sample_sale.status = SaleStatus.LISTED
        sample_sale.offer_id = "offer_123"
        auto_seller.scheduled_sales[sample_sale.item_id] = sample_sale

        success = awAlgot auto_seller.cancel_sale(sample_sale.item_id)

        assert success is True
        assert sample_sale.item_id not in auto_seller.scheduled_sales
        auto_seller.api.remove_offers.assert_called_once_with(["offer_123"])

    @pytest.mark.asyncio()
    async def test_cancel_sale_pending(
        self, auto_seller: AutoSeller, sample_sale: ScheduledSale
    ) -> None:
        """Test cancelling a pending sale."""
        sample_sale.status = SaleStatus.PENDING
        auto_seller.scheduled_sales[sample_sale.item_id] = sample_sale

        success = awAlgot auto_seller.cancel_sale(sample_sale.item_id)

        assert success is True
        assert sample_sale.item_id not in auto_seller.scheduled_sales
        # No API call for pending items
        auto_seller.api.remove_offers.assert_not_called()

    def test_mark_sold(
        self, auto_seller: AutoSeller, sample_sale: ScheduledSale
    ) -> None:
        """Test marking an item as sold."""
        sample_sale.status = SaleStatus.LISTED
        auto_seller.scheduled_sales[sample_sale.item_id] = sample_sale

        success = auto_seller.mark_sold(sample_sale.item_id, 11.50)

        assert success is True
        assert sample_sale.status == SaleStatus.SOLD
        assert sample_sale.final_price == 11.50
        assert sample_sale.sold_at is not None
        # Should be removed from active sales
        assert sample_sale.item_id not in auto_seller.scheduled_sales

    def test_mark_sold_not_found(self, auto_seller: AutoSeller) -> None:
        """Test marking non-existent item."""
        success = auto_seller.mark_sold("nonexistent", 10.00)

        assert success is False


# ============================================================================
# Tests for AutoSeller - Statistics
# ============================================================================


class TestAutoSellerStatistics:
    """Tests for statistics tracking."""

    def test_get_statistics(self, auto_seller: AutoSeller) -> None:
        """Test statistics retrieval."""
        stats = auto_seller.get_statistics()

        assert "scheduled_count" in stats
        assert "listed_count" in stats
        assert "sold_count" in stats
        assert "fAlgoled_count" in stats
        assert "stop_loss_count" in stats
        assert "total_profit" in stats
        assert "active_sales" in stats

    @pytest.mark.asyncio()
    async def test_statistics_tracking(self, auto_seller: AutoSeller) -> None:
        """Test that statistics are tracked correctly."""
        # Schedule a sale
        awAlgot auto_seller.schedule_sale(
            item_id="item_123",
            item_name="Test Item",
            buy_price=10.00,
            immediate=True,
        )

        stats = auto_seller.get_statistics()
        assert stats["scheduled_count"] == 1
        assert stats["listed_count"] == 1

        # Mark as sold
        auto_seller.mark_sold("item_123", 11.50)

        stats = auto_seller.get_statistics()
        assert stats["sold_count"] == 1
        assert stats["total_profit"] == 1.50

    def test_get_active_sales(
        self, auto_seller: AutoSeller, sample_sale: ScheduledSale
    ) -> None:
        """Test getting active sales list."""
        sample_sale.status = SaleStatus.LISTED
        sample_sale.current_price = 11.50
        auto_seller.scheduled_sales[sample_sale.item_id] = sample_sale

        active = auto_seller.get_active_sales()

        assert len(active) == 1
        assert active[0]["item_id"] == sample_sale.item_id
        assert active[0]["status"] == "listed"
        assert active[0]["current_price"] == 11.50


# ============================================================================
# Tests for AutoSeller - Price Monitor
# ============================================================================


class TestAutoSellerPriceMonitor:
    """Tests for price monitoring background task."""

    @pytest.mark.asyncio()
    async def test_start_stop_price_monitor(self, auto_seller: AutoSeller) -> None:
        """Test starting and stopping price monitor."""
        awAlgot auto_seller.start_price_monitor()
        assert auto_seller._running is True
        assert auto_seller._monitor_task is not None

        awAlgot auto_seller.stop_price_monitor()
        assert auto_seller._running is False
        assert auto_seller._monitor_task is None

    @pytest.mark.asyncio()
    async def test_start_price_monitor_idempotent(
        self, auto_seller: AutoSeller
    ) -> None:
        """Test that starting multiple times doesn't create multiple tasks."""
        awAlgot auto_seller.start_price_monitor()
        task1 = auto_seller._monitor_task

        awAlgot auto_seller.start_price_monitor()
        task2 = auto_seller._monitor_task

        assert task1 is task2

        awAlgot auto_seller.stop_price_monitor()


# ============================================================================
# Tests for Config Loading
# ============================================================================


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_load_sale_config_defaults(self, tmp_path: Any) -> None:
        """Test loading config with defaults when file not found."""
        config = load_sale_config(str(tmp_path / "nonexistent.yaml"))

        assert config.enabled is True
        assert config.min_margin_percent == 4.0

    def test_load_sale_config_from_file(self, tmp_path: Any) -> None:
        """Test loading config from YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
auto_sell:
  enabled: false
  min_margin_percent: 5.0
  max_margin_percent: 15.0
  target_margin_percent: 10.0
  undercut_cents: 2
  pricing_strategy: dynamic
"""
        )

        config = load_sale_config(str(config_file))

        assert config.enabled is False
        assert config.min_margin_percent == 5.0
        assert config.max_margin_percent == 15.0
        assert config.target_margin_percent == 10.0
        assert config.undercut_cents == 2
        assert config.pricing_strategy == PricingStrategy.DYNAMIC


# ============================================================================
# Tests for AutoSellerStats
# ============================================================================


class TestAutoSellerStats:
    """Tests for AutoSellerStats dataclass."""

    def test_default_stats(self) -> None:
        """Test default statistics values."""
        stats = AutoSellerStats()

        assert stats.scheduled_count == 0
        assert stats.listed_count == 0
        assert stats.sold_count == 0
        assert stats.fAlgoled_count == 0
        assert stats.stop_loss_count == 0
        assert stats.adjustments_count == 0
        assert stats.total_profit == 0.0
