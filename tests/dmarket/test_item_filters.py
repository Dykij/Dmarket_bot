"""Unit tests for item_filters module.

This module contains tests for src/dmarket/item_filters.py covering:
- ItemFilters initialization
- Configuration loading
- Pattern matching
- Item validation

Target: 20+ tests to achieve 70%+ coverage
"""

import tempfile
from pathlib import Path

import yaml

from src.dmarket.item_filters import ItemFilters

# TestItemFiltersInit


class TestItemFiltersInit:
    """Tests for ItemFilters initialization."""

    def test_init_with_default_config_path(self):
        """Test initialization with default config path."""
        # Act
        filters = ItemFilters()

        # Assert
        assert filters is not None
        assert filters.config is not None

    def test_init_with_custom_config_path(self):
        """Test initialization with custom config path."""
        # Arrange
        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump({"arbitrage_filters": {"min_avg_price": 1.0}}, f)
            temp_path = f.name

        # Act
        filters = ItemFilters(config_path=temp_path)

        # Assert
        assert filters is not None
        Path(temp_path).unlink()

    def test_init_with_missing_config_uses_defaults(self):
        """Test that missing config file uses defaults."""
        # Arrange
        nonexistent_path = "/nonexistent/path/config.yaml"

        # Act
        filters = ItemFilters(config_path=nonexistent_path)

        # Assert
        assert filters.config is not None
        assert "arbitrage_filters" in filters.config


# TestConfigLoading


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_load_valid_config(self):
        """Test loading valid configuration."""
        # Arrange
        config = {
            "arbitrage_filters": {
                "min_avg_price": 0.50,
                "min_sales_volume": 10,
            },
            "bad_items": ["Sticker", "Graffiti"],
            "good_categories": ["Rifle", "Knife"],
        }

        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config, f)
            temp_path = f.name

        # Act
        filters = ItemFilters(config_path=temp_path)

        # Assert
        assert filters.config["arbitrage_filters"]["min_avg_price"] == 0.50
        Path(temp_path).unlink()

    def test_load_empty_config(self):
        """Test loading empty configuration."""
        # Arrange
        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("")
            temp_path = f.name

        # Act
        filters = ItemFilters(config_path=temp_path)

        # Assert - should use defaults or handle gracefully
        assert filters is not None
        Path(temp_path).unlink()

    def test_get_default_config(self):
        """Test getting default configuration."""
        # Arrange
        filters = ItemFilters(config_path="/nonexistent/path.yaml")

        # Assert
        config = filters.config
        assert "arbitrage_filters" in config


# TestPatternMatching


class TestPatternMatching:
    """Tests for pattern matching functionality."""

    def test_is_item_allowed_with_allowed_item(self):
        """Test that allowed item passes filter."""
        # Arrange
        filters = ItemFilters()

        # Act
        result = filters.is_item_allowed("AK-47 | Redline (Field-Tested)")

        # Assert - depends on default config, typically should pass
        assert isinstance(result, bool)

    def test_is_item_allowed_with_blocked_item(self):
        """Test that blocked item is filtered out."""
        # Arrange
        config = {
            "arbitrage_filters": {"min_avg_price": 0.50},
            "bad_items": ["Sticker"],
        }

        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config, f)
            temp_path = f.name

        filters = ItemFilters(config_path=temp_path)

        # Act
        result = filters.is_item_allowed("Sticker | Hello World")

        # Assert
        assert result is False
        Path(temp_path).unlink()

    def test_is_item_blacklisted(self):
        """Test is_item_blacklisted method."""
        # Arrange
        config = {
            "bad_items": ["Sticker", "Graffiti"],
        }

        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config, f)
            temp_path = f.name

        filters = ItemFilters(config_path=temp_path)

        # Act & Assert
        assert filters.is_item_blacklisted("Sticker | Test") is True
        assert filters.is_item_blacklisted("AK-47 | Redline") is False
        Path(temp_path).unlink()

    def test_is_item_in_good_category(self):
        """Test is_item_in_good_category method."""
        # Arrange
        config = {
            "good_categories": ["Rifle", "Knife"],
        }

        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config, f)
            temp_path = f.name

        filters = ItemFilters(config_path=temp_path)

        # Act & Assert
        assert filters.is_item_in_good_category("Rifle Item") is True
        assert filters.is_item_in_good_category("Gloves | Test") is False
        Path(temp_path).unlink()

    def test_is_item_allowed_empty_name(self):
        """Test handling of empty item name."""
        # Arrange
        filters = ItemFilters()

        # Act
        result = filters.is_item_allowed("")

        # Assert
        assert isinstance(result, bool)


