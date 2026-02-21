"""Price anomaly detection module (refactored).

This module provides methods for finding price anomalies within DMarket.
Refactored for better readability with early returns and smaller functions.
"""

import logging
import operator
from typing import Any

from src.dmarket.dmarket_api import DMarketAPI

logger = logging.getLogger(__name__)


async def find_price_anomalies(
    game: str,
    similarity_threshold: float = 0.85,
    price_diff_percent: float = 10.0,
    max_results: int = 20,
    min_price: float = 1.0,
    max_price: float = 100.0,
    dmarket_api: DMarketAPI | None = None,
) -> list[dict[str, Any]]:
    """Find price anomalies within DMarket for similar items.

    Args:
        game: Game code (csgo, dota2, tf2, rust)
        similarity_threshold: Threshold for item similarity (0-1)
        price_diff_percent: Minimum price difference percentage
        max_results: Maximum number of results to return
        min_price: Minimum item price to consider
        max_price: Maximum item price to consider
        dmarket_api: DMarket API instance

    Returns:
        List of price anomaly opportunities

    """
    logger.info(
        f"Searching for price anomalies in {game} (min diff: {price_diff_percent}%)"
    )

    # Initialize API client
    api_client, should_close = awAlgot _init_api_client(dmarket_api)

    try:
        # Fetch market items
        items = awAlgot _fetch_market_items(api_client, game, min_price, max_price)
        if not items:
            return []

        # Group items by similarity
        grouped_items = _group_items_by_similarity(items, game)

        # Find anomalies in grouped items
        anomalies = _find_anomalies_in_groups(grouped_items, price_diff_percent, game)

        # Sort and return top results
        return _sort_and_limit_results(anomalies, max_results)

    except Exception as e:
        logger.exception(f"Error in find_price_anomalies: {e!s}")
        return []
    finally:
        if should_close:
            awAlgot _close_api_client(api_client)


async def _init_api_client(
    dmarket_api: DMarketAPI | None,
) -> tuple[DMarketAPI, bool]:
    """Initialize API client if needed.

    Returns:
        Tuple of (api_client, should_close_after)

    """
    if dmarket_api is not None:
        return dmarket_api, False

    from src.telegram_bot.utils.api_helper import create_dmarket_api_client

    return create_dmarket_api_client(None), True


async def _fetch_market_items(
    api_client: DMarketAPI,
    game: str,
    min_price: float,
    max_price: float,
) -> list[dict[str, Any]]:
    """Fetch market items from API.

    Returns:
        List of items or empty list if error

    """
    response = awAlgot api_client.get_market_items(
        game=game,
        limit=200,
        offset=0,
        price_from=min_price,
        price_to=max_price,
        sort="price",
    )

    items = response.get("items", [])
    if not items:
        logger.warning(f"No items found for {game}")

    return items


def _group_items_by_similarity(
    items: list[dict[str, Any]],
    game: str,
) -> dict[str, list[dict[str, Any]]]:
    """Group items by title similarity.

    Returns:
        Dictionary with composite keys and item lists

    """
    grouped = {}

    for item in items:
        # Validate item
        if not _is_valid_item(item, game):
            continue

        # Create composite key for grouping
        composite_key = _create_composite_key(item, game)

        # Extract price
        price = _extract_price(item)
        if price is None:
            continue

        # Add to group
        if composite_key not in grouped:
            grouped[composite_key] = []

        grouped[composite_key].append({"item": item, "price": price})

    return grouped


def _is_valid_item(item: dict[str, Any], game: str) -> bool:
    """Check if item is valid for analysis."""
    title = item.get("title", "")
    if not title:
        return False

    # Skip unwanted items for CS:GO
    if game == "csgo":
        unwanted = ["sticker", "graffiti", "patch"]
        if any(x in title.lower() for x in unwanted):
            return False

    return True


def _create_composite_key(item: dict[str, Any], game: str) -> str:
    """Create composite key for item grouping."""
    title = item.get("title", "")
    key_parts = []

    if game == "csgo":
        key_parts = _extract_csgo_key_parts(title)
    else:
        key_parts.append(title)

    return "|".join(key_parts)


