"""Unit tests for dmarket/scanner/filters.py module.

This module tests:
- ScannerFilters class
- create_filter_key function
- Price extraction and filtering
- Profit filtering
- Item filtering with blacklist/whitelist
"""

from unittest.mock import MagicMock

from src.dmarket.scanner.filters import (
    ScannerFilters,
    create_filter_key,
)


class TestScannerFiltersInit:
    """Tests for ScannerFilters initialization."""

    def test_init_without_item_filters(self):
        """Test initialization without item filters."""
        filters = ScannerFilters()
        assert filters.item_filters is None

    def test_init_with_item_filters(self):
        """Test initialization with item filters."""
        mock_filters = MagicMock()
        filters = ScannerFilters(item_filters=mock_filters)
        assert filters.item_filters is mock_filters

    def test_item_filters_property_setter(self):
        """Test item_filters property setter."""
        filters = ScannerFilters()
        mock_filters = MagicMock()
        filters.item_filters = mock_filters
        assert filters.item_filters is mock_filters

    def test_item_filters_property_set_none(self):
        """Test setting item_filters to None."""
        mock_filters = MagicMock()
        filters = ScannerFilters(item_filters=mock_filters)
        filters.item_filters = None
        assert filters.item_filters is None


class TestIsItemAllowed:
    """Tests for is_item_allowed method."""

    def test_is_item_allowed_no_filters(self):
        """Test item allowed when no filters set."""
        filters = ScannerFilters()
        assert filters.is_item_allowed("Any Item Name") is True

    def test_is_item_allowed_with_filters_allowed(self):
        """Test item allowed with filters that allow it."""
        mock_filters = MagicMock()
        mock_filters.is_item_allowed.return_value = True
        filters = ScannerFilters(item_filters=mock_filters)

        result = filters.is_item_allowed("Test Item")
        assert result is True
        mock_filters.is_item_allowed.assert_called_once_with("Test Item")

    def test_is_item_allowed_with_filters_denied(self):
        """Test item denied by filters."""
        mock_filters = MagicMock()
        mock_filters.is_item_allowed.return_value = False
        filters = ScannerFilters(item_filters=mock_filters)

        result = filters.is_item_allowed("Blacklisted Item")
        assert result is False


class TestIsItemBlacklisted:
    """Tests for is_item_blacklisted method."""

    def test_is_item_blacklisted_no_filters(self):
        """Test item not blacklisted when no filters set."""
        filters = ScannerFilters()
        assert filters.is_item_blacklisted("Any Item") is False

    def test_is_item_blacklisted_true(self):
        """Test item is blacklisted."""
        mock_filters = MagicMock()
        mock_filters.is_item_blacklisted.return_value = True
        filters = ScannerFilters(item_filters=mock_filters)

        result = filters.is_item_blacklisted("Bad Item")
        assert result is True

    def test_is_item_blacklisted_false(self):
        """Test item is not blacklisted."""
        mock_filters = MagicMock()
        mock_filters.is_item_blacklisted.return_value = False
        filters = ScannerFilters(item_filters=mock_filters)

        result = filters.is_item_blacklisted("Good Item")
        assert result is False


class TestApplyFilters:
    """Tests for apply_filters method."""

    def test_apply_filters_empty_list(self):
        """Test applying filters to empty list."""
        filters = ScannerFilters()
        result = filters.apply_filters([])
        assert result == []

    def test_apply_filters_no_item_filters(self):
        """Test applying filters when no item filters set."""
        filters = ScannerFilters()
        items = [{"title": "Item 1"}, {"title": "Item 2"}]
        result = filters.apply_filters(items)
        assert result == items

    def test_apply_filters_with_item_filters(self):
        """Test applying filters with item filters."""
        mock_filters = MagicMock()
        mock_filters.filter_items.return_value = [{"title": "Item 1"}]
        filters = ScannerFilters(item_filters=mock_filters)

        items = [{"title": "Item 1"}, {"title": "Item 2"}]
        result = filters.apply_filters(items, game="csgo")

        assert len(result) == 1
        mock_filters.filter_items.assert_called_once_with(items, "csgo")

    def test_apply_filters_no_game(self):
        """Test applying filters without game parameter."""
        mock_filters = MagicMock()
        mock_filters.filter_items.return_value = []
        filters = ScannerFilters(item_filters=mock_filters)

        items = [{"title": "Item 1"}]
        filters.apply_filters(items)

        mock_filters.filter_items.assert_called_once_with(items, None)


