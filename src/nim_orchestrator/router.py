"""
router.py — Adaptive Model Swapping + Weighted Circuit Breaker.

Core routing logic: when a model returns 429 or 5xx, the router instantly
switches to the next equivalent model in the same fallback tier without
exposing the error to the caller.

Implements:
  - Circuit Breaker with sliding penalty weights per model
  - Retry-After / X-RateLimit header parsing
  - Tier-based fallback cascading
  - Exponential backoff with ±20% jitter
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    ModelTier,
    NimCircuitState,
    NimCircuitStatus,
    NimOrchestratorConfig,
)
from .state import NimStateStore

logger = logging.getLogger("NIM.Router")


class WeightedCircuitBreaker:
    """Per-model circuit breaker with sliding penalty weights."""

    def __init__(
        self,
        model_id: str,
        config: NimOrchestratorConfig,
        state_store: Optional[NimStateStore] = None,
    ) -> None:
        self.model_id = model_id
        self._config = config
        self._store = state_store

        if state_store:
            persisted = state_store.get_circuit(model_id)
            self._status = persisted
        else:
            self._status = NimCircuitStatus(model_id=model_id)

        self._lock = asyncio.Lock()

    @property
    def state(self) -> NimCircuitState:
        return self._status.state

    @property
    def weight(self) -> float:
        return self._status.weight

    async def allow_request(self) -> bool:
        async with self._lock:
            now = time.time()
            if now < self._status.server_backoff_until:
                return False

            if self._status.state == NimCircuitState.CLOSED:
                return True

            if self._status.state == NimCircuitState.OPEN:
                elapsed = now - self._status.opened_at
                if elapsed >= self._status.current_cooldown:
                    self._status.state = NimCircuitState.HALF_OPEN
                    logger.info(
                        f"[NIM:{self.model_id}] OPEN → HALF_OPEN "
                        f"(cooldown={self._status.current_cooldown:.1f}s)"
                    )
                    self._persist()
                    return True
                return False

            if self._status.state == NimCircuitState.HALF_OPEN:
                if self._status.consecutive_failures == 0:
                    return True
                return False

            return True

    async def record_success(self) -> None:
        async with self._lock:
            if self._status.state != NimCircuitState.CLOSED:
                logger.info(
                    f"[NIM:{self.model_id}] {self._status.state.value} → CLOSED (success)"
                )
            self._status.state = NimCircuitState.CLOSED
            self._status.consecutive_failures = 0
            self._status.current_cooldown = self._config.circuit_base_cooldown
            self._status.last_error = ""
            self._status.success_count += 1
            self._status.weight = min(2.0, self._status.weight + 0.05)
            self._persist()

    async def record_failure(self, error_msg: str = "") -> None:
        async with self._lock:
            self._status.consecutive_failures += 1
            self._status.fail_count += 1
            self._status.last_error = error_msg[:200]
            self._status.weight = max(0.1, self._status.weight - 0.15)

            if self._status.consecutive_failures >= self._config.circuit_fail_threshold:
                jitter = 1.0 + random.uniform(
                    -self._config.circuit_jitter_pct,
                    self._config.circuit_jitter_pct,
                )
                if self._status.state != NimCircuitState.OPEN:
                    self._status.state = NimCircuitState.OPEN
                    self._status.total_opens += 1
                    self._status.opened_at = time.time()
                    self._status.current_cooldown = (
                        self._config.circuit_base_cooldown * jitter
                    )
                    logger.warning(
                        f"[NIM:{self.model_id}] → OPEN "
                        f"(failures={self._status.consecutive_failures}, "
                        f"cooldown={self._status.current_cooldown:.1f}s)"
                    )
                else:
                    self._status.current_cooldown = min(
                        self._status.current_cooldown * 2.0,
                        self._config.circuit_max_cooldown,
                    )
                    self._status.opened_at = time.time()
                    logger.warning(
                        f"[NIM:{self.model_id}] OPEN extended "
                        f"(cooldown={self._status.current_cooldown:.1f}s)"
                    )
            self._persist()

    def apply_retry_after(self, retry_after: float) -> None:
        now = time.time()
        proposed = now + retry_after
        if proposed > self._status.server_backoff_until:
            self._status.server_backoff_until = proposed
            logger.info(
                f"[NIM:{self.model_id}] Retry-After: {retry_after:.1f}s"
            )

    def apply_rate_limit_remaining(self, remaining: int, reset_seconds: Optional[float] = None) -> None:
        if remaining <= 0:
            self.apply_retry_after(
                reset_seconds if reset_seconds is not None else self._config.circuit_base_cooldown
            )
        elif remaining < self._config.rate_limit_remaining_warn:
            self._status.server_backoff_until = max(
                self._status.server_backoff_until,
                time.time() + self._config.preemptive_slowdown,
            )

    def status(self) -> dict:
        return {
            "model_id": self.model_id,
            "state": self._status.state.value,
            "weight": self._status.weight,
            "consecutive_failures": self._status.consecutive_failures,
            "current_cooldown": self._status.current_cooldown,
            "total_opens": self._status.total_opens,
            "success_count": self._status.success_count,
            "fail_count": self._status.fail_count,
            "last_error": self._status.last_error,
            "server_backoff_remaining": round(
                max(0.0, self._status.server_backoff_until - time.time()), 1
            ),
        }

    def _persist(self) -> None:
        if self._store:
            self._store.save_circuit(self._status)


class NimModelRouter:
    """
    Adaptive model router: selects the best available model from a tier,
    handles failover across tiers on 429/5xx, and manages per-model circuit
    breakers.
    """

    _TIER_ORDER: List[ModelTier] = [
        ModelTier.FRONTIER,
        ModelTier.STRONG,
        ModelTier.MID,
        ModelTier.LIGHTWEIGHT,
    ]

    def __init__(
        self,
        config: NimOrchestratorConfig,
        state_store: Optional[NimStateStore] = None,
    ) -> None:
        self._config = config
        self._store = state_store
        self._breakers: Dict[str, WeightedCircuitBreaker] = {}
        self._init_breakers()

    def _init_breakers(self) -> None:
        for model_id in self._config.model_list_flat:
            self._breakers[model_id] = WeightedCircuitBreaker(
                model_id=model_id,
                config=self._config,
                state_store=self._store,
            )

    def _get_breaker(self, model_id: str) -> WeightedCircuitBreaker:
        if model_id not in self._breakers:
            self._breakers[model_id] = WeightedCircuitBreaker(
                model_id=model_id,
                config=self._config,
                state_store=self._store,
            )
        return self._breakers[model_id]

    async def select_model(self, tier: Optional[str] = None) -> Optional[str]:
        """
        Select the best available model. If the requested tier is specified
        and unavailable, cascade to the next tier.

        Returns:
            model_id string or None if all models in all tiers are blocked.
        """
        tiers_to_try = self._resolve_tiers(tier)

        for t in tiers_to_try:
            candidates = self._config.models_by_tier.get(t, [])
            available = []
            for mid in candidates:
                breaker = self._get_breaker(mid)
                if await breaker.allow_request():
                    available.append((mid, breaker.weight))

            if available:
                available.sort(key=lambda x: x[1], reverse=True)
                return available[0][0]

        logger.warning("All models across all tiers are blocked")
        return None

    def _resolve_tiers(self, tier: Optional[str]) -> List[str]:
        if tier and tier in self._config.models_by_tier:
            idx = self._TIER_ORDER.index(ModelTier(tier)) if ModelTier(tier) in self._TIER_ORDER else 0
            return [t.value for t in self._TIER_ORDER[idx:]]
        return [t.value for t in self._TIER_ORDER]

    async def mark_failure(self, model_id: str, error_msg: str = "") -> None:
        breaker = self._get_breaker(model_id)
        await breaker.record_failure(error_msg)

    async def mark_success(self, model_id: str) -> None:
        breaker = self._get_breaker(model_id)
        await breaker.record_success()

    def apply_rate_limit_headers(
        self,
        model_id: str,
        retry_after: Optional[float],
        remaining: Optional[int],
        reset_seconds: Optional[float],
    ) -> None:
        breaker = self._get_breaker(model_id)
        if retry_after is not None:
            breaker.apply_retry_after(retry_after)
        if remaining is not None:
            breaker.apply_rate_limit_remaining(remaining, reset_seconds)

    def status(self) -> List[dict]:
        return [
            self._get_breaker(mid).status()
            for mid in sorted(self._breakers.keys())
        ]


def parse_rate_limit_headers(headers: Dict[str, Any]) -> Tuple[Optional[float], Optional[int], Optional[float]]:
    """
    Parse NVIDIA NIM rate limit headers from response.

    Returns:
        Tuple of (retry_after_seconds, remaining_requests, reset_seconds).
    """
    h = {k.lower(): v for k, v in headers.items()}

    retry_after = None
    ra = h.get("retry-after")
    if ra is not None:
        try:
            retry_after = float(ra)
        except (ValueError, TypeError):
            pass

    remaining = None
    rem = h.get("x-ratelimit-remaining-requests")
    if rem is not None:
        try:
            remaining = int(rem)
        except (ValueError, TypeError):
            pass

    reset_seconds = None
    reset = h.get("x-ratelimit-reset-requests")
    if reset is not None:
        try:
            reset_seconds = float(reset)
        except (ValueError, TypeError):
            pass

    return retry_after, remaining, reset_seconds