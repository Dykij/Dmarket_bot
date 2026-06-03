"""
storage.py — Persist market snapshots to the DB and export to CSV.

Two responsibilities (kept in one module because they share the
`MarketSnapshot` import + `db_manager.async_session_maker`):
    store_snapshot       — write one snapshot row
    cleanup_old_data     — delete rows older than retention_days
    export_to_csv        — dump historical snapshots to a CSV file
"""

from __future__ import annotations

import asyncio
import csv
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from src.utils.database import DatabaseManager

logger = structlog.get_logger(__name__)


async def store_snapshot(
    db_manager: "DatabaseManager",
    snapshot: dict[str, Any],
) -> None:
    """Store market snapshot in database.

    Args:
        db_manager: Database manager
        snapshot: Market data snapshot
    """
    from src.models.market_history import MarketSnapshot

    async with db_manager.async_session_maker() as session:
        db_snapshot = MarketSnapshot(
            timestamp=snapshot["timestamp"],
            total_items=snapshot["total_items"],
            total_sales=snapshot["total_sales"],
            games_data=snapshot["games"],
        )
        session.add(db_snapshot)
        await session.commit()

    logger.debug("snapshot_stored_in_db", timestamp=snapshot["timestamp"])


async def cleanup_old_data(
    db_manager: "DatabaseManager",
    retention_days: int,
) -> int:
    """Delete data older than retention period.

    Returns the number of rows deleted.
    """
    from sqlalchemy import delete

    from src.models.market_history import MarketSnapshot

    cutoff_date = datetime.now() - timedelta(days=retention_days)

    async with db_manager.async_session_maker() as session:
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
        return deleted_count


async def export_to_csv(
    db_manager: "DatabaseManager",
    output_path: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> int:
    """Export historical data to CSV.

    Args:
        db_manager: Database manager
        output_path: Path to output CSV file
        start_date: Start date (optional)
        end_date: End date (optional)

    Returns:
        Number of records exported
    """
    from sqlalchemy import select

    from src.models.market_history import MarketSnapshot

    logger.info("exporting_data_to_csv", path=output_path)

    async with db_manager.async_session_maker() as session:
        query = select(MarketSnapshot)

        if start_date:
            query = query.where(MarketSnapshot.timestamp >= start_date)
        if end_date:
            query = query.where(MarketSnapshot.timestamp <= end_date)

        query = query.order_by(MarketSnapshot.timestamp)

        result = await session.execute(query)
        snapshots = result.scalars().all()

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
    return len(snapshots)


__all__ = ["store_snapshot", "cleanup_old_data", "export_to_csv"]
