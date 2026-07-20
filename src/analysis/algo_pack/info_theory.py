"""
info_theory.py — Information-Theoretic Signals for DMarket.

Source: arXiv information theory in finance
        Shannon (1948) "A Mathematical Theory of Communication"
        Cover & Thomas "Elements of Information Theory"

Information theory measures applied to price series:
  - Shannon Entropy: uncertainty in price distribution
  - Approximate Entropy: regularity/predictability of price movements
  - Mutual Information: dependence between order flow and price

Applications in DMarket:
  - Low entropy = trending (predictable) → momentum strategies work
  - High entropy = random (unpredictable) → mean-reversion or skip
  - Approximate entropy detects regime changes
  - Mutual information measures signal quality

Complexity: O(N * bin_count) for entropy, O(N²) for ApEn
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger("InfoTheory")


@dataclass
class InfoSignals:
    """Information-theoretic signal package."""
    shannon_entropy: float = 0.0     # bits per symbol [0, log2(bins)]
    normalized_entropy: float = 0.0  # entropy / max_entropy [0, 1]
    approximate_entropy: float = 0.0 # regularity measure [0, 2]
    mutual_information: float = 0.0  # MI between flow and price [0, 1]
    entropy_regime: str = "random"   # "trending", "random", "mean_reverting"
    predictability: float = 0.5      # 0 = unpredictable, 1 = predictable
    signal_quality: float = 0.5      # MI-based signal quality


class InformationTheorySignals:
    """
    Information-theoretic analysis of price series.

    Computes entropy, approximate entropy, and mutual information
    to characterize market dynamics.

    Typical usage:
        info = InformationTheorySignals()
        signals = info.compute(returns, flow_series)
        # Use signals.entropy_regime to adapt strategy
    """

    DEFAULT_BINS: int = 10  # for discretization
    APEN_M: int = 2         # embedding dimension for ApEn
    APEN_R: float = 0.2     # tolerance for ApEn (fraction of std)

    def __init__(self, n_bins: int = 10) -> None:
        self.n_bins = n_bins

    def compute(
        self,
        returns: list[float],
        flow: list[float] | None = None,
    ) -> InfoSignals:
        """
        Compute all information-theoretic signals.

        Args:
            returns: Log return series.
            flow: Order flow series (signed volume). Optional for MI.

        Returns:
            InfoSignals package.
        """
        if len(returns) < 10:
            return InfoSignals()

        # 1. Shannon Entropy
        shannon = self._shannon_entropy(returns)
        max_entropy = math.log2(self.n_bins)
        normalized = shannon / max_entropy if max_entropy > 0 else 0.0

        # 2. Approximate Entropy
        apen = self._approximate_entropy(returns)

        # 3. Mutual Information (if flow data available)
        mi = 0.0
        if flow and len(flow) == len(returns):
            mi = self._mutual_information(returns, flow)

        # 4. Regime classification
        if normalized < 0.4:
            regime = "trending"
        elif normalized > 0.75:
            regime = "random"
        else:
            regime = "mean_reverting"

        # 5. Predictability (inverse of entropy)
        predictability = 1.0 - normalized

        # 6. Signal quality (based on MI)
        signal_quality = 0.5 + mi * 0.5  # MI > 0 → better signal

        return InfoSignals(
            shannon_entropy=round(shannon, 4),
            normalized_entropy=round(normalized, 4),
            approximate_entropy=round(apen, 4),
            mutual_information=round(mi, 4),
            entropy_regime=regime,
            predictability=round(predictability, 4),
            signal_quality=round(signal_quality, 4),
        )

    def _shannon_entropy(self, data: list[float]) -> float:
        """
        Shannon entropy of discretized data.

        H(X) = -Σ p(x) * log2(p(x))

        Higher entropy = more uncertainty = harder to predict.
        """
        if not data:
            return 0.0

        # Discretize into bins
        min_val = min(data)
        max_val = max(data)
        data_range = max_val - min_val

        if data_range < 1e-10:
            return 0.0  # all values same → zero entropy

        # Bin each value
        bins = [0] * self.n_bins
        for val in data:
            bin_idx = int((val - min_val) / data_range * (self.n_bins - 1))
            bin_idx = max(0, min(self.n_bins - 1, bin_idx))
            bins[bin_idx] += 1

        # Compute entropy
        n = len(data)
        entropy = 0.0
        for count in bins:
            if count > 0:
                p = count / n
                entropy -= p * math.log2(p)

        return entropy

    def _approximate_entropy(
        self,
        data: list[float],
        m: int | None = None,
        r: float | None = None,
    ) -> float:
        """
        Approximate Entropy (ApEn) — measures regularity/predictability.

        ApEn(m, r, N) quantifies the probability that patterns
        that are close for m points remain close for m+1 points.

        Low ApEn = regular, predictable (trending)
        High ApEn = irregular, unpredictable (random)

        Reference: Pincus (1991) "Approximate entropy as a measure of
        system complexity"
        """
        if m is None:
            m = self.APEN_M
        if r is None:
            r = self.APEN_R

        n = len(data)
        if n < m + 3:
            return 0.0

        # Tolerance: r × std (sample std with Bessel correction)
        mean_val = sum(data) / n
        std = math.sqrt(sum((x - mean_val) ** 2 for x in data) / (n - 1))
        r_tolerance = r * std if std > 0 else 1e-10

        def _count_matches(template_len: int) -> int:
            """Count template matches of given length."""
            count = 0
            for i in range(n - template_len + 1):
                template = data[i:i + template_len]
                for j in range(n - template_len + 1):
                    if i == j:
                        continue
                    candidate = data[j:j + template_len]
                    # Check if max distance < r
                    max_dist = max(abs(template[k] - candidate[k]) for k in range(template_len))
                    if max_dist <= r_tolerance:
                        count += 1
            return count

        # Count matches for m and m+1
        c_m = _count_matches(m)
        c_m1 = _count_matches(m + 1)

        if c_m == 0 or c_m1 == 0:
            # FIX W3: When c_m > 0 but c_m1 == 0, patterns never persist → maximum irregularity
            if c_m > 0 and c_m1 == 0:
                n_pairs = (n - m) * (n - m - 1) if n > m + 1 else 1
                return math.log(max(n_pairs, 1)) - math.log(max(c_m, 1))
            # FIX W4: When c_m == 0 but c_m1 > 0, extremely irregular signal
            if c_m == 0 and c_m1 > 0:
                norm_m1 = (n - m - 1) * (n - m - 2) if n > m + 2 else 1
                return math.log(max(norm_m1, 1)) - math.log(max(c_m1, 1))
            return 0.0

        # ApEn = ln(c_m / c_m1)
        # FIX W2: Correct normalization for template length m
        norm_m = (n - m) * (n - m - 1) if n > m + 1 else 1
        norm_m1 = (n - m - 1) * (n - m - 2) if n > m + 2 else 1
        phi_m = math.log(c_m / norm_m) if c_m > 0 else 0.0
        phi_m1 = math.log(c_m1 / norm_m1) if c_m1 > 0 else 0.0

        return phi_m - phi_m1

    def _mutual_information(
        self,
        x: list[float],
        y: list[float],
    ) -> float:
        """
        Mutual Information between two series.

        I(X;Y) = Σ p(x,y) * log2(p(x,y) / (p(x) * p(y)))

        Measures statistical dependence between order flow and price returns.
        Higher MI = flow is informative about price direction.
        """
        n = min(len(x), len(y))
        if n < 20:
            return 0.0

        # Discretize both series
        x_bins = self._discretize(x)
        y_bins = self._discretize(y)

        # Joint distribution
        joint = [[0] * self.n_bins for _ in range(self.n_bins)]
        for i in range(n):
            joint[x_bins[i]][y_bins[i]] += 1

        # Marginals
        x_marginal = [0] * self.n_bins
        y_marginal = [0] * self.n_bins
        for i in range(n):
            x_marginal[x_bins[i]] += 1
            y_marginal[y_bins[i]] += 1

        # MI computation
        mi = 0.0
        for i in range(self.n_bins):
            for j in range(self.n_bins):
                if joint[i][j] > 0 and x_marginal[i] > 0 and y_marginal[j] > 0:
                    p_xy = joint[i][j] / n
                    p_x = x_marginal[i] / n
                    p_y = y_marginal[j] / n
                    mi += p_xy * math.log2(p_xy / (p_x * p_y))

        # Normalize by max MI (entropy of the more variable series)
        h_x = self._shannon_entropy(x)
        max_mi = min(h_x, math.log2(self.n_bins))
        if max_mi > 0:
            mi = mi / max_mi

        return max(0.0, min(1.0, mi))

    def _discretize(self, data: list[float]) -> list[int]:
        """Discretize continuous data into bins."""
        min_val = min(data)
        max_val = max(data)
        data_range = max_val - min_val

        if data_range < 1e-10:
            return [0] * len(data)

        return [
            max(0, min(self.n_bins - 1, int((v - min_val) / data_range * (self.n_bins - 1))))
            for v in data
        ]

    def get_state(self) -> dict:
        """Get current state for diagnostics."""
        return {
            "n_bins": self.n_bins,
            "apen_m": self.APEN_M,
            "apen_r": self.APEN_R,
        }


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for information theory signals."""
    import random
    random.seed(42)

    # 1. Trending series (low entropy) — use returns with clear signal
    # Strong trend: returns are consistently positive with small noise
    trending = [0.02 + random.gauss(0, 0.002) for _ in range(100)]
    # 2. Random series (high entropy) — pure noise
    random_walk = [random.gauss(0, 0.02) for _ in range(100)]
    # 3. Correlated flow (same length as random_walk)
    flow = [r + random.gauss(0, 0.005) for r in random_walk]

    info = InformationTheorySignals()

    # Test trending
    sig_trend = info.compute(trending)
    print(f"[InfoTheory] Trending: entropy={sig_trend.normalized_entropy:.3f} "
          f"regime={sig_trend.entropy_regime} predict={sig_trend.predictability:.3f}")

    # Test random
    sig_random = info.compute(random_walk)
    print(f"[InfoTheory] Random:  entropy={sig_random.normalized_entropy:.3f} "
          f"regime={sig_random.entropy_regime} predict={sig_random.predictability:.3f}")

    # Test with flow
    sig_flow = info.compute(random_walk, flow)
    print(f"[InfoTheory] MI with flow: {sig_flow.mutual_information:.3f} "
          f"signal_quality={sig_flow.signal_quality:.3f}")

    # Sanity checks
    assert sig_trend.normalized_entropy < sig_random.normalized_entropy, \
        "Trending should have lower entropy than random"
    assert sig_flow.mutual_information > 0, "MI should be positive for correlated data"
    assert sig_trend.entropy_regime in ("trending", "random", "mean_reverting")
    print("[InfoTheory] Self-check PASSED")


if __name__ == "__main__":
    _demo()
