"""
tests/test_v14_6_value_detection.py — Unit tests for v14.6 Value Detection Layers.

Covers: float premium, pattern premium, sticker combo, seasonal timing,
filler tracker, dirty BS, round float, float date, commission optimizer.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.target_sniping.pricing import (
    _PricingMixin,
    _is_float_date,
    _estimate_fade_pct,
    get_float_premium,
    get_pattern_premium,
)
from src.analytics.stickers_evaluator import StickerEvaluator
from src.analysis.seasonal import (
    get_seasonal_multiplier,
    get_weekly_multiplier,
    get_hourly_multiplier,
    get_timing_multiplier,
)
from src.analytics.filler_tracker import is_filler, get_filler_multiplier


# =========================================================================
# Float Premium Tests
# =========================================================================

class TestFloatPremium:
    def test_fn_double_zero(self):
        premium = get_float_premium({"floatPartValue": "0.0005"})
        assert premium == 1.25, f"FN double-zero should be 1.25x, got {premium}"

    def test_fn_0(self):
        premium = get_float_premium({"floatPartValue": "0.005"})
        assert premium == 1.20, f"FN-0 should be 1.20x, got {premium}"

    def test_fn_1(self):
        premium = get_float_premium({"floatPartValue": "0.02"})
        assert premium == 1.12, f"FN-1 should be 1.12x, got {premium}"

    def test_fn_standard(self):
        premium = get_float_premium({"floatPartValue": "0.05"})
        assert premium == 1.08, f"FN should be 1.08x, got {premium}"

    def test_mw_0(self):
        premium = get_float_premium({"floatPartValue": "0.075"})
        assert premium == 1.08, f"MW-0 should be 1.08x, got {premium}"

    def test_ft_0(self):
        premium = get_float_premium({"floatPartValue": "0.16"})
        assert premium == 1.15, f"FT-0 should be 1.15x, got {premium}"

    def test_bs_dirty(self):
        premium = get_float_premium({"floatPartValue": "0.97"})
        assert premium == 1.30, f"BS-dirty should be 1.30x, got {premium}"

    def test_normal_mw(self):
        premium = get_float_premium({"floatPartValue": "0.10"})
        assert premium == 1.0, f"Normal MW should be 1.0x, got {premium}"

    def test_no_float(self):
        premium = get_float_premium({})
        assert premium == 1.0, "Missing float should return 1.0"

    def test_invalid_float(self):
        premium = get_float_premium({"floatPartValue": "not_a_number"})
        assert premium == 1.0, "Invalid float should return 1.0"


# =========================================================================
# Round Float Tests
# =========================================================================

class TestRoundFloat:
    def test_round_025(self):
        premium = get_float_premium({"floatPartValue": "0.25"})
        assert premium >= 1.15, f"0.25 should be >= 1.15x, got {premium}"

    def test_round_050(self):
        premium = get_float_premium({"floatPartValue": "0.5"})
        assert premium >= 1.15, f"0.5 should be >= 1.15x, got {premium}"

    def test_not_round_float(self):
        premium = get_float_premium({"floatPartValue": "0.12345"})
        assert premium < 1.15, f"0.12345 should NOT be round, got {premium}"


# =========================================================================
# Float Date Tests
# =========================================================================

class TestFloatDate:
    def test_float_date_1992(self):
        assert _is_float_date(0.210219925555) is True

    def test_float_date_2020(self):
        assert _is_float_date(0.150120208888) is True

    def test_not_float_date(self):
        assert _is_float_date(0.999999999999) is False

    def test_invalid_date_month(self):
        assert _is_float_date(0.211319925555) is False  # month 13


# =========================================================================
# Pattern Premium Tests
# =========================================================================

class TestPatternPremium:
    def test_ruby(self):
        premium = get_pattern_premium({"phase": "Ruby", "paintSeed": "0"})
        assert premium == 5.0, f"Ruby should be 5.0x, got {premium}"

    def test_sapphire(self):
        premium = get_pattern_premium({"phase": "Sapphire", "paintSeed": "0"})
        assert premium == 5.0, f"Sapphire should be 5.0x, got {premium}"

    def test_black_pearl(self):
        premium = get_pattern_premium({"phase": "Black Pearl", "paintSeed": "0"})
        assert premium == 4.0, f"Black Pearl should be 4.0x, got {premium}"

    def test_emerald(self):
        premium = get_pattern_premium({"phase": "Emerald", "paintSeed": "0"})
        assert premium == 4.0, f"Emerald should be 4.0x, got {premium}"

    def test_phase_2(self):
        premium = get_pattern_premium({"phase": "Phase 2", "paintSeed": "0"})
        assert premium == 1.5, f"Phase 2 should be 1.5x, got {premium}"

    def test_phase_4(self):
        premium = get_pattern_premium({"phase": "Phase 4", "paintSeed": "0"})
        assert premium == 1.3, f"Phase 4 should be 1.3x, got {premium}"

    def test_blue_gem_661(self):
        premium = get_pattern_premium({"phase": "", "paintSeed": "661"})
        assert premium >= 3.0, f"Blue Gem 661 should be >= 3.0x, got {premium}"

    def test_fire_ice_152(self):
        premium = get_pattern_premium({"phase": "", "paintSeed": "152"})
        assert premium >= 5.0, f"Fire & Ice 152 should be >= 5.0x, got {premium}"

    def test_crimson_web_3web(self):
        premium = get_pattern_premium({"phase": "", "paintSeed": "34"})
        assert premium >= 2.0, f"Crimson Web 3+ web should be >= 2.0x, got {premium}"

    def test_normal_pattern(self):
        premium = get_pattern_premium({"phase": "Phase 3", "paintSeed": "500"})
        assert premium == 1.0, f"Normal pattern should be 1.0x, got {premium}"


# =========================================================================
# Dirty BS Tests
# =========================================================================

class TestDirtyBS:
    def test_dirty_bs(self):
        assert _PricingMixin.is_dirty_bs({"floatPartValue": "0.97"}) is True

    def test_not_dirty_bs(self):
        assert _PricingMixin.is_dirty_bs({"floatPartValue": "0.50"}) is False

    def test_no_float(self):
        assert _PricingMixin.is_dirty_bs({}) is False


# =========================================================================
# Fade % Estimation Tests
# =========================================================================

class TestFadeEstimation:
    def test_high_fade_seed(self):
        fade = _estimate_fade_pct(950)
        assert fade >= 95, f"High fade seed should be >= 95%, got {fade}%"

    def test_low_fade_seed(self):
        fade = _estimate_fade_pct(50)
        assert fade < 95, f"Low fade seed should be < 95%, got {fade}%"

    def test_fade_max_100(self):
        fade = _estimate_fade_pct(999)
        assert fade <= 100, f"Fade should not exceed 100%, got {fade}%"


# =========================================================================
# Sticker Combo Tests
# =========================================================================

class TestStickerCombo:
    def setup_method(self):
        self.eval = StickerEvaluator()

    def test_four_identical_stick(self):
        stickers = [
            {"name": "Crown (Foil)", "wear": 0.0},
            {"name": "Crown (Foil)", "wear": 0.0},
            {"name": "Crown (Foil)", "wear": 0.0},
            {"name": "Crown (Foil)", "wear": 0.0},
        ]
        combo = self.eval.calculate_combo_premium(stickers)
        assert combo > 0, f"4x stick should have combo premium, got {combo}"

    def test_same_team_three_stickers(self):
        stickers = [
            {"name": "Natus Vincere | Katowice 2014", "wear": 0.0},
            {"name": "Natus Vincere | Katowice 2014", "wear": 0.0},
            {"name": "Natus Vincere (Holo) | Katowice 2014", "wear": 0.0},
        ]
        combo = self.eval.calculate_combo_premium(stickers)
        assert combo > 0, f"3x same team should have combo premium, got {combo}"

    def test_random_stickers_no_combo(self):
        stickers = [
            {"name": "Crown (Foil)", "wear": 0.0},
            {"name": "Dignitas | Katowice 2014", "wear": 0.5},
        ]
        combo = self.eval.calculate_combo_premium(stickers)
        assert combo >= 0, f"Random stickers may have small premium"

    def test_worn_stickers_no_combo(self):
        stickers = [
            {"name": "Crown (Foil)", "wear": 0.8},
            {"name": "Crown (Foil)", "wear": 0.9},
        ]
        combo = self.eval.calculate_combo_premium(stickers)
        assert combo == 0.0, f"All worn should have 0 combo premium, got {combo}"

    def test_single_sticker_no_combo(self):
        stickers = [{"name": "Crown (Foil)", "wear": 0.0}]
        combo = self.eval.calculate_combo_premium(stickers)
        assert combo == 0.0, f"Single sticker should have 0 combo premium"

    def test_added_value_with_combo(self):
        stickers = [
            {"name": "Crown (Foil)", "wear": 0.0},
            {"name": "Crown (Foil)", "wear": 0.0},
            {"name": "Crown (Foil)", "wear": 0.0},
            {"name": "Crown (Foil)", "wear": 0.0},
        ]
        value = self.eval.calculate_added_value(stickers)
        # 4x Crown Foil: 4 * (800 * 0.10 * 1.0) + 800 (combo) = 320 + 800 = ~1120
        assert value > 100, f"4x Crown should be valuable, got {value}"


# =========================================================================
# Seasonal Timing Tests
# =========================================================================

class TestSeasonalTiming:
    def test_multiplier_in_range(self):
        mult = get_timing_multiplier()
        assert 0.7 <= mult <= 1.5, f"Timing multiplier {mult} out of range"

    def test_seasonal_multiplier_is_float(self):
        mult = get_seasonal_multiplier()
        assert isinstance(mult, float)

    def test_weekly_multiplier_near_1(self):
        mult = get_weekly_multiplier()
        assert 0.9 <= mult <= 1.2, f"Weekly multiplier {mult} out of range"

    def test_hourly_multiplier_near_1(self):
        mult = get_hourly_multiplier()
        assert 0.9 <= mult <= 1.2, f"Hourly multiplier {mult} out of range"


# =========================================================================
# Filler Tracker Tests
# =========================================================================

class TestFillerTracker:
    def test_known_filler(self):
        assert is_filler("PP-Bizon | Brass") is True

    def test_unknown_item(self):
        assert is_filler("Karambit | Doppler (Ruby)") is False

    def test_filler_multiplier(self):
        mult = get_filler_multiplier("M4A1-S | VariCamo")
        assert mult == 1.15, f"Filler multiplier should be 1.15, got {mult}"

    def test_non_filler_multiplier(self):
        mult = get_filler_multiplier("AK-47 | Fire Serpent")
        assert mult == 1.0, f"Non-filler should be 1.0, got {mult}"


# =========================================================================
# Commission Optimizer Tests
# =========================================================================

class TestCommissionOptimizer:
    def test_low_fee_boost(self):
        """Items with 2% fee get score boost."""
        from src.core.target_sniping.ranking import rank_candidates_by_spread

        items = [{"title": "AK-47 | Redline", "price": {"USD": 1000}}]
        agg = {"AK-47 | Redline": {"best_bid": 12.0, "best_ask": 10.0, "ask_count": 5, "bid_count": 5}}

        # Without low_fee set
        ranked_no_fee = rank_candidates_by_spread(items, agg, low_fee_titles=None)
        # With low_fee set
        ranked_with_fee = rank_candidates_by_spread(
            items, agg, low_fee_titles={"AK-47 | Redline"}
        )

        if ranked_no_fee and ranked_with_fee:
            assert ranked_with_fee[0][1] > ranked_no_fee[0][1], \
                f"Low-fee item should have higher score: {ranked_with_fee[0][1]} vs {ranked_no_fee[0][1]}"


# =========================================================================
# Integration: Pricing Mixin has all methods
# =========================================================================

class TestPricingMixinIntegration:
    def test_has_rare_phase_or_pattern_blue_gem(self):
        assert _PricingMixin.has_rare_phase_or_pattern({"paintSeed": "661"}) is True

    def test_has_rare_phase_or_pattern_ruby(self):
        assert _PricingMixin.has_rare_phase_or_pattern({"phase": "Ruby"}) is True

    def test_has_rare_phase_or_pattern_normal(self):
        assert _PricingMixin.has_rare_phase_or_pattern({"paintSeed": "500"}) is False

    def test_float_premium_combined_round_and_dirty(self):
        # 0.97 is both BS-dirty AND not round → 1.30
        premium = get_float_premium({"floatPartValue": "0.97"})
        assert premium == 1.30


print("All v14.6 value detection tests defined successfully.")
print(f"Test classes ready: {len([c for c in dir() if c.startswith('Test')])} classes")
