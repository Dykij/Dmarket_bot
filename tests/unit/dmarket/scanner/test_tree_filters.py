"""Tests for tree_filters module.

Tests ensure that:
- Tree filters are generated correctly for each game
- Filters adapt to arbitrage mode (low, medium, high)
- Filter effectiveness estimates are reasonable
"""

import json

import pytest

from src.dmarket.scanner.tree_filters import (
    get_filter_description,
    get_filter_effectiveness,
    get_tree_filters_for_game,
)


class TestTreeFilters:
    """Tests for tree filters generation."""

    def test_csgo_high_mode_filters(self):
        """Test CS:GO filters for high mode (knives, gloves only)."""
        filters_json = get_tree_filters_for_game("csgo", "high")
        assert filters_json is not None

        filters = json.loads(filters_json)
        assert "category" in filters
        assert "weapon_knife" in filters["category"]
        assert "weapon_gloves" in filters["category"]
        assert len(filters["category"]) == 2  # Only knives and gloves

    def test_csgo_medium_mode_filters(self):
        """Test CS:GO filters for medium mode (knives, gloves, rifles)."""
        filters_json = get_tree_filters_for_game("csgo", "medium")
        assert filters_json is not None

        filters = json.loads(filters_json)
        assert "category" in filters
        assert "weapon_knife" in filters["category"]
        assert "weapon_gloves" in filters["category"]
        assert "weapon_rifle" in filters["category"]
        assert len(filters["category"]) == 3

    def test_csgo_low_mode_filters(self):
        """Test CS:GO filters for low mode (includes pistols, SMGs)."""
        filters_json = get_tree_filters_for_game("csgo", "low")
        assert filters_json is not None

        filters = json.loads(filters_json)
        assert "category" in filters
        assert len(filters["category"]) >= 4  # More categories for volume

    def test_dota2_high_mode_filters(self):
        """Test Dota 2 filters for high mode (Arcana, Immortal only)."""
        filters_json = get_tree_filters_for_game("dota2", "high")
        assert filters_json is not None

        filters = json.loads(filters_json)
        assert "rarity" in filters
        assert "arcana" in filters["rarity"]
        assert "immortal" in filters["rarity"]
        assert len(filters["rarity"]) == 2

    def test_dota2_medium_mode_filters(self):
        """Test Dota 2 filters for medium mode (adds Mythical)."""
        filters_json = get_tree_filters_for_game("dota2", "medium")
        assert filters_json is not None

        filters = json.loads(filters_json)
        assert "rarity" in filters
        assert "mythical" in filters["rarity"]
        assert len(filters["rarity"]) == 3

    def test_tf2_filters(self):
        """Test TF2 filters focus on quality."""
        filters_json = get_tree_filters_for_game("tf2", "high")
        assert filters_json is not None

        filters = json.loads(filters_json)
        assert "quality" in filters
        assert "unusual" in filters["quality"]

    def test_rust_filters(self):
        """Test Rust filters focus on categories."""
        filters_json = get_tree_filters_for_game("rust", "medium")
        assert filters_json is not None

        filters = json.loads(filters_json)
        assert "category" in filters
        assert "weapon" in filters["category"]

    def test_unsupported_game_returns_none(self):
        """Test unsupported game returns None."""
        filters_json = get_tree_filters_for_game("unsupported_game", "medium")
        assert filters_json is None

    def test_filter_description_csgo(self):
        """Test filter description generation for CS:GO."""
        desc = get_filter_description("csgo", "high")
        assert "CSGO" in desc
        assert "category" in desc
        assert "weapon_knife" in desc

    def test_filter_description_dota2(self):
        """Test filter description generation for Dota 2."""
        desc = get_filter_description("dota2", "high")
        assert "DOTA2" in desc
        assert "rarity" in desc
        assert "arcana" in desc

    def test_filter_description_unsupported(self):
        """Test filter description for unsupported game."""
        desc = get_filter_description("unknown", "medium")
        assert "no specific filters" in desc

    def test_filter_effectiveness_csgo_high(self):
        """Test effectiveness estimate for CS:GO high mode."""
        effectiveness = get_filter_effectiveness("csgo", "high")
        assert 0.6 <= effectiveness <= 0.8  # 60-80% reduction expected

    def test_filter_effectiveness_dota2_high(self):
        """Test effectiveness estimate for Dota 2 high mode."""
        effectiveness = get_filter_effectiveness("dota2", "high")
        assert 0.7 <= effectiveness <= 0.9  # 70-90% reduction expected

    def test_filter_effectiveness_decreases_with_mode(self):
        """Test that effectiveness decreases from high to low mode."""
        high_eff = get_filter_effectiveness("csgo", "high")
        medium_eff = get_filter_effectiveness("csgo", "medium")
        low_eff = get_filter_effectiveness("csgo", "low")

        assert high_eff > medium_eff > low_eff

    def test_filter_effectiveness_unsupported_game(self):
        """Test effectiveness for unsupported game returns 0."""
        effectiveness = get_filter_effectiveness("unknown", "medium")
        assert effectiveness == 0.0

    @pytest.mark.parametrize(
        "game,mode",
        [
            ("csgo", "low"),
            ("csgo", "medium"),
            ("csgo", "high"),
            ("dota2", "low"),
            ("dota2", "medium"),
            ("dota2", "high"),
            ("tf2", "low"),
            ("tf2", "medium"),
            ("tf2", "high"),
            ("rust", "low"),
            ("rust", "medium"),
            ("rust", "high"),
        ],
    )
    def test_all_supported_combinations(self, game: str, mode: str):
        """Test all supported game/mode combinations produce valid JSON."""
        filters_json = get_tree_filters_for_game(game, mode)
        assert filters_json is not None

        # Should be valid JSON
        filters = json.loads(filters_json)
        assert isinstance(filters, dict)
        assert len(filters) > 0

    def test_json_format_compatibility(self):
        """Test that generated JSON is compatible with DMarket API format."""
        filters_json = get_tree_filters_for_game("csgo", "high")
        filters = json.loads(filters_json)

        # DMarket API expects format: {"key": ["value1", "value2"]}
        for key, values in filters.items():
            assert isinstance(values, list)
            assert len(values) > 0
            assert all(isinstance(v, str) for v in values)

    def test_case_insensitive_game_code(self):
        """Test that game codes work in different cases."""
        filters_upper = get_tree_filters_for_game("CSGO", "high")
        filters_lower = get_tree_filters_for_game("csgo", "high")
        filters_mixed = get_tree_filters_for_game("CsGo", "high")

        assert filters_upper == filters_lower == filters_mixed
