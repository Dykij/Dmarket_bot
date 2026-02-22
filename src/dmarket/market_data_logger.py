"""Market Data Logger for Algo TrAlgoning.

This module collects market data for training the Algo price predictor.
It runs in the background and logs item prices, float values, and other
relevant data to a CSV file.

The first 48 hours of operation are dedicated to data collection only.
After sufficient data is collected, the Algo model can be trained.

Usage:
    ```python
    from src.dmarket.market_data_logger import MarketDataLogger

    logger = MarketDataLogger(api)
    await logger.start_logging()
    ```

CSV Output Format:
    item_name,price,float_value,is_stat_trak,game_id,timestamp
"""

import asyncio
import csv
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI

logger = logging.getLogger(__name__)

# Default paths
DEFAULT_OUTPUT_PATH = "data/market_history.csv"
DEFAULT_LOG_INTERVAL = 300  # 5 minutes between scans


@dataclass
class MarketDataLoggerConfig:
    """Configuration for Market Data Logger.

    Attributes:
        output_path: Path to CSV file
        log_interval: Seconds between scan iterations
        max_items_per_scan: Maximum items to log per scan
        games: List of game IDs to scan
        min_price_cents: Minimum item price in cents
        max_price_cents: Maximum item price in cents
    """

    output_path: str = DEFAULT_OUTPUT_PATH
    log_interval: float = DEFAULT_LOG_INTERVAL
    max_items_per_scan: int = 100
    games: list[str] | None = None
    min_price_cents: int = 100  # $1 minimum
    max_price_cents: int = 50000  # $500 maximum

    def __post_init__(self) -> None:
        if self.games is None:
            self.games = ["a8db"]  # CS:GO/CS2 by default


