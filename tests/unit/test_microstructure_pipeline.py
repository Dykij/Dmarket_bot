"""Unit tests for microstructure_pipeline.py (v15.7)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.core.target_sniping.microstructure_pipeline import (
    MicrostructureResult,
    run_microstructure_pipeline,
)


class TestMicrostructureResult:
    """Tests for the MicrostructureResult dataclass."""

    def test_defaults(self) -> None:
        r = MicrostructureResult()
        assert r.passed is True
        assert r.reason == ""
        assert r.obi_signal == 0.0
        assert r.vwap_signal == 0.0
        assert r.cvd == 0.0
        assert r.vpin == 0.0
        assert r.vol_regime == "medium"
        assert r.trade_records == []
        assert r.multi_obi == 0.0


class TestRunMicrostructurePipeline:
    """Tests for run_microstructure_pipeline()."""

    @patch("src.core.target_sniping.microstructure_pipeline.Config")
    def test_strict_disabled_returns_passed(self, mock_config) -> None:
        """When STRICT_MICROSTRUCTURE_FILTERS=False, all checks are skipped."""
        mock_config.STRICT_MICROSTRUCTURE_FILTERS = False
        result = run_microstructure_pipeline(
            title="test",
            base_price=10.0,
            best_ask=10.0,
            best_bid=12.0,
            ask_count=5,
            bid_count=5,
        )
        assert result.passed is True
        assert result.reason == ""

    @patch("src.core.target_sniping.microstructure_pipeline.Config")
    def test_strict_enabled_obi_pass(self, mock_config) -> None:
        """OBI check passes with balanced order book."""
        mock_config.STRICT_MICROSTRUCTURE_FILTERS = True
        mock_config.OBI_ENABLED = True
        mock_config.OBI_MIN_RATIO = 0.5
        mock_config.QUEUE_IMBALANCE_ENABLED = False
        mock_config.MULTI_LEVEL_OBI_ENABLED = False
        mock_config.OFI_ENABLED = False
        mock_config.VWAP_FILTER_ENABLED = False
        mock_config.VPIN_ENABLED = False
        mock_config.CVD_ENABLED = False
        mock_config.ADVERSER_SELECTION_ENABLED = False
        mock_config.VOL_REGIME_ENABLED = False
        mock_config.ROLL_MODEL_ENABLED = False
        mock_config.VOLUME_PROFILE_ENABLED = False

        with patch("src.core.target_sniping.microstructure_pipeline.check_obi", return_value={"pass": True, "signal": 1.0}):
            with patch("src.core.target_sniping.microstructure_pipeline.check_slippage_at_risk", return_value={"pass": True}):
                with patch("src.core.target_sniping.microstructure_pipeline.check_vwap_filter", return_value={"pass": True, "signal": 0.0}):
                    with patch("src.core.target_sniping.microstructure_pipeline.check_cvd_vpin", return_value={"pass": True, "cvd": 0.0, "vpin": 0.0, "trade_records": []}):
                        with patch("src.core.target_sniping.microstructure_pipeline.check_adverse_selection", return_value={"pass": True}):
                            with patch("src.core.target_sniping.microstructure_pipeline.check_vol_regime", return_value={"pass": True, "regime": "medium"}):
                                with patch("src.core.target_sniping.microstructure_pipeline.check_roll_spread", return_value={"pass": True}):
                                    with patch("src.core.target_sniping.microstructure_pipeline.check_volume_profile_poc", return_value=0.0):
                                        result = run_microstructure_pipeline(
                                            title="AK-47 | Redline (FT)",
                                            base_price=10.0,
                                            best_ask=10.0,
                                            best_bid=12.0,
                                            ask_count=5,
                                            bid_count=5,
                                        )
        assert result.passed is True
        assert result.obi_signal == 1.0

    @patch("src.core.target_sniping.microstructure_pipeline.Config")
    def test_obi_failure_blocks(self, mock_config) -> None:
        """OBI check failure blocks the candidate."""
        mock_config.STRICT_MICROSTRUCTURE_FILTERS = True
        mock_config.OBI_ENABLED = True

        with patch("src.core.target_sniping.microstructure_pipeline.check_obi", return_value={"pass": False, "signal": 0.2}):
            result = run_microstructure_pipeline(
                title="test",
                base_price=10.0,
                best_ask=10.0,
                best_bid=12.0,
                ask_count=5,
                bid_count=5,
            )
        assert result.passed is False
        assert "OBI" in result.reason

    @patch("src.core.target_sniping.microstructure_pipeline.Config")
    def test_vpin_high_blocks(self, mock_config) -> None:
        """High VPIN blocks the candidate."""
        mock_config.STRICT_MICROSTRUCTURE_FILTERS = True
        mock_config.OBI_ENABLED = True
        mock_config.OBI_MIN_RATIO = 0.5
        mock_config.QUEUE_IMBALANCE_ENABLED = False
        mock_config.MULTI_LEVEL_OBI_ENABLED = False
        mock_config.OFI_ENABLED = False
        mock_config.VWAP_FILTER_ENABLED = False
        mock_config.VPIN_ENABLED = True
        mock_config.VPIN_THRESHOLD = 0.8
        mock_config.CVD_ENABLED = False
        mock_config.ADVERSER_SELECTION_ENABLED = False
        mock_config.VOL_REGIME_ENABLED = False
        mock_config.ROLL_MODEL_ENABLED = False
        mock_config.VOLUME_PROFILE_ENABLED = False

        with patch("src.core.target_sniping.microstructure_pipeline.check_obi", return_value={"pass": True, "signal": 1.0}):
            with patch("src.core.target_sniping.microstructure_pipeline.check_slippage_at_risk", return_value={"pass": True}):
                with patch("src.core.target_sniping.microstructure_pipeline.check_vwap_filter", return_value={"pass": True, "signal": 0.0}):
                    with patch("src.core.target_sniping.microstructure_pipeline.check_cvd_vpin", return_value={"pass": False, "cvd": 0.0, "vpin": 0.95, "trade_records": []}):
                        result = run_microstructure_pipeline(
                            title="test",
                            base_price=10.0,
                            best_ask=10.0,
                            best_bid=12.0,
                            ask_count=5,
                            bid_count=5,
                        )
        assert result.passed is False
        assert "VPIN" in result.reason
