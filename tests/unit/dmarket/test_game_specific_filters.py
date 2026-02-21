"""Tests for Game-Specific Filters module.

Tests for game_specific_filters.py with filters for CS:GO, Dota 2, TF2 and Rust.
"""


from src.dmarket.game_specific_filters import (
    CSGO_BLUE_GEM_PATTERNS,
    CSGO_DOPPLER_PREMIUMS,
    CSGO_FADE_PERCENTAGES,
    CSGO_FLOAT_RANGES,
    CSGO_KATOWICE_2014_STICKERS,
    DOTA2_ETHEREAL_GEMS,
    DOTA2_PRISMATIC_GEMS,
    DOTA2_UNLOCK_STYLES,
    DOTA2_VALUABLE_ITEMS,
    PRESET_FILTERS,
    RUST_LUMINESCENT_PREMIUM,
    RUST_TEMPERED_PREMIUM,
    RUST_TWITCH_DROPS,
    RUST_VALUABLE_SKINS,
    TF2_UNUSUAL_EFFECTS,
    CSGODopplerPhase,
    CSGOFilter,
    # CS:GO
    CSGOWear,
    Dota2Filter,
    # Dota 2
    Dota2Quality,
    Dota2Rarity,
    RustFilter,
    # Rust
    RustItemType,
    RustRarity,
    TF2Class,
    TF2Filter,
    TF2KillstreakTier,
    # TF2
    TF2Quality,
    create_csgo_blue_gem_filter,
    create_csgo_doppler_filter,
    # Functions
    create_csgo_float_filter,
    create_dota2_arcana_filter,
    create_dota2_unusual_courier_filter,
    create_rust_garage_door_filter,
    create_tf2_australium_filter,
    create_tf2_unusual_filter,
    get_preset_filter,
    list_preset_filters,
)


class TestCSGOWear:
    """Tests for CSGOWear enum."""

    def test_factory_new_value(self):
        """Test Factory New value."""
        assert CSGOWear.FACTORY_NEW == "fn"

    def test_minimal_wear_value(self):
        """Test Minimal Wear value."""
        assert CSGOWear.MINIMAL_WEAR == "mw"

    def test_field_tested_value(self):
        """Test Field-Tested value."""
        assert CSGOWear.FIELD_TESTED == "ft"

    def test_well_worn_value(self):
        """Test Well-Worn value."""
        assert CSGOWear.WELL_WORN == "ww"

    def test_battle_scarred_value(self):
        """Test Battle-Scarred value."""
        assert CSGOWear.BATTLE_SCARRED == "bs"


class TestCSGODopplerPhase:
    """Tests for CSGODopplerPhase enum."""

    def test_phase_values(self):
        """Test phase values."""
        assert CSGODopplerPhase.PHASE_1 == "phase1"
        assert CSGODopplerPhase.PHASE_2 == "phase2"
        assert CSGODopplerPhase.PHASE_3 == "phase3"
        assert CSGODopplerPhase.PHASE_4 == "phase4"

    def test_special_phases(self):
        """Test special Doppler phases."""
        assert CSGODopplerPhase.RUBY == "ruby"
        assert CSGODopplerPhase.SAPPHIRE == "sapphire"
        assert CSGODopplerPhase.BLACK_PEARL == "black_pearl"
        assert CSGODopplerPhase.EMERALD == "emerald"


class TestCSGOFloatRanges:
    """Tests for CSGO float ranges."""

    def test_factory_new_range(self):
        """Test FN float range."""
        assert CSGO_FLOAT_RANGES[CSGOWear.FACTORY_NEW] == (0.00, 0.07)

    def test_minimal_wear_range(self):
        """Test MW float range."""
        assert CSGO_FLOAT_RANGES[CSGOWear.MINIMAL_WEAR] == (0.07, 0.15)

    def test_field_tested_range(self):
        """Test FT float range."""
        assert CSGO_FLOAT_RANGES[CSGOWear.FIELD_TESTED] == (0.15, 0.38)

    def test_well_worn_range(self):
        """Test WW float range."""
        assert CSGO_FLOAT_RANGES[CSGOWear.WELL_WORN] == (0.38, 0.45)

    def test_battle_scarred_range(self):
        """Test BS float range."""
        assert CSGO_FLOAT_RANGES[CSGOWear.BATTLE_SCARRED] == (0.45, 1.00)


