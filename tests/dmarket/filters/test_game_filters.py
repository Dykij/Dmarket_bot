"""Comprehensive tests for game_filters module.

This module tests all game filter classes and the FilterFactory.
Target coverage: 70%+ (currently 15.06%)
"""

import pytest

from src.dmarket.filters.game_filters import (
    BaseGameFilter,
    CS2Filter,
    Dota2Filter,
    FilterFactory,
    RustFilter,
    TF2Filter,
    apply_filters_to_items,
)

# ========================
# BaseGameFilter Tests
# ========================


class TestBaseGameFilter:
    """Tests for BaseGameFilter class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.filter = BaseGameFilter()

    def test_game_name_default(self):
        """Test default game name."""
        assert self.filter.game_name == "base"

    def test_supported_filters_includes_price(self):
        """Test that min/max price are in supported filters."""
        assert "min_price" in self.filter.supported_filters
        assert "max_price" in self.filter.supported_filters

    def test_get_price_value_with_usd_dict(self):
        """Test price extraction from USD dict format."""
        item = {"price": {"USD": 1500}}
        assert self.filter._get_price_value(item) == 1500.0

    def test_get_price_value_with_amount_dict(self):
        """Test price extraction from amount dict format."""
        item = {"price": {"amount": 2500}}
        assert self.filter._get_price_value(item) == 2500.0

    def test_get_price_value_with_direct_int(self):
        """Test price extraction from direct integer."""
        item = {"price": 3000}
        assert self.filter._get_price_value(item) == 3000.0

    def test_get_price_value_missing_price(self):
        """Test price extraction when price is missing."""
        item = {}
        assert self.filter._get_price_value(item) == 0.0

    def test_apply_filters_no_filters(self):
        """Test that items pass when no filters applied."""
        item = {"price": {"USD": 1000}}
        assert self.filter.apply_filters(item, {}) is True

    def test_apply_filters_min_price_pass(self):
        """Test min_price filter with passing value."""
        item = {"price": {"USD": 1500}}
        filters = {"min_price": 1000}
        assert self.filter.apply_filters(item, filters) is True

    def test_apply_filters_min_price_fail(self):
        """Test min_price filter with failing value."""
        item = {"price": {"USD": 500}}
        filters = {"min_price": 1000}
        assert self.filter.apply_filters(item, filters) is False

    def test_apply_filters_max_price_pass(self):
        """Test max_price filter with passing value."""
        item = {"price": {"USD": 500}}
        filters = {"max_price": 1000}
        assert self.filter.apply_filters(item, filters) is True

    def test_apply_filters_max_price_fail(self):
        """Test max_price filter with failing value."""
        item = {"price": {"USD": 1500}}
        filters = {"max_price": 1000}
        assert self.filter.apply_filters(item, filters) is False

    def test_apply_filters_price_range(self):
        """Test both min and max price filters."""
        item = {"price": {"USD": 1500}}
        filters = {"min_price": 1000, "max_price": 2000}
        assert self.filter.apply_filters(item, filters) is True


# ========================
# CS2Filter Tests
# ========================


class TestCS2Filter:
    """Tests for CS2/CSGO filter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.filter = CS2Filter()

    def test_game_name(self):
        """Test CS2 game name."""
        assert self.filter.game_name == "csgo"

    def test_supported_filters_cs2_specific(self):
        """Test CS2-specific filters are included."""
        assert "exterior" in self.filter.supported_filters
        assert "rarity" in self.filter.supported_filters
        assert "quality" in self.filter.supported_filters

    def test_apply_filters_exterior_match(self):
        """Test exterior filter with matching value."""
        item = {"price": {"USD": 1000}, "extra": {"exterior": "Factory New"}}
        filters = {"exterior": "Factory New"}
        assert self.filter.apply_filters(item, filters) is True

    def test_apply_filters_exterior_no_match(self):
        """Test exterior filter with non-matching value."""
        item = {"price": {"USD": 1000}, "extra": {"exterior": "Field-Tested"}}
        filters = {"exterior": "Factory New"}
        assert self.filter.apply_filters(item, filters) is False

    def test_apply_filters_rarity_match(self):
        """Test rarity filter with matching value."""
        item = {"price": {"USD": 1000}, "extra": {"rarity": "Covert"}}
        filters = {"rarity": "Covert"}
        assert self.filter.apply_filters(item, filters) is True

    def test_apply_filters_multiple_cs2_filters(self):
        """Test multiple CS2-specific filters combined."""
        item = {
            "price": {"USD": 1500},
            "extra": {
                "exterior": "Factory New",
                "rarity": "Covert",
                "type": "Rifle",
            },
        }
        filters = {
            "min_price": 1000,
            "exterior": "Factory New",
            "rarity": "Covert",
            "weapon_type": "Rifle",
        }
        assert self.filter.apply_filters(item, filters) is True


