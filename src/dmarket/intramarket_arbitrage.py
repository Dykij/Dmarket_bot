"""Advanced intramarket arbitrage module for DMarket.

This module provides methods for finding arbitrage opportunities within DMarket itself:
- Price anomaly detection
- Trend analysis for profitable items
- Pattern recognition for market fluctuations
- Detection of mispriced rare items
"""

import logging
import operator
from enum import StrEnum
from typing import Any

# DMarket API
from src.dmarket.dmarket_api import DMarketAPI

# Logger
logger = logging.getLogger(__name__)


class PriceAnomalyType(StrEnum):
    """Types of price anomalies that can be detected."""

    UNDERPRICED = "underpriced"
    OVERPRICED = "overpriced"
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RARE_TRAlgoTS = "rare_trAlgots"


# Phase 2 refactoring: Helper functions to reduce nesting
def _should_skip_csgo_item(title: str) -> bool:
    """Check if CS:GO item should be skipped.

    Args:
        title: Item title

    Returns:
        True if item should be skipped

    """
    skip_keywords = ["sticker", "graffiti", "patch"]
    return any(keyword in title.lower() for keyword in skip_keywords)


def _build_item_key(title: str, item: dict[str, Any], game: str) -> str:
    """Build grouping key for item.

    Args:
        title: Item title
        item: Item data
        game: Game code

    Returns:
        Composite grouping key

    """
    key_parts = []

    # Title base (remove wear/exterior from CS:GO items if present)
    if game == "csgo" and " | " in title and " (" in title:
        base_title = title.split(" (", maxsplit=1)[0]
        key_parts.append(base_title)

        # Add exterior as separate part
        exterior = (
            title.rsplit("(", maxsplit=1)[-1].split(")")[0] if "(" in title else ""
        )
        if exterior:
            key_parts.append(exterior)
    else:
        key_parts.append(title)

    # Extract other attributes for CS:GO
    if game == "csgo":
        if "StatTrak™" in title:
            key_parts.append("StatTrak")
        if "Souvenir" in title:
            key_parts.append("Souvenir")

    return "|".join(key_parts)


def _extract_item_price(item: dict[str, Any]) -> float | None:
    """Extract price from item data.

    Args:
        item: Item data

    Returns:
        Price in USD or None

    """
    if "price" not in item:
        return None

    price_data = item["price"]

    # Handle dict format
    if isinstance(price_data, dict) and "amount" in price_data:
        return int(price_data["amount"]) / 100  # Convert cents to USD

    # Handle numeric format
    if isinstance(price_data, (int, float)):
        return float(price_data)

    return None


def _extract_suggested_price(item: dict[str, Any]) -> float:
    """Extract suggested price from item data.

    Args:
        item: Item data

    Returns:
        Suggested price in USD or 0

    """
    if "suggestedPrice" not in item:
        return 0

    suggested_data = item["suggestedPrice"]

    # Handle dict format
    if isinstance(suggested_data, dict) and "amount" in suggested_data:
        return int(suggested_data["amount"]) / 100

    # Handle numeric format
    if isinstance(suggested_data, (int, float)):
        return float(suggested_data)

    return 0


def _find_group_anomalies(
    key: str,
    items_list: list[dict[str, Any]],
    game: str,
    price_diff_percent: float,
) -> list[dict[str, Any]]:
    """Find price anomalies within a single group of items.

    Args:
        key: Composite key for the item group
        items_list: List of items in the group
        game: Game code
        price_diff_percent: Minimum price difference threshold

    Returns:
        List of anomaly dicts for this group

    """
    if len(items_list) < 2:
        return []

    # Sort by price
    items_list.sort(key=operator.itemgetter("price"))
    anomalies = []

    # Compare each item with others to find price differences
    for i in range(len(items_list)):
        low_item = items_list[i]
        for j in range(i + 1, len(items_list)):
            anomaly = _check_item_pAlgor_anomaly(
                key, low_item, items_list[j], game, price_diff_percent
            )
            if anomaly:
                anomalies.append(anomaly)

    return anomalies