class TestCSGODopplerPremiums:
    """Tests for Doppler premium multipliers."""

    def test_ruby_premium(self):
        """Test Ruby premium is highest."""
        assert CSGO_DOPPLER_PREMIUMS[CSGODopplerPhase.RUBY] == 6.0

    def test_sapphire_premium(self):
        """Test Sapphire premium."""
        assert CSGO_DOPPLER_PREMIUMS[CSGODopplerPhase.SAPPHIRE] == 5.5

    def test_black_pearl_premium(self):
        """Test Black Pearl premium."""
        assert CSGO_DOPPLER_PREMIUMS[CSGODopplerPhase.BLACK_PEARL] == 4.0

    def test_emerald_premium(self):
        """Test Emerald premium."""
        assert CSGO_DOPPLER_PREMIUMS[CSGODopplerPhase.EMERALD] == 3.0

    def test_phase_1_premium(self):
        """Test Phase 1 premium."""
        assert CSGO_DOPPLER_PREMIUMS[CSGODopplerPhase.PHASE_1] == 1.0

    def test_phase_3_below_base(self):
        """Test Phase 3 is below base price."""
        assert CSGO_DOPPLER_PREMIUMS[CSGODopplerPhase.PHASE_3] == 0.95


class TestCSGOBlueGemPatterns:
    """Tests for Blue Gem pattern IDs."""

    def test_ak47_patterns_exist(self):
        """Test AK-47 patterns exist."""
        assert "ak47_best" in CSGO_BLUE_GEM_PATTERNS
        assert 661 in CSGO_BLUE_GEM_PATTERNS["ak47_best"]
        assert 670 in CSGO_BLUE_GEM_PATTERNS["ak47_best"]

    def test_karambit_patterns_exist(self):
        """Test Karambit patterns exist."""
        assert "karambit_best" in CSGO_BLUE_GEM_PATTERNS
        assert 387 in CSGO_BLUE_GEM_PATTERNS["karambit_best"]

    def test_five_seven_patterns_exist(self):
        """Test Five-Seven patterns exist."""
        assert "five_seven_best" in CSGO_BLUE_GEM_PATTERNS
        assert 278 in CSGO_BLUE_GEM_PATTERNS["five_seven_best"]


class TestCSGOKatowice2014Stickers:
    """Tests for Katowice 2014 sticker premiums."""

    def test_ibuypower_holo_premium(self):
        """Test iBUYPOWER Holo premium."""
        assert CSGO_KATOWICE_2014_STICKERS["iBUYPOWER (Holo)"] == 50.0

    def test_titan_holo_premium(self):
        """Test Titan Holo premium."""
        assert CSGO_KATOWICE_2014_STICKERS["Titan (Holo)"] == 30.0

    def test_reason_gaming_premium(self):
        """Test Reason Gaming Holo premium."""
        assert CSGO_KATOWICE_2014_STICKERS["Reason Gaming (Holo)"] == 20.0


class TestCSGOFadePercentages:
    """Tests for Fade percentage premiums."""

    def test_100_percent_fade(self):
        """Test 100% fade premium."""
        assert CSGO_FADE_PERCENTAGES["100%"] == 1.5

    def test_99_percent_fade(self):
        """Test 99% fade premium."""
        assert CSGO_FADE_PERCENTAGES["99%"] == 1.4

    def test_85_percent_no_premium(self):
        """Test 85% fade has no premium."""
        assert CSGO_FADE_PERCENTAGES["85%"] == 1.0


