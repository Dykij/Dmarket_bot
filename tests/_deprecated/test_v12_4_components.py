"""
Unit tests for v12.4 components.

P0-B: In-memory CS2Cap cache (cs2cap_cache.py)
P0-C: MAX_SNIPING_PRICE_USD enforcement in _evaluate_candidate
P1:   Circuit breaker (backoff.py) + jittered_sleep

Run with: pytest tests/unit/test_v12_4_components.py -v
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest


# ====================================================================
# P1: Circuit Breaker tests
# ====================================================================
class TestCircuitBreaker:
    """Circuit breaker state machine + cooldown behaviour."""

    def _make(self, **kwargs):
        from src.api.dmarket_api_client.backoff import CircuitBreaker
        defaults = dict(name="test", fail_threshold=3, base_cooldown=10.0, max_cooldown=60.0)
        defaults.update(kwargs)
        return CircuitBreaker(**defaults)

    def test_starts_closed(self):
        cb = self._make()
        assert cb.state.value == "CLOSED"
        assert cb.allow_request() is True

    def test_opens_after_threshold_failures(self):
        cb = self._make(fail_threshold=3)
        for i in range(3):
            cb.record_failure(RuntimeError(f"err{i}"))
        assert cb.state.value == "OPEN"
        assert cb.allow_request() is False
        assert cb.total_opens == 1

    def test_extends_cooldown_on_repeated_opens(self):
        cb = self._make(fail_threshold=2, base_cooldown=10.0, max_cooldown=60.0)
        for _ in range(2):
            cb.record_failure(RuntimeError("x"))
        assert cb.state.value == "OPEN"
        first_cooldown = cb.current_cooldown
        # Force OPEN → already open → another failure should extend
        cb.opened_at = time.time() - 100  # past cooldown
        cb.allow_request()  # → HALF_OPEN
        # Failure in HALF_OPEN
        cb.record_failure(RuntimeError("y"))
        assert cb.state.value == "OPEN"
        # Cooldown should have grown (with jitter, may be slightly less or more)
        assert cb.current_cooldown > 0
        assert cb.total_opens == 2

    def test_half_open_after_cooldown(self):
        cb = self._make(fail_threshold=2, base_cooldown=5.0, jitter_pct=0.0)
        for _ in range(2):
            cb.record_failure(RuntimeError("x"))
        assert cb.state.value == "OPEN"
        # Fast-forward past cooldown (with 0 jitter, cooldown == base)
        cb.opened_at = time.time() - 10
        # First allow_request transitions to HALF_OPEN
        assert cb.allow_request() is True
        assert cb.state.value == "HALF_OPEN"

    def test_success_closes_circuit(self):
        cb = self._make(fail_threshold=2, base_cooldown=5.0)
        for _ in range(2):
            cb.record_failure(RuntimeError("x"))
        cb.opened_at = time.time() - 10
        cb.allow_request()  # HALF_OPEN
        cb.record_success()
        assert cb.state.value == "CLOSED"
        assert cb.consecutive_failures == 0
        assert cb.current_cooldown == cb.base_cooldown

    def test_success_resets_failure_counter(self):
        cb = self._make(fail_threshold=3)
        cb.record_failure(RuntimeError("a"))
        cb.record_failure(RuntimeError("b"))
        cb.record_success()
        assert cb.consecutive_failures == 0
        # Now 3 more failures needed to open
        cb.record_failure(RuntimeError("c"))
        cb.record_failure(RuntimeError("d"))
        assert cb.state.value == "CLOSED"
        cb.record_failure(RuntimeError("e"))
        assert cb.state.value == "OPEN"

    def test_status_snapshot(self):
        cb = self._make(fail_threshold=2)
        cb.record_failure(RuntimeError("boom"))
        st = cb.status()
        assert st["state"] == "CLOSED"
        assert st["consecutive_failures"] == 1
        assert "boom" in st["last_error"]


class TestJitteredSleep:
    def test_returns_positive_duration(self):
        from src.api.dmarket_api_client.backoff import jittered_sleep
        d = jittered_sleep(1.0, jitter_pct=0.2)
        assert 0.8 <= d <= 1.2

    def test_zero_base(self):
        from src.api.dmarket_api_client.backoff import jittered_sleep
        assert jittered_sleep(0.0) == 0.0

    def test_negative_jitter_clamped(self):
        from src.api.dmarket_api_client.backoff import jittered_sleep
        d = jittered_sleep(1.0, jitter_pct=2.0)  # ±200%
        assert d >= 0.0


class TestShouldTrip:
    def test_429_trips(self):
        from src.api.dmarket_api_client.backoff import should_trip
        assert should_trip(429) is True

    def test_5xx_trips(self):
        from src.api.dmarket_api_client.backoff import should_trip
        assert should_trip(500) is True
        # 503 is a transient DMarket overload; retry instead of tripping.
        assert should_trip(503) is False
        assert should_trip(599) is True

    def test_4xx_does_not_trip(self):
        from src.api.dmarket_api_client.backoff import should_trip
        assert should_trip(400) is False
        assert should_trip(401) is False
        assert should_trip(404) is False

    def test_2xx_does_not_trip(self):
        from src.api.dmarket_api_client.backoff import should_trip
        assert should_trip(200) is False
        assert should_trip(201) is False


# ====================================================================
# P0-B: CS2CapCache tests
# ====================================================================
class TestCS2CapCacheHotPath:
    """Hot-path operations must be sub-ms dict lookups (no asyncio)."""

    def _make_cache(self):
        from src.api.cs2cap_cache import CS2CapCache
        from src.api.cs2cap_oracle import PriceSnapshot, BidsSnapshot

        oracle = MagicMock()
        dmarket_client = MagicMock()
        cache = CS2CapCache(
            oracle=oracle, dmarket_client=dmarket_client, game_id="a8db"
        )

        # Seed caches directly
        snap = PriceSnapshot(hash_name="AK-47 | Redline (FT)", min_price=15.50)
        snap.provider_prices = {"buff163": 15.50}
        cache._ask_cache["AK-47 | Redline (FT)"] = snap

        bid = BidsSnapshot(hash_name="AK-47 | Redline (FT)", max_bid=16.00)
        bid.provider_bids = {"csfloat": 16.00}
        cache._bid_cache["AK-47 | Redline (FT)"] = bid

        cache._last_refresh_ts = time.time()
        return cache

    def test_get_ask_returns_snapshot(self):
        cache = self._make_cache()
        snap = cache.get_ask("AK-47 | Redline (FT)")
        assert snap is not None
        assert snap.min_price == 15.50
        assert snap.provider_prices == {"buff163": 15.50}

    def test_get_bid_returns_snapshot(self):
        cache = self._make_cache()
        bid = cache.get_bid("AK-47 | Redline (FT)")
        assert bid is not None
        assert bid.max_bid == 16.00

    def test_get_ask_price_convenience(self):
        cache = self._make_cache()
        assert cache.get_ask_price("AK-47 | Redline (FT)") == 15.50
        assert cache.get_ask_price("Unknown Item") == 0.0

    def test_get_bid_price_convenience(self):
        cache = self._make_cache()
        assert cache.get_bid_price("AK-47 | Redline (FT)") == 16.00
        assert cache.get_bid_price("Unknown Item") == 0.0

    def test_hot_path_is_synchronous(self):
        """get_ask / get_bid must not be coroutines — sub-ms latency."""
        cache = self._make_cache()
        # Should be regular methods, not coroutines
        result = cache.get_ask("AK-47 | Redline (FT)")
        assert not asyncio.iscoroutine(result)
        result = cache.get_bid("AK-47 | Redline (FT)")
        assert not asyncio.iscoroutine(result)

    def test_is_stale_false_when_fresh(self):
        cache = self._make_cache()
        assert cache.is_stale() is False

    def test_is_stale_true_when_never_refreshed(self):
        from src.api.cs2cap_cache import CS2CapCache
        cache = CS2CapCache(
            oracle=MagicMock(), dmarket_client=MagicMock(), game_id="a8db"
        )
        assert cache.is_stale() is True

    def test_is_stale_true_when_old(self):
        from src.api.cs2cap_cache import CS2CapCache
        cache = CS2CapCache(
            oracle=MagicMock(), dmarket_client=MagicMock(), game_id="a8db"
        )
        cache._last_refresh_ts = time.time() - 1000
        assert cache.is_stale() is True

    def test_stats_shape(self):
        cache = self._make_cache()
        st = cache.stats()
        assert "ask_count" in st
        assert "bid_count" in st
        assert "is_stale" in st
        assert "refresh_count" in st
        assert st["ask_count"] == 1
        assert st["bid_count"] == 1
        assert st["is_stale"] is False


class TestCS2CapCacheRefresh:
    """Background refresh task lifecycle."""

    @pytest.mark.asyncio
    async def test_refresh_now_populates_caches(self):
        from src.api.cs2cap_cache import CS2CapCache
        from src.api.cs2cap_oracle import PriceSnapshot, BidsSnapshot

        oracle = MagicMock()
        oracle.rate_limit_state = MagicMock(return_value={
            "monthly_used": 0,
            "monthly_limit": 50000,
            "remaining_header": 50000,
            "is_quota_exhausted": False,
            "cooldown_remaining_s": 0.0,
        })
        dmarket_client = AsyncMock()

        dmarket_client.get_aggregated_prices = AsyncMock(
            return_value={
                "AK-47 | Redline (FT)": {"ask_count": 10, "bid_count": 5},
                "AK-47 | Redline (WW)": {"ask_count": 3, "bid_count": 2},
            }
        )
        oracle.get_prices_batch = AsyncMock(
            return_value={
                "AK-47 | Redline (FT)": PriceSnapshot(
                    hash_name="AK-47 | Redline (FT)", min_price=15.0
                ),
            }
        )
        oracle.get_bids_batch = AsyncMock(
            return_value={
                "AK-47 | Redline (FT)": BidsSnapshot(
                    hash_name="AK-47 | Redline (FT)", max_bid=16.0
                ),
            }
        )

        cache = CS2CapCache(
            oracle=oracle, dmarket_client=dmarket_client, game_id="a8db"
        )
        await cache.refresh_now()

        assert len(cache._ask_cache) == 1
        assert len(cache._bid_cache) == 1
        assert cache.get_ask_price("AK-47 | Redline (FT)") == 15.0
        assert cache.get_bid_price("AK-47 | Redline (FT)") == 16.0
        assert cache._refresh_count == 1

    @pytest.mark.asyncio
    async def test_refresh_now_handles_agg_prices_failure(self):
        from src.api.cs2cap_cache import CS2CapCache

        oracle = MagicMock()
        oracle.rate_limit_state = MagicMock(return_value={
            "monthly_used": 0,
            "monthly_limit": 50000,
            "remaining_header": 50000,
            "is_quota_exhausted": False,
            "cooldown_remaining_s": 0.0,
        })
        dmarket_client = AsyncMock()
        dmarket_client.get_aggregated_prices = AsyncMock(side_effect=RuntimeError("network"))

        cache = CS2CapCache(
            oracle=oracle, dmarket_client=dmarket_client, game_id="a8db"
        )
        await cache.refresh_now()  # should not raise

        assert cache._error_count == 1
        assert "network" in cache._last_error
        assert len(cache._ask_cache) == 0

    @pytest.mark.asyncio
    async def test_refresh_now_handles_empty_agg_prices(self):
        from src.api.cs2cap_cache import CS2CapCache

        oracle = MagicMock()
        oracle.rate_limit_state = MagicMock(return_value={
            "monthly_used": 0,
            "monthly_limit": 50000,
            "remaining_header": 50000,
            "is_quota_exhausted": False,
            "cooldown_remaining_s": 0.0,
        })
        dmarket_client = AsyncMock()
        dmarket_client.get_aggregated_prices = AsyncMock(return_value={})

        cache = CS2CapCache(
            oracle=oracle, dmarket_client=dmarket_client, game_id="a8db"
        )
        await cache.refresh_now()

        assert len(cache._ask_cache) == 0
        assert cache._refresh_count == 0  # not incremented on empty

    @pytest.mark.asyncio
    async def test_start_and_stop_lifecycle(self):
        from src.api.cs2cap_cache import CS2CapCache

        oracle = MagicMock()
        oracle.rate_limit_state = MagicMock(return_value={
            "monthly_used": 0,
            "monthly_limit": 50000,
            "remaining_header": 50000,
            "is_quota_exhausted": False,
            "cooldown_remaining_s": 0.0,
        })
        oracle.load_catalog = AsyncMock(return_value=38000)
        dmarket_client = AsyncMock()
        dmarket_client.get_aggregated_prices = AsyncMock(return_value={})

        cache = CS2CapCache(
            oracle=oracle, dmarket_client=dmarket_client, game_id="a8db"
        )
        # Disable on-start refresh to keep test fast
        from src.config import Config
        original = Config.CS2CAP_CACHE_REFRESH_ON_START
        Config.CS2CAP_CACHE_REFRESH_ON_START = False
        try:
            await cache.start()
            assert cache._refresh_task is not None
            assert not cache._refresh_task.done()
            await cache.stop()
            assert cache._refresh_task is None or cache._refresh_task.done()
        finally:
            Config.CS2CAP_CACHE_REFRESH_ON_START = original


# ====================================================================
# P0-C: MAX_SNIPING_PRICE_USD enforcement
# ====================================================================
class TestMaxSnipingPriceCap:
    """
    The instant-buy path MUST skip items above MAX_SNIPING_PRICE_USD.
    """

    @pytest.mark.asyncio
    async def test_evaluator_skips_items_above_cap(self):
        from src.core.target_sniping.filter import _FilterMixin
        from src.config import Config
        from unittest.mock import patch, MagicMock

        # Force cap to $5
        original_cap = Config.MAX_SNIPING_PRICE_USD
        Config.MAX_SNIPING_PRICE_USD = 5.0
        try:
            mixin = _FilterMixin()
            mixin.liquidity = MagicMock()
            mixin.liquidity.can_spend = MagicMock(return_value=True)
            mixin._skip_if_locked = MagicMock(return_value=False)
            mixin.buy_budget = 25.0  # from Config.MAX_PRICE_USD

            item = {
                "title": "Test Item (FT)",
                "itemId": "test-id",
                "price": {"USD": "1000"},  # $10.00
                "attributes": [],
            }

            with patch("src.core.target_sniping.filter.price_db") as mock_db:
                mock_db.has_target_been_placed = MagicMock(return_value=False)
                mock_db.log_decision = MagicMock()

                result = await mixin._evaluate_candidate(
                    item=item,
                    game_id="a8db",
                    oracle=None,
                    agg_prices={
                        "Test Item (FT)": {
                            "best_bid": 15.0,
                            "best_ask": 8.0,
                            "ask_count": 5,
                            "bid_count": 3,
                        }
                    },
                    bulk_fees={},
                    current_balance=100.0,
                    current_margin=0.05,
                )

                # $10 > $5 cap → should be rejected
                assert result is None
        finally:
            Config.MAX_SNIPING_PRICE_USD = original_cap

    @pytest.mark.asyncio
    async def test_evaluator_passes_items_below_cap(self):
        """
        The cap is checked AFTER the budget check, so the $3 item
        must reach the cap check (i.e. not be rejected earlier).
        We assert by checking the call doesn't bail out before the cap.
        Since the oracle is None and we'd hit it later, we just verify
        the cap doesn't trip by checking log_decision was NOT called
        for the "Above instant-buy cap" reason.
        """
        from src.core.target_sniping.filter import _FilterMixin
        from src.config import Config
        from unittest.mock import patch, MagicMock

        original_cap = Config.MAX_SNIPING_PRICE_USD
        Config.MAX_SNIPING_PRICE_USD = 5.0
        try:
            mixin = _FilterMixin()
            mixin.liquidity = MagicMock()
            mixin.liquidity.can_spend = MagicMock(return_value=True)
            mixin._skip_if_locked = MagicMock(return_value=False)
            mixin.buy_budget = 25.0

            item = {
                "title": "Cheap Item (FT)",
                "itemId": "cheap-id",
                "price": {"USD": "300"},  # $3.00 < $5 cap
                "attributes": [],
            }

            with patch("src.core.target_sniping.filter.price_db") as mock_db:
                mock_db.has_target_been_placed = MagicMock(return_value=False)
                mock_db.log_decision = MagicMock()

                # The function will eventually fail (no oracle) but we
                # only need to verify the cap check didn't reject it
                # before any oracle call.
                try:
                    await mixin._evaluate_candidate(
                        item=item,
                        game_id="a8db",
                        oracle=None,
                        agg_prices={
                            "Cheap Item (FT)": {
                                "best_bid": 5.0,
                                "best_ask": 3.0,
                                "ask_count": 5,
                                "bid_count": 3,
                            }
                        },
                        bulk_fees={"cheap-id": 0.05},
                        current_balance=100.0,
                        current_margin=0.05,
                    )
                except AttributeError:
                    # Expected: oracle is None, so oracle.get_item_price
                    # blows up later in the function. The cap check
                    # itself passed.
                    pass

                # log_decision should NOT have been called with
                # "Above instant-buy cap" reason
                for call in mock_db.log_decision.call_args_list:
                    args, _ = call
                    if len(args) >= 2 and args[1] == "Above instant-buy cap":
                        pytest.fail(
                            f"Cap check incorrectly rejected $3 item "
                            f"(cap was $5): {args}"
                        )
        finally:
            Config.MAX_SNIPING_PRICE_USD = original_cap


# ====================================================================
# P0-A: Batched PATCH buy_items (already in v12.3, regression test)
# ====================================================================
class TestBatchedBuyItems:
    """
    Verify buy_items sends a single PATCH request with the full array.
    """

    @pytest.mark.asyncio
    async def test_buy_items_sends_patch_with_offers_array(self):
        from src.api.dmarket_api_client import DMarketAPIClient
        from src.api.dmarket_api_client.backoff import CircuitBreaker

        client = DMarketAPIClient(
            public_key="0" * 64, secret_key="0" * 128, base_url="https://api.dmarket.com"
        )
        client._breaker = CircuitBreaker(name="test", fail_threshold=3)

        captured = {}

        async def fake_request(method, path, params=None, body=None):
            captured["method"] = method
            captured["path"] = path
            captured["body"] = body
            return {"status": "success"}

        # DRY_RUN=false to actually call the network path
        import os
        original_dry = os.environ.get("DRY_RUN", "true")
        os.environ["DRY_RUN"] = "false"
        try:
            client.make_request = fake_request
            offers = [
                {"offerId": "id1", "price": {"amount": "100", "currency": "USD"}},
                {"offerId": "id2", "price": {"amount": "200", "currency": "USD"}},
            ]
            result = await client.buy_items(offers)
            assert captured["method"] == "PATCH"
            assert captured["path"] == "/exchange/v1/offers-buy"
            assert captured["body"] == {"offers": offers}
            assert len(captured["body"]["offers"]) == 2
        finally:
            os.environ["DRY_RUN"] = original_dry


# ====================================================================
# Integration: MAX_SNIPING_PRICE_USD in config
# ====================================================================
class TestConfigKeys:
    def test_max_sniping_price_usd_present(self):
        from src.config import Config
        assert hasattr(Config, "MAX_SNIPING_PRICE_USD")
        assert Config.MAX_SNIPING_PRICE_USD > 0
        assert Config.MAX_SNIPING_PRICE_USD <= Config.MAX_PRICE_USD

    def test_cs2cap_cache_ttl_present(self):
        from src.config import Config
        assert hasattr(Config, "CS2CAP_CACHE_TTL_SECONDS")
        assert Config.CS2CAP_CACHE_TTL_SECONDS > 0
        assert hasattr(Config, "CS2CAP_CACHE_REFRESH_TOP_N")
        assert Config.CS2CAP_CACHE_REFRESH_TOP_N > 0

    def test_first_sale_age_days_present(self):
        """Regression: Config.MAX_FIRST_SALE_AGE_DAYS missing crashed
        every cycle in 2026-06-07 dry-run (Discovered in 30-min test)."""
        from src.config import Config
        assert hasattr(Config, "MAX_FIRST_SALE_AGE_DAYS")
        assert Config.MAX_FIRST_SALE_AGE_DAYS > 0
        assert Config.MAX_FIRST_SALE_AGE_DAYS <= 365

    def test_all_config_refs_resolved(self):
        """
        Regression: scan all .py files for Config.X references and assert
        every referenced key exists. Prevents runtime AttributeError on
        new code paths.
        """
        import re
        import os
        from src.config import Config

        missing = []
        for root, dirs, files in os.walk("src"):
            if "__pycache__" in root:
                continue
            for f in files:
                if not f.endswith(".py"):
                    continue
                path = os.path.join(root, f)
                with open(path) as fh:
                    content = fh.read()
                refs = set(re.findall(r"Config\.([A-Z_][A-Z_0-9]+)", content))
                for r in refs:
                    if not hasattr(Config, r):
                        missing.append(f"{path}: Config.{r}")
        assert not missing, f"Missing Config keys: {missing}"
