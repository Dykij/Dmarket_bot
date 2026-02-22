"""Tests for price anomaly detector module (refactored)."""

from unittest.mock import AsyncMock

import pytest

from src.dmarket.price_anomaly_detector import (
    _calculate_anomaly,
    _compare_item_prices,
    _create_composite_key,
    _extract_csgo_key_parts,
    _extract_price,
    _fetch_market_items,
    _find_anomalies_in_groups,
    _group_items_by_similarity,
    _init_api_client,
    _is_valid_item,
    _sort_and_limit_results,
    find_price_anomalies,
)


@pytest.fixture()
def mock_api_client():
    """Create mock API client."""
    client = AsyncMock()
    client._close_client = AsyncMock()
    return client


@pytest.fixture()
def sample_items():
    """Create sample items for testing."""
    return [
        {
            "title": "AK-47 | Redline (Field-Tested)",
            "price": {"amount": 1000},  # $10.00
        },
        {
            "title": "AK-47 | Redline (Field-Tested)",
            "price": {"amount": 1500},  # $15.00
        },
        {
            "title": "AWP | Dragon Lore (Factory New)",
            "price": {"amount": 50000},  # $500.00
        },
    ]


class TestInitApiClient:
    """Tests for _init_api_client helper."""

    @pytest.mark.asyncio()
    async def test_init_with_existing_client(self, mock_api_client):
        """Test returns existing client without close flag."""
        client, should_close = await _init_api_client(mock_api_client)

        assert client is mock_api_client
        assert should_close is False

    @pytest.mark.asyncio()
    async def test_init_without_client_creates_new(self):
        """Test creates new client when None provided."""
        client, should_close = await _init_api_client(None)

        assert client is not None
        assert should_close is True


class TestFetchMarketItems:
    """Tests for _fetch_market_items helper."""

    @pytest.mark.asyncio()
    async def test_fetch_returns_items_on_success(self, mock_api_client):
        """Test returns items from API response."""
        mock_api_client.get_market_items = AsyncMock(
            return_value={"items": [{"title": "Test"}]}
        )

        items = await _fetch_market_items(mock_api_client, "csgo", 1.0, 100.0)

        assert len(items) == 1
        assert items[0]["title"] == "Test"

    @pytest.mark.asyncio()
    async def test_fetch_returns_empty_list_on_no_items(self, mock_api_client):
        """Test returns empty list when no items."""
        mock_api_client.get_market_items = AsyncMock(return_value={"items": []})

        items = await _fetch_market_items(mock_api_client, "csgo", 1.0, 100.0)

        assert items == []


class TestIsValidItem:
    """Tests for _is_valid_item helper."""

    def test_valid_csgo_item_returns_true(self):
        """Test valid CS:GO item passes validation."""
        item = {"title": "AK-47 | Redline (Field-Tested)"}

        assert _is_valid_item(item, "csgo") is True

    def test_invalid_empty_title_returns_false(self):
        """Test empty title fails validation."""
        item = {"title": ""}

        assert _is_valid_item(item, "csgo") is False

    def test_csgo_sticker_returns_false(self):
        """Test CS:GO sticker is filtered out."""
        item = {"title": "Sticker | Team Liquid"}

        assert _is_valid_item(item, "csgo") is False

    def test_csgo_graffiti_returns_false(self):
        """Test CS:GO graffiti is filtered out."""
        item = {"title": "Graffiti | Hello"}

        assert _is_valid_item(item, "csgo") is False

    def test_dota2_item_returns_true(self):
        """Test Dota 2 item passes validation."""
        item = {"title": "Sticker | Test"}  # "sticker" only filtered for CS:GO

        assert _is_valid_item(item, "dota2") is True


class TestExtractCsgoKeyParts:
    """Tests for _extract_csgo_key_parts helper."""

    def test_standard_weapon_skin(self):
        """Test extracts parts from standard weapon skin."""
        title = "AK-47 | Redline (Field-Tested)"

        parts = _extract_csgo_key_parts(title)

        assert "AK-47 | Redline" in parts
        assert "Field-Tested" in parts

    def test_stattrak_weapon(self):
        """Test detects StatTrak attribute."""
        title = "StatTrak™ AK-47 | Redline (Field-Tested)"

        parts = _extract_csgo_key_parts(title)

        assert "StatTrak" in parts

    def test_souvenir_weapon(self):
        """Test detects Souvenir attribute."""
        title = "Souvenir AK-47 | Redline (Field-Tested)"

        parts = _extract_csgo_key_parts(title)

        assert "Souvenir" in parts

    def test_simple_title(self):
        """Test handles simple title without exterior."""
        title = "CS:GO Case Key"

        parts = _extract_csgo_key_parts(title)

        assert "CS:GO Case Key" in parts
        assert len(parts) == 1


