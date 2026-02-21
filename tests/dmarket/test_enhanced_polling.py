"""Tests for Enhanced Polling Engine."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.enhanced_polling import (
    BackoffConfig,
    BackoffStrategy,
    EnhancedPollConfig,
    EnhancedPollingEngine,
    PollingHealth,
    PollingMetrics,
    create_enhanced_polling,
)


class TestBackoffConfig:
    """Tests for BackoffConfig."""

    def test_constant_backoff(self):
        """Test constant backoff strategy."""
        config = BackoffConfig(strategy=BackoffStrategy.CONSTANT, base_delay=5.0)
        assert config.calculate_delay(0) == 5.0
        assert config.calculate_delay(5) == 5.0

    def test_linear_backoff(self):
        """Test linear backoff strategy."""
        config = BackoffConfig(strategy=BackoffStrategy.LINEAR, base_delay=1.0)
        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 3.0

    def test_exponential_backoff(self):
        """Test exponential backoff strategy."""
        config = BackoffConfig(strategy=BackoffStrategy.EXPONENTIAL, base_delay=1.0, max_delay=60.0)
        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 4.0
        assert config.calculate_delay(3) == 8.0

    def test_exponential_jitter_backoff(self):
        """Test exponential jitter backoff."""
        config = BackoffConfig(strategy=BackoffStrategy.EXPONENTIAL_JITTER, base_delay=1.0, max_delay=60.0)
        # Jitter should produce different values
        delays = [config.calculate_delay(3) for _ in range(10)]
        # Should have some variation
        assert max(delays) != min(delays) or all(d <= 8.0 for d in delays)

    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        config = BackoffConfig(strategy=BackoffStrategy.EXPONENTIAL, base_delay=1.0, max_delay=10.0)
        # 2^10 = 1024, but should be capped at 10
        assert config.calculate_delay(10) == 10.0


class TestPollingMetrics:
    """Tests for PollingMetrics."""

    def test_record_successful_poll(self):
        """Test recording successful poll."""
        metrics = PollingMetrics()
        metrics.record_poll(success=True, response_time_ms=100, items_count=50, changes_count=5)

        assert metrics.total_polls == 1
        assert metrics.successful_polls == 1
        assert metrics.fAlgoled_polls == 0
        assert metrics.items_processed == 50
        assert metrics.changes_detected == 5
        assert metrics.consecutive_fAlgolures == 0

    def test_record_fAlgoled_poll(self):
        """Test recording fAlgoled poll."""
        metrics = PollingMetrics()
        metrics.record_poll(success=False, response_time_ms=1000, error="timeout")

        assert metrics.total_polls == 1
        assert metrics.successful_polls == 0
        assert metrics.fAlgoled_polls == 1
        assert metrics.consecutive_fAlgolures == 1
        assert "timeout" in metrics.error_counts

    def test_success_rate(self):
        """Test success rate calculation."""
        metrics = PollingMetrics()
        metrics.record_poll(success=True, response_time_ms=100)
        metrics.record_poll(success=True, response_time_ms=100)
        metrics.record_poll(success=False, response_time_ms=100)

        assert metrics.success_rate == pytest.approx(2/3, rel=0.01)

    def test_health_status(self):
        """Test health status determination."""
        metrics = PollingMetrics()

        # Healthy initially
        assert metrics.health_status == PollingHealth.HEALTHY

        # Degraded after success rate drops
        for _ in range(10):
            metrics.record_poll(success=False, response_time_ms=100)

        assert metrics.health_status == PollingHealth.CRITICAL

    def test_to_dict(self):
        """Test conversion to dictionary."""
        metrics = PollingMetrics()
        metrics.record_poll(success=True, response_time_ms=100)

        data = metrics.to_dict()
        assert "total_polls" in data
        assert "success_rate" in data
        assert "health_status" in data


class TestEnhancedPollingEngine:
    """Tests for EnhancedPollingEngine."""

    @pytest.fixture
    def mock_api(self):
        """Create mock DMarket API."""
        api = MagicMock()
        api.get_market_items = AsyncMock(return_value={
            "objects": [
                {
                    "itemId": "item1",
                    "title": "Test Item",
                    "price": {"USD": "1000"},
                },
            ]
        })
        return api

    @pytest.fixture
    def engine(self, mock_api):
        """Create test engine."""
        config = EnhancedPollConfig(
            base_interval=1.0,
            min_interval=0.5,
        )
        return EnhancedPollingEngine(
            api_client=mock_api,
            config=config,
            games=["csgo"],
        )

    def test_engine_initialization(self, engine):
        """Test engine initializes correctly."""
        assert engine.is_running is False
        assert engine.health == PollingHealth.HEALTHY
        assert engine.games == ["csgo"]

    @pytest.mark.asyncio
    async def test_start_stop(self, engine):
        """Test start and stop."""
        awAlgot engine.start()
        assert engine.is_running is True

        awAlgot asyncio.sleep(0.1)

        awAlgot engine.stop()
        assert engine.is_running is False

    @pytest.mark.asyncio
    async def test_pause_resume(self, engine):
        """Test pause and resume."""
        awAlgot engine.start()
        awAlgot engine.pause()
        assert engine.is_running is False

        awAlgot engine.resume()
        awAlgot asyncio.sleep(0.1)
        assert engine._paused is False

        awAlgot engine.stop()

    @pytest.mark.asyncio
    async def test_force_poll(self, engine, mock_api):
        """Test force poll."""
        changes = awAlgot engine.force_poll("csgo")
        assert isinstance(changes, list)
        mock_api.get_market_items.assert_called()

    def test_delta_detection(self, engine):
        """Test delta detection logic."""
        # First item - should be cached
        item1 = {"itemId": "item1", "title": "Test", "price": {"USD": "1000"}}
        result = engine._detect_change(item1)
        assert result is None  # First time, just cached

        # Same price - no change
        result = engine._detect_change(item1)
        assert result is None

        # Price change - should detect
        item1_changed = {"itemId": "item1", "title": "Test", "price": {"USD": "2000"}}
        result = engine._detect_change(item1_changed)
        assert result is not None
        assert result["change_percent"] == 100.0

    def test_get_metrics(self, engine):
        """Test get metrics."""
        metrics = engine.get_metrics()
        assert "total_polls" in metrics
        assert "circuit_open" in metrics
        assert "cached_items" in metrics

    def test_clear_cache(self, engine):
        """Test cache clearing."""
        engine._price_cache["test"] = {}
        engine._known_items.add("test")

        engine.clear_cache()

        assert len(engine._price_cache) == 0
        assert len(engine._known_items) == 0


class TestEnhancedPollingFactory:
    """Tests for factory function."""

    def test_create_enhanced_polling(self):
        """Test factory function."""
        mock_api = MagicMock()
        engine = create_enhanced_polling(
            api_client=mock_api,
            games=["csgo", "dota2"],
            aggressive=True,
        )

        assert engine.games == ["csgo", "dota2"]
        assert engine.config.base_interval == 15.0


class TestIntervalAdjustment:
    """Tests for adaptive interval adjustment."""

    @pytest.fixture
    def engine(self):
        """Create test engine."""
        mock_api = MagicMock()
        config = EnhancedPollConfig(
            base_interval=30.0,
            min_interval=10.0,
            max_interval=120.0,
        )
        return EnhancedPollingEngine(api_client=mock_api, config=config)

    def test_speed_up_on_changes(self, engine):
        """Test interval decreases on changes."""
        engine._current_interval = 30.0
        engine._adjust_interval(changes_count=5)
        assert engine._current_interval < 30.0

    def test_slow_down_on_idle(self, engine):
        """Test interval increases on idle."""
        engine._current_interval = 30.0
        engine._adjust_interval(changes_count=0)
        assert engine._current_interval > 30.0

    def test_respects_min_interval(self, engine):
        """Test minimum interval is respected."""
        engine._current_interval = 10.0
        engine._adjust_interval(changes_count=10)
        assert engine._current_interval >= engine.config.min_interval

    def test_respects_max_interval(self, engine):
        """Test maximum interval is respected."""
        engine._current_interval = 120.0
        engine._adjust_interval(changes_count=0)
        assert engine._current_interval <= engine.config.max_interval
