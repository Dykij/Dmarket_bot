"""
supply_tracking.py — DMarket Supply Monitoring.

v15.7: Monitors listing counts on DMarket to detect thin markets.
Thin market = fewer listings = higher margins for snipers.

Integration:
- Called from _stage_scan in cycle_orchestrator.py
- Results used in filter pipeline for margin adjustment
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("SupplyTracking")


@dataclass
class SupplyMetrics:
    """Supply metrics for a specific item."""
    title: str = ""
    ask_count: int = 0  # number of sell listings
    bid_count: int = 0  # number of buy orders
    supply_ratio: float = 0.0  # asks / (asks + bids)
    is_thin_market: bool = False
    margin_boost_pct: float = 0.0  # extra margin % for thin markets

    @property
    def is_liquid(self) -> bool:
        """Item has enough listings for reliable pricing."""
        return self.ask_count >= 3 and self.bid_count >= 1


class SupplyTracker:
    """
    Tracks DMarket listing counts to detect thin markets.

    Thin markets (few listings) = higher margins because:
    1. Less competition from other bots
    2. Sellers more willing to accept lower offers
    3. Price discovery is less efficient

    This is a passive tracker — it analyzes existing agg_prices data
    without making additional API calls.
    """

    def __init__(self) -> None:
        self._supply_cache: dict[str, SupplyMetrics] = {}
        self._cache_ts: float = 0.0
        self._cache_ttl: float = 60.0  # 1 minute

    def analyze_supply(
        self,
        title: str,
        ask_count: int,
        bid_count: int,
    ) -> SupplyMetrics:
        """
        Analyze supply metrics for a single item.
        Returns SupplyMetrics with thin market detection.
        """
        total = ask_count + bid_count
        supply_ratio = ask_count / total if total > 0 else 0.5

        # Thin market thresholds
        is_thin = ask_count < 5 or (ask_count < 10 and bid_count > ask_count * 2)

        # Margin boost for thin markets (more listings = less boost)
        if ask_count <= 2:
            margin_boost = 3.0  # very thin — high boost
        elif ask_count <= 5:
            margin_boost = 1.5  # thin — moderate boost
        elif ask_count <= 10:
            margin_boost = 0.5  # slightly thin — small boost
        else:
            margin_boost = 0.0  # liquid — no boost

        metrics = SupplyMetrics(
            title=title,
            ask_count=ask_count,
            bid_count=bid_count,
            supply_ratio=supply_ratio,
            is_thin_market=is_thin,
            margin_boost_pct=margin_boost,
        )

        # Cache the result
        self._supply_cache[title] = metrics

        return metrics

    def analyze_batch(
        self,
        agg_prices: dict[str, dict[str, Any]],
    ) -> dict[str, SupplyMetrics]:
        """
        Analyze supply for a batch of items from aggregated prices.
        Returns dict of title -> SupplyMetrics.
        """
        results: dict[str, SupplyMetrics] = {}

        for title, agg in agg_prices.items():
            ask_count = int(agg.get("ask_count") or 0)
            bid_count = int(agg.get("bid_count") or 0)
            results[title] = self.analyze_supply(title, ask_count, bid_count)

        self._cache_ts = time.time()
        return results

    def get_thin_market_items(
        self,
        min_boost_pct: float = 1.0,
    ) -> list[SupplyMetrics]:
        """
        Get items currently in thin market conditions.
        Returns items with margin_boost_pct >= min_boost_pct.
        """
        return [
            m for m in self._supply_cache.values()
            if m.margin_boost_pct >= min_boost_pct
        ]

    @property
    def thin_market_count(self) -> int:
        """Number of items currently in thin market conditions."""
        return len([m for m in self._supply_cache.values() if m.is_thin_market])

    def get_supply_summary(self) -> dict[str, Any]:
        """Get a summary of current supply conditions."""
        total = len(self._supply_cache)
        thin = self.thin_market_count
        avg_asks = (
            sum(m.ask_count for m in self._supply_cache.values()) / total
            if total > 0 else 0
        )
        return {
            "total_items": total,
            "thin_market_items": thin,
            "thin_market_pct": (thin / total * 100) if total > 0 else 0,
            "avg_ask_count": round(avg_asks, 1),
        }