class TestCSGOFilter:
    """Tests for CSGOFilter dataclass."""

    def test_create_empty_filter(self):
        """Test creating empty filter."""
        filter = CSGOFilter()
        assert filter.wear is None
        assert filter.is_stattrak is None

    def test_create_filter_with_wear(self):
        """Test creating filter with wear."""
        filter = CSGOFilter(wear=CSGOWear.FACTORY_NEW)
        assert filter.wear == CSGOWear.FACTORY_NEW

    def test_create_filter_with_float_range(self):
        """Test creating filter with float range."""
        filter = CSGOFilter(float_min=0.0, float_max=0.01)
        assert filter.float_min == 0.0
        assert filter.float_max == 0.01

    def test_create_filter_with_doppler_phase(self):
        """Test creating filter with Doppler phase."""
        filter = CSGOFilter(doppler_phase=CSGODopplerPhase.RUBY)
        assert filter.doppler_phase == CSGODopplerPhase.RUBY

    def test_filter_matches_wear(self):
        """Test filter matches wear."""
        filter = CSGOFilter(wear=CSGOWear.FACTORY_NEW)
        item = {"wear": "fn", "float_value": 0.03}
        assert filter.matches(item) is True

    def test_filter_rejects_wrong_wear(self):
        """Test filter rejects wrong wear."""
        filter = CSGOFilter(wear=CSGOWear.FACTORY_NEW)
        item = {"wear": "ft", "float_value": 0.25}
        assert filter.matches(item) is False

    def test_filter_matches_float_range(self):
        """Test filter matches float range."""
        filter = CSGOFilter(float_min=0.00, float_max=0.01)
        item = {"wear": "fn", "float_value": 0.005}
        assert filter.matches(item) is True

    def test_filter_rejects_float_too_high(self):
        """Test filter rejects float too high."""
        filter = CSGOFilter(float_min=0.00, float_max=0.01)
        item = {"wear": "fn", "float_value": 0.05}
        assert filter.matches(item) is False

    def test_filter_matches_stattrak(self):
        """Test filter matches StatTrak."""
        filter = CSGOFilter(is_stattrak=True)
        item = {"title": "StatTrak™ AK-47 | Redline", "float_value": 0.25}
        assert filter.matches(item) is True

    def test_filter_rejects_non_stattrak(self):
        """Test filter rejects non-StatTrak."""
        filter = CSGOFilter(is_stattrak=True)
        item = {"title": "AK-47 | Redline", "float_value": 0.25}
        assert filter.matches(item) is False

    def test_filter_matches_souvenir(self):
        """Test filter matches Souvenir."""
        filter = CSGOFilter(is_souvenir=True)
        item = {"title": "Souvenir P250 | Sand Dune", "float_value": 0.5}
        assert filter.matches(item) is True

    def test_filter_matches_doppler_phase(self):
        """Test filter matches Doppler phase."""
        filter = CSGOFilter(doppler_phase=CSGODopplerPhase.RUBY)
        item = {"phase": "Ruby", "float_value": 0.01}
        assert filter.matches(item) is True

    def test_filter_matches_pattern_id(self):
        """Test filter matches pattern ID."""
        filter = CSGOFilter(pattern_ids=[661, 670])
        item = {"pattern_id": 661, "float_value": 0.3}
        assert filter.matches(item) is True

    def test_filter_rejects_wrong_pattern(self):
        """Test filter rejects wrong pattern."""
        filter = CSGOFilter(pattern_ids=[661, 670])
        item = {"pattern_id": 123, "float_value": 0.3}
        assert filter.matches(item) is False

    def test_calculate_premium_doppler_ruby(self):
        """Test premium calculation for Ruby Doppler."""
        filter = CSGOFilter(doppler_phase=CSGODopplerPhase.RUBY)
        item = {"float_value": 0.03}
        premium = filter.calculate_premium(item)
        assert premium == 6.0

    def test_calculate_premium_very_low_float(self):
        """Test premium calculation for very low float."""
        filter = CSGOFilter()
        item = {"float_value": 0.005, "stickers": []}
        premium = filter.calculate_premium(item)
        assert premium == 1.5  # +50% for float < 0.01

    def test_calculate_premium_low_float(self):
        """Test premium calculation for low float."""
        filter = CSGOFilter()
        item = {"float_value": 0.02, "stickers": []}
        premium = filter.calculate_premium(item)
        assert premium == 1.2  # +20% for float < 0.03

    def test_calculate_premium_with_stickers(self):
        """Test premium calculation with stickers."""
        filter = CSGOFilter()
        item = {
            "float_value": 0.1,
            "stickers": [{"name": "iBUYPOWER (Holo)"}],
        }
        premium = filter.calculate_premium(item)
        assert premium > 1.0  # Should have sticker premium


class TestDota2Enums:
    """Tests for Dota 2 enums."""

    def test_dota2_quality_values(self):
        """Test Dota 2 quality values."""
        assert Dota2Quality.ARCANA == "arcana"
        assert Dota2Quality.IMMORTAL == "immortal"
        assert Dota2Quality.UNUSUAL == "unusual"
        assert Dota2Quality.GOLDEN == "golden"
        assert Dota2Quality.GENUINE == "genuine"

    def test_dota2_rarity_values(self):
        """Test Dota 2 rarity values."""
        assert Dota2Rarity.COMMON == "common"
        assert Dota2Rarity.ARCANA == "arcana"
        assert Dota2Rarity.IMMORTAL == "immortal"
        assert Dota2Rarity.LEGENDARY == "legendary"


class TestDota2Gems:
    """Tests for Dota 2 gem premiums."""

    def test_ethereal_flame_premium(self):
        """Test Ethereal Flame premium."""
        assert DOTA2_ETHEREAL_GEMS["Ethereal Flame"] == 3.0

    def test_divine_essence_premium(self):
        """Test Divine Essence premium."""
        assert DOTA2_ETHEREAL_GEMS["Divine Essence"] == 4.0

    def test_legacy_prismatic_premium(self):
        """Test Legacy prismatic premium."""
        assert DOTA2_PRISMATIC_GEMS["Legacy"] == 10.0

    def test_creators_light_premium(self):
        """Test Creator's Light premium."""
        assert DOTA2_PRISMATIC_GEMS["Creator's Light"] == 5.0


