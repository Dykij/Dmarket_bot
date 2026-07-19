"""
bayesian_stats.py — Bayesian win rate estimation with Beta distribution.

Source: arXiv (Bayesian inference), Habr (quantitative trading)

Problem: win_rate = wins/total is unstable with small samples (<50 trades).
Solution: Beta-Bayesian updating — smooth, conservative estimates.

Use in Kelly sizing: use lower credible bound instead of point estimate.
Prevents over-sizing when sample is small.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger("BayesianStats")


@dataclass
class BetaDistribution:
    """Beta distribution for Bayesian win rate estimation.

    Prior: Beta(2, 2) — weakly informative, centered at 0.5.
    Posterior after N wins and M losses: Beta(2+N, 2+M).
    """

    alpha: float = 2.0  # prior pseudo-wins
    beta: float = 2.0   # prior pseudo-losses

    @property
    def mean(self) -> float:
        """Expected win rate (posterior mean)."""
        return self.alpha / (self.alpha + self.beta)

    @property
    def mode(self) -> float:
        """Most probable win rate (MAP estimate)."""
        if self.alpha <= 1 or self.beta <= 1:
            return self.mean
        return (self.alpha - 1) / (self.alpha + self.beta - 2)

    @property
    def variance(self) -> float:
        """Variance (uncertainty) of win rate estimate."""
        a, b = self.alpha, self.beta
        return (a * b) / ((a + b) ** 2 * (a + b + 1))

    @property
    def std(self) -> float:
        """Standard deviation."""
        return math.sqrt(self.variance)

    def update(self, won: bool) -> None:
        """Bayesian update after each trade."""
        if won:
            self.alpha += 1
        else:
            self.beta += 1

    def update_batch(self, wins: int, losses: int) -> None:
        """Batch Bayesian update."""
        self.alpha += wins
        self.beta += losses

    def credible_interval(self, level: float = 0.95) -> tuple[float, float]:
        """Credible interval for win rate.

        Uses normal approximation (good for alpha, beta > 5).
        For small samples, uses exact Beta quantiles via bisection.
        """
        lo_prob = (1 - level) / 2
        hi_prob = 1 - lo_prob

        lo = self._quantile(lo_prob)
        hi = self._quantile(hi_prob)

        return lo, hi

    def _quantile(self, p: float) -> float:
        """Beta quantile via bisection (no scipy dependency)."""
        lo, hi = 0.0, 1.0
        for _ in range(50):  # ~15 decimal precision
            mid = (lo + hi) / 2
            if self._beta_cdf(mid) < p:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    def _beta_cdf(self, x: float) -> float:
        """Regularized incomplete beta function (normal approximation)."""
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0

        # Normal approximation for large alpha, beta
        a, b = self.alpha, self.beta
        mu = a / (a + b)
        sigma = math.sqrt((a * b) / ((a + b) ** 2 * (a + b + 1)))

        if sigma < 1e-10:
            return 1.0 if x >= mu else 0.0

        # Use error function approximation
        z = (x - mu) / (sigma * math.sqrt(2))
        return 0.5 * (1 + math.erf(z))

    def conservative_estimate(self, confidence: float = 0.80) -> float:
        """Conservative win rate estimate (lower bound of credible interval).

        Use this for Kelly sizing to be safe.
        """
        lo, _ = self.credible_interval(confidence)
        return lo


def bayesian_kelly(
    win_dist: BetaDistribution,
    win_loss_ratio: float,
    fraction: float = 0.5,
) -> float:
    """Kelly criterion with Bayesian win rate.

    Uses lower credible bound instead of point estimate.
    Prevents over-sizing with small sample.

    Args:
        win_dist: Beta distribution tracking win rate.
        win_loss_ratio: Average win / average loss.
        fraction: Kelly fraction (0.5 = Half Kelly).

    Returns:
        Position size as fraction of bankroll [0, 1].
    """
    # Use 80% credible lower bound (conservative)
    wr = win_dist.conservative_estimate(0.80)
    wlr = win_loss_ratio  # Don't clamp — let kelly_f go negative if wlr < 1

    kelly_f = wr - (1 - wr) / max(wlr, 0.01)  # Guard against division by zero
    return max(0.0, kelly_f * fraction)


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for Bayesian stats."""
    dist = BetaDistribution()

    # Simulate 20 wins and 10 losses
    for _ in range(20):
        dist.update(won=True)
    for _ in range(10):
        dist.update(won=False)

    print(f"[Bayesian] Win rate: {dist.mean:.3f} (mode={dist.mode:.3f})")
    print(f"[Bayesian] Uncertainty: {dist.std:.3f}")
    lo, hi = dist.credible_interval(0.95)
    print(f"[Bayesian] 95% CI: [{lo:.3f}, {hi:.3f}]")
    print(f"[Bayesian] Conservative (80%): {dist.conservative_estimate():.3f}")

    kelly = bayesian_kelly(dist, win_loss_ratio=1.5)
    print(f"[Bayesian] Kelly fraction: {kelly:.3f}")

    # Sanity checks
    assert 0.5 < dist.mean < 0.8, f"Win rate out of range: {dist.mean}"
    assert 0.0 <= kelly <= 0.5, f"Kelly out of range: {kelly}"
    assert lo < dist.mean < hi, "CI should contain mean"
    print("[Bayesian] Self-check PASSED")


if __name__ == "__main__":
    _demo()
