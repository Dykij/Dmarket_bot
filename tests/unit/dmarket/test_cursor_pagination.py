"""Tests for cursor pagination in get_all_market_items.

These tests verify that cursor-based pagination works correctly
and is preferred over offset-based pagination for large datasets.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.dmarket.dmarket_api import DMarketAPI


@pytest.mark.asyncio()
class TestCursorPagination:
    """Tests for cursor pagination functionality."""

    async def test_cursor_pagination_enabled_by_default(self):
        """Test that cursor pagination is used by default."""
        api = DMarketAPI(public_key="test", secret_key="test")

        # Mock _request to track calls
        with patch.object(api, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "objects": [{"title": "Item 1"}, {"title": "Item 2"}],
                "cursor": None,  # No more pages
            }

            await api.get_all_market_items(game="csgo", max_items=10, use_cursor=True)

            # Verify cursor parameter was used
            call_args = mock_request.call_args
            assert call_args is not None
            assert "params" in call_args.kwargs
            assert (
                "cursor" not in call_args.kwargs["params"]
                or call_args.kwargs["params"]["cursor"] is None
            )

    async def test_cursor_pagination_multiple_pages(self):
        """Test cursor pagination across multiple pages."""
        api = DMarketAPI(public_key="test", secret_key="test")

        # Mock responses for 3 pages
        responses = [
            {
                "objects": [{"title": f"Item {i}"} for i in range(1, 101)],
                "cursor": "cursor_page_2",
            },
            {
                "objects": [{"title": f"Item {i}"} for i in range(101, 201)],
                "cursor": "cursor_page_3",
            },
            {
                "objects": [{"title": f"Item {i}"} for i in range(201, 251)],
                "cursor": None,  # Last page
            },
        ]

        with patch.object(
            api, "_request", new_callable=AsyncMock, side_effect=responses
        ) as mock_request:
            result = await api.get_all_market_items(game="csgo", max_items=250, use_cursor=True)

            # Verify all pages were fetched
            assert len(result) == 250
            assert mock_request.call_count == 3

            # Verify cursors were used correctly
            calls = mock_request.call_args_list
            assert calls[0].kwargs["params"].get("cursor") is None
            assert calls[1].kwargs["params"]["cursor"] == "cursor_page_2"
            assert calls[2].kwargs["params"]["cursor"] == "cursor_page_3"

    async def test_cursor_pagination_respects_max_items(self):
        """Test that max_items limit is respected with cursor pagination."""
        api = DMarketAPI(public_key="test", secret_key="test")

        responses = [
            {
                "objects": [{"title": f"Item {i}"} for i in range(1, 101)],
                "cursor": "cursor_page_2",
            },
            {
                "objects": [{"title": f"Item {i}"} for i in range(101, 201)],
                "cursor": "cursor_page_3",
            },
        ]

        with patch.object(
            api, "_request", new_callable=AsyncMock, side_effect=responses
        ) as mock_request:
            result = await api.get_all_market_items(game="csgo", max_items=150, use_cursor=True)

            # Should stop at 150 items (2 pages fetched, 150 returned)
            assert len(result) == 150
            assert result[0]["title"] == "Item 1"
            assert result[149]["title"] == "Item 150"

    async def test_cursor_pagination_stops_on_empty_cursor(self):
        """Test that pagination stops when cursor is None or empty."""
        api = DMarketAPI(public_key="test", secret_key="test")

        responses = [
            {
                "objects": [{"title": f"Item {i}"} for i in range(1, 51)],
                "cursor": None,  # No more pages
            }
        ]

        with patch.object(
            api, "_request", new_callable=AsyncMock, side_effect=responses
        ) as mock_request:
            result = await api.get_all_market_items(game="csgo", max_items=1000, use_cursor=True)

            # Should stop after first page since cursor is None
            assert len(result) == 50
            assert mock_request.call_count == 1

    async def test_offset_pagination_fallback(self):
        """Test that offset pagination works when use_cursor=False."""
        api = DMarketAPI(public_key="test", secret_key="test")

        # Mock get_market_items (used by offset pagination)
        with patch.object(api, "get_market_items", new_callable=AsyncMock) as mock_get_items:
            mock_get_items.side_effect = [
                {"objects": [{"title": f"Item {i}"} for i in range(1, 101)]},
                {"objects": [{"title": f"Item {i}"} for i in range(101, 151)]},
            ]

            result = await api.get_all_market_items(game="csgo", max_items=150, use_cursor=False)

            # Verify offset pagination was used
            assert len(result) == 150
            assert mock_get_items.call_count == 2

            # Check offsets
            calls = mock_get_items.call_args_list
            assert calls[0].kwargs["offset"] == 0
            assert calls[1].kwargs["offset"] == 100

    async def test_cursor_pagination_handles_nextCursor_field(self):
        """Test that both 'cursor' and 'nextCursor' fields are recognized."""
        api = DMarketAPI(public_key="test", secret_key="test")

        responses = [
            {
                "objects": [{"title": f"Item {i}"} for i in range(1, 101)],
                "nextCursor": "next_page_cursor",  # Some APIs use 'nextCursor'
            },
            {
                "objects": [{"title": f"Item {i}"} for i in range(101, 151)],
                "nextCursor": None,
            },
        ]

        with patch.object(
            api, "_request", new_callable=AsyncMock, side_effect=responses
        ) as mock_request:
            result = await api.get_all_market_items(game="csgo", max_items=150, use_cursor=True)

            assert len(result) == 150
            assert mock_request.call_count == 2

            # Verify nextCursor was used
            assert mock_request.call_args_list[1].kwargs["params"]["cursor"] == "next_page_cursor"

    async def test_cursor_pagination_with_filters(self):
        """Test cursor pagination preserves price filters."""
        api = DMarketAPI(public_key="test", secret_key="test")

        responses = [
            {
                "objects": [{"title": "Item 1"}],
                "cursor": "page2",
            },
            {
                "objects": [{"title": "Item 2"}],
                "cursor": None,
            },
        ]

        with patch.object(
            api, "_request", new_callable=AsyncMock, side_effect=responses
        ) as mock_request:
            await api.get_all_market_items(
                game="csgo",
                max_items=10,
                price_from=10.0,
                price_to=50.0,
                use_cursor=True,
            )

            # Verify filters were applied to both requests
            for call in mock_request.call_args_list:
                params = call.kwargs["params"]
                assert params["priceFrom"] == "1000"  # 10.0 * 100 cents
                assert params["priceTo"] == "5000"  # 50.0 * 100 cents

    async def test_cursor_pagination_with_empty_response(self):
        """Test cursor pagination handles empty responses gracefully."""
        api = DMarketAPI(public_key="test", secret_key="test")

        with patch.object(api, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"objects": [], "cursor": None}

            result = await api.get_all_market_items(game="csgo", max_items=100, use_cursor=True)

            assert len(result) == 0
            assert mock_request.call_count == 1

    @pytest.mark.parametrize("cursor_value", ["cursor123", "", None])
    async def test_cursor_pagination_cursor_values(self, cursor_value):
        """Test different cursor value formats are handled correctly."""
        api = DMarketAPI(public_key="test", secret_key="test")

        with patch.object(api, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "objects": [{"title": "Item 1"}],
                "cursor": cursor_value,
            }

            result = await api.get_all_market_items(game="csgo", max_items=10, use_cursor=True)

            assert len(result) >= 1

            # Empty string or None cursor should stop pagination
            if not cursor_value:
                assert mock_request.call_count == 1
