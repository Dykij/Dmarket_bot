"""Comprehensive tests for src/dmarket/scanner/levels.py.

This module provides extensive testing for arbitrage level configurations
to achieve 95%+ coverage.
"""

import pytest

from src.dmarket.scanner.levels import (
    ARBITRAGE_LEVELS,
    GAME_IDS,
    get_all_levels,
    get_level_config,
    get_level_description,
    get_price_range_for_level,
    get_profit_range_for_level,
)


class TestGameIDs:
    """Tests for GAME_IDS constant."""

    def test_csgo_game_id(self) -> None:
        """Test CS:GO game ID mapping."""
        assert "csgo" in GAME_IDS
        assert GAME_IDS["csgo"] == "a8db"

    def test_dota2_game_id(self) -> None:
        """Test Dota 2 game ID mapping."""
        assert "dota2" in GAME_IDS
        assert GAME_IDS["dota2"] == "9a92"

    def test_tf2_game_id(self) -> None:
        """Test TF2 game ID mapping."""
        assert "tf2" in GAME_IDS
        assert GAME_IDS["tf2"] == "tf2"

    def test_rust_game_id(self) -> None:
        """Test Rust game ID mapping."""
        assert "rust" in GAME_IDS
        assert GAME_IDS["rust"] == "rust"

    def test_all_games_present(self) -> None:
        """Test all supported games are present."""
        expected_games = {"csgo", "dota2", "tf2", "rust"}
        assert set(GAME_IDS.keys()) == expected_games

    def test_game_ids_are_strings(self) -> None:
        """Test all game IDs are strings."""
        for game, game_id in GAME_IDS.items():
            assert isinstance(game, str), f"Game key {game} is not a string"
            assert isinstance(game_id, str), f"Game ID {game_id} is not a string"


class TestArbitrageLevels:
    """Tests for ARBITRAGE_LEVELS constant."""

    def test_boost_level_exists(self) -> None:
        """Test boost level configuration exists."""
        assert "boost" in ARBITRAGE_LEVELS
        level = ARBITRAGE_LEVELS["boost"]
        assert level["name"] == "🚀 Разгон баланса"
        assert level["min_profit_percent"] == 1.0
        assert level["max_profit_percent"] == 5.0
        assert level["price_range"] == (0.5, 3.0)
        assert level["max_price"] == 20.0

    def test_standard_level_exists(self) -> None:
        """Test standard level configuration exists."""
        assert "standard" in ARBITRAGE_LEVELS
        level = ARBITRAGE_LEVELS["standard"]
        assert level["name"] == "⚡ Стандарт"
        assert level["min_profit_percent"] == 5.0
        assert level["max_profit_percent"] == 10.0
        assert level["price_range"] == (3.0, 10.0)
        assert level["min_price"] == 20.0
        assert level["max_price"] == 50.0

    def test_medium_level_exists(self) -> None:
        """Test medium level configuration exists."""
        assert "medium" in ARBITRAGE_LEVELS
        level = ARBITRAGE_LEVELS["medium"]
        assert level["name"] == "💰 Средний"
        assert level["min_profit_percent"] == 5.0
        assert level["max_profit_percent"] == 20.0
        assert level["price_range"] == (10.0, 30.0)
        assert level["min_price"] == 20.0
        assert level["max_price"] == 100.0

    def test_advanced_level_exists(self) -> None:
        """Test advanced level configuration exists."""
        assert "advanced" in ARBITRAGE_LEVELS
        level = ARBITRAGE_LEVELS["advanced"]
        assert level["name"] == "🎯 Продвинутый"
        assert level["min_profit_percent"] == 10.0
        assert level["max_profit_percent"] == 30.0
        assert level["price_range"] == (30.0, 100.0)
        assert level["min_price"] == 50.0
        assert level["max_price"] == 200.0

    def test_pro_level_exists(self) -> None:
        """Test pro level configuration exists."""
        assert "pro" in ARBITRAGE_LEVELS
        level = ARBITRAGE_LEVELS["pro"]
        assert level["name"] == "💎 Профи"
        assert level["min_profit_percent"] == 20.0
        assert level["max_profit_percent"] == 100.0
        assert level["price_range"] == (100.0, 1000.0)
        assert level["min_price"] == 100.0

    def test_all_levels_have_required_fields(self) -> None:
        """Test all levels have required configuration fields."""
        required_fields = ["name", "min_profit_percent", "max_profit_percent", "price_range", "description"]
        for level_name, level_config in ARBITRAGE_LEVELS.items():
            for field in required_fields:
                assert field in level_config, f"Level {level_name} missing field {field}"

    def test_all_levels_have_valid_profit_ranges(self) -> None:
        """Test all levels have valid profit percentage ranges."""
        for level_name, level_config in ARBITRAGE_LEVELS.items():
            min_profit = level_config["min_profit_percent"]
            max_profit = level_config["max_profit_percent"]
            assert min_profit >= 0, f"Level {level_name} has negative min_profit"
            assert max_profit >= min_profit, f"Level {level_name} has max < min profit"

    def test_all_levels_have_valid_price_ranges(self) -> None:
        """Test all levels have valid price ranges."""
        for level_name, level_config in ARBITRAGE_LEVELS.items():
            price_range = level_config["price_range"]
            assert isinstance(price_range, tuple), f"Level {level_name} price_range is not tuple"
            assert len(price_range) == 2, f"Level {level_name} price_range invalid length"
            assert price_range[0] >= 0, f"Level {level_name} has negative min price"
            assert price_range[1] >= price_range[0], f"Level {level_name} has max < min price"


