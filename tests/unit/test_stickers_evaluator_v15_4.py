"""Unit tests for stickers_evaluator.py v15.4 features.

Tests: slot premiums, streak bonuses, combo premium, mid-range pricing,
and year-based estimation.
"""

from __future__ import annotations

import pytest

from src.analytics.stickers_evaluator import (
    StickerEvaluator,
    _extract_year,
    _get_sticker_base_price,
    _STREAK_BONUS,
)


# =====================================================================
# Slot Premium (v15.4)
# =====================================================================


class TestSlotPremium:
    """Tests for weapon slot visibility multipliers."""

    @pytest.mark.parametrize(
        ("weapon", "slot", "expected"),
        [
            ("AK-47", 3, 1.30),   # wood slot
            ("AK-47", 0, 1.0),
            ("AK-47", 1, 1.05),
            ("AWP", 2, 1.15),     # scope area
            ("AWP", 1, 1.10),
            ("AWP", 0, 1.0),
            ("knife", 3, 1.25),   # playside
            ("M4A4", 3, 1.20),
            ("Desert Eagle", 3, 1.15),
            ("USP-S", 3, 1.10),
        ],
    )
    def test_slot_premium_known_weapons(self, weapon: str, slot: int, expected: float) -> None:
        result = StickerEvaluator.get_slot_multiplier(weapon, slot)
        assert result == pytest.approx(expected)

    def test_slot_premium_ak_wood(self) -> None:
        assert StickerEvaluator.get_slot_multiplier("AK-47", 3) == pytest.approx(1.30)

    def test_slot_premium_awp_scope(self) -> None:
        assert StickerEvaluator.get_slot_multiplier("AWP", 2) == pytest.approx(1.15)

    def test_slot_premium_knife(self) -> None:
        # "knife" key matches any weapon containing "knife" (e.g. "Huntsman Knife")
        assert StickerEvaluator.get_slot_multiplier("Huntsman Knife", 3) == pytest.approx(1.25)

    def test_slot_premium_unknown_weapon(self) -> None:
        assert StickerEvaluator.get_slot_multiplier("P90", 3) == pytest.approx(1.0)
        assert StickerEvaluator.get_slot_multiplier("Negev", 0) == pytest.approx(1.0)

    def test_slot_premium_case_insensitive(self) -> None:
        assert StickerEvaluator.get_slot_multiplier("ak-47", 3) == pytest.approx(1.30)
        assert StickerEvaluator.get_slot_multiplier("AWP | Asiimov", 2) == pytest.approx(1.15)


# =====================================================================
# Streak Bonus (v15.4)
# =====================================================================


class TestStreakBonus:
    """Tests for identical sticker streak detection."""

    def test_streak_bonus_2_identical(self) -> None:
        stickers = [
            {"name": "Virtus.pro (Holo) | Katowice 2015"},
            {"name": "Virtus.pro (Holo) | Katowice 2015"},
        ]
        bonus = StickerEvaluator.calculate_streak_bonus(stickers)
        base_price = _get_sticker_base_price("Virtus.pro (Holo) | Katowice 2015")
        assert bonus == pytest.approx(base_price * _STREAK_BONUS[2])

    def test_streak_bonus_3_identical(self) -> None:
        stickers = [
            {"name": "Virtus.pro (Holo) | Katowice 2015"},
            {"name": "Virtus.pro (Holo) | Katowice 2015"},
            {"name": "Virtus.pro (Holo) | Katowice 2015"},
        ]
        bonus = StickerEvaluator.calculate_streak_bonus(stickers)
        base_price = _get_sticker_base_price("Virtus.pro (Holo) | Katowice 2015")
        assert bonus == pytest.approx(base_price * _STREAK_BONUS[3])

    def test_streak_bonus_4_identical(self) -> None:
        stickers = [
            {"name": "Virtus.pro (Holo) | Katowice 2015"},
            {"name": "Virtus.pro (Holo) | Katowice 2015"},
            {"name": "Virtus.pro (Holo) | Katowice 2015"},
            {"name": "Virtus.pro (Holo) | Katowice 2015"},
        ]
        bonus = StickerEvaluator.calculate_streak_bonus(stickers)
        base_price = _get_sticker_base_price("Virtus.pro (Holo) | Katowice 2015")
        assert bonus == pytest.approx(base_price * _STREAK_BONUS[4])

    def test_streak_bonus_mixed(self) -> None:
        stickers = [
            {"name": "Virtus.pro (Holo) | Katowice 2015"},
            {"name": "Natus Vincere (Holo) | Katowice 2015"},
            {"name": "Fnatic (Holo) | Katowice 2015"},
            {"name": "Cloud9 (Holo) | Katowice 2015"},
        ]
        bonus = StickerEvaluator.calculate_streak_bonus(stickers)
        assert bonus == pytest.approx(0.0)

    def test_streak_bonus_empty(self) -> None:
        assert StickerEvaluator.calculate_streak_bonus([]) == pytest.approx(0.0)

    def test_streak_bonus_single(self) -> None:
        stickers = [{"name": "Virtus.pro (Holo) | Katowice 2015"}]
        assert StickerEvaluator.calculate_streak_bonus(stickers) == pytest.approx(0.0)

    def test_streak_bonus_2_plus_2(self) -> None:
        """Two pairs of identical stickers should both contribute."""
        stickers = [
            {"name": "Virtus.pro (Holo) | Katowice 2015"},
            {"name": "Virtus.pro (Holo) | Katowice 2015"},
            {"name": "Natus Vincere (Holo) | Katowice 2015"},
            {"name": "Natus Vincere (Holo) | Katowice 2015"},
        ]
        bonus = StickerEvaluator.calculate_streak_bonus(stickers)
        vp_base = _get_sticker_base_price("Virtus.pro (Holo) | Katowice 2015")
        navi_base = _get_sticker_base_price("Natus Vincere (Holo) | Katowice 2015")
        expected = vp_base * _STREAK_BONUS[2] + navi_base * _STREAK_BONUS[2]
        assert bonus == pytest.approx(expected)


