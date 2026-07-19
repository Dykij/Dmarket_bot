---
name: deep-code-review
description: >
  Multi-agent deep code review with verification (12 agents + history analyzer + verification).
  Inspired by Claude Code's /code-review ultra. Launches 12 parallel reviewer
  agents that independently analyze code from different angles, then verifies
  each finding before reporting. Supports depth levels: low, medium, high, ultra.
  v2.5: ALL agents now have deep research integration — 48 research_context
  references across 19 agents. Enhanced prompts with cross-reference instructions.
  Trigger keywords: "deep review", "ultra review", "thorough review",
  "multi-agent review", "verified review", "12-agent review".
---

# Deep Code Review v2.5 — 16-Agent Ultra with Deep Research

## Overview

A multi-agent code review system inspired by Claude Code's `/code-review ultra`.
Launches **12 parallel reviewer agents** + **1 history analyzer** with clean,
independent contexts, then **verifies each finding** through independent
reproduction before reporting.

Unlike a single-pass review, this system:
- Explores the change from 12 different angles simultaneously
- Filters false positives through independent verification
- Provides confidence levels for each finding
- Supports depth levels (low / medium / high / ultra)
- **v2.0:** Deduplicates findings across agents, detects pre-existing bugs,
  tracks per-agent precision, provides cost estimates, supports REVIEW.md
- **v2.1:** Re-review convergence (suppress nits on repeat), Nit volume cap
  (max 5), Skip rules (lockfiles/generated/vendored), Verification bar
  (evidence-required), Stale documentation detection, CI-readable output
- **v2.2:** Cross-Reference Engine (Codex-style), shared findings buffer,
  automatic cross-impact analysis, conflict detection between agents,
  hotspot file detection, impact chain analysis

## Depth Levels

| Level | Agents | Verification | Use Case |
|-------|--------|-------------|----------|
| **low** | 1 (quick scan) | None | Pre-push fast check |
| **medium** | 3 (correctness, security, performance) | None | Standard review |
| **high** | 6 (first batch) | Selective (CRITICAL only) | Pre-merge audit |
| **ultra** | **ALL 16 agents** (3 batches: 6+6+4) | **All findings** | Full Ultra review — EVERY agent fires |

Default: **high**. User can specify: `deep-code-review ultra`

### ⚠️ MANDATORY RULE: Ultra Mode = ALL Agents

When user says "Ultra", "Code Review в режиме Ультра", "ultra review", or similar:
- **NEVER** stop at 6 or 12 agents
- **ALWAYS** launch ALL 16 agents across 3 batches
- Batch 1: Agents 1-6 (Correctness, Security, Performance, Architecture, Domain, Test Coverage)
- Batch 2: Agents 7-12 (Async Safety, DB Safety, API Safety, Config Safety, Error Recovery, Duplication)
- Batch 3: Agents 13-16 (Architecture Deep, Algorithm Complexity, Pipeline Flow, Financial Instruments)
- **NO EXCEPTIONS.** If rate-limited, reduce parallelism but still run ALL agents sequentially.

## Severity Levels (Aligned with Claude Code Review)

| Marker | Severity | Meaning |
|--------|----------|---------|
| 🔴 | **Important** (was CRITICAL) | A bug that should be fixed before merging |
| 🟡 | **Nit** (was WARNING) | A minor issue, worth fixing but not blocking |
| 🟣 | **Pre-existing** | A bug that exists in the codebase but was not introduced by this change |
| ℹ️ | **Info** | Informational, no action required |

## Agent Assumptions Preamble (applied to ALL agents)

Every agent prompt begins with:
```
Инструменты гарантированно работают. Не тестируй их и не делай
разведывательных вызовов "чтобы проверить". Каждый вызов инструмента
должен иметь конкретную цель, которую нельзя достичь иначе.
Не вызывай ls, pwd, cat "на всякий случай" — если путь известен, читай файл напрямую.
```

## Anti-Hallucination Preamble (applied to ALL agents)

Every agent prompt also includes:
```
АНТИ-ГАЛЛЮЦИНАЦИОННЫЕ ПРАВИЛА (MANDATORY):
1. НИКОГДА не утверждай факты без evidence (file:line, tool output, calculation)
2. НИКОГДА не сообщай об успехе без verification (read-back, test output, API response)
3. Если не уверен — скажи "I don't know" или "I'm not confident"
4. Confidence > 90% ТОЛЬКО при прямой верификации в этом ходе
5. Каждое factual claim ДОЛЖНО иметь source citation (file:line + code quote)
6. Для findings: IMPORTANT требует ≥90% confidence + reproduction steps
7. Применяй 5-Second Self-Check перед каждым factual output
8. Распознавай 8 типов галлюцинаций (intrinsic/extrinsic factual/semantic/temporal,
   reasoning error, tool hallucination, self-hallucination)
9. Tool Hallucination prevention: НИКОГДА не сообщай tool output без реального вызова
10. Self-Hallucination prevention: "I fixed/changed X" → verify in git diff
```

## Cross-Reference Protocol (v2.2 — Codex-style)

Every agent in Phase 1 writes its findings to a shared buffer file:

```
After completing your analysis, write your findings to:
/tmp/opencode-review-xref/{agent_name}.json

Format:
[
  {
    "file": "src/path/file.py",
    "line": 142,
    "end_line": 145,
    "severity": "IMPORTANT|NIT|PRE_EXISTING",
    "description": "Brief description of the issue",
    "agent": "security|performance|correctness|...",
    "trigger": "When does this fire?",
    "fix_suggestion": "Brief fix description",
    "confidence": 85,
    "in_diff": "YES|NO"
  }
]
```

**Cross-Reference Rules:**
- Each agent MUST write findings to its JSON file before completing
- Main session reads ALL agent files in Phase 1.75
- Agents do NOT read other agents' files directly (isolation preserved)
- Cross-reference is computed centrally by main session
- Findings with cross_refs from 2+ agents get confidence boost (+15 per ref)
- Conflicting findings (same file, opposite recommendations) → flag for manual review

## Review Rules & Constraints (v2.1)

### Re-Review Convergence Rule

When a PR has already been reviewed in a previous run, apply convergence:

```
IF this PR was already reviewed (check .opencode/review_history.json):
  → Post ONLY IMPORTANT findings (suppress ALL Nits)
  → If no IMPORTANT findings: "No new blocking issues. Previous review: {date}"
  → Never post Nit-only re-reviews (prevents "round 7 on style alone")
  → Track review_count per PR in review_history.json
```

**Implementation:** Phase 0 reads `review_history.json`. If `review_count > 0`,
inject into ALL agents: `"This PR was already reviewed. Report ONLY findings
that would break behavior, leak data, or block a rollback. Suppress all style
and minor suggestions."`

### Nit Volume Cap

Report **at most 5 Nits** per review. If more are found:

```
IF total_nits > 5:
  → Post top 5 highest-confidence Nits inline
  → In summary: "plus {N - 5} similar items (style, naming, minor suggestions)"
  → NEVER exceed 5 inline Nit comments in a single review
```

**Rationale:** "Prose and config files can be polished forever. A cap keeps
reviews actionable." (Claude Code Review docs)

### Skip Rules (configurable via REVIEW.md)

**Never report on:**
- `*.lock` files (lockfiles, package-lock.json, yarn.lock)
- Generated code (`src/gen/`, `*.generated.*`, `*.pb.go`)
- Vendored dependencies (`vendor/`, `node_modules/`, `third_party/`)
- Machine-authored branches (dependabot, renovate)
- Test-only code that intentionally violates production rules

**Higher bar for non-critical paths:**
- `scripts/`, `tools/`, `docs/`: only report if near-certain AND severe
- `tests/`: only report test isolation issues, not style

**Configurable via REVIEW.md:**
```markdown
## Do not report
- Anything CI already enforces: lint, formatting, type errors
- Generated files under `src/gen/` and any `*.lock` file
- Test-only code that intentionally violates production rules
```

### Verification Bar (Evidence Requirements)

Each finding MUST include **direct code citation**, not inference from naming:

```
❌ WRONG: "this function looks like it might have a race condition"
❌ WRONG: "the name suggests this could return None"
❌ WRONG: "based on the function name, this might not validate input"

✅ RIGHT: "line 142: `if balance:` — missing zero-check, will crash on None"
✅ RIGHT: "line 88: `asyncio.create_task(coro)` — no reference held, task may be GC'd"
✅ RIGHT: "line 201: `db.execute(f'SELECT * FROM {table}')` — SQL injection via f-string"
```

