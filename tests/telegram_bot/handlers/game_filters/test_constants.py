"""Tests for game_filters constants module.

This module tests the constants used for game filters:
- CS2/CSGO constants (categories, rarities, exteriors)
- Dota 2 constants (heroes, rarities, slots)
- Team Fortress 2 constants (classes, qualities, types)
- Rust constants (categories, types, rarities)
- Default filters and game names
"""

from src.telegram_bot.handlers.game_filters.constants import (
    CS2_CATEGORIES,
    CS2_EXTERIORS,
    CS2_RARITIES,
    DEFAULT_FILTERS,
    DOTA2_HEROES,
    DOTA2_RARITIES,
    DOTA2_SLOTS,
    GAME_NAMES,
    RUST_CATEGORIES,
    RUST_RARITIES,
    RUST_TYPES,
    TF2_CLASSES,
    TF2_QUALITIES,
    TF2_TYPES,
)


class TestCS2Constants:
    """Tests for CS2/CSGO constants."""

    def test_cs2_categories_is_list(self):
        """Test that CS2_CATEGORIES is a list."""
        assert isinstance(CS2_CATEGORIES, list)

    def test_cs2_categories_not_empty(self):
        """Test that CS2_CATEGORIES is not empty."""
        assert len(CS2_CATEGORIES) > 0

    def test_cs2_categories_contains_expected_items(self):
        """Test that CS2_CATEGORIES contains expected items."""
        expected = ["Pistol", "Rifle", "Knife", "Gloves"]
        for item in expected:
            assert item in CS2_CATEGORIES

    def test_cs2_rarities_is_list(self):
        """Test that CS2_RARITIES is a list."""
        assert isinstance(CS2_RARITIES, list)

    def test_cs2_rarities_not_empty(self):
        """Test that CS2_RARITIES is not empty."""
        assert len(CS2_RARITIES) > 0

    def test_cs2_rarities_contains_covert(self):
        """Test that CS2_RARITIES contains Covert."""
        assert "Covert" in CS2_RARITIES

    def test_cs2_rarities_contains_contraband(self):
        """Test that CS2_RARITIES contains Contraband."""
        assert "Contraband" in CS2_RARITIES

    def test_cs2_exteriors_is_list(self):
        """Test that CS2_EXTERIORS is a list."""
        assert isinstance(CS2_EXTERIORS, list)

    def test_cs2_exteriors_has_five_items(self):
        """Test that CS2_EXTERIORS has exactly 5 items."""
        assert len(CS2_EXTERIORS) == 5

    def test_cs2_exteriors_contains_factory_new(self):
        """Test that CS2_EXTERIORS contains Factory New."""
        assert "Factory New" in CS2_EXTERIORS

    def test_cs2_exteriors_contains_battle_scarred(self):
        """Test that CS2_EXTERIORS contains Battle-Scarred."""
        assert "Battle-Scarred" in CS2_EXTERIORS


class TestDota2Constants:
    """Tests for Dota 2 constants."""

    def test_dota2_heroes_is_list(self):
        """Test that DOTA2_HEROES is a list."""
        assert isinstance(DOTA2_HEROES, list)

    def test_dota2_heroes_not_empty(self):
        """Test that DOTA2_HEROES is not empty."""
        assert len(DOTA2_HEROES) > 0

    def test_dota2_heroes_contains_popular_heroes(self):
        """Test that DOTA2_HEROES contains popular heroes."""
        expected = ["Pudge", "Invoker", "Axe"]
        for hero in expected:
            assert hero in DOTA2_HEROES

    def test_dota2_rarities_is_list(self):
        """Test that DOTA2_RARITIES is a list."""
        assert isinstance(DOTA2_RARITIES, list)

    def test_dota2_rarities_not_empty(self):
        """Test that DOTA2_RARITIES is not empty."""
        assert len(DOTA2_RARITIES) > 0

    def test_dota2_rarities_contains_arcana(self):
        """Test that DOTA2_RARITIES contains Arcana."""
        assert "Arcana" in DOTA2_RARITIES

    def test_dota2_rarities_contains_immortal(self):
        """Test that DOTA2_RARITIES contains Immortal."""
        assert "Immortal" in DOTA2_RARITIES

    def test_dota2_slots_is_list(self):
        """Test that DOTA2_SLOTS is a list."""
        assert isinstance(DOTA2_SLOTS, list)

    def test_dota2_slots_not_empty(self):
        """Test that DOTA2_SLOTS is not empty."""
        assert len(DOTA2_SLOTS) > 0

    def test_dota2_slots_contains_weapon(self):
        """Test that DOTA2_SLOTS contains Weapon."""
        assert "Weapon" in DOTA2_SLOTS


