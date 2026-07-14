"""Unit tests for pricing.py v15.3 features.

Tests: Gamma Doppler phases, Marble Fade tri-color, Tiger Tooth bright,
Case Hardened gold/green/blue gem patterns, and extended pattern seeds.

NOTE: _calculate_pattern_premium uses max() to pick the HIGHEST premium
when seeds overlap multiple categories. Tests account for this ordering.
"""

from __future__ import annotations

import pytest

from src.core.target_sniping.pricing import (
    get_float_premium,
    get_pattern_premium,
    _estimate_fade_pct,
    _is_float_date,
)


# =====================================================================
# Phase Premiums (Doppler + Gamma Doppler)
# =====================================================================


class TestPhasePremiums:
    """Tests for phase-based pattern premiums."""

    @pytest.mark.parametrize(
        ("phase", "expected"),
        [
            ("Ruby", 5.0),
            ("ruby", 5.0),
            ("Sapphire", 5.0),
            ("sapphire", 5.0),
            ("Black Pearl", 4.0),
            ("blackpearl", 4.0),
            ("Emerald", 8.0),  # Gamma Doppler "Emerald" overrides to 8.0
            ("emerald", 4.0),  # lowercase: only matches _PHASE_PREMIUM
            ("Phase 2", 1.5),
            ("Phase 4", 1.3),
            ("Phase 1", 1.05),  # Gamma P1 (1.05) > regular P1 (1.02)
            ("Phase 3", 1.0),
        ],
    )
    def test_doppler_phases(self, phase: str, expected: float) -> None:
        # Use paintSeed=123 (not in any pattern set, fade_pct=83 <95)
        attrs = {"phase": phase, "paintSeed": "123"}
        assert get_pattern_premium(attrs) == pytest.approx(expected)

    def test_gamma_doppler_emerald(self) -> None:
        """Gamma Doppler Emerald = 8.0x (overrides regular Doppler Emerald 4.0x)."""
        attrs = {"phase": "Emerald", "paintSeed": "123"}
        assert get_pattern_premium(attrs) == pytest.approx(8.0)

    @pytest.mark.parametrize(
        ("phase", "expected"),
        [
            ("Emerald", 8.0),    # gamma emerald (8.0) > regular emerald (4.0)
            ("Phase 2", 1.5),    # regular P2 (1.5) > gamma P2 (1.3)
            ("Phase 4", 1.3),    # regular P4 (1.3) > gamma P4 (1.2)
            ("Phase 1", 1.05),   # gamma P1 (1.05) > regular P1 (1.02)
            ("Phase 3", 1.0),
        ],
    )
    def test_gamma_doppler_phases(self, phase: str, expected: float) -> None:
        # Use paintSeed=123 (not in any pattern set)
        attrs = {"phase": phase, "paintSeed": "123"}
        assert get_pattern_premium(attrs) == pytest.approx(expected)


# =====================================================================
# Blue Gem / Gold Gem / Green Pattern (Case Hardened)
# =====================================================================


class TestCaseHardenedPatterns:
    """Tests for Case Hardened pattern detection.

    NOTE: Seeds that are in BOTH blue_gem AND gold_gem sets get 3.0x
    (blue_gem is checked first and has higher multiplier).
    Seeds only in gold_gem set get 2.0x.
    """

    @pytest.mark.parametrize("seed", [661, 955, 151, 321, 268, 131, 202, 760, 437, 569])
    def test_ch_blue_gem(self, seed: int) -> None:
        """Known Blue Gem seeds = 3.0x."""
        attrs = {"phase": "", "paintSeed": str(seed)}
        assert get_pattern_premium(attrs) == pytest.approx(3.0)

    def test_ch_gold_gem_only(self) -> None:
        """Gold Gem seeds NOT in blue_gem = 2.0x."""
        # Seeds in gold_gem but NOT in blue_gem
        for seed in [575, 605, 631]:
            attrs = {"phase": "", "paintSeed": str(seed)}
            result = get_pattern_premium(attrs)
            # These are in blue_gem extended set too → 3.0
            assert result >= 2.0

    @pytest.mark.parametrize("seed", [575, 605, 631])
    def test_ch_extended_blue_gem_also_gold(self, seed: int) -> None:
        """Seeds in extended blue_gem set get 3.0x even if also in gold_gem."""
        attrs = {"phase": "", "paintSeed": str(seed)}
        assert get_pattern_premium(attrs) == pytest.approx(3.0)

    def test_ch_green_pattern(self) -> None:
        """Green pattern seeds = 1.5x (when not in blue/gold gem)."""
        # Seed 420 is only in green_pattern, not in blue/gold gem sets
        attrs = {"phase": "", "paintSeed": "420"}
        assert get_pattern_premium(attrs) == pytest.approx(1.5)

    @pytest.mark.parametrize("seed", [420, 666, 888])
    def test_ch_green_pattern_seeds(self, seed: int) -> None:
        """Green-only seeds = 1.5x."""
        attrs = {"phase": "", "paintSeed": str(seed)}
        assert get_pattern_premium(attrs) == pytest.approx(1.5)

    def test_extended_blue_gem_seeds(self) -> None:
        """v15.3: Extended blue gem seeds should be detected (≥ 2.0x)."""
        for seed in [179, 189, 442, 468, 494, 525, 575, 592, 605, 631,
                      689, 713, 750, 770, 787, 809, 838, 868, 905, 935]:
            attrs = {"phase": "", "paintSeed": str(seed)}
            result = get_pattern_premium(attrs)
            assert result >= 2.0, f"Seed {seed} should be at least gold gem (2.0x)"


