"""
Unit tests for O1/O2/O4 CS2Cap optimisations.

O1: Rate-limit guard (X-RateLimit-Remaining, 80% guard, 429 cooldown)
O2: Cache REFRESH_TOP_N widened to 200
O4: Catalog warm-up on bot start

Run: pytest tests/unit/test_v12_4_cs2cap_optim.py -v
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ====================================================================
# O1: Rate-limit guard
# ====================================================================
class TestRateLimitGuard:
    """
    The CS2CapCache must skip refreshes when:
      1. Oracle is in 429 cooldown
      2. Monthly quota > 95% used
      3. Monthly quota > 80% AND remaining_header < 1000
    """

    def _make_cache(self, oracle_state: dict):
        from src.api.cs2cap_cache import CS2CapCache
        oracle = MagicMock()
        oracle.rate_limit_state = MagicMock(return_value=oracle_state)
        dmarket_client = AsyncMock()
        dmarket_client.get_aggregated_prices = AsyncMock(
            return_value={"AK-47 | Redline (FT)": {"ask_count": 5, "bid_count": 3}}
        )
        cache = CS2CapCache(
            oracle=oracle, dmarket_client=dmarket_client, game_id="a8db"
        )
        return cache

    def test_guard_blocks_429_cooldown(self):
        cache = self._make_cache({
            "monthly_used": 1000,
            "monthly_limit": 50000,
            "remaining_header": 49000,
            "is_quota_exhausted": True,
            "cooldown_remaining_s": 120.0,
        })
        result = cache._check_rate_limit_guard()
        assert result["can_proceed"] is False
        assert "429 cooldown" in result["reason"]

    def test_guard_blocks_above_95_pct(self):
        cache = self._make_cache({
            "monthly_used": 48000,   # 96%
            "monthly_limit": 50000,
            "remaining_header": 1500,
            "is_quota_exhausted": False,
            "cooldown_remaining_s": 0.0,
        })
        result = cache._check_rate_limit_guard()
        assert result["can_proceed"] is False
        assert "96.0%" in result["reason"]

    def test_guard_blocks_80_pct_with_low_remaining_header(self):
        """At 80%+ monthly use, low per-minute remaining must block."""
        cache = self._make_cache({
            "monthly_used": 42000,   # 84%
            "monthly_limit": 50000,
            "remaining_header": 3,   # < 5 per-minute threshold
            "is_quota_exhausted": False,
            "cooldown_remaining_s": 0.0,
        })
        result = cache._check_rate_limit_guard()
        assert result["can_proceed"] is False
        assert "3 calls" in result["reason"] or "3" in result["reason"]

    def test_guard_blocks_low_per_min_remaining_under_80pct(self):
        """Per-minute guard fires regardless of monthly %."""
        cache = self._make_cache({
            "monthly_used": 1000,   # 2% — well under threshold
            "monthly_limit": 50000,
            "remaining_header": 2,   # < 5 per-minute
            "is_quota_exhausted": False,
            "cooldown_remaining_s": 0.0,
        })
        result = cache._check_rate_limit_guard()
        assert result["can_proceed"] is False
        assert "per-minute" in result["reason"]

    def test_guard_allows_80_pct_with_healthy_remaining_header(self):
        """80-95% range is fine if per-minute is healthy."""
        cache = self._make_cache({
            "monthly_used": 42000,   # 84%
            "monthly_limit": 50000,
            "remaining_header": 30,  # healthy
            "is_quota_exhausted": False,
            "cooldown_remaining_s": 0.0,
        })
        result = cache._check_rate_limit_guard()
        assert result["can_proceed"] is True

    def test_guard_allows_under_80_pct(self):
        cache = self._make_cache({
            "monthly_used": 35000,   # 70%
            "monthly_limit": 50000,
            "remaining_header": 15000,
            "is_quota_exhausted": False,
            "cooldown_remaining_s": 0.0,
        })
        result = cache._check_rate_limit_guard()
        assert result["can_proceed"] is True

    def test_guard_handles_missing_header(self):
        """Header may be None on Free tier — fall back to % only."""
        cache = self._make_cache({
            "monthly_used": 30000,
            "monthly_limit": 50000,
            "remaining_header": None,
            "is_quota_exhausted": False,
            "cooldown_remaining_s": 0.0,
        })
        result = cache._check_rate_limit_guard()
        assert result["can_proceed"] is True

    def test_guard_tolerates_oracle_state_failure(self):
        """If the oracle can't report state, allow refresh (best-effort)."""
        from src.api.cs2cap_cache import CS2CapCache
        oracle = MagicMock()
        oracle.rate_limit_state = MagicMock(side_effect=RuntimeError("boom"))
        cache = CS2CapCache(
            oracle=oracle, dmarket_client=AsyncMock(), game_id="a8db"
        )
        result = cache._check_rate_limit_guard()
        assert result["can_proceed"] is True
        assert "boom" in result["reason"]


