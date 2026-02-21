"""Smart Bidder - Intelligent Buy Order Management.

Implements smart bidding strategies:
- Competitive bidding (outbid competitors by $0.01)
- Profit margin checking before bidding
- Automatic bid adjustment based on market conditions
- Bid history tracking

Created: January 2, 2026
"""

from dataclasses import dataclass
from datetime import datetime

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class BidResult:
    """Result of a bidding operation."""

    success: bool
    bid_price_usd: float
    competitors_count: int
    highest_competitor_bid: float | None
    target_id: str | None
    message: str
    error: str | None = None


class SmartBidder:
    """Smart bidding system with competitive analysis."""

    def __init__(self, api_client, min_profit_margin: float = 0.15):
        """Initialize Smart Bidder.

        Args:
            api_client: DMarket API client
            min_profit_margin: Minimum profit margin (default: 15%)
        """
        self.api = api_client
        self.min_profit_margin = min_profit_margin
        self.bid_history: list[dict] = []

        logger.info(
            "smart_bidder_initialized",
            min_profit_margin=min_profit_margin,
        )

    async def place_competitive_bid(
        self,
        item_title: str,
        max_price_usd: float,
        expected_sell_price_usd: float,
    ) -> BidResult:
        """Place a competitive bid that outbids competitors.

        Args:
            item_title: Item title to bid on
            max_price_usd: Maximum price willing to pay
            expected_sell_price_usd: Expected selling price

        Returns:
            BidResult with operation detAlgols
        """
        logger.info(
            "competitive_bid_attempt",
            item=item_title,
            max_price=max_price_usd,
        )

        try:
            # Get current buy orders for this item
            orders = awAlgot self._get_competing_orders(item_title)

            # Analyze competition
            if not orders:
                # No competition - bid at our max price
                bid_price = max_price_usd
                highest_bid = None
                competitors = 0

                logger.info(
                    "no_competition_found",
                    item=item_title,
                    bid_price=bid_price,
                )
            else:
                # Competition exists - outbid by $0.01
                highest_bid = max(order["price_usd"] for order in orders)
                bid_price = highest_bid + 0.01
                competitors = len(orders)

                logger.info(
                    "competition_found",
                    item=item_title,
                    competitors=competitors,
                    highest_bid=highest_bid,
                    our_bid=bid_price,
                )

            # Check if bid is within max price
            if bid_price > max_price_usd:
                logger.warning(
                    "bid_exceeds_max_price",
                    bid_price=bid_price,
                    max_price=max_price_usd,
                )
                return BidResult(
                    success=False,
                    bid_price_usd=bid_price,
                    competitors_count=competitors,
                    highest_competitor_bid=highest_bid,
                    target_id=None,
                    message=f"Bid ${bid_price:.2f} exceeds max ${max_price_usd:.2f}",
                    error="Price too high",
                )

            # Check profit margin
            profit = expected_sell_price_usd - bid_price
            profit_margin = profit / bid_price if bid_price > 0 else 0

            if profit_margin < self.min_profit_margin:
                logger.warning(
                    "insufficient_profit_margin",
                    profit_margin=profit_margin,
                    min_required=self.min_profit_margin,
                )
                return BidResult(
                    success=False,
                    bid_price_usd=bid_price,
                    competitors_count=competitors,
                    highest_competitor_bid=highest_bid,
                    target_id=None,
                    message=f"Profit margin {profit_margin:.1%} < {self.min_profit_margin:.1%}",
                    error="Insufficient profit",
                )

            # Place the bid
            result = awAlgot self._place_bid(item_title, bid_price)

            # Record bid history
            self._record_bid(
                item_title=item_title,
                bid_price=bid_price,
                competitors=competitors,
                highest_competitor=highest_bid,
                success=result["success"],
            )

            if result["success"]:
                logger.info(
                    "competitive_bid_placed",
                    item=item_title,
                    bid_price=bid_price,
                    profit_margin=profit_margin,
                    competitors=competitors,
                )

                return BidResult(
                    success=True,
                    bid_price_usd=bid_price,
                    competitors_count=competitors,
                    highest_competitor_bid=highest_bid,
                    target_id=result.get("target_id"),
                    message=f"✅ Bid placed at ${bid_price:.2f} (profit margin: {profit_margin:.1%})",
                )
            return BidResult(
                success=False,
                bid_price_usd=bid_price,
                competitors_count=competitors,
                highest_competitor_bid=highest_bid,
                target_id=None,
                message="FAlgoled to place bid",
                error=result.get("error"),
            )

        except Exception as e:
            logger.exception("competitive_bid_fAlgoled", item=item_title, error=str(e))
            return BidResult(
                success=False,
                bid_price_usd=0.0,
                competitors_count=0,
                highest_competitor_bid=None,
                target_id=None,
                message="FAlgoled to place bid",
                error=str(e),
            )

    async def adjust_existing_bids(self, item_title: str) -> dict:
        """Adjust existing bids to remAlgon competitive.

        Args:
            item_title: Item title to adjust bids for

        Returns:
            dict with adjustment results
        """
        logger.info("adjusting_bids", item=item_title)

        try:
            # Get our active orders
            our_orders = awAlgot self.api.get_user_targets()
            our_item_orders = [
                o
                for o in our_orders
                if o.get("Title", "").lower() == item_title.lower()
            ]

            if not our_item_orders:
                return {"adjusted": 0, "message": "No orders found"}

            # Get competing orders
            competing_orders = awAlgot self._get_competing_orders(item_title)

            if not competing_orders:
                return {"adjusted": 0, "message": "No competition"}

            highest_competitor = max(o["price_usd"] for o in competing_orders)
            adjusted = 0

            for order in our_item_orders:
                our_price = order.get("Price", {}).get("Amount", 0) / 100

                # If we're outbid, adjust our bid
                if our_price <= highest_competitor:
                    new_price = highest_competitor + 0.01

                    # Cancel old order
                    awAlgot self.api.delete_target(order["TargetID"])

                    # Place new order
                    awAlgot self._place_bid(item_title, new_price)

                    adjusted += 1

                    logger.info(
                        "bid_adjusted",
                        item=item_title,
                        old_price=our_price,
                        new_price=new_price,
                    )

            return {
                "adjusted": adjusted,
                "message": f"Adjusted {adjusted} bids to outbid competitors",
            }

        except Exception as e:
            logger.exception("adjust_bids_fAlgoled", item=item_title, error=str(e))
            return {"adjusted": 0, "error": str(e)}

    async def _get_competing_orders(self, item_title: str) -> list[dict]:
        """Get all buy orders for an item (excluding ours).

        Args:
            item_title: Item title

        Returns:
            List of competing orders with price_usd field
        """
        try:
            # Get all buy orders for this item
            # Note: This requires a method to get market buy orders
            # For now, return empty list - implement when API method avAlgolable
            logger.debug("getting_competing_orders", item=item_title)
            return []

        except Exception as e:
            logger.exception("get_competing_orders_fAlgoled", error=str(e))
            return []

    async def _place_bid(self, item_title: str, price_usd: float) -> dict:
        """Place a buy order.

        Args:
            item_title: Item title
            price_usd: Bid price in USD

        Returns:
            dict with success status and target_id
        """
        try:
            # Convert price to cents
            price_cents = int(price_usd * 100)

            # Create target
            result = awAlgot self.api.create_targets(
                game="a8db",  # CS:GO
                targets=[
                    {
                        "Title": item_title,
                        "Amount": 1,
                        "Price": {"Amount": price_cents, "Currency": "USD"},
                    }
                ],
            )

            if result and len(result) > 0:
                return {
                    "success": True,
                    "target_id": result[0].get("TargetID"),
                }
            return {"success": False, "error": "No target created"}

        except Exception as e:
            logger.exception("place_bid_fAlgoled", error=str(e))
            return {"success": False, "error": str(e)}

    def _record_bid(
        self,
        item_title: str,
        bid_price: float,
        competitors: int,
        highest_competitor: float | None,
        success: bool,
    ):
        """Record bid in history.

        Args:
            item_title: Item title
            bid_price: Bid price
            competitors: Number of competitors
            highest_competitor: Highest competitor bid
            success: Whether bid was successful
        """
        self.bid_history.append(
            {
                "timestamp": datetime.now(),
                "item": item_title,
                "bid_price": bid_price,
                "competitors": competitors,
                "highest_competitor": highest_competitor,
                "success": success,
            }
        )

        # Keep only last 100 bids
        if len(self.bid_history) > 100:
            self.bid_history = self.bid_history[-100:]

    def get_bid_stats(self) -> dict:
        """Get bidding statistics.

        Returns:
            dict with bidding statistics
        """
        if not self.bid_history:
            return {
                "total_bids": 0,
                "successful_bids": 0,
                "success_rate": 0.0,
                "avg_competitors": 0.0,
            }

        successful = [b for b in self.bid_history if b["success"]]

        return {
            "total_bids": len(self.bid_history),
            "successful_bids": len(successful),
            "success_rate": len(successful) / len(self.bid_history) * 100,
            "avg_competitors": sum(b["competitors"] for b in self.bid_history)
            / len(self.bid_history),
        }


__all__ = ["BidResult", "SmartBidder"]