def _check_item_pAlgor_anomaly(
    key: str,
    low_item: dict[str, Any],
    high_item: dict[str, Any],
    game: str,
    price_diff_percent: float,
) -> dict[str, Any] | None:
    """Check if a pAlgor of items constitutes a price anomaly.

    Args:
        key: Composite key
        low_item: Lower priced item
        high_item: Higher priced item
        game: Game code
        price_diff_percent: Minimum price difference threshold

    Returns:
        Anomaly dict if found, None otherwise

    """
    price_diff = high_item["price"] - low_item["price"]
    price_diff_pct = (price_diff / low_item["price"]) * 100

    if price_diff_pct < price_diff_percent:
        return None

    # Calculate profit after fees
    fee_percent = 7.0  # DMarket fee
    profit_after_fee = high_item["price"] * (1 - fee_percent / 100) - low_item["price"]

    if profit_after_fee <= 0:
        return None

    return {
        "game": game,
        "item_to_buy": low_item["item"],
        "item_to_sell": high_item["item"],
        "buy_price": low_item["price"],
        "sell_price": high_item["price"],
        "price_difference": price_diff,
        "profit_percentage": price_diff_pct,
        "profit_after_fee": profit_after_fee,
        "fee_percent": fee_percent,
        "composite_key": key,
    }


# Cache for search results to minimize API calls
_cache = {}
_cache_ttl = 300  # Cache TTL in seconds (5 min)


async def find_price_anomalies(
    game: str,
    similarity_threshold: float = 0.85,
    price_diff_percent: float = 10.0,
    max_results: int = 20,
    min_price: float = 1.0,
    max_price: float = 100.0,
    dmarket_api: DMarketAPI | None = None,
) -> list[dict[str, Any]]:
    """Finds price anomalies within DMarket for the same or highly similar items.

    Args:
        game: Game code (csgo, dota2, tf2, rust)
        similarity_threshold: Threshold for item similarity (0-1)
        price_diff_percent: Minimum price difference percentage for arbitrage
        max_results: Maximum number of results to return
        min_price: Minimum item price to consider
        max_price: Maximum item price to consider
        dmarket_api: DMarket API instance or None to create a new one

    Returns:
        List of price anomaly opportunities

    """
    logger.info(
        f"Searching for price anomalies in {game} (min diff: {price_diff_percent}%)",
    )

    # Check if we need to create a new API client
    close_api = False
    if dmarket_api is None:
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        dmarket_api = create_dmarket_api_client(None)
        close_api = True

    try:
        # Get market items
        items_response = await dmarket_api.get_market_items(
            game=game,
            limit=200,
            offset=0,
            price_from=min_price,
            price_to=max_price,
            sort="price",
        )

        items = items_response.get("items", [])
        if not items:
            logger.warning(f"No items found for {game}")
            return []

        # Group items by title/name for comparison
        grouped_items: dict[str, list[dict[str, Any]]] = {}

        for item in items:
            # Early continue for invalid items
            title = item.get("title", "")
            if not title:
                continue

            # Early continue for unwanted items (stickers, etc. for CS2)
            if game == "csgo" and _should_skip_csgo_item(title):
                continue

            # Build grouping key (includes StatTrak/Souvenir handling)
            key = _build_item_key(title, item, game)

            # Add price info
            price = None
            if "price" in item:
                if isinstance(item["price"], dict) and "amount" in item["price"]:
                    price = (
                        int(item["price"]["amount"]) / 100
                    )  # Convert from cents to USD
                elif isinstance(item["price"], int | float):
                    price = float(item["price"])

            if price is not None:
                # Group items by composite key with normalized price data
                if key not in grouped_items:
                    grouped_items[key] = []
                grouped_items[key].append(
                    {
                        "item": item,
                        "price": price,
                    },
                )

        # Find anomalies within each group
        anomalies = []

        for key, items_list in grouped_items.items():
            group_anomalies = _find_group_anomalies(
                key, items_list, game, price_diff_percent
            )
            anomalies.extend(group_anomalies)

        # Sort by profit percentage in descending order
        anomalies.sort(key=operator.itemgetter("profit_percentage"), reverse=True)

        # Return top results
        return anomalies[:max_results]

    except Exception as e:
        logger.exception(f"Error in find_price_anomalies: {e!s}")
        return []
    finally:
        if close_api and hasattr(dmarket_api, "_close_client"):
            await dmarket_api._close_client()