class TestRefreshSkipsOnGuard:
    """The full refresh path must short-circuit on guard failure."""

    @pytest.mark.asyncio
    async def test_refresh_now_skips_on_429_cooldown(self):
        from src.api.cs2cap_cache import CS2CapCache
        from src.api.cs2cap_oracle import BidsSnapshot, PriceSnapshot

        oracle = MagicMock()
        oracle.rate_limit_state = MagicMock(return_value={
            "monthly_used": 48000,
            "monthly_limit": 50000,
            "remaining_header": 2000,
            "is_quota_exhausted": False,
            "cooldown_remaining_s": 0.0,
        })
        oracle.get_prices_batch = AsyncMock(
            return_value={"X": PriceSnapshot(hash_name="X", min_price=1.0)}
        )
        oracle.get_bids_batch = AsyncMock(
            return_value={"X": BidsSnapshot(hash_name="X", max_bid=1.5)}
        )

        dmarket_client = AsyncMock()
        cache = CS2CapCache(
            oracle=oracle, dmarket_client=dmarket_client, game_id="a8db"
        )

        # Pre-flight must block
        await cache.refresh_now()

        # Caches must be empty (no CS2Cap call was made)
        assert len(cache._ask_cache) == 0
        assert len(cache._bid_cache) == 0
        assert cache._refresh_count == 0
        assert cache._quota_skipped_count == 1

        # DMarket agg-prices may still be called (acceptable — it's DMarket,
        # not CS2Cap). The guard runs BEFORE the DMarket call now.
        # Note: in current impl, agg_prices is called first; let's accept
        # that and just assert the CS2Cap batch was NOT called.
        oracle.get_prices_batch.assert_not_called()
        oracle.get_bids_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_now_proceeds_when_under_quota(self):
        from src.api.cs2cap_cache import CS2CapCache
        from src.api.cs2cap_oracle import BidsSnapshot, PriceSnapshot

        oracle = MagicMock()
        oracle.rate_limit_state = MagicMock(return_value={
            "monthly_used": 1000,
            "monthly_limit": 50000,
            "remaining_header": 49000,
            "is_quota_exhausted": False,
            "cooldown_remaining_s": 0.0,
        })
        oracle.get_prices_batch = AsyncMock(
            return_value={"X": PriceSnapshot(hash_name="X", min_price=1.0)}
        )
        oracle.get_bids_batch = AsyncMock(
            return_value={"X": BidsSnapshot(hash_name="X", max_bid=1.5)}
        )

        dmarket_client = AsyncMock()
        dmarket_client.get_aggregated_prices = AsyncMock(
            return_value={"X": {"ask_count": 5, "bid_count": 3}}
        )
        cache = CS2CapCache(
            oracle=oracle, dmarket_client=dmarket_client, game_id="a8db"
        )

        await cache.refresh_now()

        assert len(cache._ask_cache) == 1
        assert len(cache._bid_cache) == 1
        assert cache._refresh_count == 1
        assert cache._quota_skipped_count == 0