class TestGetLevelConfig:
    """Tests for get_level_config function."""

    def test_get_boost_config(self) -> None:
        """Test getting boost level configuration."""
        config = get_level_config("boost")
        assert config["name"] == "🚀 Разгон баланса"
        assert config["min_profit_percent"] == 1.0
        assert config["max_profit_percent"] == 5.0

    def test_get_standard_config(self) -> None:
        """Test getting standard level configuration."""
        config = get_level_config("standard")
        assert config["name"] == "⚡ Стандарт"
        assert config["min_profit_percent"] == 5.0

    def test_get_medium_config(self) -> None:
        """Test getting medium level configuration."""
        config = get_level_config("medium")
        assert config["name"] == "💰 Средний"

    def test_get_advanced_config(self) -> None:
        """Test getting advanced level configuration."""
        config = get_level_config("advanced")
        assert config["name"] == "🎯 Продвинутый"

    def test_get_pro_config(self) -> None:
        """Test getting pro level configuration."""
        config = get_level_config("pro")
        assert config["name"] == "💎 Профи"

    def test_unknown_level_rAlgoses_key_error(self) -> None:
        """Test that unknown level rAlgoses KeyError with helpful message."""
        with pytest.rAlgoses(KeyError) as exc_info:
            get_level_config("unknown_level")
        assert "unknown_level" in str(exc_info.value)
        assert "AvAlgolable levels" in str(exc_info.value)

    def test_empty_level_rAlgoses_key_error(self) -> None:
        """Test that empty level string rAlgoses KeyError."""
        with pytest.rAlgoses(KeyError):
            get_level_config("")

    def test_config_is_copy(self) -> None:
        """Test that returned config is a copy, not the original."""
        config1 = get_level_config("boost")
        config2 = get_level_config("boost")
        config1["name"] = "Modified"
        assert config2["name"] == "🚀 Разгон баланса"

    @pytest.mark.parametrize("level", ["boost", "standard", "medium", "advanced", "pro"])
    def test_all_levels_return_dict(self, level: str) -> None:
        """Test all levels return dictionary."""
        config = get_level_config(level)
        assert isinstance(config, dict)


