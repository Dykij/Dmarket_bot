"""
Unit tests for v12.0 SnipingLoop selective-oracle ranking.

Phase 1: _rank_candidates_by_spread must sort by DMarket bid-ask spread
descending and filter out items that don't clear the spread gate.
Run: python -m pytest tests/unit/test_v12_selective_oracle.py -v
"""

import pytest
from decimal import Decimal
from src.config import Config
from src.core.target_sniping.filter import _FilterMixin


@pytest.fixture(autouse=True)
def _reset_config_for_tests(monkeypatch):
    """Isolate ranking tests from local .env overrides."""
    monkeypatch.setattr(Config, "MIN_SPREAD_PCT", 2.0)
    monkeypatch.setattr(Config, "WITHDRAWAL_FEE_RATE", 0.015)
    monkeypatch.setattr(Config, "INTRA_MIN_SPREAD_PCT", 1.0)
    monkeypatch.setattr(Config, "COMMISSION_OPTIMIZER_ENABLED", False)
    monkeypatch.setattr(Config, "FILLER_TRACKING_ENABLED", False)
    monkeypatch.setattr(Config, "SEASONAL_TIMING_ENABLED", False)


class TestRankCandidatesBySpread:
    """_FilterMixin._rank_candidates_by_spread behaviour."""

    def test_empty_input(self):
        result = _FilterMixin._rank_candidates_by_spread([], {})
        assert result == []

    def test_sorts_by_net_margin_descending(self):
        # v14.8: ranking uses fee-aware net margin * liquidity, not raw spread.
        items = [
            {"title": "AK-47 | Redline (Field-Tested)"},
            {"title": "AWP | Asiimov (Field-Tested)"},
            {"title": "USP-S | Kill Confirmed (Minimal Wear)"},
        ]
        agg = {
            "AK-47 | Redline (Field-Tested)": {
                # 20% spread, high net margin after fees
                "best_bid": 12.0, "best_ask": 10.0, "ask_count": 1, "bid_count": 1,
            },
            "AWP | Asiimov (Field-Tested)": {
                # Big absolute spread but lower margin% after fees
                "best_bid": 100.0, "best_ask": 85.0, "ask_count": 1, "bid_count": 1,
            },
            "USP-S | Kill Confirmed (Minimal Wear)": {
                # Spread 3.0 (>5% of 21 = 1.05, so clears the gate)
                "best_bid": 24.0, "best_ask": 21.0, "ask_count": 1, "bid_count": 1,
            },
        }
        result = _FilterMixin._rank_candidates_by_spread(items, agg)
        # AK has highest net margin% -> ranks first with equal liquidity
        assert [t for t, _ in result] == [
            "AK-47 | Redline (Field-Tested)",
            "AWP | Asiimov (Field-Tested)",
            "USP-S | Kill Confirmed (Minimal Wear)",
        ]
        assert result[0][1] > result[1][1] > result[2][1]

    def test_filters_zero_bid_or_ask(self):
        items = [{"title": "X"}, {"title": "Y"}, {"title": "Z"}]
        agg = {
            "X": {"best_bid": 10.0, "best_ask": 9.0, "ask_count": 1, "bid_count": 1},
            "Y": {"best_bid": 0.0, "best_ask": 9.0, "ask_count": 1, "bid_count": 1},  # no bid
            "Z": {"best_bid": 10.0, "best_ask": 0.0, "ask_count": 1, "bid_count": 1},  # no ask
        }
        result = _FilterMixin._rank_candidates_by_spread(items, agg)
        assert [t for t, _ in result] == ["X"]

    def test_filters_unprofitable_after_fees(self):
        """Items with net margin <= 0 after fees must be filtered out."""
        items = [{"title": "Flat"}, {"title": "Wide"}]
        agg = {
            # 2% spread is below fee stack (3%), so net margin is negative -> filtered.
            "Flat": {"best_bid": 10.2, "best_ask": 10.0, "ask_count": 1, "bid_count": 1},
            # 20% spread leaves positive net margin after fees.
            "Wide": {"best_bid": 12.0, "best_ask": 10.0, "ask_count": 1, "bid_count": 1},
        }
        result = _FilterMixin._rank_candidates_by_spread(items, agg)
        # v14.8: fee-aware ranking drops Flat because it cannot cover fees + target margin.
        assert [t for t, _ in result] == ["Wide"]

    def test_skips_items_without_agg_entry(self):
        items = [{"title": "Known"}, {"title": "Unknown"}]
        agg = {
            "Known": {"best_bid": 12.0, "best_ask": 10.0, "ask_count": 1, "bid_count": 1},
            # "Unknown" intentionally missing
        }
        result = _FilterMixin._rank_candidates_by_spread(items, agg)
        assert [t for t, _ in result] == ["Known"]

    def test_top_k_selection(self):
        """Verify the calling pattern in core.py: ranked[:ORACLE_TOP_K_VALIDATE]."""
        items = [{"title": f"Item {i}"} for i in range(10)]
        agg = {}
        for i in range(10):
            agg[f"Item {i}"] = {
                "best_bid": 100.0 + i,
                "best_ask": 10.0,
                "ask_count": 1,
                "bid_count": 1,
            }
        result = _FilterMixin._rank_candidates_by_spread(items, agg)
        top_5 = [t for t, _ in result[:5]]
        # Sorted by spread desc: Item 9 has biggest spread (109.0)
        assert top_5[0] == "Item 9"
        assert top_5[-1] == "Item 5"
        assert len(top_5) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