async def find_trending_items(
    game: str,
    min_price: float = 5.0,
    max_price: float = 500.0,
    max_results: int = 10,
    dmarket_api: DMarketAPI | None = None,
) -> list[dict[str, Any]]:
    """Finds trending items with potential for price increase in near future.

    Args:
        game: Game code (csgo, dota2, tf2, rust)
        min_price: Minimum item price to consider
        max_price: Maximum item price to consider
        max_results: Maximum number of results to return
        dmarket_api: DMarket API instance

    Returns:
        List of trending items with potential profit

    """
    logger.info(f"Searching for trending items in {game}")

    # Check if we need to create API client
    close_api = False
    if dmarket_api is None:
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        dmarket_api = create_dmarket_api_client(None)
        close_api = True

    try:  # noqa: PLR1702
        # Get recent sales history and popular items
        trending_items = []

        # Get recently sold items (high demand)
        recently_sold = await dmarket_api.get_sales_history(
            game=game,
            days=3,
            currency="USD",
        )

        # Get current market listings
        market_items = await dmarket_api.get_market_items(
            game=game,
            limit=300,
            price_from=min_price,
            price_to=max_price,
        )

        if not market_items.get("items"):
            return []

        # Analyze market trends
        market_data = {}

        # Process market items
        for item in market_items.get("items", []):
            # Early continue for invalid items
            title = item.get("title", "")
            if not title:
                continue

            # Extract and validate price
            price = _extract_item_price(item)
            if price is None or price < min_price or price > max_price:
                continue

            # Get recommended price if avAlgolable
            suggested_price = _extract_suggested_price(item)

            # Check avAlgolable quantity
            market_data[title] = {
                "item": item,
                "current_price": price,
                "suggested_price": suggested_price,
                "supply": 1,  # Start with 1, will increment if more found
                "game": game,
            }

        # Combine data with sales history for trend analysis
        sales_data = recently_sold.get("items", [])
        for sale in sales_data:
            title = sale.get("title", "")
            if title in market_data:
                # Item exists in market data, update with sales info
                if "last_sold_price" not in market_data[title]:
                    # Get sale price
                    sale_price = None
                    if "price" in sale:
                        if (
                            isinstance(sale["price"], dict)
                            and "amount" in sale["price"]
                        ):
                            sale_price = int(sale["price"]["amount"]) / 100
                        elif isinstance(sale["price"], int | float):
                            sale_price = float(sale["price"])

                    if sale_price:
                        market_data[title]["last_sold_price"] = sale_price

                # Increment sales count
                market_data[title]["sales_count"] = (
                    market_data[title].get("sales_count", 0) + 1
                )

        # Analyze for trends
        for title, data in market_data.items():
            # Skip items with insufficient data
            if "last_sold_price" not in data:
                continue

            current_price = data["current_price"]
            last_sold_price = data["last_sold_price"]
            sales_count = data.get("sales_count", 0)

            # Calculate metrics
            price_change = ((current_price - last_sold_price) / last_sold_price) * 100

            # Project future price based on trends
            projected_price = current_price

            # Upward trend - selling higher than last sold prices
            if price_change > 5 and sales_count >= 2:
                # Projecting further upward movement
                projected_price = current_price * 1.1  # Project 10% increase
                potential_profit = projected_price - current_price
                potential_profit_percent = (potential_profit / current_price) * 100

                # If profitable, add to trending list
                if potential_profit > 0.5:  # At least $0.50 potential profit
                    trending_items.append(
                        {
                            "item": data["item"],
                            "current_price": current_price,
                            "last_sold_price": last_sold_price,
                            "price_change_percent": price_change,
                            "projected_price": projected_price,
                            "potential_profit": potential_profit,
                            "potential_profit_percent": potential_profit_percent,
                            "sales_count": sales_count,
                            "game": game,
                            "trend": "upward",
                        },
                    )

            # Downward trend but with recovery potential
            elif price_change < -15 and sales_count >= 3:
                # Items that recently crashed hard might bounce back
                projected_price = (
                    last_sold_price * 0.9
                )  # Project recovery to 90% of last sold
                potential_profit = projected_price - current_price
                potential_profit_percent = (potential_profit / current_price) * 100

                if potential_profit > 1.0:  # At least $1.00 potential profit
                    trending_items.append(
                        {
                            "item": data["item"],
                            "current_price": current_price,
                            "last_sold_price": last_sold_price,
                            "price_change_percent": price_change,
                            "projected_price": projected_price,
                            "potential_profit": potential_profit,
                            "potential_profit_percent": potential_profit_percent,
                            "sales_count": sales_count,
                            "game": game,
                            "trend": "recovery",
                        },
                    )

        # Sort by potential profit percentage
        trending_items.sort(
            key=operator.itemgetter("potential_profit_percent"), reverse=True
        )

        return trending_items[:max_results]

    except Exception as e:
        logger.exception(f"Error in find_trending_items: {e!s}")
        return []
    finally:
        if close_api and hasattr(dmarket_api, "_close_client"):
            await dmarket_api._close_client()