# ========================
# Dota2Filter Tests
# ========================


class TestDota2Filter:
    """Tests for Dota 2 filter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.filter = Dota2Filter()

    def test_game_name(self):
        """Test Dota 2 game name."""
        assert self.filter.game_name == "dota2"

    def test_supported_filters_dota2_specific(self):
        """Test Dota 2-specific filters are included."""
        assert "rarity" in self.filter.supported_filters
        assert "hero" in self.filter.supported_filters

    def test_apply_filters_hero_match(self):
        """Test hero filter for Dota 2."""
        item = {"price": {"USD": 1000}, "extra": {"hero": "Pudge"}}
        filters = {"hero": "Pudge"}
        assert self.filter.apply_filters(item, filters) is True


# ========================
# FilterFactory Tests
# ========================


class TestFilterFactory:
    """Tests for FilterFactory."""

    def test_get_filter_csgo(self):
        """Test getting CSGO filter."""
        filter_obj = FilterFactory.get_filter("csgo")
        assert isinstance(filter_obj, CS2Filter)

    def test_get_filter_dota2(self):
        """Test getting Dota 2 filter."""
        filter_obj = FilterFactory.get_filter("dota2")
        assert isinstance(filter_obj, Dota2Filter)

    def test_get_filter_unsupported_game(self):
        """Test error raised for unsupported game."""
        with pytest.raises(ValueError, match="Unsupported game"):
            FilterFactory.get_filter("minecraft")


# ========================
# apply_filters_to_items Tests
# ========================


class TestApplyFiltersToItems:
    """Tests for apply_filters_to_items function."""

    def test_apply_filters_empty_list(self):
        """Test filtering empty list returns empty list."""
        result = apply_filters_to_items([], "csgo", {})
        assert result == []

    def test_apply_filters_no_filters(self):
        """Test that all items pass when no filters applied."""
        items = [
            {"price": {"USD": 1000}, "title": "Item 1"},
            {"price": {"USD": 2000}, "title": "Item 2"},
        ]
        result = apply_filters_to_items(items, "csgo", {})
        assert len(result) == 2

    def test_apply_filters_min_price(self):
        """Test filtering by minimum price."""
        items = [
            {"price": {"USD": 500}, "title": "Cheap"},
            {"price": {"USD": 1500}, "title": "Mid"},
            {"price": {"USD": 2500}, "title": "Expensive"},
        ]
        result = apply_filters_to_items(items, "csgo", {"min_price": 1000})
        assert len(result) == 2

    def test_apply_filters_cs2_exterior(self):
        """Test filtering CSGO items by exterior."""
        items = [
            {
                "price": {"USD": 1000},
                "title": "FN Item",
                "extra": {"exterior": "Factory New"},
            },
            {
                "price": {"USD": 800},
                "title": "FT Item",
                "extra": {"exterior": "Field-Tested"},
            },
        ]
        result = apply_filters_to_items(items, "csgo", {"exterior": "Factory New"})
        assert len(result) == 1
        assert result[0]["title"] == "FN Item"


# ========================
# RustFilter Tests
# ========================


class TestRustFilter:
    """Tests for RustFilter."""

    def test_game_name(self):
        """Test RustFilter has correct game name."""
        filter_obj = RustFilter()
        assert filter_obj.game_name == "rust"

    def test_supported_filters_rust_specific(self):
        """Test RustFilter supports rust-specific filters."""
        filter_obj = RustFilter()
        assert "item_type" in filter_obj.supported_filters
        assert "rarity" in filter_obj.supported_filters

    def test_apply_filters_item_type_match(self):
        """Test filtering by item_type matches."""
        filter_obj = RustFilter()
        item = {"price": {"USD": 1000}, "extra": {"type": "Weapon"}}
        assert filter_obj.apply_filters(item, {"item_type": "Weapon"})

    def test_apply_filters_item_type_no_match(self):
        """Test filtering by item_type doesn't match."""
        filter_obj = RustFilter()
        item = {"price": {"USD": 1000}, "extra": {"type": "Armor"}}
        assert not filter_obj.apply_filters(item, {"item_type": "Weapon"})

    def test_apply_filters_rarity_match(self):
        """Test filtering by rarity matches."""
        filter_obj = RustFilter()
        item = {"price": {"USD": 1000}, "extra": {"rarity": "Rare"}}
        assert filter_obj.apply_filters(item, {"rarity": "Rare"})

    def test_apply_filters_rarity_no_match(self):
        """Test filtering by rarity doesn't match."""
        filter_obj = RustFilter()
        item = {"price": {"USD": 1000}, "extra": {"rarity": "Common"}}
        assert not filter_obj.apply_filters(item, {"rarity": "Rare"})

    def test_apply_filters_multiple_rust_filters(self):
        """Test filtering with multiple rust-specific filters."""
        filter_obj = RustFilter()
        item = {
            "price": {"USD": 1500},
            "extra": {"type": "Weapon", "rarity": "Legendary"},
        }
        filters = {
            "min_price": 1000,
            "item_type": "Weapon",
            "rarity": "Legendary",
        }
        assert filter_obj.apply_filters(item, filters)

    def test_get_filter_rust(self):
        """Test FilterFactory returns RustFilter for rust."""
        filter_obj = FilterFactory.get_filter("rust")
        assert isinstance(filter_obj, RustFilter)


