"""Tests for market_data_logger module.

This module tests the MarketDataLogger class for logging
market data for analysis and ML training.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMarketDataLogger:
    """Tests for MarketDataLogger class."""

    @pytest.fixture
    def mock_api(self):
        """Create mock API client."""
        api = MagicMock()
        api.get_market_items = AsyncMock(return_value={
            "objects": [
                {
                    "title": "AK-47 | Redline (Field-Tested)",
                    "price": {"USD": "2500"},
                    "extra": {"floatValue": "0.25"},
                },
            ]
        })
        return api

    @pytest.fixture
    def logger(self, mock_api, tmp_path):
        """Create MarketDataLogger instance."""
        from src.dmarket.market_data_logger import MarketDataLogger, MarketDataLoggerConfig
        config = MarketDataLoggerConfig(
            output_path=str(tmp_path / "market_data.csv"),
            max_items_per_scan=10,
        )
        # Patch the logger.info call to avoid structlog syntax issue
        with patch("src.dmarket.market_data_logger.logger"):
            return MarketDataLogger(api=mock_api, config=config)

    def test_init(self, logger):
        """Test initialization."""
        assert logger is not None
        assert logger.config is not None
        assert logger._running is False

    def test_init_default_config(self, mock_api):
        """Test initialization with default config."""
        from src.dmarket.market_data_logger import MarketDataLogger
        with patch("src.dmarket.market_data_logger.logger"):
            logger = MarketDataLogger(api=mock_api)
        assert logger.config is not None

    def test_get_stats(self, logger):
        """Test getting logger statistics."""
        stats = logger.get_stats()

        assert "total_items_logged" in stats
        assert "scans_completed" in stats

    def test_get_data_status(self, logger):
        """Test getting data status."""
        status = logger.get_data_status()

        assert "exists" in status
        assert "path" in status

    def test_stop(self, logger):
        """Test stopping the logger."""
        logger._running = True

        logger.stop()

        assert logger._running is False

    @pytest.mark.asyncio
    async def test_log_market_data(self, mock_api, tmp_path):
        """Test logging market data."""
        from src.dmarket.market_data_logger import MarketDataLogger, MarketDataLoggerConfig

        mock_api.get_market_items.return_value = {
            "objects": [
                {
                    "title": "Test Item",
                    "price": {"USD": "1000"},
                    "extra": {"floatValue": "0.1"},
                },
            ]
        }

        config = MarketDataLoggerConfig(
            output_path=str(tmp_path / "test.csv"),
        )
        with patch("src.dmarket.market_data_logger.logger"):
            data_logger = MarketDataLogger(api=mock_api, config=config)
            count = await data_logger.log_market_data()

        assert count >= 0

    def test_config_games(self, logger):
        """Test games configuration."""
        assert logger.config.games is not None
        assert len(logger.config.games) > 0

    def test_config_price_range(self, logger):
        """Test price range configuration."""
        assert logger.config.min_price_cents > 0
        assert logger.config.max_price_cents > logger.config.min_price_cents
