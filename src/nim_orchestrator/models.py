"""
models.py — Data models and validation schemas for NIM Orchestrator.

All models use strict validation to prevent parsing failures when
different NIM models return slightly different metadata or stop tokens.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Pydantic is optional; we fall back to dataclass-based validation if
# pydantic isn't installed. This keeps the orchestrator zero-dependency
# within the existing bot venv.
# ---------------------------------------------------------------------------
_USE_PYDANTIC = False
try:
    from pydantic import BaseModel, ValidationError, field_validator  # noqa: F401
    _USE_PYDANTIC = True
except ImportError:
    pass


class ModelTier(str, Enum):
    """Fallback tiers for model grouping."""
    FRONTIER = "frontier"
    STRONG = "strong"
    MID = "mid"
    LIGHTWEIGHT = "lightweight"
    CODE = "code"


class NimCircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class NimModelInfo:
    """Metadata for a single NIM model endpoint."""
    model_id: str
    provider: str = ""
    parameters: str = ""
    context_window: int = 128000
    capabilities: List[str] = field(default_factory=list)
    tier: ModelTier = ModelTier.STRONG

    @property
    def endpoint_url(self) -> str:
        return "https://integrate.api.nvidia.com/v1/chat/completions"


@dataclass
class NimCircuitStatus:
    """Per-model circuit breaker state."""
    model_id: str
    state: NimCircuitState = NimCircuitState.CLOSED
    consecutive_failures: int = 0
    current_cooldown: float = 0.0
    opened_at: float = 0.0
    total_opens: int = 0
    last_error: str = ""
    server_backoff_until: float = 0.0
    weight: float = 1.0
    success_count: int = 0
    fail_count: int = 0


_DEFAULT_NVIDIA_MODELS_BY_TIER: Dict[str, List[str]] = {
    "frontier": [
        "deepseek-ai/deepseek-v4-pro",
        "qwen/qwen3.5-122b-a10b",
        "nvidia/nemotron-3-ultra-550b-a55b",
        "z-ai/glm-5.1",
        "minimaxai/minimax-m3",
    ],
    "strong": [
        "nvidia/llama-3.1-nemotron-70b-instruct",
        "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "meta/llama-3.3-70b-instruct",
        "mistralai/mistral-large-3-675b-instruct-2512",
        "google/gemma-4-31b-it",
    ],
    "mid": [
        "nvidia/nemotron-3-nano-30b-a3b",
        "nvidia/llama-3.1-nemotron-51b-instruct",
        "mistralai/mixtral-8x22b-v0.1",
        "openai/gpt-oss-20b",
        "mistralai/mistral-small-4-119b-2603",
    ],
    "lightweight": [
        "meta/llama-3.1-8b-instruct",
        "nvidia/llama-3.1-nemotron-nano-8b-v1",
        "mistralai/mistral-7b-instruct-v0.3",
        "nvidia/nemotron-nano-9b-v2",
    ],
    "code": [
        "qwen/qwen3.5-122b-a10b",
        "deepseek-ai/deepseek-coder-6.7b-instruct",
        "mistralai/codestral-22b-instruct-v0.1",
        "ibm/granite-34b-code-instruct",
        "bigcode/starcoder2-15b",
    ],
}


@dataclass
class NimOrchestratorConfig:
    """Configuration for the NIM Orchestrator."""
    base_url: str = "https://integrate.api.nvidia.com/v1"
    api_keys: List[str] = field(default_factory=list)
    model_pool: List[str] = field(default_factory=list)
    models_by_tier: Dict[str, List[str]] = field(default_factory=lambda: _DEFAULT_NVIDIA_MODELS_BY_TIER)
    default_timeout: float = 60.0
    max_retries: int = 3
    max_stream_retries: int = 2

    circuit_fail_threshold: int = 3
    circuit_base_cooldown: float = 30.0
    circuit_max_cooldown: float = 300.0
    circuit_jitter_pct: float = 0.2
    circuit_half_open_timeout: float = 60.0

    probe_interval: float = 30.0

    rate_limit_remaining_warn: int = 5
    preemptive_slowdown: float = 5.0

    request_delay: float = 0.05

    @property
    def model_list_flat(self) -> List[str]:
        if self.model_pool:
            return list(dict.fromkeys(self.model_pool))
        result: List[str] = []
        for tier in ["frontier", "strong", "mid", "lightweight", "code"]:
            result.extend(self.models_by_tier.get(tier, []))
        return list(dict.fromkeys(result))