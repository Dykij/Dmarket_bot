"""Тесты src/utils/units.py: функции равны выражениям, которые уже стоят в коде бота."""

import pytest

from src.utils.units import cents_to_usd, usd_to_cents

CENTS = [0, 1, 99, 100, 101, 2999, 12345, 10**9, "0", "1234", 2999.0]
USD = [0.0, 0.01, 0.29, 0.57, 1.15, 4.35, 10.01, 50.6, 0.125, 123.45, 999.99]


@pytest.mark.parametrize("value", CENTS)
def test_cents_to_usd_matches_inline_expression(value):
    got = cents_to_usd(value)
    assert got == float(value) / 100.0
    assert type(got) is float


@pytest.mark.parametrize("value", USD)
def test_usd_to_cents_matches_inline_expression(value):
    got = usd_to_cents(value)
    assert got == int(round(value * 100))
    assert type(got) is int


@pytest.mark.parametrize(
    ("usd", "cents"),
    [(0.29, 29), (0.57, 57), (1.15, 115), (4.35, 435), (50.6, 5060), (0.125, 12)],
)
def test_usd_to_cents_rounds_not_truncates(usd, cents):
    assert usd_to_cents(usd) == cents


@pytest.mark.parametrize(("cents", "usd"), [(1, 0.01), (2999, 29.99), ("1234", 12.34), (0, 0.0)])
def test_cents_to_usd_known_values(cents, usd):
    assert cents_to_usd(cents) == usd


def test_round_trip_keeps_cents():
    for c in range(0, 200001, 7):
        assert usd_to_cents(cents_to_usd(c)) == c
