"""
ou_process.py — Ornstein-Uhlenbeck Mean-Reversion Model for DMarket.

Source: Ornstein & Uhlenbeck (1930), Doob (1942)
        Quantitative Finance: mean-reversion strategies
        arXiv: optimal trading under mean-reversion

The OU process models mean-reverting price dynamics:
    dX = θ(μ - X)dt + σdW

Where:
    θ (theta)  = speed of mean reversion (higher = faster reversion)
    μ (mu)     = long-term mean (equilibrium price)
    σ (sigma)  = volatility of the process
    X          = current price (log-transformed)

Applications in DMarket:
- Detect mean-reverting items (H < 0.5 via Hurst)
- Generate entry signals: buy when price << μ, sell when price >> μ
- Estimate half-life of reversion for optimal hold period
- Z-score based position sizing

Complexity: O(N) for calibration via OLS, O(1) per signal update
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger("OUProcess")


@dataclass
class OUParams:
    """Calibrated OU process parameters."""
    theta: float = 0.0      # speed of mean reversion
    mu: float = 0.0         # long-term mean (log price)
    sigma: float = 0.0      # volatility
    half_life: float = 0.0  # days until half the deviation reverts
    half_life_hours: float = 0.0  # in hours (for DMarket 30s cycles)
    log_price_mean: float = 0.0   # sample mean of log prices
    log_price_std: float = 0.0    # sample std of log prices
    r_squared: float = 0.0        # goodness of fit
    n_observations: int = 0       # number of data points used


@dataclass
class OUSignal:
    """Trading signal from OU model."""
    z_score: float = 0.0           # standard deviations from mean
    expected_return_pct: float = 0.0  # expected return to mean
    confidence: float = 0.0        # 0-1, based on R² and sample size
    action: str = "hold"           # "buy", "sell", "hold"
    entry_price: float = 0.0       # suggested entry (if action=buy)
    target_price: float = 0.0      # fair value (μ)
    stop_loss: float = 0.0         # invalidation level


class OUProcessEstimator:
    """
    Online Ornstein-Uhlenbeck process estimator.

    Calibrates θ, μ, σ from historical prices using OLS regression.
    Generates mean-reversion signals in real-time.

    Typical usage:
        ou = OUProcessEstimator()
        ou.calibrate(prices)           # from price history
        signal = ou.update(current_price)  # per tick
        if signal.action == "buy":
            # execute buy
    """

    # Signal thresholds — FIX W11: Read from Config when available
    ENTRY_Z_SCORE: float = -1.5    # buy when Z < -1.5 (1.5σ below mean)
    EXIT_Z_SCORE: float = 0.0      # exit when Z reaches mean
    STOP_Z_SCORE: float = -3.0     # stop loss at 3σ below mean
    MIN_OBSERVATIONS: int = 20      # minimum data points for calibration
    MIN_R_SQUARED: float = 0.10     # minimum R² for valid model

    def __init__(self) -> None:
        from src.config import Config
        # FIX W11: Override class constants with Config values
        self.ENTRY_Z_SCORE = Config.OU_ENTRY_Z_SCORE
        self.STOP_Z_SCORE = Config.OU_STOP_Z_SCORE
        self.MIN_R_SQUARED = Config.OU_MIN_R_SQUARED
        self.params: OUParams = OUParams()
        self._log_prices: list[float] = []
        self._dt: float = 1.0  # time step in days (default)

    def calibrate(
        self,
        prices: list[float],
        dt_hours: float = 0.5,
    ) -> OUParams:
        """
        Calibrate OU parameters from historical prices using OLS.

        The discrete-time OU process:
            X_{t+1} - X_t = a + b * X_t + ε_t

        Where:
            a = θ * μ * dt
            b = -θ * dt
            σ² = Var(ε) / dt

        Args:
            prices: Historical prices (oldest first).
            dt_hours: Time step in hours between observations.

        Returns:
            Calibrated OUParams.
        """
        if len(prices) < self.MIN_OBSERVATIONS:
            logger.warning(
                f"[OU] Insufficient data: {len(prices)} < {self.MIN_OBSERVATIONS}"
            )
            return self.params

        # Log-transform prices (OU process on log-prices)
        log_prices = [math.log(p) for p in prices if p > 0]
        if len(log_prices) < self.MIN_OBSERVATIONS:
            return self.params

        self._log_prices = log_prices
        self._dt = dt_hours / 24.0  # convert to days

        # OLS regression: ΔX = a + b * X
        n = len(log_prices) - 1
        y = [log_prices[i + 1] - log_prices[i] for i in range(n)]
        x = log_prices[:-1]

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        # Covariance and variance
        cov_xy = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n)) / n
        var_x = sum((x[i] - mean_x) ** 2 for i in range(n)) / n

        if var_x < 1e-12:
            logger.warning("[OU] Zero variance in log prices — cannot calibrate")
            return self.params

        b = cov_xy / var_x  # slope
        a = mean_y - b * mean_x  # intercept

        # Recover OU parameters
        theta = -b / self._dt
        if theta <= 0:
            # Non-stationary (no mean reversion)
            self.params = OUParams(
                theta=0.0,
                mu=0.0,
                sigma=0.0,
                half_life=float('inf'),
                n_observations=len(log_prices),
            )
            logger.info("[OU] Non-stationary series (θ ≤ 0) — no mean reversion detected")
            return self.params

        mu = -a / b  # long-term mean

        # Residual variance → σ
        residuals = [y[i] - (a + b * x[i]) for i in range(n)]
        residual_var = sum(r ** 2 for r in residuals) / (n - 2)
        sigma = math.sqrt(max(0.0, residual_var / self._dt))

        # R-squared
        ss_res = sum(r ** 2 for r in residuals)
        ss_tot = sum((y[i] - mean_y) ** 2 for i in range(n))
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        # Half-life of mean reversion
        half_life_days = math.log(2) / theta
        half_life_hours = half_life_days * 24

        self.params = OUParams(
            theta=theta,
            mu=mu,
            sigma=sigma,
            half_life=half_life_days,
            half_life_hours=half_life_hours,
            log_price_mean=mean_x,
            log_price_std=math.sqrt(var_x),
            r_squared=r_squared,
            n_observations=len(log_prices),
        )

        logger.info(
            f"[OU] Calibrated: θ={theta:.4f} μ={mu:.4f} σ={sigma:.4f} "
            f"half_life={half_life_hours:.1f}h R²={r_squared:.3f} "
            f"n={len(log_prices)}"
        )

        return self.params

    def update(self, current_price: float) -> OUSignal:
        """
        Generate mean-reversion signal for current price.

        Args:
            current_price: Current market price.

        Returns:
            OUSignal with action recommendation.
        """
        p = self.params

        if p.theta <= 0 or p.n_observations < self.MIN_OBSERVATIONS:
            return OUSignal(action="hold", confidence=0.0)

        log_price = math.log(max(current_price, 1e-8))

        # Z-score: how many standard deviations from mean
        if p.log_price_std < 1e-10:
            z_score = 0.0
        else:
            z_score = (log_price - p.mu) / p.log_price_std

        # Expected return to mean (annualized)
        # E[price at T] = μ + (X - μ) * e^(-θT)
        expected_return_pct = (p.mu - log_price) * p.theta * 365.0 * 100.0

        # Confidence based on R² and sample size
        confidence = min(1.0, p.r_squared) * min(1.0, p.n_observations / 100.0)

        # Target price (fair value in price space)
        target_price = math.exp(p.mu)

        # Entry price: current price if signal is buy
        entry_price = current_price

        # Stop loss: 3σ below mean (negative Z_SCORE)
        stop_log = p.mu + self.STOP_Z_SCORE * p.log_price_std
        stop_price = math.exp(stop_log)

        # Decision logic — FIX: check stop_loss FIRST (most extreme condition)
        action = "hold"
        if z_score < self.STOP_Z_SCORE:
            action = "stop_loss"
        elif z_score < self.ENTRY_Z_SCORE and confidence > 0.2:
            action = "buy"
        elif z_score > abs(self.ENTRY_Z_SCORE) and confidence > 0.2:
            action = "sell"

        signal = OUSignal(
            z_score=round(z_score, 4),
            expected_return_pct=round(expected_return_pct, 2),
            confidence=round(confidence, 4),
            action=action,
            entry_price=round(entry_price, 4),
            target_price=round(target_price, 4),
            stop_loss=round(stop_price, 4),
        )

        logger.debug(
            f"[OU] Z={z_score:.2f} E[r]={expected_return_pct:.1f}% "
            f"conf={confidence:.2f} → {action}"
        )

        return signal

    def is_mean_reverting(self) -> bool:
        """Check if the calibrated model indicates mean reversion."""
        return (
            self.params.theta > 0
            and self.params.r_squared >= self.MIN_R_SQUARED
            and self.params.n_observations >= self.MIN_OBSERVATIONS
        )

    def get_half_life_hours(self) -> float:
        """Get half-life in hours (optimal hold period estimate)."""
        return self.params.half_life_hours

    def get_state(self) -> dict:
        """Get current state for diagnostics."""
        return {
            "theta": self.params.theta,
            "mu": self.params.mu,
            "sigma": self.params.sigma,
            "half_life_hours": self.params.half_life_hours,
            "r_squared": self.params.r_squared,
            "n_obs": self.params.n_observations,
            "is_mean_reverting": self.is_mean_reverting(),
        }


# ══════════════════════════════════════════════════════════════════════
# Quick calibrate + signal (utility)
# ══════════════════════════════════════════════════════════════════════

def ou_signal_from_prices(
    prices: list[float],
    current_price: float,
    dt_hours: float = 0.5,
) -> OUSignal:
    """One-shot: calibrate + signal from price history."""
    ou = OUProcessEstimator()
    ou.calibrate(prices, dt_hours=dt_hours)
    return ou.update(current_price)


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for OU process."""
    import random
    random.seed(42)

    # Simulate mean-reverting prices around $10
    mu_true = math.log(10.0)
    theta_true = 0.5
    sigma_true = 0.02
    prices = [10.0]
    for _ in range(99):
        log_p = math.log(prices[-1])
        dlog = theta_true * (mu_true - log_p) * 0.02 + sigma_true * random.gauss(0, 1)
        prices.append(math.exp(log_p + dlog))

    ou = OUProcessEstimator()
    params = ou.calibrate(prices, dt_hours=0.5)

    print(f"[OU] θ={params.theta:.4f} (true=0.5)")
    print(f"[OU] μ={params.mu:.4f} (true={mu_true:.4f})")
    print(f"[OU] σ={params.sigma:.4f} (true={sigma_true:.4f})")
    print(f"[OU] Half-life: {params.half_life_hours:.1f}h")
    print(f"[OU] R²: {params.r_squared:.3f}")
    print(f"[OU] Mean-reverting: {ou.is_mean_reverting()}")

    # Test signal at a low price (should be buy)
    low_signal = ou.update(8.0)
    print(f"[OU] Low price signal: Z={low_signal.z_score:.2f} → {low_signal.action}")

    # Test signal at a high price (should be sell)
    high_signal = ou.update(12.0)
    print(f"[OU] High price signal: Z={high_signal.z_score:.2f} → {high_signal.action}")

    # Sanity checks
    assert params.theta > 0, "Should detect mean reversion"
    assert params.mu > 0, "Mu should be positive"
    assert low_signal.z_score < 0, "Low price should have negative Z"
    assert high_signal.z_score > 0, "High price should have positive Z"
    print("[OU] Self-check PASSED")


if __name__ == "__main__":
    _demo()
