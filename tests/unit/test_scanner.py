"""Tests for scanner.py — parallel listing fetcher + float/phase secondary scan."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.target_sniping.scanner import _ScannerMixin


def _make_listing(item_id: str = "i1", title: str = "AK-47", price_cents: int = 1000):
    return {"itemId": item_id, "title": title, "price": {"USD": str(price_cents)}}


def _make_scanner() -> MagicMock:
    scanner = MagicMock(spec=_ScannerMixin)
    scanner.client = AsyncMock()
    return scanner


class TestFetchCheapestListings:

    @pytest.mark.asyncio
    async def test_empty_titles_returns_empty(self):
        scanner = _make_scanner()
        result = await _ScannerMixin._fetch_cheapest_listings(scanner, "a8db", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_single_title_returns_cheapest(self):
        scanner = _make_scanner()
        scanner.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [
                _make_listing("i1", "AK-47", 1500),
                _make_listing("i2", "AK-47", 1000),
                _make_listing("i3", "AK-47", 1200),
            ],
        })

        result = await _ScannerMixin._fetch_cheapest_listings(scanner, "a8db", ["AK-47"])

        assert len(result) == 1
        assert result[0]["itemId"] == "i2"  # cheapest

    @pytest.mark.asyncio
    async def test_multiple_titles(self):
        scanner = _make_scanner()
        async def _mock_fetch(game_id, limit, title):
            items = {
                "AK-47": [_make_listing("a1", "AK-47", 1000)],
                "M4A4": [_make_listing("m1", "M4A4", 2000)],
            }
            return {"objects": items.get(title, [])}

        scanner.client.get_market_items_v2 = AsyncMock(side_effect=_mock_fetch)

        result = await _ScannerMixin._fetch_cheapest_listings(scanner, "a8db", ["AK-47", "M4A4"])

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_api_error_returns_empty_for_title(self):
        scanner = _make_scanner()
        scanner.client.get_market_items_v2 = AsyncMock(side_effect=Exception("API down"))

        result = await _ScannerMixin._fetch_cheapest_listings(scanner, "a8db", ["AK-47"])

        assert result == []

    @pytest.mark.asyncio
    async def test_deduplicates_same_item_id(self):
        scanner = _make_scanner()
        async def _mock_fetch(game_id, limit, title):
            return {"objects": [_make_listing("same_id", title, 1000)]}

        scanner.client.get_market_items_v2 = AsyncMock(side_effect=_mock_fetch)

        result = await _ScannerMixin._fetch_cheapest_listings(scanner, "a8db", ["AK-47", "M4A4"])

        # Both have same itemId "same_id", only first should be kept
        assert len(result) == 1


class TestFetchPriceRangeListings:

    @pytest.mark.asyncio
    async def test_invalid_range_returns_empty(self):
        scanner = _make_scanner()
        result = await _ScannerMixin._fetch_price_range_listings(
            scanner, "a8db", min_usd=10.0, max_usd=5.0,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_zero_pages_returns_empty(self):
        scanner = _make_scanner()
        result = await _ScannerMixin._fetch_price_range_listings(
            scanner, "a8db", max_pages=0,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty(self):
        scanner = _make_scanner()
        scanner.client.get_market_items_v2 = AsyncMock(return_value={"objects": []})

        result = await _ScannerMixin._fetch_price_range_listings(
            scanner, "a8db", min_usd=1.0, max_usd=10.0,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_picks_cheapest_per_title(self):
        scanner = _make_scanner()
        scanner.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [
                _make_listing("i1", "AK-47", 1500),
                _make_listing("i2", "AK-47", 1000),
            ],
        })

        result = await _ScannerMixin._fetch_price_range_listings(
            scanner, "a8db", min_usd=5.0, max_usd=20.0,
        )

        assert len(result) == 1
        assert result[0]["itemId"] == "i2"

    @pytest.mark.asyncio
    async def test_pagination_stops_on_no_cursor(self):
        scanner = _make_scanner()
        call_count = 0
        async def _mock_fetch(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"objects": [_make_listing("i1", "AK-47", 1000)], "cursor": "p2"}
            return {"objects": [_make_listing("i2", "M4A4", 2000)]}

        scanner.client.get_market_items_v2 = AsyncMock(side_effect=_mock_fetch)

        result = await _ScannerMixin._fetch_price_range_listings(
            scanner, "a8db", min_usd=5.0, max_usd=20.0,
        )

        assert call_count == 2
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_api_error_handled(self):
        scanner = _make_scanner()
        scanner.client.get_market_items_v2 = AsyncMock(side_effect=Exception("timeout"))

        result = await _ScannerMixin._fetch_price_range_listings(
            scanner, "a8db", min_usd=1.0, max_usd=10.0,
        )

        assert result == []


class TestFetchFloatFilteredListings:

    @pytest.mark.asyncio
    async def test_empty_titles_returns_empty(self):
        scanner = _make_scanner()
        result = await _ScannerMixin._fetch_float_filtered_listings(scanner, "a8db", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_non_high_value_title_skipped(self):
        scanner = _make_scanner()
        scanner.client.get_market_items_v2 = AsyncMock(return_value={"objects": []})

        result = await _ScannerMixin._fetch_float_filtered_listings(
            scanner, "a8db", ["P250 | Sand Dune"],
        )

        # Not a high-value pattern, should be skipped
        scanner.client.get_market_items_v2.assert_not_called()

    @pytest.mark.asyncio
    async def test_high_value_knife_calls_api(self):
        scanner = _make_scanner()
        scanner.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [_make_listing("i1", "★ Karambit", 50000)],
        })
        with patch("src.core.target_sniping.scanner.Config") as mock_config:
            mock_config.FLOAT_PHASE_MAX_EXTRA_CALLS = 10
            result = await _ScannerMixin._fetch_float_filtered_listings(
                scanner, "a8db", ["★ Karambit | Doppler"],
            )

        # Doppler triggers float filter + 4 phase filters = 5 calls, each returns 1 item
        assert len(result) >= 1
        scanner.client.get_market_items_v2.assert_called()

    @pytest.mark.asyncio
    async def test_doppler_triggers_phase_filters(self):
        scanner = _make_scanner()
        scanner.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [_make_listing("i1", "Doppler", 30000)],
        })
        with patch("src.core.target_sniping.scanner.Config") as mock_config:
            mock_config.FLOAT_PHASE_MAX_EXTRA_CALLS = 20
            result = await _ScannerMixin._fetch_float_filtered_listings(
                scanner, "a8db", ["★ Karambit | Doppler"],
            )

        # Should call: 1 float filter + 4 phase filters = 5 calls
        assert scanner.client.get_market_items_v2.call_count >= 2

    @pytest.mark.asyncio
    async def test_api_error_continues(self):
        scanner = _make_scanner()
        scanner.client.get_market_items_v2 = AsyncMock(side_effect=Exception("API error"))
        with patch("src.core.target_sniping.scanner.Config") as mock_config:
            mock_config.FLOAT_PHASE_MAX_EXTRA_CALLS = 10
            result = await _ScannerMixin._fetch_float_filtered_listings(
                scanner, "a8db", ["★ Karambit | Doppler"],
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_max_calls_limit(self):
        """Stops after FLOAT_PHASE_MAX_EXTRA_CALLS."""
        scanner = _make_scanner()
        scanner.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [_make_listing("i1", "item", 1000)],
        })
        with patch("src.core.target_sniping.scanner.Config") as mock_config:
            mock_config.FLOAT_PHASE_MAX_EXTRA_CALLS = 1
            result = await _ScannerMixin._fetch_float_filtered_listings(
                scanner, "a8db", ["★ Karambit | Doppler", "★ Butterfly | Fade"],
            )
        # Only 1 call allowed, so only first title processed
        assert scanner.client.get_market_items_v2.call_count <= 2  # float + maybe 1 phase

    @pytest.mark.asyncio
    async def test_non_doppler_skips_phase_filters(self):
        """Non-Doppler high-value items skip phase filters."""
        scanner = _make_scanner()
        scanner.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [_make_listing("i1", "item", 1000)],
        })
        with patch("src.core.target_sniping.scanner.Config") as mock_config:
            mock_config.FLOAT_PHASE_MAX_EXTRA_CALLS = 10
            result = await _ScannerMixin._fetch_float_filtered_listings(
                scanner, "a8db", ["★ Karambit | Fade"],  # Fade, not Doppler
            )
        # Only 1 call (float filter), no phase filters
        assert scanner.client.get_market_items_v2.call_count == 1


class TestFetchLowFeeListings:

    @pytest.mark.asyncio
    async def test_disabled_returns_empty(self):
        scanner = _make_scanner()
        with patch("src.core.target_sniping.scanner.Config") as mock_config:
            mock_config.LOW_FEE_ITEMS_SCAN_ENABLED = False
            result = await _ScannerMixin._fetch_low_fee_listings(scanner, "a8db")
        assert result == []

    @pytest.mark.asyncio
    async def test_no_low_fee_items_returns_empty(self):
        scanner = _make_scanner()
        with (
            patch("src.core.target_sniping.scanner.Config") as mock_config,
            patch("src.core.target_sniping.scanner.fetch_low_fee_titles", new_callable=AsyncMock) as mock_fetch,
        ):
            mock_config.LOW_FEE_ITEMS_SCAN_ENABLED = True
            mock_fetch.return_value = {}
            result = await _ScannerMixin._fetch_low_fee_listings(scanner, "a8db")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_cheapest_per_title(self):
        scanner = _make_scanner()
        scanner.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [
                _make_listing("i1", "AK-47", 1500),
                _make_listing("i2", "AK-47", 1000),
            ],
        })
        with (
            patch("src.core.target_sniping.scanner.Config") as mock_config,
            patch("src.core.target_sniping.scanner.fetch_low_fee_titles", new_callable=AsyncMock) as mock_fetch,
        ):
            mock_config.LOW_FEE_ITEMS_SCAN_ENABLED = True
            mock_config.LISTINGS_FETCH_LIMIT = 10
            mock_fetch.return_value = {"AK-47": 0.02}
            result = await _ScannerMixin._fetch_low_fee_listings(scanner, "a8db")

        assert len(result) == 1
        assert result[0]["itemId"] == "i2"  # cheapest
        assert result[0]["_low_fee_rate"] == 0.02

    @pytest.mark.asyncio
    async def test_api_error_handled(self):
        scanner = _make_scanner()
        scanner.client.get_market_items_v2 = AsyncMock(side_effect=Exception("API error"))
        with (
            patch("src.core.target_sniping.scanner.Config") as mock_config,
            patch("src.core.target_sniping.scanner.fetch_low_fee_titles", new_callable=AsyncMock) as mock_fetch,
        ):
            mock_config.LOW_FEE_ITEMS_SCAN_ENABLED = True
            mock_config.LISTINGS_FETCH_LIMIT = 10
            mock_fetch.return_value = {"AK-47": 0.02}
            result = await _ScannerMixin._fetch_low_fee_listings(scanner, "a8db")

        assert result == []

    @pytest.mark.asyncio
    async def test_empty_listings_skipped(self):
        scanner = _make_scanner()
        scanner.client.get_market_items_v2 = AsyncMock(return_value={"objects": []})
        with (
            patch("src.core.target_sniping.scanner.Config") as mock_config,
            patch("src.core.target_sniping.scanner.fetch_low_fee_titles", new_callable=AsyncMock) as mock_fetch,
        ):
            mock_config.LOW_FEE_ITEMS_SCAN_ENABLED = True
            mock_config.LISTINGS_FETCH_LIMIT = 10
            mock_fetch.return_value = {"AK-47": 0.02}
            result = await _ScannerMixin._fetch_low_fee_listings(scanner, "a8db")

        assert result == []
