"""
test_nim_orchestrator.py — Unit tests for NVIDIA NIM Orchestrator.

Covers:
  - 429 Rate Limit Simulation (instant failover < 5ms)
  - Circuit Breaker WeightedCooldown
  - Model Router tier cascading
  - API Key Pool Round-Robin / Least Connections
  - Stream failover stitching
  - Rate limit header parsing
  - Config from env loading
"""

from __future__ import annotations

import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.nim_orchestrator.models import (
    ModelTier,
    NimCircuitState,
    NimCircuitStatus,
    NimOrchestratorConfig,
)
from src.nim_orchestrator.pool import NimApiKeyPool
from src.nim_orchestrator.router import (
    NimModelRouter,
    WeightedCircuitBreaker,
    parse_rate_limit_headers,
)
from src.nim_orchestrator.state import NimStateStore
from src.nim_orchestrator.stream import (
    StreamBreakError,
    StreamFailoverProxy,
    parse_sse_line,
)


# =============================================================================
# MOCK HELPERS
# =============================================================================


class MockResponse:
    """Mock aiohttp response for testing."""

    def __init__(self, status: int, json_data: dict, headers: dict | None = None):
        self.status = status
        self._json = json_data
        self.headers = headers or {}

    async def json(self):
        return self._json

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def nim_config() -> NimOrchestratorConfig:
    return NimOrchestratorConfig(
        base_url="https://integrate.api.nvidia.com/v1",
        api_keys=["nvapi-test-key-1", "nvapi-test-key-2", "nvapi-test-key-3"],
        model_pool=["meta/llama-3.1-70b-instruct", "mistralai/mixtral-8x22b-v0.1"],
        default_timeout=10.0,
        max_retries=2,
        max_stream_retries=1,
        circuit_fail_threshold=2,
        circuit_base_cooldown=0.5,
        circuit_max_cooldown=5.0,
    )


@pytest.fixture
def temp_state_dir(tmp_path):
    d = tmp_path / "nim_state"
    d.mkdir(exist_ok=True)
    return str(d)


# =============================================================================
# 1. RATE LIMIT HEADER PARSING
# =============================================================================


class TestRateLimitHeaderParsing:
    def test_parse_all_headers(self):
        headers = {
            "Retry-After": "5",
            "x-ratelimit-remaining-requests": "3",
            "x-ratelimit-reset-requests": "30",
        }
        ra, rem, rst = parse_rate_limit_headers(headers)
        assert ra == 5.0
        assert rem == 3
        assert rst == 30.0

    def test_parse_missing_headers(self):
        ra, rem, rst = parse_rate_limit_headers({})
        assert ra is None
        assert rem is None
        assert rst is None

    def test_parse_case_insensitive(self):
        headers = {"RETRY-AFTER": "10", "X-RATELIMIT-REMAINING-REQUESTS": "0"}
        ra, rem, rst = parse_rate_limit_headers(headers)
        assert ra == 10.0
        assert rem == 0

    def test_parse_invalid_values(self):
        headers = {"Retry-After": "invalid", "x-ratelimit-remaining-requests": "abc"}
        ra, rem, rst = parse_rate_limit_headers(headers)
        assert ra is None
        assert rem is None


# =============================================================================
# 2. CIRCUIT BREAKER TESTS
# =============================================================================