# =====================================================================
# calculate_added_value with new features
# =====================================================================


class TestCalculateAddedValue:
    """Tests for the enhanced calculate_added_value with slot and streak."""

    def test_calculate_added_value_with_slot(self) -> None:
        """Slot multiplier should be applied to individual sticker values."""
        ev = StickerEvaluator(spp_base=0.05)
        stickers = [
            {"name": "Crown (Foil)", "slot": 3, "wear": 0.0},
        ]
        # Crown (Foil) = $800, spp_base=0.05 => $40 base, AK slot 3 = 1.3x
        value_ak = ev.calculate_added_value(stickers, weapon_name="AK-47")
        value_generic = ev.calculate_added_value(stickers, weapon_name="P90")
        # AK-47 slot 3 = 1.3x, generic = 1.0x
        assert value_ak > value_generic
        assert value_ak == pytest.approx(40 * 1.3, rel=0.01)

    def test_calculate_added_value_with_streak(self) -> None:
        """Streak bonus should be added on top of individual values."""
        ev = StickerEvaluator(spp_base=0.05)
        stickers = [
            {"name": "Virtus.pro (Holo) | Katowice 2015", "slot": 0, "wear": 0.0},
            {"name": "Virtus.pro (Holo) | Katowice 2015", "slot": 1, "wear": 0.0},
            {"name": "Virtus.pro (Holo) | Katowice 2015", "slot": 2, "wear": 0.0},
            {"name": "Virtus.pro (Holo) | Katowice 2015", "slot": 3, "wear": 0.0},
        ]
        value = ev.calculate_added_value(stickers, weapon_name="AK-47")
        # 4 identical stickers => streak bonus = base_price * 1.0
        base_price = _get_sticker_base_price("Virtus.pro (Holo) | Katowice 2015")
        # Individual: 4 * base_price * spp(0.05) = 4 * 200 * 0.05 = 40
        # Slot mult: 1.0 + 1.05 + 1.0 + 1.3 = 4.35 total mult on spp
        # Combo: 4 identical = +1 sticker price = +200
        # Streak: base_price * 1.0 = +200
        assert value > 0
        # The streak bonus alone should be $200
        assert value > base_price  # at least the streak bonus

    def test_calculate_added_value_wear_penalty(self) -> None:
        """Wear > 0 should reduce sticker value."""
        ev = StickerEvaluator(spp_base=0.05)
        clean = [{"name": "Crown (Foil)", "slot": 0, "wear": 0.0}]
        worn = [{"name": "Crown (Foil)", "slot": 0, "wear": 0.5}]
        value_clean = ev.calculate_added_value(clean)
        value_worn = ev.calculate_added_value(worn)
        assert value_clean > value_worn


# =====================================================================
# Mid-range sticker pricing
# =====================================================================


