---
name: bug-hunt-loop
description: >
  Autonomous multi-agent bug hunting loop — 4 parallel agents scan code, logs,
  config, and dependencies for hidden errors. 8 analysis layers: SAST, SCA,
  DAST, Performance, Architecture, Data/Logs, Security, Skeptic Review.
  Runs cyclically until all critical bugs are fixed. Inspired by SkillsMP
  patterns: adversarial-investigation, multi-agent-orchestration,
  ecosystem-validation, stress-hunt.
  Trigger keywords: "bug hunt", "find bugs", "scan for errors",
  "autonomous fix", "баг-хантер", "найди баги", "исправь ошибки",
  "deep scan", "infrastructure audit".
---

# Bug Hunt Loop v3 — Multi-Agent Compose with Debate

Autonomous 4-agent cycle that continuously analyzes code, logs, config, and
dependencies. Each iteration runs 8 analysis layers in parallel, then feeds
findings through a Skeptic gate, Multi-Agent Debate, and Context-Aware Fix.

## Anti-Hallucination Rules (MANDATORY)

Every finding MUST pass before reporting:
1. **Source**: File actually read (not from memory)
2. **Citation**: `file:line` with direct code quote
3. **Reproduction**: Issue reproducible
4. **Confidence**: >90% only with direct evidence

## Scope Constraint (CRITICAL)

**DO NOT touch trading algorithm logic.** Targets ONLY:
- Environment variables, .env loading, config safety
- Import order and module initialization
- Error handling and resilience
- Code quality (lint, types, dead code)
- API safety (rate limits, timeouts, auth)
- Infrastructure stability (asyncio, SQLite, logging)
- Security (secrets, injection, dependencies)
- Performance (hot paths, resource leaks)

Trading logic (Kelly, spread, position sizing, OU, GARCH) — **OUT OF SCOPE**.

## Database Safety (MANDATORY)

Each parallel agent MUST use:
- **Separate SQLite connection** in WAL mode, OR
- **Temporary in-memory data** (no shared DB handles)
- NEVER share a single connection across concurrent agents

---

## Architecture: 4 Parallel Agents

```
┌─────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                          │
│  (main session — dispatches, collects, decides)         │
└────────┬──────────┬──────────┬──────────┬───────────────┘
         │          │          │          │
    ┌────▼────┐ ┌───▼────┐ ┌──▼─────┐ ┌──▼──────────┐
    │ Agent   │ │ Agent  │ │ Agent  │ │ Agent       │
    │ -SAST   │ │-Runtime│ │-Sec    │ │ -Observer   │
    │         │ │        │ │        │ │             │
    │ Static  │ │ Async  │ │ Config │ │ Skeptic     │
    │ Lint    │ │ API    │ │ Deps   │ │ Cross-ref   │
    │ Types   │ │ Errors │ │ CVE    │ │ Log stats   │
    └────┬────┘ └───┬────┘ └──┬─────┘ └──┬──────────┘
         │          │         │          │
         └──────────┴─────────┴──────────┘
                     │
              ┌──────▼──────┐
              │   SKEPTIC   │
              │    GATE     │
              │ (mandatory) │
              └──────┬──────┘
                     │
              ┌──────▼──────┐
              │    FIX &    │
              │   VERIFY    │
              └─────────────┘
```

---

## 8 Analysis Layers

### Layer 1: Static Analysis (SAST) — Agent-SAST

```bash
# Critical errors
ruff check src/ --select=E9,F63,F7,F82

# Unused imports
ruff check src/ --select=F401

# Import order
ruff check src/ --select=E402,I001

# Type safety (if ty available)
ty check src/ --project . 2>/dev/null || echo "ty not available"

# Complexity hotspots
ruff check src/ --select=C90 2>/dev/null || true
```

### Layer 2: Supply Chain Analysis (SCA) — Agent-Security

```bash
# Dependency vulnerabilities
pip-audit 2>/dev/null || pip install pip-audit && pip-audit

# Known CVEs in requirements
safety check -r requirements.txt 2>/dev/null || echo "safety not installed"

# Semgrep SAST scan
semgrep scan --config auto src/ --quiet 2>/dev/null || echo "semgrep not available"
```

### Layer 3: Dynamic/Runtime Analysis (DAST) — Agent-Runtime

Search patterns:
```bash
# Event loop issues
grep -rn "loop.is_closed\|get_event_loop\|get_running_loop" src/

# Resource leaks (unclosed sessions/connections)
grep -rn "ClientSession\|sqlite3.connect" src/ | grep -v "close\|__exit__\|async with"

# Bare except blocks (silently swallowed errors)
grep -rn "except.*pass\|except:$\|except Exception:$" src/

# Fire-and-forget tasks (GC risk)
grep -rn "asyncio.create_task\|asyncio.ensure_future" src/ | grep -v "_background_tasks\|_tasks\|task_ref\|_signal_tasks"
```

