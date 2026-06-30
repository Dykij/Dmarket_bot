"""
orchestrator.py — NvidiaNimOrchestrator: Central routing engine.

Singleton orchestrator that provides transparent NVIDIA NIM model failover,
API key pool rotation, circuit breaking, and stream-through failover.

Usage:
    orch = NvidiaNimOrchestrator.get_instance()
    response = await orch.route_chat(messages=[...], tier="frontier")
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiohttp

from .models import NimOrchestratorConfig, ModelTier
from .pool import NimApiKeyPool, create_key_pool_from_config
from .router import (
    NimModelRouter,
    parse_rate_limit_headers,
)
from .state import NimStateStore
from .stream import (
    StreamBreakError,
    StreamFailoverProxy,
    sse_stream_to_chunks,
)

logger = logging.getLogger("NIM.Orchestrator")

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def _load_env_list(var_name: str, default: Optional[List[str]] = None) -> List[str]:
    """Load a comma/semicolon-separated list from env."""
    raw = os.getenv(var_name, "")
    if not raw:
        return default or []
    parts = [p.strip().strip("'\" ") for p in raw.replace(";", ",").split(",") if p.strip()]
    return [p for p in parts if p]


def build_config_from_env() -> NimOrchestratorConfig:
    """Build NimOrchestratorConfig from environment variables (v1.1)."""
    api_keys = _load_env_list("NVIDIA_NGC_KEYS")
    if not api_keys:
        single_key = os.getenv("NVIDIA_NGC_KEY", "")
        if single_key:
            api_keys = [single_key]
        else:
            api_keys = ["nvapi-placeholder"]

    model_pool = _load_env_list("NVIDIA_NIM_POOL")

    cooldown_s = float(os.getenv("NIM_CIRCUIT_BREAKER_COOLDOWN_MS", "60000")) / 1000.0
    timeout_s = float(os.getenv("NIM_REQUEST_TIMEOUT_MS", "120000")) / 1000.0

    return NimOrchestratorConfig(
        base_url=os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        api_keys=api_keys,
        model_pool=model_pool,
        default_timeout=float(os.getenv("NIM_DEFAULT_TIMEOUT", str(timeout_s))),
        max_retries=int(os.getenv("NIM_MAX_RETRIES", "4")),
        max_stream_retries=int(os.getenv("NIM_MAX_STREAM_RETRIES", "2")),
        circuit_fail_threshold=int(os.getenv("NIM_CB_THRESHOLD", "3")),
        circuit_base_cooldown=float(os.getenv("NIM_CB_COOLDOWN_BASE", str(cooldown_s))),
        circuit_max_cooldown=float(os.getenv("NIM_CB_COOLDOWN_MAX", "300.0")),
        circuit_jitter_pct=float(os.getenv("NIM_CB_JITTER_PCT", "0.2")),
        circuit_half_open_timeout=float(os.getenv("NIM_CB_HALF_OPEN_TIMEOUT", "60.0")),
        probe_interval=float(os.getenv("NIM_PROBE_INTERVAL", "30.0")),
        rate_limit_remaining_warn=int(os.getenv("NIM_RL_WARN", "5")),
        preemptive_slowdown=float(os.getenv("NIM_PREEMPTIVE_SLOWDOWN", "5.0")),
    )


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

class NvidiaNimOrchestrator:
    """
    Autonomous NVIDIA NIM orchestrator with:
      - Adaptive model swapping via circuit breakers
      - API key pool rotation (Round-Robin / Least Connections)
      - Transparent stream-through failover
      - Singleton pattern for application-wide reuse
    """

    _instance: Optional["NvidiaNimOrchestrator"] = None
    _instance_lock = asyncio.Lock()

    def __init__(self, config: Optional[NimOrchestratorConfig] = None) -> None:
        self._config = config or build_config_from_env()
        self._state_store = NimStateStore()
        self._key_pool = create_key_pool_from_config(self._config)
        self._router = NimModelRouter(self._config, self._state_store)
        self._stream_proxy = StreamFailoverProxy(
            max_stream_retries=self._config.max_stream_retries,
        )
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()

    @classmethod
    async def get_instance(cls, config: Optional[NimOrchestratorConfig] = None) -> "NvidiaNimOrchestrator":
        """Get or create the singleton orchestrator instance."""
        async with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(config)
                await cls._instance._ensure_session()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Remove the cached singleton (useful for testing)."""
        cls._instance = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        async with self._session_lock:
            if self._session is None or self._session.closed:
                connector = aiohttp.TCPConnector(
                    limit=100,
                    limit_per_host=20,
                    ttl_dns_cache=300,
                )
                timeout = aiohttp.ClientTimeout(total=self._config.default_timeout)
                self._session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                )
            return self._session

    async def close(self) -> None:
        async with self._session_lock:
            if self._session and not self._session.closed:
                await self._session.close()
        NvidiaNimOrchestrator._instance = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def route_chat(
        self,
        messages: List[Dict[str, Any]],
        tier: str = "frontier",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Route a chat completion request through the model pool.

        Automatically handles:
          - Rate-limit detection (429)
          - Circuit breaker trips
          - Tier cascading on exhaustion
          - Model failover on failure

        Args:
            messages: OpenAI-format message list.
            tier: Starting tier ('frontier', 'strong', 'mid', 'lightweight', 'code').
            **kwargs: Additional OpenAI parameters (temperature, max_tokens, etc.).

        Returns:
            OpenAI-compatible chat completion response dict.

        Raises:
            RuntimeError: If all models across all tiers are exhausted.
        """
        stream = kwargs.pop("stream", False)
        if stream:
            raise ValueError(
                "route_chat does not support stream=True. "
                "Use route_chat_stream() instead."
            )

        session = await self._ensure_session()

        for attempt in range(self._config.max_retries + 1):
            model_id = await self._router.select_model(tier)
            if model_id is None:
                if attempt < self._config.max_retries:
                    wait = min(2 ** attempt * 2, 30)
                    logger.warning(f"No available models — retrying in {wait}s")
                    await asyncio.sleep(wait)
                    continue
                raise RuntimeError(
                    "All NVIDIA NIM models exhausted across all tiers"
                )

            api_key, key_idx = self._key_pool.acquire()
            try:
                result = await self._send_request(
                    session, model_id, api_key, messages, kwargs
                )

                await self._router.mark_success(model_id)
                self._key_pool.release(key_idx)
                return result

            except RateLimitError as e:
                self._key_pool.release(key_idx)
                self._key_pool.record_429(api_key)
                self._router.apply_rate_limit_headers(
                    model_id,
                    e.retry_after,
                    e.remaining,
                    e.reset_seconds,
                )
                await self._router.mark_failure(
                    model_id, f"429: retry_after={e.retry_after}"
                )
                logger.info(
                    f"[NIM] 429 on {model_id} → switching model "
                    f"(Retry-After={e.retry_after}s)"
                )

            except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as e:
                self._key_pool.release(key_idx)
                await self._router.mark_failure(model_id, str(e))
                logger.warning(f"[NIM] {type(e).__name__} on {model_id}: {e}")

        raise RuntimeError("Max retries exceeded for NIM chat request")

    async def route_chat_stream(
        self,
        messages: List[Dict[str, Any]],
        tier: str = "frontier",
        **kwargs,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Route a streaming chat completion request with transparent failover.

        Yields SSE-like dicts. On stream interruption, performs failover
        to next model and emits a synthetic "failover" event.

        Args:
            messages: OpenAI-format message list.
            tier: Starting tier.
            **kwargs: Additional OpenAI parameters.

        Yields:
            Dicts representing SSE chunks. Special keys:
              - "type": "failover" when failover occurs
              - "type": "error" on unrecoverable failure
        """
        session = await self._ensure_session()

        async def _stream_generator(model_id, msgs, **kw):
            api_key, key_idx = self._key_pool.acquire()
            try:
                kw_with_stream = dict(kw)
                kw_with_stream["stream"] = True
                async with session.post(
                    f"{self._config.base_url}/chat/completions",
                    json={
                        "model": model_id,
                        "messages": msgs,
                        **kw_with_stream,
                    },
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "Accept": "text/event-stream",
                    },
                ) as resp:
                    if resp.status == 429:
                        headers = dict(resp.headers)
                        ra, rem, rst = parse_rate_limit_headers(headers)
                        self._router.apply_rate_limit_headers(model_id, ra, rem, rst)
                        self._key_pool.release(key_idx)
                        self._key_pool.record_429(api_key)
                        await self._router.mark_failure(model_id, "429 stream")
                        raise StreamBreakError(
                            "429 rate limit", model_id, 429,
                            next_model=await self._router.select_model(tier),
                        )

                    if resp.status >= 500:
                        self._key_pool.release(key_idx)
                        await self._router.mark_failure(model_id, f"5xx: {resp.status}")
                        raise StreamBreakError(
                            f"Server error {resp.status}", model_id, resp.status,
                            next_model=await self._router.select_model(tier),
                        )

                    async for chunk in sse_stream_to_chunks(resp):
                        yield chunk

                self._key_pool.release(key_idx)
                await self._router.mark_success(model_id)

            except StreamBreakError:
                raise
            except Exception as e:
                self._key_pool.release(key_idx)
                await self._router.mark_failure(model_id, str(e))
                raise StreamBreakError(
                    str(e), model_id, 0,
                    next_model=await self._router.select_model(tier),
                )

        async for chunk in self._stream_proxy.proxy_stream(
            _stream_generator, "", messages, **kwargs
        ):
            yield chunk

    async def probe_all_models(self) -> Dict[str, bool]:
        """Health-check probe: send a minimal request to every model. Returns {model_id: healthy}."""
        session = await self._ensure_session()
        results: Dict[str, bool] = {}

        async def _probe_one(model_id: str) -> tuple:
            breaker = self._router._get_breaker(model_id)
            if not await breaker.allow_request():
                return model_id, False

            api_key, key_idx = self._key_pool.acquire()
            try:
                async with session.post(
                    f"{self._config.base_url}/chat/completions",
                    json={
                        "model": model_id,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                        "temperature": 0.0,
                    },
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                ) as resp:
                    if resp.status == 200:
                        await breaker.record_success()
                        return model_id, True
                    elif resp.status == 429:
                        headers = dict(resp.headers)
                        ra, rem, rst = parse_rate_limit_headers(headers)
                        self._router.apply_rate_limit_headers(model_id, ra, rem, rst)
                        self._key_pool.record_429(api_key)
                        await breaker.record_failure(f"429 probe")
                        return model_id, False
                    else:
                        await breaker.record_failure(f"{resp.status} probe")
                        return model_id, False
            except Exception as e:
                await breaker.record_failure(str(e))
                return model_id, False
            finally:
                self._key_pool.release(key_idx)

        tasks = [_probe_one(mid) for mid in self._config.model_list_flat]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        for item in gathered:
            if isinstance(item, tuple):
                mid, ok = item
                results[mid] = ok
            elif isinstance(item, Exception):
                logger.warning(f"Probe exception: {item}")
        return results

    async def status(self) -> Dict[str, Any]:
        """Return comprehensive orchestrator status."""
        return {
            "config": {
                "base_url": self._config.base_url,
                "key_count": self._key_pool.key_count,
                "model_count": len(self._config.model_list_flat),
                "timeout": self._config.default_timeout,
                "max_retries": self._config.max_retries,
            },
            "models": self._router.status(),
            "key_pool": self._key_pool.status(),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _send_request(
        self,
        session: aiohttp.ClientSession,
        model_id: str,
        api_key: str,
        messages: List[Dict[str, Any]],
        extra_kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        async with session.post(
            f"{self._config.base_url}/chat/completions",
            json={
                "model": model_id,
                "messages": messages,
                **extra_kwargs,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        ) as resp:
            headers = dict(resp.headers)
            body = await resp.json()

            if resp.status == 429:
                ra, rem, rst = parse_rate_limit_headers(headers)
                raise RateLimitError(
                    body.get("error", {}).get("message", "Rate limit exceeded"),
                    retry_after=ra,
                    remaining=rem,
                    reset_seconds=rst,
                )

            if resp.status >= 500:
                raise RuntimeError(
                    f"NIM server error {resp.status}: {body}"
                )

            if resp.status == 200:
                ra, rem, rst = parse_rate_limit_headers(headers)
                if rem is not None and rem < self._config.rate_limit_remaining_warn:
                    self._router.apply_rate_limit_headers(
                        model_id, None, rem, rst
                    )
                return body

            raise RuntimeError(f"NIM unexpected status {resp.status}: {body}")


class RateLimitError(Exception):
    """Raised when a NIM endpoint returns HTTP 429."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[float] = None,
        remaining: Optional[int] = None,
        reset_seconds: Optional[float] = None,
    ):
        super().__init__(message)
        self.retry_after = retry_after
        self.remaining = remaining
        self.reset_seconds = reset_seconds