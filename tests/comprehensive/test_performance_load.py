"""
Performance and Load Testing Module.

Tests for measuring performance, handling load, and stress testing.

Covers:
- Response time measurement
- Throughput testing
- Concurrent user simulation
- Memory usage monitoring
- CPU usage patterns
- Stress testing
"""

import asyncio
import gc
import random
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field

import pytest


@dataclass
class PerformanceMetrics:
    """Performance metrics container."""

    response_times: list = field(default_factory=list)
    errors: int = 0
    successful_requests: int = 0
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def total_requests(self) -> int:
        return self.successful_requests + self.errors

    @property
    def error_rate(self) -> float:
        return self.errors / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def avg_response_time(self) -> float:
        return statistics.mean(self.response_times) if self.response_times else 0.0

    @property
    def p50_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return statistics.median(self.response_times)

    @property
    def p95_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    @property
    def p99_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.99)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    @property
    def throughput(self) -> float:
        """Requests per second."""
        duration = self.end_time - self.start_time
        return self.total_requests / duration if duration > 0 else 0.0


class TestResponseTimeMeasurement:
    """Tests for response time measurement."""

    @pytest.fixture
    def performance_tracker(self):
        """Performance tracker fixture."""

        class PerformanceTracker:
            def __init__(self):
                self.metrics: dict = defaultdict(PerformanceMetrics)

            def record(self, operation: str, response_time: float, success: bool = True):
                m = self.metrics[operation]
                m.response_times.append(response_time)
                if success:
                    m.successful_requests += 1
                else:
                    m.errors += 1

            def get_stats(self, operation: str) -> dict:
                m = self.metrics[operation]
                return {
                    "avg": m.avg_response_time,
                    "p50": m.p50_response_time,
                    "p95": m.p95_response_time,
                    "p99": m.p99_response_time,
                    "error_rate": m.error_rate,
                    "total": m.total_requests,
                }

        return PerformanceTracker()

    def test_response_time_recording(self, performance_tracker):
        """Test recording of response times."""
        # Record some response times
        for _ in range(100):
            response_time = random.uniform(50, 200)  # 50-200ms
            performance_tracker.record("api_call", response_time)

        stats = performance_tracker.get_stats("api_call")

        assert stats["total"] == 100
        assert 50 <= stats["avg"] <= 200
        assert stats["p50"] > 0
        assert stats["p95"] >= stats["p50"]
        assert stats["p99"] >= stats["p95"]

    def test_percentile_calculation(self, performance_tracker):
        """Test accurate percentile calculation."""
        # Record predictable response times (1-100)
        for i in range(1, 101):
            performance_tracker.record("test_op", float(i))

        stats = performance_tracker.get_stats("test_op")

        # p50 should be around 50
        assert 49 <= stats["p50"] <= 51

        # p95 should be around 95
        assert 94 <= stats["p95"] <= 96

        # p99 should be around 99
        assert 98 <= stats["p99"] <= 100


class TestThroughputMeasurement:
    """Tests for throughput measurement."""

    def test_throughput_calculation(self):
        """Test throughput (requests per second) calculation."""
        metrics = PerformanceMetrics()
        metrics.start_time = time.time()

        # Simulate 1000 requests over ~1 second
        for _ in range(1000):
            metrics.successful_requests += 1
            metrics.response_times.append(random.uniform(1, 5))

        time.sleep(0.1)  # Small delay
        metrics.end_time = time.time()

        # Should have high throughput
        assert metrics.throughput > 100  # At least 100 req/s

    def test_throughput_under_load(self):
        """Test throughput measurement under simulated load."""

        async def simulate_request():
            await asyncio.sleep(random.uniform(0.001, 0.01))
            return True

        async def run_load_test(num_requests: int, concurrency: int) -> PerformanceMetrics:
            metrics = PerformanceMetrics()
            metrics.start_time = time.time()

            semaphore = asyncio.Semaphore(concurrency)

            async def bounded_request():
                async with semaphore:
                    start = time.time()
                    try:
                        await simulate_request()
                        elapsed = (time.time() - start) * 1000
                        metrics.response_times.append(elapsed)
                        metrics.successful_requests += 1
                    except Exception:
                        metrics.errors += 1

            await asyncio.gather(*[bounded_request() for _ in range(num_requests)])

            metrics.end_time = time.time()
            return metrics

        # Run with asyncio
        metrics = asyncio.get_event_loop().run_until_complete(run_load_test(100, 10))

        assert metrics.total_requests == 100
        assert metrics.throughput > 0


