"""
thompson_sampling.py — Thompson Sampling for Strategy Selection.

Source: Thompson (1933) "On the Likelihood that One Unknown Probability
        Exceeds Another in View of the Evidence of Two Samples"
        Chapelle & Li (2011) "An Empirical Evaluation of Thompson Sampling"

Replaces CanaryMode A/B testing with faster convergence.
Thompson Sampling converges to optimal strategy in O(log N) trades
vs O(N) for frequentist A/B testing.

Key advantages over CanaryMode:
  - No minimum trade count requirement (starts learning immediately)
  - Automatically balances exploration vs exploitation
  - Handles non-stationary environments (strategy performance changes)
  - Bayesian: provides uncertainty estimates

Algorithm:
  1. Each strategy has Beta(alpha, beta) posterior for win rate
  2. To select strategy: sample from each posterior, pick highest
  3. After trade: update alpha (win) or beta (loss)
  4. For non-stationary: add forgetting factor

Complexity: O(K) per selection where K = number of strategies
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("ThompsonSampling")


@dataclass
class StrategyArm:
    """Single strategy arm in the multi-armed bandit."""
    name: str
    alpha: float = 1.0   # pseudo-wins (prior = Beta(1,1) = uniform)
    beta_param: float = 1.0   # pseudo-losses
    total_pulls: int = 0
    total_wins: int = 0
    total_reward: float = 0.0
    last_pull_time: float = 0.0

    @property
    def mean(self) -> float:
        """Posterior mean win rate."""
        return self.alpha / (self.alpha + self.beta_param)

    @property
    def variance(self) -> float:
        """Posterior variance."""
        a, b = self.alpha, self.beta_param
        return (a * b) / ((a + b) ** 2 * (a + b + 1))

    @property
    def std(self) -> float:
        """Posterior standard deviation."""
        return math.sqrt(self.variance)

    @property
    def empirical_win_rate(self) -> float:
        """Actual observed win rate."""
        if self.total_pulls == 0:
            return 0.0
        return self.total_wins / self.total_pulls

    @property
    def empirical_avg_reward(self) -> float:
        """Actual observed average reward."""
        if self.total_pulls == 0:
            return 0.0
        return self.total_reward / self.total_pulls

    def sample(self) -> float:
        """Sample from posterior Beta distribution."""
        return random.betavariate(self.alpha, self.beta_param)

    def update(self, won: bool, reward: float = 0.0) -> None:
        """Bayesian update after observing outcome."""
        self.total_pulls += 1
        if won:
            self.alpha += 1
            self.total_wins += 1
        else:
            self.beta_param += 1
        self.total_reward += reward

    def decay(self, forgetting_factor: float) -> None:
        """Apply forgetting factor for non-stationary environments."""
        # Decay toward prior (1, 1)
        self.alpha = 1.0 + (self.alpha - 1.0) * forgetting_factor
        self.beta_param = 1.0 + (self.beta_param - 1.0) * forgetting_factor


@dataclass
class ThompsonResult:
    """Result of strategy selection."""
    selected_strategy: str
    samples: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    exploration_bonus: float = 0.0


class ThompsonStrategySelector:
    """
    Thompson Sampling multi-armed bandit for strategy selection.

    Replaces CanaryMode A/B testing with Bayesian approach.
    Converges faster and handles non-stationary environments.

    Usage:
        selector = ThompsonStrategySelector(["MarketMaker", "CrossMarket", "MeanReversion"])
        strategy = selector.select()
        # ... execute strategy ...
        selector.update(strategy, won=True, reward=profit)
    """

    def __init__(
        self,
        strategies: list[str],
        forgetting_factor: float = 0.995,
        min_pulls_per_arm: int = 5,
    ):
        """
        Args:
            strategies: List of strategy names.
            forgetting_factor: Decay toward prior for non-stationary (0.99-1.0).
                0.995 = moderate forgetting, 1.0 = no forgetting (stationary).
            min_pulls_per_arm: Minimum pulls before allowing exploitation.
                Ensures each strategy is tried at least this many times.
        """
        self.arms: dict[str, StrategyArm] = {
            name: StrategyArm(name=name) for name in strategies
        }
        self.forgetting_factor = forgetting_factor
        self.min_pulls_per_arm = min_pulls_per_arm
        self._total_selections = 0
        self._selection_history: list[str] = []

    def select(self) -> ThompsonResult:
        """
        Select strategy using Thompson Sampling.

        1. If any arm has < min_pulls: force explore that arm
        2. Otherwise: sample from each posterior, select highest
        """
        self._total_selections += 1

        # Force exploration: ensure each arm is tried (shuffled to avoid ordering bias)
        import random as _random
        under_pulled = [
            (name, arm) for name, arm in self.arms.items()
            if arm.total_pulls < self.min_pulls_per_arm
        ]
        if under_pulled:
            _random.shuffle(under_pulled)
            name, arm = under_pulled[0]
            logger.info(
                f"[Thompson] Exploring {name} "
                f"(pulls={arm.total_pulls} < {self.min_pulls_per_arm})"
            )
            self._selection_history.append(name)
            return ThompsonResult(
                selected_strategy=name,
                samples={name: 1.0},
                confidence=0.0,  # low confidence during exploration
            )

        # Thompson Sampling: sample from each posterior
        samples = {name: arm.sample() for name, arm in self.arms.items()}
        selected = max(samples, key=lambda k: samples[k])

        # Confidence: based on how much the winner beat the runner-up
        sorted_samples = sorted(samples.values(), reverse=True)
        if len(sorted_samples) > 1:
            margin = sorted_samples[0] - sorted_samples[1]
            confidence = min(1.0, margin * 5)  # scale margin to [0, 1]
        else:
            confidence = 0.5

        self._selection_history.append(selected)

        logger.debug(
            f"[Thompson] Selected {selected} "
            f"(samples={', '.join(f'{k}={v:.3f}' for k, v in samples.items())})"
        )

        return ThompsonResult(
            selected_strategy=selected,
            samples=samples,
            confidence=round(confidence, 4),
        )

    def update(
        self,
        strategy: str,
        won: bool,
        reward: float = 0.0,
    ) -> None:
        """
        Update strategy posterior after observing outcome.

        Args:
            strategy: Name of the strategy that was used.
            won: Whether the trade was profitable.
            reward: Dollar profit/loss (for reward-weighted updates).
        """
        if strategy not in self.arms:
            logger.warning(f"[Thompson] Unknown strategy: {strategy}")
            return

        self.arms[strategy].update(won, reward)

        # Apply forgetting to all arms (non-stationary adaptation)
        if self.forgetting_factor < 1.0:
            for name, arm in self.arms.items():
                if name != strategy:  # don't decay the arm we just updated
                    arm.decay(self.forgetting_factor)

        logger.debug(
            f"[Thompson] Updated {strategy}: "
            f"alpha={self.arms[strategy].alpha:.2f} "
            f"beta={self.arms[strategy].beta_param:.2f} "
            f"mean={self.arms[strategy].mean:.3f}"
        )

    def get_rankings(self) -> list[dict[str, Any]]:
        """Get strategy rankings by posterior mean."""
        rankings = []
        for name, arm in self.arms.items():
            rankings.append({
                "strategy": name,
                "posterior_mean": round(arm.mean, 4),
                "posterior_std": round(arm.std, 4),
                "empirical_win_rate": round(arm.empirical_win_rate, 4),
                "empirical_avg_reward": round(arm.empirical_avg_reward, 4),
                "total_pulls": arm.total_pulls,
                "total_wins": arm.total_wins,
            })
        return sorted(rankings, key=lambda x: x["posterior_mean"], reverse=True)

    def get_state(self) -> dict[str, Any]:
        """Get current state for diagnostics."""
        return {
            "total_selections": self._total_selections,
            "arms": {
                name: {
                    "alpha": round(arm.alpha, 4),
                    "beta": round(arm.beta_param, 4),
                    "mean": round(arm.mean, 4),
                    "pulls": arm.total_pulls,
                    "wins": arm.total_wins,
                }
                for name, arm in self.arms.items()
            },
            "rankings": self.get_rankings(),
        }

    def should_explore(self) -> bool:
        """Check if we should force exploration (any arm under-pulled)."""
        return any(
            arm.total_pulls < self.min_pulls_per_arm
            for arm in self.arms.values()
        )


# ══════════════════════════════════════════════════════════════════════
# Utility: Thompson Sampling with contextual features
# ══════════════════════════════════════════════════════════════════════


class ContextualThompsonSelector:
    """
    Contextual Thompson Sampling: adjusts selection based on market regime.

    Uses HMM regime as context to condition strategy selection.
    Different regimes may favor different strategies.

    Usage:
        selector = ContextualThompsonSelector(["MarketMaker", "CrossMarket", "MeanReversion"])
        regime = hmm.update(return).most_likely_state
        strategy = selector.select(context=regime)
    """

    def __init__(
        self,
        strategies: list[str],
        contexts: list[str] | None = None,
        forgetting_factor: float = 0.995,
    ):
        if contexts is None:
            contexts = ["CRISIS", "BEAR", "RECOVERY", "BULL"]

        self.contexts = contexts
        # Separate Thompson selector per context
        self._selectors: dict[str, ThompsonStrategySelector] = {
            ctx: ThompsonStrategySelector(
                strategies, forgetting_factor=forgetting_factor
            )
            for ctx in contexts
        }
        self._default_selector = ThompsonStrategySelector(
            strategies, forgetting_factor=forgetting_factor
        )

    def select(self, context: str = "BULL") -> ThompsonResult:
        """Select strategy conditioned on market regime."""
        selector = self._selectors.get(context, self._default_selector)
        return selector.select()

    def update(
        self,
        strategy: str,
        won: bool,
        context: str = "BULL",
        reward: float = 0.0,
    ) -> None:
        """Update the context-specific posterior."""
        selector = self._selectors.get(context, self._default_selector)
        selector.update(strategy, won, reward)

    def get_state(self) -> dict[str, Any]:
        """Get state for all contexts."""
        return {
            ctx: selector.get_state()
            for ctx, selector in self._selectors.items()
        }


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for Thompson Sampling."""
    random.seed(42)

    # Create selector with 3 strategies
    selector = ThompsonStrategySelector(
        ["MarketMaker", "CrossMarket", "MeanReversion"],
        min_pulls_per_arm=3,
    )

    # Simulate: MarketMaker wins 60%, CrossMarket wins 50%, MeanReversion wins 40%
    win_rates = {"MarketMaker": 0.6, "CrossMarket": 0.5, "MeanReversion": 0.4}

    for _ in range(100):
        result = selector.select()
        strategy = result.selected_strategy
        won = random.random() < win_rates[strategy]
        reward = 1.0 if won else -0.5
        selector.update(strategy, won, reward)

    rankings = selector.get_rankings()
    print("[Thompson] Rankings after 100 trades:")
    for r in rankings:
        print(f"  {r['strategy']}: mean={r['posterior_mean']:.3f} "
              f"empirical={r['empirical_win_rate']:.3f} "
              f"pulls={r['total_pulls']}")

    # MarketMaker should be ranked highest (60% win rate)
    assert rankings[0]["strategy"] == "MarketMaker", \
        f"Expected MarketMaker first, got {rankings[0]['strategy']}"

    # Test contextual
    ctx_selector = ContextualThompsonSelector(
        ["MarketMaker", "CrossMarket"],
        contexts=["CRISIS", "BULL"],
    )
    result = ctx_selector.select(context="CRISIS")
    assert result.selected_strategy in ["MarketMaker", "CrossMarket"]

    print("[Thompson] Self-check PASSED")


if __name__ == "__main__":
    _demo()
