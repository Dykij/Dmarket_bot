"""Tests for whitelist_config module.

Whitelist is a RECOMMENDATION system, not a strict filter.
Items in whitelist get priority (lower profit threshold), but
all items are still scanned.
"""


from src.dmarket.whitelist_config import (
    GAME_APP_ID_MAP,
    WHITELIST_ITEMS,
    WHITELIST_SETTINGS,
    WhitelistChecker,
    WhitelistMode,
    add_to_whitelist,
    get_game_weight,
    get_whitelist_for_game,
    remove_from_whitelist,
)


class TestWhitelistMode:
    """Tests for WhitelistMode constants."""

    def test_priority_mode_is_default(self):
        """Verify PRIORITY mode is the default (recommendation mode)."""
        assert WHITELIST_SETTINGS["mode"] == WhitelistMode.PRIORITY

    def test_whitelist_modes_exist(self):
        """Verify all whitelist modes are defined."""
        assert WhitelistMode.PRIORITY == "priority"
        assert WhitelistMode.STRICT == "strict"
        assert WhitelistMode.DISABLED == "disabled"


class TestWhitelistItems:
    """Tests for WHITELIST_ITEMS configuration."""

    def test_csgo_items_exist(self):
        """Verify CS:GO/CS2 whitelist has items."""
        assert "730" in WHITELIST_ITEMS
        assert len(WHITELIST_ITEMS["730"]) > 0

    def test_csgo_has_new_cases(self):
        """Verify CS:GO whitelist includes new 2025-2026 cases."""
        csgo_items = WHITELIST_ITEMS["730"]
        # Check for new cases added in improvements
        assert any("Gallery Case" in item for item in csgo_items)
        assert any("Kilowatt Case" in item for item in csgo_items)
        assert any("Revolution Case" in item for item in csgo_items)

    def test_rust_items_exist(self):
        """Verify Rust whitelist has items."""
        assert "252490" in WHITELIST_ITEMS
        assert len(WHITELIST_ITEMS["252490"]) > 0

    def test_dota2_items_exist(self):
        """Verify Dota 2 whitelist has items."""
        assert "570" in WHITELIST_ITEMS
        assert len(WHITELIST_ITEMS["570"]) > 0

    def test_tf2_items_exist(self):
        """Verify TF2 whitelist has items."""
        assert "440" in WHITELIST_ITEMS
        assert len(WHITELIST_ITEMS["440"]) > 0
        # TF2 keys are the most liquid
        assert any("Key" in item for item in WHITELIST_ITEMS["440"])


class TestGameAppIdMap:
    """Tests for GAME_APP_ID_MAP."""

    def test_csgo_mapping(self):
        """Verify CS:GO/CS2 maps to app ID 730."""
        assert GAME_APP_ID_MAP["csgo"] == "730"
        assert GAME_APP_ID_MAP["cs2"] == "730"

    def test_rust_mapping(self):
        """Verify Rust maps to app ID 252490."""
        assert GAME_APP_ID_MAP["rust"] == "252490"

    def test_dota2_mapping(self):
        """Verify Dota 2 maps to app ID 570."""
        assert GAME_APP_ID_MAP["dota2"] == "570"

    def test_tf2_mapping(self):
        """Verify TF2 maps to app ID 440."""
        assert GAME_APP_ID_MAP["tf2"] == "440"


class TestWhitelistChecker:
    """Tests for WhitelistChecker class."""

    def test_is_whitelisted_returns_true_for_whitelist_item(self):
        """Verify whitelisted items are detected."""
        checker = WhitelistChecker()
        item = {"title": "Kilowatt Case"}
        assert checker.is_whitelisted(item, "csgo") is True

    def test_is_whitelisted_returns_false_for_non_whitelist_item(self):
        """Verify non-whitelisted items are not detected."""
        checker = WhitelistChecker()
        item = {"title": "Some Random Skin (Field-Tested)"}
        assert checker.is_whitelisted(item, "csgo") is False

    def test_is_whitelisted_partial_match(self):
        """Verify partial matching works (item name contains whitelist entry)."""
        checker = WhitelistChecker()
        # "AK-47 | Redline" is in whitelist, full title includes wear
        item = {"title": "AK-47 | Redline (Field-Tested)"}
        assert checker.is_whitelisted(item, "csgo") is True

    def test_is_whitelisted_unknown_game(self):
        """Verify unknown games return False."""
        checker = WhitelistChecker()
        item = {"title": "Some Item"}
        assert checker.is_whitelisted(item, "unknown_game") is False

    def test_get_adjusted_profit_margin_whitelist_boost(self):
        """Verify whitelist items get profit margin boost."""
        checker = WhitelistChecker(enable_priority_boost=True, profit_boost_percent=2.0)

        # Whitelist item gets lower threshold
        adjusted = checker.get_adjusted_profit_margin(10.0, is_whitelist=True)
        assert adjusted == 8.0  # 10% - 2% boost

    def test_get_adjusted_profit_margin_non_whitelist(self):
        """Verify non-whitelist items keep original margin."""
        checker = WhitelistChecker(enable_priority_boost=True, profit_boost_percent=2.0)

        # Non-whitelist keeps original
        adjusted = checker.get_adjusted_profit_margin(10.0, is_whitelist=False)
        assert adjusted == 10.0

    def test_get_adjusted_profit_margin_minimum_threshold(self):
        """Verify minimum profit threshold is respected."""
        checker = WhitelistChecker(enable_priority_boost=True, profit_boost_percent=5.0)

        # Should not go below 3%
        adjusted = checker.get_adjusted_profit_margin(5.0, is_whitelist=True)
        assert adjusted == 3.0  # Minimum is 3%

    def test_priority_boost_disabled(self):
        """Verify priority boost can be disabled."""
        checker = WhitelistChecker(enable_priority_boost=False)

        adjusted = checker.get_adjusted_profit_margin(10.0, is_whitelist=True)
        assert adjusted == 10.0  # No boost when disabled