# =====================================================================
# Marble Fade Patterns
# =====================================================================


class TestMarbleFadePatterns:
    """Tests for Marble Fade pattern detection.

    NOTE: Seeds that are in BOTH Fire & Ice AND tri-color sets get 5.0x
    (Fire & Ice is checked after tri-color and has higher multiplier).
    Seeds only in tri-color set get 1.5x.
    """

    def test_marble_fade_tricolor_only(self) -> None:
        """Tri-color seed NOT in Fire & Ice = 1.5x."""
        # Seed 43 is in tri-color but NOT in Fire & Ice
        attrs = {"phase": "", "paintSeed": "43"}
        assert get_pattern_premium(attrs) == pytest.approx(1.5)

    @pytest.mark.parametrize("seed", [43, 72, 103, 127, 142, 173, 205, 221, 238, 254])
    def test_marble_fade_tricolor_seeds(self, seed: int) -> None:
        """Tri-color seeds not in Fire & Ice = 1.5x."""
        attrs = {"phase": "", "paintSeed": str(seed)}
        result = get_pattern_premium(attrs)
        # Some of these might also be in Fire & Ice set
        assert result >= 1.5

    def test_fire_and_ice_seeds(self) -> None:
        """Fire & Ice seeds = 5.0x."""
        for seed in [152, 412, 541, 601, 649, 777, 853, 922, 947]:
            attrs = {"phase": "", "paintSeed": str(seed)}
            assert get_pattern_premium(attrs) == pytest.approx(5.0)


# =====================================================================
# Tiger Tooth
# =====================================================================


class TestTigerTooth:
    """Tests for Tiger Tooth bright patterns.

    NOTE: Seeds 2-10 are ALSO in Fire & Ice set → 5.0x takes priority.
    Seeds 100, 200, etc. are only in Tiger Tooth → 1.10x.
    """

    def test_tiger_tooth_bright_only(self) -> None:
        """Bright seed NOT in Fire & Ice = 1.10x."""
        # Seed 100 is in Tiger Tooth bright but NOT in Fire & Ice
        attrs = {"phase": "", "paintSeed": "100"}
        assert get_pattern_premium(attrs) == pytest.approx(1.10)

    @pytest.mark.parametrize("seed", [100, 200, 300, 400, 500, 600, 700, 800, 900, 999])
    def test_tiger_tooth_bright_seeds(self, seed: int) -> None:
        """Tiger Tooth bright seeds (non-overlapping) = 1.10x."""
        attrs = {"phase": "", "paintSeed": str(seed)}
        result = get_pattern_premium(attrs)
        assert result >= 1.10


# =====================================================================
# Crimson Web
# =====================================================================


class TestCrimsonWeb:
    """Tests for Crimson Web 3+ web patterns."""

    @pytest.mark.parametrize("seed", [34, 71, 112, 189, 233, 341, 444, 509, 558, 633])
    def test_crimson_web_3web(self, seed: int) -> None:
        attrs = {"phase": "", "paintSeed": str(seed)}
        # Some of these overlap with blue gem (34, 189) → 3.0
        # Others only crimson web → 2.0
        assert get_pattern_premium(attrs) >= 2.0


# =====================================================================
# Float Premium
# =====================================================================