class TestDota2ValuableItems:
    """Tests for Dota 2 valuable items."""

    def test_io_arcana_value(self):
        """Test Io Arcana value."""
        assert DOTA2_VALUABLE_ITEMS["Benevolent Companion"] == 200.0

    def test_terrorblade_arcana_value(self):
        """Test Terrorblade Arcana value."""
        assert DOTA2_VALUABLE_ITEMS["Fractal Horns of Inner Abysm"] == 80.0

    def test_juggernaut_arcana_value(self):
        """Test Juggernaut Arcana value."""
        assert DOTA2_VALUABLE_ITEMS["Bladeform Legacy"] == 45.0


class TestDota2UnlockStyles:
    """Tests for Dota 2 unlock styles."""

    def test_second_style_premium(self):
        """Test Second Style premium."""
        assert DOTA2_UNLOCK_STYLES["Second Style"] == 1.5

    def test_third_style_premium(self):
        """Test Third Style premium."""
        assert DOTA2_UNLOCK_STYLES["Third Style"] == 2.0


class TestDota2Filter:
    """Tests for Dota2Filter dataclass."""

    def test_create_empty_filter(self):
        """Test creating empty filter."""
        filter = Dota2Filter()
        assert filter.qualities is None
        assert filter.has_ethereal_gem is False

    def test_create_filter_with_qualities(self):
        """Test creating filter with qualities."""
        filter = Dota2Filter(qualities=[Dota2Quality.ARCANA, Dota2Quality.IMMORTAL])
        assert Dota2Quality.ARCANA in filter.qualities

    def test_filter_matches_quality(self):
        """Test filter matches quality."""
        filter = Dota2Filter(qualities=[Dota2Quality.ARCANA])
        item = {"quality": "arcana", "rarity": "arcana"}
        assert filter.matches(item) is True

    def test_filter_rejects_wrong_quality(self):
        """Test filter rejects wrong quality."""
        filter = Dota2Filter(qualities=[Dota2Quality.ARCANA])
        item = {"quality": "standard", "rarity": "common"}
        assert filter.matches(item) is False

    def test_filter_matches_rarity(self):
        """Test filter matches rarity."""
        filter = Dota2Filter(rarities=[Dota2Rarity.IMMORTAL])
        item = {"quality": "standard", "rarity": "immortal"}
        assert filter.matches(item) is True

    def test_filter_matches_hero(self):
        """Test filter matches hero."""
        filter = Dota2Filter(heroes=["Juggernaut", "Phantom Assassin"])
        item = {"hero": "Juggernaut", "quality": "standard"}
        assert filter.matches(item) is True

    def test_filter_rejects_wrong_hero(self):
        """Test filter rejects wrong hero."""
        filter = Dota2Filter(heroes=["Juggernaut"])
        item = {"hero": "Axe", "quality": "standard"}
        assert filter.matches(item) is False

    def test_filter_matches_ethereal_gem(self):
        """Test filter matches ethereal gem."""
        filter = Dota2Filter(has_ethereal_gem=True)
        item = {"gems": [{"type": "Ethereal Gem", "name": "Ethereal Flame"}]}
        assert filter.matches(item) is True

    def test_filter_rejects_no_ethereal_gem(self):
        """Test filter rejects item without ethereal gem."""
        filter = Dota2Filter(has_ethereal_gem=True)
        item = {"gems": []}
        assert filter.matches(item) is False

    def test_filter_matches_prismatic_gem(self):
        """Test filter matches prismatic gem."""
        filter = Dota2Filter(has_prismatic_gem=True)
        item = {"gems": [{"type": "Prismatic Gem", "name": "Rubiline"}]}
        assert filter.matches(item) is True

    def test_filter_matches_unlocked_style(self):
        """Test filter matches unlocked style."""
        filter = Dota2Filter(has_unlocked_style=True)
        item = {"styles_unlocked": 2}
        assert filter.matches(item) is True

    def test_filter_rejects_no_unlocked_style(self):
        """Test filter rejects item without unlocked style."""
        filter = Dota2Filter(has_unlocked_style=True)
        item = {"styles_unlocked": 0}
        assert filter.matches(item) is False

    def test_calculate_premium_with_ethereal_gem(self):
        """Test premium calculation with ethereal gem."""
        filter = Dota2Filter()
        item = {"gems": [{"name": "Ethereal Flame"}], "styles_unlocked": 0}
        premium = filter.calculate_premium(item)
        assert premium == 3.0

    def test_calculate_premium_with_prismatic_gem(self):
        """Test premium calculation with prismatic gem."""
        filter = Dota2Filter()
        item = {"gems": [{"name": "Legacy"}], "styles_unlocked": 0}
        premium = filter.calculate_premium(item)
        assert premium == 10.0

    def test_calculate_premium_with_styles(self):
        """Test premium calculation with unlocked styles."""
        filter = Dota2Filter()
        item = {"gems": [], "styles_unlocked": 3}
        premium = filter.calculate_premium(item)
        assert premium == 2.0

    def test_calculate_premium_with_valuable_item(self):
        """Test premium calculation with valuable item."""
        filter = Dota2Filter()
        item = {"title": "Benevolent Companion", "gems": [], "styles_unlocked": 0}
        premium = filter.calculate_premium(item)
        assert premium == 20.0  # 200 / 10


