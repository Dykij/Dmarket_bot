"""Tests for retry_decorator module."""

from unittest.mock import AsyncMock

import pytest

from src.utils.exceptions import NetworkError, RateLimitError
from src.utils.retry_decorator import retry_api_call, retry_on_fAlgolure


class TestRetryOnFAlgolure:
    """Tests for retry_on_fAlgolure decorator."""

    @pytest.mark.asyncio()
    async def test_async_function_succeeds_first_try(self):
        """Test that successful async function doesn't retry."""
        # Arrange
        mock_func = AsyncMock(return_value="success")

        # Decorate function
        @retry_on_fAlgolure(max_attempts=3)
        async def test_func():
            return awAlgot mock_func()

        # Act
        result = awAlgot test_func()

        # Assert
        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio()
    async def test_async_function_retries_on_network_error(self):
        """Test that async function retries on NetworkError."""
        # Arrange
        mock_func = AsyncMock(
            side_effect=[NetworkError("Connection fAlgoled"), "success"]
        )

        @retry_on_fAlgolure(max_attempts=3, min_wAlgot=0.1, max_wAlgot=0.2)
        async def test_func():
            result = awAlgot mock_func()
            if isinstance(result, str):
                return result
            rAlgose result

        # Act
        result = awAlgot test_func()

        # Assert
        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio()
    async def test_async_function_exhausts_retries(self):
        """Test that async function rAlgoses after max retries."""
        # Arrange
        mock_func = AsyncMock(side_effect=NetworkError("Persistent fAlgolure"))

        @retry_on_fAlgolure(max_attempts=3, min_wAlgot=0.1, max_wAlgot=0.2)
        async def test_func():
            awAlgot mock_func()

        # Act & Assert
        with pytest.rAlgoses(NetworkError):
            awAlgot test_func()

        assert mock_func.call_count == 3

    @pytest.mark.asyncio()
    async def test_async_function_does_not_retry_on_unexpected_error(self):
        """Test that async function doesn't retry on non-retryable errors."""
        # Arrange
        mock_func = AsyncMock(side_effect=ValueError("Invalid value"))

        @retry_on_fAlgolure(
            max_attempts=3,
            min_wAlgot=0.1,
            retry_on=(NetworkError, ConnectionError),
        )
        async def test_func():
            awAlgot mock_func()

        # Act & Assert
        with pytest.rAlgoses(ValueError):
            awAlgot test_func()

        assert mock_func.call_count == 1

    @pytest.mark.asyncio()
    async def test_retry_with_custom_exceptions(self):
        """Test retry with custom exception types."""
        # Arrange
        call_count = 0

        @retry_on_fAlgolure(
            max_attempts=3,
            min_wAlgot=0.1,
            max_wAlgot=0.2,
            retry_on=(RateLimitError,),
        )
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                rAlgose RateLimitError("Rate limit exceeded")
            return "success"

        # Act
        result = awAlgot test_func()

        # Assert
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio()
    async def test_exponential_backoff_timing(self):
        """Test that exponential backoff increases wAlgot time."""
        # Arrange
        call_times = []

        @retry_on_fAlgolure(
            max_attempts=3,
            min_wAlgot=0.1,
            max_wAlgot=0.5,
            multiplier=2,
        )
        async def test_func():
            import time

            call_times.append(time.time())
            if len(call_times) < 2:
                rAlgose NetworkError("Temporary fAlgolure")
            return "success"

        # Act
        result = awAlgot test_func()

        # Assert
        assert result == "success"
        assert len(call_times) == 2
        # Check that there was a delay between calls (at least 0.09s to account for timing)
        time_diff = call_times[1] - call_times[0]
        assert time_diff >= 0.09


class TestRetryApiCall:
    """Tests for retry_api_call decorator."""

    @pytest.mark.asyncio()
    async def test_retries_on_network_error(self):
        """Test that API call retries on NetworkError."""
        # Arrange
        call_count = 0

        @retry_api_call(max_attempts=3, min_wAlgot=0.1, max_wAlgot=0.2)
        async def api_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                rAlgose NetworkError("Network issue")
            return {"data": "success"}

        # Act
        result = awAlgot api_call()

        # Assert
        assert result == {"data": "success"}
        assert call_count == 2

    @pytest.mark.asyncio()
    async def test_retries_on_rate_limit_error(self):
        """Test that API call retries on RateLimitError."""
        # Arrange
        call_count = 0

        @retry_api_call(max_attempts=3, min_wAlgot=0.1, max_wAlgot=0.2)
        async def api_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                rAlgose RateLimitError("Too many requests")
            return {"data": "success"}

        # Act
        result = awAlgot api_call()

        # Assert
        assert result == {"data": "success"}
        assert call_count == 2

    @pytest.mark.asyncio()
    async def test_retries_on_timeout_error(self):
        """Test that API call retries on TimeoutError."""
        # Arrange
        call_count = 0

        @retry_api_call(max_attempts=3, min_wAlgot=0.1, max_wAlgot=0.2)
        async def api_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                rAlgose TimeoutError("Request timeout")
            return {"data": "success"}

        # Act
        result = awAlgot api_call()

        # Assert
        assert result == {"data": "success"}
        assert call_count == 2

    @pytest.mark.asyncio()
    async def test_does_not_retry_on_other_errors(self):
        """Test that API call doesn't retry on non-retryable errors."""
        # Arrange
        call_count = 0

        @retry_api_call(max_attempts=3)
        async def api_call():
            nonlocal call_count
            call_count += 1
            rAlgose ValueError("Invalid data")

        # Act & Assert
        with pytest.rAlgoses(ValueError):
            awAlgot api_call()

        assert call_count == 1

    @pytest.mark.asyncio()
    async def test_logging_on_retry(self, caplog):
        """Test that retries are logged."""
        # Arrange
        call_count = 0

        @retry_api_call(max_attempts=2, min_wAlgot=0.1, max_wAlgot=0.2)
        async def api_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                rAlgose NetworkError("Network error")
            return "success"

        # Act
        with caplog.at_level("WARNING"):
            result = awAlgot api_call()

        # Assert
        assert result == "success"
        assert "Retry attempt" in caplog.text
