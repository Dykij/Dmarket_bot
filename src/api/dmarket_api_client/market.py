"""
market.py — Market data endpoints.

Mixin with the read-only market-scan and aggregated-price methods.
Mixed into `DMarketAPIClient` (see `core.py`).
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("DMarketAPI")


class _MarketMixin:
    """Read-only market data endpoints (no writes)."""

    async def get_market_items_v2(
        self,
        game_id: str,
        limit: int = 100,
        cursor: Optional[str] = None,
        **filters: Any,
    ) -> Dict[str, Any]:
        """High-throughput Marketplace v2 scan."""
        params = {"currency": "USD", "gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        if filters:
            params.update(filters)
        return await self.make_request("GET", "/exchange/v1/market/items", params=params)

    # --- v12.0: Aggregated Prices (Strategy A core) ---
    async def get_aggregated_prices(
        self, game_id: str, titles: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Batch fetch of best_bid + best_ask + count for up to 100 items in 1 request.
        Returns: {title: {"best_ask": float, "best_bid": float, "ask_count": int, "bid_count": int}}

        Endpoint: POST /marketplace-api/v1/aggregated-prices
        Body: {"gameId": "a8db", "titles": ["AK-47 | Redline (Field-Tested)", ...]}
        """
        if not titles:
            return {}

        # Chunk to 100 per request (DMarket limit)
        results: Dict[str, Dict[str, Any]] = {}
        for chunk_start in range(0, len(titles), 100):
            chunk = titles[chunk_start : chunk_start + 100]
            try:
                res = await self.make_request(
                    "POST",
                    "/marketplace-api/v1/aggregated-prices",
                    body={"gameId": game_id, "titles": chunk},
                )
                # Response format: {"aggregatedPrices": [{title, bestAsk, bestBid, ...}, ...]}
                for entry in res.get("aggregatedPrices", []):
                    title = entry.get("title", "")
                    if not title:
                        continue
                    # bestAsk and bestBid are in cents (strings) per DMarket format
                    best_ask_cents = entry.get("bestAsk", "0")
                    best_bid_cents = entry.get("bestBid", "0")
                    try:
                        best_ask = float(best_ask_cents) / 100.0 if best_ask_cents else 0.0
                    except (ValueError, TypeError):
                        best_ask = 0.0
                    try:
                        best_bid = float(best_bid_cents) / 100.0 if best_bid_cents else 0.0
                    except (ValueError, TypeError):
                        best_bid = 0.0
                    results[title] = {
                        "best_ask": best_ask,
                        "best_bid": best_bid,
                        "ask_count": int(entry.get("askCount", 0)),
                        "bid_count": int(entry.get("bidCount", 0)),
                    }
            except Exception as e:
                logger.warning(f"Aggregated prices batch failed: {e}")
                # Fill with zeros for failed items
                for t in chunk:
                    if t not in results:
                        results[t] = {
                            "best_ask": 0.0,
                            "best_bid": 0.0,
                            "ask_count": 0,
                            "bid_count": 0,
                        }

        return results

    # --- v12.0: Last Sales (Strategy B) ---
    async def get_last_sales(
        self, game_id: str, title: str, days: int = 30, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Fetch real DMarket sale transactions for an item.

        Endpoint: GET /trade-aggregator/v1/last-sales
        Params: gameId, title, days, limit
        """
        try:
            params = {
                "gameId": game_id,
                "title": title,
                "days": days,
                "limit": limit,
            }
            res = await self.make_request("GET", "/trade-aggregator/v1/last-sales", params=params)
            sales = res.get("sales", res.get("items", []))
            normalized = []
            for s in sales:
                price_cents = (
                    s.get("price", {}).get("USD", 0)
                    if isinstance(s.get("price"), dict)
                    else s.get("price", 0)
                )
                try:
                    price_usd = float(price_cents) / 100.0
                except (ValueError, TypeError):
                    continue
                normalized.append(
                    {
                        "price": price_usd,
                        "date": s.get("date") or s.get("soldAt") or s.get("createdAt"),
                    }
                )
            return normalized
        except Exception as e:
            logger.debug(f"Last sales fetch failed for {title}: {e}")
            return []

    # --- v12.0: Low Fee Items (Strategy C) ---
    async def get_low_fee_items(self, game_id: str) -> List[Dict[str, Any]]:
        """
        Daily list of items with reduced DMarket fees (2-3% vs 5%).

        Endpoint: GET /marketplace-api/v1/low-fee-items
        """
        try:
            res = await self.make_request(
                "GET", "/marketplace-api/v1/low-fee-items", params={"gameId": game_id}
            )
            items = res.get("items", [])
            normalized = []
            for it in items:
                title = it.get("title", "")
                fee = it.get("fee", 0.05)
                if isinstance(fee, str):
                    try:
                        fee = float(fee) / 100.0
                    except ValueError:
                        fee = 0.05
                normalized.append({"title": title, "fee_rate": fee})
            return normalized
        except Exception as e:
            logger.debug(f"Low-fee items fetch failed: {e}")
            return []
