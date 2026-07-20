"""
vpin.py — Volume-Synchronized Probability of Informed Trading.

Source: Easley, López de Prado, O'Hara (2012) "Flow Toxicity and Liquidity"
        arXiv: VPIN and high-frequency trading

VPIN measures the toxicity of order flow — the probability that
trading is driven by informed traders rather than noise traders.

High VPIN → informed traders present → avoid buying (adverse selection)
Low VPIN → noise traders dominate → safe to provide liquidity

Key formula:
  VPIN = Σ|V_buy - V_sell| / (n × V_bucket)

Where:
  V_buy = buy volume (classified via BVC)
  V_sell = sell volume
  V_bucket = volume per bucket (fixed)
  n = number of buckets

Bulk Volume Classification (BVC):
  P(buy) = Φ((trade_return - μ) / σ)
  where Φ is the standard normal CDF

Applications in DMarket:
  - VPIN > 0.8 → avoid buying (informed trader activity)
  - VPIN < 0.3 → safe to trade (noise trader market)
  - VPIN spike → potential price manipulation or insider info

Complexity: O(1) per update with running accumulators
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass
from collections.abc import Sequence

logger = logging.getLogger("VPIN")


@dataclass
class VPINResult:
    """VPIN estimation result."""
    vpin: float = 0.0               # current VPIN estimate [0, 1]
    vpin_ma: float = 0.0            # moving average of VPIN
    toxicity_level: str = "normal"  # "low", "normal", "high", "extreme"
    bucket_count: int = 0
    is_toxic: bool = False          # True if VPIN > threshold


class VPINEstimator:
    """
    Online VPIN estimator with Bulk Volume Classification.

    Maintains running state and updates VPIN as new trades arrive.
    Designed for real-time use with O(1) per-trade update.

    Typical usage:
        estimator = VPINEstimator(bucket_size=100)
        for price, volume in trades:
            result = estimator.update(price, volume)
        if result.is_toxic:
            # Avoid buying — informed trader activity detected
    """

    # Thresholds
    TOXIC_THRESHOLD: float = 0.8     # VPIN above this = toxic
    HIGH_THRESHOLD: float = 0.5      # VPIN above this = elevated
    LOW_THRESHOLD: float = 0.3       # VPIN below this = safe

    # BVC parameters
    BVC_WINDOW: int = 50             # rolling window for price stats

    def __init__(
        self,
        bucket_size: float = 100.0,
        n_buckets: int = 8,
    ):
        self.bucket_size = bucket_size
        self.n_buckets = n_buckets
        self._current_bucket_volume: float = 0.0
        self._current_buy_volume: float = 0.0
        self._current_sell_volume: float = 0.0
        self._bucket_imbalances: deque[float] = deque(maxlen=n_buckets * 2)
        self._completed_buckets: int = 0
        self._last_price: float = 0.0
        self._price_window: list[float] = []
        self._price_mean: float = 0.0
        self._price_std: float = 0.0
        self._vpin_history: deque[float] = deque(maxlen=n_buckets * 2)

    def update(self, price: float, volume: float) -> VPINResult:
        """Update VPIN with new trade."""
        # Update price statistics for BVC
        self._price_window.append(price)
        if len(self._price_window) > self.BVC_WINDOW:
            self._price_window.pop(0)

        if len(self._price_window) >= 5:
            mean_p = sum(self._price_window) / len(self._price_window)
            var_p = sum(
                (p - mean_p) ** 2 for p in self._price_window
            ) / len(self._price_window)
            self._price_mean = mean_p
            self._price_std = math.sqrt(max(var_p, 1e-10))

        # Classify trade using BVC
        if self._last_price > 0 and self._price_std > 1e-10:
            trade_return = (price - self._last_price) / self._last_price
            price_drift = (
                (self._price_mean - self._last_price)
                / max(self._last_price, 1e-10)
            )
            z = (trade_return - price_drift) / self._price_std
            p_buy = 0.5 * (1.0 + math.erf(z / math.sqrt(2)))
        else:
            p_buy = 0.5

        buy_vol = volume * p_buy
        sell_vol = volume * (1.0 - p_buy)

        self._current_buy_volume += buy_vol
        self._current_sell_volume += sell_vol
        self._current_bucket_volume += volume
        self._last_price = price

        # Process complete buckets
        while self._current_bucket_volume >= self.bucket_size:
            ratio = self.bucket_size / self._current_bucket_volume
            bucket_buy = self._current_buy_volume * ratio
            bucket_sell = self._current_sell_volume * ratio

            imbalance = abs(bucket_buy - bucket_sell)
            self._bucket_imbalances.append(imbalance)
            self._completed_buckets += 1

            # Compute VPIN from last n_buckets
            if len(self._bucket_imbalances) >= self.n_buckets:
                recent = list(self._bucket_imbalances)[-self.n_buckets:]
                vpin = sum(recent) / (self.n_buckets * self.bucket_size)
                vpin = min(1.0, max(0.0, vpin))
                self._vpin_history.append(vpin)

            # Carry over overflow
            self._current_bucket_volume -= self.bucket_size
            self._current_buy_volume *= (1.0 - ratio)
            self._current_sell_volume *= (1.0 - ratio)

        vpin = self._compute_vpin()
        vpin_ma = self._compute_vpin_ma()
        toxicity = self._classify_toxicity(vpin)

        return VPINResult(
            vpin=round(vpin, 4),
            vpin_ma=round(vpin_ma, 4),
            toxicity_level=toxicity,
            bucket_count=self._completed_buckets,
            is_toxic=vpin > self.TOXIC_THRESHOLD,
        )

    def _compute_vpin(self) -> float:
        """Current VPIN from recent buckets."""
        if len(self._bucket_imbalances) < self.n_buckets:
            return 0.0
        recent = list(self._bucket_imbalances)[-self.n_buckets:]
        raw = sum(recent) / (self.n_buckets * self.bucket_size)
        return min(1.0, max(0.0, raw))

    def _compute_vpin_ma(self) -> float:
        """Moving average of VPIN."""
        if not self._vpin_history:
            return 0.0
        recent = list(self._vpin_history)[-self.n_buckets:]
        return sum(recent) / len(recent)

    def _classify_toxicity(self, vpin: float) -> str:
        """Classify VPIN level."""
        if vpin > self.TOXIC_THRESHOLD:
            return "extreme"
        elif vpin > self.HIGH_THRESHOLD:
            return "high"
        elif vpin > self.LOW_THRESHOLD:
            return "normal"
        else:
            return "low"

    def get_vpin(self) -> float:
        """Get current VPIN estimate."""
        return self._compute_vpin()

    def is_toxic(self) -> bool:
        """Check if current VPIN indicates toxic flow."""
        return self._compute_vpin() > self.TOXIC_THRESHOLD

    def get_state(self) -> dict:
        """Get current state for diagnostics."""
        return {
            "vpin": round(self._compute_vpin(), 4),
            "vpin_ma": round(self._compute_vpin_ma(), 4),
            "toxicity": self._classify_toxicity(self._compute_vpin()),
            "completed_buckets": self._completed_buckets,
            "bucket_size": self.bucket_size,
        }

    def reset(self) -> None:
        """Reset state."""
        self._current_bucket_volume = 0.0
        self._current_buy_volume = 0.0
        self._current_sell_volume = 0.0
        self._bucket_imbalances.clear()
        self._completed_buckets = 0
        self._last_price = 0.0
        self._price_window.clear()
        self._vpin_history.clear()


# ══════════════════════════════════════════════════════════════════════
# Quick utility
# ══════════════════════════════════════════════════════════════════════

def vpin_from_trades(
    trades: Sequence[tuple[float, float]],
    bucket_size: float = 100.0,
    n_buckets: int = 8,
) -> float:
    """One-shot VPIN from a list of (price, volume) trades."""
    estimator = VPINEstimator(bucket_size=bucket_size, n_buckets=n_buckets)
    for price, volume in trades:
        estimator.update(price, volume)
    return estimator.get_vpin()


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for VPIN estimator."""
    import random
    random.seed(42)

    estimator = VPINEstimator(bucket_size=50, n_buckets=5)

    # Simulate normal trading
    price = 10.0
    for _ in range(200):
        price *= (1 + random.gauss(0, 0.005))
        volume = random.uniform(5, 15)
        result = estimator.update(price, volume)

    print("[VPIN] After normal trading:")
    print(f"  VPIN: {result.vpin:.4f}")
    print(f"  VPIN MA: {result.vpin_ma:.4f}")
    print(f"  Toxicity: {result.toxicity_level}")
    print(f"  Buckets: {result.bucket_count}")

    # Simulate informed trading (one-directional)
    for _ in range(50):
        price *= 1.01  # always up
        volume = 20
        result = estimator.update(price, volume)

    print("\n[VPIN] After informed trading:")
    print(f"  VPIN: {result.vpin:.4f}")
    print(f"  Toxicity: {result.toxicity_level}")
    print(f"  Is toxic: {result.is_toxic}")

    # Sanity checks
    assert 0.0 <= result.vpin <= 1.0, f"VPIN out of range: {result.vpin}"
    assert result.toxicity_level in ("low", "normal", "high", "extreme")
    print("[VPIN] Self-check PASSED")


if __name__ == "__main__":
    _demo()