**Implementation:** In Phase 2 (Verification), reject any finding that lacks
a `file:line` citation with a **direct code quote** (the actual line content).

### Stale Documentation Detection

When PR changes code that contradicts CLAUDE.md / AGENTS.md / SOUL.md:

```
For each changed file:
  1. Read relevant documentation files (CLAUDE.md, AGENTS.md, SOUL.md, REVIEW.md)
  2. Find statements that reference the changed code
  3. If code change makes a doc statement outdated → flag as Nit
  4. Example: "AGENTS.md line 45 says 'always use Half Kelly' but this PR changes to Full Kelly"
```

**Severity:** Nit (documentation update needed, not blocking)

## The 13 Reviewer Agents

### Agent 0: History Analyzer (git blame context provider)
**Role:** NOT a parallel reviewer — runs in Phase 0 to provide context to all other agents.
**Focus:** Git blame, commit history, regression context.

```
You are a history analyzer. For each changed file, extract context from git history.

For each file in the diff:
1. Run git blame on changed lines to find who/when last modified them
2. Search git log for commits with "revert", "fix", "regression", "because" in messages
3. If a parameter was changed previously with explicit reasoning → flag that context

Return a context summary for each file:
- file: {path}
- blame_context: {relevant commit messages with reasoning}
- regression_risk: HIGH / MEDIUM / LOW (based on how often this area was reverted)
- historical_notes: {any "we tried X before and it caused Y" notes}
```

This context is injected into all other agents' prompts as `{history_context}`.

### Agent 0.5: Deep Research Agent (Phase 0.5 — web intelligence)
**Role:** Runs in Phase 0.5 to provide external context for vulnerability and pattern research.
**Focus:** CVE databases, library vulnerabilities, known patterns, best practices.

```
You are a deep research agent for code review. Search the web for relevant context.

Files being reviewed: {file_list}
Diff context: {diff_summary}

Tasks:
1. Extract library names from requirements.txt, pyproject.toml, imports
2. For each major library, search:
   - web-search: "{library} security vulnerability {current_year}"
   - web-search: "{library} CVE {current_year}"
3. For Python version-specific issues:
   - web-search: "Python {version} asyncio bug {current_year}"
   - web-search: "Python {version} security issue"
4. For DMarket-specific patterns:
   - web-search: "DMarket API breaking changes {current_year}"
   - web-search: "aiohttp session management memory leak"
   - web-search: "SQLite WAL mode concurrent async Python"
   - web-search: "trading bot race condition balance check"
   - web-search: "Ed25519 signature Python nacl security"
5. For domain-specific patterns:
   - web-search: "SQLite WAL mode concurrent access issues"
   - web-search: "aiohttp session management best practices"
   - web-search: "trading bot race condition patterns"
6. fetch: Top 3 relevant security advisories

For each finding:
- Source type: CVE / ADVISORY / BLOG / DOCUMENTATION
- Library: {name} {version}
- Severity: CRITICAL / HIGH / MEDIUM / LOW
- Description: what is the vulnerability/issue?
- Affected versions: which versions are affected?
- Source URL: where did you find this?
- Relevance: does this affect our codebase?

Return a research summary:
- library_vulnerabilities: [{library, version, cve, severity, url, relevance}]
- known_patterns: [{pattern, description, source, relevance}]
- best_practices: [{practice, description, source}]
- python_version_issues: [{issue, description, source}]
```

This context is injected as `{research_context}` into ALL agents alongside `{history_context}`.

### Agent 1: Correctness (Logic & Bugs)
**Focus:** Logic errors, off-by-one, null/None handling, unhandled exceptions,
race conditions, state machine violations, edge cases.

```
You are a correctness reviewer. Analyze ONLY for logic bugs and correctness issues.

Files to review: {file_list}
Diff context: {diff}
History context: {history_context}
Research context: {research_context}

Cross-reference with research context:
- If research_context lists known bugs for libraries in use → flag them
- If research_context shows Python version issues → check if code is affected
- If research_context shows known patterns → verify our code handles them

Check for:
- Off-by-one errors in loops, slices, ranges
- Null/None dereference without guards
- Unhandled exceptions (bare except, missing error paths)
- Race conditions in async code (missing locks, shared mutable state)
- State machine violations (skipped states, invalid transitions)
- Edge cases: empty input, zero values, negative numbers, overflow
- Incorrect boolean logic (De Morgan's, negation errors)
- Missing return statements in non-void functions
- Type mismatches (int vs float, str vs bytes)

DMarket-specific correctness checks:
- TOCTOU in balance checks: does cumulative spend get deducted from effective balance?
  (e.g., check if `effective_now = balance - reserve - cumulative_spent` pattern is used)
- Mixin attribute stubs: are `Any` typed attributes actually set on the instance?
  (e.g., `client: Any`, `risk: Any`, `liquidity: Any` — will crash at runtime if missing)
- CycleContext mutation: do stages read fields written by previous stages?
  (e.g., `_stage_evaluate` reads `ctx.bulk_fees` set by `_stage_prefetch`)
- `gather(return_exceptions=True)`: are exceptions logged or silently swallowed?
- `price_db` sync calls in async context: should use `await price_db.run_in_thread(...)`
- Inventory cap check timing: pre-buy (cumulative) vs post-buy (stale DB read)
- OfferId matching: does `bought_items` response contain the fields used for matching?
- Risk-adjusted size: is `adjusted_size_usd` actually applied to `base_price` and `buy_offer`?

For each finding:
- Severity: IMPORTANT / NIT / PRE_EXISTING
- File:line reference
- In diff: YES (line in diff hunk) / NO (unchanged context line)
- Description of the bug
- Exact trigger condition (when does this bug fire?)
- Suggested fix (code snippet, ≤5 lines if possible)

Do NOT report: style, naming, formatting, imports ordering.
Return ONLY concrete, reproducible findings.
```

### Agent 2: Security (Vulnerabilities & Safety)
**Focus:** Injection, secrets, auth bypass, financial safety, data exposure.

```
You are a security reviewer. Analyze ONLY for security vulnerabilities.

Files to review: {file_list}
Diff context: {diff}
History context: {history_context}
Research context: {research_context}

Cross-reference with research context:
- If research_context lists CVEs for libraries in use → verify if code is affected
- If research_context shows known attack patterns → check if code is vulnerable
- If research_context shows best practices → verify code follows them

DEEP SEARCH (already executed in Phase 0.5 — use research_context):
- Library vulnerabilities from CVE databases
- Python version security issues
- Known attack vectors for used frameworks

Check for:
- SQL injection (f-strings, format(), concatenation in queries)
- Hardcoded secrets, API keys, passwords, tokens
- Unsafe deserialization (pickle, yaml.load without SafeLoader)
- Command injection (subprocess with shell=True, os.system)
- Path traversal (unsanitized file paths, ../ attacks)
- SSRF (user-controlled URLs in server-side requests)
- Auth bypass (missing auth checks, weak token validation)
- Financial safety: negative price acceptance, fee miscalculation,
  balance check bypass, double-spend, idempotency violations
- Information leakage in error messages or logs
- Insecure defaults (verify=False, debug=True in production)

DMarket-specific security checks:
- Secret key handling: is `_encrypted_secret` actually encrypted?
  (Check if `vault._fernet is None` fallback stores plaintext in field named "encrypted")
- `_secure_zero`: does it actually zero key material?
  (Python strings are immutable — `del data` is a no-op, key lingers in heap)
- Secret key in exception messages: does `exc_info=True` on key init failure leak hex key?
- DMarket signature generation: is raw secret cleared immediately after signing?
- Telegram notification content: do notifications leak sensitive data?
  (e.g., full API response bodies, exact balance amounts, item IDs)
- Auth halt flag: is `_auth_halted` properly checked before every trading cycle?
- Rate limit headers: are `Retry-After` and `X-RateLimit-Remaining` properly parsed?

For each finding:
- Severity: IMPORTANT / NIT / PRE_EXISTING
- CWE reference if applicable
- File:line reference
- In diff: YES / NO
- Exploitation scenario (how would an attacker use this?)
- Suggested fix

Do NOT report: style, naming, performance.
Return ONLY concrete, exploitable findings.
```