### Layer 4: Performance Analysis — Agent-Runtime

```bash
# Module-level heavy operations
grep -rn "^import numpy\|^import pandas\|^from sklearn" src/ | head -10

# Blocking calls in async context
grep -rn "time.sleep\|requests.get\|requests.post" src/ | grep -v "test\|#"

# SQLite lock contention
grep -rn "sqlite3.OperationalError\|database is locked" src/ logs/ 2>/dev/null
```

### Layer 5: Architecture Analysis — Agent-Observer

```bash
# Architecture health (if archy available)
archy score src/ 2>/dev/null || echo "archy not available"
archy check src/ 2>/dev/null || echo "archy not available"
archy cycles src/ 2>/dev/null || echo "archy not available"

# Circular imports
python -c "
import importlib, sys
sys.path.insert(0, '.')
for mod in ['src.config', 'src.telegram.notifier', 'src.core.autonomous_scanner']:
    try: importlib.import_module(mod)
    except Exception as e: print(f'{mod}: {e}')
" 2>&1
```

### Layer 6: Log Analysis — Agent-Observer

```bash
# Error frequency in logs
for pattern in "OfferNotFound" "403" "429" "TypeError" "KeyError" "disabled" "returned False"; do
  count=$(grep -rc "$pattern" logs/*.log 2>/dev/null | awk -F: '{s+=$2}END{print s+0}')
  echo "$pattern: $count occurrences"
done

# Recent critical errors
grep -i "critical\|fatal\|crash" logs/*.log 2>/dev/null | tail -10
```

### Layer 7: Security Audit — Agent-Security

```bash
# Hardcoded secrets
grep -rn "password\|secret\|api_key\|token" src/ | grep -v "getenv\|environ\|config\|#" | head -10

# SQL injection (f-strings in queries)
grep -rn "f\".*SELECT\|f\".*INSERT\|f\".*UPDATE\|f\".*DELETE" src/

# Unsafe deserialization
grep -rn "pickle.load\|yaml.load\|eval(" src/ | grep -v "test\|#"
```

### Layer 8: Skeptic Analysis (Devil's Advocate) — Agent-Observer

After EACH finding, ask:
1. "If we fix this, what other module could break?"
2. "Does this fix work in GitHub Actions (no .env)?"
3. "Does this fix work in Docker?"
4. "Could this introduce a race condition in asyncio?"
5. "Could this mask a real error?"
6. "Does this affect LiveShadow or position_guard?"

---

## Execution Protocol

### Phase 1: Parallel Dispatch

Spawn 4 agents simultaneously:

```
Agent-SAST:   Layer 1 (Static) + Layer 5 (Architecture)
Agent-Runtime: Layer 3 (DAST) + Layer 4 (Performance)
Agent-Security: Layer 2 (SCA) + Layer 7 (Security)
Agent-Observer: Layer 6 (Logs) + Layer 8 (Skeptic prep)
```

Each agent writes findings to a structured format:
```
SEVERITY: P0/P1/P2
FILE: path/to/file.py:42
BUG: description
EVIDENCE: direct code quote
LAYER: SAST|SCA|DAST|PERF|ARCH|LOG|SEC
```

### Phase 2: Skeptic Gate

Agent-Observer collects ALL findings from 3 other agents and runs Layer 8
skeptic analysis on each. Produces verdict:
- `SAFE_TO_FIX` — proceed
- `NEEDS_REDESIGN` — flag for manual review
- `OUT_OF_SCOPE` — skip (trading logic)
- `FALSE_POSITIVE` — discard

### Phase 2.5: Multi-Agent Debate (NEW — v3)

For every P0/P1 finding, spawn a **structured debate** between two agents:

```
┌─────────────┐     ┌─────────────┐
│  DEFENDER   │     │   CRITIC    │
│             │     │             │
│ Argues WHY  │     │ Argues WHY  │
│ current code│     │ it's a BUG  │
│ is correct  │     │ that MUST   │
│             │     │ be fixed    │
└──────┬──────┘     └──────┬──────┘
       │                   │
       └─────────┬─────────┘
                 │
          ┌──────▼──────┐
          │    JUDGE     │
          │              │
          │ Synthesizes  │
          │ both sides   │
          │ into verdict │
          └──────────────┘
```

**Defender** provides:
- `DEFENSE`: why current code is acceptable
- `RISK_OF_CHANGE`: what could break
- `ALTERNATIVE`: minimal change if needed

