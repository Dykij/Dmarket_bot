"""
Test suite for the Agent Facade (integration layer).
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from src.integration.agent_facade import AgentFacade
from src.cot_audit.core import FormatStyle
from src.sandbox.core import BashSandbox, SandboxConfig


@pytest.fixture
def agent(tmp_path):
    return AgentFacade(repo_root=str(tmp_path), work_dir=str(tmp_path))


async def test_safe_bash_echo(agent):
    result = await agent.safe_bash("echo hello")
    assert result.status.value == "success"
    assert "hello" in result.stdout


async def test_safe_bash_timeout(agent):
    # Configure sandbox to allow 'sleep' command for this test
    from src.sandbox.core import SandboxConfig
    agent.sandbox = BashSandbox(SandboxConfig(timeout_seconds=1, allowed_commands=["sleep"]))
    result = await agent.safe_bash("sleep 5")
    assert result.status.value == "timeout"


async def test_safe_bash_forbidden_command(agent):
    result = await agent.safe_bash("rm -rf /")
    assert result.status.value == "disallowed"


async def test_cot_logging(agent):
    await agent.safe_bash("echo test")
    await agent.safe_bash("echo second")
    md = agent.get_cot_markdown()
    assert "# Chain-of-Thought Report" in md
    assert "Bash Execution" in md
    assert "test" in md


async def test_snapshot_and_rollback(agent):
    # Create a dummy file
    dummy = Path(agent.snapshot_manager.config.repo_root) / "test_file.txt"
    dummy.write_text("original")

    # Use the facade's snapshot mechanism
    manifest = agent.create_snapshot("integration_test")
    # Modify file
    dummy.write_text("modified")
    result = agent.rollback(manifest.id)
    assert result is True


async def test_workflow_integration(agent):
    workflow = agent.start_workflow()
    # Register a simple handler for the PARSER role
    calls = []

    async def handler(payload):
        calls.append(payload)
        return {"processed": True}

    from src.workflow.chains import AgentRole
    workflow.register_handler(AgentRole.PARSER, handler)
    workflow.add_step(AgentRole.PARSER, {"data": "test"})
    result = await agent.run_workflow()
    assert len(result) == 1
    assert result[0].status.value == "success"


async def test_execute_with_snapshot_success(agent):
    result = await agent.execute_with_snapshot("echo success")
    assert result.status.value == "success"
    assert "success" in result.stdout


async def test_execute_with_snapshot_failure_and_rollback(agent):
    # This command will fail, triggering rollback
    with pytest.raises(RuntimeError):
        await agent.execute_with_snapshot("rm -rf /")
