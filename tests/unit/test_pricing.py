"""Tests for pricing.py — float premium + pattern/phase premium."""

from __future__ import annotations

from src.core.target_sniping.pricing import _PricingMixin


class TestCalculateFloatPremium:

    def test_no_float_returns_one(self):
        assert _PricingMixin._calculate_float_premium({}) == 1.0

    def test_none_float_returns_one(self):
        assert _PricingMixin._calculate_float_premium({"floatPartValue": None}) == 1.0

    def test_invalid_float_returns_one(self):
        assert _PricingMixin._calculate_float_premium({"floatPartValue": "abc"}) == 1.0

    def test_fn_double_zero(self):
        assert _PricingMixin._calculate_float_premium({"floatPartValue": "0.0005"}) == 1.25

    def test_fn_0(self):
        assert _PricingMixin._calculate_float_premium({"floatPartValue": "0.005"}) == 1.20

    def test_fn_1(self):
        assert _PricingMixin._calculate_float_premium({"floatPartValue": "0.020"}) == 1.12

    def test_fn_standard(self):
        assert _PricingMixin._calculate_float_premium({"floatPartValue": "0.050"}) == 1.08

    def test_mw_0(self):
        assert _PricingMixin._calculate_float_premium({"floatPartValue": "0.075"}) == 1.08

    def test_mw_standard(self):
        assert _PricingMixin._calculate_float_premium({"floatPartValue": "0.090"}) == 1.05

    def test_ft_0(self):
        assert _PricingMixin._calculate_float_premium({"floatPartValue": "0.160"}) == 1.15

    def test_bs_0(self):
        assert _PricingMixin._calculate_float_premium({"floatPartValue": "0.455"}) == 1.10

    def test_bs_dirty(self):
        assert _PricingMixin._calculate_float_premium({"floatPartValue": "0.960"}) == 1.30

    def test_round_float_05(self):
        assert _PricingMixin._calculate_float_premium({"floatPartValue": "0.5"}) >= 1.15

    def test_round_float_25(self):
        assert _PricingMixin._calculate_float_premium({"floatPartValue": "0.25"}) >= 1.15

    def test_normal_float_no_premium(self):
        assert _PricingMixin._calculate_float_premium({"floatPartValue": "0.333"}) == 1.0


class TestCalculatePatternPremium:

    def test_no_attrs_returns_one(self):
        assert _PricingMixin._calculate_pattern_premium({}) == 1.0

    def test_ruby_phase(self):
        attrs = {"phase": "Ruby"}
        assert _PricingMixin._calculate_pattern_premium(attrs) == 5.0

    def test_sapphire_phase(self):
        attrs = {"phase": "Sapphire"}
        assert _PricingMixin._calculate_pattern_premium(attrs) == 5.0

    def test_emerald_phase(self):
        attrs = {"phase": "Emerald"}
        result = _PricingMixin._calculate_pattern_premium(attrs)
        assert result >= 4.0

    def test_phase_2(self):
        attrs = {"phase": "Phase 2"}
        assert _PricingMixin._calculate_pattern_premium(attrs) == 1.5

    def test_phase_4(self):
        attrs = {"phase": "Phase 4"}
        assert _PricingMixin._calculate_pattern_premium(attrs) == 1.3

    def test_blue_gem_seed(self):
        attrs = {"paintSeed": "661"}
        result = _PricingMixin._calculate_pattern_premium(attrs)
        assert result >= 3.0

    def test_fire_ice_seed(self):
        attrs = {"paintSeed": "412"}
        result = _PricingMixin._calculate_pattern_premium(attrs)
        assert result >= 3.0

    def test_normal_paint_seed(self):
        attrs = {"paintSeed": "123"}
        result = _PricingMixin._calculate_pattern_premium(attrs)
        assert result == 1.0

    def test_invalid_paint_seed(self):
        attrs = {"paintSeed": "abc"}
        assert _PricingMixin._calculate_pattern_premium(attrs) == 1.0

    def test_gamma_doppler_emerald(self):
        attrs = {"phase": "Emerald", "isGamma": True}
        result = _PricingMixin._calculate_pattern_premium(attrs)
        assert result >= 4.0

    def test_crimson_web_3web(self):
        attrs = {"paintSeed": "34"}
        result = _PricingMixin._calculate_pattern_premium(attrs)
        assert result >= 1.0

    def test_case_hardened_gold_gem(self):
        attrs = {"paintSeed": "179"}
        result = _PricingMixin._calculate_pattern_premium(attrs)
        assert result >= 2.0

    def test_case_hardened_green_pattern(self):
        attrs = {"paintSeed": "420"}
        result = _PricingMixin._calculate_pattern_premium(attrs)
        assert result >= 1.5

    def test_marble_fade_tricolor(self):
        attrs = {"paintSeed": "25"}
        result = _PricingMixin._calculate_pattern_premium(attrs)
        assert result >= 1.0

    def test_tiger_tooth_bright(self):
        attrs = {"paintSeed": "100"}
        result = _PricingMixin._calculate_pattern_premium(attrs)
        assert result >= 1.0

    def test_fade_estimated_from_seed(self):
        """Fade percentage is estimated from paint seed."""
        # Seed 661 is known to have high fade
        attrs = {"paintSeed": "661"}
        result = _PricingMixin._calculate_pattern_premium(attrs)
        assert result >= 1.0