class TestTF2Enums:
    """Tests for TF2 enums."""

    def test_tf2_quality_values(self):
        """Test TF2 quality values."""
        assert TF2Quality.UNUSUAL == "unusual"
        assert TF2Quality.STRANGE == "strange"
        assert TF2Quality.VINTAGE == "vintage"
        assert TF2Quality.GENUINE == "genuine"
        assert TF2Quality.COLLECTORS == "collectors"

    def test_tf2_class_values(self):
        """Test TF2 class values."""
        assert TF2Class.SCOUT == "scout"
        assert TF2Class.SOLDIER == "soldier"
        assert TF2Class.PYRO == "pyro"
        assert TF2Class.SPY == "spy"
        assert TF2Class.ALL_CLASS == "all_class"

    def test_tf2_killstreak_tier_values(self):
        """Test TF2 killstreak tier values."""
        assert TF2KillstreakTier.NONE == "none"
        assert TF2KillstreakTier.BASIC == "basic"
        assert TF2KillstreakTier.SPECIALIZED == "specialized"
        assert TF2KillstreakTier.PROFESSIONAL == "professional"


class TestTF2UnusualEffects:
    """Tests for TF2 unusual effects."""

    def test_burning_flames_premium(self):
        """Test Burning Flames premium."""
        assert TF2_UNUSUAL_EFFECTS["Burning Flames"] == 10.0

    def test_scorching_flames_premium(self):
        """Test Scorching Flames premium."""
        assert TF2_UNUSUAL_EFFECTS["Scorching Flames"] == 9.0

    def test_sunbeams_premium(self):
        """Test Sunbeams premium."""
        assert TF2_UNUSUAL_EFFECTS["Sunbeams"] == 8.0

    def test_hearts_premium(self):
        """Test Hearts premium."""
        assert TF2_UNUSUAL_EFFECTS["Hearts"] == 7.0


class TestTF2Filter:
    """Tests for TF2Filter dataclass."""

    def test_create_empty_filter(self):
        """Test creating empty filter."""
        filter = TF2Filter()
        assert filter.qualities is None
        assert filter.is_australium is None

    def test_create_filter_with_qualities(self):
        """Test creating filter with qualities."""
        filter = TF2Filter(qualities=[TF2Quality.UNUSUAL, TF2Quality.STRANGE])
        assert TF2Quality.UNUSUAL in filter.qualities

    def test_create_filter_with_classes(self):
        """Test creating filter with classes."""
        filter = TF2Filter(classes=[TF2Class.SCOUT, TF2Class.SPY])
        assert TF2Class.SCOUT in filter.classes

    def test_create_filter_with_killstreak(self):
        """Test creating filter with killstreak tier."""
        filter = TF2Filter(killstreak_tier=TF2KillstreakTier.PROFESSIONAL)
        assert filter.killstreak_tier == TF2KillstreakTier.PROFESSIONAL

    def test_filter_matches_quality(self):
        """Test filter matches quality."""
        filter = TF2Filter(qualities=[TF2Quality.UNUSUAL])
        item = {"quality": "unusual", "title": "Unusual Team CaptAlgon"}
        assert filter.matches(item) is True

    def test_filter_matches_australium(self):
        """Test filter matches Australium."""
        filter = TF2Filter(is_australium=True)
        item = {"title": "Australium Rocket Launcher", "quality": "strange"}
        assert filter.matches(item) is True

    def test_filter_rejects_non_australium(self):
        """Test filter rejects non-Australium."""
        filter = TF2Filter(is_australium=True)
        item = {"title": "Strange Rocket Launcher", "quality": "strange"}
        assert filter.matches(item) is False

    def test_filter_matches_festive(self):
        """Test filter matches Festive."""
        filter = TF2Filter(is_festive=True)
        item = {"title": "Festive Rocket Launcher", "quality": "unique"}
        assert filter.matches(item) is True

    def test_filter_matches_class(self):
        """Test filter matches class."""
        filter = TF2Filter(classes=[TF2Class.SOLDIER])
        item = {"class": "soldier", "quality": "unique"}
        assert filter.matches(item) is True

    def test_filter_matches_killstreak_tier(self):
        """Test filter matches killstreak tier."""
        filter = TF2Filter(killstreak_tier=TF2KillstreakTier.PROFESSIONAL)
        item = {"killstreak_tier": "professional", "quality": "strange"}
        assert filter.matches(item) is True

    def test_calculate_premium_unusual_effect(self):
        """Test premium calculation with unusual effect."""
        filter = TF2Filter()
        item = {"effect": "Burning Flames", "quality": "unusual", "title": "Team CaptAlgon"}
        premium = filter.calculate_premium(item)
        # Premium should be calculated based on effect
        assert premium >= 1.0

    def test_calculate_premium_australium(self):
        """Test premium calculation for Australium."""
        filter = TF2Filter()
        item = {"title": "Australium Scattergun", "quality": "strange"}
        premium = filter.calculate_premium(item)
        assert premium >= 1.0  # Australium should have some premium

    def test_calculate_premium_killstreak(self):
        """Test premium calculation with killstreak."""
        filter = TF2Filter()
        item = {"killstreak_tier": "professional", "quality": "strange"}
        premium = filter.calculate_premium(item)
        assert premium >= 1.5


