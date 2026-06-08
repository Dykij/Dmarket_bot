"""
Unit tests for src.utils.health_server (v12.7).

Coverage:
- HealthState: all setters + snapshot + is_ready
- HTTP handlers: /healthz, /readyz, /metrics
  (200 happy path, 503 shutdown, 503 not-ready, 503 metrics available)
- Prometheus exposition format: valid syntax, all expected metrics
- Lifecycle: start_health_server returns runner when port is free,
  returns None when port is busy, returns None when HEALTH_PORT not set
- Stop is idempotent (None runner is OK)

No real network. All tests use aiohttp's test_utils.TestClient.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Skip the whole module if aiohttp is not available
pytest.importorskip("aiohttp")

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.utils import health_server  # noqa: E402
from src.utils.health_server import (  # noqa: E402
    HealthState,
    _handle_healthz,
    _handle_metrics,
    _handle_readyz,
    health_state,
    is_enabled,
    start_health_server,
    stop_health_server,
)


# =====================================================================
# TestHealthState
# =====================================================================

class TestHealthState:
    def test_initial_snapshot(self) -> None:
        s = HealthState()
        snap = s.snapshot()
        assert snap["status"] == "ok"
        assert snap["uptime_s"] >= 0
        assert snap["process"]["cycle_count"] == 0
        assert snap["process"]["last_cycle_ts"] == 0.0
        assert snap["process"]["seconds_since_last_cycle"] is None
        assert snap["equity"]["current_usd"] == 0.0
        assert snap["equity"]["drawdown_pct"] == 0.0
        assert snap["halts"]["soft_halt_active"] is False
        assert snap["halts"]["daily_halt_active"] is False
        assert snap["pump_detector"]["active_blacklist_size"] == 0

    def test_mark_cycle_updates_state(self) -> None:
        s = HealthState()
        s.mark_cycle(equity_usd=50.0, peak_equity_usd=60.0, drawdown_pct=16.67)
        snap = s.snapshot()
        assert snap["process"]["cycle_count"] == 1
        assert snap["process"]["last_cycle_ts"] > 0
        assert snap["process"]["seconds_since_last_cycle"] is not None
        assert snap["process"]["seconds_since_last_cycle"] >= 0
        assert snap["equity"]["current_usd"] == 50.0
        assert snap["equity"]["peak_usd"] == 60.0
        assert snap["equity"]["drawdown_pct"] == 16.67

    def test_set_daily_stats(self) -> None:
        s = HealthState()
        s.set_daily_stats(pnl_usd=-5.0, trade_count=10)
        snap = s.snapshot()
        assert snap["daily"]["pnl_usd"] == -5.0
        assert snap["daily"]["trade_count"] == 10

    def test_set_halts(self) -> None:
        s = HealthState()
        s.set_halts(soft_halt=True, daily_halt=False)
        snap = s.snapshot()
        assert snap["halts"]["soft_halt_active"] is True
        assert snap["halts"]["daily_halt_active"] is False
        s.set_halts(soft_halt=False, daily_halt=True)
        snap = s.snapshot()
        assert snap["halts"]["soft_halt_active"] is False
        assert snap["halts"]["daily_halt_active"] is True

    def test_set_pump_stats(self) -> None:
        s = HealthState()
        s.set_pump_stats(blacklist_size=3, total_detections=7)
        snap = s.snapshot()
        assert snap["pump_detector"]["active_blacklist_size"] == 3
        assert snap["pump_detector"]["total_detections"] == 7

    def test_set_cs2cap_quota(self) -> None:
        s = HealthState()
        s.set_cs2cap_quota_pct(45.5)
        assert s.snapshot()["cs2cap"]["monthly_quota_used_pct"] == 45.5
        s.set_cs2cap_quota_pct(None)
        assert s.snapshot()["cs2cap"]["monthly_quota_used_pct"] is None

    def test_record_error(self) -> None:
        s = HealthState()
        s.record_error("Test error")
        assert s.snapshot()["last_error"] == "Test error"

    def test_record_error_truncates_long_strings(self) -> None:
        s = HealthState()
        s.record_error("x" * 1000)
        snap = s.snapshot()
        assert snap["last_error"] is not None
        assert len(snap["last_error"]) <= 500

    def test_set_shutting_down(self) -> None:
        s = HealthState()
        assert s.snapshot()["status"] == "ok"
        s.set_shutting_down(True)
        assert s.snapshot()["status"] == "shutting_down"

    def test_is_ready_default(self) -> None:
        s = HealthState()
        assert s.is_ready() is True

    def test_is_ready_false_when_shutting_down(self) -> None:
        s = HealthState()
        s.set_shutting_down(True)
        assert s.is_ready() is False

    def test_is_ready_false_when_daily_halt(self) -> None:
        s = HealthState()
        s.set_halts(soft_halt=False, daily_halt=True)
        assert s.is_ready() is False

    def test_is_ready_true_under_soft_halt(self) -> None:
        """Soft halt allows trading at half size → still ready."""
        s = HealthState()
        s.set_halts(soft_halt=True, daily_halt=False)
        assert s.is_ready() is True

    def test_mark_cycle_increments_counter(self) -> None:
        s = HealthState()
        for _ in range(5):
            s.mark_cycle(50.0, 60.0, 16.0)
        assert s.snapshot()["process"]["cycle_count"] == 5


# =====================================================================
# TestHttpHandlers (using aiohttp test client)
# =====================================================================

@pytest.fixture
def fresh_health_state() -> HealthState:
    """Reset the module-level health_state before each test."""
    s = HealthState()
    s.set_shutting_down(False)
    s.set_halts(soft_halt=False, daily_halt=False)
    s.set_daily_stats(pnl_usd=0.0, trade_count=0)
    s.set_pump_stats(blacklist_size=0, total_detections=0)
    s.set_cs2cap_quota_pct(None)
    s.record_error("")
    return s


@pytest.fixture
async def http_client(fresh_health_state: HealthState):
    """Build a minimal aiohttp app with the 3 handlers, return TestClient."""
    # Monkey-patch the module singleton so the handlers see fresh state
    original_state = health_server.health_state
    health_server.health_state = fresh_health_state
    try:
        app = web.Application()
        app.router.add_get("/healthz", _handle_healthz)
        app.router.add_get("/readyz", _handle_readyz)
        app.router.add_get("/metrics", _handle_metrics)
        async with TestClient(TestServer(app)) as client:
            yield client
    finally:
        health_server.health_state = original_state


@pytest.mark.asyncio
async def test_healthz_returns_200_happy_path(http_client: TestClient) -> None:
    resp = await http_client.get("/healthz")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ok"
    assert "uptime_s" in data
    assert "equity" in data
    assert "halts" in data
    assert "pump_detector" in data


@pytest.mark.asyncio
async def test_healthz_returns_503_when_shutting_down(
    http_client: TestClient, fresh_health_state: HealthState
) -> None:
    fresh_health_state.set_shutting_down(True)
    resp = await http_client.get("/healthz")
    assert resp.status == 503
    data = await resp.json()
    assert data["status"] == "shutting_down"


@pytest.mark.asyncio
async def test_readyz_returns_200_when_ready(
    http_client: TestClient, fresh_health_state: HealthState
) -> None:
    fresh_health_state.mark_cycle(50.0, 60.0, 0.0)
    resp = await http_client.get("/readyz")
    assert resp.status == 200
    data = await resp.json()
    assert data["ready"] is True


@pytest.mark.asyncio
async def test_readyz_returns_503_when_daily_halt(
    http_client: TestClient, fresh_health_state: HealthState
) -> None:
    fresh_health_state.set_halts(soft_halt=False, daily_halt=True)
    resp = await http_client.get("/readyz")
    assert resp.status == 503
    data = await resp.json()
    assert data["ready"] is False


@pytest.mark.asyncio
async def test_readyz_returns_503_when_shutting_down(
    http_client: TestClient, fresh_health_state: HealthState
) -> None:
    fresh_health_state.set_shutting_down(True)
    resp = await http_client.get("/readyz")
    assert resp.status == 503


@pytest.mark.asyncio
async def test_metrics_returns_prometheus_format(
    http_client: TestClient, fresh_health_state: HealthState
) -> None:
    fresh_health_state.mark_cycle(50.0, 60.0, 5.0)
    fresh_health_state.set_pump_stats(blacklist_size=2, total_detections=5)
    fresh_health_state.set_cs2cap_quota_pct(42.5)

    resp = await http_client.get("/metrics")
    assert resp.status == 200
    assert "text/plain" in resp.content_type
    text = await resp.text()

    # Spot-check key metrics
    assert "bot_uptime_seconds" in text
    assert "bot_cycle_count_total" in text
    assert "bot_equity_usd 50.0" in text
    assert "bot_equity_peak_usd 60.0" in text
    assert "bot_equity_drawdown_pct 5.0" in text
    assert "bot_pump_blacklist_size 2" in text
    assert "bot_pump_total_detections_total 5" in text
    assert "bot_cs2cap_quota_used_pct 42.5" in text

    # Every metric line should end with a number (Prometheus format)
    for line in text.split("\n"):
        if line.startswith("#") or not line.strip():
            continue
        # Should be `name value` or `name{labels} value`
        parts = line.split()
        assert len(parts) >= 2, f"Malformed metric line: {line!r}"
        # Last token must parse as a number
        try:
            float(parts[-1])
        except ValueError:
            pytest.fail(f"Metric value not numeric: {line!r}")


@pytest.mark.asyncio
async def test_metrics_omits_quota_when_none(
    http_client: TestClient, fresh_health_state: HealthState
) -> None:
    fresh_health_state.set_cs2cap_quota_pct(None)
    resp = await http_client.get("/metrics")
    text = await resp.text()
    assert "bot_cs2cap_quota_used_pct" not in text


# =====================================================================
# TestServerLifecycle
# =====================================================================

class TestServerLifecycle:
    def test_is_enabled_default_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HEALTH_PORT", raising=False)
        assert is_enabled() is False

    def test_is_enabled_when_port_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HEALTH_PORT", "9090")
        assert is_enabled() is True

    def test_is_enabled_zero_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HEALTH_PORT", "0")
        assert is_enabled() is False

    @pytest.mark.asyncio
    async def test_start_returns_none_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("HEALTH_PORT", raising=False)
        result = await start_health_server()
        assert result is None

    @pytest.mark.asyncio
    async def test_start_binds_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Find a free port to bind to
        import socket
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        free_port = sock.getsockname()[1]
        sock.close()

        monkeypatch.setenv("HEALTH_PORT", str(free_port))
        monkeypatch.setenv("HEALTH_HOST", "127.0.0.1")
        runner = await start_health_server()
        try:
            assert runner is not None
            # Sanity-check: actually reachable
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{free_port}/healthz") as r:
                    assert r.status == 200
                    data = await r.json()
                    assert data["status"] == "ok"
        finally:
            await stop_health_server(runner)

    @pytest.mark.asyncio
    async def test_start_returns_none_when_port_busy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If the port is already in use, start_health_server returns None
        and the bot continues without health server (degraded but trading
        is not affected)."""
        import socket
        # Block a port
        blocker = socket.socket()
        blocker.bind(("127.0.0.1", 0))
        busy_port = blocker.getsockname()[1]
        # Don't close the socket — that would free the port

        monkeypatch.setenv("HEALTH_PORT", str(busy_port))
        runner = await start_health_server()
        try:
            assert runner is None  # must give up gracefully
        finally:
            blocker.close()

    @pytest.mark.asyncio
    async def test_stop_with_none_is_noop(self) -> None:
        """stop_health_server(None) must not crash."""
        await stop_health_server(None)  # should be silent no-op


# =====================================================================
# TestGlobalSingleton
# =====================================================================

class TestGlobalSingleton:
    def test_module_level_singleton_exists(self) -> None:
        """The `health_state` module-level singleton must be a HealthState."""
        assert isinstance(health_state, HealthState)

    def test_singleton_persists_across_imports(self) -> None:
        """Re-importing the module must return the same instance."""
        from src.utils import health_server as hs2
        assert hs2.health_state is health_state