class MarketDataLogger:
    """Logger for collecting market data for Algo training.

    This class scans the DMarket and logs item data to CSV format.
    The collected data is used to train the Algo price prediction model.

    Data Collected:
    - Item name (full title)
    - Price in USD
    - Float value (for wear items)
    - StatTrak status
    - Game ID
    - Timestamp

    Example:
        ```python
        logger = MarketDataLogger(api)

        # Start continuous logging
        await logger.start_logging(duration_hours=48)

        # Or log once
        await logger.log_market_data()
        ```
    """

    def __init__(
        self,
        api: "DMarketAPI",
        config: MarketDataLoggerConfig | None = None,
    ) -> None:
        """Initialize the Market Data Logger.

        Args:
            api: DMarket API client
            config: Logger configuration (uses defaults if not provided)
        """
        self.api = api
        self.config = config or MarketDataLoggerConfig()

        # Statistics
        self.stats = {
            "total_items_logged": 0,
            "scans_completed": 0,
            "start_time": None,
        }

        self._running = False

        # Ensure output directory exists
        self._ensure_output_dir()

        logger.info(
            "market_data_logger_initialized",
            output_path=self.config.output_path,
            log_interval=self.config.log_interval,
        )

    def _ensure_output_dir(self) -> None:
        """Create output directory if it doesn't exist."""
        output_dir = os.path.dirname(self.config.output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

    def _ensure_csv_header(self) -> None:
        """Create CSV file with header if it doesn't exist."""
        path = Path(self.config.output_path)

        if not path.exists():
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "item_name",
                        "price",
                        "float_value",
                        "is_stat_trak",
                        "game_id",
                        "timestamp",
                    ]
                )
            logger.info("csv_file_created", path=str(path))

    async def log_market_data(self) -> int:
        """Log current market data to CSV.

        Returns:
            Number of items logged
        """
        self._ensure_csv_header()

        items_logged = 0

        try:
            for game_id in self.config.games or ["a8db"]:
                items = await self._fetch_items(game_id)

                if items:
                    self._write_items_to_csv(items, game_id)
                    items_logged += len(items)

            self.stats["total_items_logged"] += items_logged
            self.stats["scans_completed"] += 1

            logger.info(
                "market_data_logged",
                items_logged=items_logged,
                total=self.stats["total_items_logged"],
            )

            return items_logged

        except Exception as e:
            logger.exception("market_data_logging_failed", error=str(e))
            return 0

    async def _fetch_items(self, game_id: str) -> list[dict[str, Any]]:
        """Fetch items from DMarket API.

        Args:
            game_id: Game identifier

        Returns:
            List of item dictionaries
        """
        try:
            # price_from and price_to are in cents in config, but API expects dollars
            response = await self.api.get_market_items(
                game=game_id,
                limit=self.config.max_items_per_scan,
                price_from=self.config.min_price_cents
                / 100,  # Convert cents to dollars
                price_to=self.config.max_price_cents / 100,  # Convert cents to dollars
                sort="price",
            )

            return response.get("objects", [])

        except Exception as e:
            logger.warning(
                "fetch_items_failed",
                game_id=game_id,
                error=str(e),
            )
            return []

    def _write_items_to_csv(self, items: list[dict[str, Any]], game_id: str) -> None:
        """Write items to CSV file.

        Args:
            items: List of item dictionaries
            game_id: Game identifier
        """
        timestamp = datetime.now(tz=None).isoformat()

        with open(self.config.output_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            for item in items:
                try:
                    title = item.get("title", "")
                    extra = item.get("extra", {}) or {}

                    # Get price
                    price_data = item.get("price", {})
                    if isinstance(price_data, dict):
                        price_cents = int(
                            price_data.get("USD", 0) or price_data.get("amount", 0)
                        )
                    else:
                        price_cents = int(price_data)

                    price_usd = price_cents / 100

                    # Get float value
                    float_value = extra.get("floatValue") or extra.get("float", 0.5)

                    # Check StatTrak
                    is_stat_trak = 1 if "StatTrak" in title else 0

                    writer.writerow(
                        [
                            title,
                            price_usd,
                            float_value,
                            is_stat_trak,
                            game_id,
                            timestamp,
                        ]
                    )

                except Exception as e:
                    logger.debug(
                        "item_write_failed",
                        item_id=item.get("itemId", ""),
                        error=str(e),
                    )

    async def start_logging(
        self,
        duration_hours: float | None = None,
    ) -> None:
        """Start continuous market data logging.

        Args:
            duration_hours: Duration to run (None = infinite)
        """
        self._running = True
        self.stats["start_time"] = time.time()

        end_time = None
        if duration_hours:
            end_time = self.stats["start_time"] + (duration_hours * 3600)

        logger.info(
            "market_logging_started",
            duration_hours=duration_hours,
        )

        try:
            while self._running:
                # Check duration
                if end_time and time.time() >= end_time:
                    logger.info("logging_duration_reached")
                    break

                # Log market data
                await self.log_market_data()

                # WAlgot before next iteration
                await asyncio.sleep(self.config.log_interval)

        except asyncio.CancelledError:
            logger.info("market_logging_cancelled")
        except Exception as e:
            logger.exception("market_logging_error", error=str(e))
        finally:
            self._running = False
            logger.info(
                "market_logging_stopped",
                stats=self.stats,
            )

    def stop(self) -> None:
        """Stop continuous logging."""
        self._running = False

    def get_stats(self) -> dict[str, Any]:
        """Get logging statistics.

        Returns:
            Dictionary with current statistics
        """
        result = dict(self.stats)

        if self.stats["start_time"]:
            elapsed = time.time() - self.stats["start_time"]
            result["elapsed_hours"] = elapsed / 3600
            result["items_per_hour"] = (
                self.stats["total_items_logged"] / (elapsed / 3600)
                if elapsed > 0
                else 0
            )

        return result

    def get_data_status(self) -> dict[str, Any]:
        """Get status of collected data.

        Returns:
            Dictionary with data collection status:
            - exists: Whether CSV file exists
            - rows: Number of data rows
            - ready_for_training: Whether enough data for training
        """
        path = Path(self.config.output_path)

        status: dict[str, Any] = {
            "exists": path.exists(),
            "rows": 0,
            "ready_for_training": False,
            "path": str(path),
        }

        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    # Count rows (excluding header)
                    row_count = sum(1 for _ in f) - 1
                    status["rows"] = max(0, row_count)
                    status["ready_for_training"] = row_count >= 100

            except Exception as e:
                logger.warning("data_status_check_failed", error=str(e))

        return status
