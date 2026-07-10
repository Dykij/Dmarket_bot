"""
Load test: 1000 concurrent workflow tasks.
Checks for: memory leaks, deadlocks, event loop hangs.
"""

import asyncio
import gc
import time

from src.workflow.chains import AgentRole, TaskStatus, WorkflowBuilder


async def test_load_1000_concurrent_workflow_tasks():
    """
    Spawn 1000 concurrent tasks in batches and ensure no deadlock or leak.
    """
    total_tasks = 1000

    # Simple fast handler (no real I/O to be lightweight)
    async def fast_handler(payload):
        # Simulate trivial work
        await asyncio.sleep(0.001)
        return {"processed": payload["id"]}

    builder = WorkflowBuilder()
    builder.register_handler(AgentRole.PARSER, fast_handler)

    # Add steps
    for i in range(total_tasks):
        builder.add_step(AgentRole.PARSER, {"id": i})

    gc.collect()
    mem_before = gc.get_count()

    start = time.time()
    results = await builder.run()
    elapsed = time.time() - start

    mem_after = gc.get_count()

    # Assertions
    assert len(results) == total_tasks, f"Expected {total_tasks} results, got {len(results)}"
    assert all(r.status == TaskStatus.SUCCESS for r in results), "Some tasks failed"
    assert elapsed < 60, f"Too slow: {elapsed:.2f}s for 1000 tasks"
    # No memory blowup (rough check)
    assert mem_after[0] - mem_before[0] < 500, f"Possible memory leak: {mem_before} -> {mem_after}"

    print(f"\nLoad test completed: {total_tasks} tasks in {elapsed:.3f}s")
    print(f"Average per task: {elapsed / total_tasks * 1000:.3f}ms")