class TestTF2Constants:
    """Tests for Team Fortress 2 constants."""

    def test_tf2_classes_is_list(self):
        """Test that TF2_CLASSES is a list."""
        assert isinstance(TF2_CLASSES, list)

    def test_tf2_classes_has_ten_items(self):
        """Test that TF2_CLASSES has 10 items (9 classes + All)."""
        assert len(TF2_CLASSES) == 10

    def test_tf2_classes_contains_all_classes(self):
        """Test that TF2_CLASSES contains all expected classes."""
        expected = [
            "Scout",
            "Soldier",
            "Pyro",
            "Demoman",
            "Heavy",
            "Engineer",
            "Medic",
            "Sniper",
            "Spy",
        ]
        for cls in expected:
            assert cls in TF2_CLASSES

    def test_tf2_classes_contains_all_classes_option(self):
        """Test that TF2_CLASSES contains All Classes option."""
        assert "All Classes" in TF2_CLASSES

    def test_tf2_qualities_is_list(self):
        """Test that TF2_QUALITIES is a list."""
        assert isinstance(TF2_QUALITIES, list)

    def test_tf2_qualities_not_empty(self):
        """Test that TF2_QUALITIES is not empty."""
        assert len(TF2_QUALITIES) > 0

    def test_tf2_qualities_contains_unusual(self):
        """Test that TF2_QUALITIES contains Unusual."""
        assert "Unusual" in TF2_QUALITIES

    def test_tf2_qualities_contains_strange(self):
        """Test that TF2_QUALITIES contains Strange."""
        assert "Strange" in TF2_QUALITIES

    def test_tf2_types_is_list(self):
        """Test that TF2_TYPES is a list."""
        assert isinstance(TF2_TYPES, list)

    def test_tf2_types_not_empty(self):
        """Test that TF2_TYPES is not empty."""
        assert len(TF2_TYPES) > 0

    def test_tf2_types_contains_hat(self):
        """Test that TF2_TYPES contains Hat."""
        assert "Hat" in TF2_TYPES


class TestRustConstants:
    """Tests for Rust constants."""

    def test_rust_categories_is_list(self):
        """Test that RUST_CATEGORIES is a list."""
        assert isinstance(RUST_CATEGORIES, list)

    def test_rust_categories_not_empty(self):
        """Test that RUST_CATEGORIES is not empty."""
        assert len(RUST_CATEGORIES) > 0

    def test_rust_categories_contains_weapon(self):
        """Test that RUST_CATEGORIES contains Weapon."""
        assert "Weapon" in RUST_CATEGORIES

    def test_rust_types_is_list(self):
        """Test that RUST_TYPES is a list."""
        assert isinstance(RUST_TYPES, list)

    def test_rust_types_not_empty(self):
        """Test that RUST_TYPES is not empty."""
        assert len(RUST_TYPES) > 0

    def test_rust_rarities_is_list(self):
        """Test that RUST_RARITIES is a list."""
        assert isinstance(RUST_RARITIES, list)

    def test_rust_rarities_not_empty(self):
        """Test that RUST_RARITIES is not empty."""
        assert len(RUST_RARITIES) > 0

    def test_rust_rarities_contains_legendary(self):
        """Test that RUST_RARITIES contains Legendary."""
        assert "Legendary" in RUST_RARITIES