class TestExtractPrice:
    """Tests for _extract_price helper."""

    def test_extract_from_dict_with_amount(self):
        """Test extracts price from dict format."""
        item = {"price": {"amount": 1000}}

        price = _extract_price(item)

        assert price == 10.0

    def test_extract_from_numeric_int(self):
        """Test extracts price from int format."""
        item = {"price": 10}

        price = _extract_price(item)

        assert price == 10.0

    def test_extract_from_numeric_float(self):
        """Test extracts price from float format."""
        item = {"price": 10.5}

        price = _extract_price(item)

        assert price == 10.5

    def test_extract_returns_none_for_missing_price(self):
        """Test returns None when price missing."""
        item = {"title": "Test"}

        price = _extract_price(item)

        assert price is None

    def test_extract_returns_none_for_invalid_format(self):
        """Test returns None for invalid price format."""
        item = {"price": "invalid"}

        price = _extract_price(item)

        assert price is None


class TestCalculateAnomaly:
    """Tests for _calculate_anomaly helper."""

    def test_calculates_anomaly_above_threshold(self):
        """Test calculates anomaly when difference above threshold."""
        low_item = {"price": 10.0, "item": {"title": "Test"}}
        high_item = {"price": 15.0, "item": {"title": "Test"}}

        anomaly = _calculate_anomaly(low_item, high_item, 10.0, "csgo", "test_key")

        assert anomaly is not None
        assert anomaly["buy_price"] == 10.0
        assert anomaly["sell_price"] == 15.0
        assert anomaly["profit_percentage"] == 50.0
        assert anomaly["profit_after_fee"] > 0

    def test_returns_none_below_threshold(self):
        """Test returns None when difference below threshold."""
        low_item = {"price": 10.0, "item": {"title": "Test"}}
        high_item = {"price": 10.5, "item": {"title": "Test"}}

        anomaly = _calculate_anomaly(low_item, high_item, 10.0, "csgo", "test_key")

        assert anomaly is None

    def test_returns_none_when_not_profitable(self):
        """Test returns None when not profitable after fees."""
        low_item = {"price": 10.0, "item": {"title": "Test"}}
        high_item = {"price": 10.1, "item": {"title": "Test"}}

        anomaly = _calculate_anomaly(low_item, high_item, 0.0, "csgo", "test_key")

        assert anomaly is None


class TestSortAndLimitResults:
    """Tests for _sort_and_limit_results helper."""

    def test_sorts_by_profit_percentage_descending(self):
        """Test sorts anomalies by profit percentage."""
        anomalies = [
            {"profit_percentage": 10.0},
            {"profit_percentage": 50.0},
            {"profit_percentage": 25.0},
        ]

        sorted_anomalies = _sort_and_limit_results(anomalies, 10)

        assert sorted_anomalies[0]["profit_percentage"] == 50.0
        assert sorted_anomalies[1]["profit_percentage"] == 25.0
        assert sorted_anomalies[2]["profit_percentage"] == 10.0

    def test_limits_results_to_max(self):
        """Test limits results to max_results."""
        anomalies = [{"profit_percentage": i} for i in range(20)]

        limited = _sort_and_limit_results(anomalies, 5)

        assert len(limited) == 5


class TestGroupItemsBySimilarity:
    """Tests for _group_items_by_similarity helper."""

    def test_groups_same_items_together(self, sample_items):
        """Test groups identical items together."""
        grouped = _group_items_by_similarity(sample_items[:2], "csgo")

        assert len(grouped) == 1
        first_group = next(iter(grouped.values()))
        assert len(first_group) == 2

    def test_separates_different_items(self, sample_items):
        """Test separates different items into different groups."""
        grouped = _group_items_by_similarity(sample_items, "csgo")

        assert len(grouped) == 2

    def test_skips_invalid_items(self):
        """Test skips items without titles."""
        items = [{"title": ""}, {"title": "Test", "price": {"amount": 1000}}]

        grouped = _group_items_by_similarity(items, "csgo")

        assert len(grouped) == 1


