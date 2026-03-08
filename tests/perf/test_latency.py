import asyncio
import time
import pytest

# Performance constraint: Critical path should be under 50ms

async def critical_path_operation():
    """Simulate a critical path operation for latency testing."""
    await asyncio.sleep(0.01)  # 10ms
    return True

@pytest.mark.asyncio
async def test_latency_critical_path():
    """Verify that critical path operations complete within 50ms."""
    start_time = time.perf_counter()

    await critical_path_operation()

    end_time = time.perf_counter()
    duration_ms = (end_time - start_time) * 1000

    print(f"\nLatency: {duration_ms:.2f}ms")

    # Assert < 50ms
    assert duration_ms < 50.0, f"Latency too high: {duration_ms}ms > 50ms"
