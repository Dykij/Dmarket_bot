"""Tests for ranking.py — volume-weighted spread ranking."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.core.target_sniping.ranking import (
    clear_trend_cache,
    rank_candidates_by_spread,
)


def _make_item(title: str = "AK-47 | Redline", price_cents: int = 1000):
    return {"title": title, "price": {"USD": str(price_cents)}}


def _make_agg(best_bid: float = 12.0, best_ask: float = 10.0, ask_count: int = 5, bid_count: int = 3):
    return {"best_bid": best_bid, "best_ask": best_ask, "ask_count": ask_count, "bid_count": bid_count}


class TestRankCandidatesBySpread:

    def test_basic_ranking(self):
        items = [_make_item("A"), _make_item("B")]
        agg = {"A": _make_agg(15.0, 10.0), "B": _make_agg(13.0, 10.0)}
        ranked = rank_candidates_by_spread(items, agg)
        assert len(ranked) == 2
        assert ranked[0][0] == "A"  # Higher spread ranks first

    def test_empty_items(self):
        assert rank_candidates_by_spread([], {}) == []

    def test_no_agg_prices_filters_out(self):
        items = [_make_item("A")]
        ranked = rank_candidates_by_spread(items, {})
        assert ranked == []

    def test_zero_bid_filtered(self):
        items = [_make_item("A")]
        agg = {"A": {"best_bid": 0, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        ranked = rank_candidates_by_spread(items, agg)
        assert ranked == []

    def test_zero_ask_filtered(self):
        items = [_make_item("A")]
        agg = {"A": {"best_bid": 12.0, "best_ask": 0, "ask_count": 5, "bid_count": 3}}
        ranked = rank_candidates_by_spread(items, agg)
        assert ranked == []

    def test_max_price_filter(self):
        items = [_make_item("Cheap", 500), _make_item("Expensive", 5000)]
        agg = {"Cheap": _make_agg(), "Expensive": _make_agg()}
        ranked = rank_candidates_by_spread(items, agg, max_price_usd=10.0)
        assert len(ranked) == 1
        assert ranked[0][0] == "Cheap"

    def test_no_title_filtered(self):
        items = [{"price": {"USD": "1000"}}]
        agg = {"": _make_agg()}
        ranked = rank_candidates_by_spread(items, agg)
        assert ranked == []

    def test_low_spread_filtered(self):
        """Items with spread below min_spread_pct are filtered."""
        items = [_make_item("A")]
        # Spread = 0.01 / 10.0 = 0.1% — below default min
        agg = {"A": {"best_bid": 10.01, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        ranked = rank_candidates_by_spread(items, agg)
        assert ranked == []

    def test_negative_margin_filtered(self):
        """Items with negative net margin after fees are filtered."""
        items = [_make_item("A")]
        # Spread = 0.1 / 10.0 = 1%, but fees = 5.5% → negative margin
        agg = {"A": {"best_bid": 10.1, "best_ask": 10.0, "ask_count": 5, "bid_count": 3}}
        ranked = rank_candidates_by_spread(items, agg)
        assert ranked == []

    def test_low_fee_boost(self):
        """Low-fee items get a score boost."""
        items = [_make_item("A"), _make_item("B")]
        agg = {"A": _make_agg(), "B": _make_agg()}
        with patch("src.core.target_sniping.ranking.Config") as mock_config:
            mock_config.INTRA_MIN_SPREAD_PCT = 0.1
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.SEASONAL_TIMING_ENABLED = False
            mock_config.COMMISSION_OPTIMIZER_ENABLED = True
            mock_config.FILLER_TRACKING_ENABLED = False
            ranked_no_fee = rank_candidates_by_spread(items, agg, low_fee_titles=set())
            ranked_with_fee = rank_candidates_by_spread(items, agg, low_fee_titles={"A"})

        # With low fee, A should score higher relative to B
        score_a_no = next(s for t, s in ranked_no_fee if t == "A")
        score_a_with = next(s for t, s in ranked_with_fee if t == "A")
        assert score_a_with > score_a_no

    def test_volume_affects_score(self):
        """Higher volume = higher score."""
        items = [_make_item("A"), _make_item("B")]
        agg = {
            "A": _make_agg(12.0, 10.0, ask_count=1, bid_count=1),
            "B": _make_agg(12.0, 10.0, ask_count=50, bid_count=50),
        }
        ranked = rank_candidates_by_spread(items, agg)
        assert ranked[0][0] == "B"  # Higher volume ranks first

    def test_clear_trend_cache(self):
        clear_trend_cache()  # Should not raise

    def test_filler_skin_boost(self):
        """Filler skins get +8% boost."""
        items = [_make_item("A"), _make_item("B")]
        agg = {"A": _make_agg(), "B": _make_agg()}
        with (
            patch("src.core.target_sniping.ranking.Config") as mock_config,
            patch("src.analytics.filler_tracker.is_filler") as mock_filler,
        ):
            mock_config.INTRA_MIN_SPREAD_PCT = 0.1
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.SEASONAL_TIMING_ENABLED = False
            mock_config.COMMISSION_OPTIMIZER_ENABLED = False
            mock_config.FILLER_TRACKING_ENABLED = True
            mock_filler.side_effect = lambda t: t == "A"

            ranked = rank_candidates_by_spread(items, agg)

        score_a = next(s for t, s in ranked if t == "A")
        score_b = next(s for t, s in ranked if t == "B")
        # A gets filler boost, B doesn't
        assert score_a > score_b

    def test_trend_boost_uptrend(self):
        """Items in uptrend get +10% boost."""
        items = [_make_item("A")]
        agg = {"A": _make_agg()}
        price_histories = {"A": [10.0, 11.0, 12.0, 13.0, 14.0] * 3}
        with (
            patch("src.core.target_sniping.ranking.Config") as mock_config,
            patch("src.analysis.algo_pack.trend_strength.trend_strength", return_value=0.8),
        ):
            mock_config.INTRA_MIN_SPREAD_PCT = 0.1
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.SEASONAL_TIMING_ENABLED = False
            mock_config.COMMISSION_OPTIMIZER_ENABLED = False
            mock_config.FILLER_TRACKING_ENABLED = False
            ranked_no_hist = rank_candidates_by_spread(items, agg)
            ranked_with_hist = rank_candidates_by_spread(items, agg, price_histories=price_histories)

        score_no = ranked_no_hist[0][1]
        score_with = ranked_with_hist[0][1]
        assert score_with > score_no

    def test_trend_penalty_downtrend(self):
        """Items in downtrend get -15% penalty."""
        items = [_make_item("A")]
        agg = {"A": _make_agg()}
        price_histories = {"A": [14.0, 13.0, 12.0, 11.0, 10.0] * 3}
        with (
            patch("src.core.target_sniping.ranking.Config") as mock_config,
            patch("src.analysis.algo_pack.trend_strength.trend_strength", return_value=0.1),
        ):
            mock_config.INTRA_MIN_SPREAD_PCT = 0.1
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.SEASONAL_TIMING_ENABLED = False
            mock_config.COMMISSION_OPTIMIZER_ENABLED = False
            mock_config.FILLER_TRACKING_ENABLED = False
            ranked_no_hist = rank_candidates_by_spread(items, agg)
            ranked_with_hist = rank_candidates_by_spread(items, agg, price_histories=price_histories)

        score_no = ranked_no_hist[0][1]
        score_with = ranked_with_hist[0][1]
        assert score_with < score_no

    def test_seasonal_timing_adjustment(self):
        """Seasonal timing multiplier affects min spread."""
        items = [_make_item("A")]
        agg = {"A": _make_agg(12.0, 10.0)}
        with (
            patch("src.core.target_sniping.ranking.Config") as mock_config,
            patch("src.analysis.seasonal.get_timing_multiplier", return_value=2.0),
        ):
            mock_config.INTRA_MIN_SPREAD_PCT = 10.0  # Very high min spread
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.SEASONAL_TIMING_ENABLED = True
            mock_config.COMMISSION_OPTIMIZER_ENABLED = False
            mock_config.FILLER_TRACKING_ENABLED = False
            ranked = rank_candidates_by_spread(items, agg)

        # With seasonal multiplier 2x, min spread = 20%, but our spread is 20% → passes
        assert len(ranked) == 1

    def test_seasonal_timing_exception_handled(self):
        """Seasonal timing import failure is caught."""
        items = [_make_item("A")]
        agg = {"A": _make_agg()}
        with (
            patch("src.core.target_sniping.ranking.Config") as mock_config,
            patch("src.analysis.seasonal.get_timing_multiplier", side_effect=Exception("no module")),
        ):
            mock_config.INTRA_MIN_SPREAD_PCT = 0.1
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.SEASONAL_TIMING_ENABLED = True
            mock_config.COMMISSION_OPTIMIZER_ENABLED = False
            mock_config.FILLER_TRACKING_ENABLED = False
            ranked = rank_candidates_by_spread(items, agg)
        # Should still work despite seasonal import failure
        assert len(ranked) == 1

    def test_regime_detector_adjusts_threshold(self):
        """Regime detector can adjust spread threshold."""
        items = [_make_item("A")]
        agg = {"A": _make_agg(12.0, 10.0)}
        mock_detector = MagicMock()
        mock_detector.update.return_value = "trending"
        mock_detector.get_params.return_value = SimpleNamespace(min_spread_mult=0.5)
        with (
            patch("src.core.target_sniping.ranking.Config") as mock_config,
            patch("src.core.target_sniping.ranking._regime_detector", mock_detector),
        ):
            mock_config.INTRA_MIN_SPREAD_PCT = 20.0  # High threshold
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.SEASONAL_TIMING_ENABLED = False
            mock_config.COMMISSION_OPTIMIZER_ENABLED = False
            mock_config.FILLER_TRACKING_ENABLED = False
            ranked = rank_candidates_by_spread(items, agg)
        # With regime_mult=0.5, effective threshold = 10%, spread = 20% → passes
        assert len(ranked) == 1

    def test_bollinger_squeeze_boost(self):
        """Bollinger squeeze near support gives +15% boost."""
        items = [_make_item("A")]
        agg = {"A": _make_agg(12.0, 10.0)}
        price_histories = {"A": [10.0 + i * 0.1 for i in range(25)]}
        with (
            patch("src.core.target_sniping.ranking.Config") as mock_config,
            patch("src.analysis.microstructure.volatility.bollinger_squeeze_signal", return_value="squeeze"),
            patch("src.analysis.microstructure.volatility.bollinger_pctb", return_value=0.2),
        ):
            mock_config.INTRA_MIN_SPREAD_PCT = 0.1
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.SEASONAL_TIMING_ENABLED = False
            mock_config.COMMISSION_OPTIMIZER_ENABLED = False
            mock_config.FILLER_TRACKING_ENABLED = False
            ranked_no_bb = rank_candidates_by_spread(items, agg)
            ranked_with_bb = rank_candidates_by_spread(items, agg, price_histories=price_histories)
        assert ranked_with_bb[0][1] > ranked_no_bb[0][1]

    def test_bollinger_expanded_penalty(self):
        """Bollinger expanded bands give -5% penalty vs squeeze."""
        items = [_make_item("A")]
        agg = {"A": _make_agg(12.0, 10.0)}
        price_histories = {"A": [10.0 + i * 0.1 for i in range(25)]}
        with (
            patch("src.core.target_sniping.ranking.Config") as mock_config,
            patch("src.analysis.microstructure.volatility.bollinger_squeeze_signal") as mock_sq,
            patch("src.analysis.microstructure.volatility.bollinger_pctb") as mock_pctb,
        ):
            mock_config.INTRA_MIN_SPREAD_PCT = 0.1
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.SEASONAL_TIMING_ENABLED = False
            mock_config.COMMISSION_OPTIMIZER_ENABLED = False
            mock_config.FILLER_TRACKING_ENABLED = False
            # Expanded → score *= 0.95
            mock_sq.return_value = "expanded"
            mock_pctb.return_value = 0.5
            ranked_expanded = rank_candidates_by_spread(items, agg, price_histories=price_histories)
            # Squeeze near support → score *= 1.15
            mock_sq.return_value = "squeeze"
            mock_pctb.return_value = 0.2
            ranked_squeeze = rank_candidates_by_spread(items, agg, price_histories=price_histories)
        assert ranked_expanded[0][1] < ranked_squeeze[0][1]

    def test_bollinger_oversold_boost(self):
        """Bollinger %B < 0 (oversold) gives +10% boost."""
        items = [_make_item("A")]
        agg = {"A": _make_agg(12.0, 10.0)}
        price_histories = {"A": [10.0 + i * 0.1 for i in range(25)]}
        with (
            patch("src.core.target_sniping.ranking.Config") as mock_config,
            patch("src.analysis.microstructure.volatility.bollinger_squeeze_signal", return_value="normal"),
            patch("src.analysis.microstructure.volatility.bollinger_pctb", return_value=-0.1),
        ):
            mock_config.INTRA_MIN_SPREAD_PCT = 0.1
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.SEASONAL_TIMING_ENABLED = False
            mock_config.COMMISSION_OPTIMIZER_ENABLED = False
            mock_config.FILLER_TRACKING_ENABLED = False
            ranked_no_bb = rank_candidates_by_spread(items, agg)
            ranked_with_bb = rank_candidates_by_spread(items, agg, price_histories=price_histories)
        assert ranked_with_bb[0][1] > ranked_no_bb[0][1]

    def test_bollinger_overbought_penalty(self):
        """Bollinger %B > 1 (overbought) gives -15% penalty."""
        items = [_make_item("A")]
        agg = {"A": _make_agg(12.0, 10.0)}
        price_histories = {"A": [10.0 + i * 0.1 for i in range(25)]}
        with (
            patch("src.core.target_sniping.ranking.Config") as mock_config,
            patch("src.analysis.microstructure.volatility.bollinger_squeeze_signal", return_value="normal"),
            patch("src.analysis.microstructure.volatility.bollinger_pctb", return_value=1.2),
        ):
            mock_config.INTRA_MIN_SPREAD_PCT = 0.1
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.SEASONAL_TIMING_ENABLED = False
            mock_config.COMMISSION_OPTIMIZER_ENABLED = False
            mock_config.FILLER_TRACKING_ENABLED = False
            ranked_no_bb = rank_candidates_by_spread(items, agg)
            ranked_with_bb = rank_candidates_by_spread(items, agg, price_histories=price_histories)
        assert ranked_with_bb[0][1] < ranked_no_bb[0][1]

    def test_hurst_trending_boost(self):
        """Hurst > 0.6 (trending) gives +8% boost."""
        items = [_make_item("A")]
        agg = {"A": _make_agg(12.0, 10.0)}
        price_histories = {"A": [10.0 + i * 0.01 for i in range(50)]}
        with (
            patch("src.core.target_sniping.ranking.Config") as mock_config,
            patch("src.analysis.algo_pack.regime_detector.hurst_exponent", return_value=0.7),
        ):
            mock_config.INTRA_MIN_SPREAD_PCT = 0.1
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.SEASONAL_TIMING_ENABLED = False
            mock_config.COMMISSION_OPTIMIZER_ENABLED = False
            mock_config.FILLER_TRACKING_ENABLED = False
            ranked_no_h = rank_candidates_by_spread(items, agg)
            ranked_with_h = rank_candidates_by_spread(items, agg, price_histories=price_histories)
        assert ranked_with_h[0][1] > ranked_no_h[0][1]

    def test_hurst_mean_reversion_boost(self):
        """Hurst < 0.4 (mean-reverting) gives +5% boost."""
        items = [_make_item("A")]
        agg = {"A": _make_agg(12.0, 10.0)}
        price_histories = {"A": [10.0 + i * 0.01 for i in range(50)]}
        with (
            patch("src.core.target_sniping.ranking.Config") as mock_config,
            patch("src.analysis.algo_pack.regime_detector.hurst_exponent", return_value=0.3),
        ):
            mock_config.INTRA_MIN_SPREAD_PCT = 0.1
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.SEASONAL_TIMING_ENABLED = False
            mock_config.COMMISSION_OPTIMIZER_ENABLED = False
            mock_config.FILLER_TRACKING_ENABLED = False
            ranked_no_h = rank_candidates_by_spread(items, agg)
            ranked_with_h = rank_candidates_by_spread(items, agg, price_histories=price_histories)
        assert ranked_with_h[0][1] > ranked_no_h[0][1]

    def test_filler_exception_handled(self):
        """Filler tracker import failure is caught."""
        items = [_make_item("A")]
        agg = {"A": _make_agg()}
        with (
            patch("src.core.target_sniping.ranking.Config") as mock_config,
            patch("src.analytics.filler_tracker.is_filler", side_effect=Exception("no module")),
        ):
            mock_config.INTRA_MIN_SPREAD_PCT = 0.1
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.SEASONAL_TIMING_ENABLED = False
            mock_config.COMMISSION_OPTIMIZER_ENABLED = False
            mock_config.FILLER_TRACKING_ENABLED = True
            ranked = rank_candidates_by_spread(items, agg)
        assert len(ranked) == 1
