"""
market.py — Market data endpoints.

Mixin with the read-only market-scan and aggregated-price methods.
Mixed into `DMarketAPIClient` (see `core.py`).
"""

from __future__ import annotations

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
        self, game_id: str, titles: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Batch fetch of best_bid + best_ask + count for up to 100 items per request.
        Returns: {title: {"best_ask": float, "best_bid": float, "ask_count": int, "bid_count": int}}

        Endpoint: POST /marketplace-api/v1/aggregated-prices
        Body: {"limit": 100, "filter": {"game": "a8db", "titles": ["...", "..."]}}
        Response: {"aggregatedPrices": [{title, orderBestPrice, offerBestPrice, orderCount, offerCount}, ...]}

        When `titles` is provided, chunks to 100 per request and asks DMarket
        to filter by those specific titles. Without `titles`, returns DMarket's
        top-100 (not what we want for sniping).
        """
        results: Dict[str, Dict[str, Any]] = {}

        # If no titles given, ask DMarket for its top page (used for discovery)
        if not titles:
            try:
                res = await self.make_request(
                    "POST",
                    "/marketplace-api/v1/aggregated-prices",
                    body={"limit": 100, "filter": {"game": game_id}},
                )
                for entry in res.get("aggregatedPrices", []):
                    title = entry.get("title", "")
                    if not title:
                        continue
                    ask_obj = entry.get("orderBestPrice") or {}
                    bid_obj = entry.get("offerBestPrice") or {}
                    try:
                        best_ask = float(ask_obj.get("Amount", "0")) / 100.0
                    except (ValueError, TypeError, AttributeError):
                        best_ask = 0.0
                    try:
                        best_bid = float(bid_obj.get("Amount", "0")) / 100.0
                    except (ValueError, TypeError, AttributeError):
                        best_bid = 0.0
                    results[title] = {
                        "best_ask": best_ask,
                        "best_bid": best_bid,
                        "ask_count": int(entry.get("orderCount", 0)),
                        "bid_count": int(entry.get("offerCount", 0)),
                    }
            except Exception as e:
                logger.warning(f"Aggregated prices batch failed: {e}", exc_info=True)
            return results

        # Chunked fetch with explicit title filter
        for chunk_start in range(0, len(titles), 100):
            chunk = titles[chunk_start : chunk_start + 100]
            try:
                res = await self.make_request(
                    "POST",
                    "/marketplace-api/v1/aggregated-prices",
                    body={"limit": 100, "filter": {"game": game_id, "titles": chunk}},
                )
                for entry in res.get("aggregatedPrices", []):
                    title = entry.get("title", "")
                    if not title:
                        continue
                    ask_obj = entry.get("orderBestPrice") or {}
                    bid_obj = entry.get("offerBestPrice") or {}
                    try:
                        best_ask = float(ask_obj.get("Amount", "0")) / 100.0
                    except (ValueError, TypeError, AttributeError):
                        best_ask = 0.0
                    try:
                        best_bid = float(bid_obj.get("Amount", "0")) / 100.0
                    except (ValueError, TypeError, AttributeError):
                        best_bid = 0.0
                    results[title] = {
                        "best_ask": best_ask,
                        "best_bid": best_bid,
                        "ask_count": int(entry.get("orderCount", 0)),
                        "bid_count": int(entry.get("offerCount", 0)),
                    }
            except Exception as e:
                logger.warning(
                    f"Aggregated prices batch failed (chunk {chunk_start}-{chunk_start+len(chunk)}): {e}",
                    exc_info=True,
                )
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
