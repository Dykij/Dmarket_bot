"""
Tests for auto-retry with exponential backoff in execute_with_snapshot().
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.integration.agent_facade import AgentFacade, RetryConfig, RetryResult


@pytest.fixture
def agent(tmp_path):
    cfg = RetryConfig(max_retries=3, base_delay=0.1, max_delay=2.0, jitter=False)
    return AgentFacade(repo_root=str(tmp_path), work_dir=str(tmp_path), retry_config=cfg)


async def test_retry_succeeds_on_first_attempt(agent):
    """No retry needed if first attempt succeeds."""
    result = await agent.execute_with_snapshot("echo ok")
    assert result.status.value == "success"
    # Count COT entries — should not contain "Retry" or "Backoff"
    log_text = agent.get_cot_markdown()
    assert "Retry Success" not in log_text
    assert "Backoff Wait" not in log_text


async def test_retry_succeeds_after_failures(agent):
    """Simulate: fail twice, succeed on third attempt."""
    call_count = 0
    original_execute = agent.sandbox.execute

    async def mock_execute(cmd):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            from src.sandbox.core import SandboxResult, SandboxResultStatus
            return SandboxResult(status=SandboxResultStatus.ERROR, stderr=f"fail #{call_count}")
        return await original_execute(cmd)

    agent.sandbox.execute = mock_execute
    result = await agent.execute_with_snapshot("echo ok")
    assert result.status.value == "success"
    assert call_count == 3

    log_text = agent.get_cot_markdown()
    assert "Retry Success" in log_text
    assert "Backoff Wait" in log_text


async def test_retry_exhausted_raises(agent):
    """All retries fail — should raise the last exception."""
    from src.sandbox.core import SandboxResult, SandboxResultStatus

    async def always_fail(cmd):
        return SandboxResult(status=SandboxResultStatus.ERROR, stderr="permanent failure")

    agent.sandbox.execute = always_fail
    with pytest.raises(RuntimeError, match="permanent failure"):
        await agent.execute_with_snapshot("echo fail")

    log_text = agent.get_cot_markdown()
    assert "All Retries Exhausted" in log_text


async def test_exponential_backoff_timing(agent):
    """Verify delays grow exponentially: ~0.1s, ~0.2s, ~0.4s (jitter=False)."""
    from src.sandbox.core import SandboxResult, SandboxResultStatus

    call_times = []

    async def track_fail(cmd):
        call_times.append(time.monotonic())
        return SandboxResult(status=SandboxResultStatus.ERROR, stderr="fail")

    agent.sandbox.execute = track_fail
    start = time.monotonic()
    with pytest.raises(RuntimeError):
        await agent.execute_with_snapshot("echo fail", max_retries=3)
    elapsed = time.monotonic() - start

    # With base_delay=0.1, jitter=False: delays are 0.1, 0.2, 0.4 = 0.7s total
    assert elapsed >= 0.6, f"Expected >= 0.6s total delay, got {elapsed:.3f}s"
    assert elapsed < 1.5, f"Expected < 1.5s total delay, got {elapsed:.3f}s"

    # Verify intervals between attempts
    assert len(call_times) == 4  # 1 initial + 3 retries
    d1 = call_times[1] - call_times[0]
    d2 = call_times[2] - call_times[1]
    d3 = call_times[3] - call_times[2]

    # Each delay should be roughly 2x the previous
    assert 0.08 < d1 < 0.15, f"First delay {d1:.3f}s"
    assert 0.15 < d2 < 0.30, f"Second delay {d2:.3f}s"
    assert 0.30 < d3 < 0.60, f"Third delay {d3:.3f}s"


async def test_retry_callback_called(agent):
    """on_retry callback is invoked for each retry attempt."""
    from src.sandbox.core import SandboxResult, SandboxResultStatus

    retry_log = []

    def on_retry(attempt, delay, error):
        retry_log.append({"attempt": attempt, "delay": delay, "error": str(error)})

    async def always_fail(cmd):
        return SandboxResult(status=SandboxResultStatus.ERROR, stderr="fail")

    agent.sandbox.execute = always_fail
    with pytest.raises(RuntimeError):
        await agent.execute_with_snapshot("echo fail", max_retries=2, on_retry=on_retry)

    assert len(retry_log) == 2
    assert retry_log[0]["attempt"] == 1
    assert retry_log[1]["attempt"] == 2
    # Delays should grow: 0.1 -> 0.2 (with jitter=False)
    assert retry_log[1]["delay"] > retry_log[0]["delay"]


async def test_rollback_before_each_retry(agent):
    """Verify rollback is called before each retry attempt."""
    from src.sandbox.core import SandboxResult, SandboxResultStatus

    rollback_calls = []
    original_rollback = agent.snapshot_manager.rollback

    def mock_rollback(snapshot_id):
        rollback_calls.append(snapshot_id)
        return original_rollback(snapshot_id)

    agent.snapshot_manager.rollback = mock_rollback

    async def always_fail(cmd):
        return SandboxResult(status=SandboxResultStatus.ERROR, stderr="fail")

    agent.sandbox.execute = always_fail
    with pytest.raises(RuntimeError):
        await agent.execute_with_snapshot("echo fail", max_retries=2)

    # Rollback called for each failed attempt (3 total = 1 initial + 2 retries)
    assert len(rollback_calls) == 3
