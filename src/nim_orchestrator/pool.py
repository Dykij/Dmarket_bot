"""
pool.py — NIM API Key Pool with Round-Robin and Least-Connections balancing.

Distributes incoming requests across multiple NVIDIA NGC API keys to
maximize aggregate TPM (Tokens Per Minute) across the free tier.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import List, Optional

from .models import NimOrchestratorConfig
from .state import NimStateStore

logger = logging.getLogger("NIM.Pool")


class NimApiKeyPool:
    """Thread-safe pool of NVIDIA NGC API keys with load-aware scheduling."""

    def __init__(
        self,
        keys: List[str],
        state_store: Optional[NimStateStore] = None,
        strategy: str = "round_robin",
    ) -> None:
        """
        Args:
            keys: List of NVIDIA NGC API keys (nvapi-...).
            state_store: Optional persistent state for usage tracking.
            strategy: 'round_robin' or 'least_connections'.
        """
        if not keys:
            raise ValueError("At least one API key is required")
        self._keys = list(keys)
        self._state = state_store
        self._strategy = strategy
        self._lock = threading.Lock()
        self._index: int = 0
        self._active: dict = {i: 0 for i in range(len(keys))}

    def _key_hash(self, key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()[:12]

    @property
    def key_count(self) -> int:
        return len(self._keys)

    def acquire(self) -> tuple:
        """
        Get the next API key and its index according to the load strategy.

        Returns:
            Tuple of (api_key: str, key_index: int).
        """
        with self._lock:
            if self._strategy == "least_connections":
                idx = min(self._active, key=self._active.get)  # type: ignore[arg-type]
            else:
                idx = self._index
                self._index = (self._index + 1) % len(self._keys)

            self._active[idx] += 1

            if self._state:
                kh = self._key_hash(self._keys[idx])
                metrics = self._state.get_key_metrics(kh)
                self._state.update_key_metrics(
                    kh,
                    last_used=time.time(),
                    request_count=metrics.get("request_count", 0) + 1,
                    active_connections=self._active[idx],
                )

            return self._keys[idx], idx

    def release(self, idx: int) -> None:
        """Release an acquired key slot (decrement active connections)."""
        with self._lock:
            if idx in self._active and self._active[idx] > 0:
                self._active[idx] -= 1

    def record_429(self, key: str) -> None:
        """Record a 429 rate limit hit for a specific API key."""
        if self._state:
            kh = self._key_hash(key)
            metrics = self._state.get_key_metrics(kh)
            self._state.update_key_metrics(
                kh,
                total_429=metrics.get("total_429", 0) + 1,
                last_used=time.time(),
            )

    def status(self) -> dict:
        with self._lock:
            return {
                "total_keys": len(self._keys),
                "strategy": self._strategy,
                "active_map": dict(self._active),
                "current_index": self._index,
            }


def create_key_pool_from_config(config: NimOrchestratorConfig) -> NimApiKeyPool:
    keys = config.api_keys
    if not keys:
        import os
        env_key = os.getenv("NVIDIA_NGC_KEY", "")
        if env_key:
            keys = [env_key]
        else:
            keys = ["nvapi-placeholder"]

    return NimApiKeyPool(
        keys=keys,
        strategy="least_connections",
    )