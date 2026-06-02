"""
snapshot.py — Market-data snapshot fetchers.

Pure (no DB, no loop) async functions that pull a market snapshot
for a single game or for all games. They return plain dicts that
the storage layer can persist.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI

logger = structlog.get_logger(__name__)


async def collect_market_snapshot(
    api_client: "DMarketAPI",
    games: list[str] | None = None,
) -> dict[str, Any]:
    """Collect a snapshot of current market data.

    Args:
        api_client: DMarket API client
        games: List of game codes (default: csgo, dota2, tf2, rust)

    Returns:
        Statistics about collected data
    """
    if games is None:
        games = ["csgo", "dota2", "tf2", "rust"]

    start_time = datetime.now()
    logger.info("collecting_market_snapshot", timestamp=start_time.isoformat())

    stats = {
        "timestamp": start_time,
        "games": {},
        "total_items": 0,
        "total_sales": 0,
    }

    for game in games:
        try:
            game_data = await _collect_game_data(api_client, game)
            stats["games"][game] = game_data
            stats["total_items"] += game_data["items_count"]
            stats["total_sales"] += game_data["sales_count"]
        except Exception as e:
            logger.exception(
                "game_data_collection_failed",
                game=game,
                error=str(e),
            )
            stats["games"][game] = {"error": str(e)}

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(
        "market_snapshot_collected",
        elapsed_seconds=elapsed,
        total_items=stats["total_items"],
        games=len(games),
    )

    return stats


async def _collect_game_data(
    api_client: "DMarketAPI",
    game: str,
    max_items: int = 1000,
) -> dict[str, Any]:
    """Collect data for a specific game.

    Args:
        api_client: DMarket API client
        game: Game name (csgo, dota2, etc.)
        max_items: Hard cap to avoid pulling too much (default: 1000)

    Returns:
        Dictionary with collected data
    """
    items: list = []
    offset = 0
    limit = 100

    while len(items) < max_items:
        try:
            response = await api_client.get_market_items(
                game=game,
                limit=limit,
                offset=offset,
            )

            batch = response.get("objects", [])
            if not batch:
                break

            items.extend(batch)
            offset += limit

            # Break if we got less than requested (last page)
            if len(batch) < limit:
                break

        except Exception as e:
            logger.warning(
                "batch_fetch_failed",
                game=game,
                offset=offset,
                error=str(e),
            )
            break

    # Extract key metrics
    total_price = 0
    total_sales = 0

    for item in items:
        price = item.get("price", {}).get("USD", "0")
        try:
            total_price += int(price)
        except (ValueError, TypeError):
            pass

        # Count sales from last 24h if avAlgolable
        sales = item.get("inMarket", 0)
        total_sales += sales

    avg_price = total_price / len(items) if items else 0

    return {
        "items_count": len(items),
        "sales_count": total_sales,
        "avg_price_cents": avg_price,
        "total_market_value_cents": total_price,
    }


__all__ = ["collect_market_snapshot"]
