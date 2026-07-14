"""Unit tests for rare_valuation.py v15.3 features.

Tests: ultra-low float bonus, Blue Gem/Ruby/Emerald phases,
sticker bonuses, and combined scoring.
"""

from __future__ import annotations

import pytest

from src.analytics.rare_valuation import RareValuationEngine


# =====================================================================
# Float Analysis
# =====================================================================


class TestFloatAnalysis:
    """Tests for float-based rarity scoring."""

    def test_ultra_low_float_bonus(self) -> None:
        """float < 0.001 = +0.20."""
        engine = RareValuationEngine()
        score = engine.get_rare_score({"float_value": 0.0005})
        assert score == pytest.approx(1.0 + 0.20)

    def test_very_low_float_bonus(self) -> None:
        """float < 0.005 = +0.10."""
        engine = RareValuationEngine()
        score = engine.get_rare_score({"float_value": 0.003})
        assert score == pytest.approx(1.0 + 0.10)

    def test_low_float_bonus(self) -> None:
        """float < 0.01 = +0.05."""
        engine = RareValuationEngine()
        score = engine.get_rare_score({"float_value": 0.008})
        assert score == pytest.approx(1.0 + 0.05)

    def test_normal_float_no_bonus(self) -> None:
        """float 0.5 = no float bonus."""
        engine = RareValuationEngine()
        score = engine.get_rare_score({"float_value": 0.5})
        assert score == pytest.approx(1.0)

    def test_float_part_value_fallback(self) -> None:
        """Falls back to floatPartValue if float_value missing."""
        engine = RareValuationEngine()
        score = engine.get_rare_score({"floatPartValue": 0.0005})
        assert score == pytest.approx(1.0 + 0.20)


# =====================================================================
# Pattern Analysis
# =====================================================================


class TestPatternAnalysis:
    """Tests for pattern seed rarity scoring."""

    @pytest.mark.parametrize("seed", [661, 902, 321, 151, 670, 760])
    def test_blue_gem_seeds(self, seed: int) -> None:
        """Known Blue Gem seeds = +2.0."""
        engine = RareValuationEngine()
        score = engine.get_rare_score({"paint_seed": seed})
        assert score == pytest.approx(1.0 + 2.0)

    def test_blue_gem_seed_661(self) -> None:
        """AK-47 #1 Blue Gem pattern."""
        engine = RareValuationEngine()
        score = engine.get_rare_score({"paint_seed": 661})
        assert score == pytest.approx(1.0 + 2.0)

    def test_normal_seed_no_bonus(self) -> None:
        """Non-rare seed gets no pattern bonus."""
        engine = RareValuationEngine()
        score = engine.get_rare_score({"paint_seed": 123})
        assert score == pytest.approx(1.0)


# =====================================================================
# Phase Analysis
# =====================================================================


class TestPhaseAnalysis:
    """Tests for Doppler/Gamma Doppler phase premiums."""

    @pytest.mark.parametrize(
        ("phase", "expected_bonus"),
        [
            ("ruby", 5.0),
            ("Ruby", 5.0),
            ("sapphire", 6.0),
            ("Sapphire", 6.0),
            ("black pearl", 4.0),
            ("emerald", 8.0),
            ("Emerald", 8.0),
            ("phase 2", 1.5),
            ("Phase 2", 1.5),
            ("phase 4", 1.3),
        ],
    )
    def test_phase_premiums(self, phase: str, expected_bonus: float) -> None:
        engine = RareValuationEngine()
        score = engine.get_rare_score({"phase": phase})
        assert score == pytest.approx(1.0 + expected_bonus)

    def test_ruby_phase(self) -> None:
        engine = RareValuationEngine()
        score = engine.get_rare_score({"phase": "ruby"})
        assert score == pytest.approx(1.0 + 5.0)

    def test_emerald_phase(self) -> None:
        engine = RareValuationEngine()
        score = engine.get_rare_score({"phase": "emerald"})
        assert score == pytest.approx(1.0 + 8.0)

    def test_unknown_phase_no_bonus(self) -> None:
        engine = RareValuationEngine()
        score = engine.get_rare_score({"phase": "Phase 3"})
        assert score == pytest.approx(1.0)