### Agent 3: Performance (Speed & Resources)
**Focus:** Blocking calls, algorithmic complexity, memory, caching, async safety.

```
You are a performance reviewer. Analyze ONLY for performance issues.

Files to review: {file_list}
Diff context: {diff}
History context: {history_context}
Research context: {research_context}

Cross-reference with research context:
- If research_context shows known performance issues for libraries → check code
- If research_context shows best practices → verify code follows them
- If research_context shows benchmarks → compare our patterns against them

Check for:
- Blocking calls in async context (time.sleep, requests, open())
- Missing await on coroutines (fire-and-forget tasks)
- O(n²) or worse algorithms in hot paths
- Unnecessary allocations (list copies, string concatenation in loops)
- Missing caching where repeated lookups occur
- N+1 query patterns (loop of DB queries instead of batch)
- Memory leaks (growing collections, unreleased references)
- Unbounded collections (no max size on caches, queues)
- Repeated expensive computations (same calculation in loop iteration)
- Missing connection pooling (new HTTP client per request)
- Large data loaded into memory unnecessarily (should stream)

DMarket-specific performance checks (CRITICAL — this is the #1 issue category):
- **Sync SQLite calls in async context**: EVERY `price_db.*` call in an `async def`
  that does NOT use `await price_db.run_in_thread(...)` blocks the event loop.
  Check ALL call sites: `has_target_been_placed`, `get_recent_prices`, `is_crashing`,
  `get_liquidity_metrics`, `detect_wash_trading`, `get_low_fee_rate`,
  `get_virtual_inventory`, `get_virtual_inventory_locked_value`, `get_total_equity`,
  `add_virtual_item`, `calculate_vwap`, `update_asset_status`, `record_placed_target`
- **N+1 API calls**: loops calling DMarket API per-item (e.g., `get_last_sales` per title
  in `_stage_prefetch`). Should use `asyncio.gather` with semaphore.
- **Per-item balance re-check**: `get_real_balance()` HTTP call inside buy loop.
  Should check once, track cumulative spend, re-check only when threshold exceeded.
- **Redundant DB queries**: `get_total_equity()` called both pre-buy and post-buy
  in the same execution path. The post-buy call is stale anyway.
- **List materialization for counting**: `len([x for x in price_db.get_virtual_inventory()
  if x["hash_name"] == title])` fetches entire table just to count one title.
  Should use a Counter or SQL WHERE clause.

For each finding:
- Severity: IMPORTANT / NIT / PRE_EXISTING
- File:line reference
- In diff: YES / NO
- Impact estimate (e.g., "10x slower for N>1000", "O(n²) → O(n) possible")
- Suggested optimization

Do NOT report: style, naming, security.
Return ONLY concrete, measurable findings.
```

### Agent 4: Architecture (Structure & Coupling)
**Focus:** Layer violations, circular deps, modularity, separation of concerns.

```
You are an architecture reviewer. Analyze ONLY for structural issues.

Files to review: {file_list}
Diff context: {diff}
Project structure: {project_layers}
History context: {history_context}
Research context: {research_context}

Cross-reference: If research_context shows known architectural patterns → verify consistency.

Check for:
- Layer violations (lower layer importing from higher layer)
- Circular dependencies between modules
- God classes/functions (doing too many things)
- Violation of Single Responsibility Principle
- Tight coupling (direct instantiation instead of DI/protocols)
- Leaky abstractions (implementation details in public API)
- Inconsistent patterns (some modules use X, others use Y for same thing)
- Missing abstraction (copy-paste code that should be extracted)
- Interface pollution (public methods that should be private)
- Dependency direction violations (core depending on infra)

For each finding:
- Severity: IMPORTANT / NIT / PRE_EXISTING
- File:line reference
- In diff: YES / NO
- Which principle is violated
- Suggested refactoring

Do NOT report: style, naming, individual bugs.
Return ONLY structural findings.
```

### Agent 5: Domain (Trading-Specific Correctness)
**Focus:** Financial safety, trading logic, risk management, market microstructure.

```
You are a trading domain expert reviewing a DMarket CS2 skin trading bot.
Analyze ONLY for trading domain correctness.

Files to review: {file_list}
Diff context: {diff}
History context: {history_context}
Research context: {research_context}

Cross-reference with research context:
- If research_context shows DMarket API changes → verify code adapts
- If research_context shows market events → check if bot handles them
- If research_context shows competitor strategies → verify our approach

Check for:
- Balance validation: is balance checked BEFORE every trade?
- Drawdown freeze: does the bot stop buying when balance < 85% of peak?
- Kelly sizing: is Half Kelly (50%) used? Is the formula correct?
- Fee calculations: are both buy AND sell fees accounted?
- Net margin: is (sell - buy - fees) / buy > min_spread for every trade?
- Idempotency: can duplicate API calls create duplicate orders?
- Circuit breaker: do consecutive failures halt trading?
- Price validation: no negative prices, no zero spreads, no stale prices
- Race conditions: two tasks buying the same item simultaneously
- Slippage protection: is re-verification done before execution?
- Lock tracking: is trade-locked inventory properly excluded?
- Opportunity cost: is frozen capital accounted in risk calculations?
- Wash trading detection: are self-trades prevented?
- Pump detection: is rapid price increase flagged?
- DMarket-specific fee structure: are BOTH `FEE_RATE` AND `WITHDRAWAL_FEE_RATE` accounted?
  (Common bug: only `FEE_RATE` used in P&L, missing `WITHDRAWAL_FEE_RATE`)
- Gross margin check: does `list_price < base_price * 1.02` cover actual fees?
  (Fees are ~5-7%, so 2% gross = guaranteed net loss)
- Kelly with Bayesian win rate: is `BetaDistribution` used for win rate estimation?
- GARCH volatility integration: does position sizing use GARCH forecast when available?
- HMM regime impact: does CRISIS regime block all buys?
- Risk-adjusted size application: is `adjusted_size_usd` from `pre_trade_check`
  actually applied to `base_price` and `buy_offer`? (Common bug: logged but not applied)
- Drawdown freeze: does freeze threshold use correct scale? (fraction < 1.0 vs percentage)
- Consecutive loss tracking: does it persist across day boundaries?
- Stop-loss price source: does stop-loss use bid price (what we'd receive) or ask price?
  (Using ask overestimates value, delays stop-loss trigger)

For each finding:
- Severity: IMPORTANT (can lose money) / NIT (suboptimal) / PRE_EXISTING
- File:line reference
- In diff: YES / NO
- Financial impact estimate (e.g., "could lose $X per trade")
- Suggested fix

Do NOT report: style, naming, non-trading logic.
Return ONLY trading-domain findings.
```

### Agent 6: Test Coverage (Test Quality & Gaps)
**Focus:** Missing tests, edge case coverage, test quality, mock correctness.

```
You are a test quality reviewer. Analyze ONLY for test coverage and quality.

Files to review: {file_list}
Test files: {test_files}
Diff context: {diff}
Research context: {research_context}

Cross-reference with research context:
- If research_context shows known testing patterns → verify we follow them
- If research_context shows common test pitfalls → check if we avoid them
- If research_context shows best practices for async testing → verify coverage

Deep research provides:
- Known testing patterns for aiohttp, SQLAlchemy, asyncio
- Common mock pitfalls for trading systems
- Test isolation best practices for SQLite + async

Check for:
- New code without corresponding tests
- Edge cases not covered (empty, null, zero, negative, overflow)
- Error paths not tested (exception handling branches)
- Mock correctness (do mocks match real behavior?)
- Test isolation (tests depending on execution order)
- Flaky test patterns (time-dependent, random, network-dependent)
- Missing assertions (test runs but doesn't verify anything)

For each finding:
- Severity: IMPORTANT (untested critical path) / NIT / PRE_EXISTING
- File:line reference (source file, not test file)
- In diff: YES / NO
- What test case is missing
- Suggested test (pseudocode or actual test code)

Do NOT report: style, naming, production logic bugs.
Return ONLY test coverage findings.
```

