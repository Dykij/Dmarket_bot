"""
Unit tests for CS2Cap batch endpoints (POST /prices/batch, POST /bids/batch).

Phase 3 of DMarket <-> CS2Cap optimization plan.
Run: python -m pytest tests/unit/api/test_cs2cap_batch.py -v
"""

import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def mock_price_db():
    """Bypass SQLite writes (record_price / save_state) in tests."""
    with patch("src.api.cs2cap_oracle.client.price_db") as db:
        db.get_state = MagicMock(return_value=None)
        db.save_state = MagicMock()
        db.get_latest_price = MagicMock(return_value=None)
        db.record_price = MagicMock()
        yield db


@pytest.fixture
def oracle(mock_price_db):
    """Construct CS2CapOracle with empty API key (no real auth needed)."""
    from src.api.cs2cap_oracle import CS2CapOracle
    return CS2CapOracle(api_key="test_key")


def _mock_response(json_payload: dict, status: int = 200, headers: dict | None = None):
    """Build an aiohttp-like response context manager."""
    resp = MagicMock()
    resp.status = status
    resp.headers = headers or {}
    resp.json = AsyncMock(return_value=json_payload)
    resp.text = AsyncMock(return_value=str(json_payload))
    # aiohttp uses async with response as ... so we need __aenter__/__aexit__
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    return resp


# =====================================================================
# Dataclass tests
# =====================================================================

class TestPriceSnapshot:
    """PriceSnapshot dataclass behaviour."""

    def test_defaults(self):
        from src.api.cs2cap_oracle import PriceSnapshot
        s = PriceSnapshot(hash_name="AK-47 | Redline (Field-Tested)")
        assert s.hash_name == "AK-47 | Redline (Field-Tested)"
        assert s.min_price == 0.0
        assert s.max_bid == 0.0
        assert s.provider_prices == {}
        assert s.total_quantity == 0
        assert s.has_data is False

    def test_has_data_true(self):
        from src.api.cs2cap_oracle import PriceSnapshot
        s = PriceSnapshot(hash_name="x", min_price=12.34)
        assert s.has_data is True

    def test_liquidity_score_capped_at_one(self):
        from src.api.cs2cap_oracle import PriceSnapshot
        s = PriceSnapshot(hash_name="x", total_quantity=99999)
        assert s.liquidity_score == 1.0

    def test_liquidity_score_proportional(self):
        from src.api.cs2cap_oracle import PriceSnapshot
        s = PriceSnapshot(hash_name="x", total_quantity=50)
        assert s.liquidity_score == 0.5


class TestBidsSnapshot:
    """BidsSnapshot dataclass behaviour."""

    def test_defaults(self):
        from src.api.cs2cap_oracle import BidsSnapshot
        s = BidsSnapshot(hash_name="AK-47 | Redline (Field-Tested)")
        assert s.has_data is False
        assert s.max_bid == 0.0


# =====================================================================
# _parse_batch_prices tests
# =====================================================================

