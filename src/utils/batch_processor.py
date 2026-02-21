"""Simplified batch processing for single-user operations.

This module provides efficient batch processing for large datasets
without the complexity of distributed task queues like Celery.
Perfect for single-user scenarios.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from structlog import get_logger

logger = get_logger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class SimpleBatchProcessor:
    """Simple batch processor for memory-efficient processing."""

    def __init__(self, batch_size: int = 100, delay_between_batches: float = 0.1):
        """Initialize batch processor.

        Args:
            batch_size: Number of items per batch
            delay_between_batches: Delay in seconds between batches

        """
        self.batch_size = batch_size
        self.delay_between_batches = delay_between_batches

    async def process_in_batches(
        self,
        items: list[T],
        process_fn: Callable[[list[T]], Awaitable[Any]],
        progress_callback: Callable[[int, int], Awaitable[Any]] | None = None,
        error_callback: Callable[[Exception, list[T]], Awaitable[Any]] | None = None,
    ) -> list[R]:
        """Process items in batches.

        Args:
            items: List of items to process
            process_fn: Function to process each batch
            progress_callback: Optional callback(processed, total)
            error_callback: Optional callback(error, failed_batch)

        Returns:
            List of processing results

        """
        results: list[R] = []
        total_items = len(items)

        logger.info(
            "Starting batch processing",
            total_items=total_items,
            batch_size=self.batch_size,
        )

        for i in range(0, total_items, self.batch_size):
            batch = items[i : i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (total_items + self.batch_size - 1) // self.batch_size

            try:
                logger.debug(
                    f"Processing batch {batch_num}/{total_batches}",
                    batch_size=len(batch),
                )

                # Process batch
                batch_result = await process_fn(batch)

                if batch_result:
                    if isinstance(batch_result, list):
                        results.extend(batch_result)
                    else:
                        results.append(batch_result)

                # Update progress
                processed = min(i + len(batch), total_items)
                if progress_callback:
                    await progress_callback(processed, total_items)

                # Delay between batches to prevent overload
                if i + self.batch_size < total_items:
                    await asyncio.sleep(self.delay_between_batches)

            except Exception as e:
                logger.exception(
                    f"Error processing batch {batch_num}",
                    error=str(e),
                    batch_size=len(batch),
                )

                if error_callback:
                    await error_callback(e, batch)
                else:
                    raise

        logger.info(
            "Batch processing completed",
            total_processed=total_items,
            results_count=len(results),
        )

        return results

    async def process_with_concurrency(
        self,
        items: list[T],
        process_fn: Callable[[T], Awaitable[R]],
        max_concurrent: int = 5,
        progress_callback: Callable[[int, int], Awaitable[Any]] | None = None,
    ) -> list[R]:
        """Process items with limited concurrency.

        Args:
            items: List of items to process
            process_fn: Function to process each item
            max_concurrent: Maximum concurrent tasks
            progress_callback: Optional callback(processed, total)

        Returns:
            List of processing results

        """
        semaphore = asyncio.Semaphore(max_concurrent)
        total_items = len(items)
        processed_count = 0
        results: list[R] = []

        logger.info(
            "Starting concurrent processing",
            total_items=total_items,
            max_concurrent=max_concurrent,
        )

        async def process_with_semaphore(item: T) -> R | None:
            """Process single item with semaphore."""
            nonlocal processed_count

            async with semaphore:
                try:
                    result = await process_fn(item)
                    processed_count += 1

                    if progress_callback:
                        await progress_callback(processed_count, total_items)

                    return result

                except Exception as e:
                    logger.exception(
                        "Error processing item",
                        error=str(e),
                        item=str(item)[:100],
                    )
                    return None

        # Create tasks
        tasks = [process_with_semaphore(item) for item in items]

        # Execute concurrently
        raw_results = await asyncio.gather(*tasks, return_exceptions=False)

        # Filter out None results
        results = [r for r in raw_results if r is not None]

        logger.info(
            "Concurrent processing completed",
            total_processed=processed_count,
            successful_results=len(results),
        )

        return results


class ProgressTracker:
    """Track and report progress of long-running operations."""

    def __init__(self, total: int, update_interval: int = 10):
        """Initialize progress tracker.

        Args:
            total: Total number of items
            update_interval: Update progress every N items

        """
        self.total = total
        self.processed = 0
        self.update_interval = update_interval
        self.last_update = 0

    def update(self, processed: int) -> dict[str, Any] | None:
        """Update progress.

        Args:
            processed: Number of processed items

        Returns:
            Progress info dict if update interval reached, None otherwise

        """
        self.processed = processed

        # Only return progress if interval reached
        if (
            processed - self.last_update >= self.update_interval
            or processed == self.total
        ):
            self.last_update = processed

            percent = (processed / self.total * 100) if self.total > 0 else 0
            remaining = self.total - processed

            return {
                "processed": processed,
                "total": self.total,
                "percent": round(percent, 1),
                "remaining": remaining,
            }

        return None

    def format_progress(self, processed: int | None = None) -> str:
        """Format progress as string.

        Args:
            processed: Number of processed items (uses current if None)

        Returns:
            Formatted progress string

        """
        if processed is not None:
            self.processed = processed

        percent = (self.processed / self.total * 100) if self.total > 0 else 0

        return (
            f"🔄 Прогресс: {self.processed}/{self.total} ({percent:.1f}%)\n"
            f"📊 Осталось: {self.total - self.processed} предметов"
        )


async def chunked_api_calls(
    items: list[T],
    api_call_fn: Callable[[list[T]], Any],
    chunk_size: int = 50,
    delay: float = 0.5,
) -> list[R]:
    """Make chunked API calls to avoid rate limiting.

    Args:
        items: Items to process via API
        api_call_fn: Async function that makes API call
        chunk_size: Number of items per API call
        delay: Delay between calls in seconds

    Returns:
        Aggregated results from all API calls

    """
    results: list[R] = []
    total_chunks = (len(items) + chunk_size - 1) // chunk_size

    for i in range(0, len(items), chunk_size):
        chunk = items[i : i + chunk_size]
        chunk_num = (i // chunk_size) + 1

        logger.debug(
            f"API call {chunk_num}/{total_chunks}",
            chunk_size=len(chunk),
        )

        try:
            chunk_results = await api_call_fn(chunk)

            if chunk_results:
                if isinstance(chunk_results, list):
                    results.extend(chunk_results)
                else:
                    results.append(chunk_results)

        except Exception as e:
            logger.exception(
                f"API call failed for chunk {chunk_num}",
                error=str(e),
            )
            raise

        # Delay between calls
        if i + chunk_size < len(items):
            await asyncio.sleep(delay)

    return results