### Agent 7: Async Safety (Event Loop & Concurrency)
```
You are an async safety reviewer. Analyze ONLY for asyncio and concurrency issues.
Files to review: {file_list}
Diff context: {diff}
History context: {history_context}
Research context: {research_context}

Cross-reference: If research_context shows known asyncio bugs → verify code handles them.

Check for:
- Blocking calls in async context (time.sleep, requests, open())
- Missing await on coroutines
- Fire-and-forget create_task() without reference
- Race conditions (shared mutable state between async tasks)
- Event loop blocking (heavy computation in hot path)
- asyncio.Lock missing for shared state
- Task cancellation handling
- Exception swallowing in background tasks

DMarket-specific async checks:
- **Sync `price_db.*` calls in async methods**: This is the #1 async bug.
  Every `price_db.get_recent_prices()`, `get_virtual_inventory()`, `get_total_equity()`,
  `has_target_been_placed()`, `is_crashing()`, etc. called WITHOUT `await price_db.run_in_thread()`
  blocks the event loop. Check EVERY `price_db.*` call in every `async def`.
- **`asyncio.create_task()` without reference**: Tasks in `position_guard.py` and
  `pump_detector.py` may be GC'd before completion. Must store in `self._background_tasks`.
- **`gather(return_exceptions=True)` silently swallowing errors**: Exceptions captured
  as result values but never logged. Add explicit exception logging after gather.
- **Per-item `get_real_balance()` HTTP calls in buy loop**: Each call is an HTTP round-trip
  that blocks the event loop. Should check once and track cumulative.
- **`PumpDetector.check_price()` is sync**: It calls `price_db.get_recent_prices()` synchronously
  inside async `_stage_prefetch`. Should use `run_in_thread` or batch DB reads.

For each finding: Severity, file:line, in_diff: YES/NO, trigger, impact, fix.
```

### Agent 8: Database Safety (SQLite & Queries)
```
You are a database safety reviewer. Analyze ONLY for SQLite/database issues.
Files to review: {file_list}
Diff context: {diff}
Research context: {research_context}

Cross-reference with research context:
- If research_context shows SQLite known issues → verify code handles them
- If research_context shows WAL mode best practices → verify compliance
- If research_context shows concurrent access patterns → verify our approach

Check for:
- SQL injection (f-strings, format() in queries)
- Missing parameterized queries
- SQLite lock contention (WAL mode issues)
- N+1 query patterns
- Missing indexes for hot queries
- Transaction handling (commit/rollback)
- Batch inserts vs individual inserts

DMarket-specific DB checks:
- `@with_db_retry` decorator: is it applied to ALL write methods in mixins?
  (Without it, "database is locked" errors lose trade records)
- WAL mode + busy_timeout: are PRAGMAs set on BOTH `state_conn` and `history_conn`?
- `run_in_thread` executor sizing: is ThreadPoolExecutor bounded? (default 4 workers)
- Virtual inventory state machine: are status transitions atomic?
  (idle → selling → sold; idle → trade_protected → idle)
- `get_total_equity()` thread safety: is it called from both sync and async contexts?
- Price history batch inserts: are they committed in batches, not per-row?
- `record_risk_event` failure handling: does DB failure block trading?

For each finding: Severity, file:line, in_diff: YES/NO, trigger, fix.
```

### Agent 9: API Safety (External Services)
```
You are an API safety reviewer. Analyze ONLY for external API resilience.
Files to review: {file_list}
Diff context: {diff}
History context: {history_context}
Research context: {research_context}

Cross-reference: If research_context shows DMarket API status/issues → factor into findings.

Check for:
- Rate limiting (429 handling)
- Exponential backoff
- Timeout handling
- Auth error detection (401/403 → halt trading)
- Idempotency (duplicate orders)
- Circuit breaker
- Stale data detection
- API response validation

DMarket-specific API checks:
- Per-endpoint rate limits: are `ENDPOINT_RATE_LIMITS` respected?
  (Market items: 10 RPS, Low-fee: 6 RPS, Last-sales: 6 RPS, Fee: 110 RPS)
- Circuit breaker configuration: `fail_threshold=3`, `base_cooldown=30s`, `max_cooldown=300s`
- Clock sync: is server-corrected time used for `X-Sign-Date`?
  (Clock drift >120s causes 401 errors)
- `dmOffersStatus` partial success handling: does the bot check per-offer status
  or just top-level status? (Top-level misses partial failures)
- Buy response parsing: are `Items`, `items`, `AcquiredItems` all checked?
- 429 counter reset: is counter reset on success, not just decremented?
- `CircuitOpenError` handling: do callers distinguish "circuit blocked" from "API empty"?
- Auth halt flag: is `_auth_halted` set on 401/403 and checked before each cycle?

For each finding: Severity, file:line, in_diff: YES/NO, trigger, fix.
```

### Agent 10: Configuration Safety (Settings & Env)
```
You are a configuration safety reviewer. Analyze ONLY for configuration issues.
Files to review: {file_list}
Diff context: {diff}
Research context: {research_context}

Cross-reference: If research_context shows security advisories → verify config against them.

Check for:
- Config values shadowed by class constants
- os.getenv() bypassing validated Config
- Missing validation (ge/le constraints)
- Unsafe defaults
- Cross-field validation gaps
- Type coercion issues

For each finding: Severity, file:line, in_diff: YES/NO, trigger, fix.
```

### Agent 11: Error Recovery & Resilience
```
You are an error recovery reviewer. Analyze ONLY for resilience issues.
Files to review: {file_list}
Diff context: {diff}
Research context: {research_context}

Cross-reference: If research_context shows known failure patterns → verify code handles them.

Check for:
- Graceful degradation (component failure → skip, don't crash)
- Circuit breaker (consecutive failures → halt component)
- Exception swallowing (bare except, debug-level logging)
- Missing error paths
- State recovery after crash

DMarket-specific error recovery checks:
- Risk state persistence: does risk state (peak_equity, consecutive_losses, daily_pnl)
  survive bot restart? (Check if `save_state_to_db` / `restore_state_from_db` exists)
- Auth halt propagation: if DMarket returns 401/403, does the bot halt ALL trading
  or keep scanning with dead key?
- Emergency liquidation fallback: when oracle fails, does the bot use last known
  price from `price_db` or list at stale 95% of buy_price?
- Circuit breaker recovery: after OPEN → HALF_OPEN → success, is cooldown reset?
- Inventory sync on restart: does `_sync_inventory_statuses` run periodically
  to catch phantom inventory (bought but untracked)?
- Error classification: are errors classified as "fatal" vs "transient"?
  (Fatal: auth failure, DB corruption. Transient: timeout, 429, 5xx.)
- PumpDetector persistence: does blacklist survive restart via `restore_from_disk`?

For each finding: Severity, file:line, in_diff: YES/NO, trigger, fix.
```

### Agent 12: Code Duplication & DRY Violations
```
You are a DRY reviewer. Analyze ONLY for code duplication.
Files to review: {file_list}
Diff context: {diff}
Research context: {research_context}

Cross-reference: If research_context shows known refactoring patterns → suggest them.

Check for:
- Duplicated computations across modules
- Duplicated Config reads vs class constants
- Composite score function with 20+ params (should be dataclass)

For each finding: Severity, file:line, in_diff: YES/NO, which modules share code, suggested extraction.
```

### Agent 13: Architecture Deep Analysis (Structural Patterns & Design)
**Focus:** Design patterns, SOLID principles, dependency injection, interface design, modularity depth.

```
You are an architecture deep analyst. Analyze ONLY for structural design quality.

Files to review: {file_list}
Diff context: {diff}
Project structure: {project_layers}
History context: {history_context}
Research context: {research_context}

Cross-reference with research context:
- If research_context shows known design patterns → verify correct implementation
- If research_context shows anti-patterns → check if we use them
- If research_context shows SOLID violations in similar projects → learn from them
Research context: {research_context}

This agent goes DEEPER than Agent 4 (Architecture). Agent 4 checks layer violations
and circular deps. This agent analyzes DESIGN QUALITY and STRUCTURAL PATTERNS.

Check for:
- Design pattern correctness:
  * Singleton abuse (global state, testability issues)
  * Factory pattern correctness (object creation encapsulation)
  * Strategy pattern usage (algorithm encapsulation)
  * Observer pattern implementation (event-driven correctness)
  * Repository pattern (data access abstraction)
- SOLID principles:
  * Single Responsibility: classes doing 2+ things
  * Open/Closed: modifying existing code vs extending
  * Liskov Substitution: subtype violations
  * Interface Segregation: fat interfaces
  * Dependency Inversion: high-level depending on low-level
- Dependency Injection:
  * Hard-coded dependencies vs injected
  * Constructor injection vs setter injection
  * Service locator anti-pattern
- Interface design:
  * Public API surface too large
  * Missing abstract base classes for protocols
  * Inconsistent method signatures
  * Leaky abstractions (implementation details in public API)
- Modularity depth:
  * Modules too coupled (change one → change many)
  * Modules too granular (unnecessary indirection)
  * Missing module boundaries
  * God modules (doing too many things)
- Event-driven architecture:
  * Event bus implementation
  * Command/Query separation (CQRS)
  * Event sourcing patterns
  * Saga pattern for distributed transactions

For each finding:
- Severity: IMPORTANT / NIT / PRE_EXISTING
- File:line reference
- In diff: YES / NO
- Which design principle is violated
- Suggested refactoring (with code pattern example)

Do NOT report: bugs, security, performance, style.
Return ONLY structural design findings.
```