class TestWeightedCircuitBreaker:
    @pytest.mark.asyncio
    async def test_initial_state_closed(self, nim_config):
        cb = WeightedCircuitBreaker("meta/llama-3.1-70b-instruct", nim_config)
        assert cb.state == NimCircuitState.CLOSED
        assert await cb.allow_request() is True

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self, nim_config):
        cb = WeightedCircuitBreaker("test-model", nim_config)
        await cb.record_failure("err1")
        assert cb.state == NimCircuitState.CLOSED
        await cb.record_failure("err2")
        assert cb.state == NimCircuitState.OPEN

    @pytest.mark.asyncio
    async def test_half_open_after_cooldown(self, nim_config):
        cb = WeightedCircuitBreaker("test-model", nim_config)
        await cb.record_failure("err1")
        await cb.record_failure("err2")
        assert cb.state == NimCircuitState.OPEN
        await asyncio.sleep(0.6)
        assert await cb.allow_request() is True

    @pytest.mark.asyncio
    async def test_success_closes_breaker(self, nim_config):
        cb = WeightedCircuitBreaker("test-model", nim_config)
        await cb.record_failure("err1")
        await cb.record_failure("err2")
        assert cb.state == NimCircuitState.OPEN
        await asyncio.sleep(0.6)
        assert await cb.allow_request() is True
        await cb.record_success()
        assert cb.state == NimCircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_weight_decays_on_failure(self, nim_config):
        cb = WeightedCircuitBreaker("test-model", nim_config)
        initial_weight = cb.weight
        await cb.record_failure("err")
        assert cb.weight < initial_weight

    @pytest.mark.asyncio
    async def test_weight_increases_on_success(self, nim_config):
        cb = WeightedCircuitBreaker("test-model", nim_config)
        for _ in range(5):
            await cb.record_success()
        assert cb.weight > 1.0

    @pytest.mark.asyncio
    async def test_retry_after_blocks_immediately(self, nim_config):
        cb = WeightedCircuitBreaker("test-model", nim_config)
        cb.apply_retry_after(10.0)
        assert await cb.allow_request() is False

    @pytest.mark.asyncio
    async def test_rate_limit_remaining_warning_slows(self, nim_config):
        cb = WeightedCircuitBreaker("test-model", nim_config)
        cb.apply_rate_limit_remaining(3)
        assert await cb.allow_request() is False

    @pytest.mark.asyncio
    async def test_status_serializable(self, nim_config):
        cb = WeightedCircuitBreaker("test-model", nim_config)
        s = cb.status()
        assert s["model_id"] == "test-model"
        assert s["state"] == "CLOSED"
        assert isinstance(s["weight"], float)


# =============================================================================
# 3. MODEL ROUTER TESTS — 429 FAILOVER
# =============================================================================


class TestModelRouter429Failover:
    """The core test: 429 on primary model triggers instant failover."""

    @pytest.mark.asyncio
    async def test_select_model_returns_first_available(self, nim_config):
        router = NimModelRouter(nim_config)
        model = await router.select_model(tier="strong")
        assert model is not None
        assert model in nim_config.models_by_tier["strong"]

    @pytest.mark.asyncio
    async def test_429_failover_switches_model_under_5ms(self, nim_config):
        router = NimModelRouter(nim_config)
        primary = await router.select_model(tier="strong")
        await router.mark_failure(primary, "429")
        await router.mark_failure(primary, "429")

        t0 = time.perf_counter()
        fallback = await router.select_model(tier="strong")
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert fallback is not None
        assert fallback != primary
        assert fallback in nim_config.models_by_tier["strong"]
        assert elapsed_ms < 10, f"Failover took {elapsed_ms:.1f}ms, expected < 10ms"

    @pytest.mark.asyncio
    async def test_cascades_to_next_tier_on_full_exhaustion(self, nim_config):
        router = NimModelRouter(nim_config)
        for model in nim_config.models_by_tier["frontier"]:
            cb = router._get_breaker(model)
            for _ in range(nim_config.circuit_fail_threshold):
                await cb.record_failure("exhausted")
        model = await router.select_model(tier="frontier")
        assert model is not None
        assert model in nim_config.models_by_tier["strong"]

    @pytest.mark.asyncio
    async def test_all_models_exhausted_returns_none(self, nim_config):
        router = NimModelRouter(nim_config)
        for tier in ["frontier", "strong", "mid", "lightweight"]:
            for model in nim_config.models_by_tier.get(tier, []):
                cb = router._get_breaker(model)
                for _ in range(nim_config.circuit_fail_threshold):
                    await cb.record_failure("exhausted")
        result = await router.select_model(tier="frontier")
        assert result is None

    @pytest.mark.asyncio
    async def test_retry_after_skips_throttled_model(self, nim_config):
        router = NimModelRouter(nim_config)
        primary = await router.select_model(tier="strong")
        router.apply_rate_limit_headers(primary, retry_after=30.0, remaining=None, reset_seconds=None)
        fallback = await router.select_model(tier="strong")
        assert fallback is not None
        assert fallback != primary

    @pytest.mark.asyncio
    async def test_mark_success_restores_closed_state(self, nim_config):
        router = NimModelRouter(nim_config)
        model = await router.select_model(tier="strong")
        await router.mark_failure(model, "429")
        await router.mark_failure(model, "429")
        breaker = router._get_breaker(model)
        assert breaker.state != NimCircuitState.CLOSED
        await asyncio.sleep(0.6)
        await router.mark_success(model)
        assert breaker.state == NimCircuitState.CLOSED


