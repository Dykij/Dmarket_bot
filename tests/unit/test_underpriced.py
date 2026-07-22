"""Tests for underpriced.py — DMarket underpriced detection."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.target_sniping.underpriced import (
    _percentile,
    fetch_low_fee_titles,
    is_dmarket_underpriced,
)


class TestPercentile:

    def test_empty_list(self):
        assert _percentile([], 0.5) is None

    def test_single_value(self):
        assert _percentile([10.0], 0.5) == 10.0

    def test_median(self):
        assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 0.5) == 3.0

    def test_p0(self):
        assert _percentile([1.0, 2.0, 3.0], 0.0) == 1.0

    def test_p1(self):
        assert _percentile([1.0, 2.0, 3.0], 1.0) == 3.0

    def test_p25(self):
        result = _percentile([1.0, 2.0, 3.0, 4.0], 0.25)
        assert result is not None
        assert 1.0 < result < 2.0

    def test_unsorted_input(self):
        assert _percentile([5.0, 1.0, 3.0], 0.5) == 3.0


class TestIsDmarketUnderpriced:

    @pytest.mark.asyncio
    async def test_disabled_returns_false(self):
        client = AsyncMock()
        with patch("src.core.target_sniping.underpriced.Config") as mock_config:
            mock_config.DMARKET_INTERNAL_UNDERPRICED_ENABLED = False
            result = await is_dmarket_underpriced(client, "a8db", "AK-47", 10.0)
        assert result["underpriced"] is False

    @pytest.mark.asyncio
    async def test_zero_price_returns_false(self):
        client = AsyncMock()
        with patch("src.core.target_sniping.underpriced.Config") as mock_config:
            mock_config.DMARKET_INTERNAL_UNDERPRICED_ENABLED = True
            result = await is_dmarket_underpriced(client, "a8db", "AK-47", 0.0)
        assert result["underpriced"] is False

    @pytest.mark.asyncio
    async def test_empty_title_returns_false(self):
        client = AsyncMock()
        with patch("src.core.target_sniping.underpriced.Config") as mock_config:
            mock_config.DMARKET_INTERNAL_UNDERPRICED_ENABLED = True
            result = await is_dmarket_underpriced(client, "a8db", "", 10.0)
        assert result["underpriced"] is False

    @pytest.mark.asyncio
    async def test_insufficient_history_returns_false(self):
        client = AsyncMock()
        with (
            patch("src.core.target_sniping.underpriced.Config") as mock_config,
            patch("src.db.price_history.price_db") as mock_db,
        ):
            mock_config.DMARKET_INTERNAL_UNDERPRICED_ENABLED = True
            mock_config.DM_UNDERPRICED_SALES_DAYS = 7
            mock_db.get_recent_prices.return_value = [(10.0, 1000)]  # only 1 price
            client.get_last_sales = AsyncMock(return_value=[])  # no fallback
            result = await is_dmarket_underpriced(client, "a8db", "AK-47", 10.0)
        assert result["underpriced"] is False

    @pytest.mark.asyncio
    async def test_underpriced_detected(self):
        client = AsyncMock()
        with (
            patch("src.core.target_sniping.underpriced.Config") as mock_config,
            patch("src.db.price_history.price_db") as mock_db,
        ):
            mock_config.DMARKET_INTERNAL_UNDERPRICED_ENABLED = True
            mock_config.DM_UNDERPRICED_SALES_DAYS = 7
            mock_config.DM_UNDERPRICED_PERCENTILE = 0.5
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.DM_UNDERPRICED_MIN_MARGIN_PCT = 5.0
            # Recent prices: median = 15.0, current = 10.0
            mock_db.get_recent_prices.return_value = [
                (10.0, 1000), (15.0, 1001), (20.0, 1002),
            ]
            result = await is_dmarket_underpriced(client, "a8db", "AK-47", 10.0)
        assert result["underpriced"] is True
        assert result["margin_pct"] > 0

    @pytest.mark.asyncio
    async def test_not_underpriced(self):
        client = AsyncMock()
        with (
            patch("src.core.target_sniping.underpriced.Config") as mock_config,
            patch("src.db.price_history.price_db") as mock_db,
        ):
            mock_config.DMARKET_INTERNAL_UNDERPRICED_ENABLED = True
            mock_config.DM_UNDERPRICED_SALES_DAYS = 7
            mock_config.DM_UNDERPRICED_PERCENTILE = 0.5
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.DM_UNDERPRICED_MIN_MARGIN_PCT = 5.0
            # Recent prices: median = 10.0, current = 10.0 — no edge
            mock_db.get_recent_prices.return_value = [
                (10.0, 1000), (10.0, 1001), (10.0, 1002),
            ]
            result = await is_dmarket_underpriced(client, "a8db", "AK-47", 10.0)
        assert result["underpriced"] is False


class TestFetchLowFeeTitles:

    @pytest.mark.asyncio
    async def test_disabled_returns_empty(self):
        client = AsyncMock()
        with patch("src.core.target_sniping.underpriced.Config") as mock_config:
            mock_config.LOW_FEE_ITEMS_SCAN_ENABLED = False
            result = await fetch_low_fee_titles(client, "a8db")
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_fee_map(self):
        client = AsyncMock()
        client.get_low_fee_items = AsyncMock(return_value=[
            {"title": "AK-47", "fee_rate": 0.02},
            {"title": "M4A4", "fee_rate": 0.03},
        ])
        with patch("src.core.target_sniping.underpriced.Config") as mock_config:
            mock_config.LOW_FEE_ITEMS_SCAN_ENABLED = True
            mock_config.LOW_FEE_ITEMS_SCAN_LIMIT = 100
            result = await fetch_low_fee_titles(client, "a8db")
        assert result["AK-47"] == 0.02
        assert result["M4A4"] == 0.03

    @pytest.mark.asyncio
    async def test_empty_title_skipped(self):
        client = AsyncMock()
        client.get_low_fee_items = AsyncMock(return_value=[
            {"title": "", "fee_rate": 0.02},
            {"title": "AK-47", "fee_rate": 0.03},
        ])
        with patch("src.core.target_sniping.underpriced.Config") as mock_config:
            mock_config.LOW_FEE_ITEMS_SCAN_ENABLED = True
            mock_config.LOW_FEE_ITEMS_SCAN_LIMIT = 100
            result = await fetch_low_fee_titles(client, "a8db")
        assert len(result) == 1
        assert "AK-47" in result
