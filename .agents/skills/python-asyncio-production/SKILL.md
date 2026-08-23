---
name: python-asyncio-production
description: Production-grade asyncio patterns for Python 3.11+. Use when writing, reviewing, or debugging async code — TaskGroup, cancellation, timeouts, backpressure, ExceptionGroups, singleton init, pytest-asyncio.
---

# Python Asyncio Production

## When to Use
- Writing/reviewing `async def` functions, background workers, or WebSocket handlers
- Designing task fan-out/fan-in with `asyncio.TaskGroup`
- Adding timeouts to network calls (DMarket API, WebSocket)
- Initializing shared singletons (DB pools, Rust FFI bindings)
- Debugging hangs, leaked tasks, or silent exception swallowing
- Writing pytest-asyncio tests for concurrent trading loops

## Core Rules

1. **Every task tracked** — Never fire `create_task()` without storing reference in `dict[str, asyncio.Task]`
2. **Every await has timeout** — Wrap `await dmarket_api.*` in `asyncio.timeout(30)`
3. **Cancellation is cooperative** — Catch `CancelledError` only in `finally` for cleanup
4. **TaskGroup over gather** — Use `asyncio.TaskGroup` for scanner/executor fan-out
5. **Bound all queues** — `asyncio.Queue(maxsize=100)` for order book backpressure
6. **Log background exceptions** — `task.add_done_callback(log_exception)` on every spawned task

## Trading Bot Patterns

### Scanner/Executor Fan-Out
```python
async def trading_cycle(items: list[MarketItem]):
    async with asyncio.TaskGroup() as tg:
        for item in items:
            tg.create_task(evaluate_and_execute(item))
```

### API Call with Timeout + Retry
```python
async def fetch_orderbook_with_retry(item_id: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            async with asyncio.timeout(10):
                return await dmarket_api.get_orderbook(item_id)
        except asyncio.TimeoutError:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)
```

### Graceful Shutdown
```python
async def shutdown(task_registry: dict[str, asyncio.Task]):
    for task in task_registry.values():
        task.cancel()
    await asyncio.gather(*task_registry.values(), return_exceptions=True)
```

### Singleton Init (DB Pool)
```python
_db_pool: asyncpg.Pool | None = None

async def get_db_pool() -> asyncpg.Pool:
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(dsn=DB_DSN, min_size=2, max_size=10)
    return _db_pool
```

### Bounded Queue for Backpressure
```python
order_queue: asyncio.Queue[Order] = asyncio.Queue(maxsize=100)

# Producer (scanner)
await order_queue.put(order)  # blocks if full

# Consumer (executor)
order = await order_queue.get()
```

## Anti-Patterns to Reject
- `asyncio.gather(*tasks)` without `return_exceptions=True` — one failure kills all
- `create_task()` without storing reference — task gets garbage collected
- `await` without timeout — can hang forever on network call
- Global mutable state without lock — race condition in concurrent tasks
- `asyncio.sleep()` in hot loop — use `asyncio.Event` with timeout instead

## Testing
- Use `pytest-asyncio` with `mode=auto`
- Test cancellation: `task.cancel()` → verify `CancelledError` propagates
- Test timeout: mock slow API, verify `asyncio.TimeoutError` handling
- Test concurrent: multiple tasks writing to shared SQLite → verify no corruption
- Use `asyncio.Barrier` to synchronize test tasks

## Key Files in This Project
- `src/core/scanner.py` — scanner loop with TaskGroup
- `src/core/executor.py` — trade execution with timeout
- `src/api/dmarket_client.py` — API calls with retry
- `src/db/price_history.py` — SQLite concurrent writes
