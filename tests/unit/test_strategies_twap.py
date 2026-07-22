"""Tests for strategies — TWAP executor."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from src.strategies.twap import TWAPExecutor


class TestTWAPExecutor:

    def test_init(self):
        client = AsyncMock()
        twap = TWAPExecutor(client=client, max_slices=5, min_interval_seconds=30.0, max_slippage_pct=5.0)
        assert twap.max_slices == 5
        assert twap.min_interval_seconds == 30.0
        assert twap.max_slippage_pct == 5.0

    def test_create_schedule(self):
        client = AsyncMock()
        twap = TWAPExecutor(client=client, max_slices=5, min_interval_seconds=1.0)
        schedule = twap.create_schedule(
            total_qty=10,
            time_horizon=timedelta(minutes=5),
        )
        assert len(schedule) >= 1
        assert len(schedule) <= 5

    def test_create_schedule_respects_max_slices(self):
        client = AsyncMock()
        twap = TWAPExecutor(client=client, max_slices=2, min_interval_seconds=1.0)
        schedule = twap.create_schedule(
            total_qty=100,
            time_horizon=timedelta(minutes=10),
        )
        assert len(schedule) <= 2
