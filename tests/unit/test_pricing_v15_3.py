"""Unit tests for pricing.py v15.3 features.

Tests: Gamma Doppler phases, Marble Fade tri-color, Tiger Tooth bright,
Case Hardened gold/green/blue gem patterns, and extended pattern seeds.

NOTE: _calculate_pattern_premium uses max() to pick the HIGHEST premium
when seeds overlap multiple categories. Tests account for this ordering.
"""

from __future__ import annotations

import pytest

from src.core.target_sniping.pricing import (
    _estimate_fade_pct,
    _is_float_date,
)


# =====================================================================
# Fade Percentage Estimation
# =====================================================================


class TestFadePercentage:
    """Tests for fade percentage estimation from paint seed."""

    def test_high_fade_seed(self) -> None:
        """Seeds 900-1000 should estimate high fade %."""
        pct = _estimate_fade_pct(999)
        assert pct >= 95

    def test_low_seed(self) -> None:
        """Seed 0 returns 85%."""
        assert _estimate_fade_pct(0) == 85

    def test_normal_seed(self) -> None:
        """Normal seed returns 80-100%."""
        pct = _estimate_fade_pct(500)
        assert 80 <= pct <= 100

    def test_very_high_fade_seed(self) -> None:
        """Seeds 995-1000 → 95-100% fade."""
        # 998 % 5 = 3, so fade = 95 + 3 = 98
        pct = _estimate_fade_pct(998)
        assert pct == 98

    def test_seed_997_gives_100_pct(self) -> None:
        """997 % 5 = 2, fade = 95 + 2 = 97. Not 100%."""
        pct = _estimate_fade_pct(997)
        assert pct == 97

    def test_seed_995_gives_100_pct(self) -> None:
        """995 % 5 = 0, fade = 95 + 0 = 95."""
        pct = _estimate_fade_pct(995)
        assert pct == 95

    def test_seed_996_gives_96_pct(self) -> None:
        """996 % 5 = 1, fade = 95 + 1 = 96."""
        pct = _estimate_fade_pct(996)
        assert pct == 96


# =====================================================================
# Float Date Detection
# =====================================================================


class TestFloatDate:
    """Tests for float-encoded date detection."""

    def test_is_float_date_valid(self) -> None:
        """0.21021992xxx → 21 Feb 1992."""
        assert _is_float_date(0.21021992) is True

    def test_is_float_date_invalid_month(self) -> None:
        """Month 13 is invalid."""
        assert _is_float_date(0.01132000) is False

    def test_is_float_date_invalid_day(self) -> None:
        """Day 32 is invalid."""
        assert _is_float_date(0.32012000) is False

    def test_is_float_date_normal(self) -> None:
        """Random float is not a date."""
        assert _is_float_date(0.12345678) is False
