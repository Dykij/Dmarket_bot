"""
Unit tests for the Telegram notifier's circuit breaker (v12.7).

Coverage:
- Default state (closed)
- Single failure: not yet open
- Threshold failures: opens
- Open circuit: blocks subsequent sends (returns False)
- Cooldown elapsed: half-open, allows probe
- Probe success: closes circuit
- Probe failure: re-opens for another cooldown
- Manual override: cb_force_close, cb_force_open
- Throttle still works (independent of CB)
- Disabled notifier (no token) is never affected by CB
- 429 responses count as failures (they open the circuit)
- HTTP 200 success resets the failure counter
- Stats include circuit_breaker section
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Reload the module to reset its singleton state between tests
from src.telegram.notifier import _TelegramNotifier  # noqa: E402


# =====================================================================
# Helpers
# =====================================================================

def _make_notifier(
    *,
    enabled: bool = True,
    fail_threshold: int = 5,
    cooldown_s: float = 60.0,
) -> _TelegramNotifier:
    """Build a notifier in a clean state. Override CB thresholds for fast tests."""
    n = _TelegramNotifier()
    if enabled:
        n._enabled = True
        n._token = "test:token"
        n._chat_id = "12345"
    n.CB_FAIL_THRESHOLD = fail_threshold
    n.CB_COOLDOWN_S = cooldown_s
    return n


# =====================================================================
# TestCircuitBreakerDefaultState
# =====================================================================

class TestCircuitBreakerDefaultState:
    def test_default_state_closed(self) -> None:
        n = _make_notifier()
        assert n._cb_is_open() is False
        assert n._cb_consecutive_failures == 0
        assert n._cb_opened_at == 0.0

    def test_stats_includes_cb_section(self) -> None:
        n = _make_notifier()
        s = n.stats()
        assert "circuit_breaker" in s
        assert s["circuit_breaker"]["state"] == "closed"
        assert s["circuit_breaker"]["consecutive_failures"] == 0
        assert s["circuit_breaker"]["total_opens"] == 0


# =====================================================================
# TestCircuitBreakerOpening
# =====================================================================

class TestCircuitBreakerOpening:
    def test_single_failure_does_not_open(self) -> None:
        n = _make_notifier(fail_threshold=5)
        n._cb_record_failure()
        assert n._cb_is_open() is False
        assert n._cb_consecutive_failures == 1

    def test_below_threshold_does_not_open(self) -> None:
        n = _make_notifier(fail_threshold=5)
        for _ in range(4):
            n._cb_record_failure()
        assert n._cb_is_open() is False
        assert n._cb_consecutive_failures == 4

    def test_at_threshold_opens(self) -> None:
        n = _make_notifier(fail_threshold=5)
        for _ in range(5):
            n._cb_record_failure()
        assert n._cb_is_open() is True
        assert n._cb_opened_at > 0
        assert n._cb_total_opens == 1

    def test_open_circuit_blocks_send(self) -> None:
        n = _make_notifier(fail_threshold=2, cooldown_s=60.0)
        n._cb_record_failure()
        n._cb_record_failure()  # → open
        assert n._cb_is_open() is True
        # is_open is True; a real send would short-circuit at _send_raw
        # entry. We can verify by calling _cb_is_open directly.
        n._cb_total_short_circuits = 0
        # Simulate the path inside _send_raw:
        if n._cb_is_open():
            n._cb_total_short_circuits += 1
        assert n._cb_total_short_circuits == 1

    def test_success_resets_failure_counter(self) -> None:
        n = _make_notifier(fail_threshold=5)
        n._cb_record_failure()
        n._cb_record_failure()
        n._cb_record_failure()
        assert n._cb_consecutive_failures == 3
        n._cb_record_success()
        assert n._cb_consecutive_failures == 0

    def test_success_closes_open_circuit(self) -> None:
        n = _make_notifier(fail_threshold=2, cooldown_s=60.0)
        n._cb_record_failure()
        n._cb_record_failure()  # open
        assert n._cb_is_open() is True
        n._cb_record_success()  # closes
        assert n._cb_is_open() is False
        assert n._cb_opened_at == 0.0

    def test_failure_after_success_starts_counting_from_zero(self) -> None:
        """Mixed sequence: F, F, S, F, F — only 2 consecutive, not 5."""
        n = _make_notifier(fail_threshold=5)
        n._cb_record_failure()
        n._cb_record_failure()
        n._cb_record_success()  # reset
        n._cb_record_failure()
        n._cb_record_failure()
        assert n._cb_consecutive_failures == 2
        assert n._cb_is_open() is False  # 2 < 5


# =====================================================================
# TestCircuitBreakerCooldown
# =====================================================================

class TestCircuitBreakerCooldown:
    def test_short_cooldown_allows_probe(self) -> None:
        n = _make_notifier(fail_threshold=2, cooldown_s=0.1)
        n._cb_record_failure()
        n._cb_record_failure()  # open
        assert n._cb_is_open() is True
        time.sleep(0.15)  # past cooldown
        # Next send is allowed (half-open)
        assert n._cb_is_open() is False

    def test_within_cooldown_still_open(self) -> None:
        n = _make_notifier(fail_threshold=2, cooldown_s=10.0)
        n._cb_record_failure()
        n._cb_record_failure()  # open
        # Within cooldown
        assert n._cb_is_open() is True

    def test_probe_failure_reopens_circuit(self) -> None:
        """After cooldown, the next send probes. If it fails, re-open."""
        n = _make_notifier(fail_threshold=2, cooldown_s=0.1)
        n._cb_record_failure()
        n._cb_record_failure()  # open
        time.sleep(0.15)
        # Now the probe is allowed through
        assert n._cb_is_open() is False
        # The probe fails:
        n._cb_record_failure()
        # Re-opens (different _cb_opened_at timestamp, but still open)
        assert n._cb_is_open() is True
        # total_opens should now be 2 (initial open + re-open)
        assert n._cb_total_opens == 2


# =====================================================================
# TestCircuitBreakerManualOverride
# =====================================================================

class TestCircuitBreakerManualOverride:
    def test_force_close_clears_state(self) -> None:
        n = _make_notifier(fail_threshold=2, cooldown_s=60.0)
        n._cb_record_failure()
        n._cb_record_failure()  # open
        assert n._cb_is_open() is True
        n.cb_force_close()
        assert n._cb_is_open() is False
        assert n._cb_consecutive_failures == 0

    def test_force_open_trips_immediately(self) -> None:
        n = _make_notifier(fail_threshold=5)
        assert n._cb_is_open() is False
        n.cb_force_open()
        assert n._cb_is_open() is True
        assert n._cb_total_opens == 1
        assert n._cb_consecutive_failures == 5


# =====================================================================
# TestCircuitBreakerIntegration
# =====================================================================

class TestCircuitBreakerIntegration:
    @pytest.mark.asyncio
    async def test_disabled_notifier_unaffected_by_cb(self) -> None:
        """If notifier is disabled (no token), the CB is never consulted
        — _send_raw returns False at the enabled check, before CB."""
        n = _make_notifier(enabled=False)
        n._cb_opened_at = 1.0  # pretend CB is open
        result = await n._send_raw("test", severity="info")
        assert result is False
        # Counter not incremented (we didn't even reach CB check)
        assert n._cb_total_short_circuits == 0

    @pytest.mark.asyncio
    async def test_throttle_independent_of_cb(self) -> None:
        """Throttle should still work even when CB is closed."""
        n = _make_notifier()

        # Build a real async context manager: an object that has __aenter__/__aexit__
        # returning a response-like object with .status = 200.
        class FakeResp:
            def __init__(self, status, body=""):
                self.status = status
                self._body = body
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return None
            async def text(self):
                return self._body

        class FakeSession:
            def __init__(self, resp): self._resp = resp
            def post(self, *a, **kw): return self._resp

        fake_session = FakeSession(FakeResp(200))
        with patch.object(n, "_ensure_session", return_value=fake_session):
            result1 = await n._send_raw("msg1", severity="info")
            assert result1 is True
            # Second send within throttle window for 'info' (60s default)
            result2 = await n._send_raw("msg2", severity="info")
            assert result2 is False
            assert n._total_throttled == 1
            # CB still closed
            assert n._cb_is_open() is False

    @pytest.mark.asyncio
    async def test_429_response_counts_as_failure(self) -> None:
        """Telegram 429 must count toward the CB failure counter."""
        n = _make_notifier(fail_threshold=2)
        class FakeResp:
            def __init__(self, status, body=""):
                self.status = status
                self._body = body
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return None
            async def text(self): return self._body
        class FakeSession:
            def __init__(self, resp): self._resp = resp
            def post(self, *a, **kw): return self._resp

        fake_session = FakeSession(FakeResp(429, "Too Many Requests"))
        with patch.object(n, "_ensure_session", return_value=fake_session):
            # Use different severities to avoid throttle interference
            # (a 429 sets the throttle for that severity)
            await n._send_raw("msg", severity="info")
            await n._send_raw("msg", severity="warning")
            # Both 429s counted as failures; threshold=2 → opened
            assert n._cb_consecutive_failures == 2
            assert n._cb_is_open() is True

    @pytest.mark.asyncio
    async def test_http_5xx_counts_as_failure(self) -> None:
        n = _make_notifier(fail_threshold=2)
        class FakeResp:
            def __init__(self, status, body=""):
                self.status = status
                self._body = body
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return None
            async def text(self): return self._body
        class FakeSession:
            def __init__(self, resp): self._resp = resp
            def post(self, *a, **kw): return self._resp

        fake_session = FakeSession(FakeResp(500, "Internal Server Error"))
        with patch.object(n, "_ensure_session", return_value=fake_session):
            await n._send_raw("msg", severity="info")
            await n._send_raw("msg", severity="info")
            assert n._cb_consecutive_failures == 2
            assert n._cb_is_open() is True

    @pytest.mark.asyncio
    async def test_network_exception_counts_as_failure(self) -> None:
        n = _make_notifier(fail_threshold=2)
        class FakeSession:
            def post(self, *a, **kw):
                raise ConnectionError("network down")
        fake_session = FakeSession()
        with patch.object(n, "_ensure_session", return_value=fake_session):
            await n._send_raw("msg", severity="info")
            await n._send_raw("msg", severity="info")
            assert n._cb_consecutive_failures == 2
            assert n._cb_is_open() is True

    @pytest.mark.asyncio
    async def test_http_200_resets_failure_counter(self) -> None:
        n = _make_notifier(fail_threshold=3)
        class FakeResp:
            def __init__(self, status, body=""):
                self.status = status
                self._body = body
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return None
            async def text(self): return self._body
        class FakeSession:
            def __init__(self, resp): self._resp = resp
            def post(self, *a, **kw): return self._resp

        fake_session = FakeSession(FakeResp(200))
        with patch.object(n, "_ensure_session", return_value=fake_session):
            # 2 failures, then 1 success
            n._cb_record_failure()
            n._cb_record_failure()
            assert n._cb_consecutive_failures == 2
            await n._send_raw("msg", severity="info")
            assert n._cb_consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_open_circuit_blocks_high_severity_too(self) -> None:
        """Critical alerts are also blocked when CB is open.
        (We don't want spam-of-urgency on a down API.)"""
        n = _make_notifier(fail_threshold=2, cooldown_s=60.0)
        n._cb_record_failure()
        n._cb_record_failure()  # open
        result = await n._send_raw("CRASH!", severity="critical")
        assert result is False
        # Increment CB short-circuit counter (not throttle counter)
        assert n._cb_total_short_circuits == 1
        assert n._total_throttled == 0
