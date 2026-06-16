"""
sources.py — Price-point collectors for individual DMarket data sources.

Each function is a stand-alone async source that takes a DMarketAPI
dependency + a (game, title, [days]) tuple and returns a list of
`PricePoint` objects. They never raise — all exceptions are logged
at DEBUG and an empty list is returned (the original behavior).

This module is intentionally framework-free: it doesn't know about
the cache or the orchestrator. That keeps the collectors trivially
testable in isolation.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from .models import PricePoint

if TYPE_CHECKING:
    from src.interfaces import IDMarketAPI

logger = logging.getLogger(__name__)


async def collect_from_sales_history(
    api: "IDMarketAPI",
    game: str,
    title: str,
    days: int,
) -> list[PricePoint]:
    """Collect price points from sales history.

    Args:
        api: DMarket API client
        game: Game code
        title: Item name
        days: Number of days

    Returns:
        List of PricePoints from sales history
    """
    points: list[PricePoint] = []

    try:
        # Get sales history from API
        history = await api.get_sales_history(
            game=game,
            title=title,
            period=f"{days}d",
        )

        if "sales" in history:
            for sale in history["sales"]:
                # Parse timestamp
                ts_str = sale.get("date") or sale.get("timestamp")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(
                            ts_str.replace("Z", "+00:00")  # noqa: FURB162
                        )
                    except (ValueError, TypeError):
                        ts = datetime.now(UTC)
                else:
                    ts = datetime.now(UTC)

                # Parse price (cents to USD)
                price_raw = sale.get("price", {})
                if isinstance(price_raw, dict):
                    usd_val = price_raw.get("USD") or price_raw.get("amount") or 0
                    price_cents = int(usd_val)
                else:
                    price_cents = int(price_raw or 0)

                price_usd = Decimal(price_cents) / 100

                points.append(
                    PricePoint(
                        game=game,
                        title=title,
                        price=price_usd,
                        timestamp=ts,
                        volume=1,
                        source="sales_history",
                    )
                )

    except Exception as e:
        logger.debug(
            "sales_history_fetch_error",
            extra={"error": str(e)},
        )

    return points


async def collect_from_aggregated(
    api: "IDMarketAPI",
    game: str,
    title: str,
) -> list[PricePoint]:
    """Collect price points from aggregated prices.

    Args:
        api: DMarket API client
        game: Game code
        title: Item name

    Returns:
        List of PricePoints from aggregated data
    """
    points: list[PricePoint] = []

    try:
        # Get aggregated prices
        aggregated = await api.get_aggregated_prices_bulk(
            game=game,
            titles=[title],
            limit=1,
        )

        if aggregated and "aggregatedPrices" in aggregated:
            for price_data in aggregated["aggregatedPrices"]:
                if price_data.get("title") == title:
                    # Best offer price
                    offer_price = int(price_data.get("offerBestPrice", 0))
                    if offer_price > 0:
                        points.append(
                            PricePoint(
                                game=game,
                                title=title,
                                price=Decimal(offer_price) / 100,
                                timestamp=datetime.now(UTC),
                                source="aggregated_offer",
                            )
                        )

                    # Best order price (buy orders)
                    order_price = int(price_data.get("orderBestPrice", 0))
                    if order_price > 0:
                        points.append(
                            PricePoint(
                                game=game,
                                title=title,
                                price=Decimal(order_price) / 100,
                                timestamp=datetime.now(UTC),
                                source="aggregated_order",
                            )
                        )

    except Exception as e:
        logger.debug(
            "aggregated_prices_fetch_error",
            extra={"error": str(e)},
        )

    return points


__all__ = ["collect_from_sales_history", "collect_from_aggregated"]