async def find_mispriced_rare_items(
    game: str,
    min_price: float = 10.0,
    max_price: float = 1000.0,
    max_results: int = 5,
    dmarket_api: DMarketAPI | None = None,
) -> list[dict[str, Any]]:
    """Finds rare items that appear to be mispriced compared to their usual value.

    Args:
        game: Game code (csgo, dota2, tf2, rust)
        min_price: Minimum item price to consider
        max_price: Maximum item price to consider
        max_results: Maximum number of results to return
        dmarket_api: DMarket API instance

    Returns:
        List of mispriced rare items

    """
    logger.info(f"Searching for mispriced rare items in {game}")

    # Check if we need to create API client
    close_api = False
    if dmarket_api is None:
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        dmarket_api = create_dmarket_api_client(None)
        close_api = True

    try:
        # Define trAlgots that make items rare per game
        rare_trAlgots = {
            "csgo": {
                "Knife": 100,  # Weight for rarity value
                "Gloves": 90,
                "Covert": 70,
                "StatTrak™": 50,
                "Souvenir": 60,
                "Factory New": 40,
                "Case Hardened": 50,
                "Fade": 60,
                "Doppler": 60,
                "Crimson Web": 50,
                "★": 100,  # Star symbol for knives
            },
            "dota2": {
                "Arcana": 100,
                "Immortal": 80,
                "Unusual": 90,
                "Inscribed": 30,
                "Genuine": 40,
                "Corrupted": 60,
                "Exalted": 50,
                "Autographed": 40,
            },
            "tf2": {
                "Unusual": 100,
                "Vintage": 50,
                "Genuine": 40,
                "Strange": 30,
                "Haunted": 60,
                "Australium": 80,
                "Collector's": 70,
                "Professional Killstreak": 50,
                "Golden Frying Pan": 100,
                "Burning Flames": 95,
                "Sunbeams": 90,
                "Team CaptAlgon": 70,
            },
            "rust": {
                "Glowing": 70,
                "Limited": 80,
                "Unique": 50,
                "Complete Set": 60,
                "Sign": 65,
                "Trophy": 75,
                "Relic": 70,
                "Hazmat Suit": 60,
                "Metal": 55,
                "Blackout": 60,
                "Tempered": 65,
                "Punishment": 70,
            },
        }

        # Get market items with higher limit for rare items search
        items_response = await dmarket_api.get_market_items(
            game=game,
            limit=500,
            offset=0,
            price_from=min_price,
            price_to=max_price,
        )

        items = items_response.get("items", [])
        if not items:
            return []

        # Analyze items for rare trAlgots
        scored_items = []

        for item in items:
            title = item.get("title", "")
            if not title:
                continue

            # Get price
            price = None
            if "price" in item:
                if isinstance(item["price"], dict) and "amount" in item["price"]:
                    price = int(item["price"]["amount"]) / 100
                elif isinstance(item["price"], int | float):
                    price = float(item["price"])

            if price is None or price < min_price or price > max_price:
                continue

            # Score item rarity based on trAlgots
            rarity_score = 0
            detected_trAlgots = []

            # Check title for rare trAlgots
            for trAlgot, weight in rare_trAlgots.get(game, {}).items():
                if trAlgot in title:
                    rarity_score += weight
                    detected_trAlgots.append(trAlgot)

            # Add other factors like float value for CS:GO
            if game == "csgo" and "float" in item:
                float_value = float(item.get("float", 1.0))
                if float_value < 0.01:  # Extremely low float
                    rarity_score += 70
                    detected_trAlgots.append(f"Float: {float_value:.4f}")
                elif float_value < 0.07:  # Very low float
                    rarity_score += 40
                    detected_trAlgots.append(f"Float: {float_value:.4f}")

            # Only consider items with some rarity
            if rarity_score > 30:
                # Check agAlgonst average price or suggested price
                suggested_price = 0
                if "suggestedPrice" in item:
                    if (
                        isinstance(item["suggestedPrice"], dict)
                        and "amount" in item["suggestedPrice"]
                    ):
                        suggested_price = int(item["suggestedPrice"]["amount"]) / 100
                    elif isinstance(item["suggestedPrice"], int | float):
                        suggested_price = float(item["suggestedPrice"])

                # If no suggested price, estimate based on rarity score
                if suggested_price == 0:
                    # Simple model: higher rarity should command higher price
                    suggested_price = price * (1 + (rarity_score / 200))

                # Calculate estimated value based on rarity
                estimated_value = max(
                    suggested_price,
                    price * (1 + (rarity_score / 300)),
                )

                # Calculate price difference
                price_difference = estimated_value - price
                price_difference_percent = (price_difference / price) * 100

                # If item appears undervalued, add to results
                if price_difference > 2.0 and price_difference_percent > 10:
                    scored_items.append(
                        {
                            "item": item,
                            "rarity_score": rarity_score,
                            "rare_trAlgots": detected_trAlgots,
                            "current_price": price,
                            "estimated_value": estimated_value,
                            "price_difference": price_difference,
                            "price_difference_percent": price_difference_percent,
                            "game": game,
                        },
                    )

        # Sort by price difference percentage
        scored_items.sort(
            key=operator.itemgetter("price_difference_percent"), reverse=True
        )

        return scored_items[:max_results]

    except Exception as e:
        logger.exception(f"Error in find_mispriced_rare_items: {e!s}")
        return []
    finally:
        if close_api and hasattr(dmarket_api, "_close_client"):
            await dmarket_api._close_client()