class TestGetWhitelistForGame:
    """Tests for get_whitelist_for_game function."""

    def test_get_csgo_whitelist(self):
        """Verify getting CS:GO whitelist."""
        whitelist = get_whitelist_for_game("csgo")
        assert len(whitelist) > 0
        assert isinstance(whitelist, list)

    def test_get_whitelist_case_insensitive(self):
        """Verify game name is case insensitive."""
        whitelist1 = get_whitelist_for_game("csgo")
        whitelist2 = get_whitelist_for_game("CSGO")
        assert whitelist1 == whitelist2

    def test_get_whitelist_unknown_game(self):
        """Verify unknown game returns empty list."""
        whitelist = get_whitelist_for_game("unknown_game")
        assert whitelist == []


class TestAddRemoveWhitelist:
    """Tests for add_to_whitelist and remove_from_whitelist functions."""

    def test_add_to_whitelist(self):
        """Test adding item to whitelist."""
        # Add a test item
        result = add_to_whitelist("csgo", "Test Item For Testing")
        assert result is True

        # Verify it's in the list
        whitelist = get_whitelist_for_game("csgo")
        assert "Test Item For Testing" in whitelist

        # Cleanup
        remove_from_whitelist("csgo", "Test Item For Testing")

    def test_add_duplicate_to_whitelist(self):
        """Test adding duplicate item returns False."""
        # First add should succeed
        add_to_whitelist("csgo", "Duplicate Test Item")

        # Second add should fail (already exists)
        result = add_to_whitelist("csgo", "Duplicate Test Item")
        assert result is False

        # Cleanup
        remove_from_whitelist("csgo", "Duplicate Test Item")

    def test_add_to_whitelist_unknown_game(self):
        """Test adding to unknown game returns False."""
        result = add_to_whitelist("unknown_game", "Test Item")
        assert result is False

    def test_remove_from_whitelist(self):
        """Test removing item from whitelist."""
        # Add then remove
        add_to_whitelist("csgo", "Item To Remove")
        result = remove_from_whitelist("csgo", "Item To Remove")
        assert result is True

        # Verify it's gone
        whitelist = get_whitelist_for_game("csgo")
        assert "Item To Remove" not in whitelist

    def test_remove_nonexistent_item(self):
        """Test removing non-existent item returns False."""
        result = remove_from_whitelist("csgo", "Non Existent Item 12345")
        assert result is False


class TestGetGameWeight:
    """Tests for get_game_weight function."""

    def test_csgo_weight(self):
        """Verify CS:GO has highest weight."""
        weight = get_game_weight("csgo")
        assert weight == 40

    def test_tf2_weight(self):
        """Verify TF2 weight."""
        weight = get_game_weight("tf2")
        assert weight == 30

    def test_rust_weight(self):
        """Verify Rust weight."""
        weight = get_game_weight("rust")
        assert weight == 20

    def test_dota2_weight(self):
        """Verify Dota 2 weight."""
        weight = get_game_weight("dota2")
        assert weight == 10

    def test_unknown_game_default_weight(self):
        """Verify unknown games get default weight."""
        weight = get_game_weight("unknown_game")
        assert weight == 10  # Default


class TestWhitelistSettings:
    """Tests for WHITELIST_SETTINGS configuration."""

    def test_whitelist_enabled_by_default(self):
        """Verify whitelist is enabled by default."""
        assert WHITELIST_SETTINGS["enabled"] is True

    def test_priority_mode_by_default(self):
        """Verify PRIORITY mode is default (not STRICT)."""
        assert WHITELIST_SETTINGS["mode"] == WhitelistMode.PRIORITY

    def test_profit_boost_configured(self):
        """Verify profit boost is configured."""
        assert "profit_boost_percent" in WHITELIST_SETTINGS
        assert WHITELIST_SETTINGS["profit_boost_percent"] > 0

    def test_liquidity_boost_enabled(self):
        """Verify liquidity boost is enabled."""
        assert WHITELIST_SETTINGS.get("liquidity_boost", False) is True
