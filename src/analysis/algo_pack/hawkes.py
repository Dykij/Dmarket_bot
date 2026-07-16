"""
hawkes.py — Hawkes Process estimator for DMarket event intensity.

Source: Cartea, Jaimungal, Penalva (2015) "Algorithmic and High-Frequency Trading"
        Easley, López de Prado, O'Hara (2012) "Flow Toxicity and Liquidity"

The Hawkes process is a self-exciting point process where each event
increases the intensity of future events temporarily. This models:

- Listing clusters: cheap items trigger chain reactions
- FOMO buying: one bot's purchase triggers others
- Price cascades: rapid listings during panic selling

Key formula:
    λ(t) = μ + Σ α × e^(-β × (t - tᵢ))

Where:
    λ(t)  = intensity at time t
    μ     = baseline intensity (background rate)
    α     = jump size (how much each event excites future events)
    β     = decay rate (how quickly excitement fades)
    tᵢ    = times of previous events

Applications:
- Detect aжиотаж (intensity spike) → avoid buying during FOMO
- Detect calm markets (low intensity) → good entry time
- Predict when listings will cluster after price drops

Complexity: O(N) per update with running accumulators
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Sequence

logger = logging.getLogger("Hawkes")


@dataclass
class HawkesState:
    """Running state for online Hawkes intensity estimation."""
    baseline: float = 0.01       # μ: background intensity (events/second)
    alpha: float = 0.5           # jump size per event
    beta: float = 0.1            # decay rate
    current_intensity: float = 0.01
    excitation: float = 0.0      # accumulated excitation Σ α × e^(-β × Δt)
    last_update_time: float = 0.0
    event_count: int = 0
    _decay_cache: float = 0.0    # precomputed e^(-β × Δt) for efficiency


@dataclass
class HawkesEstimator:
    """Online Hawkes process intensity estimator.

    Maintains running state and updates intensity as new events arrive.
    Designed for real-time use with O(1) per-event update.

    Typical usage:
        estimator = HawkesEstimator()
        for event_time in listing_timestamps:
            intensity = estimator.update(event_time)
        current = estimator.get_intensity()
    """

    baseline: float = 0.01       # μ: baseline event rate
    alpha: float = 0.5           # excitation per event
    beta: float = 0.1            # decay speed

    # Internal state
    _state: HawkesState = field(default_factory=HawkesState, init=False)

    def __post_init__(self) -> None:
        self._state = HawkesState(
            baseline=self.baseline,
            alpha=self.alpha,
            beta=self.beta,
            current_intensity=self.baseline,
        )

    def update(self, event_time: float) -> float:
        """Update intensity with a new event at event_time (seconds).

        Args:
            event_time: Timestamp of the event (seconds since epoch or relative).

        Returns:
            Current intensity λ(t) after this event.
        """
        s = self._state

        if s.last_update_time > 0 and event_time > s.last_update_time:
            dt = event_time - s.last_update_time
            # Decay accumulated excitation
            decay = math.exp(-s.beta * dt)
            s.excitation *= decay

        # Each new event adds α to excitation
        s.excitation += s.alpha

        # Current intensity = μ + excitation
        s.current_intensity = s.baseline + s.excitation

        s.last_update_time = event_time
        s.event_count += 1

        return s.current_intensity

    def intensity_at(self, t: float) -> float:
        """Predict intensity at future time t (seconds from last event).

        Does NOT update state — read-only projection.
        """
        s = self._state
        if s.last_update_time <= 0:
            return s.baseline

        dt = max(0.0, t - s.last_update_time)
        decay = math.exp(-s.beta * dt) if s.beta > 0 else 1.0
        return s.baseline + s.excitation * decay

    def get_intensity(self) -> float:
        """Current intensity estimate."""
        return self._state.current_intensity

    def get_intensity_ratio(self) -> float:
        """Ratio of current to baseline intensity.

        Returns:
            1.0 = normal activity
            > 2.0 = elevated (aжиотаж)
            > 3.0 = high excitement (avoid buying)
            < 0.5 = very quiet (good entry time)
        """
        return self._state.current_intensity / max(self._state.baseline, 1e-8)

    def get_state(self) -> HawkesState:
        """Get copy of current state for debugging."""
        return HawkesState(
            baseline=self._state.baseline,
            alpha=self._state.alpha,
            beta=self._state.beta,
            current_intensity=self._state.current_intensity,
            excitation=self._state.excitation,
            last_update_time=self._state.last_update_time,
            event_count=self._state.event_count,
        )

    def reset(self) -> None:
        """Reset state to baseline."""
        self._state = HawkesState(
            baseline=self.baseline,
            alpha=self.alpha,
            beta=self.beta,
            current_intensity=self.baseline,
        )


def hawkes_intensity_from_timestamps(
    timestamps: Sequence[float],
    baseline: float = 0.01,
    alpha: float = 0.5,
    beta: float = 0.1,
) -> float:
    """One-shot Hawkes intensity from a list of event timestamps.

    Args:
        timestamps: Sorted list of event timestamps (seconds).
        baseline: Background rate μ.
        alpha: Excitation per event.
        beta: Decay rate.

    Returns:
        Final intensity after processing all events.
    """
    if not timestamps:
        return baseline

    estimator = HawkesEstimator(baseline=baseline, alpha=alpha, beta=beta)
    for ts in timestamps:
        estimator.update(ts)
    return estimator.get_intensity()


def hawkes_intensity_from_intervals(
    intervals: Sequence[float],
    baseline: float = 0.01,
    alpha: float = 0.5,
    beta: float = 0.1,
) -> float:
    """Hawkes intensity from inter-event times (seconds between events).

    More practical when we have time deltas rather than absolute timestamps.

    Args:
        intervals: Time gaps between consecutive events (seconds).
        baseline: Background rate μ.
        alpha: Excitation per event.
        beta: Decay rate.

    Returns:
        Final intensity.
    """
    if not intervals:
        return baseline

    estimator = HawkesEstimator(baseline=baseline, alpha=alpha, beta=beta)
    t = 0.0
    for dt in intervals:
        t += dt
        estimator.update(t)
    return estimator.get_intensity()


def classify_activity_level(intensity_ratio: float) -> str:
    """Classify market activity from Hawkes intensity ratio.

    Args:
        intensity_ratio: current_intensity / baseline

    Returns:
        "quiet"     — good entry time, low competition
        "normal"    — typical activity
        "elevated"  — increased activity, be cautious
        "frenzy"    — aжиотаж, avoid buying
    """
    if intensity_ratio < 0.5:
        return "quiet"
    elif intensity_ratio < 1.5:
        return "normal"
    elif intensity_ratio < 3.0:
        return "elevated"
    else:
        return "frenzy"


# ══════════════════════════════════════════════════════════════════════
# Self-check
# ══════════════════════════════════════════════════════════════════════

def _demo() -> None:
    """Quick self-check for Hawkes estimator."""
    # Simulate clustered events (timestamps in seconds)
    timestamps = [
        10.0, 10.5, 11.0,  # cluster 1: 3 events in 1 second
        20.0,               # gap
        50.0, 50.2, 50.5, 51.0,  # cluster 2: 4 events in 1 second
        100.0,              # quiet period
    ]

    estimator = HawkesEstimator(baseline=0.01, alpha=0.5, beta=0.1)
    intensities = []
    for ts in timestamps:
        intensities.append(estimator.update(ts))

    print(f"[Hawkes] Final intensity: {intensities[-1]:.4f}")
    print(f"[Hawkes] Ratio: {estimator.get_intensity_ratio():.2f}x")
    print(f"[Hawkes] Activity: {classify_activity_level(estimator.get_intensity_ratio())}")
    print(f"[Hawkes] Event count: {estimator.get_state().event_count}")

    # After 10 events, intensity should be significantly above baseline
    assert intensities[-1] > 0.05, f"Intensity too low: {intensities[-1]}"
    # Ratio should be > 5x after clusters
    assert estimator.get_intensity_ratio() > 5.0, f"Ratio too low: {estimator.get_intensity_ratio()}"

    # Test intensity_at future time (should decay)
    future_intensity = estimator.intensity_at(200.0)  # 100 seconds later
    assert future_intensity < intensities[-1], "Future intensity should decay"

    # Test one-shot function
    one_shot = hawkes_intensity_from_timestamps(timestamps)
    assert abs(one_shot - intensities[-1]) < 0.001, "One-shot should match incremental"

    # Test intervals function
    intervals = [0.5, 0.5, 9.0, 30.0, 0.2, 0.3, 0.5, 49.0]
    from_intervals = hawkes_intensity_from_intervals(intervals)
    assert from_intervals > 0.01, f"From intervals too low: {from_intervals}"

    print("[Hawkes] Self-check PASSED")


if __name__ == "__main__":
    _demo()
