"""Utility functions for smart notifications."""

import asyncio
import logging
from typing import Any

from src.dmarket.dmarket_api import DMarketAPI
from src.utils.exceptions import APIError, NetworkError

logger = logging.getLogger(__name__)


async def get_market_data_for_items(
    api: DMarketAPI,
    item_ids: list[str],
    game: str,
) -> dict[str, dict[str, Any]]:
    """Get market data for multiple items from DMarket.

    Args:
        api: DMarketAPI instance
        item_ids: List of item IDs
        game: Game code

    Returns:
        Dictionary mapping item IDs to item data
    """
    result: dict[str, dict[str, Any]] = {}

    try:
        # Get market items in batches
        batch_size = 50
        for i in range(0, len(item_ids), batch_size):
            batch_ids = item_ids[i : i + batch_size]

            # Construct query parameters
            params = {
                "itemId": batch_ids,
                "gameId": game,
                "currency": "USD",
            }

            # Make API request
            response = await api._request(
                "GET",
                "/exchange/v1/market/items",
                params=params,
            )

            items = response.get("items", [])

            # Index by item ID
            for item in items:
                item_id = item.get("itemId")
                if item_id:
                    result[item_id] = item

            # Small delay between batches
            if i + batch_size < len(item_ids):
                await asyncio.sleep(0.5)

    except (APIError, NetworkError) as e:
        logger.exception(f"Error getting market data for items: {e}")
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Unexpected error getting market data for items: {e}")

    return result


async def get_item_by_id(
    api: DMarketAPI,
    item_id: str,
    game: str,
) -> dict[str, Any] | None:
    """Get data for a single item by ID.

    Args:
        api: DMarketAPI instance
        item_id: Item ID
        game: Game code

    Returns:
        Item data or None if not found
    """
    try:
        # Construct query parameters
        params = {
            "itemId": [item_id],
            "gameId": game,
            "currency": "USD",
        }

        # Make API request
        response = await api._request(
            "GET",
            "/exchange/v1/market/items",
            params=params,
        )

        items = response.get("items", [])

        if items:
            item: dict[str, Any] = items[0]
            return item

    except (APIError, NetworkError) as e:
        logger.exception(f"Error getting item {item_id}: {e}")
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Unexpected error getting item {item_id}: {e}")

    return None


async def get_market_items_for_game(
    api: DMarketAPI,
    game: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Get market items for a game.

    Args:
        api: DMarketAPI instance
        game: Game code
        limit: Maximum number of items to return

    Returns:
        List of market items
    """
    try:
        # Make API request
        response = await api._request(
            "GET",
            "/exchange/v1/market/items",
            params={
                "gameId": game,
                "limit": limit,
                "currency": "USD",
                "orderBy": "popular",
            },
        )

        items: list[dict[str, Any]] = response.get("items", [])
        return items

    except (APIError, NetworkError) as e:
        logger.exception(f"Error getting market items for game {game}: {e}")
        return []
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Unexpected error getting market items for game {game}: {e}")
        return []


async def get_price_history_for_items(
    api: DMarketAPI,
    item_ids: list[str],
    game: str,
) -> dict[str, list[dict[str, Any]]]:
    """Get price history for multiple items.

    Args:
        api: DMarketAPI instance
        item_ids: List of item IDs
        game: Game code

    Returns:
        Dictionary mapping item IDs to price history
    """
    result: dict[str, list[dict[str, Any]]] = {}

    try:
        # Get price history for each item
        for item_id in item_ids:
            # Make API request
            response = await api._request(
                "GET",
                "/exchange/v1/market/price-history",
                params={
                    "itemId": item_id,
                    "gameId": game,
                    "currency": "USD",
                    "period": "last_month",
                },
            )

            history = response.get("data", [])

            if history:
                result[item_id] = history

            # Small delay between requests
            await asyncio.sleep(0.2)

    except (APIError, NetworkError) as e:
        logger.exception(f"Error getting price history for items: {e}")
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Unexpected error getting price history for items: {e}")

    return result


def get_item_price(item_data: dict[str, Any]) -> float:
    """Extract price from item data.

    Args:
        item_data: Item data from DMarket

    Returns:
        Item price as float
    """
    if "price" in item_data:
        if isinstance(item_data["price"], dict) and "amount" in item_data["price"]:
            return float(item_data["price"]["amount"]) / 100
        if isinstance(item_data["price"], int | float):
            return float(item_data["price"])

    return 0.0
