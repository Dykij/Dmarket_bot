"""DMarket API targets (buy orders) operations.

This module provides target-related API operations including:
- Creating targets (buy orders)
- Getting user targets
- Deleting targets
- Competition analysis for buy orders
"""

import logging
from typing import Any
from urllib.parse import quote

logger = logging.getLogger(__name__)


class TargetsOperationsMixin:
    """Mixin class providing target-related API operations.

    This mixin is designed to be used with DMarketAPIClient or DMarketAPI
    which provides the _request method and endpoint constants.
    """

    # Type hints for mixin compatibility
    _request: Any
    ENDPOINT_USER_TARGETS: str
    ENDPOINT_TARGETS_BY_TITLE: str

    async def create_targets(
        self,
        game_id: str,
        targets: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Create targets (buy orders) for items.

        Args:
            game_id: Game identifier (a8db, 9a92, tf2, rust)
            targets: List of targets to create

        Returns:
            Target creation result

        Example:
            >>> targets = [
            ...     {
            ...         "Title": "AK-47 | Redline (Field-Tested)",
            ...         "Amount": 1,
            ...         "Price": {"Amount": 800, "Currency": "USD"},
            ...     }
            ... ]
            >>> result = await api.create_targets("a8db", targets)
        """
        data = {"GameID": game_id, "Targets": targets}

        return await self._request(
            "POST",
            "/marketplace-api/v1/user-targets/create",
            data=data,
        )

    async def get_user_targets(
        self,
        game_id: str,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Get user targets list.

        Args:
            game_id: Game identifier
            status: Status filter (TargetStatusActive, TargetStatusInactive)
            limit: Results limit
            offset: Offset for pagination

        Returns:
            User targets list
        """
        params = {"GameID": game_id, "Limit": str(limit), "Offset": str(offset)}

        if status:
            params["BasicFilters.Status"] = status

        return await self._request(
            "GET",
            "/marketplace-api/v1/user-targets",
            params=params,
        )

    async def delete_targets(
        self,
        target_ids: list[str],
    ) -> dict[str, Any]:
        """Delete targets.

        Args:
            target_ids: List of target IDs to delete

        Returns:
            Deletion result
        """
        data = {"Targets": [{"TargetID": tid} for tid in target_ids]}

        return await self._request(
            "POST",
            "/marketplace-api/v1/user-targets/delete",
            data=data,
        )

    async def get_targets_by_title(
        self,
        game_id: str,
        title: str,
    ) -> dict[str, Any]:
        """Get targets for specific item (aggregated data, API v1.1.0).

        Args:
            game_id: Game identifier (csgo, dota2, tf2, rust)
            title: Exact item name in game

        Returns:
            Targets list for the item

        Response format:
            {
                "orders": [
                    {
                        "amount": 10,
                        "price": "1200",  # in cents
                        "title": "AK-47 | Redline (Field-Tested)",
                        "attributes": {
                            "exterior": "Field-Tested"
                        }
                    }
                ]
            }

        Example:
            >>> targets = await api.get_targets_by_title(
            ...     game_id="csgo", title="AK-47 | Redline (Field-Tested)"
            ... )
            >>> for target in targets["orders"]:
            ...     print(f"Price: ${int(target['price']) / 100:.2f}, Amount: {target['amount']}")
        """
        encoded_title = quote(title)
        path = f"{self.ENDPOINT_TARGETS_BY_TITLE}/{game_id}/{encoded_title}"

        logger.debug(f"Requesting targets for '{title}' (game: {game_id})")

        return await self._request("GET", path)

    async def get_buy_orders_competition(
        self,
        game_id: str,
        title: str,
        price_threshold: float | None = None,
    ) -> dict[str, Any]:
        """Evaluate buy orders competition for an item.

        Uses targets-by-title endpoint to get aggregated data
        about buy orders and evaluate competition level among buyers.

        Args:
            game_id: Game identifier (csgo, dota2, tf2, rust)
            title: Exact item name
            price_threshold: Price threshold for filtering (in USD).
                If specified, only orders with price >= threshold are counted.

        Returns:
            Competition data

        Response format:
            {
                "title": "AK-47 | Redline (Field-Tested)",
                "game_id": "csgo",
                "total_orders": 15,
                "total_amount": 45,  # Total buy orders quantity
                "competition_level": "medium",  # "low", "medium", "high"
                "best_price": 8.50,  # Best buy order price in USD
                "average_price": 8.20,  # Average buy order price
                "filtered_orders": 10,  # Orders above threshold (if specified)
                "orders": [...]  # All orders list
            }

        Example:
            >>> competition = await api.get_buy_orders_competition(
            ...     game_id="csgo", title="AK-47 | Redline (Field-Tested)", price_threshold=8.00
            ... )
            >>> if competition["competition_level"] == "low":
            ...     print("Low competition - can create target")
            >>> else:
            ...     print(f"High competition: {competition['total_orders']} orders")
        """
        price_str = f"${price_threshold:.2f}" if price_threshold else "not specified"
        logger.debug(
            f"Evaluating buy orders competition for '{title}' (game: {game_id}, "
            f"price threshold: {price_str})"
        )

        try:
            targets_response = await self.get_targets_by_title(
                game_id=game_id,
                title=title,
            )

            orders = targets_response.get("orders", [])

            total_orders = len(orders)
            total_amount = 0
            prices: list[float] = []
            filtered_orders = 0
            filtered_amount = 0

            for order in orders:
                amount = order.get("amount", 0)
                price_cents = float(order.get("price", 0))
                price_usd = price_cents / 100

                total_amount += amount
                prices.append(price_usd)

                if price_threshold is None or price_usd >= price_threshold:
                    filtered_orders += 1
                    filtered_amount += amount

            best_price = max(prices) if prices else 0.0
            average_price = sum(prices) / len(prices) if prices else 0.0

            # Determine competition level
            if total_orders <= 2 or total_amount <= 5:
                competition_level = "low"
            elif total_orders <= 10 or total_amount <= 20:
                competition_level = "medium"
            else:
                competition_level = "high"

            result = {
                "title": title,
                "game_id": game_id,
                "total_orders": total_orders,
                "total_amount": total_amount,
                "competition_level": competition_level,
                "best_price": best_price,
                "average_price": round(average_price, 2),
                "filtered_orders": filtered_orders if price_threshold else total_orders,
                "filtered_amount": filtered_amount if price_threshold else total_amount,
                "price_threshold": price_threshold,
                "orders": orders,
            }

            logger.info(
                f"Competition for '{title}': level={competition_level}, "
                f"orders={total_orders}, amount={total_amount}, "
                f"best price=${best_price:.2f}"
            )

            return result

        except Exception as e:
            logger.exception(f"Error evaluating competition for '{title}': {e}")
            return {
                "title": title,
                "game_id": game_id,
                "total_orders": 0,
                "total_amount": 0,
                "competition_level": "unknown",
                "best_price": 0.0,
                "average_price": 0.0,
                "filtered_orders": 0,
                "filtered_amount": 0,
                "price_threshold": price_threshold,
                "orders": [],
                "error": str(e),
            }

    async def get_closed_targets(
        self,
        limit: int = 50,
        status: str | None = None,
        from_timestamp: int | None = None,
        to_timestamp: int | None = None,
    ) -> dict[str, Any]:
        """Get closed targets history.

        Args:
            limit: Results limit
            status: Status filter (successful, reverted, trade_protected)
            from_timestamp: Period start (timestamp)
            to_timestamp: Period end (timestamp)

        Returns:
            Closed targets history
        """
        params: dict[str, str] = {"Limit": str(limit), "OrderDir": "desc"}

        if status:
            params["Status"] = status

        if from_timestamp:
            params["TargetClosed.From"] = str(from_timestamp)

        if to_timestamp:
            params["TargetClosed.To"] = str(to_timestamp)

        return await self._request(
            "GET",
            "/marketplace-api/v1/user-targets/closed",
            params=params,
        )
