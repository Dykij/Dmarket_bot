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
