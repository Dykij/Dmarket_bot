"""Regression tests: get_recent_prices returns NEWEST FIRST; PVC / peak-avoidance / OFI must handle that."""
import time

import pytest

from src.core.target_sniping import demand_strategy as ds


def _db(monkeypatch, prices_oldest_first):
    now = time.time()
    n = len(prices_oldest_first)
    rows = [(p, now - (n - i) * 3600) for i, p in enumerate(prices_oldest_first)]
    rows.reverse()  # newest first, exactly like PriceHistoryDB.get_recent_prices
    monkeypatch.setattr(ds.price_db, "get_recent_prices", lambda title, days=7: rows)


@pytest.fixture(autouse=True)
def _clean():
    ds._obi_history.clear()
    ds._obi_ewma.clear()
    yield
    ds._obi_history.clear()
    ds._obi_ewma.clear()


def _rising_obi(title):
    ds._obi_history[title] = [0.3, 0.4, 0.5, 0.6]


def test_pvc_no_boost_when_price_falls(monkeypatch):
    monkeypatch.setattr(ds.Config, "PVC_ENABLED", True)
    _db(monkeypatch, [10.0, 9.5, 9.0, 8.5, 8.0, 7.5, 7.0])
    _rising_obi("T")
    assert ds._apply_pvc_multiplier(1.0, "T") == pytest.approx(1.0)


def test_pvc_boost_when_price_rises(monkeypatch):
    monkeypatch.setattr(ds.Config, "PVC_ENABLED", True)
    _db(monkeypatch, [7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0])
    _rising_obi("T")
    assert ds._apply_pvc_multiplier(1.0, "T") == pytest.approx(1.2)


def test_peak_uptrend_detected_on_rising_series(monkeypatch):
    _db(monkeypatch, [8.0, 8.0, 8.0, 8.0, 8.1, 8.6, 9.2, 9.9, 10.6])
    score, parts = ds._apply_peak_avoidance(1.0, "T", 10.6)
    assert score == pytest.approx(0.90)
    assert parts == ["uptrend-peak-10%"]


def test_peak_plain_penalty_on_falling_series(monkeypatch):
    _db(monkeypatch, [10.6, 9.9, 9.2, 8.6, 8.1, 8.0, 8.0, 8.0, 8.0])
    score, parts = ds._apply_peak_avoidance(1.0, "T", 10.6)
    assert score == pytest.approx(0.85)
    assert parts == ["peak-penalty-15%"]


def test_ofi_first_observation_is_zero():
    ofi_value, _ = ds._update_obi_history("T", 0.5)
    assert ofi_value == 0.0


def test_ofi_static_book_stays_zero():
    vals = [ds._update_obi_history("T", 0.5)[0] for _ in range(5)]
    assert vals == [0.0] * 5


def test_ofi_is_change_vs_previous_obi():
    ds._update_obi_history("T", 0.5)
    ofi_value, _ = ds._update_obi_history("T", 0.2)
    assert ofi_value == pytest.approx(-0.3)
