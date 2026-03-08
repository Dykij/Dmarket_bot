"""
MarkovChainPredictor v2.0 — CUDA-accelerated spread regime classifier.

Uses CuPy for GPU-accelerated tensor operations when CUDA is available,
with automatic fallback to NumPy on CPU-only systems.

Architecture:
  - Transition matrix (3×3) updated incrementally via Laplace smoothing.
  - Z-score classification against rolling mean/std (window=30).
  - Batch mode: classify 10,000+ spreads in a single GPU kernel call.

States:
  STABLE (0)    — spread within ±1σ of rolling mean
  VOLATILE (1)  — spread within ±1σ..±3σ
  ANOMALOUS (2) — spread outside ±3σ (likely bait / flash crash)

Hardware target: NVIDIA RTX 5060 Ti (CUDA 12.x, Tensor Cores).
"""

# ── GPU/CPU backend selection ──
try:
    import cupy as xp  # type: ignore[import-untyped]
    GPU_AVAILABLE = True
except ImportError:
    import numpy as xp  # type: ignore[assignment]
    GPU_AVAILABLE = False

import numpy as np  # Always needed for CPU-side I/O
from typing import List, Tuple, Optional
from enum import IntEnum


class MarketState(IntEnum):
    """Discrete order-book regimes."""
    STABLE = 0
    VOLATILE = 1
    ANOMALOUS = 2


class MarkovChainPredictor:
    """
    3-state Markov Chain for spread regime classification.

    When CuPy is available, the rolling statistics and batch classification
    run entirely on the GPU. The transition matrix and persistence calculations
    use GPU tensors for parallel evaluation across thousands of items.

    Parameters
    ----------
    lookback : int
        Rolling window size for mean/std calculation (default 30).
    sigma_volatile : float
        σ threshold for STABLE → VOLATILE boundary (default 1.0).
    sigma_anomalous : float
        σ threshold for VOLATILE → ANOMALOUS boundary (default 3.0).
    smoothing : float
        Laplace smoothing constant for transition counts (default 1.0).

    Example
    -------
    >>> mc = MarkovChainPredictor()
    >>> for spread in historical_spreads:
    ...     mc.observe(spread)
    >>> state = mc.classify(current_spread)
    >>> p = mc.predict_persistence(state, steps=3)
    """

    def __init__(
        self,
        lookback: int = 30,
        sigma_volatile: float = 1.0,
        sigma_anomalous: float = 3.0,
        smoothing: float = 1.0,
    ):
        self.lookback = lookback
        self.sigma_volatile = sigma_volatile
        self.sigma_anomalous = sigma_anomalous
        self.smoothing = smoothing

        # Raw spread history (CPU list for append efficiency)
        self._spreads: List[float] = []

        # Transition counts on GPU/CPU: C[i][j] = transitions from i → j
        self._counts = xp.full((3, 3), smoothing, dtype=xp.float64)

        # Last classified state
        self._last_state: Optional[MarketState] = None

        if GPU_AVAILABLE:
            print("   🟢 MarkovChainPredictor: CuPy CUDA backend active")
        else:
            print("   🟡 MarkovChainPredictor: NumPy CPU fallback")

    # ───────── Public API ─────────

    def observe(self, spread: float) -> MarketState:
        """Record a spread observation and update the transition matrix."""
        self._spreads.append(spread)
        state = self.classify(spread)

        if self._last_state is not None:
            self._counts[self._last_state][state] += 1.0

        self._last_state = state
        return state

    def classify(self, spread: float) -> MarketState:
        """
        Classify a single spread value into a market state.

        Uses GPU-accelerated rolling statistics when CuPy is available.
        """
        if len(self._spreads) < 2:
            return MarketState.STABLE

        # Transfer window to GPU array for accelerated mean/std
        window = xp.array(self._spreads[-self.lookback:], dtype=xp.float64)
        mu = float(xp.mean(window))
        sigma = float(xp.std(window))

        if sigma < 1e-9:
            return MarketState.STABLE

        z_score = abs(spread - mu) / sigma

        if z_score > self.sigma_anomalous:
            return MarketState.ANOMALOUS
        elif z_score > self.sigma_volatile:
            return MarketState.VOLATILE
        else:
            return MarketState.STABLE

    def classify_batch(self, spreads: List[float]) -> List[MarketState]:
        """
        Classify multiple spreads in a single GPU kernel call.

        This is the key acceleration: instead of looping 10,000 times,
        we compute z-scores for all spreads in one vectorized operation.

        Parameters
        ----------
        spreads : list[float]
            Batch of spread values (e.g., from 10K order books).

        Returns
        -------
        list[MarketState]
            Classified state for each spread.
        """
        if len(self._spreads) < 2:
            return [MarketState.STABLE] * len(spreads)

        # Window statistics (GPU)
        window = xp.array(self._spreads[-self.lookback:], dtype=xp.float64)
        mu = xp.mean(window)
        sigma = xp.std(window)

        if float(sigma) < 1e-9:
            return [MarketState.STABLE] * len(spreads)

        # Vectorized z-scores (single GPU kernel)
        batch_gpu = xp.array(spreads, dtype=xp.float64)
        z_scores = xp.abs(batch_gpu - mu) / sigma

        # Classify via GPU comparison
        states_gpu = xp.zeros(len(spreads), dtype=xp.int32)  # Default: STABLE
        states_gpu[z_scores > self.sigma_volatile] = MarketState.VOLATILE
        states_gpu[z_scores > self.sigma_anomalous] = MarketState.ANOMALOUS

        # Transfer back to CPU
        if GPU_AVAILABLE:
            states_cpu = xp.asnumpy(states_gpu)
        else:
            states_cpu = np.asarray(states_gpu)

        return [MarketState(s) for s in states_cpu]

    @property
    def transition_matrix(self) -> np.ndarray:
        """
        Row-stochastic transition matrix P[i][j] = P(j | i).

        Returns a CPU numpy array (for logging/serialization).
        """
        row_sums = self._counts.sum(axis=1, keepdims=True)
        row_sums = xp.maximum(row_sums, 1e-9)
        P = self._counts / row_sums

        # Ensure CPU-side return
        if GPU_AVAILABLE:
            return xp.asnumpy(P)
        return np.asarray(P)

    def predict_persistence(self, state: MarketState, steps: int = 3) -> float:
        """
        P(chain stays in `state` for `steps` consecutive steps).

        P(persist) = P[state][state] ^ steps
        """
        P = self.transition_matrix
        p_stay = P[state][state]
        return float(p_stay ** steps)

    def is_organic_spread(
        self,
        spread: float,
        threshold: float = 0.05,
        persistence_steps: int = 3,
    ) -> Tuple[bool, MarketState, float]:
        """
        Gate function for the Scanner pipeline.

        Returns (is_organic, state, probability).
        If state == ANOMALOUS and P(persist) < threshold → blocked.
        """
        state = self.observe(spread)
        prob = self.predict_persistence(state, steps=persistence_steps)

        if state == MarketState.ANOMALOUS and prob < threshold:
            return False, state, prob

        return True, state, prob

    def get_statistics(self) -> dict:
        """Return diagnostic statistics for logging."""
        P = self.transition_matrix
        return {
            "observations": len(self._spreads),
            "gpu_accelerated": GPU_AVAILABLE,
            "transition_matrix": P.tolist(),
            "last_state": self._last_state.name if self._last_state else "N/A",
            "p_stable_stay": float(P[0][0]),
            "p_volatile_stay": float(P[1][1]),
            "p_anomalous_stay": float(P[2][2]),
        }