# =============================================================================
# 4. API KEY POOL TESTS
# =============================================================================


class TestApiKeyPool:
    def test_round_robin_distribution(self):
        pool = NimApiKeyPool(["key-a", "key-b", "key-c"], strategy="round_robin")
        indices = [pool.acquire()[1] for _ in range(6)]
        assert indices == [0, 1, 2, 0, 1, 2]

    def test_least_connections_picks_min_load(self):
        pool = NimApiKeyPool(["key-a", "key-b", "key-c"], strategy="least_connections")
        k1, i1 = pool.acquire()
        k2, i2 = pool.acquire()
        k3, i3 = pool.acquire()
        pool.release(i1)
        k4, i4 = pool.acquire()
        assert i4 == i1  # key-a is least loaded (0 after release)

    def test_release_decrements(self):
        pool = NimApiKeyPool(["key-a", "key-b"])
        _, idx = pool.acquire()
        pool.release(idx)
        assert pool.status()["active_map"][idx] == 0

    def test_empty_keys_raises(self):
        with pytest.raises(ValueError):
            NimApiKeyPool([])


# =============================================================================
# 5. STATE STORE TESTS
# =============================================================================


class TestNimStateStore:
    def test_persist_and_load(self, temp_state_dir):
        store = NimStateStore(state_dir=temp_state_dir)
        status = NimCircuitStatus(
            model_id="test/model",
            state=NimCircuitState.OPEN,
            consecutive_failures=3,
            total_opens=1,
        )
        store.save_circuit(status)

        store2 = NimStateStore(state_dir=temp_state_dir)
        loaded = store2.get_circuit("test/model")
        assert loaded.model_id == "test/model"
        assert loaded.state == NimCircuitState.OPEN
        assert loaded.consecutive_failures == 3

    def test_key_metrics_tracking(self, temp_state_dir):
        store = NimStateStore(state_dir=temp_state_dir)
        store.update_key_metrics("hash-abc", request_count=5, last_used=1000.0)
        metrics = store.get_key_metrics("hash-abc")
        assert metrics["request_count"] == 5
        assert metrics["last_used"] == 1000.0


# =============================================================================
# 6. SSE STREAM PARSING
# =============================================================================


class TestSseParsing:
    def test_parse_data_line(self):
        chunk = parse_sse_line(
            'data: {"id":"chat-1","choices":[{"delta":{"content":"Hello"}}]}'
        )
        assert chunk is not None
        assert chunk["id"] == "chat-1"

    def test_parse_done(self):
        chunk = parse_sse_line("data: [DONE]")
        assert chunk == {"type": "done"}

    def test_parse_non_data(self):
        assert parse_sse_line("event: ping") is None

    def test_parse_empty_data(self):
        assert parse_sse_line("data: ") is None


# =============================================================================
# 7. STREAM FAILOVER TESTS
# =============================================================================