# ========================
# TF2Filter Tests
# ========================


class TestTF2Filter:
    """Tests for TF2Filter."""

    def test_game_name(self):
        """Test TF2Filter has correct game name."""
        filter_obj = TF2Filter()
        assert filter_obj.game_name == "tf2"

    def test_supported_filters_tf2_specific(self):
        """Test TF2Filter supports TF2-specific filters."""
        filter_obj = TF2Filter()
        assert "class" in filter_obj.supported_filters
        assert "quality" in filter_obj.supported_filters
        assert "item_type" in filter_obj.supported_filters
        assert "effect" in filter_obj.supported_filters
        assert "killstreak" in filter_obj.supported_filters
        assert "australium" in filter_obj.supported_filters

    def test_apply_filters_class_match(self):
        """Test filtering by class matches."""
        filter_obj = TF2Filter()
        item = {"price": {"USD": 1000}, "extra": {"class": "Scout"}}
        assert filter_obj.apply_filters(item, {"class": "Scout"})

    def test_apply_filters_class_no_match(self):
        """Test filtering by class doesn't match."""
        filter_obj = TF2Filter()
        item = {"price": {"USD": 1000}, "extra": {"class": "Soldier"}}
        assert not filter_obj.apply_filters(item, {"class": "Scout"})

    def test_apply_filters_quality_match(self):
        """Test filtering by quality matches."""
        filter_obj = TF2Filter()
        item = {"price": {"USD": 1000}, "extra": {"quality": "Unusual"}}
        assert filter_obj.apply_filters(item, {"quality": "Unusual"})

    def test_apply_filters_item_type_match(self):
        """Test filtering by item_type matches."""
        filter_obj = TF2Filter()
        item = {"price": {"USD": 1000}, "extra": {"type": "Hat"}}
        assert filter_obj.apply_filters(item, {"item_type": "Hat"})

    def test_apply_filters_effect_match(self):
        """Test filtering by effect matches."""
        filter_obj = TF2Filter()
        item = {"price": {"USD": 1000}, "extra": {"effect": "Burning Flames"}}
        assert filter_obj.apply_filters(item, {"effect": "Burning Flames"})

    def test_apply_filters_killstreak_match(self):
        """Test filtering by killstreak matches."""
        filter_obj = TF2Filter()
        item = {"price": {"USD": 1000}, "extra": {"killstreak": "Professional"}}
        assert filter_obj.apply_filters(item, {"killstreak": "Professional"})

    def test_apply_filters_australium_true(self):
        """Test filtering by australium=True."""
        filter_obj = TF2Filter()
        item = {"price": {"USD": 1000}, "extra": {"australium": True}}
        assert filter_obj.apply_filters(item, {"australium": True})

    def test_apply_filters_australium_false(self):
        """Test filtering by australium=False."""
        filter_obj = TF2Filter()
        item = {"price": {"USD": 1000}, "extra": {"australium": False}}
        assert not filter_obj.apply_filters(item, {"australium": True})

    def test_apply_filters_multiple_tf2_filters(self):
        """Test filtering with multiple TF2-specific filters."""
        filter_obj = TF2Filter()
        item = {
            "price": {"USD": 2000},
            "extra": {
                "class": "Scout",
                "quality": "Unusual",
                "type": "Hat",
                "effect": "Scorching Flames",
            },
        }
        filters = {
            "min_price": 1500,
            "class": "Scout",
            "quality": "Unusual",
            "effect": "Scorching Flames",
        }
        assert filter_obj.apply_filters(item, filters)

    def test_get_filter_tf2(self):
        """Test FilterFactory returns TF2Filter for tf2."""
        filter_obj = FilterFactory.get_filter("tf2")
        assert isinstance(filter_obj, TF2Filter)
