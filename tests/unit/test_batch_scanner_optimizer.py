"""Tests for batch_scanner_optimizer module.

Tests the optimized batch processing functionality for ArbitrageScanner.
"""

from unittest.mock import AsyncMock

import pytest

from src.dmarket.batch_scanner_optimizer import (
    OPTIMAL_BATCH_SIZE,
    BatchScannerOptimizer,
    optimize_batch_processing,
)


class TestBatchScannerOptimizer:
    """Tests for BatchScannerOptimizer class."""

    def test_initialization_with_default_batch_size(self):
        """Test optimizer initializes with default batch size."""
        # Act
        optimizer = BatchScannerOptimizer()

        # Assert
        assert optimizer.batch_size == OPTIMAL_BATCH_SIZE
        assert optimizer.metrics["total_items"] == 0
        assert optimizer.metrics["batches_processed"] == 0

    def test_initialization_with_custom_batch_size(self):
        """Test optimizer initializes with custom batch size."""
        # Arrange
        custom_size = 100

        # Act
        optimizer = BatchScannerOptimizer(batch_size=custom_size)

        # Assert
        assert optimizer.batch_size == custom_size

    @pytest.mark.asyncio()
    async def test_process_items_batched_with_empty_list(self):
        """Test batch processing returns empty list for empty input."""
        # Arrange
        optimizer = BatchScannerOptimizer()
        process_func = AsyncMock(return_value=[])

        # Act
        results = await optimizer.process_items_batched([], process_func)

        # Assert
        assert results == []
        process_func.assert_not_called()

    @pytest.mark.asyncio()
    async def test_process_items_batched_single_batch(self):
        """Test batch processing with items fitting in single batch."""
        # Arrange
        optimizer = BatchScannerOptimizer(batch_size=100)
        items = [{"id": i} for i in range(50)]
        expected_results = [{"result": i} for i in range(50)]

        async def mock_process(batch):
            return [{"result": item["id"]} for item in batch]

        # Act
        results = await optimizer.process_items_batched(items, mock_process)

        # Assert
        assert len(results) == 50
        assert results == expected_results
        assert optimizer.metrics["batches_processed"] == 1
        assert optimizer.metrics["total_items"] == 50

    @pytest.mark.asyncio()
    async def test_process_items_batched_multiple_batches(self):
        """Test batch processing with multiple batches."""
        # Arrange
        optimizer = BatchScannerOptimizer(batch_size=100)
        items = [{"id": i} for i in range(250)]  # 3 batches

        async def mock_process(batch):
            return [{"result": item["id"]} for item in batch]

        # Act
        results = await optimizer.process_items_batched(items, mock_process)

        # Assert
        assert len(results) == 250
        assert optimizer.metrics["batches_processed"] == 3
        assert optimizer.metrics["total_items"] == 250

    @pytest.mark.asyncio()
    async def test_process_items_batched_handles_errors_gracefully(self):
        """Test batch processing continues after error in one batch."""
        # Arrange
        optimizer = BatchScannerOptimizer(batch_size=10)
        items = [{"id": i} for i in range(25)]

        call_count = 0

        async def mock_process_with_error(batch):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # FAlgol second batch
                raise ValueError("Test error")
            return [{"result": item["id"]} for item in batch]

        # Act
        results = await optimizer.process_items_batched(items, mock_process_with_error)

        # Assert
        assert len(results) == 15  # 25 - 10 (failed batch)
        assert optimizer.metrics["errors"] == 1
        assert optimizer.metrics["batches_processed"] == 3

    @pytest.mark.asyncio()
    async def test_process_games_parallel_success(self):
        """Test parallel game scanning with successful results."""
        # Arrange
        optimizer = BatchScannerOptimizer()
        games = ["csgo", "dota2", "tf2"]

        async def mock_scan(game):
            return [{"game": game, "opp": i} for i in range(5)]

        # Act
        results = await optimizer.process_games_parallel(games, mock_scan)

        # Assert
        assert len(results) == 3
        assert all(game in results for game in games)
        assert len(results["csgo"]) == 5
        assert len(results["dota2"]) == 5
        assert len(results["tf2"]) == 5

    @pytest.mark.asyncio()
    async def test_process_games_parallel_handles_errors(self):
        """Test parallel game scanning handles errors gracefully."""
        # Arrange
        optimizer = BatchScannerOptimizer()
        games = ["csgo", "dota2", "tf2"]

        async def mock_scan_with_error(game):
            if game == "dota2":
                raise ValueError("API Error")
            return [{"game": game, "opp": i} for i in range(5)]

        # Act
        results = await optimizer.process_games_parallel(games, mock_scan_with_error)

        # Assert
        assert len(results) == 3
        assert len(results["csgo"]) == 5
        assert len(results["dota2"]) == 0  # Error handled
        assert len(results["tf2"]) == 5

    def test_get_metrics_returns_correct_stats(self):
        """Test get_metrics returns correct performance statistics."""
        # Arrange
        optimizer = BatchScannerOptimizer()
        optimizer.metrics = {
            "total_items": 1000,
            "total_time": 2.0,
            "batches_processed": 5,
            "errors": 1,
        }

        # Act
        metrics = optimizer.get_metrics()

        # Assert
        assert metrics["total_items"] == 1000
        assert metrics["batches_processed"] == 5
        assert metrics["errors"] == 1
        assert metrics["average_batch_time"] == 0.4  # 2.0 / 5
        assert metrics["throughput_items_per_sec"] == 500.0  # 1000 / 2.0

    def test_get_metrics_handles_zero_division(self):
        """Test get_metrics handles zero batches gracefully."""
        # Arrange
        optimizer = BatchScannerOptimizer()

        # Act
        metrics = optimizer.get_metrics()

        # Assert
        assert metrics["average_batch_time"] == 0
        assert metrics["throughput_items_per_sec"] == 0

    def test_reset_metrics_clears_all_stats(self):
        """Test reset_metrics clears all performance statistics."""
        # Arrange
        optimizer = BatchScannerOptimizer()
        optimizer.metrics = {
            "total_items": 1000,
            "total_time": 2.0,
            "batches_processed": 5,
            "errors": 1,
        }

        # Act
        optimizer.reset_metrics()

        # Assert
        assert optimizer.metrics["total_items"] == 0
        assert optimizer.metrics["total_time"] == 0.0
        assert optimizer.metrics["batches_processed"] == 0
        assert optimizer.metrics["errors"] == 0

    @pytest.mark.asyncio()
    async def test_optimize_batch_processing_convenience_function(self):
        """Test convenience function for quick optimization."""
        # Arrange
        items = [{"id": i} for i in range(100)]

        async def mock_process(batch):
            return [{"result": item["id"]} for item in batch]

        # Act
        results = await optimize_batch_processing(items, mock_process)

        # Assert
        assert len(results) == 100
        assert results[0] == {"result": 0}
        assert results[99] == {"result": 99}

    @pytest.mark.asyncio()
    async def test_batch_size_optimization_with_large_dataset(self):
        """Test batch processing performs well with large datasets."""
        # Arrange
        optimizer = BatchScannerOptimizer(batch_size=500)
        items = [{"id": i} for i in range(10000)]  # 20 batches

        async def mock_process(batch):
            return [{"result": item["id"]} for item in batch]

        # Act
        results = await optimizer.process_items_batched(items, mock_process)

        # Assert
        assert len(results) == 10000
        assert optimizer.metrics["batches_processed"] == 20
        assert optimizer.metrics["total_items"] == 10000
        assert optimizer.metrics["errors"] == 0

        # Verify throughput is logged
        metrics = optimizer.get_metrics()
        assert metrics["throughput_items_per_sec"] > 0


