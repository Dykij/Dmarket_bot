"""Unit tests for DMarket-internal underpriced detection helpers."""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DRY_RUN"] = "true"
os.environ.setdefault("ENCRYPTION_KEY", "test-key")

from src.config import Config


class TestUnderpricedHelpers:
    def test_percentile_median(self):
        from src.core.target_sniping.underpriced import _percentile
        assert _percentile([1, 2, 3, 4, 5], 0.5) == 3.0

    def test_percentile_empty(self):
        from src.core.target_sniping.underpriced import _percentile
        assert _percentile([], 0.5) is None

    @pytest.mark.asyncio
    async def test_dmarket_underpriced_disabled(self):
        from src.core.target_sniping.underpriced import is_dmarket_underpriced

        class FakeClient:
            pass

        original = Config.DMARKET_INTERNAL_UNDERPRICED_ENABLED
        Config.DMARKET_INTERNAL_UNDERPRICED_ENABLED = False
        try:
            result = await is_dmarket_underpriced(FakeClient(), "a8db", "Test", 1.0)
            assert result["underpriced"] is False
        finally:
            Config.DMARKET_INTERNAL_UNDERPRICED_ENABLED = original

    @pytest.mark.asyncio
    async def test_dmarket_underpriced_with_history(self):
        from src.core.target_sniping.underpriced import is_dmarket_underpriced
        from src.db.price_history import price_db

        title = "__test_underpriced_item__"
        # Seed price history at $2.00
        for _ in range(5):
            price_db.record_price(title, 2.0, source="test")

        class FakeClient:
            pass

        original_enabled = Config.DMARKET_INTERNAL_UNDERPRICED_ENABLED
        original_margin = Config.DM_UNDERPRICED_MIN_MARGIN_PCT
        Config.DMARKET_INTERNAL_UNDERPRICED_ENABLED = True
        Config.DM_UNDERPRICED_MIN_MARGIN_PCT = 5.0
        try:
            result = await is_dmarket_underpriced(FakeClient(), "a8db", title, 1.50)
            assert result["underpriced"] is True
            assert result["reference_price"] == 2.0
            assert result["margin_pct"] > 0
        finally:
            Config.DMARKET_INTERNAL_UNDERPRICED_ENABLED = original_enabled
            Config.DM_UNDERPRICED_MIN_MARGIN_PCT = original_margin