class TestDefaultFilters:
    """Tests for DEFAULT_FILTERS constant."""

    def test_default_filters_is_dict(self):
        """Test that DEFAULT_FILTERS is a dict."""
        assert isinstance(DEFAULT_FILTERS, dict)

    def test_default_filters_has_all_games(self):
        """Test that DEFAULT_FILTERS has all games."""
        expected_games = ["csgo", "dota2", "tf2", "rust"]
        for game in expected_games:
            assert game in DEFAULT_FILTERS

    def test_csgo_filters_has_min_price(self):
        """Test that csgo filters has min_price."""
        assert "min_price" in DEFAULT_FILTERS["csgo"]

    def test_csgo_filters_has_max_price(self):
        """Test that csgo filters has max_price."""
        assert "max_price" in DEFAULT_FILTERS["csgo"]

    def test_csgo_filters_has_float_range(self):
        """Test that csgo filters has float range."""
        assert "float_min" in DEFAULT_FILTERS["csgo"]
        assert "float_max" in DEFAULT_FILTERS["csgo"]

    def test_csgo_filters_has_stattrak(self):
        """Test that csgo filters has stattrak."""
        assert "stattrak" in DEFAULT_FILTERS["csgo"]

    def test_csgo_filters_has_souvenir(self):
        """Test that csgo filters has souvenir."""
        assert "souvenir" in DEFAULT_FILTERS["csgo"]

    def test_dota2_filters_has_hero(self):
        """Test that dota2 filters has hero."""
        assert "hero" in DEFAULT_FILTERS["dota2"]

    def test_dota2_filters_has_tradable(self):
        """Test that dota2 filters has tradable."""
        assert "tradable" in DEFAULT_FILTERS["dota2"]

    def test_tf2_filters_has_class(self):
        """Test that tf2 filters has class."""
        assert "class" in DEFAULT_FILTERS["tf2"]

    def test_tf2_filters_has_australium(self):
        """Test that tf2 filters has australium."""
        assert "australium" in DEFAULT_FILTERS["tf2"]

    def test_rust_filters_has_category(self):
        """Test that rust filters has category."""
        assert "category" in DEFAULT_FILTERS["rust"]

    def test_default_min_price_is_one(self):
        """Test that default min_price is 1.0."""
        for game in ["csgo", "dota2", "tf2", "rust"]:
            assert DEFAULT_FILTERS[game]["min_price"] == 1.0

    def test_default_max_price_is_thousand(self):
        """Test that default max_price is 1000.0."""
        for game in ["csgo", "dota2", "tf2", "rust"]:
            assert DEFAULT_FILTERS[game]["max_price"] == 1000.0


class TestGameNames:
    """Tests for GAME_NAMES constant."""

    def test_game_names_is_dict(self):
        """Test that GAME_NAMES is a dict."""
        assert isinstance(GAME_NAMES, dict)

    def test_game_names_has_all_games(self):
        """Test that GAME_NAMES has all games."""
        expected_games = ["csgo", "dota2", "tf2", "rust"]
        for game in expected_games:
            assert game in GAME_NAMES

    def test_csgo_name_contains_cs2(self):
        """Test that csgo name contains CS2."""
        assert "CS2" in GAME_NAMES["csgo"]

    def test_dota2_name_is_correct(self):
        """Test that dota2 name is correct."""
        assert "Dota 2" in GAME_NAMES["dota2"]

    def test_tf2_name_is_correct(self):
        """Test that tf2 name is correct."""
        assert "Team Fortress 2" in GAME_NAMES["tf2"]

    def test_rust_name_is_correct(self):
        """Test that rust name is correct."""
        assert "Rust" in GAME_NAMES["rust"]


class TestModuleExports:
    """Tests for module __all__ exports."""

    def test_all_exports_are_importable(self):
        """Test that all exports are importable."""
        from src.telegram_bot.handlers.game_filters import constants

        expected_exports = [
            "CS2_CATEGORIES",
            "CS2_EXTERIORS",
            "CS2_RARITIES",
            "DEFAULT_FILTERS",
            "DOTA2_HEROES",
            "DOTA2_RARITIES",
            "DOTA2_SLOTS",
            "GAME_NAMES",
            "RUST_CATEGORIES",
            "RUST_RARITIES",
            "RUST_TYPES",
            "TF2_CLASSES",
            "TF2_QUALITIES",
            "TF2_TYPES",
        ]

        for name in expected_exports:
            assert hasattr(constants, name)
