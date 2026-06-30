"""
NIM Orchestrator v1.0 — Autonomous NVIDIA NIM Rate-Limit Bypass Engine.

Provides transparent model failover, API key pool rotation, circuit breaker
with exponential backoff, and stream-through failover for OpenAI-compatible
NVIDIA NIM endpoints (https://integrate.api.nvidia.com/v1).

Usage:
    from src.nim_orchestrator import NvidiaNimOrchestrator

    orchestrator = NvidiaNimOrchestrator()
    response = await orchestrator.route_chat(
        messages=[{"role": "user", "content": "Hello"}],
        tier="primary",
    )
"""

from .orchestrator import NvidiaNimOrchestrator  # noqa: F401
from .models import NimOrchestratorConfig, NimModelInfo, NimCircuitState  # noqa: F401