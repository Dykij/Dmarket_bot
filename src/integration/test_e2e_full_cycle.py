"""
E2E Test: Bug Detection → Workflow → Error → Rollback → Retry
"""

from pathlib import Path

import pytest

from src.integration.agent_facade import AgentFacade
from src.workflow.chains import AgentRole, TaskStatus


@pytest.fixture
def agent(tmp_path):
    return AgentFacade(repo_root=str(tmp_path), work_dir=str(tmp_path))


async def test_e2e_bug_detection_to_rollback(agent):
    """
    Full cycle E2E scenario:
    1. Detect bug (simulate by creating a file)
    2. Run workflow that modifies the file
    3. Force an error in the workflow
    4. Rollback to the snapshot
    5. Verify the file is restored
    6. Retry with a correct workflow
    """
    # Step 1: Initial state setup
    target_file = Path(agent.snapshot_manager.config.repo_root) / "buggy_feature.py"
    target_file.write_text("# Original code\ndef feature(): pass\n")

    # Step 2: Create snapshot before any changes
    snapshot = agent.create_snapshot("before_bug_fix")

    # Step 3: Run workflow with intentional error (simulating a bug)
    workflow = agent.start_workflow()

    async def buggy_handler(payload):
        # Simulate writing a buggy fix
        target_file.write_text("# Buggy code\ndef feature(): raise RuntimeError('bug')\n")
        raise RuntimeError("Intentional bug in workflow")

    async def good_handler(payload):
        target_file.write_text("# Fixed code\ndef feature(): return 'success'\n")
        return {"fixed": True}

    workflow.register_handler(AgentRole.PARSER, buggy_handler)
    workflow.add_step(AgentRole.PARSER, {"action": "fix_bug"})

    try:
        await agent.run_workflow()
        raise AssertionError("Workflow should have failed")
    except Exception:
        pass  # Expected failure

    # Step 4: Verify file is buggy after failed workflow
    assert "Buggy code" in target_file.read_text()

    # Step 5: Rollback to snapshot
    rollback_result = agent.rollback(snapshot.id)
    assert rollback_result is True

    # Step 6: Verify file is restored to original state
    restored_content = target_file.read_text()
    assert "Original code" in restored_content
    assert "Buggy code" not in restored_content

    # Step 7: Retry with corrected workflow
    workflow_retry = agent.start_workflow()
    workflow_retry.register_handler(AgentRole.PARSER, good_handler)
    workflow_retry.add_step(AgentRole.PARSER, {"action": "fix_bug_correctly"})

    results = await agent.run_workflow()
    assert all(r.status == TaskStatus.SUCCESS for r in results)

    # Step 8: Verify the fix was applied after successful retry
    assert "Fixed code" in target_file.read_text()
    assert "success" in target_file.read_text()

    # Step 9: Verify CoT log captures the full cycle
    cot_md = agent.get_cot_markdown()
    assert "Snapshot Created" in cot_md
    assert "Rollback" in cot_md
    assert "Workflow Started" in cot_md