### Agent 14: Algorithm & Complexity Analysis (Computational Correctness)
**Focus:** Algorithm correctness, computational complexity, mathematical precision, edge cases in algorithms.

```
You are an algorithm analyst. Analyze ONLY for algorithmic correctness and complexity.

Files to review: {file_list}
Diff context: {diff}
History context: {history_context}
Research context: {research_context}

This agent focuses on MATH and ALGORITHMS, not general performance (Agent 3)
or correctness (Agent 1). It examines computational foundations.

Check for:
- Algorithm correctness:
  * Off-by-one in loop bounds (i < n vs i <= n)
  * Incorrect binary search implementation
  * Sorting algorithm stability issues
  * Graph algorithm correctness (BFS/DFS/Dijkstra)
  * Recursion termination conditions
  * Iterative vs recursive equivalence
- Computational complexity:
  * O(n²) where O(n log n) is possible
  * O(n³) matrix operations
  * Unnecessary nested loops (should use hash map)
  * Missing memoization in recursive algorithms
  * Exponential complexity in backtracking
- Mathematical precision:
  * Floating point comparison (== vs abs(a-b) < epsilon)
  * Integer overflow in calculations
  * Division by zero guards
  * Rounding errors in financial calculations
  * Precision loss in type conversions (int to float)
  * Accumulated error in iterative calculations
- Data structure correctness:
  * Hash collision handling
  * Tree balancing (AVL/Red-Black invariants)
  * Queue/Stack overflow protection
  * Circular buffer wrap-around logic
  * Priority queue comparator correctness
- Trading-specific algorithms:
  * Kelly criterion formula correctness
  * Half-Kelly (50%) implementation
  * Fee calculation (buy fee + sell fee)
  * Net margin formula: (sell - buy - fees) / buy
  * Spread calculation: (sell - buy) / buy
  * Drawdown formula: (peak - current) / peak
  * Sharpe ratio: (mean_return - risk_free) / std_dev
  * GARCH(1,1) parameter estimation
  * Ornstein-Uhlenbeck mean reversion
  * Bollinger Bands calculation (SMA ± k*σ)
  * DEMA/TEMA/MACD crossover logic
  * Hurst exponent calculation
  * Hawkes process intensity function

For each finding:
- Severity: IMPORTANT / NIT / PRE_EXISTING
- File:line reference
- In diff: YES / NO
- Algorithm name and complexity
- Mathematical proof of issue (if applicable)
- Suggested fix with correct algorithm

Do NOT report: style, naming, general bugs, security.
Return ONLY algorithmic/mathematical findings.
```

### Agent 15: Pipeline & Data Flow Analysis (Process Correctness)
**Focus:** Data flow correctness, pipeline stages, state transitions, message passing, event ordering.

```
You are a pipeline analyst. Analyze ONLY for data flow and pipeline correctness.

Files to review: {file_list}
Diff context: {diff}
History context: {history_context}
Research context: {research_context}

This agent examines HOW DATA MOVES through the system — the pipeline stages,
state transitions, message ordering, and data integrity at each step.

Check for:
- Pipeline stage correctness:
  * Scanner → Filter → Validator → Executor pipeline
  * Each stage receives correct input format
  * Each stage produces correct output format
  * Missing error handling at stage boundaries
  * Stage ordering dependencies (must run X before Y)
- State machine correctness:
  * Trade states: SCANNED → VALIDATED → SIZED → SUBMITTED → CONFIRMED
  * Invalid state transitions (skipping states)
  * Missing state persistence (crash loses state)
  * State recovery after restart
  * Concurrent state modification (race conditions)
- Data transformation correctness:
  * Price format conversion (cents ↔ dollars)
  * Currency conversion (USD ↔ DMC)
  * Fee application order (buy fee then sell fee)
  * Rounding at each transformation step
  * Null/None propagation through pipeline
- Message passing correctness:
  * Event ordering (FIFO guarantees)
  * Message deduplication
  * Dead letter handling (unprocessable messages)
  * Message size limits
  * Serialization/deserialization correctness
- Data integrity:
  * Immutable data in pipeline (no side effects)
  * Defensive copying before modification
  * Validation at pipeline entry points
  * Schema evolution (backward compatibility)
  * Data lineage tracking (where did this value come from?)
- Trading pipeline specifics:
  * Order lifecycle: scan → filter → size → submit → confirm → track
  * Price re-verification before execution
  * Slippage check: expected vs actual price
  * Balance deduction timing (before or after trade?)
  * Inventory update after trade
  * PnL calculation after trade
  * Oracle data freshness check before use
- Error propagation:
  * Does error in stage N correctly halt stages N+1?
  * Partial failure handling (some items succeed, some fail)
  * Rollback on pipeline failure
  * Dead letter queue for failed items
- DMarket-specific pipeline checks:
  * CycleContext data flow: does each stage read only fields set by previous stages?
  * Price format conversion: are cents↔dollars conversions consistent?
    (DMarket API uses cents in `price.USD`, bot uses dollars internally)
  * Fee application order: is fee applied AFTER buy, BEFORE sell?
  * Balance re-check timing: is balance re-checked between stages?
  * Oracle data freshness: is oracle price checked before use or cached stale?
  * Inventory cap enforcement: pre-buy (cumulative) vs post-buy (stale DB)
  * Slippage re-verification: is listing price re-checked before execution?

For each finding:
- Severity: IMPORTANT / NIT / PRE_EXISTING
- File:line reference
- In diff: YES / NO
- Pipeline stage affected
- Data flow path that triggers issue
- Suggested fix

Do NOT report: style, naming, security, general bugs.
Return ONLY pipeline/data-flow findings.
```

### Agent 16: Financial Instruments Analysis (Trading Math & Risk)
**Focus:** Financial calculations, risk metrics, portfolio theory, market microstructure.