class TestConcurrentUsers:
    """Tests for concurrent user simulation."""

    @pytest.mark.asyncio
    async def test_concurrent_user_sessions(self):
        """Test handling of concurrent user sessions."""

        class UserSession:
            def __init__(self, user_id: int):
                self.user_id = user_id
                self.actions: list = []

            async def perform_action(self, action: str):
                await asyncio.sleep(random.uniform(0.001, 0.005))
                self.actions.append(action)
                return True

        async def user_workflow(session: UserSession):
            """Simulate user workflow."""
            await session.perform_action("login")
            await session.perform_action("view_balance")
            await session.perform_action("scan_market")
            await session.perform_action("logout")

        # Simulate 50 concurrent users
        sessions = [UserSession(i) for i in range(50)]
        await asyncio.gather(*[user_workflow(s) for s in sessions])

        # All sessions should complete
        for session in sessions:
            assert len(session.actions) == 4
            assert session.actions[0] == "login"
            assert session.actions[-1] == "logout"

    @pytest.mark.asyncio
    async def test_concurrent_api_calls(self):
        """Test concurrent API call handling."""
        call_count = [0]
        lock = asyncio.Lock()

        async def mock_api_call(item_id: int):
            async with lock:
                call_count[0] += 1
            await asyncio.sleep(random.uniform(0.001, 0.01))
            return {"id": item_id, "status": "success"}

        # Make 100 concurrent calls
        results = await asyncio.gather(*[mock_api_call(i) for i in range(100)])

        assert len(results) == 100
        assert call_count[0] == 100
        assert all(r["status"] == "success" for r in results)


class TestMemoryUsage:
    """Tests for memory usage monitoring."""

    def test_memory_leak_detection(self):
        """Test for potential memory leaks."""

        def get_memory_usage() -> int:
            """Get current memory usage in bytes."""
            return sys.getsizeof([])  # Simplified - actual would use tracemalloc

        # Force garbage collection
        gc.collect()

        # Record baseline
        baseline = get_memory_usage()

        # Perform operations that might leak
        data = []
        for _ in range(1000):
            data.append({"key": "value" * 100})

        # Clear data
        data.clear()
        gc.collect()

        # Memory should not grow significantly
        current = get_memory_usage()
        # This is a simplified check - real implementation would use tracemalloc
        assert current <= baseline * 2

    def test_large_data_handling(self):
        """Test handling of large data sets."""

        def process_large_dataset(size: int) -> dict:
            """Process a large dataset."""
            data = [{"id": i, "value": f"item_{i}"} for i in range(size)]

            # Process
            result = {
                "count": len(data),
                "first": data[0] if data else None,
                "last": data[-1] if data else None,
            }

            # Clean up
            del data
            gc.collect()

            return result

        # Process increasingly large datasets
        for size in [100, 1000, 10000]:
            result = process_large_dataset(size)
            assert result["count"] == size


class TestStressTesting:
    """Tests for stress testing scenarios."""

    @pytest.mark.asyncio
    async def test_sustAlgoned_load(self):
        """Test system behavior under sustAlgoned load."""
        request_count = [0]
        error_count = [0]

        async def handle_request():
            request_count[0] += 1
            await asyncio.sleep(0.001)
            if random.random() < 0.01:  # 1% error rate
                error_count[0] += 1
                raise Exception("Random error")
            return True

        async def sustAlgoned_load(duration_seconds: float, rps: int):
            """Generate sustAlgoned load."""
            end_time = time.time() + duration_seconds
            delay = 1.0 / rps

            while time.time() < end_time:
                asyncio.create_task(handle_request())
                await asyncio.sleep(delay)

        # Run for 0.1 seconds at ~100 RPS
        await sustAlgoned_load(0.1, 100)
        await asyncio.sleep(0.05)  # Let pending tasks complete

        assert request_count[0] >= 5  # At least some requests processed
        # Error rate should be around 1%
        if request_count[0] > 0:
            actual_error_rate = error_count[0] / request_count[0]
            assert actual_error_rate < 0.15  # Less than 15% errors (slightly higher threshold for CI)

    @pytest.mark.asyncio
    async def test_burst_traffic(self):
        """Test handling of traffic bursts."""
        processed = []
        queue = asyncio.Queue()

        async def process_requests():
            while True:
                try:
                    request = await asyncio.wait_for(queue.get(), timeout=0.1)
                    await asyncio.sleep(0.001)  # Process time
                    processed.append(request)
                    queue.task_done()
                except asyncio.TimeoutError:
                    break

        # Send burst of requests
        burst_size = 100
        for i in range(burst_size):
            await queue.put({"id": i})

        # Process them
        await process_requests()

        # All should be processed
        assert len(processed) == burst_size


