"""Tests for targets validators module.

This module contains comprehensive tests for:
- validate_attributes: Validation of target attributes
- extract_attributes_from_title: Extraction of attributes from item title
- GAME_IDS: Game ID mapping
"""

from __future__ import annotations

import pytest


class TestValidateAttributes:
    """Tests for validate_attributes function."""

    def test_validate_attributes_none(self) -> None:
        """Test validation with None attributes."""
        from src.dmarket.targets.validators import validate_attributes

        # Should not raise any exception
        validate_attributes("csgo", None)

    def test_validate_attributes_empty(self) -> None:
        """Test validation with empty attributes dict."""
        from src.dmarket.targets.validators import validate_attributes

        # Should not raise any exception
        validate_attributes("csgo", {})

    def test_validate_attributes_valid_float_value(self) -> None:
        """Test validation with valid floatPartValue."""
        from src.dmarket.targets.validators import validate_attributes

        # Valid float values between 0 and 1
        validate_attributes("csgo", {"floatPartValue": "0.5"})
        validate_attributes("csgo", {"floatPartValue": 0.0})
        validate_attributes("csgo", {"floatPartValue": 1.0})
        validate_attributes("csgo", {"floatPartValue": "0"})
        validate_attributes("csgo", {"floatPartValue": "1"})

    def test_validate_attributes_invalid_float_value_range(self) -> None:
        """Test validation with floatPartValue out of range."""
        from src.dmarket.targets.validators import validate_attributes

        # Out of range (negative)
        with pytest.raises(ValueError, match="floatPartValue должен быть от 0 до 1"):
            validate_attributes("csgo", {"floatPartValue": -0.1})

        # Out of range (> 1)
        with pytest.raises(ValueError, match="floatPartValue должен быть от 0 до 1"):
            validate_attributes("csgo", {"floatPartValue": 1.1})

    def test_validate_attributes_invalid_float_value_type(self) -> None:
        """Test validation with non-numeric floatPartValue."""
        from src.dmarket.targets.validators import validate_attributes

        with pytest.raises(ValueError, match="floatPartValue должен быть числом"):
            validate_attributes("csgo", {"floatPartValue": "invalid"})

        with pytest.raises(ValueError, match="floatPartValue должен быть числом"):
            validate_attributes("csgo", {"floatPartValue": "abc"})

    def test_validate_attributes_valid_paint_seed(self) -> None:
        """Test validation with valid paintSeed."""
        from src.dmarket.targets.validators import validate_attributes

        # Valid paint seeds (positive integers)
        validate_attributes("csgo", {"paintSeed": 0})
        validate_attributes("csgo", {"paintSeed": 100})
        validate_attributes("csgo", {"paintSeed": "500"})
        validate_attributes("csgo", {"paintSeed": 999})

    def test_validate_attributes_invalid_paint_seed_negative(self) -> None:
        """Test validation with negative paintSeed."""
        from src.dmarket.targets.validators import validate_attributes

        with pytest.raises(ValueError, match="paintSeed должен быть положительным"):
            validate_attributes("csgo", {"paintSeed": -1})

        with pytest.raises(ValueError, match="paintSeed должен быть положительным"):
            validate_attributes("csgo", {"paintSeed": -100})

    def test_validate_attributes_invalid_paint_seed_type(self) -> None:
        """Test validation with non-integer paintSeed."""
        from src.dmarket.targets.validators import validate_attributes

        with pytest.raises(ValueError, match="paintSeed должен быть целым числом"):
            validate_attributes("csgo", {"paintSeed": "invalid"})

        with pytest.raises(ValueError, match="paintSeed должен быть целым числом"):
            validate_attributes("csgo", {"paintSeed": "abc"})

    def test_validate_attributes_cs2_game(self) -> None:
        """Test validation for CS2 game."""
        from src.dmarket.targets.validators import validate_attributes

        # CS2 should use same validation as CSGO
        validate_attributes("cs2", {"floatPartValue": 0.5})
        validate_attributes("cs2", {"paintSeed": 100})

    def test_validate_attributes_a8db_game(self) -> None:
        """Test validation for a8db (DMarket CSGO ID)."""
        from src.dmarket.targets.validators import validate_attributes

        # a8db should use same validation as CSGO
        validate_attributes("a8db", {"floatPartValue": 0.5})
        validate_attributes("a8db", {"paintSeed": 100})

    def test_validate_attributes_other_game(self) -> None:
        """Test validation for non-CSGO games."""
        from src.dmarket.targets.validators import validate_attributes

        # Other games should not validate CSGO-specific attributes
        validate_attributes("dota2", {"floatPartValue": 100})  # Invalid for CSGO
        validate_attributes("rust", {"paintSeed": -1})  # Invalid for CSGO

    def test_validate_attributes_both_valid(self) -> None:
        """Test validation with both floatPartValue and paintSeed."""
        from src.dmarket.targets.validators import validate_attributes

        validate_attributes("csgo", {"floatPartValue": 0.3, "paintSeed": 500})

    def test_validate_attributes_float_boundary_0(self) -> None:
        """Test validation at float boundary 0."""
        from src.dmarket.targets.validators import validate_attributes

        validate_attributes("csgo", {"floatPartValue": 0})
        validate_attributes("csgo", {"floatPartValue": 0.0})
        validate_attributes("csgo", {"floatPartValue": "0.0"})

    def test_validate_attributes_float_boundary_1(self) -> None:
        """Test validation at float boundary 1."""
        from src.dmarket.targets.validators import validate_attributes

        validate_attributes("csgo", {"floatPartValue": 1})
        validate_attributes("csgo", {"floatPartValue": 1.0})
        validate_attributes("csgo", {"floatPartValue": "1.0"})