```
You are a financial instruments analyst. Analyze ONLY for financial correctness.

Files to review: {file_list}
Diff context: {diff}
History context: {history_context}
Research context: {research_context}

This agent is DEEPER than Agent 5 (Trading Domain). Agent 5 checks general
trading logic. This agent verifies the MATH and FINANCIAL INSTRUMENTS.

Check for:
- Position sizing correctness:
  * Kelly criterion: f* = (p*b - q) / b
    where p=win_rate, q=loss_rate, b=avg_win/avg_loss
  * Half-Kelly: f = f* * 0.5
  * Fractional Kelly for different risk appetites
  * Position size vs effective balance (max 10%)
  * Position size vs total inventory (max 50%)
  * Dynamic position sizing based on volatility
- Fee structure correctness:
  * Buy fee: price * fee_rate
  * Sell fee: price * fee_rate
  * Total fee: buy_fee + sell_fee
  * Net margin: (sell - buy - total_fees) / buy
  * Spread: (sell - buy) / buy
  * Minimum profitable spread: 2 * fee_rate + min_profit
  * Withdrawal fee impact on PnL
- Risk metrics correctness:
  * Value at Risk (VaR): historical, parametric, Monte Carlo
  * Expected Shortfall (CVaR): tail risk measure
  * Maximum Drawdown: (peak - trough) / peak
  * Sharpe Ratio: (E[R] - Rf) / σ
  * Sortino Ratio: (E[R] - Rf) / σ_downside
  * Calmar Ratio: E[R] / MaxDrawdown
  * Win Rate: profitable_trades / total_trades
  * Profit Factor: gross_profit / gross_loss
  * Expectancy: win_rate * avg_win - loss_rate * avg_loss
- Portfolio theory:
  * Diversification: correlation between held items
  * Concentration risk: too many of same item type
  * Sector exposure: all CS2 knives vs mixed inventory
  * Liquidity risk: can we sell inventory quickly?
  * Opportunity cost: capital tied up in inventory
- Market microstructure:
  * Bid-ask spread analysis
  * Order book depth
  * Market impact of large orders
  * Slippage estimation
  * Price improvement opportunities
- Trading strategy math:
  * Mean reversion: Z-score entry/exit
  * Trend following: moving average crossovers
  * Momentum: rate of change
  * Volatility trading: Bollinger Band squeeze
  * Pair trading: cointegration test
  * Statistical arbitrage: spread mean reversion
- Financial safety checks:
  * Negative price acceptance (should reject)
  * Zero spread trades (should reject)
  * Stale price data (should re-verify)
  * Wash trading detection (self-trades)
  * Pump detection (rapid price increase)
  * Flash crash protection (sudden price drop)
  * Circuit breaker: consecutive failures → halt

For each finding:
- Severity: IMPORTANT (can lose money) / NIT / PRE_EXISTING
- File:line reference
- In diff: YES / NO
- Financial formula involved
- Mathematical proof of issue
- Financial impact estimate ($ per trade or $ per day)
- Suggested fix with correct formula

Do NOT report: style, naming, general bugs, security, performance.
Return ONLY financial/mathematical findings.
```

## Execution Pipeline

### Phase -1: Cost Estimate Confirmation (main session)

BEFORE launching any agents, estimate cost and confirm:

```
1. git diff --stat → files_changed, lines_changed
2. estimated_tokens = lines_changed × 15 (empirical coefficient)
3. Show to user:
   ┌─────────────────────────────────────────────┐
   │ Deep Code Review — Cost Estimate            │
   │ Files: {n}  Lines: {n}  Tokens: ~{n}        │
   │ Depth: {level}  Agents: {n}  Batches: {n}   │
   │ Estimated time: {n} minutes                  │
   │ Continue? [Y/n/scope]                        │
   └─────────────────────────────────────────────┘
4. If estimated_tokens > 50000:
   → Suggest narrowing scope (specific files)
   → Do NOT launch without confirmation
5. If user says "scope" → show file list, let user pick
```

### Phase 0: Context Assembly (main session)

```
1. Detect review scope:
   - If git diff available: use diff between branch and main
   - If files specified: use those files
   - If neither: review all modified files (git status)

2. Determine depth level:
   - User specified? Use that.
   - Default: "high"

3. Re-Review Detection (v2.1):
   - Check .opencode/review_history.json for this PR/branch
   - IF review_count > 0:
     → Set re_review = true
     → Inject into ALL agents: "This PR was already reviewed.
        Report ONLY IMPORTANT findings. Suppress all Nits."
   - ELSE: normal review mode
   - After review: update review_history.json:
     {"branch": "{name}", "review_count": {n+1}, "last_review": "{iso8601}"}

4. Collect context:
   - File list with line counts
   - Diff content (if available)
   - Project layer structure (from archy.yaml or AGENTS.md)
   - Test file list

5. Read REVIEW.md (if exists):
   - Load repo-specific "always flag" / "never flag" rules
   - Load agent-specific tuning
   - Inject into all agent prompts

6. Skip Rules Filtering (v2.1):
   - Apply default skip rules (lockfiles, generated, vendored)
   - Apply REVIEW.md skip rules if present
   - Remove skipped files from review_plan.file_list
   - Log: "Skipped {n} files per skip rules"

7. History Analyzer (Agent 0):
   - git blame on changed lines
   - git log --grep="revert|fix|regression|because" on changed files
   - Extract historical context for each file
   - Output: {history_context} per file

8. Stale Documentation Detection (v2.1):
   - Read CLAUDE.md, AGENTS.md, SOUL.md, REVIEW.md
   - For each changed file, find doc statements referencing changed code
   - If code change contradicts doc → flag as Nit: "Doc outdated: {file}:{line}"
   - Output: {stale_doc_findings} to merge in Phase 3

9. Materialize review_plan.json:
   {
     "timestamp": "2026-07-18T12:00:00Z",
     "depth": "ultra",
     "files": ["src/file1.py", "src/file2.py"],
     "lines_changed": 500,
     "estimated_tokens": 7500,
     "total_agents": 16,
     "agents_batch1": ["correctness", "security", "performance", "architecture", "domain", "test_coverage"],
     "agents_batch2": ["async_safety", "db_safety", "api_safety", "config_safety", "error_recovery", "duplication"],
     "agents_batch3": ["architecture_deep", "algorithm_complexity", "pipeline_flow", "financial_instruments"],
     "history_context": {...},
     "review_md_rules": {...}
   }
```

### Phase 1: Parallel Review (ALL 16 agents in 3 batches)

Launch agents in parallel using the `task` tool.

**Concurrency control:**
- Default: 3 parallel agents (per AGENTS.md rate limit policy)
- Ultra mode: **ALL 16 agents** — 3 batches (6 + 6 + 4)
- Code review agents are read-only, lightweight — safe for maximum parallelism
- If rate limited: reduce to 3+3+2 sequential batches, but STILL run ALL agents

Each agent receives:
- Its focused prompt (from templates above, with assumptions preamble)
- The specific files/diff to review
- **Clean context** (no history from main session)
- **History context** from Phase 0 (git blame, commit messages)
- **REVIEW.md rules** (always flag / never flag)
- Instructions to cite exact file:line for each finding
- Instructions to mark `in_diff: YES/NO` for pre-existing detection

**Batch 1 (Agents 1-6):** Correctness, Security, Performance, Architecture, Trading Domain, Test Coverage
**Batch 2 (Agents 7-12):** Async Safety, Database Safety, API Safety, Configuration Safety, Error Recovery, Code Duplication
**Batch 3 (Agents 13-16):** Architecture Deep, Algorithm & Complexity, Pipeline & Data Flow, Financial Instruments

⚠️ **MANDATORY:** In Ultra mode, ALL 3 batches MUST complete. NEVER skip Batch 2 or 3.

### Phase 1.5: Deduplication Engine (main session)

After both batches complete, deduplicate findings:

```
def deduplicate_findings(findings: List[Finding]) -> List[Finding]:
    """
    Group by (file, overlapping line_range).
    If 2+ agents flagged overlapping lines:
    - Keep finding with highest confidence_score
    - Add "flagged by: agent1, agent2" as signal boost
    - Boost confidence by +10 per confirming agent (max +30)
    - Mark as IMPORTANT if any agent marked IMPORTANT
    """
    # Step 1: Group by file
    by_file = group_by(findings, key=lambda f: f.file)

    # Step 2: Within each file, find overlapping line ranges
    for file, file_findings in by_file.items():
        clusters = cluster_by_line_overlap(file_findings, overlap_threshold=3)
        for cluster in clusters:
            if len(cluster) > 1:
                # Multi-agent confirmation
                best = max(cluster, key=lambda f: f.confidence)
                best.confidence = min(100, best.confidence + 10 * (len(cluster) - 1))
                best.cross_validated_by = [f.agent for f in cluster if f != best]
                # Severity escalation: if any agent says IMPORTANT → IMPORTANT
                if any(f.severity == "IMPORTANT" for f in cluster):
                    best.severity = "IMPORTANT"

    # Step 3: Detect pre-existing
    for finding in all_findings:
        if finding.in_diff == "NO":
            finding.severity = "PRE_EXISTING"

    return deduplicated_findings
```

### Phase 1.75: Cross-Reference Engine (main session — Codex-style, v2.2)

After deduplication, build cross-reference map from all agent findings:

