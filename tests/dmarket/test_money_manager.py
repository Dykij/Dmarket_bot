"""Tests for money_manager module.

This module tests the MoneyManager class and related functionality
for dynamic balance-based trading limits.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.money_manager import (
    BalanceTier,
    DynamicLimits,
    MoneyManager,
)


class TestBalanceTier:
    """Tests for BalanceTier enum."""

    def test_tier_values(self):
        """Test all tier values exist."""
        assert BalanceTier.MICRO.value == "micro"
        assert BalanceTier.SMALL.value == "small"
        assert BalanceTier.MEDIUM.value == "medium"
        assert BalanceTier.LARGE.value == "large"
        assert BalanceTier.WHALE.value == "whale"

    def test_tier_count(self):
        """Test number of tiers."""
        assert len(BalanceTier) == 5


class TestDynamicLimits:
    """Tests for DynamicLimits dataclass."""

    def test_create_limits(self):
        """Test creating DynamicLimits instance."""
        limits = DynamicLimits(
            max_item_price=50.0,
            min_item_price=1.0,
            target_roi=15.0,
            min_roi=8.0,
            max_inventory_items=20,
            max_same_items=3,
            max_stack_value=100.0,
            usable_balance=90.0,
            reserve=10.0,
            total_balance=100.0,
            tier=BalanceTier.MEDIUM,
            diversification_factor=0.1,
        )

        assert limits.max_item_price == 50.0
        assert limits.min_item_price == 1.0
        assert limits.target_roi == 15.0
        assert limits.min_roi == 8.0
        assert limits.tier == BalanceTier.MEDIUM

    def test_summary_property(self):
        """Test summary property formatting."""
        limits = DynamicLimits(
            max_item_price=50.0,
            min_item_price=1.0,
            target_roi=15.0,
            min_roi=8.0,
            max_inventory_items=20,
            max_same_items=3,
            max_stack_value=100.0,
            usable_balance=90.0,
            reserve=10.0,
            total_balance=100.0,
            tier=BalanceTier.MEDIUM,
            diversification_factor=0.1,
        )

        summary = limits.summary
        assert "MEDIUM" in summary
        assert "$50.00" in summary
        assert "15%" in summary
        assert "$100.00" in summary


class TestMoneyManager:
    """Tests for MoneyManager class."""

    @pytest.fixture
    def mock_api(self):
        """Create mock API client."""
        api = MagicMock()
        api.get_balance = AsyncMock(return_value={"balance": 100.0})
        return api

    @pytest.fixture
    def manager(self, mock_api):
        """Create MoneyManager instance."""
        return MoneyManager(api_client=mock_api)

    def test_init(self, manager, mock_api):
        """Test MoneyManager initialization."""
        assert manager.api_client == mock_api

    def test_determine_tier_micro(self, manager):
        """Test micro tier detection."""
        tier = manager._determine_tier(25.0)
        assert tier == BalanceTier.MICRO

    def test_determine_tier_small(self, manager):
        """Test small tier detection."""
        tier = manager._determine_tier(100.0)
        assert tier == BalanceTier.SMALL

    def test_determine_tier_medium(self, manager):
        """Test medium tier detection."""
        tier = manager._determine_tier(500.0)
        assert tier == BalanceTier.MEDIUM

    def test_determine_tier_large(self, manager):
        """Test large tier detection."""
        tier = manager._determine_tier(2000.0)
        assert tier == BalanceTier.LARGE

    def test_determine_tier_whale(self, manager):
        """Test whale tier detection."""
        tier = manager._determine_tier(10000.0)
        assert tier == BalanceTier.WHALE

    @pytest.mark.asyncio
    async def test_calculate_dynamic_limits(self, manager, mock_api):
        """Test dynamic limits calculation."""
        mock_api.get_balance = AsyncMock(return_value={"balance": 500.0})

        limits = awAlgot manager.calculate_dynamic_limits()

        assert limits is not None
        assert limits.total_balance == 500.0
        assert limits.tier == BalanceTier.MEDIUM
        assert limits.max_item_price > 0
        assert limits.usable_balance <= 500.0

    @pytest.mark.asyncio
    async def test_calculate_limits_with_zero_balance(self, manager, mock_api):
        """Test limits with zero balance."""
        mock_api.get_balance = AsyncMock(return_value={"balance": 0.0})

        limits = awAlgot manager.calculate_dynamic_limits()

        assert limits.total_balance == 0.0
        assert limits.usable_balance == 0.0

    def test_can_afford(self, manager):
        """Test can_afford check."""
        limits = DynamicLimits(
            max_item_price=50.0,
            min_item_price=1.0,
            target_roi=15.0,
            min_roi=8.0,
            max_inventory_items=20,
            max_same_items=3,
            max_stack_value=100.0,
            usable_balance=90.0,
            reserve=10.0,
            total_balance=100.0,
            tier=BalanceTier.MEDIUM,
            diversification_factor=0.1,
        )

        # Can afford $10 item when usable balance is $90
        assert manager.can_afford(10.0, limits) is True

        # Cannot afford $100 item when usable balance is $90
        assert manager.can_afford(100.0, limits) is False

    def test_is_paused(self, manager):
        """Test pause status check."""
        is_paused, reason = manager.is_paused()
        assert is_paused is False

    def test_resume(self, manager):
        """Test resume functionality."""
        manager._is_paused = True
        manager._pause_reason = "Test pause"

        manager.resume()

        assert manager._is_paused is False