class TestBatchProcessingPerformance:
    """Performance-focused tests for batch processing."""

    @pytest.mark.asyncio()
    async def test_concurrent_batch_processing_limit(self):
        """Test that batches are processed correctly."""
        # Arrange
        optimizer = BatchScannerOptimizer(batch_size=10)
        items = [{"id": i} for i in range(50)]  # 5 batches

        async def mock_process(batch):
            # Return results for each item in batch
            return [{"result": item["id"]} for item in batch]

        # Act
        results = await optimizer.process_items_batched(items, mock_process)

        # Assert
        assert len(results) == 50, f"Expected 50 results, got {len(results)}"
        assert optimizer.metrics["batches_processed"] == 5
        # Verify all IDs are present
        result_ids = sorted([r["result"] for r in results])
        assert result_ids == list(range(50))

    @pytest.mark.asyncio()
    async def test_batch_processing_preserves_order(self):
        """Test that batch processing preserves item order."""
        # Arrange
        optimizer = BatchScannerOptimizer(batch_size=10)
        items = [{"id": i, "value": i * 2} for i in range(50)]

        async def mock_process(batch):
            return [{"id": item["id"], "value": item["value"]} for item in batch]

        # Act
        results = await optimizer.process_items_batched(items, mock_process)

        # Assert
        assert len(results) == 50
        for i, result in enumerate(results):
            assert result["id"] == i
            assert result["value"] == i * 2
