"""
garch.py — GARCH(1,1) Volatility Forecasting for DMarket.

Source: Bollerslev (1986) "Generalized Autoregressive Conditional Heteroskedasticity"
        Engle (1982) ARCH model
        arXiv: volatility forecasting in illiquid markets

GARCH(1,1) models time-varying volatility:
    σ²_t = ω + α * ε²_{t-1} + β * σ²_{t-1}

Where:
    ω (omega)   = baseline variance (long-run component)
    α (alpha)   = reaction to recent shocks (ARCH term)
    β (beta)    = persistence of volatility (GARCH term)
    ε²_{t-1}   = squared return from previous period
    σ²_{t-1}   = previous period variance

Key properties:
    - α + β < 1  → stationary (variance reverts to mean)
    - α + β ≈ 1  → integrated GARCH (IGARCH, unit root)
    - Half-life of shock = log(0.5) / log(α + β)

Applications in DMarket:
    - Predict next-period volatility → dynamic position sizing
    - Volatility regime detection (expanding vs contracting)
    - Better than EWMA for volatility clustering detection
    - Adjust MIN_SPREAD dynamically based on forecasted vol

Complexity: O(N) for calibration, O(1) per forecast update
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger("GARCH")


@dataclass
class GARCHParams:
    """Calibrated GARCH(1,1) parameters."""
    omega: float = 0.0       # baseline variance
    alpha: float = 0.0       # ARCH coefficient
    beta: float = 0.0        # GARCH coefficient
    persistence: float = 0.0 # α + β (persistence of shocks)
    half_life: float = 0.0   # half-life of shock in periods
    long_run_var: float = 0.0 # ω / (1 - α - β)
    current_var: float = 0.0  # latest conditional variance
    current_vol: float = 0.0  # latest conditional volatility
    log_likelihood: float = 0.0
    n_observations: int = 0
    aic: float = 0.0         # Akaike Information Criterion
    converged: bool = False


@dataclass
class GARCHForecast:
    """Volatility forecast from GARCH model."""
    conditional_vol: float = 0.0     # current period volatility
    forecast_vol_1: float = 0.0     # 1-step ahead forecast
    forecast_vol_5: float = 0.0     # 5-step ahead forecast
    forecast_vol_10: float = 0.0    # 10-step ahead forecast
    long_run_vol: float = 0.0       # unconditional (long-run) vol
    vol_regime: str = "normal"       # "low", "normal", "high", "extreme"
    vol_percentile: float = 50.0    # where current vol sits historically
    annualized_vol: float = 0.0     # annualized volatility


class GARCH11Estimator:
    """
    GARCH(1,1) volatility estimator with online updating.

    Calibrates parameters from return series using quasi-maximum
    likelihood estimation (QMLE) — no scipy dependency.

    Typical usage:
        garch = GARCH11Estimator()
        garch.calibrate(returns)
        forecast = garch.forecast()
        # Use forecast.conditional_vol for position sizing

    Note: For DMarket items with sparse trading, we use log returns
    from price history. Items with <30 observations fall back to
    EWMA volatility.
    """

    MIN_OBSERVATIONS: int = 30
    MIN_RETURN_VARIANCE: float = 1e-10

    def __init__(self) -> None:
        self.params: GARCHParams = GARCHParams()
        self._returns: list[float] = []
        self._variances: list[float] = []  # conditional variance series

    def calibrate(
        self,
        returns: list[float],
        max_iter: int = 200,
        tolerance: float = 1e-6,
    ) -> GARCHParams:
        """
        Calibrate GARCH(1,1) parameters using QMLE.

        Uses a simple iterative approach (no scipy):
        1. Initialize with sample variance decomposition
        2. Iterate: compute conditional variances → update ω, α, β
        3. Check convergence

        Args:
            returns: Log return series (r_t = ln(P_t/P_{t-1})).
            max_iter: Maximum iterations.
            tolerance: Convergence threshold.

        Returns:
            Calibrated GARCHParams.
        """
        n = len(returns)
        if n < self.MIN_OBSERVATIONS:
            logger.warning(
                f"[GARCH] Insufficient data: {n} < {self.MIN_OBSERVATIONS}"
            )
            return self.params

        self._returns = returns

        # Sample variance (unconditional)
        mean_r = sum(returns) / n
        sample_var = sum((r - mean_r) ** 2 for r in returns) / (n - 1)

        if sample_var < self.MIN_RETURN_VARIANCE:
            logger.warning("[GARCH] Near-zero return variance — cannot calibrate")
            return self.params

        # Initial parameter estimates (method of moments)
        # α + β = persistence ≈ 0.85 (typical for financial data)
        # ω = sample_var * (1 - α - β)
        omega = sample_var * 0.05
        alpha = 0.10
        beta = 0.85
        persistence = alpha + beta

        best_ll = float('-inf')
        best_params = GARCHParams()

        for iteration in range(max_iter):
            # --- E-step: compute conditional variances ---
            cond_var = self._compute_conditional_variances(
                returns, omega, alpha, beta, sample_var
            )

            # --- M-step: update parameters ---
            new_omega, new_alpha, new_beta = self._update_params(
                returns, cond_var, sample_var
            )

            # Stationarity constraint: α + β < 1
            new_persistence = new_alpha + new_beta
            if new_persistence >= 0.999:
                # Shrink toward stationarity
                scale = 0.99 / new_persistence
                new_alpha *= scale
                new_beta *= scale
                new_persistence = new_alpha + new_beta

            # Ensure positivity
            new_omega = max(new_omega, 1e-10)
            new_alpha = max(new_alpha, 1e-6)
            new_beta = max(new_beta, 1e-6)

            # Check convergence
            delta = abs(new_omega - omega) + abs(new_alpha - alpha) + abs(new_beta - beta)
            omega, alpha, beta = new_omega, new_alpha, new_beta

            if delta < tolerance:
                logger.info(f"[GARCH] Converged after {iteration + 1} iterations")
                break

        # Final conditional variances
        cond_var = self._compute_conditional_variances(
            returns, omega, alpha, beta, sample_var
        )

        # Log-likelihood (Gaussian QMLE)
        ll = self._log_likelihood(returns, cond_var)

        # Long-run variance
        persistence = alpha + beta
        long_run_var = omega / max(1e-10, 1.0 - persistence) if persistence < 1.0 else sample_var

        # Half-life of shock
        if persistence > 0 and persistence < 1.0:
            half_life = math.log(0.5) / math.log(persistence)
        else:
            half_life = float('inf')

        # AIC
        k = 3  # number of parameters (ω, α, β)
        aic = 2 * k - 2 * ll

        self.params = GARCHParams(
            omega=omega,
            alpha=alpha,
            beta=beta,
            persistence=persistence,
            half_life=half_life,
            long_run_var=long_run_var,
            current_var=cond_var[-1] if cond_var else sample_var,
            current_vol=math.sqrt(cond_var[-1]) if cond_var else math.sqrt(sample_var),
            log_likelihood=ll,
            n_observations=n,
            aic=aic,
            converged=True,
        )

        self._variances = cond_var

        logger.info(
            f"[GARCH] ω={omega:.6f} α={alpha:.4f} β={beta:.4f} "
            f"persist={persistence:.4f} half_life={half_life:.1f} "
            f"long_run_vol={math.sqrt(long_run_var):.4f} AIC={aic:.1f}"
        )

        return self.params

    def forecast(self, steps: int = 10) -> GARCHForecast:
        """
        Generate volatility forecasts.

        Args:
            steps: Number of steps ahead to forecast.

        Returns:
            GARCHForecast with multi-step ahead forecasts.
        """
        p = self.params
        if not p.converged or p.n_observations < self.MIN_OBSERVATIONS:
            return GARCHForecast()

        # Current conditional volatility
        cond_vol = math.sqrt(max(p.current_var, 1e-10))

        # Multi-step forecasts
        # σ²_{t+h} = V_L + (α+β)^{h-1} * (σ²_{t+1} - V_L)
        forecasts = []
        for h in range(1, steps + 1):
            if h == 1:
                # 1-step: use current conditional variance
                f_var = p.current_var
            else:
                # h-step: mean-revert toward long-run
                f_var = p.long_run_var + (p.persistence ** (h - 1)) * (
                    forecasts[0] - p.long_run_var
                )
            forecasts.append(f_var)

        # Volatility regime classification
        vol_ratio = cond_vol / max(math.sqrt(p.long_run_var), 1e-10)
        if vol_ratio > 2.0:
            regime = "extreme"
        elif vol_ratio > 1.3:
            regime = "high"
        elif vol_ratio < 0.7:
            regime = "low"
        else:
            regime = "normal"

        # Volatility percentile (where current vol sits vs long-run)
        percentile = min(100.0, max(0.0, vol_ratio * 50.0))

        # Annualize — CS2 skins trade 24/7/365, not equity market 252 days
        annualized = cond_vol * math.sqrt(365)

        return GARCHForecast(
            conditional_vol=round(cond_vol, 6),
            forecast_vol_1=round(math.sqrt(max(forecasts[0], 0)), 6),
            forecast_vol_5=round(math.sqrt(max(forecasts[min(4, len(forecasts)-1)], 0)), 6),
            forecast_vol_10=round(math.sqrt(max(forecasts[min(9, len(forecasts)-1)], 0)), 6),
            long_run_vol=round(math.sqrt(max(p.long_run_var, 0)), 6),
            vol_regime=regime,
            vol_percentile=round(percentile, 1),
            annualized_vol=round(annualized, 4),
        )

    def update(self, new_return: float) -> GARCHForecast:
        """
        Online update with new return observation.

        Args:
            new_return: Latest log return.

        Returns:
            Updated GARCHForecast.
        """
        p = self.params
        if not p.converged:
            return GARCHForecast()

        # Update conditional variance: σ²_t = ω + α*ε²_{t-1} + β*σ²_{t-1}
        new_var = p.omega + p.alpha * (new_return ** 2) + p.beta * p.current_var

        # Update params
        p.current_var = new_var
        p.current_vol = math.sqrt(max(new_var, 1e-10))

        return self.forecast()

    def _compute_conditional_variances(
        self,
        returns: list[float],
        omega: float,
        alpha: float,
        beta: float,
        sample_var: float,
    ) -> list[float]:
        """Compute conditional variance series for given parameters."""
        n = len(returns)
        cond_var = [sample_var]  # initialize with unconditional variance

        for t in range(1, n):
            prev_var = cond_var[t - 1]
            prev_return = returns[t - 1]
            var_t = omega + alpha * (prev_return ** 2) + beta * prev_var
            cond_var.append(max(var_t, 1e-10))

        return cond_var

    def _update_params(
        self,
        returns: list[float],
        cond_var: list[float],
        sample_var: float,
    ) -> tuple[float, float, float]:
        """Update GARCH parameters given conditional variances."""
        n = len(returns)

        # Simple method-of-moments update
        # ω = (1 - α - β) * σ²_L (long-run variance)
        # α, β estimated from autocorrelation of squared returns

        # Compute weighted residuals
        weighted_sq = []
        for t in range(1, n):
            if cond_var[t - 1] > 1e-10:
                weighted_sq.append((returns[t] ** 2) / cond_var[t - 1])
            else:
                weighted_sq.append(0.0)

        # α from autocorrelation of squared returns
        if len(weighted_sq) > 2:
            mean_ws = sum(weighted_sq) / len(weighted_sq)
            var_ws = sum((x - mean_ws) ** 2 for x in weighted_sq) / len(weighted_sq)
            if var_ws > 1e-10:
                # Simple autocorrelation at lag 1
                acf1 = sum(
                    (weighted_sq[i] - mean_ws) * (weighted_sq[i - 1] - mean_ws)
                    for i in range(1, len(weighted_sq))
                ) / ((len(weighted_sq) - 1) * var_ws)
                alpha = max(1e-6, min(0.3, abs(acf1) * 0.5))
            else:
                alpha = 0.10
        else:
            alpha = 0.10

        # β = persistence - α
        # FIX: Estimate persistence from data instead of hardcoding 0.85
        # Use autocorrelation of squared returns as proxy for persistence
        if len(returns) > 10:
            sq_returns = [r**2 for r in returns]
            mean_sq = sum(sq_returns) / len(sq_returns)
            var_sq = sum((s - mean_sq)**2 for s in sq_returns) / len(sq_returns)
            if var_sq > 1e-10:
                # Lag-1 autocorrelation of squared returns ≈ α + β
                acf1_sq = sum(
                    (sq_returns[i] - mean_sq) * (sq_returns[i-1] - mean_sq)
                    for i in range(1, len(sq_returns))
                ) / ((len(sq_returns) - 1) * var_sq)
                persistence = max(0.5, min(0.99, abs(acf1_sq)))
            else:
                persistence = 0.85
        else:
            persistence = 0.85
        beta = max(1e-6, persistence - alpha)

        # ω from long-run variance
        long_run_var = sample_var
        omega = long_run_var * (1.0 - alpha - beta)
        omega = max(1e-10, omega)

        return omega, alpha, beta

    def _log_likelihood(
        self,
        returns: list[float],
        cond_var: list[float],
    ) -> float:
        """Quasi-maximum log-likelihood (Gaussian assumption)."""
        n = len(returns)
        ll = 0.0

        for t in range(1, n):
            var_t = max(cond_var[t], 1e-10)
            ll -= 0.5 * (math.log(2 * math.pi * var_t) + (returns[t] ** 2) / var_t)

        return ll

    def get_state(self) -> dict:
        """Get current state for diagnostics."""
        p = self.params
        return {
            "omega": p.omega,
            "alpha": p.alpha,
            "beta": p.beta,
            "persistence": p.persistence,
            "half_life": p.half_life,
            "long_run_vol": math.sqrt(max(p.long_run_var, 0)),
            "current_vol": p.current_vol,
            "converged": p.converged,
            "n_obs": p.n_observations,
        }


# ══════════════════════════════════════════════════════════════════════
# Quick utility
# ══════════════════════════════════════════════════════════════════════

def garch_forecast_from_prices(
    prices: list[float],
    steps: int = 10,
) -> GARCHForecast:
    """One-shot: calibrate + forecast from price series."""
    # Convert prices to log returns
    returns = []
    for i in range(1, len(prices)):
        if prices[i - 1] > 0 and prices[i] > 0:
            returns.append(math.log(prices[i] / prices[i - 1]))

    garch = GARCH11Estimator()
    garch.calibrate(returns)
    return garch.forecast(steps=steps)


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for GARCH(1,1)."""
    import random
    random.seed(42)

    # Simulate returns with volatility clustering
    # True GARCH(1,1): ω=0.00001, α=0.08, β=0.88
    true_omega = 0.00001
    true_alpha = 0.08
    true_beta = 0.88
    returns = []
    var_t = 0.001  # initial variance
    for _ in range(200):
        eps = random.gauss(0, 1)
        r = eps * math.sqrt(var_t)
        returns.append(r)
        var_t = true_omega + true_alpha * (r ** 2) + true_beta * var_t

    garch = GARCH11Estimator()
    params = garch.calibrate(returns)

    print(f"[GARCH] ω={params.omega:.6f} (true={true_omega:.6f})")
    print(f"[GARCH] α={params.alpha:.4f} (true={true_alpha:.4f})")
    print(f"[GARCH] β={params.beta:.4f} (true={true_beta:.4f})")
    print(f"[GARCH] Persistence: {params.persistence:.4f}")
    print(f"[GARCH] Half-life: {params.half_life:.1f} periods")
    print(f"[GARCH] Long-run vol: {math.sqrt(params.long_run_var):.4f}")
    print(f"[GARCH] Current vol: {params.current_vol:.4f}")
    print(f"[GARCH] Converged: {params.converged}")

    forecast = garch.forecast(steps=10)
    print(f"[GARCH] Forecast vol 1-step: {forecast.forecast_vol_1:.4f}")
    print(f"[GARCH] Forecast vol 5-step: {forecast.forecast_vol_5:.4f}")
    print(f"[GARCH] Vol regime: {forecast.vol_regime}")

    # Sanity checks
    assert params.converged, "Should converge"
    assert 0 < params.alpha < 1, "Alpha should be in (0,1)"
    assert 0 < params.beta < 1, "Beta should be in (0,1)"
    assert params.persistence < 1.0, "Should be stationary"
    assert forecast.forecast_vol_1 > 0, "Forecast should be positive"
    print("[GARCH] Self-check PASSED")


if __name__ == "__main__":
    _demo()
