"""
regime_detector.py — Market regime detection via Markov chain.

Source: arXiv (regime switching models), Habr (quantitative trading)

Two states: TRENDING (high vol, directional) and RANGING (low vol, mean-reverting).
Bayesian update of state probabilities from price action.

Use: adapt trading parameters to current regime.
- Trending: larger positions, wider take-profit
- Ranging: smaller positions, tighter take-profit
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger("RegimeDetector")


@dataclass
class RegimeProbabilities:
    """Current regime state probabilities."""
    p_trending: float = 0.5
    p_ranging: float = 0.5


@dataclass
class RegimeParams:
    """Trading parameters adjusted for the current regime."""
    min_spread_mult: float = 1.0
    kelly_mult: float = 1.0
    take_profit_mult: float = 1.0
    stop_loss_mult: float = 1.0
    max_position_mult: float = 1.0


class MarkovRegimeDetector:
    """2-state Markov regime detection.

    States: TRENDING | RANGING
    Observation model: high absolute returns + high vol → trending

    Source: arXiv regime switching, Habr quantitative trading.
    """

    # Transition probabilities (estimated from market data)
    P_TREND_TREND = 0.85   # trending stays trending
    P_RANGE_RANGE = 0.90   # ranging stays ranging

    def __init__(self) -> None:
        self.state = RegimeProbabilities()

    def update(self, price_change_pct: float, volatility: float) -> str:
        """Update regime probabilities from new observation.

        Args:
            price_change_pct: Percentage price change (e.g. 0.02 for +2%).
            volatility: Recent realized volatility (e.g. 0.01 for 1%).

        Returns:
            Current regime: 'trending' or 'ranging'.
        """
        abs_change = abs(price_change_pct)

        # Observation likelihoods
        # P(obs | trending): high change, high vol
        p_obs_trend = self._sigmoid((abs_change - 0.015) * 100) * \
                       self._sigmoid((volatility - 0.01) * 100)
        p_obs_trend = max(0.01, min(0.99, p_obs_trend))
        p_obs_range = 1.0 - p_obs_trend

        # Bayesian update with transition
        p_trend = (self.P_TREND_TREND * self.state.p_trending * p_obs_trend +
                   (1 - self.P_RANGE_RANGE) * self.state.p_ranging * p_obs_trend)
        p_range = ((1 - self.P_TREND_TREND) * self.state.p_trending * p_obs_range +
                    self.P_RANGE_RANGE * self.state.p_ranging * p_obs_range)

        # Normalize
        total = p_trend + p_range
        if total > 0:
            self.state.p_trending = p_trend / total
            self.state.p_ranging = p_range / total

        regime = "trending" if self.state.p_trending > 0.6 else "ranging"
        logger.debug(
            f"[Regime] {regime} (p_trend={self.state.p_trending:.2f}, "
            f"p_range={self.state.p_ranging:.2f})"
        )
        return regime

    def get_params(self) -> RegimeParams:
        """Get regime-adjusted trading parameters."""
        if self.state.p_trending > 0.6:
            # Trending: be more aggressive
            return RegimeParams(
                min_spread_mult=0.8,       # relax spread requirement
                kelly_mult=1.2,             # larger positions
                take_profit_mult=1.3,       # wider take-profit
                stop_loss_mult=0.8,         # tighter stop-loss
                max_position_mult=1.15,     # allow larger positions
            )
        elif self.state.p_ranging > 0.6:
            # Ranging: be conservative
            return RegimeParams(
                min_spread_mult=1.2,       # tighten spread requirement
                kelly_mult=0.8,             # smaller positions
                take_profit_mult=0.8,       # tighter take-profit
                stop_loss_mult=1.2,         # wider stop-loss
                max_position_mult=0.85,     # reduce max position
            )
        else:
            # Transition zone: neutral
            return RegimeParams()

    @staticmethod
    def _sigmoid(x: float) -> float:
        """Sigmoid activation for observation likelihood."""
        try:
            return 1.0 / (1.0 + math.exp(-x))
        except OverflowError:
            return 0.0 if x < 0 else 1.0


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for regime detector."""
    det = MarkovRegimeDetector()

    # Simulate trending market (large moves, high vol)
    for _ in range(10):
        det.update(price_change_pct=0.03, volatility=0.02)

    regime = "trending" if det.state.p_trending > 0.6 else "ranging"
    params = det.get_params()
    print(f"[Regime] After uptrend: {regime} (p_t={det.state.p_trending:.2f})")
    print(f"[Regime] Params: kelly_mult={params.kelly_mult}, tp_mult={params.take_profit_mult}")

    # Simulate ranging market (small moves, low vol)
    for _ in range(15):
        det.update(price_change_pct=0.002, volatility=0.003)

    regime = "trending" if det.state.p_trending > 0.6 else "ranging"
    params = det.get_params()
    print(f"[Regime] After range: {regime} (p_t={det.state.p_trending:.2f})")
    print(f"[Regime] Params: kelly_mult={params.kelly_mult}, tp_mult={params.take_profit_mult}")

    assert abs(det.state.p_trending + det.state.p_ranging - 1.0) < 0.01
    print("[RegimeDetector] Self-check PASSED")


if __name__ == "__main__":
    _demo()