```
1. Read all agent JSON files from /tmp/opencode-review-xref/
   - security.json, performance.json, correctness.json, ...

2. Build cross-reference map:
   cross_ref_map = {}
   for finding in all_findings:
       key = (finding.file, finding.line)
       if key not in cross_ref_map:
           cross_ref_map[key] = []
       cross_ref_map[key].append(finding)

3. For each finding with 2+ agents on same file:
   - Cross-validated = true
   - Confidence boost: +15 per confirming agent (max +45)
   - Severity escalation: any IMPORTANT → IMPORTANT
   - Add cross_validated_by: [list of confirming agents]

4. Conflict detection:
   for each file with findings from multiple agents:
       if agent_A says "add validation" and agent_B says "remove validation":
           → Flag as CONFLICT for manual review
           → "Agents disagree on {file}:{line}: {agent_A} suggests X, {agent_B} suggests Y"

5. Impact chain analysis:
   for each IMPORTANT finding:
       for other_important in same file:
           if they affect the same code path:
               → "Fixing {finding_A} may impact {finding_B} in same file"

6. Write cross-ref-summary.json:
   {
     "total_findings": {n},
     "cross_validated": {n},
     "conflicts": [{file, agents, descriptions}],
     "impact_chains": [{finding_A, finding_B, reason}],
     "high_confidence": [{finding, boosted_confidence}],
     "file_hotspots": [{file, agent_count, finding_count}]
   }

7. Inject cross-ref context into Phase 2 verification agents:
   "Cross-reference context:
    - This finding was flagged by {agents} ({count} agents)
    - Conflicts: {none | description}
    - Impact chains: {none | description}
    - Hotspot file: flagged by {n} agents across {m} findings"
```

**Cross-Reference Benefits:**
- Multi-agent confirmation → higher confidence
- Conflict detection → prevents contradictory fixes
- Impact chains → prevents fixing one bug while creating another
- Hotspot detection → files with many findings need special attention

### Phase 2: Verification (1-2 verification subagents)

For each IMPORTANT and NIT finding from Phase 1.5:

```
You are a verification agent. Your job is to independently verify or reject
a code review finding.

Finding to verify:
- Source agent: {agent_name}
- Cross-validated by: {other_agents}
- Severity: {severity}
- Description: {description}
- File:line: {file}:{line}
- In diff: {yes/no}
- Claimed trigger: {trigger_condition}

Tasks:
1. Read the file at the specified line and surrounding context
2. Understand the code flow
3. Determine if this is a REAL issue or FALSE POSITIVE
4. If real: construct the exact input/condition that triggers the bug
5. If false positive: explain precisely why it's not a real issue

Return:
- Verdict: CONFIRMED / FALSE_POSITIVE / NEEDS_MANUAL
- Confidence: HIGH / MEDIUM / LOW
- Explanation (1-3 sentences)
- If CONFIRMED: reproduction steps
```

**Verification strategy by depth level:**
- `low`: No verification
- `medium`: Verify IMPORTANT only
- `high`: Verify IMPORTANT + NIT
- `ultra`: Verify ALL findings, including PRE_EXISTING

### Phase 2.5: Feedback Collection (main session)

After verification, prepare feedback artifacts:

```
For each confirmed finding:
  - Log to .opencode/review_feedback.jsonl:
    {
      "finding_id": "{hash}",
      "agent": "{agent_name}",
      "confidence": {score},
      "severity": "{severity}",
      "cross_validated": {bool},
      "cross_validated_by": ["agent1", "agent2"],
      "file": "{path}",
      "line": {n},
      "timestamp": "{iso8601}"
    }
```

### Phase 3: Synthesis (main session)

Combine all verified findings into a structured report:

```markdown
## Deep Code Review v2.1 — {date} — Level: {depth}

### Scope
- Files reviewed: {n}
- Lines changed: {n}
- Agents launched: {n} (depth: {depth})
- History context: {n} files with git blame analysis
- Re-review: {yes/no} (review #{n} on this branch)
- Raw findings: {n}
- After deduplication: {n}
- Verified findings: {n}
- False positives filtered: {n}
- Pre-existing issues: {n}
- Stale docs detected: {n}

### Severity Summary (Claude Code Review format)
| Severity | File:Line | Issue |
|----------|-----------|-------|
| 🔴 Important | `file.py:120` | Fail-open slippage check |
| 🔴 Important | `file.py:265` | Inventory cap after buy |
| 🟡 Nit | `file.py:134` | Falsy `or` for 0.0 |
| 🟣 Pre-existing | `file.py:411` | Singleton pattern abuse |

### Confirmed Important Issues
1. **{issue}** — `{file}:{line}` [CONFIRMED-IMPORTANT]
   - Trigger: {when does this fire?}
   - Impact: {what breaks / how much money at risk}
   - Cross-validated by: {agents}
   - History context: {git blame notes}
   - Fix: {code change}
   - Suggestion: {committable diff if ≤5 lines, else "see description"}

### Confirmed Nits (max 5 inline, v2.1 cap)
1. **{issue}** — `{file}:{line}` [CONFIRMED-NIT]
2. **{issue}** — `{file}:{line}` [CONFIRMED-NIT]
3. **{issue}** — `{file}:{line}` [CONFIRMED-NIT]
4. **{issue}** — `{file}:{line}` [CONFIRMED-NIT]
5. **{issue}** — `{file}:{line}` [CONFIRMED-NIT]
{IF total_nits > 5: "plus {N - 5} similar items (style, naming, minor suggestions)"}

### Pre-existing Issues (not introduced by this change)
1. **{issue}** — `{file}:{line}` [PRE_EXISTING]

### Stale Documentation (v2.1)
1. **{doc_file}:{line}** — statement contradicted by change in `{code_file}`
   - Old: "{what the doc says}"
   - New: "{what the code now does}"

### Needs Manual Review
1. **{issue}** — `{file}:{line}` [UNVERIFIED]

### False Positives (filtered)
- ~~{finding}~~ — rejected by verification: {reason}

### Agent Statistics
| Agent | Raw | After Dedup | Confirmed | FP | Precision* |
|-------|-----|-------------|-----------|-----|-----------|
| Correctness | {n} | {n} | {n} | {n} | {pct}% |
| Security | {n} | {n} | {n} | {n} | {pct}% |
| Performance | {n} | {n} | {n} | {n} | {pct}% |
| Architecture | {n} | {n} | {n} | {n} | {pct}% |
| Domain | {n} | {n} | {n} | {n} | {pct}% |
| Test Coverage | {n} | {n} | {n} | {n} | {pct}% |
| Async Safety | {n} | {n} | {n} | {n} | {pct}% |
| DB Safety | {n} | {n} | {n} | {n} | {pct}% |
| API Safety | {n} | {n} | {n} | {n} | {pct}% |
| Config Safety | {n} | {n} | {n} | {n} | {pct}% |
| Error Recovery | {n} | {n} | {n} | {n} | {pct}% |
| Duplication | {n} | {n} | {n} | {n} | {pct}% |

*Precision from historical feedback (see .opencode/review_feedback.jsonl)

### Verdict: PASS / NEEDS WORK / BLOCK

**Blocking criteria (advisory philosophy):**
- BLOCK only when ALL of:
  1. Finding severity = IMPORTANT
  2. Confidence ≥ 90
  3. Cross-validated by ≥ 2 independent agents
- Otherwise: NEEDS WORK (advisory, does not block push)

### CI-Readable Output (v2.1)

Machine-parseable line appended to report (for GitHub Actions / git-gate):
```
<!-- deep-review-json: {"important":{n},"nit":{n},"pre_existing":{n},"stale_docs":{n},"verdict":"{PASS|NEEDS_WORK|BLOCK}","review_count":{n},"depth":"{level}"} -->
```

Parse with:
```bash
grep -oP '(?<=deep-review-json: ).*' review_report.md | jq '.important'
```
```

### Phase 3.5: Update Review History (main session)

After synthesis, update `.opencode/review_history.json`:

```json
{
  "branch": "{current_branch}",
  "review_count": {n},
  "last_review": "{iso8601}",
  "last_verdict": "{PASS|NEEDS_WORK|BLOCK}",
  "important_count": {n},
  "nit_count": {n}
}
```

This enables re-review convergence on subsequent runs.

## Git-Gate Integration (Advisory Philosophy)

**Claude Code Review philosophy:** "Findings are tagged by severity and don't
approve or block your PR, so existing review workflows stay intact."

**Our implementation:**
```
Pre-commit (LIGHT) → Pre-push (FULL) → Deep Review (OPTIONAL) → Push

Deep Review verdict:
- PASS → push allowed
- NEEDS WORK → push allowed (advisory), warning shown
- BLOCK → push blocked ONLY when:
  confidence ≥ 90 AND cross_validated_by ≥ 2 agents
```

