"""Smart Repricing Module for automatic price adjustments.

This module handles:
- Age-based repricing (reduce prices for stale listings)
- Dynamic undercut (smart spread analysis)
- Night mode pricing (aggressive selling during low activity)
- Panic sell protection (market crash detection)
"""

import logging
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI

logger = logging.getLogger(__name__)


class RepricingAction(StrEnum):
    """Actions for repricing based on listing age."""

    HOLD = "hold"  # Keep current price
    REDUCE_TO_TARGET = "reduce_to_target"  # Reduce to target margin
    REDUCE_TO_BREAK_EVEN = "reduce_to_break_even"  # Reduce to break-even
    LIQUIDATE = "liquidate"  # Sell at any price (emergency exit)


class SmartRepricer:
    """Intelligent repricing engine for inventory management."""

    def __init__(
        self,
        api_client: "DMarketAPI",
        config: dict[str, Any] | None = None,
    ):
        """Initialize smart repricer.

        Args:
            api_client: DMarket API client
            config: Configuration dictionary
        """
        self.api = api_client
        self.config = config or {}

        # Default repricing intervals (hours -> action)
        self.repricing_rules = self.config.get(
            "repricing_intervals",
            [
                {"hours": 24, "action": RepricingAction.REDUCE_TO_TARGET},
                {"hours": 48, "action": RepricingAction.REDUCE_TO_BREAK_EVEN},
                {"hours": 72, "action": RepricingAction.LIQUIDATE},
            ],
        )

        # Price limits
        self.max_price_cut_percent = self.config.get("max_price_cut_percent", 15)
        self.dmarket_fee_percent = self.config.get("dmarket_fee_percent", 7.0)

        # Night mode settings (UTC hours)
        self.night_mode_enabled = self.config.get("night_mode_enabled", True)
        self.night_start_hour = self.config.get("night_start_hour", 2)
        self.night_end_hour = self.config.get("night_end_hour", 6)
        self.night_undercut_multiplier = self.config.get(
            "night_undercut_multiplier", 2.0
        )

        # Panic sell protection
        self.panic_threshold_percent = self.config.get("panic_threshold_percent", 15)
        self.panic_check_hours = self.config.get("panic_check_hours", 1)

        # Price history cache for panic detection
        self._price_history: dict[str, list[tuple[datetime, int]]] = {}

        logger.info(
            "SmartRepricer initialized: "
            f"max_cut={self.max_price_cut_percent}%, "
            f"night_mode={self.night_mode_enabled}, "
            f"panic_threshold={self.panic_threshold_percent}%"
        )

    def is_night_mode(self) -> bool:
        """Check if current time is in night mode window."""
        if not self.night_mode_enabled:
            return False
        current_hour = datetime.now(UTC).hour
        return self.night_start_hour <= current_hour < self.night_end_hour

    def get_undercut_step(self, base_step: int = 1) -> int:
        """Get undercut step based on time of day.

        Args:
            base_step: Base undercut step in cents

        Returns:
            Adjusted undercut step
        """
        if self.is_night_mode():
            return int(base_step * self.night_undercut_multiplier)
        return base_step

    def determine_repricing_action(
        self,
        listed_at: datetime,
        current_time: datetime | None = None,
    ) -> RepricingAction:
        """Determine what repricing action to take based on listing age.

        Args:
            listed_at: When the item was listed
            current_time: Current time (for testing)

        Returns:
            RepricingAction to take
        """
        if current_time is None:
            current_time = datetime.now(UTC)

        # Ensure both datetimes are timezone-aware
        if listed_at.tzinfo is None:
            listed_at = listed_at.replace(tzinfo=UTC)

        hours_listed = (current_time - listed_at).total_seconds() / 3600

        # Find the appropriate action based on hours listed
        action = RepricingAction.HOLD
        for rule in sorted(self.repricing_rules, key=lambda x: x.get("hours", 0)):
            if hours_listed >= rule.get("hours", 0):
                action = RepricingAction(rule.get("action", RepricingAction.HOLD))

        return action

    def calculate_new_price(
        self,
        item: dict[str, Any],
        market_min_price: int,
        action: RepricingAction,
    ) -> int | None:
        """Calculate new price based on repricing action.

        Args:
            item: Item data with buy_price and current_price
            market_min_price: Current minimum market price (cents)
            action: Repricing action to take

        Returns:
            New price in cents, or None if no change needed
        """
        # Extract buy price
        buy_price_data = item.get("buy_price", item.get("buyPrice", 0))
        if isinstance(buy_price_data, dict):
            buy_price = int(buy_price_data.get("amount", 0))
        else:
            buy_price = int(buy_price_data) if buy_price_data else 0

        # Extract current price
        current_price_data = item.get("price", item.get("currentPrice", 0))
        if isinstance(current_price_data, dict):
            current_price = int(current_price_data.get("amount", 0))
        else:
            current_price = int(current_price_data) if current_price_data else 0

        if buy_price <= 0:
            logger.warning(
                f"Cannot reprice item without buy_price: {item.get('title')}"
            )
            return None

        # Calculate price limits
        # Break-even: sell_price * 0.93 = buy_price -> sell_price = buy_price / 0.93
        break_even_price = int(buy_price / (1 - self.dmarket_fee_percent / 100))
        max_cut_price = int(current_price * (1 - self.max_price_cut_percent / 100))
        undercut_step = self.get_undercut_step()

        new_price: int | None = None

        if action == RepricingAction.HOLD:
            # Just undercut if needed
            if market_min_price < current_price:
                new_price = max(market_min_price - undercut_step, break_even_price)
            else:
                return None  # No change needed

        elif action == RepricingAction.REDUCE_TO_TARGET:
            # Target 5% profit above break-even
            target_price = int(break_even_price * 1.05)
            new_price = max(
                min(market_min_price - undercut_step, target_price), break_even_price
            )

        elif action == RepricingAction.REDUCE_TO_BREAK_EVEN:
            # Sell at break-even (no profit, no loss)
            new_price = min(market_min_price - undercut_step, break_even_price)

        elif action == RepricingAction.LIQUIDATE:
            # Emergency exit - sell at market price or below
            new_price = market_min_price - undercut_step
            # Allow going below break-even, but log warning
            if new_price < break_even_price:
                logger.warning(
                    f"LIQUIDATING {item.get('title')} at loss: "
                    f"${new_price / 100:.2f} < break-even ${break_even_price / 100:.2f}"
                )

        # Apply maximum cut limit (except for liquidation)
        if action != RepricingAction.LIQUIDATE and new_price:
            new_price = max(new_price, max_cut_price)

        # Don't reprice if new price equals current
        if new_price and new_price == current_price:
            return None

        return new_price

    def calculate_dynamic_undercut(
        self,
        my_price: int,
        market_prices: list[int],
    ) -> int:
        """Calculate smart undercut based on order book density.

        Instead of always undercutting by $0.01, analyze the spread between
        competitors and undercut just enough to be first.

        Args:
            my_price: Current listing price (cents)
            market_prices: List of competitor prices (sorted ascending)

        Returns:
            Optimal new price (cents)
        """
        if not market_prices:
            return my_price

        lowest_price = market_prices[0]

        # If we're already the lowest, no change needed
        if my_price <= lowest_price:
            return my_price

        # Calculate spread between 1st and 2nd position
        if len(market_prices) >= 2:
            first_second_spread = market_prices[1] - market_prices[0]
        else:
            first_second_spread = 1  # Default $0.01

        # Dynamic undercut logic:
        # If spread is large (>$0.10), we can keep more profit
        # If spread is small (<$0.03), just undercut by $0.01
        base_step = self.get_undercut_step()

        if first_second_spread > 10:  # > $0.10 spread
            # Undercut by half the spread (max $0.05)
            optimal_undercut = min(first_second_spread // 2, 5)
        elif first_second_spread > 3:  # $0.03-$0.10 spread
            # Undercut by $0.02
            optimal_undercut = 2
        else:
            # Tight spread, just $0.01
            optimal_undercut = base_step

        new_price = lowest_price - optimal_undercut
        return max(new_price, 1)  # Minimum 1 cent

    async def check_market_panic(
        self,
        item_title: str,
        current_price: int,
    ) -> bool:
        """Check if market is in panic mode (price crashed recently).

        Args:
            item_title: Item title for tracking
            current_price: Current market price (cents)

        Returns:
            True if panic detected (should pause selling)
        """
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=self.panic_check_hours)

        # Initialize or clean price history
        if item_title not in self._price_history:
            self._price_history[item_title] = []

        # Remove old entries
        self._price_history[item_title] = [
            (ts, price) for ts, price in self._price_history[item_title] if ts > cutoff
        ]

        # Add current price
        self._price_history[item_title].append((now, current_price))

        history = self._price_history[item_title]
        if len(history) < 2:
            return False

        # Check for price crash
        oldest_price = history[0][1]
        if oldest_price <= 0:
            return False

        price_change_percent = (current_price - oldest_price) / oldest_price * 100

        if price_change_percent <= -self.panic_threshold_percent:
            logger.warning(
                f"🚨 MARKET PANIC detected for {item_title}: "
                f"{price_change_percent:.1f}% drop in {self.panic_check_hours}h"
            )
            return True

        return False

    async def should_pause_selling(
        self,
        item: dict[str, Any],
        market_min_price: int,
    ) -> bool:
        """Check if selling should be paused for this item.

        Args:
            item: Item data
            market_min_price: Current minimum market price

        Returns:
            True if selling should be paused
        """
        title = item.get("title", "Unknown")
        return await self.check_market_panic(title, market_min_price)

    def get_repricing_summary(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate summary of repricing actions needed.

        Args:
            items: List of items with listing data

        Returns:
            Summary dictionary with counts per action
        """
        summary = {
            "hold": 0,
            "reduce_to_target": 0,
            "reduce_to_break_even": 0,
            "liquidate": 0,
            "total": len(items),
        }

        now = datetime.now(UTC)

        for item in items:
            listed_at_str = item.get("createdAt", item.get("listed_at"))
            if listed_at_str:
                try:
                    if isinstance(listed_at_str, str):
                        listed_at = datetime.fromisoformat(listed_at_str)
                    else:
                        listed_at = listed_at_str
                    action = self.determine_repricing_action(listed_at, now)
                    summary[action.value] += 1
                except (ValueError, TypeError):
                    summary["hold"] += 1
            else:
                summary["hold"] += 1

        return summary
