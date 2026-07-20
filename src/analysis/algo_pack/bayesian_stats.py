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
        """Regularized incomplete beta function via continued fraction.

        Uses the Lentz continued fraction method for accurate computation
        even with small alpha/beta (< 5). Falls back to normal approximation
        for very large parameters where the CF converges slowly.
        """
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0

        a, b = self.alpha, self.beta

        # For large alpha, beta — normal approximation is accurate
        if a > 100 and b > 100:
            mu = a / (a + b)
            sigma = math.sqrt((a * b) / ((a + b) ** 2 * (a + b + 1)))
            if sigma < 1e-10:
                return 1.0 if x >= mu else 0.0
            z = (x - mu) / (sigma * math.sqrt(2))
            return 0.5 * (1 + math.erf(z))

        # Lentz continued fraction for I_x(a, b)
        # I_x(a,b) = x^a * (1-x)^b / (a * B(a,b)) * CF
        # where B(a,b) = Gamma(a)*Gamma(b)/Gamma(a+b)
        # We compute log(B(a,b)) using lgamma to avoid overflow
        try:
            log_beta = (math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b))
            log_prefix = a * math.log(x) + b * math.log(1 - x) - log_beta - math.log(a)

            # Continued fraction (Lentz's method)
            # Standard form: I_x(a,b) = exp(log_prefix) * CF
            # CF = 1 + d1/(1 + d2/(1 + ...))
            # where d_n are computed from the recurrence
            cf = self._beta_cf(x, a, b)
            result = math.exp(log_prefix) * cf

            return max(0.0, min(1.0, result))
        except (ValueError, OverflowError, ZeroDivisionError):
            # Fallback to normal approximation
            mu = a / (a + b)
            sigma = math.sqrt((a * b) / ((a + b) ** 2 * (a + b + 1)))
            if sigma < 1e-10:
                return 1.0 if x >= mu else 0.0
            z = (x - mu) / (sigma * math.sqrt(2))
            return 0.5 * (1 + math.erf(z))

    @staticmethod
    def _beta_cf(x: float, a: float, b: float, max_iter: int = 100) -> float:
        """Continued fraction for regularized incomplete beta function.

        Uses the modified Lentz method from Numerical Recipes.
        """
        qab = a + b
        qap = a + 1.0
        qam = a - 1.0

        # First step
        c = 1.0
        d = 1.0 - qab * x / qap
        if abs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d
        h = d

        for m in range(1, max_iter + 1):
            m2 = 2 * m

            # Even step
            aa = m * (b - m) * x / ((qam + m2) * (a + m2))
            d = 1.0 + aa * d
            if abs(d) < 1e-30:
                d = 1e-30
            c = 1.0 + aa / c
            if abs(c) < 1e-30:
                c = 1e-30
            d = 1.0 / d
            h *= d * c

            # Odd step
            aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
            d = 1.0 + aa * d
            if abs(d) < 1e-30:
                d = 1e-30
            c = 1.0 + aa / c
            if abs(c) < 1e-30:
                c = 1e-30
            d = 1.0 / d
            delta = d * c
            h *= delta

            if abs(delta - 1.0) < 1e-8:
                break

        return h

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


def confidence_weighted_kelly(
    win_dist: BetaDistribution,
    win_loss_ratio: float,
    vol_regime: str = "normal",
    hmm_state: str = "BULL",
    entropy_regime: str = "random",
    fraction: float = 0.5,
) -> float:
    """
    Kelly criterion with multi-source confidence weighting.

    Combines Bayesian win rate with regime-based adjustments:
    - GARCH volatility regime: reduce in high/extreme vol
    - HMM market state: reduce in CRISIS/BEAR
    - Information entropy: reduce in random (unpredictable) markets

    Source: SSRN (2025) "Uncertainty of ML Predictions in Asset Pricing"
            arXiv (2024) "Confidence-Calibrated Kelly Criterion"

    Args:
        win_dist: Beta distribution tracking win rate.
        win_loss_ratio: Average win / average loss.
        vol_regime: GARCH volatility regime ("low", "normal", "high", "extreme").
        hmm_state: HMM market state ("CRISIS", "BEAR", "RECOVERY", "BULL").
        entropy_regime: Information entropy regime ("trending", "random", "mean_reverting").
        fraction: Base Kelly fraction (0.5 = Half Kelly).

    Returns:
        Adjusted position size as fraction of bankroll [0, 1].
    """
    # Base Kelly from Bayesian estimate
    base_kelly = bayesian_kelly(win_dist, win_loss_ratio, fraction)

    # 1. Volatility regime adjustment
    vol_mult = {
        "low": 1.2,
        "normal": 1.0,
        "high": 0.6,
        "extreme": 0.3,
    }.get(vol_regime, 1.0)

    # 2. HMM regime adjustment
    regime_mult = {
        "CRISIS": 0.0,   # NO BUYS in crisis
        "BEAR": 0.5,
        "RECOVERY": 1.0,
        "BULL": 1.2,
    }.get(hmm_state, 1.0)

    # 3. Entropy regime adjustment
    entropy_mult = {
        "trending": 1.1,      # predictable → slightly more confident
        "random": 0.7,        # unpredictable → reduce
        "mean_reverting": 1.0, # normal
    }.get(entropy_regime, 1.0)

    # Combined adjustment
    combined_mult = vol_mult * regime_mult * entropy_mult

    return max(0.0, min(1.0, base_kelly * combined_mult))


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