class TestExtractAttributesFromTitle:
    """Tests for extract_attributes_from_title function."""

    def test_extract_phase_from_doppler(self) -> None:
        """Test extraction of phase from Doppler knife."""
        from src.dmarket.targets.validators import extract_attributes_from_title

        title = "Karambit | Doppler (Factory New) Phase 2"
        attrs = extract_attributes_from_title("csgo", title)
        assert attrs.get("phase") == "Phase 2"

    def test_extract_phase_1(self) -> None:
        """Test extraction of Phase 1."""
        from src.dmarket.targets.validators import extract_attributes_from_title

        title = "M9 Bayonet | Doppler (Minimal Wear) Phase 1"
        attrs = extract_attributes_from_title("csgo", title)
        assert attrs.get("phase") == "Phase 1"

    def test_extract_phase_3(self) -> None:
        """Test extraction of Phase 3."""
        from src.dmarket.targets.validators import extract_attributes_from_title

        title = "Butterfly Knife | Doppler (FN) Phase 3"
        attrs = extract_attributes_from_title("csgo", title)
        assert attrs.get("phase") == "Phase 3"

    def test_extract_phase_4(self) -> None:
        """Test extraction of Phase 4."""
        from src.dmarket.targets.validators import extract_attributes_from_title

        title = "Bayonet | Doppler (Factory New) Phase 4"
        attrs = extract_attributes_from_title("csgo", title)
        assert attrs.get("phase") == "Phase 4"

    def test_extract_ruby(self) -> None:
        """Test extraction of Ruby phase."""
        from src.dmarket.targets.validators import extract_attributes_from_title

        title = "Karambit | Doppler Ruby (Factory New)"
        attrs = extract_attributes_from_title("csgo", title)
        assert attrs.get("phase") == "Ruby"

    def test_extract_sapphire(self) -> None:
        """Test extraction of Sapphire phase."""
        from src.dmarket.targets.validators import extract_attributes_from_title

        title = "M9 Bayonet | Doppler Sapphire (Minimal Wear)"
        attrs = extract_attributes_from_title("csgo", title)
        assert attrs.get("phase") == "Sapphire"

    def test_extract_black_pearl(self) -> None:
        """Test extraction of Black Pearl phase."""
        from src.dmarket.targets.validators import extract_attributes_from_title

        title = "Butterfly Knife | Doppler Black Pearl (FN)"
        attrs = extract_attributes_from_title("csgo", title)
        assert attrs.get("phase") == "Black Pearl"

    def test_extract_emerald(self) -> None:
        """Test extraction of Emerald phase."""
        from src.dmarket.targets.validators import extract_attributes_from_title

        title = "Bayonet | Gamma Doppler Emerald (Factory New)"
        attrs = extract_attributes_from_title("csgo", title)
        assert attrs.get("phase") == "Emerald"

    def test_extract_no_phase(self) -> None:
        """Test extraction when no phase present."""
        from src.dmarket.targets.validators import extract_attributes_from_title

        title = "AK-47 | Redline (Field-Tested)"
        attrs = extract_attributes_from_title("csgo", title)
        assert "phase" not in attrs

    def test_extract_case_insensitive_phase(self) -> None:
        """Test that phase extraction is case insensitive."""
        from src.dmarket.targets.validators import extract_attributes_from_title

        title = "Karambit | Doppler (Factory New) phase 2"
        attrs = extract_attributes_from_title("csgo", title)
        assert attrs.get("phase") == "Phase 2"

        title = "M9 Bayonet | Doppler (MW) PHASE 3"
        attrs = extract_attributes_from_title("csgo", title)
        assert attrs.get("phase") == "Phase 3"

    def test_extract_cs2_game(self) -> None:
        """Test extraction for CS2 game."""
        from src.dmarket.targets.validators import extract_attributes_from_title

        title = "Karambit | Doppler (Factory New) Phase 2"
        attrs = extract_attributes_from_title("cs2", title)
        assert attrs.get("phase") == "Phase 2"

    def test_extract_a8db_game(self) -> None:
        """Test extraction for a8db (DMarket CSGO ID)."""
        from src.dmarket.targets.validators import extract_attributes_from_title

        title = "Karambit | Doppler Ruby (Factory New)"
        attrs = extract_attributes_from_title("a8db", title)
        assert attrs.get("phase") == "Ruby"

    def test_extract_other_game_returns_empty(self) -> None:
        """Test that extraction for non-CSGO games returns empty dict."""
        from src.dmarket.targets.validators import extract_attributes_from_title

        title = "Karambit | Doppler (Factory New) Phase 2"
        attrs = extract_attributes_from_title("dota2", title)
        assert attrs == {}

        attrs = extract_attributes_from_title("rust", title)
        assert attrs == {}

    def test_ruby_overrides_phase_number(self) -> None:
        """Test that Ruby overrides numeric phase."""
        from src.dmarket.targets.validators import extract_attributes_from_title

        # If both Ruby and Phase N are present, Ruby takes precedence
        title = "Karambit | Doppler Ruby Phase 2 (Factory New)"
        attrs = extract_attributes_from_title("csgo", title)
        assert attrs.get("phase") == "Ruby"