class TestParseBatchPrices:
    """_parse_batch_prices must handle the documented response shape."""

    def test_basic_parsing(self, oracle):
        from src.api.cs2cap_oracle import PriceSnapshot
        results = {
            "AK-47 | Redline (Field-Tested)": PriceSnapshot(hash_name="AK-47 | Redline (Field-Tested)"),
            "AWP | Dragon Lore": PriceSnapshot(hash_name="AWP | Dragon Lore"),
        }
        data = {
            "items": [
                {
                    "market_hash_name": "AK-47 | Redline (Field-Tested)",
                    "providers": [
                        {"provider": "buff163", "lowest_ask": 435886, "quantity": 3},
                        {"provider": "csfloat", "lowest_ask": 440100, "quantity": 1},
                    ],
                },
                {
                    "market_hash_name": "AWP | Dragon Lore",
                    "providers": [
                        {"provider": "buff163", "lowest_ask": 15000000, "quantity": 0},
                    ],
                },
            ]
        }
        oracle._parse_batch_prices(data, results)

        ak = results["AK-47 | Redline (Field-Tested)"]
        assert ak.min_price == pytest.approx(4358.86)  # 435886 / 100
        assert ak.provider_prices == {"buff163": 4358.86, "csfloat": 4401.00}
        assert ak.provider_quantities == {"buff163": 3, "csfloat": 1}
        assert ak.total_quantity == 4
        assert ak.has_data is True

        awp = results["AWP | Dragon Lore"]
        assert awp.min_price == pytest.approx(150000.00)
        assert awp.total_quantity == 0  # quantity=0 in payload

    def test_unknown_item_ignored(self, oracle):
        from src.api.cs2cap_oracle import PriceSnapshot
        results = {"Known": PriceSnapshot(hash_name="Known")}
        data = {
            "items": [
                {
                    "market_hash_name": "Unknown",
                    "providers": [{"provider": "buff163", "lowest_ask": 1000, "quantity": 1}],
                },
            ]
        }
        oracle._parse_batch_prices(data, results)
        assert results["Known"].min_price == 0.0
        # Unknown key not in `results` so dict is unchanged.

    def test_zero_ask_ignored(self, oracle):
        from src.api.cs2cap_oracle import PriceSnapshot
        results = {"X": PriceSnapshot(hash_name="X")}
        data = {
            "items": [
                {
                    "market_hash_name": "X",
                    "providers": [
                        {"provider": "buff163", "lowest_ask": 0, "quantity": 0},
                    ],
                },
            ]
        }
        oracle._parse_batch_prices(data, results)
        assert results["X"].min_price == 0.0
        assert results["X"].total_quantity == 0

    def test_takes_min_ask(self, oracle):
        from src.api.cs2cap_oracle import PriceSnapshot
        results = {"X": PriceSnapshot(hash_name="X")}
        data = {
            "items": [
                {
                    "market_hash_name": "X",
                    "providers": [
                        {"provider": "buff163", "lowest_ask": 5000, "quantity": 1},
                        {"provider": "csfloat", "lowest_ask": 4500, "quantity": 1},
                        {"provider": "dmarket", "lowest_ask": 4800, "quantity": 1},
                    ],
                },
            ]
        }
        oracle._parse_batch_prices(data, results)
        assert results["X"].min_price == 45.00  # csfloat lowest

    def test_fallback_field_names(self, oracle):
        """Some API responses use 'title' or 'name' instead of 'market_hash_name'."""
        from src.api.cs2cap_oracle import PriceSnapshot
        results = {"X": PriceSnapshot(hash_name="X")}
        data = {
            "items": [
                {
                    "title": "X",  # alternate field
                    "providers": [{"provider": "buff163", "lowest_ask": 9999, "quantity": 2}],
                },
            ]
        }
        oracle._parse_batch_prices(data, results)
        assert results["X"].min_price == 99.99


# =====================================================================
# _parse_batch_bids tests
# =====================================================================

class TestParseBatchBids:
    """_parse_batch_bids must handle the documented /bids/batch shape."""

    def test_basic_parsing(self, oracle):
        from src.api.cs2cap_oracle import BidsSnapshot
        results = {
            "X": BidsSnapshot(hash_name="X"),
            "Y": BidsSnapshot(hash_name="Y"),
        }
        data = {
            "items": [
                {
                    "market_hash_name": "X",
                    "providers": [
                        {"provider": "buff163", "highest_bid": 420000},
                        {"provider": "csfloat", "highest_bid": 425000},
                    ],
                },
                {
                    "market_hash_name": "Y",
                    "providers": [
                        {"provider": "buff163", "highest_bid": 1000},
                    ],
                },
            ]
        }
        oracle._parse_batch_bids(data, results)
        assert results["X"].max_bid == pytest.approx(4250.00)
        assert results["X"].provider_bids == {"buff163": 4200.00, "csfloat": 4250.00}
        assert results["Y"].max_bid == pytest.approx(10.00)


# =====================================================================
# get_prices_batch integration tests (with mocked HTTP)
# =====================================================================