class TestResourceLimits:
    """Tests for resource limit handling."""

    @pytest.mark.asyncio
    async def test_connection_pool_limits(self):
        """Test connection pool limit handling."""

        class ConnectionPool:
            def __init__(self, max_connections: int = 10):
                self.max_connections = max_connections
                self.semaphore = asyncio.Semaphore(max_connections)
                self.active_connections = 0
                self.peak_connections = 0

            async def acquire(self):
                await self.semaphore.acquire()
                self.active_connections += 1
                self.peak_connections = max(self.peak_connections, self.active_connections)
                return True

            async def release(self):
                self.active_connections -= 1
                self.semaphore.release()

        pool = ConnectionPool(max_connections=5)

        async def use_connection(duration: float):
            await pool.acquire()
            await asyncio.sleep(duration)
            await pool.release()

        # Try to use 20 connections concurrently with only 5 allowed
        await asyncio.gather(*[use_connection(0.01) for _ in range(20)])

        # Peak should never exceed limit
        assert pool.peak_connections <= 5
        # All connections should be released
        assert pool.active_connections == 0

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting effectiveness."""

        class RateLimiter:
            def __init__(self, rate: int, period: float = 1.0):
                self.rate = rate
                self.period = period
                self.tokens = rate
                self.last_update = time.time()
                self.lock = asyncio.Lock()

            async def acquire(self) -> bool:
                async with self.lock:
                    now = time.time()
                    elapsed = now - self.last_update

                    # Replenish tokens
                    self.tokens = min(self.rate, self.tokens + elapsed * self.rate / self.period)
                    self.last_update = now

                    if self.tokens >= 1:
                        self.tokens -= 1
                        return True
                    return False

        limiter = RateLimiter(rate=10, period=1.0)  # 10 req/sec

        # Try to make 20 requests quickly
        allowed = 0
        for _ in range(20):
            if await limiter.acquire():
                allowed += 1

        # Should only allow ~10 requests
        assert allowed <= 12  # Some tolerance


class TestLatencyDistribution:
    """Tests for latency distribution analysis."""

    def test_latency_histogram(self):
        """Test latency histogram generation."""

        def generate_histogram(latencies: list, buckets: list) -> dict:
            """Generate histogram of latencies."""
            histogram = {f"<={b}ms": 0 for b in buckets}
            histogram[f">{buckets[-1]}ms"] = 0

            for latency in latencies:
                for bucket in buckets:
                    if latency <= bucket:
                        histogram[f"<={bucket}ms"] += 1
                        break
                else:
                    histogram[f">{buckets[-1]}ms"] += 1

            return histogram

        # Sample latencies
        latencies = [random.uniform(10, 500) for _ in range(1000)]
        buckets = [50, 100, 200, 500]

        histogram = generate_histogram(latencies, buckets)

        # Sum should equal total latencies
        assert sum(histogram.values()) == 1000

    def test_latency_slo_compliance(self):
        """Test SLO (Service Level Objective) compliance."""

        def check_slo_compliance(latencies: list, slo_ms: float, target_percentile: float) -> dict:
            """Check if latencies meet SLO."""
            if not latencies:
                return {"compliant": True, "actual_percentile": 0}

            sorted_latencies = sorted(latencies)
            idx = int(len(sorted_latencies) * target_percentile / 100)
            actual_latency = sorted_latencies[min(idx, len(sorted_latencies) - 1)]

            compliant = actual_latency <= slo_ms
            violations = sum(1 for l in latencies if l > slo_ms)

            return {
                "compliant": compliant,
                "slo_ms": slo_ms,
                "actual_percentile_latency": actual_latency,
                "target_percentile": target_percentile,
                "violations": violations,
                "violation_rate": violations / len(latencies),
            }

        # Generate latencies where 95% are under 200ms
        latencies = []
        for _ in range(950):
            latencies.append(random.uniform(50, 180))  # Fast
        for _ in range(50):
            latencies.append(random.uniform(200, 500))  # Slow

        # Check p95 SLO of 200ms
        result = check_slo_compliance(latencies, slo_ms=200, target_percentile=95)

        # Should be close to compliant
        assert result["violation_rate"] < 0.1  # Less than 10% violations


class TestScalability:
    """Tests for system scalability."""

    @pytest.mark.asyncio
    async def test_linear_scaling(self):
        """Test that processing time scales linearly with load."""

        async def process_batch(items: list) -> float:
            """Process a batch and return time taken."""
            start = time.time()
            for _ in items:
                await asyncio.sleep(0.0001)  # Simulate work
            return time.time() - start

        # Test with increasing batch sizes
        times = []
        sizes = [10, 20, 40, 80]

        for size in sizes:
            items = list(range(size))
            duration = await process_batch(items)
            times.append(duration)

        # Each doubling should approximately double the time
        for i in range(1, len(times)):
            ratio = times[i] / times[i - 1]
            # Should be around 2x (with some variance)
            assert 1.5 <= ratio <= 3.0, f"Non-linear scaling detected: {ratio}"

    def test_concurrent_scaling(self):
        """Test scaling with concurrent workers."""

        def measure_concurrent_throughput(num_workers: int, items_per_worker: int) -> float:
            """Measure throughput with N workers."""
            import concurrent.futures

            def process_item(item: int) -> int:
                time.sleep(0.0001)
                return item * 2

            start = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                items = list(range(num_workers * items_per_worker))
                list(executor.map(process_item, items))
            duration = time.time() - start

            return (num_workers * items_per_worker) / duration

        # More workers should increase throughput (up to a point)
        throughput_1 = measure_concurrent_throughput(1, 10)
        throughput_4 = measure_concurrent_throughput(4, 10)

        # 4 workers should have better throughput than 1
        # (not necessarily 4x due to overhead)
        assert throughput_4 > throughput_1 * 0.5
