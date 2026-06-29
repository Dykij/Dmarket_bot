"""
Test suite for Workflow Chains (chains.py).
Covers: unit, integration, async, pipeline correctness.
"""

import asyncio
import pytest

from src.workflow.chains import (
    AgentRole,
    AgentTask,
    Conductor,
    TaskRegistry,
    TaskStatus,
    WorkflowBuilder,
    WorkItem,
)

pytestmark = pytest.mark.asyncio

# ── Fixtures ──

@pytest.fixture
async def conductor():
    c = Conductor()
    yield c
    await c.shutdown()


# ── Unit tests ──

async def test_task_registry_add_and_get():
    registry = TaskRegistry()
    task = AgentTask(id="t1", role=AgentRole.PARSER, payload={})
    registry.add(task)
    assert registry.get("t1") == task


async def test_task_registry_is_ready():
    registry = TaskRegistry()
    t1 = AgentTask(id="t1", role=AgentRole.PARSER, payload={}, status=TaskStatus.SUCCESS)
    t2 = AgentTask(id="t2", role=AgentRole.CODER, payload={}, depends_on=["t1"])
    registry.add(t1)
    registry.add(t2)
    assert registry.is_ready("t2") is True
    assert registry.is_ready("t1") is True  # No deps


async def test_task_registry_not_ready():
    registry = TaskRegistry()
    t1 = AgentTask(id="t1", role=AgentRole.PARSER, payload={}, status=TaskStatus.PENDING)
    t2 = AgentTask(id="t2", role=AgentRole.CODER, payload={}, depends_on=["t1"])
    registry.add(t1)
    registry.add(t2)
    assert registry.is_ready("t2") is False


async def test_task_registry_all_complete():
    registry = TaskRegistry()
    t1 = AgentTask(id="t1", role=AgentRole.PARSER, payload={}, status=TaskStatus.SUCCESS)
    t2 = AgentTask(id="t2", role=AgentRole.CODER, payload={}, status=TaskStatus.FAILURE)
    registry.add(t1)
    registry.add(t2)
    assert registry.all_complete() is True


# ── Async integration tests ──

async def test_conductor_single_task():
    results = []

    async def handler(payload):
        results.append(payload)
        return {"ok": True}

    conductor = Conductor()
    conductor.register_handler(AgentRole.PARSER, handler)
    task = AgentTask(id="t1", role=AgentRole.PARSER, payload={"x": 1})
    future = conductor.submit(task)
    await conductor.start()
    await asyncio.sleep(0.05)
    await conductor.shutdown()
    assert task.status == TaskStatus.SUCCESS
    assert task.result == {"ok": True}
    assert results[0] == {"x": 1}


async def test_conductor_pipeline():
    calls = []

    async def parser_handler(payload):
        calls.append("parser")
        return {"code": "print('hello')"}

    async def coder_handler(payload):
        calls.append("coder")
        return {"output": "hello"}

    async def tester_handler(payload):
        calls.append("tester")
        return {"passed": True}

    builder = WorkflowBuilder()
    builder.register_handler(AgentRole.PARSER, parser_handler)
    builder.register_handler(AgentRole.CODER, coder_handler)
    builder.register_handler(AgentRole.TESTER, tester_handler)

    parser_id = builder.add_step(AgentRole.PARSER, {"file": "main.py"})
    coder_id = builder.add_step(AgentRole.CODER, {"code_ref": "prev"}, depends_on=[parser_id])
    tester_id = builder.add_step(AgentRole.TESTER, {"code_ref": "prev"}, depends_on=[coder_id])

    tasks = await builder.run()
    assert len(tasks) == 3
    assert all(t.status == TaskStatus.SUCCESS for t in tasks)
    assert calls == ["parser", "coder", "tester"]


async def test_conductor_failure_handling():
    async def bad_handler(payload):
        raise ValueError("Intentional failure")

    conductor = Conductor()
    conductor.register_handler(AgentRole.PARSER, bad_handler)
    task = AgentTask(id="t1", role=AgentRole.PARSER, payload={})
    future = conductor.submit(task)
    await conductor.start()
    await asyncio.sleep(0.05)
    await conductor.shutdown()
    assert task.status == TaskStatus.FAILURE
    assert "Intentional failure" in str(task.error)


async def test_conductor_multiple_workers():
    results = []

    async def slow_handler(payload):
        await asyncio.sleep(0.01)
        results.append(payload["id"])
        return {}

    conductor = Conductor(max_workers_per_role={AgentRole.PARSER: 3})
    conductor.register_handler(AgentRole.PARSER, slow_handler)
    futures = []
    for i in range(5):
        task = AgentTask(id=f"t{i}", role=AgentRole.PARSER, payload={"id": i})
        futures.append(conductor.submit(task))
    await conductor.start()
    await asyncio.gather(*futures, return_exceptions=True)
    await conductor.shutdown()
    assert len(results) == 5
    assert set(results) == {0, 1, 2, 3, 4}


# ── Negative / Edge tests ──

async def test_conductor_unregistered_role():
    conductor = Conductor()
    task = AgentTask(id="t1", role=AgentRole.PARSER, payload={})
    with pytest.raises(ValueError, match="No handler registered for role"):
        conductor.submit(task)


async def test_workflow_builder_no_handler():
    builder = WorkflowBuilder()
    builder.add_step(AgentRole.PARSER, {})
    with pytest.raises(ValueError, match="No handler registered for role"):
        await builder.run()
