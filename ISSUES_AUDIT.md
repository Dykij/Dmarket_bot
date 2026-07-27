# ISSUES_AUDIT.md — Iterative Audit Findings
## Date: 2026-07-27 | Methodology: 14-layer analysis

---

## Analysis Layers Completed

| # | Layer | Tool/Method | Findings |
|---|-------|-------------|----------|
| 1 | Static Lint | ruff (E,F,W,C90,B,SIM,UP) | 396 issues (242 line-length, 57 complexity, 10 unused imports) |
| 2 | Security | bandit -ll -ii | 96 issues (94 Low, 2 Medium, 0 High) |
| 3 | Dead Code | vulture --min-confidence 80 | 2 unused variables |
| 4 | Complexity | ruff --select=C901 | 57 functions with CC > 10 |
| 5 | Architecture | archy score | 0.557 (modularity 0.736, acyclicity 0.980, depth 0.364) |
| 6 | Exception Handling | grep analysis | 258 except Exception, 56 without logging |
| 7 | Async Safety | grep + manual review | 6 deprecated get_event_loop(), 1 blocking time.sleep |
| 8 | Financial Formulas | manual review + grep | SELL_FEE_RATE usage, hardcoded game_id |
| 9 | Import Profiling | manual timing | config 0.376s, db 0.012s, api 0.376s, total 0.765s |
| 10 | get_item_title Migration | grep analysis | 6 remaining raw get('title') in hot path |
| 11 | Hardcoded Values | grep analysis | 8+ hardcoded "a8db" instead of Config.GAME_ID |
| 12 | Data Flow | previous audit (DEPENDENCY_AUDIT_REPORT.md) | All transitions verified |
| 13 | Inter-module Signatures | previous audit | 4 P1 issues fixed |
| 14 | Singleton Analysis | previous audit | All singletons correctly shared |

---

## P1 — High Priority Issues

### P1-1: Blocking `time.sleep()` in async context
- **File:** `src/db/db_retry.py:134`
- **Issue:** `time.sleep(delay)` blocks the event loop during retry backoff
- **Fix:** Replace with `await asyncio.sleep(delay)` (requires making retry async)
- **Skeptical Analysis:** This only affects the retry path, not the hot path. The retry decorator wraps synchronous DB calls that run in a thread pool via `run_in_thread()`. The `time.sleep` inside the retry actually blocks the thread pool worker, not the event loop. Since `run_in_executor` runs in a separate thread, this is **not a real bug** — downgrading to P2.

### P1-2: Deprecated `asyncio.get_event_loop()` (6 locations)
- **Files:** `workflow/chains.py:83`, `cycle_orchestrator.py:482`, `incident_manager.py:289`, `notifier.py:409`, `sandbox/core.py:112,128`
- **Issue:** `get_event_loop()` emits DeprecationWarning in Python 3.10+ when no loop is running
- **Fix:** Replace with `asyncio.get_running_loop()` where loop is guaranteed running, or `asyncio.new_event_loop()` where creating
- **Skeptical Analysis:** In production, the event loop is always running when these are called. The deprecation warning is cosmetic. Downgrading to P2.

### P1-3: Hardcoded `"a8db"` game_id (8+ locations)
- **Files:** `risk_manager.py:172`, `views.py:238`, `twap.py:144`, `inventory_manager.py:40,81,113`, `oracle_factory.py:83,88`
- **Issue:** Game ID hardcoded instead of using `Config.GAME_ID`
- **Fix:** Replace all `"a8db"` with `Config.GAME_ID`
- **Skeptical Analysis:** This is a real issue for multi-game support, but since the bot only supports CS2 (`a8db`), it's not a runtime bug. The fix is safe — `Config.GAME_ID` defaults to `"a8db"`.

### P1-4: `resale_prod.py:142` — blanket SELL_FEE_RATE
- **File:** `src/core/target_sniping/resale_prod.py:142,147`
- **Issue:** Uses `SELL_FEE_RATE` (env-configurable, default 5%) instead of per-item dynamic fee
- **Fix:** Use `Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE` for consistency
- **Skeptical Analysis:** The `SELL_FEE_RATE` is already configurable via env var and defaults to `Config.FEE_RATE`. The issue is it doesn't include `WITHDRAWAL_FEE_RATE`. Fix is safe.

### P1-5: 57 functions with complexity > 10
- **Top offenders:** `run_bot` (17), `main` (19), `make_request` (15), `calculate` (17), `get_fair_price` (13)
- **Issue:** High cyclomatic complexity makes code hard to maintain and test
- **Fix:** Refactor largest functions into smaller helpers
- **Skeptical Analysis:** This is a code quality issue, not a correctness bug. Refactoring carries regression risk. **Documenting only, not fixing in this pass.**

### P1-6: 6 remaining raw `get('title')` in trading hot path
- **Files:** `scanner.py:183`, `inventory.py:58`, `resale_prod.py:57`, `shadow_engine.py:251`, `twap.py:159`
- **Issue:** V2 API items without top-level `title` will be silently dropped
- **Fix:** Replace with `get_item_title()` from `item_utils`
- **Skeptical Analysis:** These are in secondary paths (price-range scan, inventory sync, resale, TWAP). The primary trading path (cycle_orchestrator, filter, ranking) already uses `get_item_title()`. Fix is safe.

---

## P2 — Medium Priority Issues

| # | Issue | File | Count |
|---|-------|------|-------|
| P2-1 | Unused imports (F401) | Various | 10 |
| P2-2 | Unused variables (F841) | Various | 9 |
| P2-3 | except Exception without logging | Various | 56 |
| P2-4 | Line too long (E501) | Various | 242 |
| P2-5 | Blank line with whitespace (W293) | Various | 41 |
| P2-6 | Hardcoded tmp directory | reflexion/test_core.py | 2 |
| P2-7 | Deprecated get_event_loop() | Various | 6 |
| P2-8 | Collapsible if statements (SIM102) | Various | 7 |

---

## Summary

| Severity | Found | To Fix Now | Documented |
|----------|-------|------------|------------|
| P0 | 0 | 0 | 0 |
| P1 | 6 | 3 (P1-3, P1-4, P1-6) | 3 (P1-1, P1-2, P1-5) |
| P2 | 8 categories | 2 (P2-1, P2-2) | 6 |