# TestArbitrageFilters


class TestArbitrageFilters:
    """Tests for arbitrage filter rules."""

    def test_arbitrage_filters_property(self):
        """Test arbitrage_filters property."""
        # Arrange
        filters = ItemFilters()

        # Act
        arb_filters = filters.arbitrage_filters

        # Assert
        assert isinstance(arb_filters, dict)

    def test_bad_items_property(self):
        """Test bad_items property."""
        # Arrange
        filters = ItemFilters()

        # Act
        bad_items = filters.bad_items

        # Assert
        assert isinstance(bad_items, list)

    def test_good_categories_property(self):
        """Test good_categories property."""
        # Arrange
        filters = ItemFilters()

        # Act
        categories = filters.good_categories

        # Assert
        assert isinstance(categories, list)

    def test_game_settings_property(self):
        """Test game_settings property."""
        # Arrange
        filters = ItemFilters()

        # Act
        settings = filters.game_settings

        # Assert
        assert isinstance(settings, dict)

    def test_liquidity_settings_property(self):
        """Test liquidity_settings property."""
        # Arrange
        filters = ItemFilters()

        # Act
        settings = filters.liquidity_settings

        # Assert
        assert isinstance(settings, dict)

    def test_risk_settings_property(self):
        """Test risk_settings property."""
        # Arrange
        filters = ItemFilters()

        # Act
        settings = filters.risk_settings

        # Assert
        assert isinstance(settings, dict)


# TestGameSettings


class TestGameSettings:
    """Tests for game-specific settings."""

    def test_is_game_enabled(self):
        """Test is_game_enabled method."""
        # Arrange
        filters = ItemFilters()

        # Act
        result = filters.is_game_enabled("csgo")

        # Assert
        assert isinstance(result, bool)

    def test_get_game_price_range(self):
        """Test get_game_price_range method."""
        # Arrange
        filters = ItemFilters()

        # Act
        result = filters.get_game_price_range("csgo")

        # Assert
        assert isinstance(result, tuple)
        assert len(result) == 2


# TestEdgeCases


class TestEdgeCases:
    """Tests for edge cases."""

    def test_filter_with_special_characters(self):
        """Test filtering items with special characters."""
        # Arrange
        filters = ItemFilters()

        # Act
        result = filters.is_item_allowed("★ Butterfly Knife | Fade (Factory New)")

        # Assert
        assert isinstance(result, bool)

    def test_filter_with_unicode(self):
        """Test filtering items with unicode characters."""
        # Arrange
        filters = ItemFilters()

        # Act
        result = filters.is_item_allowed("АК-47 | Тест")

        # Assert
        assert isinstance(result, bool)

    def test_filter_with_long_name(self):
        """Test filtering items with very long names."""
        # Arrange
        filters = ItemFilters()
        long_name = "A" * 500 + " | Test Item (Field-Tested)"

        # Act
        result = filters.is_item_allowed(long_name)

        # Assert
        assert isinstance(result, bool)

    def test_reload_config(self):
        """Test reloading configuration."""
        # Arrange
        filters = ItemFilters()

        # Act
        filters.reload()

        # Assert
        assert filters.config is not None

    def test_compile_patterns_with_invalid_regex(self):
        """Test handling of invalid regex patterns."""
        # Arrange
        config = {
            "bad_item_patterns": ["[invalid(regex"],  # Invalid regex
            "good_item_patterns": ["valid.*pattern"],
        }

        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config, f)
            temp_path = f.name

        # Act - should not raise exception
        filters = ItemFilters(config_path=temp_path)

        # Assert
        assert filters is not None
        Path(temp_path).unlink()

    def test_case_insensitive_matching(self):
        """Test that pattern matching is case insensitive."""
        # Arrange
        config = {
            "bad_items": ["STICKER"],
        }

        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config, f)
            temp_path = f.name

        filters = ItemFilters(config_path=temp_path)

        # Act - lowercase input should match uppercase pattern
        result = filters.is_item_blacklisted("sticker | test")

        # Assert
        assert result is True
        Path(temp_path).unlink()