# =====================================================================
# Sticker Bonus
# =====================================================================


class TestStickerBonus:
    """Tests for sticker holo/foil/gold bonus."""

    def test_sticker_bonus_3_holo(self) -> None:
        """3 holo stickers = +0.15."""
        engine = RareValuationEngine()
        stickers = [
            {"name": "Virtus.pro (Holo) | Katowice 2015"},
            {"name": "Natus Vincere (Holo) | Katowice 2015"},
            {"name": "Fnatic (Holo) | Katowice 2015"},
        ]
        score = engine.get_rare_score({"stickers": stickers})
        assert score == pytest.approx(1.0 + 0.15)

    def test_sticker_bonus_1_holo(self) -> None:
        """1 holo sticker = +0.05."""
        engine = RareValuationEngine()
        stickers = [
            {"name": "Virtus.pro (Holo) | Katowice 2015"},
        ]
        score = engine.get_rare_score({"stickers": stickers})
        assert score == pytest.approx(1.0 + 0.05)

    def test_sticker_bonus_2_holo(self) -> None:
        """2 holo stickers = +0.05 (only 1 holo threshold)."""
        engine = RareValuationEngine()
        stickers = [
            {"name": "Virtus.pro (Holo) | Katowice 2015"},
            {"name": "Natus Vincere (Foil) | Katowice 2015"},
        ]
        score = engine.get_rare_score({"stickers": stickers})
        assert score == pytest.approx(1.0 + 0.05)

    def test_sticker_bonus_gold(self) -> None:
        """Gold stickers count as premium."""
        engine = RareValuationEngine()
        stickers = [
            {"name": "Astralis (Gold) | Katowice 2019"},
            {"name": "Natus Vincere (Gold) | Katowice 2019"},
            {"name": "FaZe Clan (Gold) | Katowice 2019"},
        ]
        score = engine.get_rare_score({"stickers": stickers})
        assert score == pytest.approx(1.0 + 0.15)

    def test_no_stickers(self) -> None:
        engine = RareValuationEngine()
        score = engine.get_rare_score({})
        assert score == pytest.approx(1.0)

    def test_empty_stickers_list(self) -> None:
        engine = RareValuationEngine()
        score = engine.get_rare_score({"stickers": []})
        assert score == pytest.approx(1.0)


# =====================================================================
# Combined Scoring
# =====================================================================


class TestCombinedScoring:
    """Tests for combined multi-factor scoring."""

    def test_combined_score_ultra_low_float_plus_blue_gem_plus_ruby(self) -> None:
        """Ultra-low float + Blue Gem + Ruby should stack."""
        engine = RareValuationEngine()
        attrs = {
            "float_value": 0.0005,   # +0.20
            "paint_seed": 661,       # +2.0
            "phase": "ruby",         # +5.0
        }
        score = engine.get_rare_score(attrs)
        assert score == pytest.approx(1.0 + 0.20 + 2.0 + 5.0)

    def test_combined_score_float_plus_stickers(self) -> None:
        """Low float + 3 holo stickers."""
        engine = RareValuationEngine()
        attrs = {
            "float_value": 0.003,    # +0.10
            "stickers": [
                {"name": "Virtus.pro (Holo) | Katowice 2015"},
                {"name": "Natus Vincere (Holo) | Katowice 2015"},
                {"name": "Fnatic (Holo) | Katowice 2015"},
            ],
        }
        score = engine.get_rare_score(attrs)
        assert score == pytest.approx(1.0 + 0.10 + 0.15)

    def test_estimate_market_value(self) -> None:
        """estimate_market_value = base_price * multiplier."""
        engine = RareValuationEngine()
        attrs = {"float_value": 0.0005}  # +0.20 → 1.20
        value = engine.estimate_market_value(100.0, attrs)
        assert value == pytest.approx(120.0)
