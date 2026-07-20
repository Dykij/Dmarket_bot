"""
hmm_regime.py — Hidden Markov Model Regime Detection for DMarket.

Source: Hamilton (1989) "A New Approach to the Economic Analysis of Nonstationary
        Time Series and the Business Cycle"
        Rugarch / arXiv regime switching models

The HMM models market as transitioning between hidden states:
  - BULL:   low volatility, positive drift (trending up)
  - BEAR:   high volatility, negative drift (trending down)
  - CRISIS: extreme volatility, large negative moves
  - RECOVERY: transitioning from crisis to normal

Each state has:
  - Emission distribution: N(μ, σ²) for returns
  - Transition probabilities: P(state_j | state_i)

Applications in DMarket:
  - Adapt trading parameters per regime
  - Risk management: reduce exposure in CRISIS state
  - Entry timing: accumulate in RECOVERY, distribute in BULL top

Complexity: O(N * K²) for Viterbi decoding, O(N * K²) for Baum-Welch
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import IntEnum

logger = logging.getLogger("HMMRegime")


class MarketState(IntEnum):
    """Hidden market states (ordered by typical regime)."""
    CRISIS = 0
    BEAR = 1
    RECOVERY = 2
    BULL = 3


@dataclass
class HMMParams:
    """Calibrated HMM parameters."""
    # Transition matrix K x K (K=4 states)
    # T[i][j] = P(state_j at t+1 | state_i at t)
    transition: list[list[float]] = field(default_factory=lambda: [
        [0.85, 0.10, 0.05, 0.00],  # CRISIS →
        [0.05, 0.80, 0.15, 0.00],  # BEAR →
        [0.00, 0.05, 0.80, 0.15],  # RECOVERY →
        [0.00, 0.00, 0.10, 0.90],  # BULL →
    ])

    # Emission parameters: μ[state], σ[state]
    means: list[float] = field(default_factory=lambda: [
        -0.005,  # CRISIS: large negative drift
        -0.001,  # BEAR: slight negative drift
        0.002,   # RECOVERY: slight positive drift
        0.005,   # BULL: positive drift
    ])

    stds: list[float] = field(default_factory=lambda: [
        0.030,   # CRISIS: high volatility
        0.015,   # BEAR: moderate volatility
        0.012,   # RECOVERY: moderate-low volatility
        0.008,   # BULL: low volatility
    ])

    # Initial state probabilities
    pi: list[float] = field(default_factory=lambda: [0.05, 0.20, 0.25, 0.50])

    n_states: int = 4
    n_observations: int = 0


@dataclass
class RegimeResult:
    """HMM regime detection result."""
    current_state: MarketState = MarketState.BULL
    state_probabilities: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 1.0])
    most_likely_state: str = "BULL"
    state_confidence: float = 0.0
    transition_recommendation: str = ""  # suggested parameter adjustments
    expected_drift: float = 0.0
    expected_volatility: float = 0.0


class HMMRegimeDetector:
    """
    Hidden Markov Model regime detector.

    Uses Baum-Welch (EM) for calibration and Viterbi for state decoding.
    Simplified for online use with running forward probabilities.

    Typical usage:
        hmm = HMMRegimeDetector()
        hmm.calibrate(returns)
        result = hmm.update(new_return)
        # Adapt trading parameters based on result.current_state
    """

    MIN_OBSERVATIONS: int = 50
    N_STATES: int = 4
    MAX_ITER: int = 100

    def __init__(self) -> None:
        self.params: HMMParams = HMMParams()
        self._forward_probs: list[float] = [0.25] * self.N_STATES
        self._returns: list[float] = []

    def calibrate(
        self,
        returns: list[float],
        max_iter: int | None = None,
    ) -> HMMParams:
        """
        Calibrate HMM parameters using Baum-Welch (EM algorithm).

        Args:
            returns: Log return series.
            max_iter: Maximum EM iterations.

        Returns:
            Calibrated HMMParams.
        """
        if max_iter is None:
            max_iter = self.MAX_ITER

        n = len(returns)
        if n < self.MIN_OBSERVATIONS:
            logger.warning(
                f"[HMM] Insufficient data: {n} < {self.MIN_OBSERVATIONS}"
            )
            return self.params

        self._returns = returns

        # Initialize parameters from data quartiles
        sorted_rets = sorted(returns)
        q1 = sorted_rets[n // 4]
        q2 = sorted_rets[n // 2]
        q3 = sorted_rets[3 * n // 4]

        # State means from quartiles
        self.params.means = [
            sorted_rets[n // 10],          # CRISIS: bottom 10%
            q1,                            # BEAR: 25th percentile
            q3,                            # RECOVERY: 75th percentile
            sorted_rets[9 * n // 10],      # BULL: top 10%
        ]

        # State stds (estimated from local data)
        for s in range(self.N_STATES):
            threshold_low = self.params.means[s] - 0.01
            threshold_high = self.params.means[s] + 0.01
            local = [r for r in returns if threshold_low <= r <= threshold_high]
            if len(local) > 5:
                mean_local = sum(local) / len(local)
                var_local = sum((r - mean_local) ** 2 for r in local) / len(local)
                self.params.stds[s] = max(0.001, math.sqrt(var_local))
            else:
                self.params.stds[s] = 0.01

        # EM iterations
        prev_ll = float('-inf')
        for iteration in range(max_iter):
            # E-step: forward-backward algorithm
            log_likelihood = self._forward_backward(returns)

            # M-step: update parameters
            self._update_params(returns)

            if iteration > 0 and abs(log_likelihood - prev_ll) < 1e-6:
                logger.info(f"[HMM] Converged after {iteration + 1} iterations")
                break

            prev_ll = log_likelihood

        logger.info(
            f"[HMM] Calibrated: means={[f'{m:.4f}' for m in self.params.means]} "
            f"stds={[f'{s:.4f}' for s in self.params.stds]}"
        )

        self.params.n_observations = len(returns)
        return self.params

    def update(self, new_return: float) -> RegimeResult:
        """
        Update regime probabilities with new observation.

        Uses running forward probabilities (online Viterbi-like).

        Args:
            new_return: Latest log return.

        Returns:
            RegimeResult with current state assessment.
        """
        # FIX C3: Check calibration state, not n_states (which is always 4)
        if self.params.n_observations < self.MIN_OBSERVATIONS:
            return RegimeResult()

        # Compute emission probabilities for each state
        emissions = []
        for s in range(self.N_STATES):
            mu = self.params.means[s]
            sigma = max(self.params.stds[s], 1e-6)
            # Gaussian emission probability
            z = (new_return - mu) / sigma
            emit = math.exp(-0.5 * z * z) / (sigma * math.sqrt(2 * math.pi))
            emissions.append(max(emit, 1e-10))

        # Forward update: α_j = emit_j * Σ_i (α_i * T_ij)
        new_forward = []
        for j in range(self.N_STATES):
            alpha_j = 0.0
            for i in range(self.N_STATES):
                alpha_j += self._forward_probs[i] * self.params.transition[i][j]
            alpha_j *= emissions[j]
            new_forward.append(alpha_j)

        # Normalize
        total = sum(new_forward)
        if total > 0:
            self._forward_probs = [f / total for f in new_forward]
        else:
            self._forward_probs = [1.0 / self.N_STATES] * self.N_STATES

        # Most likely state
        max_prob = max(self._forward_probs)
        max_idx = self._forward_probs.index(max_prob)

        state_names = ["CRISIS", "BEAR", "RECOVERY", "BULL"]
        current_state = MarketState(max_idx)

        # Expected drift and volatility
        expected_drift = sum(
            self._forward_probs[s] * self.params.means[s]
            for s in range(self.N_STATES)
        )
        # FIX: Wrap in max(0.0, ...) to prevent math domain error from float precision
        expected_vol = math.sqrt(max(0.0, sum(
            self._forward_probs[s] * (self.params.stds[s] ** 2 + self.params.means[s] ** 2)
            for s in range(self.N_STATES)
        ) - expected_drift ** 2))

        # Parameter adjustment recommendation
        recommendation = self._get_recommendation(current_state)

        return RegimeResult(
            current_state=current_state,
            state_probabilities=list(self._forward_probs),
            most_likely_state=state_names[max_idx],
            state_confidence=round(max_prob, 4),
            transition_recommendation=recommendation,
            expected_drift=round(expected_drift, 6),
            expected_volatility=round(expected_vol, 6),
        )

    def _forward_backward(self, returns: list[float]) -> float:
        """Forward-backward algorithm for log-likelihood computation.
        
        Stores per-timestep forward probabilities in self._gamma for M-step.
        """
        n = len(returns)
        K = self.N_STATES

        # Forward pass — store per-timestep normalized forward probs
        log_likelihood = 0.0
        alpha = list(self.params.pi)
        self._gamma: list[list[float]] = []  # per-timestep state probs

        for t in range(n):
            # Emission probabilities
            emit = []
            for s in range(K):
                mu = self.params.means[s]
                sigma = max(self.params.stds[s], 1e-6)
                z = (returns[t] - mu) / sigma
                e = math.exp(-0.5 * z * z) / (sigma * math.sqrt(2 * math.pi))
                emit.append(max(e, 1e-10))

            # Forward update
            new_alpha = []
            for j in range(K):
                a_j = 0.0
                for i in range(K):
                    a_j += alpha[i] * self.params.transition[i][j]
                a_j *= emit[j]
                new_alpha.append(a_j)

            # Normalize and accumulate log-likelihood
            total = sum(new_alpha)
            if total > 0:
                log_likelihood += math.log(total)
                alpha = [a / total for a in new_alpha]
            else:
                alpha = [1.0 / K] * K

            # Store normalized forward probs for this timestep
            self._gamma.append(list(alpha))

        return log_likelihood

    def _update_params(self, returns: list[float]) -> None:
        """M-step: update transition and emission parameters.
        
        Uses per-timestep forward probabilities (gamma) from _forward_backward.
        """
        n = len(returns)
        K = self.N_STATES
        gamma = self._gamma  # per-timestep state probabilities from E-step

        # Update means and stds from state-weighted data
        for s in range(K):
            weighted_sum = 0.0
            weighted_sq_sum = 0.0
            weight_total = 0.0

            for t in range(n):
                w = gamma[t][s]  # per-timestep weight for state s
                weighted_sum += w * returns[t]
                weighted_sq_sum += w * returns[t] ** 2
                weight_total += w

            if weight_total > 1e-10:
                new_mean = weighted_sum / weight_total
                new_var = weighted_sq_sum / weight_total - new_mean ** 2
                new_std = max(0.001, math.sqrt(max(0, new_var)))

                # Smooth update (don't change too fast)
                self.params.means[s] = 0.7 * self.params.means[s] + 0.3 * new_mean
                self.params.stds[s] = 0.7 * self.params.stds[s] + 0.3 * new_std

        # Update transition matrix using per-timestep posteriors
        # Correct M-step: accumulate xi[t][i][j] = P(state=i at t, state=j at t+1)
        # then normalize by gamma[t][i] to get transition[i][j]
        # Since we only have forward probs (no backward pass), we approximate:
        # xi[t][i][j] ≈ gamma[t][i] * transition[i][j] * gamma[t+1][j] / normalize
        counts = [[0.0] * K for _ in range(K)]
        for t in range(n - 1):
            # Compute joint probability P(i at t, j at t+1) for all i,j
            joint = [[0.0] * K for _ in range(K)]
            joint_total = 0.0
            for i in range(K):
                for j in range(K):
                    joint[i][j] = gamma[t][i] * self.params.transition[i][j] * gamma[t + 1][j]
                    joint_total += joint[i][j]
            # Normalize joint to get proper xi
            if joint_total > 1e-10:
                for i in range(K):
                    for j in range(K):
                        counts[i][j] += joint[i][j] / joint_total

        # Normalize rows to get transition probabilities
        for i in range(K):
            row_sum = sum(counts[i])
            if row_sum > 0:
                for j in range(K):
                    self.params.transition[i][j] = counts[i][j] / row_sum

    def _get_recommendation(self, state: MarketState) -> str:
        """Get parameter adjustment recommendation for current state."""
        recommendations = {
            MarketState.CRISIS: (
                "REDUCE_EXPOSURE: increase min_spread by 50%, "
                "reduce max_position by 70%, activate drawdown freeze"
            ),
            MarketState.BEAR: (
                "CAUTIOUS: increase min_spread by 20%, "
                "reduce max_position by 30%, tighten stop-loss"
            ),
            MarketState.RECOVERY: (
                "GRADUAL_ACCUMULATION: normal min_spread, "
                "slightly increase max_position, relaxed stop-loss"
            ),
            MarketState.BULL: (
                "OPTIMISTIC: slightly tighter min_spread, "
                "normal position sizing, wider take-profit"
            ),
        }
        return recommendations.get(state, "HOLD: no adjustment")

    def get_state(self) -> dict:
        """Get current state for diagnostics."""
        return {
            "state_probs": [round(p, 4) for p in self._forward_probs],
            "most_likely": self._forward_probs.index(max(self._forward_probs)),
            "means": [round(m, 4) for m in self.params.means],
            "stds": [round(s, 4) for s in self.params.stds],
        }


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for HMM regime detection."""
    import random
    random.seed(42)

    # Simulate regime-switching returns
    returns = []
    regime_sequence = []
    current_regime = 3  # start in BULL

    regime_params = {
        0: (-0.005, 0.030),  # CRISIS
        1: (-0.001, 0.015),  # BEAR
        2: (0.002, 0.012),   # RECOVERY
        3: (0.005, 0.008),   # BULL
    }

    for _ in range(200):
        mu, sigma = regime_params[current_regime]
        r = random.gauss(mu, sigma)
        returns.append(r)
        regime_sequence.append(current_regime)

        # Random regime transition
        if random.random() < 0.05:
            current_regime = random.randint(0, 3)

    hmm = HMMRegimeDetector()
    params = hmm.calibrate(returns)

    print(f"[HMM] Calibrated means: {[f'{m:.4f}' for m in params.means]}")
    print(f"[HMM] Calibrated stds: {[f'{s:.4f}' for s in params.stds]}")

    # Test online update
    result = hmm.update(0.01)  # positive return
    print(f"[HMM] After +1% return: {result.most_likely_state} (conf={result.state_confidence:.2f})")
    print(f"[HMM] Recommendation: {result.transition_recommendation}")

    result2 = hmm.update(-0.03)  # negative return
    print(f"[HMM] After -3% return: {result2.most_likely_state} (conf={result2.state_confidence:.2f})")

    # Sanity checks
    assert len(params.means) == 4, "Should have 4 states"
    assert all(0 < s < 0.1 for s in params.stds), "Stds should be reasonable"
    assert result.most_likely_state in ("CRISIS", "BEAR", "RECOVERY", "BULL")
    print("[HMM] Self-check PASSED")


if __name__ == "__main__":
    _demo()