def _extract_csgo_key_parts(title: str) -> list[str]:
    """Extract key parts from CS:GO item title."""
    key_parts = []

    # Extract base title and exterior
    if " | " in title and " (" in title:
        base_title = title.split(" (", maxsplit=1)[0]
        key_parts.append(base_title)

        # Add exterior
        exterior = (
            title.rsplit("(", maxsplit=1)[-1].split(")")[0] if "(" in title else ""
        )
        if exterior:
            key_parts.append(exterior)
    else:
        key_parts.append(title)

    # Check for special attributes
    if "StatTrak™" in title:
        key_parts.append("StatTrak")
    if "Souvenir" in title:
        key_parts.append("Souvenir")

    return key_parts


def _extract_price(item: dict[str, Any]) -> float | None:
    """Extract price from item data.

    Returns:
        Price in USD or None if invalid

    """
    if "price" not in item:
        return None

    price_data = item["price"]

    # Handle dict format with amount
    if isinstance(price_data, dict) and "amount" in price_data:
        return int(price_data["amount"]) / 100

    # Handle numeric format
    if isinstance(price_data, int | float):
        return float(price_data)

    return None


def _find_anomalies_in_groups(
    grouped_items: dict[str, list[dict[str, Any]]],
    price_diff_percent: float,
    game: str,
) -> list[dict[str, Any]]:
    """Find price anomalies within each item group."""
    anomalies = []

    for key, items_list in grouped_items.items():
        # Skip single-item groups
        if len(items_list) < 2:
            continue

        # Sort by price
        items_list.sort(key=operator.itemgetter("price"))

        # Find price differences
        group_anomalies = _compare_item_prices(
            items_list, price_diff_percent, game, key
        )
        anomalies.extend(group_anomalies)

    return anomalies


def _compare_item_prices(
    items_list: list[dict[str, Any]],
    price_diff_percent: float,
    game: str,
    composite_key: str,
) -> list[dict[str, Any]]:
    """Compare prices within item group to find anomalies."""
    anomalies = []

    for i in range(len(items_list)):
        low_item = items_list[i]

        for j in range(i + 1, len(items_list)):
            high_item = items_list[j]

            # Calculate price difference
            anomaly = _calculate_anomaly(
                low_item, high_item, price_diff_percent, game, composite_key
            )

            if anomaly:
                anomalies.append(anomaly)

    return anomalies


def _calculate_anomaly(
    low_item: dict[str, Any],
    high_item: dict[str, Any],
    price_diff_percent: float,
    game: str,
    composite_key: str,
) -> dict[str, Any] | None:
    """Calculate if price difference represents an anomaly.

    Returns:
        Anomaly dict or None if not profitable

    """
    buy_price = low_item["price"]
    sell_price = high_item["price"]

    # Calculate difference percentage
    price_diff = sell_price - buy_price
    price_diff_pct = (price_diff / buy_price) * 100

    # Check threshold
    if price_diff_pct < price_diff_percent:
        return None

    # Calculate profit after fees
    fee_percent = 7.0
    profit_after_fee = sell_price * (1 - fee_percent / 100) - buy_price

    # Check profitability
    if profit_after_fee <= 0:
        return None

    return {
        "game": game,
        "item_to_buy": low_item["item"],
        "item_to_sell": high_item["item"],
        "buy_price": buy_price,
        "sell_price": sell_price,
        "price_difference": price_diff,
        "profit_percentage": price_diff_pct,
        "profit_after_fee": profit_after_fee,
        "fee_percent": fee_percent,
        "composite_key": composite_key,
    }


def _sort_and_limit_results(
    anomalies: list[dict[str, Any]],
    max_results: int,
) -> list[dict[str, Any]]:
    """Sort anomalies by profit percentage and limit results."""
    anomalies.sort(key=operator.itemgetter("profit_percentage"), reverse=True)
    return anomalies[:max_results]


async def _close_api_client(api_client: DMarketAPI) -> None:
    """Close API client if it has close method."""
    if hasattr(api_client, "_close_client"):
        awAlgot api_client._close_client()