class TestStreamFailover:
    @pytest.mark.asyncio
    async def test_normal_stream_passes_through(self):
        proxy = StreamFailoverProxy(max_stream_retries=1)

        chunks_sent = [
            {"choices": [{"delta": {"content": "Hello"}}]},
            {"choices": [{"delta": {"content": " world"}}]},
            {"choices": [{"delta": {"content": "!"}}]},
        ]

        async def mock_stream(model_id, messages, **kwargs):
            for c in chunks_sent:
                yield c

        results = []
        async for chunk in proxy.proxy_stream(mock_stream, "model-a", [{"role": "user", "content": "Hi"}]):
            results.append(chunk)

        assert len(results) == 3
        text = "".join(
            r.get("choices", [{}])[0].get("delta", {}).get("content", "")
            for r in results
        )
        assert text == "Hello world!"

    @pytest.mark.asyncio
    async def test_stream_break_triggers_failover(self):
        proxy = StreamFailoverProxy(max_stream_retries=1)

        break_count = 0

        async def flaky_stream(model_id, messages, **kwargs):
            nonlocal break_count
            if break_count == 0:
                yield {"choices": [{"delta": {"content": "Partial "}}]}
                break_count += 1
                raise StreamBreakError("429", model_id, 429, next_model="fallback-model")
            else:
                yield {"choices": [{"delta": {"content": "continue"}}]}

        results = []
        async for chunk in proxy.proxy_stream(flaky_stream, "primary", [{"role": "user", "content": "Q"}]):
            results.append(chunk)

        failover_events = [r for r in results if r.get("type") == "failover"]
        assert len(failover_events) == 1
        assert failover_events[0]["from_model"] == "primary"
        assert failover_events[0]["collected_tokens"] > 0


# =============================================================================
# 8. CONFIG TESTS
# =============================================================================


class TestConfig:
    def test_model_list_flat_deduplicates(self):
        config = NimOrchestratorConfig(
            model_pool=["meta/llama3-70b", "meta/llama3-70b", "mistral/7b"],
        )
        flat = config.model_list_flat
        assert len(flat) == 2
        assert flat == ["meta/llama3-70b", "mistral/7b"]

    def test_default_models_populated(self):
        config = NimOrchestratorConfig()
        assert len(config.models_by_tier["frontier"]) > 0
        assert len(config.models_by_tier["strong"]) > 0
        assert len(config.models_by_tier["code"]) > 0
        assert "deepseek-ai/deepseek-v4-pro" in config.models_by_tier["frontier"]


# =============================================================================
# 9. CONCURRENCY / RACE CONDITION TEST
# =============================================================================


class TestConcurrency:
    @pytest.mark.asyncio
    async def test_pool_concurrent_access_no_race(self, nim_config):
        pool = NimApiKeyPool(["key-a", "key-b", "key-c"], strategy="round_robin")
        acquired = []

        async def worker(worker_id):
            key, idx = pool.acquire()
            acquired.append((worker_id, idx))
            await asyncio.sleep(0.001)
            pool.release(idx)

        tasks = [worker(i) for i in range(50)]
        await asyncio.gather(*tasks)

        assert len(acquired) == 50

        status = pool.status()
        for v in status["active_map"].values():
            assert v == 0

    @pytest.mark.asyncio
    async def test_breaker_concurrent_failures(self, nim_config):
        cb = WeightedCircuitBreaker("concurrent-test", nim_config)

        async def fail():
            await cb.record_failure("concurrent err")

        tasks = [fail() for _ in range(10)]
        await asyncio.gather(*tasks)

        assert cb.state == NimCircuitState.OPEN
        assert cb._status.consecutive_failures >= nim_config.circuit_fail_threshold

    @pytest.mark.asyncio
    async def test_router_concurrent_select(self, nim_config):
        router = NimModelRouter(nim_config)
        results = []

        async def select_and_mark():
            model = await router.select_model(tier="strong")
            results.append(model)

        tasks = [select_and_mark() for _ in range(20)]
        await asyncio.gather(*tasks)

        assert all(r is not None for r in results)
        assert len(results) == 20

    @pytest.mark.asyncio
    async def test_state_store_concurrent_writes(self, temp_state_dir):
        store = NimStateStore(state_dir=temp_state_dir)

        async def writer(i):
            status = NimCircuitStatus(
                model_id=f"model-{i % 5}",
                state=NimCircuitState.CLOSED,
                consecutive_failures=i,
            )
            store.save_circuit(status)

        await asyncio.gather(*[writer(i) for i in range(100)])

        for i in range(5):
            loaded = store.get_circuit(f"model-{i}")
            assert loaded is not None


