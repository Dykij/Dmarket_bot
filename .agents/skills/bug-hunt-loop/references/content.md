
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