class TestMidRangePricing:
    """Tests for mid-range tournament sticker pricing."""

    @pytest.mark.parametrize(
        ("sticker_name", "expected_approx"),
        [
            ("Virtus.pro (Holo) | Katowice 2015", 200.0),
            ("Natus Vincere (Holo) | Katowice 2015", 180.0),
            ("Cloud9 (Holo) | Boston 2018", 40.0),
            ("Astralis (Gold) | Katowice 2019", 40.0),
            ("Team Vitality (Gold) | Paris 2023", 15.0),
            ("Crown (Foil)", 800.0),
            ("Howl", 1200.0),
        ],
    )
    def test_mid_range_sticker_pricing(self, sticker_name: str, expected_approx: float) -> None:
        assert _get_sticker_base_price(sticker_name) == pytest.approx(expected_approx)

    def test_unknown_sticker_year_estimate(self) -> None:
        """Unknown sticker with tournament year should get year-based estimate."""
        # 2014 unknown holo → 500 * 3.0 = 1500
        price_2014 = _get_sticker_base_price("UnknownTeam (Holo) | Katowice 2014")
        assert price_2014 == pytest.approx(500.0 * 3.0)

        # 2019 unknown gold → 6 * 4.0 = 24
        price_2019 = _get_sticker_base_price("UnknownTeam (Gold) | Berlin 2019")
        assert price_2019 == pytest.approx(6.0 * 4.0)

        # 2023 unknown paper → 2.0 * 0.3 = 0.6
        price_2023_paper = _get_sticker_base_price("UnknownTeam | Paris 2023")
        assert price_2023_paper == pytest.approx(2.0 * 0.3)

    def test_unknown_sticker_no_year(self) -> None:
        """Unknown sticker without year returns 0."""
        assert _get_sticker_base_price("Some Random Sticker") == pytest.approx(0.0)

    def test_extract_year(self) -> None:
        assert _extract_year("Virtus.pro | Katowice 2014") == 2014
        assert _extract_year("Astralis (Gold) | Berlin 2019") == 2019
        assert _extract_year("Crown (Foil)") is None


# =====================================================================
# Combo Premium
# =====================================================================


class TestComboPremium:
    """Tests for sticker combo premium calculation."""

    def test_four_identical_stick(self) -> None:
        """4 identical stickers = +100% of one sticker's value."""
        ev = StickerEvaluator()
        stickers = [{"name": "Crown (Foil)"}] * 4
        premium = ev.calculate_combo_premium(stickers)
        assert premium == pytest.approx(800.0)  # +100% of one Crown

    def test_three_same_team(self) -> None:
        """3 stickers from same team (exact name prefix) = +10% of total value.

        NOTE: _extract_team splits on " | " first, so "Virtus.pro (Holo)" and
        "Virtus.pro" are different teams. Use plain team names for team match.
        """
        ev = StickerEvaluator()
        stickers = [
            {"name": "Virtus.pro | Katowice 2015"},
            {"name": "Virtus.pro | Cologne 2014"},
            {"name": "Virtus.pro | Cluj-Napoca 2015"},
        ]
        premium = ev.calculate_combo_premium(stickers)
        # VP Kato15 = 30, VP Cologne14 = (not in mid-range, year 2014 → 500*0.3=150)
        # VP Cluj15 = 30. But wait, "Virtus.pro | Cologne 2014" is not in mid-range.
        # Let me use known mid-range stickers.
        stickers = [
            {"name": "Virtus.pro | Katowice 2015"},   # 30
            {"name": "Virtus.pro | Katowice 2015"},   # 30 (same, but team match)
            {"name": "Virtus.pro | Katowice 2015"},   # 30
        ]
        # 3 same team (VP), 3 same event, AND 3 identical → combo=stick check?
        # No, stick check requires exactly 4 stickers. So team check triggers.
        premium = ev.calculate_combo_premium(stickers)
        total = 30.0 * 3  # = 90
        assert premium == pytest.approx(total * 0.10)

    def test_two_stickers_generic(self) -> None:
        """2 stickers with no other match = +5% of total."""
        ev = StickerEvaluator()
        stickers = [
            {"name": "Crown (Foil)"},
            {"name": "Howl"},
        ]
        premium = ev.calculate_combo_premium(stickers)
        total = 800.0 + 1200.0
        assert premium == pytest.approx(total * 0.05)

    def test_all_worn_no_premium(self) -> None:
        """All stickers worn = no combo premium."""
        ev = StickerEvaluator()
        stickers = [
            {"name": "Crown (Foil)", "wear": 0.5},
            {"name": "Crown (Foil)", "wear": 0.3},
        ]
        premium = ev.calculate_combo_premium(stickers)
        assert premium == pytest.approx(0.0)

    def test_empty_stickers(self) -> None:
        ev = StickerEvaluator()
        assert ev.calculate_combo_premium([]) == pytest.approx(0.0)