This prevents false positives from blocking legitimate work while still
catching high-confidence, multi-confirmed critical issues.

## Per-Agent Precision Tracking

Store feedback in `.opencode/review_feedback.jsonl`. Monthly calculate:

```python
for agent in agents:
    feedback = read_jsonl(f".opencode/review_feedback.jsonl")
    agent_feedback = [f for f in feedback if f["agent"] == agent]
    fixed = sum(1 for f in agent_feedback if f.get("was_fixed"))
    dismissed = sum(1 for f in agent_feedback if f.get("was_dismissed"))
    precision = fixed / (fixed + dismissed) if (fixed + dismissed) > 0 else 0.5

    # Adjust confidence threshold per agent
    if precision < 0.4:
        agent.confidence_threshold = 90  # raise bar for low-precision agents
    elif precision > 0.8:
        agent.confidence_threshold = 70  # lower bar for high-precision agents
    else:
        agent.confidence_threshold = 80  # default
```

## Committable Suggestion Criteria

For auto-fix suggestions, follow Claude Code Review's rule:

```
If fix:
  - ≤5 lines
  - in one location (not scattered across files)
  - guaranteed to close the issue entirely (no follow-up needed)
→ Generate committable patch (unified diff)

Otherwise:
→ Text description only, NO auto-patch
  (risk: incomplete patch creates illusion of "fixed")
```

## Git Worktree Isolation

For ultra mode, isolate batches using git worktrees:

```bash
# Create isolated worktrees for each batch
git worktree add /tmp/review-batch1 HEAD
git worktree add /tmp/review-batch2 HEAD

# Batch 1 agents work in /tmp/review-batch1
# Batch 2 agents work in /tmp/review-batch2

# Cleanup after review
git worktree remove /tmp/review-batch1
git worktree remove /tmp/review-batch2
```

This prevents agents from interfering with each other's working directory.

## Integration Points

### With archy MCP
Use `archy_check` and `archy_cycles` as input for Agent 4 (Architecture).

### With semgrep MCP
Run `semgrep scan` as a pre-filter before Agent 2 (Security) to catch
known patterns, letting the agent focus on novel vulnerabilities.

### With git-gate skill
Add as Phase 2.5 in the git-gate pipeline:
```
Pre-commit (LIGHT) → Pre-push (FULL) → Deep Review (OPTIONAL) → Push
```

## Usage Examples

### Basic usage (high depth)
```
skill("deep-code-review")
```

### Ultra depth with specific files
```
Run deep-code-review ultra on src/core/target_sniping/sticker_cache.py
and src/core/target_sniping/filter.py
```

### Low depth (fast pre-push)
```
Run deep-code-review low on the current diff
```

## Comparison with Alternatives

| Feature | code-reviewer | deep-code-review v2.1 | Claude Code ultra |
|---------|--------------|----------------------|-------------------|
| Agents | 1 | 16 + history analyzer + research | Fleet (N) |
| Verification | None | Yes (configurable) | Yes (all findings) |
| Depth levels | None | low/med/high/ultra | low/med/high/ultra/x-high/ultra |
| Deduplication | No | Yes (file:line overlap) | Yes |
| Pre-existing detection | No | Yes (in_diff flag) | Yes (🟣 Pre-existing) |
| History analysis | No | Yes (git blame) | Yes |
| Feedback loop | No | Yes (👍/👎 + precision tracking) | Yes |
| REVIEW.md support | No | Yes | Yes |
| Cost estimate | No | Yes (Phase -1) | Yes |
| Agent assumptions | No | Yes (preamble) | Yes |
| Advisory philosophy | N/A | Yes (confidence≥90 + 2 agents) | Yes (never blocks) |
| Severity levels | CRITICAL/WARN/INFO | Important/Nit/Pre-existing | Important/Nit/Pre-existing |
| Committable suggestions | No | Yes (≤5 lines criteria) | Yes |
| Worktree isolation | No | Yes (ultra mode) | Yes (cloud sandbox) |
| **Re-review convergence** | No | **Yes (suppress nits)** | Yes |
| **Nit volume cap** | No | **Yes (max 5)** | Yes |
| **Skip rules** | No | **Yes (configurable)** | Yes |
| **Verification bar** | No | **Yes (evidence required)** | Yes |
| **Stale doc detection** | No | **Yes** | Yes |
| **CI-readable output** | No | **Yes (JSON comment)** | Yes (check run API) |
| **Cross-Reference Engine** | No | **Yes (Codex-style, v2.2)** | Yes (cloud fleet) |
| **Conflict detection** | No | **Yes** | Yes |
| **Impact chains** | No | **Yes** | No |
| Token cost | 1x | 6-12x | Cloud credits |
| Time | ~30s | ~2-5 min | ~5-10 min |
| PR mode | No | No (planned) | Yes |
| Use case | Quick check | Thorough audit | Production PR |

## Limitations

- **No cloud sandbox**: Agents run locally as subagents, not in isolated containers
- **No PR mode**: Reviews local diff, not GitHub PRs directly
- **Token cost**: 6-12x of single-agent review
- **Rate limits**: 6 parallel agents may hit provider limits (fallback to 3+3)
- **Verification is best-effort**: Complex bugs may not reproduce in static analysis

## Future Improvements

1. **PR mode**: Fetch PR diff from GitHub API instead of local git diff
2. **CI integration**: Run as GitHub Action on every PR
3. **Inline PR comments**: Post findings as inline comments on specific lines
4. **Thread resolution**: Auto-resolve threads when issue is fixed on push
5. **Analytics dashboard**: Review metrics, cost tracking, agent performance
6. **Custom agent prompts**: User-defined review focus areas
7. **Auto-fix mode**: Apply committable suggestions automatically (`--fix`)
8. **Effort levels**: Map depth levels to Claude Code effort levels

## Changelog

### v2.5 (2026-07-19)
- Improved research_context injection into ALL agents (6, 8, 10, 12, 13 now have it)
- Enhanced prompts with cross-reference instructions for all agents
- All 19 agents now have deep research integration
- 48 research_context references across 19 agents

### v2.4 (2026-07-19)
- Added Agent 13: Architecture Deep Analysis (design patterns, SOLID, DI, interfaces)
- Added Agent 14: Algorithm & Complexity Analysis (algorithm correctness, math precision)
- Added Agent 15: Pipeline & Data Flow Analysis (state machines, data transformations)
- Added Agent 16: Financial Instruments Analysis (Kelly, VaR, Sharpe, portfolio theory)
- Updated to 3 batches (16 agents total)
- Batch 3 specializes in deep structural/mathematical analysis

### v2.3 (2026-07-19)
- Added Phase 0.5: Deep Research Agent (CVE, vulnerability, pattern research)
- Added research_context injection into ALL agents (1-12)
- Added cross-reference with web sources for all findings
- Security agent now uses research_context instead of inline web-search
- All agents cross-reference with research findings
- Library vulnerability detection via web-search
- Python version issue detection
- Best practices verification from web sources

### v2.2 (2026-07-19)
- Added Cross-Reference Engine (Codex-style automatic cross-agent analysis)
- Added shared findings buffer (/tmp/opencode-review-xref/)
- Added conflict detection (agents disagree on same file)
- Added impact chain analysis (fixing A may affect B)
- Added hotspot file detection (files flagged by many agents)
- Updated all agent prompts to write findings to JSON buffer
- Cross-ref context injected into Phase 2 verification agents

### v2.1 (2026-07-19)
- Added re-review convergence (suppress nits on repeat reviews)
- Added Nit volume cap (max 5 inline per review)
- Added Skip rules (lockfiles, generated code, vendored deps)
- Added Verification bar (evidence-required: direct code citation)
- Added Stale documentation detection (CLAUDE.md/AGENTS.md contradictions)
- Added CI-readable output format (JSON comment for automation)
- Updated Phase 0 with re-review detection and skip rules
- Updated Phase 3 with Nit cap, stale docs, and CI output
- Added Phase 3.5 for review history tracking

### v2.0 (2026-07-18)
- Initial multi-agent architecture (12 agents + history analyzer)
- Deduplication engine
- Pre-existing bug detection
- Per-agent precision tracking
- REVIEW.md support
- Advisory philosophy (confidence≥90 + 2 agents)
- Cost estimation
- Git worktree isolation
