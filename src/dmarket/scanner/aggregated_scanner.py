"""Aggregated price scanner for fast pre-screening of arbitrage opportunities.

This module provides fast scanning using DMarket's aggregated prices endpoint
to identify promising arbitrage opportunities before detailed item fetching.

Benefits:
- 10-100x faster than full market scans
- Reduces API calls by focusing on high-potential items
- Provides market depth insights (demand/supply)
- Enables batch processing of up to 100 titles

API Endpoint: POST /marketplace-api/v1/aggregated-prices
Documentation: https://docs.dmarket.com/v1/swagger.html

Example:
    scanner = AggregatedScanner(api_client)
    opportunities = await scanner.pre_scan(
        titles=["AK-47 | Redline", "AWP | Asiimov"],
        game="csgo",
        min_margin=0.15
    )
"""

import asyncio
import logging
import operator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.interfaces import IDMarketAPI

logger = logging.getLogger(__name__)


class AggregatedScanner:
    """Fast scanner using aggregated prices for pre-screening opportunities.

    Uses /marketplace-api/v1/aggregated-prices to quickly identify items with
    profitable spreads between best buy orders and best sell offers.

    Attributes:
        api_client: DMarket API client implementing IDMarketAPI
        default_commission: DMarket commission rate (default 0.07 = 7%)
    """

    def __init__(
        self,
        api_client: "IDMarketAPI",
        default_commission: float = 0.07,
    ) -> None:
        """Initialize aggregated scanner.

        Args:
            api_client: DMarket API client
            default_commission: Commission rate for profit calculations (default: 7%)
        """
        self.api_client = api_client
        self.default_commission = default_commission

    async def pre_scan_opportunities(
        self,
        titles: list[str],
        game: str,
        min_margin: float = 0.10,
        min_demand: int = 1,
        max_supply: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fast pre-scan using aggregated prices to find opportunities.

        Args:
            titles: List of item titles to check (max 100)
            game: Game identifier (csgo, dota2, tf2, rust)
            min_margin: Minimum profit margin (default: 10%)
            min_demand: Minimum number of buy orders (default: 1)
            max_supply: Maximum number of sell offers (None = no limit)

        Returns:
            List of opportunities sorted by margin (highest first):
            [
                {
                    "title": "AK-47 | Redline (Field-Tested)",
                    "order_price": 1250,  # cents
                    "offer_price": 1000,  # cents
                    "spread": 180,  # cents (after commission)
                    "margin": 0.18,  # 18%
                    "demand": 15,  # buy orders
                    "supply": 5,  # sell offers
                    "game": "csgo"
                },
                ...
            ]

        RAlgoses:
            ValueError: If titles list exceeds 100 items
        """
        if len(titles) > 100:
            raise ValueError("Maximum 100 titles allowed per request")

        logger.info(
            "aggregated_pre_scan_started",
            extra={
                "game": game,
                "title_count": len(titles),
                "min_margin": min_margin,
            },
        )

        try:
            # Call aggregated prices endpoint (using bulk method for API v1.1.0)
            response = await self.api_client.get_aggregated_prices_bulk(
                titles=titles,
                game=game,
                limit=100,
            )

            opportunities = []
            # API v1.1.0 returns "aggregatedPrices" (not "aggregatedTitles")
            aggregated_items = response.get("aggregatedPrices", [])

            for item in aggregated_items:
                # Extract prices (in cents) - API returns as strings, convert to int
                order_price = int(item.get("orderBestPrice", "0"))
                offer_price = int(item.get("offerBestPrice", "0"))

                # Skip if no valid prices
                if not order_price or not offer_price:
                    continue

                # Calculate spread and margin
                spread = self._calculate_spread(
                    order_price=order_price,
                    offer_price=offer_price,
                )

                margin = spread / offer_price if offer_price > 0 else 0

                # Check filters
                demand = item.get("orderCount", 0)
                supply = item.get("offerCount", 0)

                if margin < min_margin:
                    continue

                if demand < min_demand:
                    continue

                if max_supply is not None and supply > max_supply:
                    continue

                opportunities.append(
                    {
                        "title": item["title"],
                        "order_price": order_price,
                        "offer_price": offer_price,
                        "spread": spread,
                        "margin": margin,
                        "demand": demand,
                        "supply": supply,
                        "game": game,
                        "demand_supply_ratio": (
                            demand / supply if supply > 0 else float("inf")
                        ),
                    }
                )

            # Sort by margin (highest first)
            opportunities.sort(key=operator.itemgetter("margin"), reverse=True)

            logger.info(
                "aggregated_pre_scan_completed",
                extra={
                    "opportunities_found": len(opportunities),
                    "best_margin": opportunities[0]["margin"] if opportunities else 0,
                },
            )

            return opportunities

        except Exception as e:
            logger.exception(
                "aggregated_pre_scan_failed",
                extra={"error": str(e), "game": game},
            )
            raise

    async def batch_pre_scan(
        self,
        all_titles: list[str],
        game: str,
        min_margin: float = 0.10,
        batch_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Pre-scan large list of titles in batches.

        Args:
            all_titles: Full list of titles to check
            game: Game identifier
            min_margin: Minimum profit margin
            batch_size: Titles per batch (max 100)

        Returns:
            Combined list of all opportunities
        """
        if batch_size > 100:
            batch_size = 100
            logger.warning("batch_size_capped", new_batch_size=100)

        all_opportunities = []
        total_batches = (len(all_titles) + batch_size - 1) // batch_size

        logger.info(
            "batch_pre_scan_started",
            extra={
                "total_titles": len(all_titles),
                "total_batches": total_batches,
            },
        )

        for i in range(0, len(all_titles), batch_size):
            batch = all_titles[i : i + batch_size]
            batch_num = i // batch_size + 1

            try:
                opportunities = await self.pre_scan_opportunities(
                    titles=batch,
                    game=game,
                    min_margin=min_margin,
                )
                all_opportunities.extend(opportunities)

                logger.info(
                    "batch_completed",
                    extra={
                        "batch": f"{batch_num}/{total_batches}",
                        "opportunities_in_batch": len(opportunities),
                    },
                )

                # Small delay between batches to respect rate limits
                if i + batch_size < len(all_titles):
                    await asyncio.sleep(0.5)

            except Exception as e:
                logger.exception(
                    "batch_failed",
                    extra={"batch": f"{batch_num}/{total_batches}", "error": str(e)},
                )
                # Continue with next batch even if one fails
                continue

        # Sort combined results
        all_opportunities.sort(key=operator.itemgetter("margin"), reverse=True)

        logger.info(
            "batch_pre_scan_completed",
            extra={"total_opportunities": len(all_opportunities)},
        )

        return all_opportunities

    def _calculate_spread(
        self,
        order_price: int,
        offer_price: int,
    ) -> int:
        """Calculate net spread after commission.

        Args:
            order_price: Best buy order price (cents)
            offer_price: Best sell offer price (cents)

        Returns:
            Net profit in cents after commission
        """
        commission = int(order_price * self.default_commission)
        spread = order_price - offer_price - commission
        return max(0, spread)

    def filter_by_demand_supply_ratio(
        self,
        opportunities: list[dict[str, Any]],
        min_ratio: float = 1.0,
    ) -> list[dict[str, Any]]:
        """Filter opportunities by demand/supply ratio.

        Args:
            opportunities: List of opportunities from pre_scan
            min_ratio: Minimum demand/supply ratio (default: 1.0)

        Returns:
            Filtered opportunities
        """
        filtered = [
            opp
            for opp in opportunities
            if opp.get("demand_supply_ratio", 0) >= min_ratio
        ]

        logger.info(
            "demand_supply_filter_applied",
            extra={
                "original_count": len(opportunities),
                "filtered_count": len(filtered),
                "min_ratio": min_ratio,
            },
        )

        return filtered

    def format_for_telegram(
        self,
        opportunities: list[dict[str, Any]],
        top_n: int = 10,
    ) -> str:
        """Format opportunities for Telegram message.

        Args:
            opportunities: List of opportunities
            top_n: Show top N opportunities

        Returns:
            Formatted markdown message
        """
        if not opportunities:
            return "❌ No opportunities found matching criteria."

        opportunities = opportunities[:top_n]

        message = f"🎯 **Top {len(opportunities)} Arbitrage Opportunities**\n\n"

        for i, opp in enumerate(opportunities, 1):
            buy_price = opp["offer_price"] / 100
            sell_price = opp["order_price"] / 100
            profit = opp["spread"] / 100
            margin_pct = opp["margin"] * 100

            message += (
                f"{i}. **{opp['title']}**\n"
                f"   💰 Buy: ${buy_price:.2f} → Sell: ${sell_price:.2f}\n"
                f"   📈 Profit: ${profit:.2f} ({margin_pct:.1f}%)\n"
                f"   📊 Demand/Supply: {opp['demand']}/{opp['supply']}\n\n"
            )

        return message
