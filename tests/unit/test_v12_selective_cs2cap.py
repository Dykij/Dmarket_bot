"""
Unit tests for v12.0 SnipingLoop selective-CS2Cap ranking.

Phase 1: _rank_candidates_by_spread must sort by DMarket bid-ask spread
descending and filter out items that don't clear the spread gate.
Run: python -m pytest tests/unit/test_v12_selective_cs2cap.py -v
"""

import pytest
from src.core.target_sniping.filter import _FilterMixin


class TestRankCandidatesBySpread:
    """_FilterMixin._rank_candidates_by_spread behaviour."""

    def test_empty_input(self):
        result = _FilterMixin._rank_candidates_by_spread([], {})
        assert result == []

    def test_sorts_by_spread_descending(self):
        items = [
            {"title": "AK-47 | Redline (Field-Tested)"},
            {"title": "AWP | Asiimov (Field-Tested)"},
            {"title": "USP-S | Kill Confirmed (Minimal Wear)"},
        ]
        agg = {
            "AK-47 | Redline (Field-Tested)": {
                "best_bid": 12.0, "best_ask": 10.0, "ask_count": 1, "bid_count": 1,
            },
            "AWP | Asiimov (Field-Tested)": {
                # Big spread (15.0)
                "best_bid": 100.0, "best_ask": 85.0, "ask_count": 1, "bid_count": 1,
            },
            "USP-S | Kill Confirmed (Minimal Wear)": {
                # Spread 3.0 (>5% of 21 = 1.05, so clears the gate)
                "best_bid": 24.0, "best_ask": 21.0, "ask_count": 1, "bid_count": 1,
            },
        }
        result = _FilterMixin._rank_candidates_by_spread(items, agg)
        assert [t for t, _ in result] == [
            "AWP | Asiimov (Field-Tested)",     # spread 15.0
            "USP-S | Kill Confirmed (Minimal Wear)",  # spread 3.0
            "AK-47 | Redline (Field-Tested)",   # spread 2.0
        ]
        assert result[0][1] == 15.0

    def test_filters_zero_bid_or_ask(self):
        items = [{"title": "X"}, {"title": "Y"}, {"title": "Z"}]
        agg = {
            "X": {"best_bid": 10.0, "best_ask": 9.0, "ask_count": 1, "bid_count": 1},
            "Y": {"best_bid": 0.0, "best_ask": 9.0, "ask_count": 1, "bid_count": 1},  # no bid
            "Z": {"best_bid": 10.0, "best_ask": 0.0, "ask_count": 1, "bid_count": 1},  # no ask
        }
        result = _FilterMixin._rank_candidates_by_spread(items, agg)
        assert [t for t, _ in result] == ["X"]

    def test_filters_below_min_spread(self):
        """Items with bid <= ask * 1.05 must be filtered out (5% gate)."""
        items = [{"title": "Flat"}, {"title": "Wide"}]
        agg = {
            "Flat": {"best_bid": 10.5, "best_ask": 10.0, "ask_count": 1, "bid_count": 1},  # 5% exactly
            "Wide": {"best_bid": 12.0, "best_ask": 10.0, "ask_count": 1, "bid_count": 1},   # 20%
        }
        result = _FilterMixin._rank_candidates_by_spread(items, agg)
        # INTRA_MIN_SPREAD_PCT default is 5.0, so bid > ask * 1.05 is the gate
        # (i.e. 10.5 > 10.5 is False, so Flat is filtered out).
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
        """Verify the calling pattern in core.py: ranked[:CS2CAP_TOP_K_VALIDATE]."""
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