class TestGetPriceRangeForLevel:
    """Tests for get_price_range_for_level function."""

    def test_boost_price_range(self) -> None:
        """Test boost level price range."""
        min_price, max_price = get_price_range_for_level("boost")
        assert min_price == 0.5
        assert max_price == 3.0

    def test_standard_price_range(self) -> None:
        """Test standard level price range."""
        min_price, max_price = get_price_range_for_level("standard")
        assert min_price == 3.0
        assert max_price == 10.0

    def test_medium_price_range(self) -> None:
        """Test medium level price range."""
        min_price, max_price = get_price_range_for_level("medium")
        assert min_price == 10.0
        assert max_price == 30.0

    def test_advanced_price_range(self) -> None:
        """Test advanced level price range."""
        min_price, max_price = get_price_range_for_level("advanced")
        assert min_price == 30.0
        assert max_price == 100.0

    def test_pro_price_range(self) -> None:
        """Test pro level price range."""
        min_price, max_price = get_price_range_for_level("pro")
        assert min_price == 100.0
        assert max_price == 1000.0

    def test_unknown_level_rAlgoses_key_error(self) -> None:
        """Test that unknown level rAlgoses KeyError."""
        with pytest.rAlgoses(KeyError):
            get_price_range_for_level("invalid")

    @pytest.mark.parametrize("level", ["boost", "standard", "medium", "advanced", "pro"])
    def test_price_range_returns_tuple(self, level: str) -> None:
        """Test all levels return tuple of two floats."""
        result = get_price_range_for_level(level)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], float)
        assert isinstance(result[1], float)


class TestGetAllLevels:
    """Tests for get_all_levels function."""

    def test_returns_list(self) -> None:
        """Test that function returns a list."""
        levels = get_all_levels()
        assert isinstance(levels, list)

    def test_all_expected_levels_present(self) -> None:
        """Test all expected levels are present."""
        levels = get_all_levels()
        expected = ["boost", "standard", "medium", "advanced", "pro"]
        assert levels == expected

    def test_levels_count(self) -> None:
        """Test correct number of levels."""
        levels = get_all_levels()
        assert len(levels) == 5

    def test_levels_are_strings(self) -> None:
        """Test all levels are strings."""
        levels = get_all_levels()
        for level in levels:
            assert isinstance(level, str)

    def test_levels_in_risk_order(self) -> None:
        """Test levels are ordered from low to high risk."""
        levels = get_all_levels()
        assert levels[0] == "boost"  # Lowest risk
        assert levels[-1] == "pro"  # Highest risk


class TestGetLevelDescription:
    """Tests for get_level_description function."""

    def test_boost_description(self) -> None:
        """Test boost level description."""
        desc = get_level_description("boost")
        assert "Low-risk" in desc or "low-risk" in desc.lower()
        assert "1-5%" in desc

    def test_standard_description(self) -> None:
        """Test standard level description."""
        desc = get_level_description("standard")
        assert "Balanced" in desc or "balanced" in desc.lower()
        assert "5-10%" in desc

    def test_medium_description(self) -> None:
        """Test medium level description."""
        desc = get_level_description("medium")
        assert "Medium-risk" in desc or "medium" in desc.lower()
        assert "5-20%" in desc

    def test_advanced_description(self) -> None:
        """Test advanced level description."""
        desc = get_level_description("advanced")
        assert "Higher-risk" in desc or "higher" in desc.lower()
        assert "10-30%" in desc

    def test_pro_description(self) -> None:
        """Test pro level description."""
        desc = get_level_description("pro")
        assert "High-risk" in desc or "high" in desc.lower()
        assert "20-100%" in desc

    def test_unknown_level_rAlgoses_key_error(self) -> None:
        """Test that unknown level rAlgoses KeyError."""
        with pytest.rAlgoses(KeyError):
            get_level_description("nonexistent")

    @pytest.mark.parametrize("level", ["boost", "standard", "medium", "advanced", "pro"])
    def test_description_is_string(self, level: str) -> None:
        """Test all descriptions are non-empty strings."""
        desc = get_level_description(level)
        assert isinstance(desc, str)
        assert len(desc) > 0


