"""
circuit_breaker_manager.py — Per-component circuit breaker with SQLite persistence.

Wraps the existing CircuitBreaker from backoff.py with:
- Per-component tracking (API, Oracle, SQLite, Telegram)
- SQLite persistence for restart survival
- Unified status reporting
- Trading loop integration (check_all, record_success/failure)

Usage:
    from src.risk.circuit_breaker_manager import circuit_manager

    # Before using a component
    if not circuit_manager.is_available("oracle"):
        skip_this_cycle()

    # After a component call
    try:
        result = await oracle.get_price(...)
        circuit_manager.record_success("oracle")
    except Exception as e:
        circuit_manager.record_failure("oracle", e)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("CircuitManager")


class ComponentState(Enum):
    CLOSED = "CLOSED"        # normal operation
    OPEN = "OPEN"            # blocking all requests
    HALF_OPEN = "HALF_OPEN"  # testing one request


@dataclass
class ComponentBreaker:
    """Per-component circuit breaker with persistence support."""

    name: str
    fail_threshold: int = 5
    base_cooldown: float = 60.0
    max_cooldown: float = 600.0

    state: ComponentState = field(default=ComponentState.CLOSED)
    consecutive_failures: int = field(default=0)
    current_cooldown: float = field(default=0.0)
    opened_at: float = field(default=0.0)
    total_opens: int = field(default=0)
    last_error: str = field(default="")
    last_success_at: float = field(default=0.0)
    last_failure_at: float = field(default=0.0)

    def __post_init__(self) -> None:
        if self.current_cooldown == 0.0:
            self.current_cooldown = self.base_cooldown

    def is_available(self) -> bool:
        """Check if component is available for use."""
        if self.state == ComponentState.CLOSED:
            return True
        if self.state == ComponentState.OPEN:
            elapsed = time.time() - self.opened_at
            if elapsed >= self.current_cooldown:
                self.state = ComponentState.HALF_OPEN
                logger.info(
                    f"[CB:{self.name}] OPEN → HALF_OPEN "
                    f"(cooldown={self.current_cooldown:.1f}s)"
                )
                return True
            return False
        # HALF_OPEN — allow one probe
        return True

    def record_success(self) -> None:
        """Record successful component call."""
        if self.state != ComponentState.CLOSED:
            logger.info(f"[CB:{self.name}] {self.state.value} → CLOSED (success)")
        self.state = ComponentState.CLOSED
        self.consecutive_failures = 0
        self.current_cooldown = self.base_cooldown
        self.last_error = ""
        self.last_success_at = time.time()

    def record_failure(self, error: Exception) -> None:
        """Record failed component call."""
        self.consecutive_failures += 1
        self.last_error = f"{type(error).__name__}: {error}"[:200]
        self.last_failure_at = time.time()

        if self.consecutive_failures >= self.fail_threshold:
            if self.state != ComponentState.OPEN:
                import random
                jitter = 1.0 + random.uniform(-0.2, 0.2)
                self.current_cooldown = min(
                    self.base_cooldown * jitter, self.max_cooldown
                )
                self.opened_at = time.time()
                self.state = ComponentState.OPEN
                self.total_opens += 1
                logger.warning(
                    f"[CB:{self.name}] → OPEN "
                    f"(failures={self.consecutive_failures}, "
                    f"cooldown={self.current_cooldown:.1f}s, err={self.last_error})"
                )
            else:
                self.current_cooldown = min(
                    self.current_cooldown * 2.0, self.max_cooldown
                )
                self.opened_at = time.time()
                logger.warning(
                    f"[CB:{self.name}] OPEN extended "
                    f"(cooldown={self.current_cooldown:.1f}s)"
                )

    def to_dict(self) -> dict[str, Any]:
        """Serialize for SQLite persistence."""
        return {
            "name": self.name,
            "state": self.state.value,
            "consecutive_failures": self.consecutive_failures,
            "current_cooldown": self.current_cooldown,
            "opened_at": self.opened_at,
            "total_opens": self.total_opens,
            "last_error": self.last_error,
            "last_success_at": self.last_success_at,
            "last_failure_at": self.last_failure_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComponentBreaker:
        """Deserialize from SQLite."""
        breaker = cls(
            name=data["name"],
            state=ComponentState(data.get("state", "CLOSED")),
            consecutive_failures=data.get("consecutive_failures", 0),
            current_cooldown=data.get("current_cooldown", 60.0),
            opened_at=data.get("opened_at", 0.0),
            total_opens=data.get("total_opens", 0),
            last_error=data.get("last_error", ""),
            last_success_at=data.get("last_success_at", 0.0),
            last_failure_at=data.get("last_failure_at", 0.0),
        )
        return breaker


class CircuitBreakerManager:
    """Manages per-component circuit breakers with SQLite persistence."""

    # Default components for the DMarket trading bot
    DEFAULT_COMPONENTS = {
        "dmarket_api": ComponentBreaker(name="dmarket_api", fail_threshold=5, base_cooldown=60.0),
        "oracle": ComponentBreaker(name="oracle", fail_threshold=3, base_cooldown=120.0),
        "sqlite": ComponentBreaker(name="sqlite", fail_threshold=3, base_cooldown=30.0),
        "telegram": ComponentBreaker(name="telegram", fail_threshold=5, base_cooldown=60.0),
    }

    def __init__(self) -> None:
        self._breakers: dict[str, ComponentBreaker] = {}
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization — load from SQLite on first access."""
        if self._initialized:
            return
        self._initialized = True

        # Create default breakers
        for name, default in self.DEFAULT_COMPONENTS.items():
            self._breakers[name] = ComponentBreaker(
                name=default.name,
                fail_threshold=default.fail_threshold,
                base_cooldown=default.base_cooldown,
            )

        # Try to restore from SQLite
        self._load_from_db()

    def _load_from_db(self) -> None:
        """Load circuit breaker state from SQLite."""
        try:
            from src.db.price_history import price_db
            import json

            raw = price_db.get_state("circuit_breaker_state")
            if raw:
                data = json.loads(raw)
                for name, state in data.items():
                    if name in self._breakers:
                        self._breakers[name] = ComponentBreaker.from_dict(state)
                        # Reset OPEN state if cooldown expired while bot was down
                        if self._breakers[name].state == ComponentState.OPEN:
                            elapsed = time.time() - self._breakers[name].opened_at
                            if elapsed >= self._breakers[name].current_cooldown:
                                self._breakers[name].state = ComponentState.HALF_OPEN
                                logger.info(
                                    f"[CB:{name}] Restored as HALF_OPEN "
                                    f"(cooldown expired during downtime)"
                                )
                logger.info(f"[CircuitManager] Restored {len(data)} breakers from SQLite")
        except Exception as e:
            logger.debug(f"[CircuitManager] Could not load state from SQLite: {e}")

    def _save_to_db(self) -> None:
        """Persist circuit breaker state to SQLite."""
        try:
            from src.db.price_history import price_db
            import json

            data = {name: breaker.to_dict() for name, breaker in self._breakers.items()}
            price_db.set_state("circuit_breaker_state", json.dumps(data))
        except Exception as e:
            logger.debug(f"[CircuitManager] Could not save state to SQLite: {e}")

    def is_available(self, component: str) -> bool:
        """Check if a component is available for use."""
        self._ensure_initialized()
        breaker = self._breakers.get(component)
        if breaker is None:
            return True  # Unknown component — allow
        return breaker.is_available()

    def record_success(self, component: str) -> None:
        """Record successful component call."""
        self._ensure_initialized()
        breaker = self._breakers.get(component)
        if breaker is None:
            return
        was_not_closed = breaker.state != ComponentState.CLOSED
        breaker.record_success()
        if was_not_closed:
            self._save_to_db()

    def record_failure(self, component: str, error: Exception) -> None:
        """Record failed component call."""
        self._ensure_initialized()
        breaker = self._breakers.get(component)
        if breaker is None:
            return
        was_closed = breaker.state == ComponentState.CLOSED
        breaker.record_failure(error)
        # Save on state change or every 5 failures
        if breaker.state == ComponentState.OPEN and was_closed or breaker.consecutive_failures % 5 == 0:
            self._save_to_db()

    def get_status(self) -> dict[str, dict]:
        """Get status of all circuit breakers."""
        self._ensure_initialized()
        return {
            name: {
                "state": breaker.state.value,
                "failures": breaker.consecutive_failures,
                "cooldown": breaker.current_cooldown,
                "total_opens": breaker.total_opens,
                "last_error": breaker.last_error,
                "available": breaker.is_available(),
            }
            for name, breaker in self._breakers.items()
        }

    def get_unavailable(self) -> list[str]:
        """Get list of unavailable components."""
        self._ensure_initialized()
        return [
            name for name, breaker in self._breakers.items()
            if not breaker.is_available()
        ]

    def reset(self, component: str) -> None:
        """Manually reset a circuit breaker."""
        self._ensure_initialized()
        breaker = self._breakers.get(component)
        if breaker:
            breaker.state = ComponentState.CLOSED
            breaker.consecutive_failures = 0
            breaker.current_cooldown = breaker.base_cooldown
            breaker.last_error = ""
            self._save_to_db()
            logger.info(f"[CB:{component}] Manually reset to CLOSED")

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for name in self._breakers:
            self.reset(name)


# Global singleton
circuit_manager = CircuitBreakerManager()
