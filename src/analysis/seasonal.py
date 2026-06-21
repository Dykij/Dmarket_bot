"""
seasonal.py — Seasonal / weekly / hourly timing multipliers.

Based on analysis of Steam CS2 market cycles (TA site, 3-year data).
All multipliers are ToS-safe: no scraping, no manipulation — pure timing.

Usage:
    from src.analysis.seasonal import get_timing_multiplier
    mult = get_timing_multiplier()  # returns float 0.85..1.15
"""

from __future__ import annotations

from datetime import datetime, timezone


_SEASONAL_MAP = {
    # Spring growth (Feb-Apr): aggressive buying
    (2, 0): 1.10,
    (3, 0): 1.10,
    (4, 0): 1.08,
    # Summer stagnation (Jun-Jul): cautious
    (6, 0): 0.90,
    (7, 0): 0.90,
    # September rally
    (9, 0): 1.08,
    # Year-end stagnation (Nov-Dec)
    (11, 0): 0.92,
    (12, 0): 0.92,
}


def get_seasonal_multiplier(now: datetime | None = None) -> float:
    """Adjust aggressiveness based on month.

    Returns >1.0 during growth phases (wider spread threshold),
    <1.0 during stagnation (tighter threshold).
    """
    dt = now or datetime.now(timezone.utc)
    return _SEASONAL_MAP.get((dt.month, 0), 1.0)


def get_weekly_multiplier(now: datetime | None = None) -> float:
    """Wednesday = weekly drop reset → price dip → buy more aggressively."""
    dt = now or datetime.now(timezone.utc)
    if dt.weekday() == 2:  # Wednesday
        return 1.05
    return 1.0


def get_hourly_multiplier(now: datetime | None = None) -> float:
    """Time-of-day cycle: daytime = selling pressure, nighttime = buying pressure.

    Based on TA analysis: daily 10-13% swing on case-like items.
    Day (10-18 UTC): sellers active → prices lower → buy
    Night (0-6 UTC): buyers active → prices higher → sell/hold
    """
    dt = now or datetime.now(timezone.utc)
    hour = dt.hour
    if 10 <= hour <= 18:
        return 1.03  # Aggressive buy window
    if 0 <= hour <= 6:
        return 0.97  # Cautious — prices rising
    return 1.0


def get_timing_multiplier(now: datetime | None = None) -> float:
    """Composite timing multiplier.

    Multiplied into INTRA_MIN_SPREAD_PCT to dynamically adjust
    the spread threshold based on seasonal/weekly/hourly cycles.
    """
    dt = now or datetime.now(timezone.utc)
    return get_seasonal_multiplier(dt) * get_weekly_multiplier(dt) * get_hourly_multiplier(dt)
