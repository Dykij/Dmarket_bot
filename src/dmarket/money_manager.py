"""Universal Money Management Module.

This module provides dynamic, percentage-based money management that scales
with any balance - from $10 to $10,000+.

Key Features:
- All limits calculated as percentages of balance (no hardcoded amounts)
- Automatic strategy adjustment based on balance tier
- Balance change detection with safety pause
- Reserve management for fees and emergencies

Usage:
    from src.dmarket.money_manager import MoneyManager

    manager = MoneyManager(api_client)
    limits = awAlgot manager.calculate_dynamic_limits()
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from src.interfaces import IDMarketAPI

logger = structlog.get_logger(__name__)


class BalanceTier(Enum):
    """Balance tiers for strategy selection."""

    MICRO = "micro"  # < $50
    SMALL = "small"  # $50 - $200
    MEDIUM = "medium"  # $200 - $1000
    LARGE = "large"  # $1000 - $5000
    WHALE = "whale"  # > $5000


@dataclass
class DynamicLimits:
    """Dynamically calculated trading limits."""

    # Price limits
    max_item_price: float  # Max price per item in USD
    min_item_price: float  # Min price per item in USD

    # Profit requirements
    target_roi: float  # Target ROI percentage
    min_roi: float  # Minimum acceptable ROI

    # Inventory limits
    max_inventory_items: int
    max_same_items: int  # Max duplicates
    max_stack_value: float  # Max total value of same item type

    # Balance info
    usable_balance: float  # Balance minus reserve
    reserve: float  # Safety reserve amount
    total_balance: float

    # Strategy info
    tier: BalanceTier
    diversification_factor: float  # Percentage per item

    @property
    def summary(self) -> str:
        """Get human-readable summary."""
        return (
            f"Tier: {self.tier.value.upper()} | "
            f"Max: ${self.max_item_price:.2f} | "
            f"ROI: {self.target_roi:.0f}%+ | "
            f"Balance: ${self.total_balance:.2f}"
        )


@dataclass
class MoneyManagerConfig:
    """Configuration for money management."""

    # Percentage-based limits (no hardcoded amounts!)
    max_buy_percent: float = 0.25  # Max 25% of balance per item
    min_buy_percent: float = 0.005  # Min 0.5% of balance per item
    reserve_percent: float = 0.05  # Keep 5% as reserve
    max_stack_percent: float = 0.15  # Max 15% in same item type

    # Tier thresholds
    micro_threshold: float = 50.0
    small_threshold: float = 200.0
    medium_threshold: float = 1000.0
    large_threshold: float = 5000.0

    # ROI targets by tier (optimized for liquidity over margin)
    micro_roi: float = 8.0  # Fast turnover for tiny balances (was 20%)
    small_roi: float = 10.0  # Balanced approach (was 15%)
    medium_roi: float = 12.0
    large_roi: float = 10.0
    whale_roi: float = 8.0

    # Balance change detection
    balance_change_threshold: float = 0.5  # 50% change triggers pause
    enable_balance_protection: bool = True


class MoneyManager:
    """Universal money manager that scales with any balance.

    This manager uses percentage-based calculations instead of
    hardcoded dollar amounts, making it work equally well for
    $45.50 or $4,550.00 balances.
    """

    def __init__(
        self,
        api_client: IDMarketAPI,
        config: MoneyManagerConfig | None = None,
    ) -> None:
        """Initialize Money Manager.

        Args:
            api_client: DMarket API client
            config: Configuration (optional, uses defaults)
        """
        self.api_client = api_client
        self.config = config or MoneyManagerConfig()

        # State tracking
        self._current_balance: float = 0.0
        self._last_balance: float = 0.0
        self._last_check: datetime | None = None
        self._is_paused: bool = False
        self._pause_reason: str = ""

        logger.info(
            "money_manager_initialized",
            max_buy_percent=self.config.max_buy_percent,
            reserve_percent=self.config.reserve_percent,
        )

    async def get_balance(self, force_refresh: bool = False) -> float:
        """Get current balance with caching.

        Args:
            force_refresh: Force API call

        Returns:
            Current balance in USD
        """
        # Cache for 30 seconds
        if (
            not force_refresh
            and self._last_check
            and (datetime.now() - self._last_check).seconds < 30
        ):
            return self._current_balance

        try:
            balance_data = awAlgot self.api_client.get_balance()

            # Debug log to see what API returns
            logger.debug("money_manager_raw_balance", data=balance_data)

            new_balance = 0.0

            if isinstance(balance_data, dict):
                # DMarket API returns 'balance' field in dollars directly
                try:
                    new_balance = float(balance_data.get("balance", 0))
                except (ValueError, TypeError) as parse_err:
                    logger.exception(
                        "balance_parse_error", data=balance_data, error=str(parse_err)
                    )
                    new_balance = 0.0
            else:
                new_balance = 0.0

            # Check for significant balance change
            if self._current_balance > 0 and self.config.enable_balance_protection:
                change_ratio = (
                    abs(new_balance - self._current_balance) / self._current_balance
                )
                if change_ratio > self.config.balance_change_threshold:
                    self._is_paused = True
                    self._pause_reason = (
                        f"Balance changed by {change_ratio * 100:.0f}% "
                        f"(${self._current_balance:.2f} -> ${new_balance:.2f})"
                    )
                    logger.warning(
                        "balance_change_detected",
                        old=self._current_balance,
                        new=new_balance,
                        change_percent=change_ratio * 100,
                    )

            self._last_balance = self._current_balance
            self._current_balance = new_balance
            self._last_check = datetime.now()

            return self._current_balance

        except Exception as e:
            logger.exception("balance_fetch_error", error=str(e))
            return self._current_balance

    def _determine_tier(self, balance: float) -> BalanceTier:
        """Determine balance tier for strategy selection."""
        if balance < self.config.micro_threshold:
            return BalanceTier.MICRO
        if balance < self.config.small_threshold:
            return BalanceTier.SMALL
        if balance < self.config.medium_threshold:
            return BalanceTier.MEDIUM
        if balance < self.config.large_threshold:
            return BalanceTier.LARGE
        return BalanceTier.WHALE

    def _get_roi_for_tier(self, tier: BalanceTier) -> float:
        """Get target ROI based on balance tier."""
        roi_map = {
            BalanceTier.MICRO: self.config.micro_roi,
            BalanceTier.SMALL: self.config.small_roi,
            BalanceTier.MEDIUM: self.config.medium_roi,
            BalanceTier.LARGE: self.config.large_roi,
            BalanceTier.WHALE: self.config.whale_roi,
        }
        return roi_map.get(tier, 15.0)

    def _get_diversification_for_tier(self, tier: BalanceTier) -> float:
        """Get diversification factor based on tier.

        Higher balances should have lower per-item percentage for safety.
        """
        diversification_map = {
            BalanceTier.MICRO: 0.30,  # 30% per item (aggressive)
            BalanceTier.SMALL: 0.25,  # 25% per item
            BalanceTier.MEDIUM: 0.15,  # 15% per item
            BalanceTier.LARGE: 0.10,  # 10% per item
            BalanceTier.WHALE: 0.05,  # 5% per item (conservative)
        }
        return diversification_map.get(tier, 0.25)

    def _get_inventory_limits_for_tier(self, tier: BalanceTier) -> tuple[int, int]:
        """Get inventory limits (max_items, max_same) based on tier."""
        limits_map = {
            BalanceTier.MICRO: (20, 3),
            BalanceTier.SMALL: (40, 5),
            BalanceTier.MEDIUM: (75, 7),
            BalanceTier.LARGE: (150, 10),
            BalanceTier.WHALE: (300, 15),
        }
        return limits_map.get(tier, (50, 5))

    async def calculate_dynamic_limits(
        self, force_balance_refresh: bool = False
    ) -> DynamicLimits:
        """Calculate all trading limits based on current balance.

        This is the core method that makes everything percentage-based.

        Returns:
            DynamicLimits with all calculated parameters
        """
        balance = awAlgot self.get_balance(force_refresh=force_balance_refresh)
        tier = self._determine_tier(balance)

        # Calculate reserve (percentage of balance)
        reserve = balance * self.config.reserve_percent
        usable = max(0, balance - reserve)

        # Get tier-specific settings
        diversification = self._get_diversification_for_tier(tier)
        target_roi = self._get_roi_for_tier(tier)
        max_items, max_same = self._get_inventory_limits_for_tier(tier)

        # Calculate price limits (all percentage-based!)
        max_price = usable * diversification
        min_price = max(0.10, balance * self.config.min_buy_percent)

        # Calculate max stack value
        max_stack = usable * self.config.max_stack_percent

        limits = DynamicLimits(
            max_item_price=round(max_price, 2),
            min_item_price=round(min_price, 2),
            target_roi=target_roi,
            min_roi=target_roi - 5.0,  # Allow 5% below target
            max_inventory_items=max_items,
            max_same_items=max_same,
            max_stack_value=round(max_stack, 2),
            usable_balance=round(usable, 2),
            reserve=round(reserve, 2),
            total_balance=round(balance, 2),
            tier=tier,
            diversification_factor=diversification,
        )

        logger.info(
            "dynamic_limits_calculated",
            tier=tier.value,
            balance=balance,
            max_price=limits.max_item_price,
            target_roi=limits.target_roi,
        )

        return limits

    def can_afford(self, price: float, limits: DynamicLimits | None = None) -> bool:
        """Check if we can afford an item within current limits.

        Args:
            price: Item price in USD
            limits: Pre-calculated limits (optional)

        Returns:
            True if purchase is within limits
        """
        if limits is None:
            # Quick check without full calculation
            reserve = self._current_balance * self.config.reserve_percent
            max_price = (self._current_balance - reserve) * self.config.max_buy_percent
            return price <= max_price and price <= self._current_balance - reserve

        return price <= limits.max_item_price and price <= limits.usable_balance

    def is_paused(self) -> tuple[bool, str]:
        """Check if manager is paused due to balance change.

        Returns:
            Tuple of (is_paused, reason)
        """
        return self._is_paused, self._pause_reason

    def resume(self) -> None:
        """Resume after pause (user confirmation)."""
        self._is_paused = False
        self._pause_reason = ""
        logger.info("money_manager_resumed")

    def get_strategy_description(self, limits: DynamicLimits) -> str:
        """Get human-readable strategy description for current tier.

        Args:
            limits: Current calculated limits

        Returns:
            Strategy description string
        """
        tier_strategies = {
            BalanceTier.MICRO: (
                "🎯 MICRO Strategy: Fast turnover mode.\n"
                "Focus: Cheap cases, stickers & high-liquidity items.\n"
                "Target: ROI 5-8% with quick resale. Volume over margin."
            ),
            BalanceTier.SMALL: (
                "📈 SMALL Strategy: Balanced growth mode.\n"
                "Focus: Cases, cheap skins, and TF2 keys.\n"
                "Target: ROI 10%+ with diversification."
            ),
            BalanceTier.MEDIUM: (
                "💼 MEDIUM Strategy: Stable growth mode.\n"
                "Focus: Popular skins, mid-range items.\n"
                "Risk: Standard ROI (12%+) with broader portfolio."
            ),
            BalanceTier.LARGE: (
                "🏦 LARGE Strategy: Capital preservation mode.\n"
                "Focus: High-liquidity items, safer bets.\n"
                "Risk: Lower ROI (10%+) but larger absolute profits."
            ),
            BalanceTier.WHALE: (
                "🐋 WHALE Strategy: Conservative mode.\n"
                "Focus: Premium items, rare collectibles.\n"
                "Risk: Minimal ROI (8%+) with maximum diversification."
            ),
        }
        return tier_strategies.get(limits.tier, "Unknown strategy tier")


# Standalone helper function
def calculate_universal_limits(balance: float) -> dict[str, Any]:
    """Calculate limits without instantiating full manager.

    This is a convenience function for quick calculations.

    Args:
        balance: Current balance in USD

    Returns:
        Dict with all calculated limits
    """
    config = MoneyManagerConfig()

    # Determine tier
    if balance < config.micro_threshold:
        tier = "micro"
        diversification = 0.30
        roi = config.micro_roi
        max_items, max_same = 20, 3
    elif balance < config.small_threshold:
        tier = "small"
        diversification = 0.25
        roi = config.small_roi
        max_items, max_same = 40, 5
    elif balance < config.medium_threshold:
        tier = "medium"
        diversification = 0.15
        roi = config.medium_roi
        max_items, max_same = 75, 7
    elif balance < config.large_threshold:
        tier = "large"
        diversification = 0.10
        roi = config.large_roi
        max_items, max_same = 150, 10
    else:
        tier = "whale"
        diversification = 0.05
        roi = config.whale_roi
        max_items, max_same = 300, 15

    reserve = balance * config.reserve_percent
    usable = max(0, balance - reserve)

    return {
        "tier": tier,
        "max_item_price": round(usable * diversification, 2),
        "min_item_price": round(max(0.10, balance * config.min_buy_percent), 2),
        "target_roi": roi,
        "min_roi": roi - 5.0,
        "max_inventory_items": max_items,
        "max_same_items": max_same,
        "max_stack_value": round(usable * config.max_stack_percent, 2),
        "usable_balance": round(usable, 2),
        "reserve": round(reserve, 2),
        "diversification_percent": diversification * 100,
    }
