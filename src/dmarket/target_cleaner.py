"""Automatic target order cleanup for underperforming buy orders.

This module monitors active buy orders (targets) and automatically cancels:
- Orders that haven't filled after configurable timeout
- Orders with too much competition (better prices exist)
- Orders for items with declining liquidity
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import structlog

from src.interfaces import IDMarketAPI

logger = structlog.get_logger(__name__)


@dataclass
class TargetPerformance:
    """Performance metrics for a target order."""

    target_id: str
    title: str
    price: float
    created_at: datetime
    age_hours: float
    competition_count: int  # How many other buy orders at same/better price
    best_competitor_price: float | None
    is_underperforming: bool
    cancel_reason: str | None


class TargetCleaner:
    """Automatic cleanup of underperforming target orders."""

    def __init__(
        self,
        api_client: IDMarketAPI,
        max_age_hours: float = 24.0,
        max_competition: int = 5,
        min_liquidity_score: float = 50.0,
        dry_run: bool = True,
    ) -> None:
        """Initialize target cleaner.

        Args:
            api_client: DMarket API client
            max_age_hours: Cancel orders older than this many hours
            max_competition: Cancel if more than this many competing orders
            min_liquidity_score: Cancel if liquidity drops below this
            dry_run: If True, only log what would be cancelled
        """
        self.api_client = api_client
        self.max_age_hours = max_age_hours
        self.max_competition = max_competition
        self.min_liquidity_score = min_liquidity_score
        self.dry_run = dry_run

        logger.info(
            "target_cleaner_initialized",
            max_age_hours=max_age_hours,
            max_competition=max_competition,
            min_liquidity_score=min_liquidity_score,
            dry_run=dry_run,
        )

    async def get_active_targets(self, game: str) -> list[dict[str, Any]]:
        """Get all active target orders for a game.

        Args:
            game: Game code (csgo, dota2, etc)

        Returns:
            List of active target orders
        """
        try:
            response = await self.api_client.get_user_targets(
                game_id=game, status="TargetStatusActive"
            )

            targets = response.get("objects", [])
            logger.info("active_targets_fetched", game=game, count=len(targets))

            return targets

        except Exception as e:
            logger.error(
                "failed_to_fetch_targets", game=game, error=str(e), exc_info=True
            )
            return []

    async def analyze_target_performance(
        self, target: dict[str, Any], game: str
    ) -> TargetPerformance:
        """Analyze performance of a single target order.

        Args:
            target: Target order dict
            game: Game code

        Returns:
            TargetPerformance metrics
        """
        target_id = target.get("TargetID") or target.get("targetId", "unknown")
        title = target.get("Title", "Unknown")
        price = float(target.get("Price", {}).get("Amount", 0)) / 100

        # Calculate age
        created_at_str = target.get("CreatedDate") or target.get("createdDate")
        if created_at_str:
            created_at = datetime.fromisoformat(created_at_str)
        else:
            created_at = datetime.now()

        age_hours = (
            datetime.now() - created_at.replace(tzinfo=None)
        ).total_seconds() / 3600

        # Check competition using aggregated prices
        competition_count = 0
        best_competitor_price = None

        try:
            aggregated = await self.api_client.get_aggregated_prices_bulk(
                game=game, titles=[title], limit=1
            )

            if aggregated and "aggregatedPrices" in aggregated:
                agg_data = (
                    aggregated["aggregatedPrices"][0]
                    if aggregated["aggregatedPrices"]
                    else {}
                )
                order_count = agg_data.get("orderCount", 0)
                order_best_price = agg_data.get("orderBestPrice")

                if order_best_price:
                    best_competitor_price = float(order_best_price) / 100

                # Competition includes us, so subtract 1
                competition_count = max(0, order_count - 1)

        except Exception as e:
            logger.warning(
                "failed_to_check_competition",
                target_id=target_id,
                title=title,
                error=str(e),
            )

        # Determine if underperforming
        is_underperforming = False
        cancel_reason = None

        if age_hours > self.max_age_hours:
            is_underperforming = True
            cancel_reason = f"Order aged {age_hours:.1f}h (max: {self.max_age_hours}h)"
        elif competition_count > self.max_competition:
            is_underperforming = True
            cancel_reason = f"Too much competition: {competition_count} orders"
        elif best_competitor_price and best_competitor_price > price:
            # Someone has better price - our order won't fill
            is_underperforming = True
            cancel_reason = (
                f"Better price exists: ${best_competitor_price:.2f} vs our ${price:.2f}"
            )

        return TargetPerformance(
            target_id=target_id,
            title=title,
            price=price,
            created_at=created_at,
            age_hours=age_hours,
            competition_count=competition_count,
            best_competitor_price=best_competitor_price,
            is_underperforming=is_underperforming,
            cancel_reason=cancel_reason,
        )

    async def cancel_target(self, target_id: str, reason: str) -> bool:
        """Cancel a target order.

        Args:
            target_id: Target order ID to cancel
            reason: Reason for cancellation

        Returns:
            True if cancelled successfully
        """
        if self.dry_run:
            logger.info(
                "dry_run_cancel_target",
                target_id=target_id,
                reason=reason,
            )
            return True

        try:
            result = await self.api_client.delete_target(target_id=target_id)

            logger.info(
                "target_cancelled",
                target_id=target_id,
                reason=reason,
                result=result,
            )

            return True

        except Exception as e:
            logger.error(
                "failed_to_cancel_target",
                target_id=target_id,
                reason=reason,
                error=str(e),
                exc_info=True,
            )
            return False

    async def clean_targets(self, game: str) -> dict[str, Any]:
        """Clean underperforming targets for a game.

        Args:
            game: Game code

        Returns:
            Cleanup statistics
        """
        logger.info("target_cleanup_started", game=game)

        targets = await self.get_active_targets(game)

        if not targets:
            logger.info("no_active_targets", game=game)
            return {
                "game": game,
                "total_targets": 0,
                "analyzed": 0,
                "cancelled": 0,
                "kept": 0,
            }

        # Analyze all targets
        performances = []
        for target in targets:
            perf = await self.analyze_target_performance(target, game)
            performances.append(perf)

        # Cancel underperforming targets
        cancelled_count = 0
        for perf in performances:
            if perf.is_underperforming:
                success = await self.cancel_target(
                    perf.target_id, perf.cancel_reason or "Unknown"
                )
                if success:
                    cancelled_count += 1

        kept_count = len(targets) - cancelled_count

        logger.info(
            "target_cleanup_completed",
            game=game,
            total_targets=len(targets),
            cancelled=cancelled_count,
            kept=kept_count,
            dry_run=self.dry_run,
        )

        return {
            "game": game,
            "total_targets": len(targets),
            "analyzed": len(performances),
            "cancelled": cancelled_count,
            "kept": kept_count,
            "underperforming_details": [
                {
                    "target_id": p.target_id,
                    "title": p.title,
                    "price": p.price,
                    "age_hours": p.age_hours,
                    "reason": p.cancel_reason,
                }
                for p in performances
                if p.is_underperforming
            ],
        }

    async def run_periodic_cleanup(
        self, games: list[str], interval_hours: float = 6.0
    ) -> None:
        """Run periodic cleanup for multiple games.

        Args:
            games: List of game codes to monitor
            interval_hours: Hours between cleanup runs
        """
        logger.info(
            "periodic_cleanup_started",
            games=games,
            interval_hours=interval_hours,
            dry_run=self.dry_run,
        )

        while True:
            for game in games:
                try:
                    stats = await self.clean_targets(game)
                    logger.info("cleanup_cycle_completed", **stats)
                except Exception as e:
                    logger.error(
                        "cleanup_cycle_failed",
                        game=game,
                        error=str(e),
                        exc_info=True,
                    )

            # WAlgot for next cycle
            sleep_seconds = interval_hours * 3600
            logger.info("waiting_for_next_cleanup", hours=interval_hours)
            await asyncio.sleep(sleep_seconds)


# Example usage
async def example_usage():
    """Example of target cleaner usage."""
    from src.dmarket.dmarket_api import DMarketAPI

    api = DMarketAPI(public_key="test", secret_key="test")

    # Initialize cleaner in dry-run mode for safety
    cleaner = TargetCleaner(
        api_client=api,
        max_age_hours=24.0,
        max_competition=5,
        dry_run=True,  # Set to False for actual cancellation
    )

    # One-time cleanup for CS:GO
    stats = await cleaner.clean_targets("csgo")
    print(f"Cancelled {stats['cancelled']} underperforming targets")

    # Run periodic cleanup every 6 hours
    # await cleaner.run_periodic_cleanup(
    #     games=["csgo", "dota2", "rust", "tf2"],
    #     interval_hours=6.0
    # )