class TestRustEnums:
    """Tests for Rust enums."""

    def test_rust_item_type_values(self):
        """Test Rust item type values."""
        assert RustItemType.WEAPON == "weapon"
        assert RustItemType.DOOR == "door"
        assert RustItemType.ARMOR == "armor"
        assert RustItemType.TOOL == "tool"

    def test_rust_rarity_values(self):
        """Test Rust rarity values."""
        assert RustRarity.COMMON == "common"
        assert RustRarity.UNCOMMON == "uncommon"
        assert RustRarity.RARE == "rare"
        assert RustRarity.VERY_RARE == "very_rare"
        assert RustRarity.LIMITED == "limited"


class TestRustFilters:
    """Tests for Rust filter constants."""

    def test_garage_door_neon_value(self):
        """Test Neon Garage Door value."""
        assert RUST_VALUABLE_SKINS["Garage Door"]["Neon Garage Door"] == 150.0

    def test_garage_door_looters_value(self):
        """Test Looter's Garage Door value."""
        assert RUST_VALUABLE_SKINS["Garage Door"]["Looter's Garage Door"] == 100.0

    def test_ak47_skins_exist(self):
        """Test AK-47 skins exist."""
        assert "AK-47" in RUST_VALUABLE_SKINS
        assert len(RUST_VALUABLE_SKINS["AK-47"]) > 0

    def test_luminescent_premium(self):
        """Test Luminescent premium."""
        assert RUST_LUMINESCENT_PREMIUM == 1.5

    def test_tempered_premium(self):
        """Test Tempered premium."""
        assert RUST_TEMPERED_PREMIUM == 1.8

    def test_twitch_drops_exist(self):
        """Test Twitch drops exist."""
        assert len(RUST_TWITCH_DROPS) > 0
        assert "Twitch Rivals" in RUST_TWITCH_DROPS


class TestRustFilter:
    """Tests for RustFilter dataclass."""

    def test_create_empty_filter(self):
        """Test creating empty filter."""
        filter = RustFilter()
        assert filter.item_types is None
        assert filter.is_luminescent is None

    def test_create_filter_with_item_types(self):
        """Test creating filter with item types."""
        filter = RustFilter(item_types=[RustItemType.DOOR])
        assert RustItemType.DOOR in filter.item_types

    def test_create_filter_with_luminescent(self):
        """Test creating filter with luminescent."""
        filter = RustFilter(is_luminescent=True)
        assert filter.is_luminescent is True

    def test_create_filter_with_tempered(self):
        """Test creating filter with tempered."""
        filter = RustFilter(is_tempered=True)
        assert filter.is_tempered is True

    def test_filter_matches_weapon_type(self):
        """Test filter matches weapon type."""
        filter = RustFilter(weapon_types=["ak47", "ak-47", "ak"])
        item = {"title": "Glory AK47", "item_type": "weapon"}
        assert filter.matches(item) is True

    def test_filter_matches_door_type(self):
        """Test filter matches door type."""
        filter = RustFilter(door_types=["Garage Door"])
        item = {"title": "Neon Garage Door", "item_type": "door"}
        assert filter.matches(item) is True

    def test_filter_matches_luminescent(self):
        """Test filter matches luminescent."""
        filter = RustFilter(is_luminescent=True)
        item = {"title": "Luminescent AK47"}
        assert filter.matches(item) is True

    def test_filter_rejects_non_luminescent(self):
        """Test filter rejects non-luminescent when required."""
        filter = RustFilter(is_luminescent=True)
        item = {"title": "Regular AK47"}
        assert filter.matches(item) is False

    def test_filter_matches_tempered(self):
        """Test filter matches tempered."""
        filter = RustFilter(is_tempered=True)
        item = {"title": "Tempered LR-300"}
        assert filter.matches(item) is True

    def test_filter_matches_limited(self):
        """Test filter matches limited item."""
        filter = RustFilter(is_limited=True)
        item = {"title": "Limited Skin", "is_limited": True}
        assert filter.matches(item) is True

    def test_filter_matches_limited_by_title(self):
        """Test filter matches limited item by title."""
        filter = RustFilter(is_limited=True)
        item = {"title": "Limited Edition Skin"}
        assert filter.matches(item) is True

    def test_calculate_premium_luminescent(self):
        """Test premium calculation for luminescent."""
        filter = RustFilter()
        item = {"title": "Luminescent AK47"}
        premium = filter.calculate_premium(item)
        assert premium == RUST_LUMINESCENT_PREMIUM

    def test_calculate_premium_tempered(self):
        """Test premium calculation for tempered."""
        filter = RustFilter()
        item = {"title": "Tempered LR-300"}
        premium = filter.calculate_premium(item)
        assert premium == RUST_TEMPERED_PREMIUM

    def test_calculate_premium_limited(self):
        """Test premium calculation for limited item."""
        filter = RustFilter()
        item = {"title": "Some Skin", "is_limited": True}
        premium = filter.calculate_premium(item)
        assert premium == 1.5

    def test_calculate_premium_twitch_drop(self):
        """Test premium calculation for Twitch drop."""
        filter = RustFilter()
        item = {"title": "Twitch Rivals AK47"}
        premium = filter.calculate_premium(item)
        assert premium >= 2.0  # Twitch Rivals premium