class TestFilterByPrice:
    """Tests for filter_by_price method."""

    def test_filter_by_price_no_limits(self):
        """Test filter with no price limits."""
        filters = ScannerFilters()
        items = [
            {"title": "Item 1", "price": {"USD": "500"}},
            {"title": "Item 2", "price": {"USD": "1500"}},
        ]
        result = filters.filter_by_price(items)
        assert len(result) == 2

    def test_filter_by_price_min_only(self):
        """Test filter with minimum price only."""
        filters = ScannerFilters()
        items = [
            {"title": "Item 1", "price": 5.0},
            {"title": "Item 2", "price": 15.0},
        ]
        result = filters.filter_by_price(items, min_price=10.0)
        assert len(result) == 1
        assert result[0]["title"] == "Item 2"

    def test_filter_by_price_max_only(self):
        """Test filter with maximum price only."""
        filters = ScannerFilters()
        items = [
            {"title": "Item 1", "price": 5.0},
            {"title": "Item 2", "price": 15.0},
        ]
        result = filters.filter_by_price(items, max_price=10.0)
        assert len(result) == 1
        assert result[0]["title"] == "Item 1"

    def test_filter_by_price_range(self):
        """Test filter with price range."""
        filters = ScannerFilters()
        items = [
            {"title": "Item 1", "price": 1.0},
            {"title": "Item 2", "price": 5.0},
            {"title": "Item 3", "price": 15.0},
        ]
        result = filters.filter_by_price(items, min_price=3.0, max_price=10.0)
        assert len(result) == 1
        assert result[0]["title"] == "Item 2"

    def test_filter_by_price_missing_price(self):
        """Test filter skips items without price."""
        filters = ScannerFilters()
        items = [
            {"title": "Item 1"},
            {"title": "Item 2", "price": {"USD": "1000"}},
        ]
        result = filters.filter_by_price(items, min_price=5.0)
        assert len(result) == 1

    def test_filter_by_price_buy_price_field(self):
        """Test filter using buy_price field."""
        filters = ScannerFilters()
        items = [
            {"title": "Item 1", "buy_price": 3.0},
            {"title": "Item 2", "buy_price": 15.0},
        ]
        result = filters.filter_by_price(items, min_price=5.0)
        assert len(result) == 1
        assert result[0]["title"] == "Item 2"

    def test_filter_by_price_invalid_price(self):
        """Test filter handles invalid price formats."""
        filters = ScannerFilters()
        items = [
            {"title": "Item 1", "price": "invalid"},
            {"title": "Item 2", "price": {"USD": "1000"}},
        ]
        result = filters.filter_by_price(items, min_price=5.0)
        assert len(result) == 1


class TestFilterByProfit:
    """Tests for filter_by_profit method."""

    def test_filter_by_profit_no_limits(self):
        """Test filter with no profit limits."""
        filters = ScannerFilters()
        items = [
            {"title": "Item 1", "profit_percent": 5.0},
            {"title": "Item 2", "profit_percent": 30.0},
        ]
        result = filters.filter_by_profit(items)
        assert len(result) == 2

    def test_filter_by_profit_min_only(self):
        """Test filter with minimum profit only."""
        filters = ScannerFilters()
        items = [
            {"title": "Item 1", "profit_percent": 5.0},
            {"title": "Item 2", "profit_percent": 30.0},
        ]
        result = filters.filter_by_profit(items, min_profit_percent=10.0)
        assert len(result) == 1
        assert result[0]["title"] == "Item 2"

    def test_filter_by_profit_max_only(self):
        """Test filter with maximum profit only."""
        filters = ScannerFilters()
        items = [
            {"title": "Item 1", "profit_percent": 5.0},
            {"title": "Item 2", "profit_percent": 30.0},
        ]
        result = filters.filter_by_profit(items, max_profit_percent=20.0)
        assert len(result) == 1
        assert result[0]["title"] == "Item 1"

    def test_filter_by_profit_range(self):
        """Test filter with profit range."""
        filters = ScannerFilters()
        items = [
            {"title": "Item 1", "profit_percent": 5.0},
            {"title": "Item 2", "profit_percent": 15.0},
            {"title": "Item 3", "profit_percent": 30.0},
        ]
        result = filters.filter_by_profit(
            items, min_profit_percent=10.0, max_profit_percent=20.0
        )
        assert len(result) == 1
        assert result[0]["title"] == "Item 2"

    def test_filter_by_profit_missing_field(self):
        """Test filter with missing profit_percent field."""
        filters = ScannerFilters()
        items = [
            {"title": "Item 1"},  # No profit_percent, defaults to 0.0
            {"title": "Item 2", "profit_percent": 15.0},
        ]
        result = filters.filter_by_profit(items, min_profit_percent=10.0)
        assert len(result) == 1
        assert result[0]["title"] == "Item 2"