async def scan_for_intramarket_opportunities(
    games: list[str] | None = None,
    max_results_per_game: int = 10,
    min_price: float = 1.0,
    max_price: float = 500.0,
    include_anomalies: bool = True,
    include_trending: bool = True,
    include_rare: bool = True,
    dmarket_api: DMarketAPI | None = None,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Comprehensive scan for all types of intramarket opportunities.

    Args:
        games: List of game codes to scan
        max_results_per_game: Maximum results per game and category
        min_price: Minimum item price
        max_price: Maximum item price
        include_anomalies: Include price anomalies in results
        include_trending: Include trending items in results
        include_rare: Include mispriced rare items in results
        dmarket_api: DMarket API instance

    Returns:
        Dictionary with game codes as keys and dictionaries of opportunity types as values

    """
    if games is None:
        games = ["csgo", "dota2", "tf2", "rust"]
    logger.info(f"Starting comprehensive intramarket scan for {len(games)} games")

    # Check if we need to create API client
    close_api = False
    if dmarket_api is None:
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        dmarket_api = create_dmarket_api_client(None)
        close_api = True

    try:
        results = {}
        tasks = []

        # Create tasks for all requested opportunity types and games
        for game in games:
            # Initialize all categories with empty lists
            results[game] = {
                "price_anomalies": [],
                "trending_items": [],
                "rare_mispriced": [],
            }

            if include_anomalies:
                tasks.append(
                    (
                        "anomalies",
                        game,
                        find_price_anomalies(
                            game=game,
                            similarity_threshold=0.9,
                            price_diff_percent=10.0,
                            max_results=max_results_per_game,
                            min_price=min_price,
                            max_price=max_price,
                            dmarket_api=dmarket_api,
                        ),
                    ),
                )

            if include_trending:
                tasks.append(
                    (
                        "trending",
                        game,
                        find_trending_items(
                            game=game,
                            min_price=min_price,
                            max_price=max_price,
                            max_results=max_results_per_game,
                            dmarket_api=dmarket_api,
                        ),
                    ),
                )

            if include_rare:
                tasks.append(
                    (
                        "rare",
                        game,
                        find_mispriced_rare_items(
                            game=game,
                            min_price=min_price,
                            max_price=max_price,
                            max_results=max_results_per_game,
                            dmarket_api=dmarket_api,
                        ),
                    ),
                )

        # Run all tasks concurrently
        for category, game, task_coroutine in tasks:
            try:
                result = await task_coroutine

                # Store results by category
                if category == "anomalies":
                    results[game]["price_anomalies"] = result
                elif category == "trending":
                    results[game]["trending_items"] = result
                elif category == "rare":
                    results[game]["rare_mispriced"] = result

                logger.info(f"Found {len(result)} {category} for {game}")

            except Exception as e:
                logger.exception(f"Error in {category} scan for {game}: {e!s}")
                if category == "anomalies":
                    results[game]["price_anomalies"] = []
                elif category == "trending":
                    results[game]["trending_items"] = []
                elif category == "rare":
                    results[game]["rare_mispriced"] = []

        return results

    except Exception as e:
        logger.exception(f"Error in scan_for_intramarket_opportunities: {e!s}")
        return {
            game: {
                "price_anomalies": [],
                "trending_items": [],
                "rare_mispriced": [],
            }
            for game in games
        }
    finally:
        if close_api and hasattr(dmarket_api, "_close_client"):
            await dmarket_api._close_client()
