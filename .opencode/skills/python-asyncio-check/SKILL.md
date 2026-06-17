---
name: python-asyncio-check
description: Use when debugging asyncio hangs, slow event loops, or concurrency bugs in the bot. Trigger keywords: "asyncio bug", "event loop blocked", "task was destroyed", "gather vs TaskGroup", "cancellation handling", "async deadlock", "coroutine was never awaited". Based on python-asyncio-pitfalls skill (⭐5 on SkillsMP), adapted for DMarket bot's trading loop.
---

# Python Asyncio Pitfalls — DMarket Bot Edition

Asyncio is cooperative — one blocking call freezes the entire trading loop. Most "asyncio is slow" bugs are actually sync calls inside coroutines.

## Bot-Specific Anti-Patterns

### 1. Sync DMarket API calls inside the trading loop

**Symptom:** "Event loop blocked" warnings. Trading cycle takes 30s+ instead of 5s.
**Diagnosis:** Any non-awaited call in the hot path: `json.loads()`, `sqlite3.execute()` without WAL mode, `float()` on large datasets, sync file I/O.
**Fix:** The bot already uses aiohttp + async DB access. Check for:
```python
# WRONG — blocks the loop on large datasets
import json
data = json.loads(huge_api_response)

# RIGHT — use Rust parser for batch data
from src.api.dmarket_parser import validate_batch_response
data = validate_batch_response(raw_json)  # Uses Rust parser
```

### 2. asyncio.gather without return_exceptions

**Bot locations:** `execution.py:109` (slippage check), `core.py:658-678` (candidate eval)
**Symptom:** One failed candidate eval kills the entire batch.
**Diagnosis:** `asyncio.gather(*tasks)` propagates the first exception, siblings keep running detached.
**Fix (already done):** The bot uses `return_exceptions=True` in `core.py:677`.
**Check:** Verify ALL gather calls have `return_exceptions=True` or use TaskGroup.

### 3. Unbounded asyncio.create_task

**Bot locations:** `execution.py:282,289` (buy notifications), `resale.py:311` (sell notifications)
**Symptom:** Hundreds of pending fire-and-forget tasks, OOM at scale.
**Diagnosis:** `asyncio.create_task(notifier.buy(...))` creates tasks that are never awaited.
**Fix:** These are low-cost (one per buy). Monitor with `len(asyncio.all_tasks())` periodically.

### 4. SQLite locking under concurrent writes

**Bot locations:** `db/price_history/inventory.py` — `with_db_retry` decorator
**Symptom:** `sqlite3.OperationalError: database is locked`
**Diagnosis:** Multiple coroutines writing to virtual_inventory simultaneously.
**Fix (already done):** `with_db_retry` with exponential backoff. WAL mode enabled.

### 5. Unclosed aiohttp sessions

**Symptom:** "Unclosed client session" warning at shutdown.
**Diagnosis:** CS2Cap oracle or DMarket client not closed on exception paths.
**Fix:** Use `async with` or guarantee `.close()` in finally blocks.

## Quality Gates

- [ ] `PYTHONASYNCIODEBUG=1` set in development `.env`
- [ ] All `asyncio.gather()` have `return_exceptions=True`
- [ ] All `asyncio.create_task()` tracked or fire-and-forget justified
- [ ] No `time.sleep()` in async code (use `asyncio.sleep`)
- [ ] No `requests.get()` in async code (use `self._request()`)
- [ ] Connection pools (aiohttp sessions) closed in finally/cleanup
- [ ] `loop.set_debug(True)` enabled in dev mode
- [ ] CancelledError always re-raised after cleanup

## Key Files to Check

| File | Concern |
|------|---------|
| `core.py:675` | gather with return_exceptions=True |
| `execution.py:109` | gather for parallel slippage |
| `cs2cap_oracle.py:212-215` | Rate limit sleep (non-blocking) |
| `db/price_history/inventory.py` | with_db_retry decorator |
| `dmarket_api_client/core.py:315` | rate limit wait |
| `cs2cap_cache.py` | Background refresh task |

## References

- Source skill: https://github.com/curiositech/windags-skills/tree/main/skills/python-asyncio-pitfalls
- SkillsMP: https://skillsmp.com
