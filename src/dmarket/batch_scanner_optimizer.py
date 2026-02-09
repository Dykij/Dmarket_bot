"""Optimized batch processing for ArbitrageScanner.

This module provides performance-optimized batch processing
with configurable batch sizes based on profiling results.

Key optimizations:
1. Batch processing with optimal size (500 items)
2. Parallel batch execution
3. Error handling with graceful degradation
4. Performance metrics logging

Based on profiling results showing 50x speedup with batch_size=500.
"""

import asyncio
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Optimal batch size from profiling (50x speedup)
OPTIMAL_BATCH_SIZE = 500
MAX_CONCURRENT_BATCHES = 4  # Limit concurrent batches to prevent resource exhaustion


class BatchScannerOptimizer:
    """Optimized batch processing for arbitrage scanning."""

    def __init__(self, batch_size: int = OPTIMAL_BATCH_SIZE):
        """Initialize batch optimizer.

        Args:
            batch_size: Number of items per batch (default: 500 from profiling)
        """
        self.batch_size = batch_size
        self.metrics = {
            "total_items": 0,
            "total_time": 0.0,
            "batches_processed": 0,
            "errors": 0,
        }

    async def process_items_batched(
        self,
        items: list[dict[str, Any]],
        process_func: callable,
    ) -> list[dict[str, Any]]:
        """Process items in optimized batches.

        Args:
            items: List of items to process
            process_func: Async function to process each batch

        Returns:
            List of processed results

        Example:
            >>> optimizer = BatchScannerOptimizer()
            >>> results = await optimizer.process_items_batched(
            ...     items=market_items, process_func=scanner.analyze_batch
            ... )
        """
        if not items:
            return []

        start_time = time.perf_counter()
        self.metrics["total_items"] += len(items)

        logger.info(
            "batch_processing_started",
            total_items=len(items),
            batch_size=self.batch_size,
            estimated_batches=len(items) // self.batch_size + 1,
        )

        # Split items into batches
        batches = [items[i : i + self.batch_size] for i in range(0, len(items), self.batch_size)]

        # Process batches with controlled concurrency
        results = []
        for i in range(0, len(batches), MAX_CONCURRENT_BATCHES):
            batch_group = batches[i : i + MAX_CONCURRENT_BATCHES]
            tasks = [
                self._process_single_batch(batch, process_func, idx + i)
                for idx, batch in enumerate(batch_group)
            ]

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Flatten results and handle errors
            for result in batch_results:
                if isinstance(result, Exception):
                    self.metrics["errors"] += 1
                    logger.warning(
                        "batch_processing_error",
                        error=str(result),
                        error_type=type(result).__name__,
                    )
                    continue

                if isinstance(result, list):
                    results.extend(result)

            self.metrics["batches_processed"] += len(batch_group)

        elapsed = time.perf_counter() - start_time
        self.metrics["total_time"] += elapsed

        throughput = len(items) / elapsed if elapsed > 0 else 0

        logger.info(
            "batch_processing_complete",
            total_items=len(items),
            results_count=len(results),
            elapsed_ms=round(elapsed * 1000, 2),
            throughput_items_per_sec=round(throughput, 2),
            batches_processed=len(batches),
            errors=self.metrics["errors"],
        )

        return results

    async def _process_single_batch(
        self,
        batch: list[dict[str, Any]],
        process_func: callable,
        batch_idx: int,
    ) -> list[dict[str, Any]]:
        """Process a single batch with error handling.

        Args:
            batch: Items in this batch
            process_func: Processing function
            batch_idx: Batch index for logging

        Returns:
            Processed results from this batch
        """
        try:
            logger.debug(
                "processing_batch",
                batch_idx=batch_idx,
                batch_size=len(batch),
            )

            result = await process_func(batch)
            return result if isinstance(result, list) else []

        except Exception as e:
            logger.error(
                "batch_processing_failed",
                batch_idx=batch_idx,
                batch_size=len(batch),
                error=str(e),
                exc_info=True,
            )
            raise

    async def process_games_parallel(
        self,
        games: list[str],
        scan_func: callable,
    ) -> dict[str, list[dict[str, Any]]]:
        """Scan multiple games in parallel.

        Args:
            games: List of game IDs to scan
            scan_func: Async function to scan a single game

        Returns:
            Dictionary mapping game ID to scan results

        Example:
            >>> optimizer = BatchScannerOptimizer()
            >>> results = await optimizer.process_games_parallel(
            ...     games=["csgo", "dota2", "tf2", "rust"], scan_func=scanner.scan_game
            ... )
        """
        start_time = time.perf_counter()

        logger.info(
            "parallel_game_scan_started",
            games=games,
            game_count=len(games),
        )

        # Scan all games in parallel
        tasks = [scan_func(game) for game in games]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        game_results = {}
        for game, result in zip(games, results, strict=False):
            if isinstance(result, Exception):
                logger.error(
                    "game_scan_failed",
                    game=game,
                    error=str(result),
                )
                game_results[game] = []
            else:
                game_results[game] = result if isinstance(result, list) else []

        elapsed = time.perf_counter() - start_time

        logger.info(
            "parallel_game_scan_complete",
            games=games,
            elapsed_ms=round(elapsed * 1000, 2),
            total_opportunities=sum(len(v) for v in game_results.values()),
        )

        return game_results

    def get_metrics(self) -> dict[str, Any]:
        """Get performance metrics.

        Returns:
            Dictionary with performance metrics
        """
        avg_time = (
            self.metrics["total_time"] / self.metrics["batches_processed"]
            if self.metrics["batches_processed"] > 0
            else 0
        )

        throughput = (
            self.metrics["total_items"] / self.metrics["total_time"]
            if self.metrics["total_time"] > 0
            else 0
        )

        return {
            **self.metrics,
            "average_batch_time": round(avg_time, 3),
            "throughput_items_per_sec": round(throughput, 2),
        }

    def reset_metrics(self) -> None:
        """Reset performance metrics."""
        self.metrics = {
            "total_items": 0,
            "total_time": 0.0,
            "batches_processed": 0,
            "errors": 0,
        }


# Convenience function for quick optimization
async def optimize_batch_processing(
    items: list[dict[str, Any]],
    process_func: callable,
    batch_size: int = OPTIMAL_BATCH_SIZE,
) -> list[dict[str, Any]]:
    """Quick helper for optimized batch processing.

    Args:
        items: Items to process
        process_func: Processing function
        batch_size: Batch size (default: 500)

    Returns:
        Processed results

    Example:
        >>> from src.dmarket.batch_scanner_optimizer import optimize_batch_processing
        >>> results = await optimize_batch_processing(
        ...     items=market_items, process_func=scanner.analyze_items
        ... )
    """
    optimizer = BatchScannerOptimizer(batch_size=batch_size)
    return await optimizer.process_items_batched(items, process_func)
