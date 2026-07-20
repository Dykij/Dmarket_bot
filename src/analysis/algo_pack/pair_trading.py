"""
pair_trading.py — Pair Trading / Cointegration for DMarket.

Source: Gatev, Goetzmann, Rouwenhorst (2006) "Pairs Trading"
        Engle & Granger (1987) cointegration test
        Alexander (2001) "Pricing and Hedging with Pairs Trading"

Pair trading exploits temporary price divergences between
correlated items. When two items that normally move together
diverge, we bet on convergence.

In DMarket context:
  - AK-47 | Redline FT and AK-47 | Redline MW (same skin, different wear)
  - Karambit | Doppler FN Phase 2 and Phase 4 (same knife, different phase)
  - Any two items with high price correlation

Algorithm:
  1. Compute hedge ratio β = Cov(P1, P2) / Var(P2)
  2. Compute spread = P1 - β * P2
  3. Test for stationarity (ADF-like test)
  4. Generate signals: buy when spread << 0, sell when spread >> 0

Complexity: O(N) for calibration, O(1) per signal
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger("PairTrading")


@dataclass
class PairParams:
    """Calibrated pair trading parameters."""
    hedge_ratio: float = 1.0       # β (how many units of P2 per unit of P1)
    spread_mean: float = 0.0       # mean of spread
    spread_std: float = 0.0        # std of spread
    correlation: float = 0.0       # Pearson correlation
    cointegration_score: float = 0.0  # stationarity of spread [0,1]
    half_life: float = 0.0         # mean reversion half-life
    n_observations: int = 0
    is_cointegrated: bool = False  # True if spread is stationary


@dataclass
class PairSignal:
    """Trading signal from pair analysis."""
    spread_z_score: float = 0.0    # spread in std deviations
    hedge_ratio: float = 1.0       # current hedge ratio
    action: str = "hold"           # "long_spread", "short_spread", "close", "hold"
    confidence: float = 0.0        # 0-1
    expected_pnl_pct: float = 0.0  # expected profit from convergence
    item1_signal: str = ""         # "buy", "sell", "hold"
    item2_signal: str = ""         # "buy", "sell", "hold"


class PairTradingEstimator:
    """
    Pair trading estimator with cointegration testing.

    Calibrates hedge ratio and spread statistics from historical prices.
    Generates mean-reversion signals on the spread.

    Typical usage:
        pair = PairTradingEstimator()
        pair.calibrate(prices1, prices2)
        signal = pair.update(price1, price2)
        if signal.action == "long_spread":
            # buy item1, sell item2 (or just buy item1 if no short)
    """

    MIN_OBSERVATIONS: int = 20
    ENTRY_Z_SCORE: float = -2.0    # buy spread when Z < -2
    EXIT_Z_SCORE: float = 0.0      # exit when spread reverts to mean
    STOP_Z_SCORE: float = -3.5     # stop loss
    MIN_CORRELATION: float = 0.5   # minimum correlation to consider pair
    MIN_CINTEGRATION: float = 0.3  # minimum cointegration score

    def __init__(self) -> None:
        from src.config import Config
        # FIX W11: Override class constants with Config values
        self.MIN_CORRELATION = Config.PAIR_MIN_CORRELATION
        self.MIN_CINTEGRATION = Config.PAIR_MIN_CINTEGRATION
        self.params: PairParams = PairParams()
        self._spread_history: list[float] = []

    def calibrate(
        self,
        prices1: list[float],
        prices2: list[float],
    ) -> PairParams:
        """
        Calibrate pair trading parameters.

        Args:
            prices1: Price series for item 1 (e.g., AK-47 Redline FT).
            prices2: Price series for item 2 (e.g., AK-47 Redline MW).

        Returns:
            Calibrated PairParams.
        """
        n = min(len(prices1), len(prices2))
        if n < self.MIN_OBSERVATIONS:
            logger.warning(
                f"[PairTrading] Insufficient data: {n} < {self.MIN_OBSERVATIONS}"
            )
            return self.params

        # Truncate to common length
        p1 = prices1[:n]
        p2 = prices2[:n]

        # 1. Pearson correlation
        correlation = self._pearson_correlation(p1, p2)

        if abs(correlation) < self.MIN_CORRELATION:
            logger.info(
                f"[PairTrading] Low correlation: {correlation:.3f} < {self.MIN_CORRELATION}"
            )
            self.params = PairParams(
                correlation=correlation,
                n_observations=n,
                is_cointegrated=False,
            )
            return self.params

        # 2. Hedge ratio (OLS: P1 = β * P2 + α)
        hedge_ratio, intercept = self._ols_hedge_ratio(p1, p2)

        # 3. Spread = P1 - β * P2
        spread = [p1[i] - hedge_ratio * p2[i] for i in range(n)]

        # 4. Spread statistics
        spread_mean = sum(spread) / n
        spread_var = sum((s - spread_mean) ** 2 for s in spread) / (n - 1)
        spread_std = math.sqrt(max(spread_var, 1e-10))

        # 5. Cointegration test (simplified ADF-like)
        cointegration_score = self._cointegration_test(spread)

        # 6. Half-life of mean reversion
        half_life = self._compute_half_life(spread)

        self.params = PairParams(
            hedge_ratio=hedge_ratio,
            spread_mean=spread_mean,
            spread_std=spread_std,
            correlation=correlation,
            cointegration_score=cointegration_score,
            half_life=half_life,
            n_observations=n,
            is_cointegrated=cointegration_score >= self.MIN_CINTEGRATION,
        )

        self._spread_history = spread

        logger.info(
            f"[PairTrading] β={hedge_ratio:.4f} corr={correlation:.3f} "
            f"spread_σ={spread_std:.4f} coint={cointegration_score:.3f} "
            f"half_life={half_life:.1f} integrated={self.params.is_cointegrated}"
        )

        return self.params

    def update(
        self,
        price1: float,
        price2: float,
    ) -> PairSignal:
        """
        Generate pair trading signal for current prices.

        Args:
            price1: Current price of item 1.
            price2: Current price of item 2.

        Returns:
            PairSignal with action recommendation.
        """
        p = self.params

        if p.n_observations < self.MIN_OBSERVATIONS or p.spread_std < 1e-10:
            return PairSignal(action="hold", confidence=0.0)

        # Current spread
        current_spread = price1 - p.hedge_ratio * price2

        # Z-score of spread
        z_score = (current_spread - p.spread_mean) / p.spread_std

        # Confidence based on correlation and cointegration
        confidence = (
            abs(p.correlation) * 0.5
            + p.cointegration_score * 0.5
        )

        # Expected PnL from convergence to mean
        expected_pnl = (p.spread_mean - current_spread) / max(abs(current_spread), 1e-8)

        # Decision logic
        # FIX C6: DMarket doesn't support short selling — only "long_spread" is valid
        action = "hold"
        item1_signal = "hold"
        item2_signal = "hold"

        # FIX: stop_loss must be checked BEFORE entry (STOP_Z < ENTRY_Z)
        if z_score < self.STOP_Z_SCORE:
            # Stop loss on long_spread — sell item1 which we own
            action = "stop_loss"
            item1_signal = "sell"
        elif z_score < self.ENTRY_Z_SCORE and p.is_cointegrated:
            # Spread is abnormally low → buy item1 (cheaper than its pair)
            action = "long_spread"
            item1_signal = "buy"
            # item2_signal stays "hold" — can't short sell on DMarket
        elif abs(z_score) < 0.5 and p.is_cointegrated:
            # Spread near mean → close position
            action = "close"
        # Removed: short_spread (requires selling item2 we don't own)

        signal = PairSignal(
            spread_z_score=round(z_score, 4),
            hedge_ratio=round(p.hedge_ratio, 4),
            action=action,
            confidence=round(confidence, 4),
            expected_pnl_pct=round(expected_pnl * 100, 2),
            item1_signal=item1_signal,
            item2_signal=item2_signal,
        )

        logger.debug(
            f"[PairTrading] Z={z_score:.2f} spread={current_spread:.4f} "
            f"→ {action} (conf={confidence:.2f})"
        )

        return signal

    def _pearson_correlation(
        self,
        x: list[float],
        y: list[float],
    ) -> float:
        """Pearson correlation coefficient."""
        n = len(x)
        if n < 2:
            return 0.0

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
        std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))

        if std_x < 1e-10 or std_y < 1e-10:
            return 0.0

        return cov / (std_x * std_y)

    def _ols_hedge_ratio(
        self,
        prices1: list[float],
        prices2: list[float],
    ) -> tuple[float, float]:
        """OLS regression: P1 = β * P2 + α."""
        n = len(prices1)
        mean1 = sum(prices1) / n
        mean2 = sum(prices2) / n

        cov = sum((prices1[i] - mean1) * (prices2[i] - mean2) for i in range(n))
        var2 = sum((p - mean2) ** 2 for p in prices2)

        if var2 < 1e-10:
            return 1.0, 0.0

        beta = cov / var2
        alpha = mean1 - beta * mean2

        return beta, alpha

    def _cointegration_test(self, spread: list[float]) -> float:
        """
        Augmented Dickey-Fuller (ADF) test for stationarity.

        Tests if the spread is stationary (mean-reverting).
        Uses the ADF test with critical values from statistical tables.

        Returns score in [0, 1]. Higher = more cointegrated.
        Score = 1.0 if ADF stat < 1% critical value (strongly stationary)
        Score = 0.0 if ADF stat > 10% critical value (unit root)
        """
        n = len(spread)
        if n < 20:
            return 0.0

        # ADF regression: ΔS_t = α + β*S_{t-1} + Σγ_i*ΔS_{t-i} + ε_t
        # We use 1 lag (simplified)
        diff = [spread[i] - spread[i - 1] for i in range(1, n)]
        lagged = spread[:-1]
        lagged_diff = diff[:-1]  # lagged differences

        # OLS: diff = alpha + beta * lagged + gamma * lagged_diff + eps
        n_obs = len(diff) - 1  # lose 1 observation for lag
        if n_obs < 10:
            return 0.0

        y = diff[1:]  # ΔS_t
        x1 = lagged[1:]  # S_{t-1}
        x2 = lagged_diff  # ΔS_{t-1}

        # Compute OLS coefficients
        mean_y = sum(y) / n_obs
        mean_x1 = sum(x1) / n_obs
        mean_x2 = sum(x2) / n_obs

        # Center variables
        yc = [yi - mean_y for yi in y]
        x1c = [xi - mean_x1 for xi in x1]
        x2c = [xi - mean_x2 for xi in x2]

        # Compute beta for S_{t-1} (the key coefficient)
        # Using simplified 2-variable OLS
        sxx1 = sum(xi ** 2 for xi in x1c)
        sxy1 = sum(yc[i] * x1c[i] for i in range(n_obs))

        if sxx1 < 1e-10:
            return 0.0

        beta1 = sxy1 / sxx1

        # Compute residuals and standard error
        residuals = [yc[i] - beta1 * x1c[i] for i in range(n_obs)]
        sse = sum(r ** 2 for r in residuals)
        se_beta = math.sqrt(sse / ((n_obs - 2) * sxx1)) if n_obs > 2 else 1.0

        # ADF test statistic
        adf_stat = beta1 / se_beta if se_beta > 0 else 0.0

        # Critical values for ADF test (from Dickey-Fuller tables)
        # These are approximate values for large samples
        critical_1pct = -3.43
        critical_5pct = -2.86
        critical_10pct = -2.57

        # Map to [0, 1] score
        if adf_stat < critical_1pct:
            # Strongly stationary at 1% level
            score = 1.0
        elif adf_stat < critical_5pct:
            # Stationary at 5% level
            score = 0.8 + 0.2 * (critical_5pct - adf_stat) / (critical_5pct - critical_1pct)
        elif adf_stat < critical_10pct:
            # Stationary at 10% level
            score = 0.5 + 0.3 * (critical_10pct - adf_stat) / (critical_10pct - critical_5pct)
        else:
            # Not stationary (unit root)
            score = max(0.0, 0.5 * (1.0 - (adf_stat - critical_10pct) / abs(critical_10pct)))

        return max(0.0, min(1.0, score))

    def _compute_half_life(self, spread: list[float]) -> float:
        """Half-life of mean reversion from AR(1) regression."""
        n = len(spread)
        if n < 10:
            return float('inf')

        # AR(1): S_t = α + ρ * S_{t-1} + ε
        x = spread[:-1]
        y = spread[1:]

        mean_x = sum(x) / len(x)
        mean_y = sum(y) / len(y)

        cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(len(x)))
        var_x = sum((xi - mean_x) ** 2 for xi in x)

        if var_x < 1e-10:
            return float('inf')

        rho = cov / var_x

        if rho >= 1.0 or rho <= 0.0:
            return float('inf')

        half_life = -math.log(2) / math.log(rho)
        return half_life

    def get_state(self) -> dict:
        """Get current state for diagnostics."""
        return {
            "hedge_ratio": self.params.hedge_ratio,
            "correlation": self.params.correlation,
            "cointegration": self.params.cointegration_score,
            "half_life": self.params.half_life,
            "is_cointegrated": self.params.is_cointegrated,
            "spread_mean": self.params.spread_mean,
            "spread_std": self.params.spread_std,
        }


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for pair trading."""
    import random
    random.seed(42)

    # Simulate two cointegrated price series
    # P1 = 1.5 * P2 + noise
    n = 100
    p2_base = 10.0
    p2 = [p2_base]
    for _ in range(n - 1):
        p2.append(p2[-1] * (1 + random.gauss(0, 0.01)))

    p1 = [1.5 * p2[i] + random.gauss(0, 0.3) for i in range(n)]

    pair = PairTradingEstimator()
    params = pair.calibrate(p1, p2)

    print(f"[PairTrading] Hedge ratio: {params.hedge_ratio:.4f} (true=1.5)")
    print(f"[PairTrading] Correlation: {params.correlation:.3f}")
    print(f"[PairTrading] Cointegration: {params.cointegration_score:.3f}")
    print(f"[PairTrading] Half-life: {params.half_life:.1f}")
    print(f"[PairTrading] Is cointegrated: {params.is_cointegrated}")

    # Test signal when spread is low
    signal = pair.update(p1[-1] * 0.9, p2[-1])
    print(f"[PairTrading] Low spread signal: Z={signal.spread_z_score:.2f} → {signal.action}")

    # Sanity checks
    assert abs(params.hedge_ratio - 1.5) < 0.3, f"Hedge ratio off: {params.hedge_ratio}"
    assert params.correlation > 0.5, f"Should be correlated: {params.correlation}"
    assert signal.action in ("long_spread", "short_spread", "close", "hold", "stop_loss")
    print("[PairTrading] Self-check PASSED")


if __name__ == "__main__":
    _demo()