class TestFilterCreationFunctions:
    """Tests for filter creation helper functions."""

    def test_create_csgo_float_filter(self):
        """Test creating CSGO float filter."""
        filter = create_csgo_float_filter(CSGOWear.FACTORY_NEW, 0.00, 0.01)
        assert filter.wear == CSGOWear.FACTORY_NEW
        assert filter.float_min == 0.00
        assert filter.float_max == 0.01

    def test_create_csgo_float_filter_default_range(self):
        """Test creating CSGO float filter with default range."""
        filter = create_csgo_float_filter(CSGOWear.FACTORY_NEW)
        assert filter.wear == CSGOWear.FACTORY_NEW
        # Should use default FN range
        assert filter.float_min is not None
        assert filter.float_max is not None

    def test_create_csgo_doppler_filter(self):
        """Test creating CSGO Doppler filter."""
        filter = create_csgo_doppler_filter(CSGODopplerPhase.RUBY)
        assert filter.doppler_phase == CSGODopplerPhase.RUBY
        assert filter.wear == CSGOWear.FACTORY_NEW  # Dopplers are FN only

    def test_create_csgo_blue_gem_filter(self):
        """Test creating CSGO Blue Gem filter."""
        filter = create_csgo_blue_gem_filter("ak47")
        assert filter.pattern_ids is not None
        assert 661 in filter.pattern_ids

    def test_create_csgo_blue_gem_filter_karambit(self):
        """Test creating CSGO Blue Gem filter for karambit."""
        filter = create_csgo_blue_gem_filter("karambit")
        assert filter.pattern_ids is not None
        assert 387 in filter.pattern_ids

    def test_create_dota2_arcana_filter(self):
        """Test creating Dota 2 Arcana filter."""
        filter = create_dota2_arcana_filter()
        assert Dota2Quality.ARCANA in filter.qualities
        assert Dota2Quality.EXALTED in filter.qualities

    def test_create_dota2_unusual_courier_filter(self):
        """Test creating Dota 2 Unusual Courier filter."""
        filter = create_dota2_unusual_courier_filter()
        assert Dota2Quality.UNUSUAL in filter.qualities
        assert filter.has_ethereal_gem is True
        assert filter.has_prismatic_gem is True
        assert "courier" in filter.item_types

    def test_create_tf2_unusual_filter(self):
        """Test creating TF2 Unusual filter."""
        filter = create_tf2_unusual_filter()
        assert TF2Quality.UNUSUAL in filter.qualities

    def test_create_tf2_unusual_filter_god_tier(self):
        """Test creating TF2 Unusual filter god tier."""
        filter = create_tf2_unusual_filter("god")
        assert TF2Quality.UNUSUAL in filter.qualities
        assert "Burning Flames" in filter.unusual_effects

    def test_create_tf2_australium_filter(self):
        """Test creating TF2 Australium filter."""
        filter = create_tf2_australium_filter()
        assert filter.is_australium is True
        assert filter.is_strange is True

    def test_create_rust_garage_door_filter(self):
        """Test creating Rust Garage Door filter."""
        filter = create_rust_garage_door_filter()
        assert "Garage Door" in filter.door_types
        assert filter.is_tradeable is True