class TestGameIds:
    """Tests for GAME_IDS constant."""

    def test_game_ids_csgo(self) -> None:
        """Test CSGO game ID."""
        from src.dmarket.targets.validators import GAME_IDS

        assert GAME_IDS["csgo"] == "a8db"

    def test_game_ids_dota2(self) -> None:
        """Test Dota 2 game ID."""
        from src.dmarket.targets.validators import GAME_IDS

        assert GAME_IDS["dota2"] == "9a92"

    def test_game_ids_tf2(self) -> None:
        """Test TF2 game ID."""
        from src.dmarket.targets.validators import GAME_IDS

        assert GAME_IDS["tf2"] == "tf2"

    def test_game_ids_rust(self) -> None:
        """Test Rust game ID."""
        from src.dmarket.targets.validators import GAME_IDS

        assert GAME_IDS["rust"] == "rust"

    def test_game_ids_all_keys(self) -> None:
        """Test all expected keys are present."""
        from src.dmarket.targets.validators import GAME_IDS

        expected_keys = {"csgo", "dota2", "tf2", "rust"}
        assert set(GAME_IDS.keys()) == expected_keys


class TestEdgeCases:
    """Tests for edge cases."""

    def test_validate_empty_string_float(self) -> None:
        """Test validation with empty string floatPartValue."""
        from src.dmarket.targets.validators import validate_attributes

        with pytest.raises(ValueError):
            validate_attributes("csgo", {"floatPartValue": ""})

    def test_validate_whitespace_float(self) -> None:
        """Test validation with whitespace floatPartValue."""
        from src.dmarket.targets.validators import validate_attributes

        with pytest.raises(ValueError):
            validate_attributes("csgo", {"floatPartValue": "   "})

    def test_extract_empty_title(self) -> None:
        """Test extraction from empty title."""
        from src.dmarket.targets.validators import extract_attributes_from_title

        attrs = extract_attributes_from_title("csgo", "")
        assert attrs == {}

    def test_extract_unicode_title(self) -> None:
        """Test extraction from title with unicode characters."""
        from src.dmarket.targets.validators import extract_attributes_from_title

        title = "Karambit | Doppler ★ Phase 2 (Factory New)"
        attrs = extract_attributes_from_title("csgo", title)
        assert attrs.get("phase") == "Phase 2"

    def test_validate_float_at_exact_boundary(self) -> None:
        """Test float validation at exact boundaries."""
        from src.dmarket.targets.validators import validate_attributes

        # Exactly 0
        validate_attributes("csgo", {"floatPartValue": 0.0})
        # Exactly 1
        validate_attributes("csgo", {"floatPartValue": 1.0})
        # Just below 0 (should fail)
        with pytest.raises(ValueError):
            validate_attributes("csgo", {"floatPartValue": -0.001})
        # Just above 1 (should fail)
        with pytest.raises(ValueError):
            validate_attributes("csgo", {"floatPartValue": 1.001})

    def test_validate_paint_seed_zero(self) -> None:
        """Test validation with zero paintSeed."""
        from src.dmarket.targets.validators import validate_attributes

        # Zero should be valid (non-negative)
        validate_attributes("csgo", {"paintSeed": 0})

    def test_validate_paint_seed_large(self) -> None:
        """Test validation with very large paintSeed."""
        from src.dmarket.targets.validators import validate_attributes

        # Large values should be valid
        validate_attributes("csgo", {"paintSeed": 999999})
        validate_attributes("csgo", {"paintSeed": 1000000})

    def test_extract_multiple_phases_picks_first(self) -> None:
        """Test extraction when multiple phase patterns match."""
        from src.dmarket.targets.validators import extract_attributes_from_title

        # Title with Phase 2, but Ruby should take precedence
        title = "Karambit | Doppler Ruby Phase 2 Sapphire (Factory New)"
        attrs = extract_attributes_from_title("csgo", title)
        # Ruby comes first in the code, so it should be Ruby
        assert attrs.get("phase") == "Ruby"

    def test_validate_none_attrs_value(self) -> None:
        """Test validation when attrs value is None."""
        from src.dmarket.targets.validators import validate_attributes

        # None value should raise ValueError when trying to convert to float
        with pytest.raises(ValueError, match="floatPartValue должен быть числом"):
            validate_attributes("csgo", {"floatPartValue": None})
