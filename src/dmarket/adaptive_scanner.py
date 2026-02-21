"""Adaptive scanning module with dynamic intervals based on market volatility.

This module implements intelligent scan frequency adjustment to:
- Increase scan rate during high volatility periods
- Reduce API calls during stable market conditions
- Optimize arbitrage opportunity detection
"""

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class MarketSnapshot:
    """Market state snapshot for volatility calculation."""

    timestamp: datetime
    avg_price: float
    items_count: int
    price_spread: float  # Max price - min price


class AdaptiveScanner:
    """Scanner with dynamic intervals based on market volatility."""

    def __init__(
        self,
        min_interval: int = 30,  # Minimum 30 seconds between scans
        max_interval: int = 300,  # Maximum 5 minutes between scans
        volatility_window: int = 10,  # Last 10 snapshots for volatility
    ) -> None:
        """Initialize adaptive scanner.

        Args:
            min_interval: Minimum seconds between scans (high volatility)
            max_interval: Maximum seconds between scans (stable market)
            volatility_window: Number of snapshots to analyze
        """
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.volatility_window = volatility_window

        self.snapshots: deque[MarketSnapshot] = deque(maxlen=volatility_window)
        self.current_interval = max_interval  # Start conservative

        logger.info(
            "adaptive_scanner_initialized",
            min_interval=min_interval,
            max_interval=max_interval,
            volatility_window=volatility_window,
        )

    def add_snapshot(self, items: list[dict[str, Any]]) -> None:
        """Add market snapshot for volatility analysis.

        Args:
            items: List of market items from latest scan
        """
        # FIX: Защита от пустых снимков (ошибки API)
        # Сбрасываем интервал до 60 сек при пустом ответе вместо увеличения до max
        if not items:
            self.current_interval = min(self.current_interval, 60)
            logger.warning(
                "empty_market_snapshot",
                message="Получен пустой снимок рынка, интервал сброшен до 60с",
            )
            return

        prices = [
            float(item.get("price", {}).get("USD", 0)) / 100
            for item in items
            if item.get("price", {}).get("USD", 0) > 0
        ]

        if not prices:
            return

        snapshot = MarketSnapshot(
            timestamp=datetime.now(),
            avg_price=sum(prices) / len(prices),
            items_count=len(items),
            price_spread=max(prices) - min(prices),
        )

        self.snapshots.append(snapshot)

        logger.debug(
            "market_snapshot_added",
            avg_price=snapshot.avg_price,
            items_count=snapshot.items_count,
            price_spread=snapshot.price_spread,
        )

    def calculate_volatility(self) -> float:
        """Calculate market volatility from recent snapshots.

        Returns:
            Volatility score (0.0 = stable, 1.0 = highly volatile)
        """
        if len(self.snapshots) < 3:
            return 0.5  # Default moderate volatility

        # Calculate price variance
        avg_prices = [s.avg_price for s in self.snapshots]
        mean = sum(avg_prices) / len(avg_prices)
        variance = sum((p - mean) ** 2 for p in avg_prices) / len(avg_prices)
        std_dev = variance**0.5

        # Calculate coefficient of variation (normalized volatility)
        if mean > 0:
            cv = std_dev / mean
        else:
            cv = 0

        # Calculate spread volatility
        spreads = [s.price_spread for s in self.snapshots]
        spread_variance = sum(
            (s - sum(spreads) / len(spreads)) ** 2 for s in spreads
        ) / len(spreads)
        spread_cv = (spread_variance**0.5) / (sum(spreads) / len(spreads))

        # Combined volatility score (0-1)
        volatility = min(1.0, (cv + spread_cv) * 10)

        logger.debug(
            "volatility_calculated",
            price_cv=cv,
            spread_cv=spread_cv,
            volatility=volatility,
        )

        return volatility

    def get_next_interval(self) -> int:
        """Calculate optimal interval for next scan based on volatility.

        Returns:
            Seconds to wait before next scan
        """
        volatility = self.calculate_volatility()

        # High volatility → shorter interval
        # Low volatility → longer interval
        interval = int(
            self.max_interval - (volatility * (self.max_interval - self.min_interval))
        )

        self.current_interval = interval

        logger.info(
            "scan_interval_adjusted",
            volatility=volatility,
            next_interval_seconds=interval,
            snapshots_count=len(self.snapshots),
        )

        return interval

    async def wait_next_scan(self) -> None:
        """Wait for the calculated interval before next scan."""
        interval = self.get_next_interval()
        logger.info("waiting_for_next_scan", seconds=interval)
        await asyncio.sleep(interval)

    def should_scan_now(self, last_scan_time: datetime) -> bool:
        """Check if enough time has passed for next scan.

        Args:
            last_scan_time: Timestamp of last scan

        Returns:
            True if should scan now
        """
        elapsed = (datetime.now() - last_scan_time).total_seconds()
        return elapsed >= self.current_interval


# Example usage
async def example_usage():
    """Example of adaptive scanner usage."""
    from src.dmarket.dmarket_api import DMarketAPI

    api = DMarketAPI(public_key="test", secret_key="test")
    scanner = AdaptiveScanner(min_interval=30, max_interval=300)

    last_scan = datetime.now() - timedelta(seconds=1000)  # Force first scan

    while True:
        if scanner.should_scan_now(last_scan):
            # Perform scan
            items_response = await api.get_market_items(game="csgo", limit=100)
            items = items_response.get("objects", [])

            # Add snapshot for volatility analysis
            scanner.add_snapshot(items)

            last_scan = datetime.now()

            logger.info("scan_completed", items_found=len(items))

        # Wait for next scan with adaptive interval
        await scanner.wait_next_scan()
