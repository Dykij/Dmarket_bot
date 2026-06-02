"""
collector.py — MarketDataCollector class: lifecycle wrapper.

Wires the snapshot fetcher and the storage helpers together with a
background task. The class is intentionally thin: it does the
start/stop/loop dance and delegates the actual work to `snapshot.py`
and `storage.py`.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog

from .snapshot import collect_market_snapshot
from .storage import cleanup_old_data, export_to_csv, store_snapshot

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI
    from src.utils.database import DatabaseManager

logger = structlog.get_logger(__name__)


class MarketDataCollector:
    """Collects and stores historical market data."""

    def __init__(
        self,
        api_client: "DMarketAPI",
        db_manager: "DatabaseManager",
        collection_interval_minutes: int = 30,
        retention_days: int = 180,  # 6 months
    ):
        """Initialize the data collector.

        Args:
            api_client: DMarket API client
            db_manager: Database manager instance
            collection_interval_minutes: How often to collect data (default: 30 min)
            retention_days: How long to keep data (default: 180 days)
        """
        self.api_client = api_client
        self.db_manager = db_manager
        self.collection_interval = (
            collection_interval_minutes * 60
        )  # Convert to seconds
        self.retention_days = retention_days
        self._running = False
        self._task: asyncio.Task | None = None

        logger.info(
            "market_data_collector_initialized",
            interval_minutes=collection_interval_minutes,
            retention_days=retention_days,
        )

    async def start(self) -> None:
        """Start the background data collection task."""
        if self._running:
            logger.warning("data_collector_already_running")
            return

        self._running = True
        self._task = asyncio.create_task(self._collection_loop())
        logger.info("data_collector_started")

    async def stop(self) -> None:
        """Stop the background data collection task."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("data_collector_stopped")

    async def _collection_loop(self) -> None:
        """MAlgon collection loop that runs every N minutes."""
        while self._running:
            try:
                await self.collect_market_snapshot()
                await cleanup_old_data(self.db_manager, self.retention_days)
            except Exception as e:
                logger.error(
                    "data_collection_failed",
                    error=str(e),
                    exc_info=True,
                )

            # WAlgot for next collection interval
            await asyncio.sleep(self.collection_interval)

    async def collect_market_snapshot(self) -> dict[str, Any]:
        """Collect a snapshot of current market data and persist it.

        Returns:
            Statistics about collected data
        """
        stats = await collect_market_snapshot(self.api_client)
        await store_snapshot(self.db_manager, stats)
        return stats

    async def export_to_csv(
        self,
        output_path: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int:
        """Export historical data to CSV.

        Args:
            output_path: Path to output CSV file
            start_date: Start date (optional)
            end_date: End date (optional)

        Returns:
            Number of records exported
        """
        return await export_to_csv(
            self.db_manager, output_path, start_date, end_date
        )


__all__ = ["MarketDataCollector"]