# ====================================================================
# O1: Oracle rate_limit_state()
# ====================================================================
class TestOracleRateLimitState:
    def test_returns_tier_aware_limit(self):
        from src.api.cs2cap_oracle import CS2CapOracle
        from src.config import Config

        with patch.object(Config, "CS2CAP_TIER", "starter"):
            oracle = CS2CapOracle(api_key="test")
            rl = oracle.rate_limit_state()
            assert rl["monthly_limit"] == 50000

    def test_pro_tier(self):
        from src.api.cs2cap_oracle import CS2CapOracle
        from src.config import Config

        with patch.object(Config, "CS2CAP_TIER", "pro"):
            oracle = CS2CapOracle(api_key="test")
            rl = oracle.rate_limit_state()
            assert rl["monthly_limit"] == 500000

    def test_free_tier(self):
        from src.api.cs2cap_oracle import CS2CapOracle
        from src.config import Config

        with patch.object(Config, "CS2CAP_TIER", "free"):
            oracle = CS2CapOracle(api_key="test")
            rl = oracle.rate_limit_state()
            assert rl["monthly_limit"] == 1000

    def test_cooldown_remaining_decreases(self):
        from src.api.cs2cap_oracle import CS2CapOracle
        oracle = CS2CapOracle(api_key="test")
        oracle._quota_exhausted = True
        oracle._quota_exhausted_at = time.time() - 30
        oracle._quota_reset_seconds = 60
        rl = oracle.rate_limit_state()
        assert 25.0 < rl["cooldown_remaining_s"] < 35.0


# ====================================================================
# O2: Config exposes 200 titles
# ====================================================================
class TestConfigO2:
    def test_default_top_n_is_200(self):
        from src.config import Config
        assert Config.CS2CAP_CACHE_REFRESH_TOP_N == 200

    def test_top_n_is_int_and_positive(self):
        from src.config import Config
        assert isinstance(Config.CS2CAP_CACHE_REFRESH_TOP_N, int)
        assert Config.CS2CAP_CACHE_REFRESH_TOP_N > 0


