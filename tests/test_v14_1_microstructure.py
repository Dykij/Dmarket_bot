"""Unit tests for v14.1 microstructure instruments."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analysis.microstructure import (
    reservation_price, reservation_spread,
    compute_vwap, vwap_signal,
    estimate_slippage,
    classify_trade_lee_ready, compute_cvd, cvd_divergence,
    compute_vpin,
    tod_multiplier,
)


class TestAS:
    def test_neutral_inventory(self):
        r = reservation_price(10.0, 0, 0, 3, 0.4, 0.3, 7)
        assert abs(r - 10.0) < 0.01

    def test_full_inventory_skew_down(self):
        r = reservation_price(10.0, 3, 0, 3, 0.4, 0.3, 7)
        assert r < 10.0, f"Expected <10, got {r}"

    def test_accumulation_skew_up(self):
        r = reservation_price(10.0, 0, 3, 3, 0.4, 0.3, 7)
        assert r > 10.0, f"Expected >10, got {r}"

    def test_zero_vol(self):
        r = reservation_price(10.0, 3, 0, 3, 1e-9, 0.3, 7)
        assert r < 10.0

    def test_spread_bid_ask(self):
        bid, ask = reservation_spread(10.0, 10.0, 0.4, 0.3, 7)
        assert bid < 10.0 < ask
        assert abs(ask - 10.0) < 0.1

class TestVWAP:
    SALES = [{"price": 1.0}, {"price": 1.1}, {"price": 0.95}, {"price": 1.05}]

    def test_standard(self):
        v, vol, std = compute_vwap(self.SALES)
        assert 1.0 < v < 1.05
        assert vol == 4
        assert std > 0

    def test_signal_undervalued(self):
        s = vwap_signal(0.85, self.SALES, 0.90)
        assert s is not None
        assert s > 0

    def test_signal_overvalued(self):
        s = vwap_signal(1.20, self.SALES, 0.90)
        assert s is None

    def test_empty(self):
        v, vol, std = compute_vwap([])
        assert v == 0 and vol == 0

class TestSlippage:
    def test_baseline(self):
        s = estimate_slippage(10.0, 1, 500, 10.0, 9.5)
        assert 0 < s < 0.01

    def test_zero_volume(self):
        s = estimate_slippage(10.0, 1, 0, 10.0, 9.5)
        assert s > 0.0005

class TestCVD:
    SALES = [{"price": 1.0}, {"price": 1.1}, {"price": 0.95}, {"price": 1.05}]

    def test_lee_ready(self):
        d = classify_trade_lee_ready(1.1, 1.0)
        assert d == 1
        d = classify_trade_lee_ready(0.9, 1.0)
        assert d == -1
        d = classify_trade_lee_ready(0.0, 1.0)
        assert d is None

    def test_cvd_positive(self):
        c = compute_cvd(self.SALES, prev_mid=1.0)
        assert c > 0

    def test_divergence_bullish(self):
        d = cvd_divergence(10.0, -0.02)
        assert d == "bullish"

    def test_divergence_bearish(self):
        d = cvd_divergence(-10.0, 0.02)
        assert d == "bearish"

    def test_divergence_none(self):
        d = cvd_divergence(1.0, 0.001)
        assert d is None

class TestVPIN:
    def test_insufficient_data(self):
        v = compute_vpin([{"price": 1.0}] * 3, n_buckets=4)
        assert v is None

    def test_sufficient_data(self):
        sales = [{"price": 1.0}, {"price": 1.1}] * 10
        v = compute_vpin(sales, n_buckets=4)
        assert v is not None
        assert 0 <= v <= 1

class TestToD:
    def test_night_hour(self):
        import datetime
        tod = tod_multiplier(0, 24, 0.5, 1.0)
        assert abs(tod - 0.5) < 0.01

    def test_range(self):
        t = tod_multiplier(night_start_utc=0, night_end_utc=24,
                          night_factor=0.85, day_factor=1.0)
        assert abs(t - 0.85) < 0.01
