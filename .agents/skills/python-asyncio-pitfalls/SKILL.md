---
name: python-asyncio-pitfalls
description: 'Use when debugging asyncio event-loop hangs, blocking calls inside coroutines, asyncio.gather vs TaskGroup choice, cancellation handling, structured concurrency, mixing sync and async, run_in_executor decisions, asyncio task lifetimes, "Task was destroyed but it is pending" warnings, or async context manager bugs. Triggers: event loop blocked by sync I/O, ConnectionResetError on cancellation, asyncio in libraries that also offer sync API, aiohttp performance regressions, queue.Queue used in async code.'
---

# Python Asyncio Pitfalls

Asyncio is cooperative — one blocking call freezes the entire event loop. Most "asyncio is slow" stories are actually "we accidentally called a synchronous function inside a coroutine."

## When to use

- Performance debug: a single slow request blocks all others
- `RuntimeError: This event loop is already running` or "Task was destroyed but it is pending"
- Choosing between `asyncio.gather`, `asyncio.TaskGroup` (3.11+), and `asyncio.wait`
- Cancellation isn't propagating; child tasks keep running
- Mixing a sync library with async code without freezing the loop

## Core Patterns

### Detect blocking calls in the event loop

```python
import asyncio

async def main():
    loop = asyncio.get_running_loop()
    loop.set_debug(True)  # warns when a coroutine takes too long
    # PYTHONASYNCIODEBUG=1 also enables debug mode at env var level
```

Debug mode logs:
```
Executing <Task ... took 0.250 seconds
```

For production: `loop.slow_callback_duration = 0.1` — anything over 100ms means a blocking call slipped in.

### TaskGroup — structured concurrency (Python 3.11+)

```python
async def fetch_all(urls: list[str]) -> list[str]:
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(fetch(u)) for u in urls]
    return [t.result() for t in tasks]  # exceptions raised here
```

If any task raises, all siblings are cancelled and the exception (or `ExceptionGroup`) propagates out. This is the safe default.

`asyncio.gather` semantics:
```python
results = await asyncio.gather(fetch(a), fetch(b), return_exceptions=True)
# Without return_exceptions=True, first exception cancels nothing — siblings keep running
```

Use `gather` only when you want older fire-and-collect-errors semantics; `TaskGroup` for everything else.

### Mixing sync code

```python
# WRONG — blocks the loop
async def slow():
    return time.sleep(2)  # NOT awaitable; runs sync, blocks loop

# RIGHT — offload to thread
async def slow():
    return await asyncio.to_thread(time.sleep, 2)
```

`asyncio.to_thread` (3.9+) runs function in thread from default executor. For CPU-bound work, use `ProcessPoolExecutor`:

```python
import concurrent.futures
loop = asyncio.get_running_loop()
with concurrent.futures.ProcessPoolExecutor() as pool:
    result = await loop.run_in_executor(pool, expensive_pure_function, arg)
```

### Cancellation that actually works

```python
async def with_cleanup():
    try:
        await long_operation()
    except asyncio.CancelledError:
        await cleanup()
        raise  # re-raise so caller knows you were cancelled
    return result
```

Swallowing `CancelledError` is common cause of "task was destroyed but it is pending" warnings. Always re-raise unless explicitly catching to ignore.

### Context propagation across tasks

```python
import contextvars

request_id = contextvars.ContextVar('request_id')

async def handler(rid: str):
    request_id.set(rid)
    # Spawned tasks inherit ContextVar values automatically
    asyncio.create_task(log_async())
```

Use ContextVars for request-scoped data instead of thread-locals; `threading.local` doesn't work right in asyncio.

### Timeouts

```python
# 3.11+ — preferred
async with asyncio.timeout(5):
    result = await long_call()

# Older — wait_for
result = await asyncio.wait_for(long_call(), timeout=5)
```

`asyncio.timeout` integrates with TaskGroup; `wait_for` doesn't and can cause double-cancel surprise.

### Queues

```python
queue: asyncio.Queue[Job] = asyncio.Queue(maxsize=100)

async def producer():
    while item := await source():
        await queue.put(item)

async def consumer():
    while True:
        job = await queue.get()
        try:
            await process(job)
        finally:
            queue.task_done()

await queue.join()  # wait until all submitted jobs marked done
```

`maxsize` provides backpressure — without it, fast producer can OOM you.

### Async context managers and locks

```python
lock = asyncio.Lock()

async with lock:
    await critical_section()
```

Don't share `asyncio.Lock` across event loops; each loop has its own.

## Anti-patterns

### Calling sync I/O inside coroutine
**Symptom:** Throughput craters under load; one slow request blocks everything
**Diagnosis:** `requests.get`, `time.sleep`, `psycopg2.execute` — all sync, all block loop
**Fix:** Switch to async libraries (`httpx.AsyncClient`, `asyncio.sleep`, `asyncpg`). For unreplaceable sync libs: `asyncio.to_thread`

### Forgetting to await coroutine
**Symptom:** `coroutine 'fn' was never awaited` warning. No error, no return value
**Diagnosis:** `result = fn()` instead of `result = await fn()`
**Fix:** Add await. Linters (ruff, pylint) flag this

### `asyncio.gather` without `return_exceptions=True`
**Symptom:** First exception kills all tasks; others are abandoned
**Fix:** Use `return_exceptions=True` or switch to `TaskGroup`

### Creating tasks without keeping reference
**Symptom:** "Task was destroyed but it is pending"
**Fix:** Keep reference: `tasks.append(asyncio.create_task(...))`

### Using `queue.Queue` in async code
**Symptom:** Event loop blocks on `queue.put()` or `queue.get()`
**Fix:** Use `asyncio.Queue` instead

### Blocking in `__init__` or `__del__`
**Symptom:** Slow startup or shutdown; event loop blocked
**Fix:** Move I/O to async methods, use `__aenter__`/`__aexit__`

## DMarket Bot Specific

### Trading loop blocking
```python
# BAD — blocks event loop
async def trading_cycle():
    items = requests.get(dmarket_api_url)  # SYNC!
    for item in items:
        process_item(item)

# GOOD — fully async
async def trading_cycle():
    async with aiohttp.ClientSession() as session:
        async with session.get(dmarket_api_url) as resp:
            items = await resp.json()
    for item in items:
        await process_item(item)
```

### Concurrent API calls
```python
# BAD — sequential
async def fetch_all_prices(item_ids: list[str]):
    results = []
    for item_id in item_ids:
        price = await fetch_price(item_id)
        results.append(price)
    return results

# GOOD — concurrent with rate limiting
async def fetch_all_prices(item_ids: list[str]):
    semaphore = asyncio.Semaphore(10)  # Max10 concurrent

    async def fetch_with_limit(item_id: str):
        async with semaphore:
            return await fetch_price(item_id)

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(fetch_with_limit(iid)) for iid in item_ids]
    return [t.result() for t in tasks]
```

### SQLite in async context
```python
# BAD — blocks loop
async def get_price_history(item_id: str):
    conn = sqlite3.connect("prices.db")
    cursor = conn.execute("SELECT * FROM prices WHERE item_id = ?", (item_id,))
    return cursor.fetchall()

# GOOD — offload to thread
async def get_price_history(item_id: str):
    def _query():
        conn = sqlite3.connect("prices.db")
        cursor = conn.execute("SELECT * FROM prices WHERE item_id = ?", (item_id,))
        return cursor.fetchall()
    return await asyncio.to_thread(_query)
```