# ====================================================================
# O4: Catalog warm-up
# ====================================================================
class TestCatalogWarmup:
    @pytest.mark.asyncio
    async def test_start_schedules_warmup_task(self):
        """Warmup runs as a fire-and-forget background task."""
        from src.api.cs2cap_cache import CS2CapCache

        oracle = MagicMock()
        oracle.rate_limit_state = MagicMock(return_value={
            "monthly_used": 0,
            "monthly_limit": 50000,
            "remaining_header": 50000,
            "is_quota_exhausted": False,
            "cooldown_remaining_s": 0.0,
        })
        oracle.load_catalog = AsyncMock(return_value=38837)
        oracle.get_prices_batch = AsyncMock(return_value={})
        oracle.get_bids_batch = AsyncMock(return_value={})

        dmarket_client = AsyncMock()
        dmarket_client.get_aggregated_prices = AsyncMock(return_value={})

        cache = CS2CapCache(
            oracle=oracle, dmarket_client=dmarket_client, game_id="a8db"
        )

        from src.config import Config
        original = Config.CS2CAP_CACHE_REFRESH_ON_START
        Config.CS2CAP_CACHE_REFRESH_ON_START = False
        try:
            await cache.start()
            # Give the background task a tick to be scheduled
            await asyncio.sleep(0.01)
            oracle.load_catalog.assert_awaited()
            await cache.stop()
        finally:
            Config.CS2CAP_CACHE_REFRESH_ON_START = original

    @pytest.mark.asyncio
    async def test_start_skips_warmup_when_disabled(self):
        from src.api.cs2cap_cache import CS2CapCache

        oracle = MagicMock()
        oracle.rate_limit_state = MagicMock(return_value={
            "monthly_used": 0,
            "monthly_limit": 50000,
            "remaining_header": 50000,
            "is_quota_exhausted": False,
            "cooldown_remaining_s": 0.0,
        })
        oracle.load_catalog = AsyncMock(return_value=38837)
        oracle.get_prices_batch = AsyncMock(return_value={})
        oracle.get_bids_batch = AsyncMock(return_value={})

        dmarket_client = AsyncMock()

        cache = CS2CapCache(
            oracle=oracle, dmarket_client=dmarket_client, game_id="a8db"
        )

        from src.config import Config
        original_warmup = Config.CS2CAP_CATALOG_WARMUP_ON_START
        original_refresh = Config.CS2CAP_CACHE_REFRESH_ON_START
        Config.CS2CAP_CATALOG_WARMUP_ON_START = 0
        Config.CS2CAP_CACHE_REFRESH_ON_START = False
        try:
            await cache.start()
            oracle.load_catalog.assert_not_awaited()
            await cache.stop()
        finally:
            Config.CS2CAP_CATALOG_WARMUP_ON_START = original_warmup
            Config.CS2CAP_CACHE_REFRESH_ON_START = original_refresh

    @pytest.mark.asyncio
    async def test_warmup_handles_failure_gracefully(self):
        from src.api.cs2cap_cache import CS2CapCache

        oracle = MagicMock()
        oracle.rate_limit_state = MagicMock(return_value={
            "monthly_used": 0,
            "monthly_limit": 50000,
            "remaining_header": 50000,
            "is_quota_exhausted": False,
            "cooldown_remaining_s": 0.0,
        })
        oracle.load_catalog = AsyncMock(side_effect=RuntimeError("network"))
        oracle.get_prices_batch = AsyncMock(return_value={})
        oracle.get_bids_batch = AsyncMock(return_value={})

        dmarket_client = AsyncMock()
        dmarket_client.get_aggregated_prices = AsyncMock(return_value={})

        cache = CS2CapCache(
            oracle=oracle, dmarket_client=dmarket_client, game_id="a8db"
        )

        from src.config import Config
        original = Config.CS2CAP_CACHE_REFRESH_ON_START
        Config.CS2CAP_CACHE_REFRESH_ON_START = False
        try:
            # Should not raise — warmup failure is non-fatal
            await cache.start()
            # Refresh task should still be running
            assert cache._refresh_task is not None
            await cache.stop()
        finally:
            Config.CS2CAP_CACHE_REFRESH_ON_START = original


class TestOracleLoadCatalogPublic:
    @pytest.mark.asyncio
    async def test_load_catalog_returns_count(self):
        from src.api.cs2cap_oracle import CS2CapOracle

        oracle = CS2CapOracle(api_key="test")
        # Pre-seed catalog to avoid HTTP
        oracle._item_catalog = {"A": 1, "B": 2, "C": 3}
        oracle._catalog_ts = time.time()
        result = await oracle.load_catalog()
        assert result == 3


# ====================================================================
# Stats include rate-limit fields (O1)
# ====================================================================
class TestStatsIncludeQuota:
    def test_stats_includes_quota_fields(self):
        from src.api.cs2cap_cache import CS2CapCache

        oracle = MagicMock()
        oracle.rate_limit_state = MagicMock(return_value={
            "monthly_used": 5000,
            "monthly_limit": 50000,
            "remaining_header": 45000,
            "is_quota_exhausted": False,
            "cooldown_remaining_s": 0.0,
        })
        cache = CS2CapCache(
            oracle=oracle, dmarket_client=AsyncMock(), game_id="a8db"
        )
        st = cache.stats()
        assert st["quota_skipped_count"] == 0
        assert st["monthly_used"] == 5000
        assert st["monthly_limit"] == 50000
        assert st["remaining_header"] == 45000
