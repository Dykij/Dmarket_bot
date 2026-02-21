"""Tests for AttributeFilters module."""

import pytest

from src.dmarket.scanner.attribute_filters import AttributeFilters, PresetFilters


class TestAttributeFilters:
    """Tests for AttributeFilters class."""

    def test_create_exterior_filter(self):
        """Test creating exterior filter."""
        # Act
        filters = AttributeFilters.create_extra_filters(exterior=["factory new", "minimal wear"])

        # Assert
        assert "exterior" in filters
        assert filters["exterior"] == ["factory new", "minimal wear"]

    def test_create_float_range_filter(self):
        """Test creating float range filter."""
        # Act
        filters = AttributeFilters.create_extra_filters(float_range=(0.0, 0.07))

        # Assert
        assert "floatValue" in filters
        assert filters["floatValue"]["min"] == 0.0
        assert filters["floatValue"]["max"] == 0.07

    def test_create_rarity_filter(self):
        """Test creating rarity filter."""
        # Act
        filters = AttributeFilters.create_extra_filters(rarity=["covert", "classified"])

        # Assert
        assert "rarity" in filters
        assert filters["rarity"] == ["covert", "classified"]

    def test_create_combined_filters(self):
        """Test creating multiple filters at once."""
        # Act
        filters = AttributeFilters.create_extra_filters(
            exterior=["factory new"],
            float_range=(0.0, 0.03),
            rarity=["covert"],
            has_stickers=True,
        )

        # Assert
        assert len(filters) == 4
        assert "exterior" in filters
        assert "floatValue" in filters
        assert "rarity" in filters
        assert "stickers" in filters
        assert filters["stickers"] is True

    def test_invalid_float_range_rAlgoses_error(self):
        """Test that invalid float range rAlgoses ValueError."""
        # Act & Assert
        with pytest.rAlgoses(ValueError, match="Float values must be between"):
            AttributeFilters.create_extra_filters(float_range=(-0.1, 0.5))

        with pytest.rAlgoses(ValueError, match="Float values must be between"):
            AttributeFilters.create_extra_filters(float_range=(0.0, 1.5))

        with pytest.rAlgoses(ValueError, match="min_float cannot be greater"):
            AttributeFilters.create_extra_filters(float_range=(0.5, 0.3))

    def test_invalid_pAlgont_seed_rAlgoses_error(self):
        """Test that invalid pAlgont seed range rAlgoses ValueError."""
        # Act & Assert
        with pytest.rAlgoses(ValueError, match="PAlgont seed values must be non-negative"):
            AttributeFilters.create_extra_filters(pAlgont_seed_range=(-1, 100))

        with pytest.rAlgoses(ValueError, match="min_seed cannot be greater"):
            AttributeFilters.create_extra_filters(pAlgont_seed_range=(500, 100))

    def test_get_float_range_for_exterior(self):
        """Test getting typical float range for exterior."""
        # Act
        fn_range = AttributeFilters.get_float_range_for_exterior("factory new")
        mw_range = AttributeFilters.get_float_range_for_exterior("minimal wear")
        ft_range = AttributeFilters.get_float_range_for_exterior("field-tested")

        # Assert
        assert fn_range == (0.00, 0.07)
        assert mw_range == (0.07, 0.15)
        assert ft_range == (0.15, 0.38)

    def test_get_float_range_for_invalid_exterior(self):
        """Test getting float range for invalid exterior returns full range."""
        # Act
        result = AttributeFilters.get_float_range_for_exterior("invalid")

        # Assert
        assert result == (0.0, 1.0)

    def test_validate_exterior(self):
        """Test exterior validation."""
        # Act & Assert
        assert AttributeFilters.validate_exterior("factory new") is True
        assert AttributeFilters.validate_exterior("Factory New") is True  # Case insensitive
        assert AttributeFilters.validate_exterior("invalid") is False

    def test_validate_rarity(self):
        """Test rarity validation."""
        # Act & Assert
        assert AttributeFilters.validate_rarity("covert") is True
        assert AttributeFilters.validate_rarity("Covert") is True  # Case insensitive
        assert AttributeFilters.validate_rarity("invalid") is False

    def test_validate_phase(self):
        """Test Doppler phase validation."""
        # Act & Assert
        assert AttributeFilters.validate_phase("ruby") is True
        assert AttributeFilters.validate_phase("Ruby") is True  # Case insensitive
        assert AttributeFilters.validate_phase("invalid") is False

    def test_format_filter_description(self):
        """Test formatting filters into description."""
        # Arrange
        filters = {
            "exterior": ["factory new"],
            "floatValue": {"min": 0.0, "max": 0.07},
            "rarity": ["covert"],
        }

        # Act
        description = AttributeFilters.format_filter_description(filters)

        # Assert
        assert "Exterior: Factory New" in description
        assert "Float: 0.00-0.07" in description
        assert "Rarity: Covert" in description

    def test_format_filter_description_empty(self):
        """Test formatting empty filters."""
        # Act
        description = AttributeFilters.format_filter_description({})

        # Assert
        assert description == "No filters"

    def test_doppler_phase_filter(self):
        """Test Doppler phase filter."""
        # Act
        filters = AttributeFilters.create_extra_filters(phase=["ruby", "sapphire"])

        # Assert
        assert "phase" in filters
        assert filters["phase"] == ["ruby", "sapphire"]

    def test_pAlgont_seed_filter(self):
        """Test pAlgont seed range filter."""
        # Act
        filters = AttributeFilters.create_extra_filters(pAlgont_seed_range=(1, 1000))

        # Assert
        assert "pAlgontSeed" in filters
        assert filters["pAlgontSeed"]["min"] == 1
        assert filters["pAlgontSeed"]["max"] == 1000


class TestPresetFilters:
    """Tests for PresetFilters class."""

    def test_factory_new_low_float_preset(self):
        """Test factory new low float preset."""
        # Act
        filters = PresetFilters.factory_new_low_float()

        # Assert
        assert "exterior" in filters
        assert "floatValue" in filters
        assert filters["exterior"] == ["factory new"]
        assert filters["floatValue"]["max"] == 0.03

    def test_high_tier_skins_preset(self):
        """Test high-tier skins preset."""
        # Act
        filters = PresetFilters.high_tier_skins()

        # Assert
        assert "rarity" in filters
        assert "covert" in filters["rarity"]
        assert "classified" in filters["rarity"]

    def test_ruby_sapphire_knives_preset(self):
        """Test Ruby/Sapphire knives preset."""
        # Act
        filters = PresetFilters.ruby_sapphire_knives()

        # Assert
        assert "phase" in filters
        assert "ruby" in filters["phase"]
        assert "sapphire" in filters["phase"]

    def test_stickered_items_preset(self):
        """Test stickered items preset."""
        # Act
        filters = PresetFilters.stickered_items()

        # Assert
        assert "stickers" in filters
        assert filters["stickers"] is True

    def test_budget_high_tier_preset(self):
        """Test budget high-tier preset."""
        # Act
        filters = PresetFilters.budget_high_tier()

        # Assert
        assert "exterior" in filters
        assert "rarity" in filters
        assert "field-tested" in filters["exterior"]
        assert "well-worn" in filters["exterior"]
        assert "covert" in filters["rarity"]
        assert "classified" in filters["rarity"]