class TestFindPriceAnomalies:
    """Tests for main find_price_anomalies function."""

    @pytest.mark.asyncio()
    async def test_finds_anomalies_successfully(self, mock_api_client, sample_items):
        """Test finds price anomalies successfully."""
        mock_api_client.get_market_items = AsyncMock(
            return_value={"items": sample_items}
        )

        anomalies = await find_price_anomalies(
            game="csgo",
            price_diff_percent=10.0,
            dmarket_api=mock_api_client,
        )

        assert len(anomalies) > 0
        assert anomalies[0]["game"] == "csgo"
        assert "profit_percentage" in anomalies[0]

    @pytest.mark.asyncio()
    async def test_returns_empty_list_on_no_items(self, mock_api_client):
        """Test returns empty list when no items avAlgolable."""
        mock_api_client.get_market_items = AsyncMock(return_value={"items": []})

        anomalies = await find_price_anomalies(
            game="csgo",
            dmarket_api=mock_api_client,
        )

        assert anomalies == []

    @pytest.mark.asyncio()
    async def test_handles_api_error_gracefully(self, mock_api_client):
        """Test handles API errors gracefully."""
        mock_api_client.get_market_items = AsyncMock(side_effect=Exception("API Error"))

        anomalies = await find_price_anomalies(
            game="csgo",
            dmarket_api=mock_api_client,
        )

        assert anomalies == []

    @pytest.mark.asyncio()
    async def test_limits_results_to_max(self, mock_api_client):
        """Test limits results to max_results parameter."""
        # Create many anomalies
        items = []
        for i in range(20):
            items.append(
                {
                    "title": "Test Item",
                    "price": {"amount": 1000 + i * 100},
                }
            )

        mock_api_client.get_market_items = AsyncMock(return_value={"items": items})

        anomalies = await find_price_anomalies(
            game="csgo",
            max_results=5,
            price_diff_percent=5.0,
            dmarket_api=mock_api_client,
        )

        assert len(anomalies) <= 5

    @pytest.mark.asyncio()
    async def test_closes_api_client_when_created_internally(self, mock_api_client):
        """Test closes API client when created internally."""
        mock_api_client.get_market_items = AsyncMock(return_value={"items": []})

        # Pass None to trigger internal client creation
        await find_price_anomalies(game="csgo", dmarket_api=None)

        # Note: Can't easily test internal client creation without mocking
        # the create_dmarket_api_client function


class TestCompareItemPrices:
    """Tests for _compare_item_prices helper."""

    def test_compares_all_price_pAlgors(self):
        """Test compares all price pAlgors in list."""
        items_list = [
            {"price": 10.0, "item": {"title": "Test"}},
            {"price": 15.0, "item": {"title": "Test"}},
            {"price": 20.0, "item": {"title": "Test"}},
        ]

        anomalies = _compare_item_prices(items_list, 10.0, "csgo", "test_key")

        # Should have 3 comparisons: (10,15), (10,20), (15,20)
        assert len(anomalies) == 3

    def test_skips_unprofitable_pAlgors(self):
        """Test skips pAlgors that aren't profitable."""
        items_list = [
            {"price": 10.0, "item": {"title": "Test"}},
            {"price": 10.01, "item": {"title": "Test"}},
        ]

        anomalies = _compare_item_prices(items_list, 10.0, "csgo", "test_key")

        assert len(anomalies) == 0


class TestFindAnomaliesInGroups:
    """Tests for _find_anomalies_in_groups helper."""

    def test_processes_multiple_groups(self):
        """Test processes multiple item groups."""
        grouped_items = {
            "item1": [
                {"price": 10.0, "item": {"title": "Item1"}},
                {"price": 15.0, "item": {"title": "Item1"}},
            ],
            "item2": [
                {"price": 20.0, "item": {"title": "Item2"}},
                {"price": 30.0, "item": {"title": "Item2"}},
            ],
        }

        anomalies = _find_anomalies_in_groups(grouped_items, 10.0, "csgo")

        assert len(anomalies) > 0

    def test_skips_single_item_groups(self):
        """Test skips groups with only one item."""
        grouped_items = {
            "item1": [{"price": 10.0, "item": {"title": "Item1"}}],
        }

        anomalies = _find_anomalies_in_groups(grouped_items, 10.0, "csgo")

        assert len(anomalies) == 0


class TestCreateCompositeKey:
    """Tests for _create_composite_key helper."""

    def test_creates_key_for_csgo_item(self):
        """Test creates composite key for CS:GO item."""
        item = {"title": "AK-47 | Redline (Field-Tested)"}

        key = _create_composite_key(item, "csgo")

        assert "AK-47 | Redline" in key
        assert "Field-Tested" in key

    def test_creates_key_for_non_csgo_item(self):
        """Test creates simple key for non-CS:GO item."""
        item = {"title": "Test Item"}

        key = _create_composite_key(item, "dota2")

        assert key == "Test Item"
