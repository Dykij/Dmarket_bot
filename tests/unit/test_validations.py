"""Tests for validations.py — microstructure validation checks."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.core.target_sniping import validations as _val_mod


def _set_config(attr, value):
    """Temporarily set a Config attribute."""
    original = getattr(_val_mod.Config, attr)
    setattr(_val_mod.Config, attr, value)
    return original


class TestCheckBaitDetection:

    def test_disabled_passes(self):
        orig = _set_config("BAIT_DETECTION_ENABLED", False)
        try:
            assert _val_mod.check_bait_detection("AK-47", 10.0)["pass"] is True
        finally:
            _val_mod.Config.BAIT_DETECTION_ENABLED = orig

    def test_no_prices_passes(self):
        orig = _set_config("BAIT_DETECTION_ENABLED", True)
        try:
            with patch.object(_val_mod.price_db, "get_recent_prices", return_value=[]):
                assert _val_mod.check_bait_detection("AK-47", 10.0)["pass"] is True
        finally:
            _val_mod.Config.BAIT_DETECTION_ENABLED = orig

    def test_stable_prices_pass(self):
        orig = _set_config("BAIT_DETECTION_ENABLED", True)
        try:
            prices = [(10.0, 1000.0), (10.0, 1001.0), (10.0, 1002.0)]
            with patch.object(_val_mod.price_db, "get_recent_prices", return_value=prices):
                assert _val_mod.check_bait_detection("AK-47", 10.0)["pass"] is True
        finally:
            _val_mod.Config.BAIT_DETECTION_ENABLED = orig

    def test_rapid_changes_fails(self):
        orig_bait = _set_config("BAIT_DETECTION_ENABLED", True)
        orig_max = _val_mod.Config.BAIT_MAX_PRICE_CHANGES
        try:
            _val_mod.Config.BAIT_MAX_PRICE_CHANGES = 1
            prices = [(10.0, 1000.0), (15.0, 1001.0), (8.0, 1002.0), (20.0, 1003.0)]
            with patch.object(_val_mod.price_db, "get_recent_prices", return_value=prices):
                assert _val_mod.check_bait_detection("AK-47", 10.0)["pass"] is False
        finally:
            _val_mod.Config.BAIT_DETECTION_ENABLED = orig_bait
            _val_mod.Config.BAIT_MAX_PRICE_CHANGES = orig_max


class TestCheckOBI:

    def test_disabled_passes(self):
        orig = _set_config("OBI_ENABLED", False)
        try:
            assert _val_mod.check_obi(5, 3, 10.0, 12.0)["pass"] is True
        finally:
            _val_mod.Config.OBI_ENABLED = orig

    def test_zero_asks_passes(self):
        assert _val_mod.check_obi(0, 3, 10.0, 12.0)["pass"] is True

    def test_zero_bids_passes(self):
        assert _val_mod.check_obi(5, 0, 10.0, 12.0)["pass"] is True

    def test_good_obi_passes(self):
        orig_en = _set_config("OBI_ENABLED", True)
        orig_ratio = _val_mod.Config.OBI_MIN_RATIO
        try:
            _val_mod.Config.OBI_MIN_RATIO = 0.5
            result = _val_mod.check_obi(5, 10, 10.0, 12.0)
            assert result["pass"] is True
            assert result["signal"] > 0.5
        finally:
            _val_mod.Config.OBI_ENABLED = orig_en
            _val_mod.Config.OBI_MIN_RATIO = orig_ratio

    def test_bad_obi_fails(self):
        orig_en = _set_config("OBI_ENABLED", True)
        orig_ratio = _val_mod.Config.OBI_MIN_RATIO
        try:
            _val_mod.Config.OBI_MIN_RATIO = 5.0
            result = _val_mod.check_obi(10, 1, 10.0, 12.0)
            assert result["pass"] is False
        finally:
            _val_mod.Config.OBI_ENABLED = orig_en
            _val_mod.Config.OBI_MIN_RATIO = orig_ratio


class TestCheckVWAPFilter:

    def test_disabled_passes(self):
        orig = _set_config("VWAP_FILTER_ENABLED", False)
        try:
            assert _val_mod.check_vwap_filter("AK-47", 10.0)["pass"] is True
        finally:
            _val_mod.Config.VWAP_FILTER_ENABLED = orig

    def test_no_sales_passes(self):
        orig = _set_config("VWAP_FILTER_ENABLED", True)
        try:
            with patch.object(_val_mod.price_db, "get_trade_history", return_value=[]):
                assert _val_mod.check_vwap_filter("AK-47", 10.0)["pass"] is True
        finally:
            _val_mod.Config.VWAP_FILTER_ENABLED = orig


class TestCheckCVDVPIN:

    def test_no_trades_passes(self):
        with patch.object(_val_mod.price_db, "get_trade_history", return_value=[]):
            assert _val_mod.check_cvd_vpin("AK-47")["pass"] is True

    def test_few_trades_passes(self):
        trades = [{"price": 10.0, "time": 1000}] * 2
        with patch.object(_val_mod.price_db, "get_trade_history", return_value=trades):
            assert _val_mod.check_cvd_vpin("AK-47")["pass"] is True

    def test_vpin_over_threshold_fails(self):
        trades = [{"price": 10.0, "time": 1000}] * 10
        orig_en = _set_config("VPIN_ENABLED", True)
        orig_thresh = _val_mod.Config.VPIN_THRESHOLD
        try:
            _val_mod.Config.VPIN_THRESHOLD = 0.01
            with (
                patch.object(_val_mod.price_db, "get_trade_history", return_value=trades),
                patch("src.analysis.microstructure.compute_cvd", return_value=0.5),
                patch("src.analysis.microstructure.compute_vpin", return_value=0.9),
            ):
                result = _val_mod.check_cvd_vpin("AK-47")
            assert result["pass"] is False
        finally:
            _val_mod.Config.VPIN_ENABLED = orig_en
            _val_mod.Config.VPIN_THRESHOLD = orig_thresh


class TestCheckAdverseSelection:

    def test_disabled_passes(self):
        orig = _set_config("ADVERSER_SELECTION_ENABLED", False)
        try:
            assert _val_mod.check_adverse_selection("AK-47", [])["pass"] is True
        finally:
            _val_mod.Config.ADVERSER_SELECTION_ENABLED = orig

    def test_empty_records_passes(self):
        orig = _set_config("ADVERSER_SELECTION_ENABLED", True)
        try:
            assert _val_mod.check_adverse_selection("AK-47", [])["pass"] is True
        finally:
            _val_mod.Config.ADVERSER_SELECTION_ENABLED = orig

    def test_few_records_passes(self):
        orig = _set_config("ADVERSER_SELECTION_ENABLED", True)
        try:
            assert _val_mod.check_adverse_selection("AK-47", [{"p": 1}] * 2)["pass"] is True
        finally:
            _val_mod.Config.ADVERSER_SELECTION_ENABLED = orig

    def test_adverse_fail_returns_reason(self):
        orig = _set_config("ADVERSER_SELECTION_ENABLED", True)
        try:
            with patch("src.analysis.microstructure.adverse_selection_check", return_value=(False, "high kyle")):
                result = _val_mod.check_adverse_selection("AK-47", [{"p": 1}] * 5)
            assert result["pass"] is False
            assert "reason" in result
        finally:
            _val_mod.Config.ADVERSER_SELECTION_ENABLED = orig

    def test_adverse_pass(self):
        orig = _set_config("ADVERSER_SELECTION_ENABLED", True)
        try:
            with patch("src.analysis.microstructure.adverse_selection_check", return_value=(True, "")):
                result = _val_mod.check_adverse_selection("AK-47", [{"p": 1}] * 5)
            assert result["pass"] is True
        finally:
            _val_mod.Config.ADVERSER_SELECTION_ENABLED = orig


class TestCheckVolRegime:

    def test_disabled_passes(self):
        orig = _set_config("VOL_REGIME_ENABLED", False)
        try:
            result = _val_mod.check_vol_regime("AK-47", [])
            assert result["pass"] is True
            assert result["regime"] == "medium"
        finally:
            _val_mod.Config.VOL_REGIME_ENABLED = orig

    def test_empty_records_passes(self):
        orig = _set_config("VOL_REGIME_ENABLED", True)
        try:
            assert _val_mod.check_vol_regime("AK-47", [])["pass"] is True
        finally:
            _val_mod.Config.VOL_REGIME_ENABLED = orig

    def test_few_records_passes(self):
        orig = _set_config("VOL_REGIME_ENABLED", True)
        try:
            assert _val_mod.check_vol_regime("AK-47", [{"p": 1}] * 3)["pass"] is True
        finally:
            _val_mod.Config.VOL_REGIME_ENABLED = orig

    def test_high_vol_fails(self):
        orig = _set_config("VOL_REGIME_ENABLED", True)
        try:
            with (
                patch("src.analysis.microstructure.realized_vol_parkinson", return_value=2.0),
                patch("src.analysis.microstructure.classify_volatility_regime", return_value="high"),
            ):
                _val_mod.Config.VOL_REGIME_HIGH_THRESHOLD = 1.0
                result = _val_mod.check_vol_regime("AK-47", [{"p": 1}] * 10)
            assert result["pass"] is False
            assert result["regime"] == "high"
        finally:
            _val_mod.Config.VOL_REGIME_ENABLED = orig

    def test_low_vol_passes(self):
        orig = _set_config("VOL_REGIME_ENABLED", True)
        try:
            with (
                patch("src.analysis.microstructure.realized_vol_parkinson", return_value=0.1),
                patch("src.analysis.microstructure.classify_volatility_regime", return_value="low"),
            ):
                result = _val_mod.check_vol_regime("AK-47", [{"p": 1}] * 10)
            assert result["pass"] is True
            assert result["regime"] == "low"
        finally:
            _val_mod.Config.VOL_REGIME_ENABLED = orig


class TestCheckRollSpread:

    def test_disabled_passes(self):
        orig = _set_config("ROLL_MODEL_ENABLED", False)
        try:
            result = _val_mod.check_roll_spread("AK-47", [], 10.0)
            assert result["pass"] is True
            assert result["signal"] is None
        finally:
            _val_mod.Config.ROLL_MODEL_ENABLED = orig

    def test_empty_records_passes(self):
        orig = _set_config("ROLL_MODEL_ENABLED", True)
        try:
            assert _val_mod.check_roll_spread("AK-47", [], 10.0)["pass"] is True
        finally:
            _val_mod.Config.ROLL_MODEL_ENABLED = orig

    def test_few_records_passes(self):
        orig = _set_config("ROLL_MODEL_ENABLED", True)
        try:
            assert _val_mod.check_roll_spread("AK-47", [{"p": 1}] * 3, 10.0)["pass"] is True
        finally:
            _val_mod.Config.ROLL_MODEL_ENABLED = orig

    def test_expensive_signal_fails(self):
        orig = _set_config("ROLL_MODEL_ENABLED", True)
        try:
            trades = [{"price": 10.0}] * 5
            with patch("src.analysis.microstructure.roll_signal", return_value="expensive"):
                result = _val_mod.check_roll_spread("AK-47", trades, 10.0)
            assert result["pass"] is False
            assert result["signal"] == "expensive"
        finally:
            _val_mod.Config.ROLL_MODEL_ENABLED = orig

    def test_cheap_signal_passes(self):
        orig = _set_config("ROLL_MODEL_ENABLED", True)
        try:
            trades = [{"price": 10.0}] * 5
            with patch("src.analysis.microstructure.roll_signal", return_value="cheap"):
                result = _val_mod.check_roll_spread("AK-47", trades, 10.0)
            assert result["pass"] is True
            assert result["signal"] == "cheap"
        finally:
            _val_mod.Config.ROLL_MODEL_ENABLED = orig


class TestCheckVolumeProfilePOC:

    def test_disabled_returns_zero(self):
        orig = _set_config("VOLUME_PROFILE_ENABLED", False)
        try:
            assert _val_mod.check_volume_profile_poc("AK-47", []) == 0.0
        finally:
            _val_mod.Config.VOLUME_PROFILE_ENABLED = orig

    def test_empty_records_returns_zero(self):
        orig = _set_config("VOLUME_PROFILE_ENABLED", True)
        try:
            assert _val_mod.check_volume_profile_poc("AK-47", []) == 0.0
        finally:
            _val_mod.Config.VOLUME_PROFILE_ENABLED = orig

    def test_few_records_returns_zero(self):
        orig = _set_config("VOLUME_PROFILE_ENABLED", True)
        try:
            assert _val_mod.check_volume_profile_poc("AK-47", [{"p": 1}] * 3) == 0.0
        finally:
            _val_mod.Config.VOLUME_PROFILE_ENABLED = orig

    def test_returns_poc_price(self):
        orig = _set_config("VOLUME_PROFILE_ENABLED", True)
        try:
            trades = [{"price": 10.0}] * 10
            with patch("src.analysis.microstructure.volume_profile_poc", return_value=10.5):
                result = _val_mod.check_volume_profile_poc("AK-47", trades)
            assert result == 10.5
        finally:
            _val_mod.Config.VOLUME_PROFILE_ENABLED = orig


class TestCheckSlippage:

    def test_disabled_returns_zero(self):
        orig = _set_config("SLIPPAGE_GATE_ENABLED", False)
        try:
            assert _val_mod.check_slippage(5, 3, 10.0, 10.0, 12.0) == 0.0
        finally:
            _val_mod.Config.SLIPPAGE_GATE_ENABLED = orig

    def test_returns_slippage_pct(self):
        orig = _set_config("SLIPPAGE_GATE_ENABLED", True)
        try:
            with patch("src.analysis.microstructure.estimate_slippage", return_value=0.02):
                result = _val_mod.check_slippage(5, 3, 10.0, 10.0, 12.0)
            assert result == 2.0  # 0.02 * 100
        finally:
            _val_mod.Config.SLIPPAGE_GATE_ENABLED = orig


class TestCheckTodAdjustment:

    def test_disabled_returns_one(self):
        orig = _set_config("TIME_OF_DAY_ENABLED", False)
        try:
            assert _val_mod.check_tod_adjustment() == 1.0
        finally:
            _val_mod.Config.TIME_OF_DAY_ENABLED = orig

    def test_returns_multiplier(self):
        orig = _set_config("TIME_OF_DAY_ENABLED", True)
        try:
            with patch("src.analysis.microstructure.tod_multiplier", return_value=1.2):
                result = _val_mod.check_tod_adjustment()
            assert result == 1.2
        finally:
            _val_mod.Config.TIME_OF_DAY_ENABLED = orig

    def test_weekend_multiplier(self):
        orig_en = _set_config("TIME_OF_DAY_ENABLED", True)
        orig_we = _set_config("TIME_OF_DAY_WEEKEND_ENABLED", True)
        try:
            with (
                patch("src.analysis.microstructure.tod_multiplier", return_value=1.0),
                patch("src.analysis.microstructure.day_of_week_multiplier", return_value=1.5),
            ):
                result = _val_mod.check_tod_adjustment()
            assert result == 1.5
        finally:
            _val_mod.Config.TIME_OF_DAY_ENABLED = orig_en
            _val_mod.Config.TIME_OF_DAY_WEEKEND_ENABLED = orig_we


class TestEvaluateCrossMarketArb:

    def test_disabled_returns_not_viable(self):
        orig = _set_config("CROSS_MARKET_ENABLED", False)
        try:
            result = _val_mod.evaluate_cross_market_arb("AK-47", 10.0)
            assert result["is_viable"] is False
        finally:
            _val_mod.Config.CROSS_MARKET_ENABLED = orig

    def test_no_bids_returns_not_viable(self):
        orig = _set_config("CROSS_MARKET_ENABLED", True)
        try:
            result = _val_mod.evaluate_cross_market_arb("AK-47", 10.0, cs_bids=None)
            assert result["is_viable"] is False
        finally:
            _val_mod.Config.CROSS_MARKET_ENABLED = orig

    def test_viable_arb(self):
        orig = _set_config("CROSS_MARKET_ENABLED", True)
        try:
            snap = SimpleNamespace(has_data=True, provider_bids={"steam": 20.0})
            result = _val_mod.evaluate_cross_market_arb("AK-47", 10.0, cs_bids={"AK-47": snap})
            assert result["is_viable"] is True
            assert result["provider"] == "steam"
            assert result["bid"] == 20.0
        finally:
            _val_mod.Config.CROSS_MARKET_ENABLED = orig

    def test_not_viable_bid_too_low(self):
        orig = _set_config("CROSS_MARKET_ENABLED", True)
        try:
            snap = SimpleNamespace(has_data=True, provider_bids={"steam": 5.0})
            result = _val_mod.evaluate_cross_market_arb("AK-47", 10.0, cs_bids={"AK-47": snap})
            assert result["is_viable"] is False
            assert result["provider"] is None
        finally:
            _val_mod.Config.CROSS_MARKET_ENABLED = orig

    def test_no_data_snapshot(self):
        orig = _set_config("CROSS_MARKET_ENABLED", True)
        try:
            snap = SimpleNamespace(has_data=False, provider_bids={})
            result = _val_mod.evaluate_cross_market_arb("AK-47", 10.0, cs_bids={"AK-47": snap})
            assert result["is_viable"] is False
        finally:
            _val_mod.Config.CROSS_MARKET_ENABLED = orig

    def test_fee_aware_threshold(self):
        orig_en = _set_config("CROSS_MARKET_ENABLED", True)
        orig_fa = _set_config("CROSS_MARKET_FEE_AWARE", True)
        try:
            # Bid must cover ask + fees + margin
            snap = SimpleNamespace(has_data=True, provider_bids={"steam": 12.0})
            result = _val_mod.evaluate_cross_market_arb("AK-47", 10.0, cs_bids={"AK-47": snap})
            # threshold = 10 * (1 + 0.05 + 0.02 + 0.005 + 0.001) ≈ 10.76
            # 12.0 > 10.76 → viable
            assert result["is_viable"] is True
        finally:
            _val_mod.Config.CROSS_MARKET_ENABLED = orig_en
            _val_mod.Config.CROSS_MARKET_FEE_AWARE = orig_fa


class TestComputeMicrostructureScores:

    def test_disabled_returns_zero(self):
        orig = _set_config("COMPOSITE_SCORE_ENABLED", False)
        try:
            result = _val_mod.compute_microstructure_scores(
                "AK-47", 10.0, 12.0, 5, 3, [], 0.0, 0.0, 0.0, True, "medium",
            )
            assert result["composite_score"] == 0.0
        finally:
            _val_mod.Config.COMPOSITE_SCORE_ENABLED = orig

    def test_few_trades_returns_zero(self):
        orig = _set_config("COMPOSITE_SCORE_ENABLED", True)
        try:
            result = _val_mod.compute_microstructure_scores(
                "AK-47", 10.0, 12.0, 5, 3, [{"p": 1}] * 2, 0.0, 0.0, 0.0, True, "medium",
            )
            assert result["composite_score"] == 0.0
        finally:
            _val_mod.Config.COMPOSITE_SCORE_ENABLED = orig

    def test_returns_composite_score(self):
        orig = _set_config("COMPOSITE_SCORE_ENABLED", True)
        try:
            trades = [{"price": 10.0}] * 5
            with (
                patch("src.analysis.microstructure.simple_obi", return_value=1.0),
                patch("src.analysis.microstructure.kyle_lambda", return_value=0.01),
                patch("src.analysis.microstructure.compute_cvd", return_value=0.5),
                patch("src.analysis.microstructure.composite_buy_score", return_value=(0.75, {"obi": 1.0})),
            ):
                result = _val_mod.compute_microstructure_scores(
                    "AK-47", 10.0, 12.0, 5, 3, trades, 0.1, 0.5, 0.2, True, "medium",
                )
            assert result["composite_score"] == 0.75
        finally:
            _val_mod.Config.COMPOSITE_SCORE_ENABLED = orig


class TestEvaluateFeeSlippageTod:

    def test_spread_too_thin_fails(self):
        with patch("src.risk.price_validator.validate_arbitrage_profit"):
            result = _val_mod.evaluate_fee_slippage_tod(
                "AK-47", 10.0, 10.0, 10.01, 5, 3, 0.05, 0.05, 10.5,
            )
        assert result["pass"] is False

    def test_wide_spread_passes(self):
        with (
            patch("src.risk.price_validator.validate_arbitrage_profit"),
            patch.object(_val_mod, "check_slippage", return_value=0.0),
            patch.object(_val_mod, "check_tod_adjustment", return_value=1.0),
        ):
            result = _val_mod.evaluate_fee_slippage_tod(
                "AK-47", 10.0, 10.0, 15.0, 5, 3, 0.05, 0.05, 15.0,
            )
        assert result["pass"] is True

    def test_validation_failure_fails(self):
        from src.risk.price_validator import PriceValidationError
        with (
            patch("src.risk.price_validator.validate_arbitrage_profit", side_effect=PriceValidationError("low margin")),
            patch.object(_val_mod, "check_slippage", return_value=0.0),
            patch.object(_val_mod, "check_tod_adjustment", return_value=1.0),
        ):
            result = _val_mod.evaluate_fee_slippage_tod(
                "AK-47", 10.0, 10.0, 15.0, 5, 3, 0.05, 0.05, 15.0,
            )
        assert result["pass"] is False
        assert "reason" in result

    def test_cross_market_discount_passes(self):
        with (
            patch("src.risk.price_validator.validate_arbitrage_profit"),
            patch.object(_val_mod, "check_slippage", return_value=0.0),
            patch.object(_val_mod, "check_tod_adjustment", return_value=1.0),
        ):
            result = _val_mod.evaluate_fee_slippage_tod(
                "AK-47", 8.0, 10.0, 12.0, 5, 3, 0.05, 0.05, 15.0,
                cs_ask_price=20.0,
            )
        assert result["pass"] is True


class TestCheckSlippageAtRisk:

    def test_zero_prices_passes(self):
        result = _val_mod.check_slippage_at_risk("AK-47", 10.0, 0.0, 12.0, 5, 3)
        assert result["pass"] is True

    def test_low_slippage_passes(self):
        result = _val_mod.check_slippage_at_risk("AK-47", 10.0, 10.0, 10.01, 20, 20)
        assert result["pass"] is True

    def test_high_slippage_fails(self):
        result = _val_mod.check_slippage_at_risk(
            "AK-47", 10.0, 10.0, 5.0, 1, 1, max_slippage_pct=0.01,
        )
        assert result["pass"] is False
        assert "reason" in result

    def test_single_seller_depth_factor(self):
        # Single seller (ask_count=1) → depth_factor=2.0, spread=10% → slippage=20%
        result = _val_mod.check_slippage_at_risk("AK-47", 10.0, 10.0, 9.0, 1, 10)
        assert result["pass"] is False  # 20% > 5% default threshold
        assert result["slippage"] > 0

    def test_deep_book_lower_slippage(self):
        shallow = _val_mod.check_slippage_at_risk("AK-47", 10.0, 10.0, 9.0, 2, 10)
        deep = _val_mod.check_slippage_at_risk("AK-47", 10.0, 10.0, 9.0, 20, 10)
        assert deep["slippage"] < shallow["slippage"]

    def test_one_sided_book_concentration(self):
        balanced = _val_mod.check_slippage_at_risk("AK-47", 10.0, 10.0, 9.0, 10, 10)
        onesided = _val_mod.check_slippage_at_risk("AK-47", 10.0, 10.0, 9.0, 10, 1)
        assert onesided["slippage"] > balanced["slippage"]

    def test_concentration_ratio_below_03(self):
        """Heavy one-sided book (ratio < 0.3) gives 1.5x concentration."""
        result = _val_mod.check_slippage_at_risk("AK-47", 10.0, 10.0, 9.0, 10, 1)
        # ratio = 1/10 = 0.1 < 0.3 → concentration = 1.5
        assert result["slippage"] > 0

    def test_concentration_ratio_03_to_05(self):
        """Moderate one-sided book (0.3 < ratio < 0.5) gives 1.2x concentration."""
        result = _val_mod.check_slippage_at_risk("AK-47", 10.0, 10.0, 9.5, 10, 4)
        # ratio = 4/10 = 0.4 → concentration = 1.2
        assert result["slippage"] > 0

    def test_depth_factor_thin_book(self):
        """2-3 sellers → depth_factor = 1.5."""
        result = _val_mod.check_slippage_at_risk("AK-47", 10.0, 10.0, 9.5, 2, 10)
        assert result["slippage"] > 0

    def test_depth_factor_normal_book(self):
        """4-10 sellers → depth_factor = 1.0."""
        result = _val_mod.check_slippage_at_risk("AK-47", 10.0, 10.0, 9.5, 5, 10)
        assert result["slippage"] > 0


class TestVWAPFilterExtended:

    def test_sales_cache_fallback(self):
        """Uses sales_cache when DB returns empty (line 64)."""
        orig = _set_config("VWAP_FILTER_ENABLED", True)
        try:
            with (
                patch.object(_val_mod.price_db, "get_trade_history", return_value=[]),
                patch("src.analysis.microstructure.vwap_signal", return_value=0.5),
            ):
                cache = {"AK-47": [{"price": 10.0}] * 5}
                result = _val_mod.check_vwap_filter("AK-47", 10.0, sales_cache=cache)
            assert result["pass"] is True
        finally:
            _val_mod.Config.VWAP_FILTER_ENABLED = orig

    def test_vwap_above_threshold_fails(self):
        """best_ask above VWAP fails (lines 72-75)."""
        orig = _set_config("VWAP_FILTER_ENABLED", True)
        try:
            with (
                patch.object(_val_mod.price_db, "get_trade_history", return_value=[{"price": 10.0}] * 5),
                patch("src.analysis.microstructure.vwap_signal", return_value=None),
                patch("src.analysis.microstructure.compute_vwap", return_value=(10.0, 9.0, 11.0)),
            ):
                result = _val_mod.check_vwap_filter("AK-47", 12.0)
            assert result["pass"] is False
        finally:
            _val_mod.Config.VWAP_FILTER_ENABLED = orig


class TestCVDVPINExtended:

    def test_sales_cache_fallback(self):
        """Uses sales_cache when DB returns empty (line 90)."""
        trades = [{"price": 10.0, "time": 1000}] * 5
        with (
            patch.object(_val_mod.price_db, "get_trade_history", return_value=[]),
            patch("src.analysis.microstructure.compute_cvd", return_value=0.5),
        ):
            result = _val_mod.check_cvd_vpin("AK-47", sales_cache={"AK-47": trades})
        assert result["pass"] is True
        assert result["cvd"] == 0.5

    def test_vpin_disabled_returns_zero(self):
        """VPIN disabled returns 0 (line 95-96)."""
        trades = [{"price": 10.0, "time": 1000}] * 5
        orig = _set_config("VPIN_ENABLED", False)
        try:
            with (
                patch.object(_val_mod.price_db, "get_trade_history", return_value=trades),
                patch("src.analysis.microstructure.compute_cvd", return_value=0.5),
            ):
                result = _val_mod.check_cvd_vpin("AK-47")
            assert result["vpin"] == 0.0
        finally:
            _val_mod.Config.VPIN_ENABLED = orig


class TestEvaluateFeeSlippageTodExtended:

    def test_sandbox_logs_decision(self):
        """is_sandbox=True logs decisions to price_db (lines 416-423)."""
        with (
            patch("src.risk.price_validator.validate_arbitrage_profit"),
            patch.object(_val_mod, "check_slippage", return_value=0.0),
            patch.object(_val_mod, "check_tod_adjustment", return_value=1.0),
            patch.object(_val_mod.price_db, "log_decision") as mock_log,
        ):
            result = _val_mod.evaluate_fee_slippage_tod(
                "AK-47", 10.0, 10.0, 10.01, 5, 3, 0.05, 0.05, 10.5,
                is_sandbox=True,
            )
        assert result["pass"] is False
        mock_log.assert_called()

    def test_spread_fee_ratio_too_low(self):
        """Spread/fee ratio < 1.3 fails (lines 427-435)."""
        with (
            patch("src.risk.price_validator.validate_arbitrage_profit"),
            patch.object(_val_mod, "check_slippage", return_value=0.0),
            patch.object(_val_mod, "check_tod_adjustment", return_value=1.0),
        ):
            # spread_ratio = (10.3 - 10.0) / 10.0 = 0.03
            # total_cost = 0.05 + 0.005 = 0.055
            # min_spread = 0.055 + 0.05 = 0.105
            # 0.03 < 0.105 → fails at first check
            result = _val_mod.evaluate_fee_slippage_tod(
                "AK-47", 10.0, 10.0, 10.3, 5, 3, 0.05, 0.05, 10.5,
            )
        assert result["pass"] is False

    def test_tod_adjustment_applied(self):
        """TOD adjustment multiplies effective margin (line 440)."""
        with (
            patch("src.risk.price_validator.validate_arbitrage_profit") as mock_validate,
            patch.object(_val_mod, "check_slippage", return_value=0.0),
            patch.object(_val_mod, "check_tod_adjustment", return_value=1.5),
        ):
            _val_mod.evaluate_fee_slippage_tod(
                "AK-47", 10.0, 10.0, 15.0, 5, 3, 0.05, 0.05, 15.0,
            )
        # validate_arbitrage_profit should be called with adjusted margin
        call_kwargs = mock_validate.call_args[1]
        assert call_kwargs["min_profit_margin"] > 0.05


class TestCrossMarketArbExtended:

    def test_cs_bids_not_in_snapshots(self):
        """Title not in cs_bids logs debug (lines 292-296)."""
        orig = _set_config("CROSS_MARKET_ENABLED", True)
        try:
            snap = SimpleNamespace(has_data=True, provider_bids={"steam": 20.0})
            result = _val_mod.evaluate_cross_market_arb("M4A4", 10.0, cs_bids={"AK-47": snap})
            assert result["is_viable"] is False
        finally:
            _val_mod.Config.CROSS_MARKET_ENABLED = orig

    def test_no_provider_bids(self):
        """Empty provider_bids returns not viable."""
        orig = _set_config("CROSS_MARKET_ENABLED", True)
        try:
            snap = SimpleNamespace(has_data=True, provider_bids={})
            result = _val_mod.evaluate_cross_market_arb("AK-47", 10.0, cs_bids={"AK-47": snap})
            assert result["is_viable"] is False
        finally:
            _val_mod.Config.CROSS_MARKET_ENABLED = orig

    def test_zero_best_ask(self):
        """Zero best_ask skips threshold check."""
        orig = _set_config("CROSS_MARKET_ENABLED", True)
        try:
            snap = SimpleNamespace(has_data=True, provider_bids={"steam": 20.0})
            result = _val_mod.evaluate_cross_market_arb("AK-47", 0.0, cs_bids={"AK-47": snap})
            assert result["is_viable"] is False
        finally:
            _val_mod.Config.CROSS_MARKET_ENABLED = orig