class TestGetPricesBatch:
    """get_prices_batch must chunk at 100, call POST /prices/batch, parse results."""

    def test_empty_input(self, oracle):
        async def run():
            return await oracle.get_prices_batch([])
        result = asyncio.run(run())
        assert result == {}

    def test_single_batch_returns_dict_for_all_names(self, oracle, mock_price_db):
        # Pre-seed catalog is not needed; batch takes market_hash_names directly.
        payload = {
            "items": [
                {
                    "market_hash_name": "AK-47 | Redline (Field-Tested)",
                    "providers": [{"provider": "buff163", "lowest_ask": 1000, "quantity": 1}],
                },
                {
                    "market_hash_name": "AWP | Asiimov (Field-Tested)",
                    "providers": [],
                },
            ]
        }
        resp = _mock_response(payload)

        with patch.object(oracle, "get_session") as gs:
            session = MagicMock()
            session.post = MagicMock(return_value=resp)
            gs.return_value = session

            async def run():
                return await oracle.get_prices_batch([
                    "AK-47 | Redline (Field-Tested)",
                    "AWP | Asiimov (Field-Tested)",
                ])
            result = asyncio.run(run())

        # All requested names must be present (even with no data)
        assert set(result.keys()) == {
            "AK-47 | Redline (Field-Tested)",
            "AWP | Asiimov (Field-Tested)",
        }
        assert result["AK-47 | Redline (Field-Tested)"].min_price == 10.00
        assert result["AWP | Asiimov (Field-Tested)"].min_price == 0.0  # no providers

        # POST must have been called once with /prices/batch
        session.post.assert_called_once()
        call_args = session.post.call_args
        assert "/prices/batch" in call_args.args[0]
        body = call_args.kwargs["json"]
        assert body["currency"] == "USD"
        assert "AK-47 | Redline (Field-Tested)" in body["market_hash_names"]

    def test_chunks_at_100_items(self, oracle, mock_price_db):
        """151 items must produce 2 POST calls (100 + 51)."""
        names = [f"Item {i}" for i in range(151)]

        # Each POST returns a single-item success so we can detect chunking.
        def make_response(*args, **kwargs):
            body = kwargs.get("json", {})
            names_in_chunk = body.get("market_hash_names", [])
            return _mock_response({
                "items": [
                    {
                        "market_hash_name": n,
                        "providers": [{"provider": "buff163", "lowest_ask": 100, "quantity": 1}],
                    }
                    for n in names_in_chunk
                ]
            })

        with patch.object(oracle, "get_session") as gs:
            session = MagicMock()
            session.post = MagicMock(side_effect=make_response)
            gs.return_value = session

            async def run():
                return await oracle.get_prices_batch(names)
            result = asyncio.run(run())

        assert session.post.call_count == 2
        # First call must have 100 items, second call must have 51
        first_body = session.post.call_args_list[0].kwargs["json"]
        second_body = session.post.call_args_list[1].kwargs["json"]
        assert len(first_body["market_hash_names"]) == 100
        assert len(second_body["market_hash_names"]) == 51
        assert len(result) == 151

    def test_post_bypasses_throttle(self, oracle, mock_price_db):
        """Batch POSTs must NOT be subject to _throttle (1 unit per call, not per item)."""
        resp = _mock_response({"items": []})
        with patch.object(oracle, "get_session") as gs:
            session = MagicMock()
            session.post = MagicMock(return_value=resp)
            gs.return_value = session

            with patch.object(oracle, "_throttle") as throttle:
                async def run():
                    return await oracle.get_prices_batch(["X"])
                asyncio.run(run())
                throttle.assert_not_called()


# =====================================================================
# get_bids_batch tests
# =====================================================================

class TestGetBidsBatch:
    """get_bids_batch must call POST /bids/batch."""

    def test_basic(self, oracle, mock_price_db):
        resp = _mock_response({
            "items": [
                {
                    "market_hash_name": "AK-47 | Redline (Field-Tested)",
                    "providers": [{"provider": "buff163", "highest_bid": 9999}],
                },
            ]
        })
        with patch.object(oracle, "get_session") as gs:
            session = MagicMock()
            session.post = MagicMock(return_value=resp)
            gs.return_value = session

            async def run():
                return await oracle.get_bids_batch(["AK-47 | Redline (Field-Tested)"])
            result = asyncio.run(run())

        assert "/bids/batch" in session.post.call_args.args[0]
        assert result["AK-47 | Redline (Field-Tested)"].max_bid == 99.99


# =====================================================================
# Monthly quota tracker tests
# =====================================================================