class TestGameFilterPresets:
    """Tests for game filter presets."""

    def test_preset_filters_csgo_exists(self):
        """Test CSGO presets exist."""
        assert "csgo" in PRESET_FILTERS
        assert len(PRESET_FILTERS["csgo"]) > 0

    def test_preset_filters_dota2_exists(self):
        """Test Dota 2 presets exist."""
        assert "dota2" in PRESET_FILTERS
        assert len(PRESET_FILTERS["dota2"]) > 0

    def test_preset_filters_tf2_exists(self):
        """Test TF2 presets exist."""
        assert "tf2" in PRESET_FILTERS
        assert len(PRESET_FILTERS["tf2"]) > 0

    def test_preset_filters_rust_exists(self):
        """Test Rust presets exist."""
        assert "rust" in PRESET_FILTERS
        assert len(PRESET_FILTERS["rust"]) > 0

    def test_get_csgo_presets(self):
        """Test getting CSGO filter presets."""
        presets = list_preset_filters("csgo")
        assert len(presets) > 0
        assert "low_float_fn" in presets
        assert "doppler_ruby" in presets

    def test_get_dota2_presets(self):
        """Test getting Dota 2 filter presets."""
        presets = list_preset_filters("dota2")
        assert len(presets) > 0
        assert "arcana" in presets

    def test_get_tf2_presets(self):
        """Test getting TF2 filter presets."""
        presets = list_preset_filters("tf2")
        assert len(presets) > 0
        assert "unusual_god" in presets
        assert "australium" in presets

    def test_get_rust_presets(self):
        """Test getting Rust filter presets."""
        presets = list_preset_filters("rust")
        assert len(presets) > 0
        assert "garage_doors" in presets

    def test_get_unknown_game_presets(self):
        """Test getting presets for unknown game."""
        presets = list_preset_filters("unknown")
        assert presets == []

    def test_get_preset_filter_csgo(self):
        """Test getting specific CSGO preset filter."""
        filter = get_preset_filter("csgo", "low_float_fn")
        assert filter is not None
        assert isinstance(filter, CSGOFilter)

    def test_get_preset_filter_dota2(self):
        """Test getting specific Dota 2 preset filter."""
        filter = get_preset_filter("dota2", "arcana")
        assert filter is not None
        assert isinstance(filter, Dota2Filter)

    def test_get_preset_filter_tf2(self):
        """Test getting specific TF2 preset filter."""
        filter = get_preset_filter("tf2", "unusual_god")
        assert filter is not None
        assert isinstance(filter, TF2Filter)

    def test_get_preset_filter_rust(self):
        """Test getting specific Rust preset filter."""
        filter = get_preset_filter("rust", "garage_doors")
        assert filter is not None
        assert isinstance(filter, RustFilter)

    def test_get_preset_filter_unknown_preset(self):
        """Test getting unknown preset returns None."""
        filter = get_preset_filter("csgo", "unknown_preset")
        assert filter is None

    def test_get_preset_filter_unknown_game(self):
        """Test getting preset for unknown game returns None."""
        filter = get_preset_filter("unknown_game", "some_preset")
        assert filter is None


class TestPresetFiltersUsage:
    """Tests for using preset filters."""

    def test_csgo_low_float_fn_matches(self):
        """Test CSGO low float FN preset matches correctly."""
        filter = get_preset_filter("csgo", "low_float_fn")
        item = {"wear": "fn", "float_value": 0.005, "stickers": []}
        assert filter.matches(item) is True

    def test_csgo_low_float_fn_rejects_high_float(self):
        """Test CSGO low float FN preset rejects high float."""
        filter = get_preset_filter("csgo", "low_float_fn")
        item = {"wear": "fn", "float_value": 0.05, "stickers": []}
        assert filter.matches(item) is False

    def test_csgo_doppler_ruby_matches(self):
        """Test CSGO Doppler Ruby preset matches."""
        filter = get_preset_filter("csgo", "doppler_ruby")
        item = {"wear": "fn", "phase": "ruby", "float_value": 0.01}
        assert filter.matches(item) is True

    def test_dota2_arcana_matches(self):
        """Test Dota 2 Arcana preset matches."""
        filter = get_preset_filter("dota2", "arcana")
        item = {"quality": "arcana", "rarity": "arcana", "gems": [], "styles_unlocked": 0}
        assert filter.matches(item) is True

    def test_tf2_unusual_god_matches(self):
        """Test TF2 Unusual God preset matches."""
        filter = get_preset_filter("tf2", "unusual_god")
        # Filter needs quality to be in the right format and effect in unusual_effect field
        item = {"quality": "unusual", "unusual_effect": "Burning Flames", "title": "Unusual Team CaptAlgon"}
        assert filter.matches(item) is True

    def test_rust_garage_doors_matches(self):
        """Test Rust Garage Doors preset matches."""
        filter = get_preset_filter("rust", "garage_doors")
        item = {"title": "Neon Garage Door", "item_type": "door"}
        assert filter.matches(item) is True