class TestGetItemPrice:
    """Tests for _get_item_price static method."""

    def test_get_item_price_dict_usd(self):
        """Test extracting price from USD dict."""
        item = {"price": {"USD": "10.0"}}
        filters = ScannerFilters()
        price = filters._get_item_price(item)
        assert price == 10.0

    def test_get_item_price_dict_usd_lowercase(self):
        """Test extracting price from lowercase usd dict."""
        item = {"price": {"usd": "10.0"}}
        filters = ScannerFilters()
        price = filters._get_item_price(item)
        assert price == 10.0

    def test_get_item_price_numeric(self):
        """Test extracting numeric price."""
        item = {"price": 10.0}
        filters = ScannerFilters()
        price = filters._get_item_price(item)
        assert price == 10.0

    def test_get_item_price_buy_price(self):
        """Test extracting from buy_price field."""
        item = {"buy_price": 15.0}
        filters = ScannerFilters()
        price = filters._get_item_price(item)
        assert price == 15.0

    def test_get_item_price_no_price(self):
        """Test with no price field."""
        item = {"title": "Item"}
        filters = ScannerFilters()
        price = filters._get_item_price(item)
        assert price is None

    def test_get_item_price_invalid_format(self):
        """Test with invalid price format."""
        item = {"price": "invalid"}
        filters = ScannerFilters()
        price = filters._get_item_price(item)
        assert price is None


class TestCreateFilterKey:
    """Tests for create_filter_key function."""

    def test_create_filter_key_basic(self):
        """Test basic filter key creation."""
        key = create_filter_key("csgo", "standard")
        assert key == "filter:csgo:standard"

    def test_create_filter_key_with_extra_filters(self):
        """Test filter key with extra filters."""
        key = create_filter_key(
            "csgo",
            "standard",
            extra_filters={"min_price": 10, "max_price": 100},
        )
        assert "filter:csgo:standard" in key
        assert "max_price=100" in key
        assert "min_price=10" in key

    def test_create_filter_key_extra_filters_sorted(self):
        """Test that extra filters are sorted for consistency."""
        key1 = create_filter_key(
            "csgo",
            "standard",
            extra_filters={"z": 1, "a": 2, "m": 3},
        )
        key2 = create_filter_key(
            "csgo",
            "standard",
            extra_filters={"m": 3, "z": 1, "a": 2},
        )
        assert key1 == key2

    def test_create_filter_key_no_extra_filters(self):
        """Test filter key with None extra filters."""
        key = create_filter_key("dota2", "boost", extra_filters=None)
        assert key == "filter:dota2:boost"

    def test_create_filter_key_empty_extra_filters(self):
        """Test filter key with empty extra filters."""
        key = create_filter_key("tf2", "medium", extra_filters={})
        assert key == "filter:tf2:medium"

    def test_create_filter_key_different_games(self):
        """Test filter keys for different games are different."""
        key1 = create_filter_key("csgo", "standard")
        key2 = create_filter_key("dota2", "standard")
        assert key1 != key2

    def test_create_filter_key_different_levels(self):
        """Test filter keys for different levels are different."""
        key1 = create_filter_key("csgo", "standard")
        key2 = create_filter_key("csgo", "boost")
        assert key1 != key2


class TestScannerFiltersIntegration:
    """Integration tests for ScannerFilters."""

    def test_filter_items_complex_scenario(self):
        """Test filtering items with multiple conditions."""
        mock_filters = MagicMock()
        mock_filters.filter_items.return_value = [
            {"title": "Item 1", "price": 5.0, "profit_percent": 15.0},
            {"title": "Item 2", "price": 15.0, "profit_percent": 25.0},
            {"title": "Item 3", "price": 25.0, "profit_percent": 5.0},
        ]

        filters = ScannerFilters(item_filters=mock_filters)
        items = [
            {"title": "Item 1", "price": 5.0, "profit_percent": 15.0},
            {"title": "Item 2", "price": 15.0, "profit_percent": 25.0},
            {"title": "Item 3", "price": 25.0, "profit_percent": 5.0},
            {"title": "Blocked Item", "price": 10.0, "profit_percent": 50.0},
        ]

        # Apply item filters
        filtered = filters.apply_filters(items, game="csgo")

        # Then apply price filter
        filtered = filters.filter_by_price(filtered, min_price=5.0, max_price=20.0)

        # Then apply profit filter
        filtered = filters.filter_by_profit(filtered, min_profit_percent=10.0)

        assert len(filtered) == 2  # Items 1 and 2 pass all filters

    def test_chAlgoned_filtering(self):
        """Test chAlgoning multiple filter operations."""
        filters = ScannerFilters()

        items = [
            {"title": "A", "price": 5.0, "profit_percent": 20.0},
            {"title": "B", "price": 15.0, "profit_percent": 10.0},
            {"title": "C", "price": 25.0, "profit_percent": 30.0},
            {"title": "D", "price": 35.0, "profit_percent": 5.0},
        ]

        # ChAlgon filters
        result = filters.filter_by_price(items, min_price=10.0, max_price=30.0)
        result = filters.filter_by_profit(result, min_profit_percent=15.0)

        assert len(result) == 1
        assert result[0]["title"] == "C"