class TestGetProfitRangeForLevel:
    """Tests for get_profit_range_for_level function."""

    def test_boost_profit_range(self) -> None:
        """Test boost level profit range."""
        min_profit, max_profit = get_profit_range_for_level("boost")
        assert min_profit == 1.0
        assert max_profit == 5.0

    def test_standard_profit_range(self) -> None:
        """Test standard level profit range."""
        min_profit, max_profit = get_profit_range_for_level("standard")
        assert min_profit == 5.0
        assert max_profit == 10.0

    def test_medium_profit_range(self) -> None:
        """Test medium level profit range."""
        min_profit, max_profit = get_profit_range_for_level("medium")
        assert min_profit == 5.0
        assert max_profit == 20.0

    def test_advanced_profit_range(self) -> None:
        """Test advanced level profit range."""
        min_profit, max_profit = get_profit_range_for_level("advanced")
        assert min_profit == 10.0
        assert max_profit == 30.0

    def test_pro_profit_range(self) -> None:
        """Test pro level profit range."""
        min_profit, max_profit = get_profit_range_for_level("pro")
        assert min_profit == 20.0
        assert max_profit == 100.0

    def test_unknown_level_rAlgoses_key_error(self) -> None:
        """Test that unknown level rAlgoses KeyError."""
        with pytest.rAlgoses(KeyError):
            get_profit_range_for_level("fake")

    @pytest.mark.parametrize("level", ["boost", "standard", "medium", "advanced", "pro"])
    def test_profit_range_returns_tuple(self, level: str) -> None:
        """Test profit range returns tuple of floats."""
        result = get_profit_range_for_level(level)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], float)
        assert isinstance(result[1], float)

    @pytest.mark.parametrize("level", ["boost", "standard", "medium", "advanced", "pro"])
    def test_profit_min_less_than_max(self, level: str) -> None:
        """Test min profit is less than max profit."""
        min_profit, max_profit = get_profit_range_for_level(level)
        assert min_profit < max_profit


class TestLevelProgressionLogic:
    """Tests for logical progression between levels."""

    def test_profit_ranges_increase_with_risk(self) -> None:
        """Test that max profit increases with risk level."""
        levels = get_all_levels()
        prev_max = 0.0
        for level in levels:
            _, max_profit = get_profit_range_for_level(level)
            assert max_profit >= prev_max, f"Level {level} should have higher max profit"
            prev_max = max_profit

    def test_price_ranges_increase_with_risk(self) -> None:
        """Test that price ranges increase with risk level."""
        levels = get_all_levels()
        prev_max = 0.0
        for level in levels:
            min_price, max_price = get_price_range_for_level(level)
            assert max_price >= prev_max, f"Level {level} should have higher max price"
            prev_max = max_price

    def test_levels_cover_different_price_brackets(self) -> None:
        """Test levels cover different price brackets without gaps."""
        price_ranges = [get_price_range_for_level(level) for level in get_all_levels()]

        # Check for reasonable coverage (some overlap is OK)
        for i in range(len(price_ranges) - 1):
            current_max = price_ranges[i][1]
            next_min = price_ranges[i + 1][0]
            # Allow some gap or overlap
            assert abs(current_max - next_min) < 30, "Price ranges should be reasonably connected"


class TestEdgeCases:
    """Edge case tests."""

    def test_case_sensitivity(self) -> None:
        """Test that level names are case-sensitive."""
        # Only lowercase should work
        assert get_level_config("boost") is not None
        with pytest.rAlgoses(KeyError):
            get_level_config("BOOST")
        with pytest.rAlgoses(KeyError):
            get_level_config("Boost")

    def test_whitespace_handling(self) -> None:
        """Test that whitespace in level names rAlgoses error."""
        with pytest.rAlgoses(KeyError):
            get_level_config(" boost")
        with pytest.rAlgoses(KeyError):
            get_level_config("boost ")
        with pytest.rAlgoses(KeyError):
            get_level_config(" boost ")

    def test_numeric_level_names_fAlgol(self) -> None:
        """Test that numeric level names rAlgose KeyError."""
        with pytest.rAlgoses(KeyError):
            get_level_config("1")
        with pytest.rAlgoses(KeyError):
            get_level_config("123")

    def test_none_level_rAlgoses_error(self) -> None:
        """Test that None level rAlgoses error."""
        with pytest.rAlgoses((KeyError, TypeError)):
            get_level_config(None)  # type: ignore