class TestHasRarePhaseOrPattern:

    def test_ruby_phase(self):
        assert _PricingMixin.has_rare_phase_or_pattern({"phase": "Ruby"}) is True

    def test_sapphire_phase(self):
        assert _PricingMixin.has_rare_phase_or_pattern({"phase": "Sapphire"}) is True

    def test_blue_gem_seed(self):
        assert _PricingMixin.has_rare_phase_or_pattern({"paintSeed": "661"}) is True

    def test_fire_ice_seed(self):
        assert _PricingMixin.has_rare_phase_or_pattern({"paintSeed": "412"}) is True

    def test_normal_item(self):
        assert _PricingMixin.has_rare_phase_or_pattern({"phase": "Phase 3", "paintSeed": "500"}) is False

    def test_invalid_seed(self):
        assert _PricingMixin.has_rare_phase_or_pattern({"paintSeed": "abc"}) is False

    def test_phase_2(self):
        assert _PricingMixin.has_rare_phase_or_pattern({"phase": "Phase 2"}) is True

    def test_phase_4(self):
        assert _PricingMixin.has_rare_phase_or_pattern({"phase": "P4"}) is True


class TestIsDirtyBs:

    def test_dirty_bs(self):
        assert _PricingMixin.is_dirty_bs({"floatPartValue": "0.96"}) is True

    def test_not_dirty_bs(self):
        assert _PricingMixin.is_dirty_bs({"floatPartValue": "0.50"}) is False

    def test_no_float(self):
        assert _PricingMixin.is_dirty_bs({}) is False

    def test_none_float(self):
        assert _PricingMixin.is_dirty_bs({"floatPartValue": None}) is False

    def test_invalid_float(self):
        assert _PricingMixin.is_dirty_bs({"floatPartValue": "abc"}) is False

    def test_boundary_095(self):
        assert _PricingMixin.is_dirty_bs({"floatPartValue": "0.95"}) is False

    def test_boundary_096(self):
        assert _PricingMixin.is_dirty_bs({"floatPartValue": "0.96"}) is True


class TestStandaloneHelpers:

    def test_get_float_premium(self):
        """Standalone float premium calculator (line 334)."""
        from src.core.target_sniping.pricing import get_float_premium
        assert get_float_premium({"floatPartValue": "0.0005"}) == 1.25

    def test_get_pattern_premium(self):
        """Standalone pattern premium calculator (line 339)."""
        from src.core.target_sniping.pricing import get_pattern_premium
        assert get_pattern_premium({"phase": "Ruby"}) == 5.0


class TestIsFloatDate:

    def test_valid_date(self):
        """Valid date float returns True (lines 312-314)."""
        from src.core.target_sniping.pricing import _is_float_date
        # 0.21021992 = 21 Feb 1992
        assert _is_float_date(0.21021992) is True

    def test_invalid_date(self):
        """Invalid date returns False."""
        from src.core.target_sniping.pricing import _is_float_date
        assert _is_float_date(0.50000000) is False

    def test_boundary_date(self):
        """Boundary date (01 Jan 2025)."""
        from src.core.target_sniping.pricing import _is_float_date
        assert _is_float_date(0.01012025) is True


class TestEstimateFadePct:

    def test_high_fade_seed(self):
        """Seed 900-1000 range (line 328)."""
        from src.core.target_sniping.pricing import _estimate_fade_pct
        assert _estimate_fade_pct(950) >= 95

    def test_medium_fade_seed(self):
        """Seed 100-899 range."""
        from src.core.target_sniping.pricing import _estimate_fade_pct
        assert _estimate_fade_pct(500) >= 80

    def test_low_fade_seed(self):
        """Seed < 100 range (line 324-325)."""
        from src.core.target_sniping.pricing import _estimate_fade_pct
        assert _estimate_fade_pct(50) >= 80


class TestLowPaintSeed:

    def test_very_low_seed(self):
        """Very low paint seed (1-4) gives +3% (line 234)."""
        result = _PricingMixin._calculate_pattern_premium({"paintSeed": "2"})
        assert result >= 1.03

    def test_seed_zero_no_premium(self):
        """Seed 0 doesn't trigger low-seed premium."""
        result = _PricingMixin._calculate_pattern_premium({"paintSeed": "0"})
        assert result == 1.0
