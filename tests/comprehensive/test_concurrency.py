"""
Concurrency Testing Module.

Tests system behavior under concurrent access:
- Race condition detection
- Deadlock prevention
- Thread safety
- Async concurrency
- Resource contention
"""
import asyncio
import threading
import time

import pytest

# =============================================================================
# ASYNC CONCURRENCY TESTS
# =============================================================================


class TestAsyncConcurrency:
    """Tests for async concurrency scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self) -> None:
        """Test concurrent API requests don't interfere."""
        results = []

        async def mock_api_call(request_id: int) -> dict:
            await asyncio.sleep(0.01)
            return {"id": request_id, "status": "success"}

        # Execute concurrent requests
        tasks = [mock_api_call(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # All requests should complete successfully
        assert len(results) == 10
        assert all(r["status"] == "success" for r in results)
        # Each request should have unique ID
        ids = [r["id"] for r in results]
        assert len(set(ids)) == 10

    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self) -> None:
        """Test concurrent cache access is thread-safe."""
        cache = {}
        lock = asyncio.Lock()
        operations = []

        async def cached_operation(key: str, value: str) -> str:
            async with lock:
                if key not in cache:
                    await asyncio.sleep(0.001)  # Simulate computation
                    cache[key] = value
                    operations.append(f"write:{key}")
                else:
                    operations.append(f"read:{key}")
                return cache[key]

        # Concurrent access to same key
        tasks = [cached_operation("key1", f"value_{i}") for i in range(5)]
        results = await asyncio.gather(*tasks)

        # Only one write should occur
        write_count = sum(1 for op in operations if op.startswith("write"))
        assert write_count == 1
        # All results should be the same
        assert len(set(results)) == 1

    @pytest.mark.asyncio
    async def test_concurrent_balance_updates(self) -> None:
        """Test concurrent balance updates maintAlgon consistency."""
        balance = {"amount": 1000}
        lock = asyncio.Lock()

        async def update_balance(delta: int) -> int:
            async with lock:
                current = balance["amount"]
                await asyncio.sleep(0.001)  # Simulate processing
                balance["amount"] = current + delta
                return balance["amount"]

        # Concurrent updates
        tasks = [
            update_balance(100),
            update_balance(-50),
            update_balance(200),
            update_balance(-100),
        ]
        await asyncio.gather(*tasks)

        # Final balance should be consistent
        expected = 1000 + 100 - 50 + 200 - 100
        assert balance["amount"] == expected

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self) -> None:
        """Test semaphore properly limits concurrency."""
        max_concurrent = 3
        semaphore = asyncio.Semaphore(max_concurrent)
        concurrent_count = []
        current_count = 0
        lock = asyncio.Lock()

        async def limited_operation(op_id: int) -> int:
            nonlocal current_count
            async with semaphore:
                async with lock:
                    current_count += 1
                    concurrent_count.append(current_count)

                await asyncio.sleep(0.01)

                async with lock:
                    current_count -= 1

            return op_id

        tasks = [limited_operation(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Concurrent count should never exceed limit
        assert max(concurrent_count) <= max_concurrent


# =============================================================================
# RACE CONDITION TESTS
# =============================================================================


class TestRaceConditions:
    """Tests for race condition detection and prevention."""

    @pytest.mark.asyncio
    async def test_check_then_act_race_condition(self) -> None:
        """Test check-then-act pattern with proper locking."""
        inventory = {"item_1": 1}
        lock = asyncio.Lock()
        purchases = []

        async def purchase_item(buyer_id: int) -> bool:
            async with lock:
                if inventory.get("item_1", 0) > 0:
                    await asyncio.sleep(0.001)  # Simulate delay
                    inventory["item_1"] -= 1
                    purchases.append(buyer_id)
                    return True
                return False

        # Two buyers try to purchase the same item
        results = await asyncio.gather(
            purchase_item(1),
            purchase_item(2),
        )

        # Only one should succeed
        assert sum(results) == 1
        assert len(purchases) == 1
        assert inventory["item_1"] == 0

    @pytest.mark.asyncio
    async def test_double_spend_prevention(self) -> None:
        """Test prevention of double-spend scenario."""
        balance = {"amount": 100}
        spent_transactions = set()
        lock = asyncio.Lock()

        async def spend(tx_id: str, amount: int) -> bool:
            async with lock:
                if tx_id in spent_transactions:
                    return False  # Already processed
                if balance["amount"] >= amount:
                    await asyncio.sleep(0.001)
                    balance["amount"] -= amount
                    spent_transactions.add(tx_id)
                    return True
                return False

        # Try to spend same transaction twice concurrently
        results = await asyncio.gather(
            spend("tx1", 100),
            spend("tx1", 100),
        )

        # Only one should succeed
        assert sum(results) == 1
        assert balance["amount"] == 0

    @pytest.mark.asyncio
    async def test_counter_increment_race(self) -> None:
        """Test counter increment is atomic."""
        counter = {"value": 0}
        lock = asyncio.Lock()

        async def increment():
            async with lock:
                current = counter["value"]
                await asyncio.sleep(0.0001)
                counter["value"] = current + 1

        tasks = [increment() for _ in range(100)]
        await asyncio.gather(*tasks)

        assert counter["value"] == 100


# =============================================================================
# DEADLOCK PREVENTION TESTS
# =============================================================================


class TestDeadlockPrevention:
    """Tests for deadlock prevention."""

    @pytest.mark.asyncio
    async def test_lock_ordering_prevents_deadlock(self) -> None:
        """Test consistent lock ordering prevents deadlock."""
        lock_a = asyncio.Lock()
        lock_b = asyncio.Lock()
        results = []

        async def operation_1():
            # Always acquire locks in same order
            async with lock_a, lock_b:
                await asyncio.sleep(0.01)
                results.append("op1")

        async def operation_2():
            # Same order as operation_1
            async with lock_a, lock_b:
                await asyncio.sleep(0.01)
                results.append("op2")

        await asyncio.gather(operation_1(), operation_2())

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_timeout_prevents_indefinite_wait(self) -> None:
        """Test timeout prevents indefinite waiting."""
        lock = asyncio.Lock()
        await lock.acquire()  # Lock is held

        async def try_acquire_with_timeout():
            try:
                # asyncio.Lock doesn't have timeout, simulate with wait_for
                acquired = False
                try:
                    await asyncio.wait_for(
                        asyncio.shield(lock.acquire()),
                        timeout=0.1
                    )
                    acquired = True
                except asyncio.TimeoutError:
                    pass
                return acquired
            finally:
                pass

        result = await try_acquire_with_timeout()

        # Should timeout, not acquire
        assert result is False

        lock.release()

    @pytest.mark.asyncio
    async def test_try_lock_pattern(self) -> None:
        """Test try-lock pattern for non-blocking acquisition."""
        lock = asyncio.Lock()
        await lock.acquire()

        # Try to acquire without blocking
        acquired = lock.locked()

        assert acquired is True  # Lock is already held

        lock.release()


# =============================================================================
# RESOURCE CONTENTION TESTS
# =============================================================================


class TestResourceContention:
    """Tests for resource contention handling."""

    @pytest.mark.asyncio
    async def test_connection_pool_contention(self) -> None:
        """Test connection pool handles contention properly."""
        pool_size = 3
        pool = asyncio.Queue(maxsize=pool_size)

        # Fill pool with connections
        for i in range(pool_size):
            await pool.put(f"conn_{i}")

        async def use_connection(task_id: int) -> str:
            conn = await pool.get()
            await asyncio.sleep(0.01)  # Use connection
            await pool.put(conn)
            return f"task_{task_id}_used_{conn}"

        # More tasks than connections
        tasks = [use_connection(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        # Pool should be back to full
        assert pool.qsize() == pool_size

    @pytest.mark.asyncio
    async def test_rate_limiting_under_load(self) -> None:
        """Test rate limiting works under concurrent load."""
        requests_per_second = 5
        window_size = 1.0
        request_times = []
        lock = asyncio.Lock()

        async def rate_limited_request(request_id: int) -> bool:
            async with lock:
                current_time = time.time()
                # Remove old requests outside window
                while request_times and current_time - request_times[0] > window_size:
                    request_times.pop(0)

                if len(request_times) >= requests_per_second:
                    return False  # Rate limited

                request_times.append(current_time)
                return True

        # Burst of requests
        results = await asyncio.gather(*[
            rate_limited_request(i) for i in range(10)
        ])

        # Only rate_limit requests should succeed
        assert sum(results) <= requests_per_second

    @pytest.mark.asyncio
    async def test_fAlgor_queue_scheduling(self) -> None:
        """Test fAlgor queue scheduling under contention."""
        queue = asyncio.Queue()
        processed_order = []

        # Add items with priorities
        for i in range(5):
            await queue.put(i)

        async def process_queue():
            while not queue.empty():
                item = await queue.get()
                processed_order.append(item)
                queue.task_done()

        await process_queue()

        # FIFO order should be maintAlgoned
        assert processed_order == [0, 1, 2, 3, 4]


# =============================================================================
# THREAD SAFETY TESTS
# =============================================================================


class TestThreadSafety:
    """Tests for thread safety in mixed async/sync code."""

    def test_thread_local_storage(self) -> None:
        """Test thread-local storage isolation."""
        thread_local = threading.local()
        results = {}

        def set_and_get(thread_id: int) -> int:
            thread_local.value = thread_id
            time.sleep(0.01)
            results[thread_id] = thread_local.value
            return thread_local.value

        threads = [
            threading.Thread(target=set_and_get, args=(i,))
            for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each thread should have its own value
        for thread_id, value in results.items():
            assert thread_id == value

    def test_shared_state_with_lock(self) -> None:
        """Test shared state access with lock."""
        counter = {"value": 0}
        lock = threading.Lock()

        def increment():
            for _ in range(100):
                with lock:
                    counter["value"] += 1

        threads = [threading.Thread(target=increment) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert counter["value"] == 500


# =============================================================================
# ASYNC QUEUE TESTS
# =============================================================================


class TestAsyncQueues:
    """Tests for async queue behavior under concurrency."""

    @pytest.mark.asyncio
    async def test_producer_consumer_pattern(self) -> None:
        """Test producer-consumer pattern works correctly."""
        queue = asyncio.Queue(maxsize=5)
        produced = []
        consumed = []

        async def producer():
            for i in range(10):
                await queue.put(i)
                produced.append(i)
                await asyncio.sleep(0.001)

        async def consumer():
            while len(consumed) < 10:
                item = await queue.get()
                consumed.append(item)
                queue.task_done()

        await asyncio.gather(producer(), consumer())

        assert produced == consumed
        assert len(consumed) == 10

    @pytest.mark.asyncio
    async def test_multiple_consumers(self) -> None:
        """Test multiple consumers share work."""
        queue = asyncio.Queue()
        consumed = {1: [], 2: [], 3: []}
        done = asyncio.Event()

        # Add items
        for i in range(30):
            await queue.put(i)

        async def consumer(consumer_id: int):
            while not done.is_set() or not queue.empty():
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=0.1)
                    consumed[consumer_id].append(item)
                    queue.task_done()
                except asyncio.TimeoutError:
                    break

        # Start consumers
        tasks = [
            asyncio.create_task(consumer(i))
            for i in range(1, 4)
        ]

        # WAlgot for queue to be processed
        await queue.join()
        done.set()

        await asyncio.gather(*tasks)

        # All items should be consumed
        total_consumed = sum(len(items) for items in consumed.values())
        assert total_consumed == 30
