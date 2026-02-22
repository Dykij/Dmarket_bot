"""Unit tests for batch processor module.

This module contains tests for src/utils/batch_processor.py covering:
- Basic batch processing
- Progress callbacks
- Error handling
- Edge cases

Target: 15+ tests to achieve 70%+ coverage
"""

from unittest.mock import AsyncMock

import pytest

from src.utils.batch_processor import SimpleBatchProcessor

# Test fixtures


@pytest.fixture()
def processor():
    """Fixture providing a SimpleBatchProcessor instance."""
    return SimpleBatchProcessor(batch_size=10, delay_between_batches=0.01)


@pytest.fixture()
def small_processor():
    """Fixture providing a processor with small batch size."""
    return SimpleBatchProcessor(batch_size=2, delay_between_batches=0.001)


# TestSimpleBatchProcessorInit


class TestSimpleBatchProcessorInit:
    """Tests for SimpleBatchProcessor initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        # Act
        processor = SimpleBatchProcessor()

        # Assert
        assert processor.batch_size == 100
        assert processor.delay_between_batches == 0.1

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        # Act
        processor = SimpleBatchProcessor(batch_size=50, delay_between_batches=0.5)

        # Assert
        assert processor.batch_size == 50
        assert processor.delay_between_batches == 0.5


# TestProcessInBatches


class TestProcessInBatches:
    """Tests for process_in_batches method."""

    @pytest.mark.asyncio()
    async def test_process_empty_list(self, processor):
        """Test processing empty list."""
        # Arrange
        items = []
        process_fn = AsyncMock(return_value=[])

        # Act
        results = await processor.process_in_batches(items, process_fn)

        # Assert
        assert results == []
        process_fn.assert_not_called()

    @pytest.mark.asyncio()
    async def test_process_single_batch(self, processor):
        """Test processing items that fit in single batch."""
        # Arrange
        items = [1, 2, 3, 4, 5]
        process_fn = AsyncMock(return_value=[10, 20, 30, 40, 50])

        # Act
        results = await processor.process_in_batches(items, process_fn)

        # Assert
        assert results == [10, 20, 30, 40, 50]
        process_fn.assert_called_once_with([1, 2, 3, 4, 5])

    @pytest.mark.asyncio()
    async def test_process_multiple_batches(self, small_processor):
        """Test processing items across multiple batches."""
        # Arrange
        items = [1, 2, 3, 4, 5]
        process_fn = AsyncMock(side_effect=lambda batch: [x * 10 for x in batch])

        # Act
        results = await small_processor.process_in_batches(items, process_fn)

        # Assert
        assert results == [10, 20, 30, 40, 50]
        assert process_fn.call_count == 3  # 2 + 2 + 1

    @pytest.mark.asyncio()
    async def test_process_with_progress_callback(self, small_processor):
        """Test processing with progress callback."""
        # Arrange
        items = [1, 2, 3, 4]
        process_fn = AsyncMock(return_value=[])
        progress_callback = AsyncMock()

        # Act
        await small_processor.process_in_batches(
            items, process_fn, progress_callback=progress_callback
        )

        # Assert
        assert progress_callback.call_count >= 1

    @pytest.mark.asyncio()
    async def test_process_with_error_callback(self, small_processor):
        """Test processing with error callback on failure."""
        # Arrange
        items = [1, 2, 3, 4]
        error = ValueError("Test error")
        process_fn = AsyncMock(side_effect=[error, [30, 40]])
        error_callback = AsyncMock()

        # Act
        await small_processor.process_in_batches(
            items, process_fn, error_callback=error_callback
        )

        # Assert
        error_callback.assert_called_once()
        call_args = error_callback.call_args
        assert isinstance(call_args[0][0], ValueError)

    @pytest.mark.asyncio()
    async def test_process_continues_after_error(self, small_processor):
        """Test that processing continues after batch error."""
        # Arrange
        items = [1, 2, 3, 4]
        error = ValueError("Test error")
        process_fn = AsyncMock(side_effect=[error, [30, 40]])
        error_callback = AsyncMock()

        # Act
        results = await small_processor.process_in_batches(
            items, process_fn, error_callback=error_callback
        )

        # Assert
        assert results == [30, 40]

    @pytest.mark.asyncio()
    async def test_process_with_non_list_result(self, processor):
        """Test processing when process_fn returns non-list."""
        # Arrange
        items = [1, 2, 3]
        process_fn = AsyncMock(return_value={"processed": True})

        # Act
        results = await processor.process_in_batches(items, process_fn)

        # Assert
        assert {"processed": True} in results


# TestBatchProcessorEdgeCases


class TestBatchProcessorEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio()
    async def test_process_exact_batch_size(self):
        """Test processing when items equal batch size."""
        # Arrange
        processor = SimpleBatchProcessor(batch_size=5, delay_between_batches=0.001)
        items = [1, 2, 3, 4, 5]
        process_fn = AsyncMock(return_value=[10, 20, 30, 40, 50])

        # Act
        results = await processor.process_in_batches(items, process_fn)

        # Assert
        assert results == [10, 20, 30, 40, 50]
        process_fn.assert_called_once()

    @pytest.mark.asyncio()
    async def test_process_with_none_result(self, processor):
        """Test processing when process_fn returns None."""
        # Arrange
        items = [1, 2, 3]
        process_fn = AsyncMock(return_value=None)

        # Act
        results = await processor.process_in_batches(items, process_fn)

        # Assert
        assert results == []

    @pytest.mark.asyncio()
    async def test_large_batch_processing(self):
        """Test processing large number of items."""
        # Arrange
        processor = SimpleBatchProcessor(batch_size=100, delay_between_batches=0.001)
        items = list(range(500))
        process_fn = AsyncMock(side_effect=lambda batch: batch)

        # Act
        results = await processor.process_in_batches(items, process_fn)

        # Assert
        assert len(results) == 500
        assert process_fn.call_count == 5

    @pytest.mark.asyncio()
    async def test_process_with_mixed_results(self, small_processor):
        """Test processing with mixed list and non-list results."""
        # Arrange
        items = [1, 2, 3, 4]
        process_fn = AsyncMock(side_effect=[[10, 20], {"status": "ok"}])

        # Act
        results = await small_processor.process_in_batches(items, process_fn)

        # Assert
        assert 10 in results
        assert 20 in results
        assert {"status": "ok"} in results
