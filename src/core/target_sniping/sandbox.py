"""
sandbox.py — DRY_RUN simulation helpers (competition, latency, errors).

These helpers are no-ops in production. They model real-world frictions
(network RTT, API 429/5xx, competitor sniping) for the simulator.

Mixed into `SnipingLoop` (see `core.py`).
"""

from __future__ import annotations

import asyncio
import logging
import os
import random

logger = logging.getLogger("SnipingBot")


class _SandboxMixin:
    """DRY_RUN simulation helpers (competition, latency, errors)."""

    def _simulate_competition(self, margin: float) -> bool:
        """Sandbox v9.0: Models the probability of being out-sniped by a competitor."""
        if os.getenv("DRY_RUN", "true").lower() != "true":
            return True
        if margin > 0.40:
            fail_chance = 0.90
        elif margin > 0.20:
            fail_chance = 0.60
        elif margin > 0.10:
            fail_chance = 0.30
        else:
            fail_chance = 0.10
        return random.random() >= fail_chance

    async def _simulate_network_latency(self, client_type: str = "dmarket") -> None:
        """Sandbox v9.5: Mimics real-world network RTT (Round Trip Time) with Jitter."""
        if os.getenv("DRY_RUN", "true").lower() != "true":
            return
        if client_type == "cs2cap":
            base_lat, jitter = 600, 400
        else:
            base_lat, jitter = 200, 200
        delay = (base_lat + random.randint(0, jitter)) / 1000.0
        await asyncio.sleep(delay)

    def _maybe_inject_error(self, method_name: str) -> None:
        """Sandbox v9.5: Randomly injects API 429/5xx errors to test resilience."""
        if os.getenv("DRY_RUN", "true").lower() != "true":
            return
        if random.random() < 0.05:
            error_code = random.choice([429, 500, 502, 503])
            logger.warning(f"[SIM ERROR] Injected {error_code} for {method_name}!")
            raise Exception(f"Simulated API Error: {error_code}")
