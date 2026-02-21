"""
Historical Market Data Collector - Roadmap Task #15.

Collects and stores historical market data for ML models and backtesting.
Runs as a background task every 30 minutes.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any

import structlog

from src.dmarket.dmarket_api import DMarketAPI
from src.utils.database import DatabaseManager

logger = structlog.get_logger(__name__)


class MarketDataCollector:
    """Collects and stores historical market data."""

    def __init__(
        self,
        api_client: DMarketAPI,
        db_manager: DatabaseManager,
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
        """Main collection loop that runs every N minutes."""
        while self._running:
            try:
                await self.collect_market_snapshot()
                await self._cleanup_old_data()
            except Exception as e:
                logger.error(
                    "data_collection_failed",
                    error=str(e),
                    exc_info=True,
                )

            # Wait for next collection interval
            await asyncio.sleep(self.collection_interval)

    async def collect_market_snapshot(self) -> dict[str, Any]:
        """Collect a snapshot of current market data.

        Returns:
            Statistics about collected data
        """
        start_time = datetime.now()
        logger.info("collecting_market_snapshot", timestamp=start_time.isoformat())

        stats = {
            "timestamp": start_time,
            "games": {},
            "total_items": 0,
            "total_sales": 0,
        }

        # Collect data for each supported game
        games = ["csgo", "dota2", "tf2", "rust"]

        for game in games:
            try:
                game_data = await self._collect_game_data(game)
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

        # Store snapshot in database
        await self._store_snapshot(stats)

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(
            "market_snapshot_collected",
            elapsed_seconds=elapsed,
            total_items=stats["total_items"],
            games=len(games),
        )

        return stats

    async def _collect_game_data(self, game: str) -> dict[str, Any]:
        """Collect data for a specific game.

        Args:
            game: Game name (csgo, dota2, etc.)

        Returns:
            Dictionary with collected data
        """
        # Get market items with pagination
        items = []
        offset = 0
        limit = 100
        max_items = 1000  # Limit to avoid too much data

        while len(items) < max_items:
            try:
                response = await self.api_client.get_market_items(
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

            # Count sales from last 24h if available
            sales = item.get("inMarket", 0)
            total_sales += sales

        avg_price = total_price / len(items) if items else 0

        return {
            "items_count": len(items),
            "sales_count": total_sales,
            "avg_price_cents": avg_price,
            "total_market_value_cents": total_price,
        }

    async def _store_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Store market snapshot in database.

        Args:
            snapshot: Market data snapshot
        """
        from src.models.market_history import MarketSnapshot

        async with self.db_manager.async_session_maker() as session:
            db_snapshot = MarketSnapshot(
                timestamp=snapshot["timestamp"],
                total_items=snapshot["total_items"],
                total_sales=snapshot["total_sales"],
                games_data=snapshot["games"],  # Store as JSON
            )
            session.add(db_snapshot)
            await session.commit()

        logger.debug("snapshot_stored_in_db", timestamp=snapshot["timestamp"])

    async def _cleanup_old_data(self) -> None:
        """Delete data older than retention period."""
        from src.models.market_history import MarketSnapshot

        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        async with self.db_manager.async_session_maker() as session:
            # Delete old snapshots
            from sqlalchemy import delete

            stmt = delete(MarketSnapshot).where(MarketSnapshot.timestamp < cutoff_date)
            result = await session.execute(stmt)
            await session.commit()

            deleted_count = result.rowcount
            if deleted_count > 0:
                logger.info(
                    "old_data_cleaned_up",
                    deleted_count=deleted_count,
                    cutoff_date=cutoff_date.isoformat(),
                )

    async def export_to_csv(
        self,
        output_path: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> None:
        """Export historical data to CSV.

        Args:
            output_path: Path to output CSV file
            start_date: Start date (optional)
            end_date: End date (optional)
        """
        import csv

        from src.models.market_history import MarketSnapshot

        logger.info("exporting_data_to_csv", path=output_path)

        async with self.db_manager.async_session_maker() as session:
            from sqlalchemy import select

            query = select(MarketSnapshot)

            if start_date:
                query = query.where(MarketSnapshot.timestamp >= start_date)
            if end_date:
                query = query.where(MarketSnapshot.timestamp <= end_date)

            query = query.order_by(MarketSnapshot.timestamp)

            result = await session.execute(query)
            snapshots = result.scalars().all()

        # Write to CSV (run in thread to avoid blocking)
        def write_csv():
            with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = [
                    "timestamp",
                    "total_items",
                    "total_sales",
                    "csgo_items",
                    "dota2_items",
                    "tf2_items",
                    "rust_items",
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for snapshot in snapshots:
                    row = {
                        "timestamp": snapshot.timestamp.isoformat(),
                        "total_items": snapshot.total_items,
                        "total_sales": snapshot.total_sales,
                        "csgo_items": snapshot.games_data.get("csgo", {}).get(
                            "items_count", 0
                        ),
                        "dota2_items": snapshot.games_data.get("dota2", {}).get(
                            "items_count", 0
                        ),
                        "tf2_items": snapshot.games_data.get("tf2", {}).get(
                            "items_count", 0
                        ),
                        "rust_items": snapshot.games_data.get("rust", {}).get(
                            "items_count", 0
                        ),
                    }
                    writer.writerow(row)

        await asyncio.to_thread(write_csv)

        logger.info(
            "data_exported",
            path=output_path,
            records=len(snapshots),
        )
