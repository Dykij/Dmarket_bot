"""
state.py — Persistent state tracking for NIM Orchestrator.

Stores per-model circuit breaker status and API key usage metrics in a
local JSON file for crash resilience. Avoids SQLite dependency for this
module to keep the orchestrator self-contained.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Optional

from .models import NimCircuitState, NimCircuitStatus

logger = logging.getLogger("NIM.State")

_DEFAULT_STATE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "nim_state"
_DEFAULT_STATE_FILE = "circuit_state.json"


class NimStateStore:
    """JSON-backed persistent state for NIM circuit breakers and key metrics."""

    def __init__(self, state_dir: Optional[str] = None) -> None:
        if state_dir:
            self._dir = Path(state_dir)
        else:
            self._dir = _DEFAULT_STATE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / _DEFAULT_STATE_FILE
        self._cache: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._cache = data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load NIM state: {e} — starting fresh")
            self._cache = {}

    def _save(self) -> None:
        try:
            self._path.write_text(
                json.dumps(self._cache, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning(f"Failed to persist NIM state: {e}")

    def get_circuit(self, model_id: str) -> NimCircuitStatus:
        raw = self._cache.get(model_id, {})
        return NimCircuitStatus(
            model_id=model_id,
            state=NimCircuitState(raw.get("state", "CLOSED")),
            consecutive_failures=raw.get("consecutive_failures", 0),
            current_cooldown=raw.get("current_cooldown", 0.0),
            opened_at=raw.get("opened_at", 0.0),
            total_opens=raw.get("total_opens", 0),
            last_error=raw.get("last_error", ""),
            server_backoff_until=raw.get("server_backoff_until", 0.0),
            weight=raw.get("weight", 1.0),
            success_count=raw.get("success_count", 0),
            fail_count=raw.get("fail_count", 0),
        )

    def save_circuit(self, status: NimCircuitStatus) -> None:
        self._cache[status.model_id] = {
            "state": status.state.value,
            "consecutive_failures": status.consecutive_failures,
            "current_cooldown": status.current_cooldown,
            "opened_at": status.opened_at,
            "total_opens": status.total_opens,
            "last_error": status.last_error,
            "server_backoff_until": status.server_backoff_until,
            "weight": status.weight,
            "success_count": status.success_count,
            "fail_count": status.fail_count,
        }
        self._save()

    def get_key_metrics(self, key_hash: str) -> dict:
        raw = self._cache.get(f"__key__{key_hash}", {})
        return {
            "request_count": raw.get("request_count", 0),
            "last_used": raw.get("last_used", 0.0),
            "active_connections": raw.get("active_connections", 0),
            "total_429": raw.get("total_429", 0),
        }

    def update_key_metrics(self, key_hash: str, **kwargs) -> None:
        key = f"__key__{key_hash}"
        if key not in self._cache:
            self._cache[key] = {}
        self._cache[key].update(kwargs)
        self._save()

    def clear(self) -> None:
        self._cache = {}
        try:
            if self._path.exists():
                self._path.unlink()
        except OSError:
            pass

    def status(self) -> Dict[str, dict]:
        result: Dict[str, dict] = {}
        for model_id, raw in self._cache.items():
            if model_id.startswith("__key__"):
                continue
            result[model_id] = dict(raw)
        return result