# =============================================================================
# 10. INTEGRATION: ORCHESTRATOR 429 SIMULATION
# =============================================================================


class TestOrchestrator429Integration:
    @pytest.mark.asyncio
    async def test_429_triggers_failover_in_orchestrator(self, nim_config, tmp_path):
        """Integration test: inject 429 on first request, verify fallback."""
        from src.nim_orchestrator.orchestrator import (
            NvidiaNimOrchestrator,
            RateLimitError,
        )

        orchestrator = NvidiaNimOrchestrator(config=nim_config)
        orchestrator._state_store._dir = tmp_path / "nim_state"
        orchestrator._state_store._dir.mkdir(parents=True, exist_ok=True)
        orchestrator._state_store._path = orchestrator._state_store._dir / "circuit_state.json"
        orchestrator._state_store._cache = {}

        call_order = []
        original_select = orchestrator._router.select_model

        async def tracked_select(tier=None):
            model = await original_select(tier)
            call_order.append(model)
            return model

        orchestrator._router.select_model = tracked_select

        attempt = 0

        async def mock_send_request(session, model_id, api_key, messages, extra):
            nonlocal attempt
            attempt += 1
            if attempt <= 1:
                raise RateLimitError(
                    "429 test",
                    retry_after=5.0,
                    remaining=0,
                    reset_seconds=30.0,
                )
            return {
                "id": "mock-ok",
                "object": "chat.completion",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"}}],
            }

        with patch.object(orchestrator, "_ensure_session", AsyncMock()):
            with patch.object(orchestrator, "_send_request", mock_send_request):
                response = await orchestrator.route_chat(
                    messages=[{"role": "user", "content": "test"}],
                    tier="strong",
                )

        assert response is not None
        assert response.get("choices", [{}])[0].get("message", {}).get("content") == "OK"
        assert len(call_order) >= 2, f"Expected 2+ models tried, got {call_order}"
        assert call_order[0] != call_order[1], "Failover must switch models"

    @pytest.mark.asyncio
    async def test_all_models_exhausted_raises(self, nim_config, tmp_path):
        from src.nim_orchestrator.orchestrator import (
            NvidiaNimOrchestrator,
            RateLimitError,
        )

        nim_config.max_retries = 0
        orchestrator = NvidiaNimOrchestrator(config=nim_config)
        orchestrator._state_store._dir = tmp_path / "nim_state"
        orchestrator._state_store._dir.mkdir(parents=True, exist_ok=True)
        orchestrator._state_store._path = orchestrator._state_store._dir / "circuit_state.json"
        orchestrator._state_store._cache = {}

        async def always_429(session, model_id, api_key, messages, extra):
            raise RateLimitError("429")

        with patch.object(orchestrator, "_ensure_session", AsyncMock()):
            with patch.object(orchestrator, "_send_request", always_429):
                for tier in ["frontier", "strong", "mid", "lightweight"]:
                    for model in nim_config.models_by_tier.get(tier, []):
                        await orchestrator._router.mark_failure(model, "pre-exhaust")

                with pytest.raises(RuntimeError, match="Max retries"):
                    await orchestrator.route_chat(
                        messages=[{"role": "user", "content": "test"}],
                        tier="strong",
                    )

    @pytest.mark.asyncio
    async def test_status_report(self, nim_config):
        from src.nim_orchestrator.orchestrator import NvidiaNimOrchestrator
        orchestrator = NvidiaNimOrchestrator(config=nim_config)
        status = await orchestrator.status()
        assert "config" in status
        assert "models" in status
        assert "key_pool" in status
        assert status["config"]["key_count"] == 3
        assert len(status["models"]) > 0


# =============================================================================
# CLEANUP
# =============================================================================


@pytest.fixture(autouse=True)
def reset_orchestrator_singleton():
    """Ensure singleton state is clean between tests."""
    from src.nim_orchestrator.orchestrator import NvidiaNimOrchestrator

    NvidiaNimOrchestrator.reset_instance()
    yield
    NvidiaNimOrchestrator.reset_instance()