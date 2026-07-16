"""
sliding_window.py — O(1) min/max in sliding window via monotone deque.

Source: CP-Algorithms (Stack/Queue modification)

Use cases in the bot:
- VWAP: track price range over last N ticks
- OBI: dynamic normalization of bid/ask volumes
- Volume Profile: rolling min/max for POC calculation

All operations are O(1) amortized — critical for 10 req/s DMarket limit.
"""

from __future__ import annotations

from collections import deque


class SlidingWindowMinMax:
    """O(1) min/max in a fixed-size sliding window.

    Uses two monotone deques:
    - min_deque: increasing (smallest at front)
    - max_deque: decreasing (largest at front)

    Source: CP-Algorithms stack_queue_modification.html
    """

    def __init__(self, window_size: int) -> None:
        self.size = window_size
        self.min_dq: deque[tuple[float, int]] = deque()
        self.max_dq: deque[tuple[float, int]] = deque()
        self.idx = 0

    def add(self, value: float) -> None:
        """Add a new value to the window. O(1) amortized."""
        # Remove from back while new value is better
        while self.min_dq and self.min_dq[-1][0] > value:
            self.min_dq.pop()
        self.min_dq.append((value, self.idx))

        while self.max_dq and self.max_dq[-1][0] < value:
            self.max_dq.pop()
        self.max_dq.append((value, self.idx))

        # Remove expired elements from front
        cutoff = self.idx - self.size
        if self.min_dq and self.min_dq[0][1] <= cutoff:
            self.min_dq.popleft()
        if self.max_dq and self.max_dq[0][1] <= cutoff:
            self.max_dq.popleft()

        self.idx += 1

    @property
    def min(self) -> float | None:
        """Current window minimum. O(1)."""
        return self.min_dq[0][0] if self.min_dq else None

    @property
    def max(self) -> float | None:
        """Current window maximum. O(1)."""
        return self.max_dq[0][0] if self.max_dq else None

    @property
    def range(self) -> float | None:
        """Current window range (max - min). O(1)."""
        mn, mx = self.min, self.max
        if mn is not None and mx is not None:
            return mx - mn
        return None

    @property
    def mid(self) -> float | None:
        """Current window midpoint."""
        mn, mx = self.min, self.max
        if mn is not None and mx is not None:
            return (mn + mx) / 2
        return None


class SlidingWindowEMA:
    """Exponential moving average with O(1) per update.

    Alternative to full recalculation — maintains running EWMA.
    """

    def __init__(self, alpha: float = 0.3) -> None:
        self.alpha = alpha
        self.value: float | None = None

    def add(self, price: float) -> float:
        """Add price and return updated EMA."""
        if self.value is None:
            self.value = price
        else:
            self.value = self.alpha * price + (1 - self.alpha) * self.value
        return self.value

    @property
    def current(self) -> float:
        return self.value or 0.0


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for sliding window."""
    sw = SlidingWindowMinMax(window_size=5)
    prices = [10.0, 9.5, 11.0, 8.0, 12.0, 7.0, 13.0]

    for p in prices:
        sw.add(p)
        print(f"  Added ${p:.1f} → min=${sw.min:.1f} max=${sw.max:.1f} range=${sw.range:.1f}")

    assert sw.min == 7.0, f"Expected min=7.0, got {sw.min}"
    assert sw.max == 13.0, f"Expected max=13.0, got {sw.max}"

    # EMA
    ema = SlidingWindowEMA(alpha=0.3)
    for p in prices:
        ema.add(p)
    print(f"  EMA final: ${ema.current:.2f}")

    print("[SlidingWindow] Self-check PASSED")


if __name__ == "__main__":
    _demo()
