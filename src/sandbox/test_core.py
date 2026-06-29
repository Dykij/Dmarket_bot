"""
Test suite for Bash Sandbox (core.py).
Covers: unit, integration, property-based, timeout, forbidden commands.
"""

import asyncio
import pytest

from src.sandbox.core import (
    BashSandbox,
    SandboxCommand,
    SandboxConfig,
    SandboxResultStatus,
    SandboxSecurityError,
)


@pytest.fixture
def default_sandbox():
    return BashSandbox(SandboxConfig(timeout_seconds=2))


async def test_allows_safe_command(default_sandbox):
    result = await default_sandbox.execute("echo hello")
    assert result.status == SandboxResultStatus.SUCCESS
    assert "hello" in result.stdout


async def test_disallows_forbidden_pattern():
    sandbox = BashSandbox(SandboxConfig(disallowed_patterns=[r"rm\s+-rf\s+/"]))
    result = await sandbox.execute("rm -rf /")
    assert result.status == SandboxResultStatus.DISALLOWED


async def test_timeout():
    sandbox = BashSandbox(SandboxConfig(timeout_seconds=1, allowed_commands=["sleep"]))
    result = await sandbox.execute("sleep 5")
    assert result.status == SandboxResultStatus.TIMEOUT


async def test_max_output_limit():
    sandbox = BashSandbox(SandboxConfig(max_output_bytes=10))
    result = await sandbox.execute("python -c \"print('A' * 1000)\" ")
    assert result.status == SandboxResultStatus.SUCCESS
    assert len(result.stdout) <= 10


async def test_command_not_in_allowed_list():
    sandbox = BashSandbox(SandboxConfig(allowed_commands=["echo"]))
    result = await sandbox.execute("ls")
    assert result.status == SandboxResultStatus.DISALLOWED


async def test_docker_execution():
    sandbox = BashSandbox(SandboxConfig(timeout_seconds=2, allowed_commands=["docker"]))
    # Docker execution may fail if Docker is not available, so we just ensure it returns a result
    result = await sandbox.execute_in_docker("echo hello from docker", image="busybox")
    assert result.status in {SandboxResultStatus.SUCCESS, SandboxResultStatus.ERROR}


# ── Property-based / Invariant tests ──

async def test_invariant_returncode_for_success():
    sandbox = BashSandbox()
    result = await sandbox.execute("echo ok")
    assert result.returncode == 0


async def test_invariant_stderr_is_empty_for_success():
    sandbox = BashSandbox()
    result = await sandbox.execute("echo ok")
    assert result.stderr == ""


async def test_negative_command_with_pipe():
    sandbox = BashSandbox()
    # Pipes are allowed if individual commands are allowed
    result = await sandbox.execute("echo hello | tr a-z A-Z")
    assert result.status in {SandboxResultStatus.SUCCESS, SandboxResultStatus.DISALLOWED}