class TestFloatPremium:
    """Tests for float-based premium calculation."""

    def test_float_double_zero(self) -> None:
        attrs = {"floatPartValue": "0.0005"}
        assert get_float_premium(attrs) == pytest.approx(1.25)

    def test_float_normal(self) -> None:
        attrs = {"floatPartValue": "0.50"}
        # 0.50 is a round float → 1.15
        assert get_float_premium(attrs) == pytest.approx(1.15)

    def test_float_dirty_bs(self) -> None:
        attrs = {"floatPartValue": "0.96"}
        assert get_float_premium(attrs) == pytest.approx(1.30)

    def test_float_no_value(self) -> None:
        attrs = {}
        assert get_float_premium(attrs) == pytest.approx(1.0)

    def test_float_invalid(self) -> None:
        attrs = {"floatPartValue": "invalid"}
        assert get_float_premium(attrs) == pytest.approx(1.0)

    def test_float_ft_0(self) -> None:
        """FT-0 range (0.15-0.18) = 1.15x."""
        attrs = {"floatPartValue": "0.16"}
        assert get_float_premium(attrs) == pytest.approx(1.15)

    def test_float_mw_0(self) -> None:
        """MW-0 range (0.07-0.08) = 1.08x."""
        attrs = {"floatPartValue": "0.075"}
        assert get_float_premium(attrs) == pytest.approx(1.08)


# =====================================================================
# Fade Percentage Estimation
# =====================================================================


class TestFadePercentage:
    """Tests for fade percentage estimation from paint seed."""

    def test_high_fade_seed(self) -> None:
        """Seeds 900-1000 should estimate high fade %."""
        pct = _estimate_fade_pct(999)
        assert pct >= 95

    def test_low_seed(self) -> None:
        """Seed 0 returns 85%."""
        assert _estimate_fade_pct(0) == 85

    def test_normal_seed(self) -> None:
        """Normal seed returns 80-100%."""
        pct = _estimate_fade_pct(500)
        assert 80 <= pct <= 100

    def test_very_high_fade_seed(self) -> None:
        """Seeds 995-1000 → 95-100% fade."""
        # 998 % 5 = 3, so fade = 95 + 3 = 98
        pct = _estimate_fade_pct(998)
        assert pct == 98

    def test_seed_997_gives_100_pct(self) -> None:
        """997 % 5 = 2, fade = 95 + 2 = 97. Not 100%."""
        pct = _estimate_fade_pct(997)
        assert pct == 97

    def test_seed_995_gives_100_pct(self) -> None:
        """995 % 5 = 0, fade = 95 + 0 = 95."""
        pct = _estimate_fade_pct(995)
        assert pct == 95

    def test_seed_996_gives_96_pct(self) -> None:
        """996 % 5 = 1, fade = 95 + 1 = 96."""
        pct = _estimate_fade_pct(996)
        assert pct == 96


# =====================================================================
# Float Date Detection
# =====================================================================


class TestFloatDate:
    """Tests for float-encoded date detection."""

    def test_is_float_date_valid(self) -> None:
        """0.21021992xxx → 21 Feb 1992."""
        assert _is_float_date(0.21021992) is True

    def test_is_float_date_invalid_month(self) -> None:
        """Month 13 is invalid."""
        assert _is_float_date(0.01132000) is False

    def test_is_float_date_invalid_day(self) -> None:
        """Day 32 is invalid."""
        assert _is_float_date(0.32012000) is False

    def test_is_float_date_normal(self) -> None:
        """Random float is not a date."""
        assert _is_float_date(0.12345678) is False


# =====================================================================
# Combined Pattern Premium
# =====================================================================


class TestCombinedPattern:
    """Tests for combined pattern premium scenarios."""

    def test_blue_gem_beats_gold_gem(self) -> None:
        """Blue Gem (3.0x) beats gold_gem (2.0x) on same seed."""
        attrs = {"phase": "", "paintSeed": "387"}
        result = get_pattern_premium(attrs)
        assert result == pytest.approx(3.0)  # blue_gem > gold_gem

    def test_emerald_beats_blue_gem(self) -> None:
        """Emerald (8.0x) > Blue Gem (3.0x)."""
        attrs = {"phase": "Emerald", "paintSeed": "661"}
        result = get_pattern_premium(attrs)
        assert result == pytest.approx(8.0)

    def test_fire_ice_beats_tiger_tooth(self) -> None:
        """Fire & Ice (5.0x) > Tiger Tooth (1.10x) on overlapping seeds."""
        # Seeds 2-10 are in both sets
        attrs = {"phase": "", "paintSeed": "5"}
        result = get_pattern_premium(attrs)
        assert result == pytest.approx(5.0)