class TestMonthlyQuota:
    """The _increment_monthly_counter must persist counts and warn at thresholds."""

    def test_counter_persists(self, oracle, mock_price_db):
        # First call: no prior state
        mock_price_db.get_state = MagicMock(return_value=None)
        oracle._increment_monthly_counter()
        # Should have written "YYYY-MM:1"
        args = mock_price_db.save_state.call_args
        assert args.args[0] == "cs2cap_calls_month"
        assert args.args[1].endswith(":1")

    def test_counter_resets_on_new_month(self, oracle, mock_price_db):
        # Pretend last record is from January
        mock_price_db.get_state = MagicMock(return_value="2025-01:9999")
        oracle._increment_monthly_counter()
        args = mock_price_db.save_state.call_args
        saved = args.args[1]
        yyyymm = time.strftime("%Y-%m")
        # If we are in 2026-06, it should reset to 1, not 10000.
        if yyyymm != "2025-01":
            assert saved.startswith(yyyymm)
            assert saved.endswith(":1")


# =====================================================================
# Rate-limit header handling tests
# =====================================================================

class TestRateLimitHeader:
    """X-RateLimit-Remaining header should drive adaptive throttling."""

    def test_low_remaining_triggers_slowdown(self, oracle, mock_price_db):
        oracle._request_delay = 1.0  # baseline
        resp = _mock_response(
            {"items": []},
            headers={"X-RateLimit-Remaining": "3"},  # below 5
        )
        with patch.object(oracle, "get_session") as gs:
            session = MagicMock()
            session.post = MagicMock(return_value=resp)
            gs.return_value = session

            async def run():
                return await oracle._request_post(
                    "/prices/batch",
                    body={"market_hash_names": []},
                    bypass_throttle=True,
                )
            asyncio.run(run())
        # After low remaining header, delay should be at least 1.5
        assert oracle._request_delay >= 1.5
        assert oracle._rate_remaining == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# =====================================================================
# get_price_snapshot tests (Phase 2 — single-item snapshot)
# =====================================================================

class TestGetPriceSnapshot:
    """get_price_snapshot hits /prices once and returns both min_price
    and the per-provider breakdown, replacing the back-to-back pattern
    of get_item_price() + get_cross_market_data()."""

    def test_hits_prices_endpoint_once(self, oracle, mock_price_db):
        # Pre-seed catalog to skip /items fetch
        oracle._item_catalog = {"AK-47 | Redline (Field-Tested)": 4994}
        oracle._catalog_ts = time.time()

        resp = _mock_response({
            "items": [
                {"provider": "buff163", "lowest_ask": 1000, "quantity": 3},
                {"provider": "csfloat", "lowest_ask": 1100, "quantity": 1},
            ]
        })
        with patch.object(oracle, "get_session") as gs:
            session = MagicMock()
            # Must be GET (single-item variant), not POST
            session.get = MagicMock(return_value=resp)
            session.post = MagicMock()
            gs.return_value = session

            async def run():
                return await oracle.get_price_snapshot("AK-47 | Redline (Field-Tested)")
            snap = asyncio.run(run())

        assert snap is not None
        assert snap.min_price == 10.00
        assert snap.provider_prices == {"buff163": 10.00, "csfloat": 11.00}
        assert snap.total_quantity == 4
        # Verify only one GET happened (no POST for single-item)
        assert session.get.call_count == 1
        session.post.assert_not_called()

    def test_returns_none_for_unknown_item(self, oracle, mock_price_db):
        # Empty catalog -> no item_id
        oracle._item_catalog = {}
        oracle._catalog_ts = time.time()

        async def run():
            return await oracle.get_price_snapshot("Unknown Item XYZ")
        snap = asyncio.run(run())
        assert snap is None

    def test_handles_empty_data(self, oracle, mock_price_db):
        oracle._item_catalog = {"X": 123}
        oracle._catalog_ts = time.time()

        resp = _mock_response({"items": []})  # no providers
        with patch.object(oracle, "get_session") as gs:
            session = MagicMock()
            session.get = MagicMock(return_value=resp)
            gs.return_value = session

            async def run():
                return await oracle.get_price_snapshot("X")
            snap = asyncio.run(run())

        assert snap is not None
        assert snap.min_price == 0.0
        assert snap.has_data is False