**Critic** provides:
- `ATTACK`: why this is a real bug
- `EVIDENCE`: concrete failure scenario
- `PROPOSED_FIX`: exact code change
- `CONFIDENCE`: 0-100%

**Judge** synthesizes:
- `DEFENDER_WINS`: keep current code
- `CRITIC_WINS`: apply fix
- `COMPROMISE`: apply modified fix

### Phase 3: Fix with Context Window (IMPROVED — v3)

Apply ONLY `SAFE_TO_FIX` + `CRITIC_WINS` findings. Rules:

1. **Context Window**: Read 3-5 lines BEFORE and AFTER the error line before fixing
2. **Auto-Tests**: Generate 2-3 pytest assertions that verify the fix prevents regression
3. Minimal changes
4. `os.getenv()` must have default value
5. `asyncio.create_task()` must store reference
6. After each edit: `python -m py_compile <file>`
7. After all edits: `ruff check <modified_files>`

**Context Window example:**
```python
# BEFORE fixing line 163, read lines 158-168:
158:     prices = [s["price"] for s in sales if s.get("price", 0) > 0]
159:     if len(prices) < 3:
160:         return None
161:     # BUG: np not imported at module level
162:     arr = np.array(prices, dtype=np.float64)  # ← fix target
163:     mean = np.mean(arr)
164:     if mean <= 0:
165:         return None
166:     daily_vol = np.std(arr, ddof=1) / mean
167:     return round(float(daily_vol * math.sqrt(annualize_factor)), 4)
```

**Auto-Test example:**
```python
# Generated assertion for the numpy fix:
def test_volatility_numpy_available():
    """Verify np is importable at module level (regression for F821)."""
    import importlib
    mod = importlib.import_module("src.analysis.microstructure.volatility")
    assert hasattr(mod, "np"), "numpy not available as module-level attribute"
```

### Phase 4: Verify

```bash
# Syntax
python -m py_compile src/__main__.py

# Lint
ruff check src/ --select=E9,F63,F7,F82

# No regressions
grep -rn "<old_pattern>" src/  # Should return nothing
```

### Phase 5: Iterate or Stop

**Continue if:** P0/P1 bugs remain, ruff errors, log failures
**Stop if:** All P0/P1 fixed, ruff clean, skeptic confirms stability

---

## Final Report Format

```markdown
# Bug Hunt Report v3 — YYYY-MM-DD

## Agent Summary
| Agent | Layer | Findings | Fixed | False+ |
|-------|-------|----------|-------|--------|
| SAST | Static+Arch | N | N | N |
| Runtime | DAST+Perf | N | N | N |
| Security | SCA+Sec | N | N | N |
| Observer | Logs+Skeptic | N | N | N |

## Debate Summary
| Finding | Defender | Critic | Judge Verdict |
|---------|----------|--------|---------------|
| [P0] ... | Acceptable | Real bug | CRITIC_WINS |
| [P1] ... | Tradeoff | Must fix | COMPROMISE |

## Fixed Bugs (with Context Window + Auto-Tests)
### [SEVERITY] Description
- File:line, Bug, Context (3-5 lines), Fix, Assertions generated

## Skeptic Analysis Log
(Every adversarial question and its resolution)

## Conclusion
- Bot readiness
- Remaining risks
- Next steps
```

---

## MCP Integration

| Tool | Agent | Purpose |
|------|-------|---------|
| ruff | SAST | Lint, complexity |
| ty | SAST | Type checking |
| semgrep | Security | SAST scan, CVE |
| pip-audit | Security | Dependency CVE |
| archy | Observer | Architecture health |
| grep/glob | All | Code search |
| read/edit | All | File operations |
| sqlite | Runtime | DB integrity |
| sequential-thinking | Observer | Skeptic reasoning |

---

## Execution Commands

```bash
# Primary: workflow with v3 features (context window, debate, auto-tests)
workflow run bug-hunt-loop-v3

# Slash command (after restart):
/bug-hunt

# Tab mode: switch to Compose-Hunter agent in TUI
# Press Tab → select "Compose-Hunter"

# Legacy v2 workflow (without debate/context):
workflow run bug-hunt-loop
```

## Monitoring

During execution, each agent logs with prefix:
- `[SAST]` — static analysis findings
- `[Runtime]` — DAST/performance findings
- `[Security]` — SCA/security findings
- `[Observer]` — log stats + skeptic verdicts
- `[Skeptic]` — adversarial questions
- `[Debate]` — Defender vs Critic arguments
- `[Compose]` — orchestrator phase transitions

Watch progress: `tail -f logs/bug_hunt.log` or observe workflow phase transitions.
