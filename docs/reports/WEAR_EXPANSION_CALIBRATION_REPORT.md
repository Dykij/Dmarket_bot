# WEAR_EXPANSION_CALIBRATION_REPORT.md
## Date: 2026-08-02 | Branch: feature/wear-expansion-calibration | READ-ONLY before review

---

## PHASE 0 — Safety guardrails

| Item | Status |
|------|--------|
| Branch | `feature/wear-expansion-calibration` created |
| Tag | `pre-wear-expansion` set |
| DRY_RUN | `true` (verified in .env) |
| PR | NOT opened (waiting for review) |

---

## PHASE 1 — Wear-expansion implementation

**File:** `src/core/target_sniping/cycle_orchestrator.py` (lines 329-370)

**Logic:** After demand expansion finds candidates, extract base skin name, query all 5 wear variants from `ctx.agg_prices`, pick best by `calculate_demand_score()`.

**Diff:** +42 lines (wear-expansion block after demand expansion)

**Key design choices:**
- Uses `ctx.agg_prices` (already fetched) — no extra API calls
- Extracts base skin by stripping ` (FN/MW/FT/WW/BS)` from title
- Skips non-weapon items (stickers, cases, pins) — no wear condition
- Logs `[WEAR-EXPAND]` for each skin checked

**Commit:** `275ec0b`

---

## PHASE 2 — Regression tests

**File:** `tests/unit/test_demand_strategy_v17.py` (TestWearExpansionMechanism class)

| Test | Description | Status |
|------|-------------|--------|
| test_wear_expansion_picks_best | WW chosen over FT when WW has higher Q | PASS |
| test_wear_expansion_4_fail_1_pass | Single passing wear is found | PASS |
| test_wear_expansion_all_fail | Keeps original when all fail | PASS |
| test_no_wear_expansion_for_stickers | Skips non-weapon items | PASS |
| test_base_skin_extraction | Extracts base name correctly | PASS |

**69/69 tests pass** (64 existing + 5 new)

---

## PHASE 3 — Calibration on historical decision_logs

### Data available

- **3380 demand entries** (all pass, 0 skip)
- **No spread_pct data** in details field (spread filter works but doesn't log the value)
- **No trade outcomes** (no data on whether items were sold profitably)
- **CRITICAL:** Without trade outcomes, calibration is distribution-based only, NOT profitability-based

### Global percentiles

| Metric | p10 | p25 | p50 | p75 | p90 |
|--------|-----|-----|-----|-----|-----|
| demand_ratio (Q) | 2.55 | 3.55 | **4.30** | 11.73 | 21.38 |
| obi_norm | 0.44 | 0.56 | **0.62** | 0.84 | 0.91 |

### Per-tier analysis

#### Tier < $2 (n=871)

| Metric | p10 | p25 | p50 | p75 | p90 | Current threshold |
|--------|-----|-----|-----|-----|-----|-------------------|
| demand_ratio | 1.63 | 1.65 | **3.16** | 4.63 | 11.73 | **1.5** |
| obi_norm | 0.24 | 0.25 | **0.52** | 0.64 | 0.84 | — |

**p50 demand_ratio = 3.16 vs threshold 1.5** → threshold is at p10 level. Quite宽松.

#### Tier $2-$5 (n=1025)

| Metric | p10 | p25 | p50 | p75 | p90 | Current threshold |
|--------|-----|-----|-----|-----|-----|-------------------|
| demand_ratio | 2.55 | 3.26 | **4.13** | 6.35 | 6.35 | **2.0** |
| obi_norm | 0.44 | 0.53 | **0.61** | 0.73 | 0.73 | — |

**p50 demand_ratio = 4.13 vs threshold 2.0** → threshold is at p10 level.

#### Tier > $5 (n=1484)

| Metric | p10 | p25 | p50 | p75 | p90 | Current threshold |
|--------|-----|-----|-----|-----|-----|-------------------|
| demand_ratio | 3.75 | 3.78 | **16.71** | 21.38 | 34.50 | **2.5** |
| obi_norm | 0.58 | 0.58 | **0.89** | 0.91 | 0.94 | — |

**p50 demand_ratio = 16.71 vs threshold 2.5** → threshold is at p10 level. Very宽松.

### Proposed thresholds (NOT applied — waiting for confirmation)

| Tier | Current min_q | Proposed min_q | Rationale |
|------|---------------|----------------|-----------|
| < $2 | 1.5 | **2.0** | p25 level (1.65) — tighter but still captures 75% of historical passes |
| $2-$5 | 2.0 | **3.0** | p25 level (3.26) — tighter |
| > $5 | 2.5 | **4.0** | p10 level (3.75) — much tighter (current is very宽松) |

**IMPORTANT CAVEAT:** These proposals are based on distribution analysis only. Without trade outcome data (profit/loss), we cannot confirm that tighter thresholds improve profitability. The current宽松 thresholds may be intentionally set to maximize opportunity discovery.

**Recommendation:** Do NOT change thresholds until:
1. Trade outcome logging is implemented (log whether each bought item was sold with profit)
2. At least 100 completed trades with outcome data are available
3. Profitability analysis confirms tighter thresholds → better returns

---

## PHASE 4 — Combined effect test

**NOT YET RUN** — requires live bot restart with wear-expansion enabled. Will be done after user reviews this report.

Expected effect:
- More wear-variant candidates (especially WW/BS for skins where FN/FT are expensive)
- Decision logs will show `[WEAR-EXPAND]` entries with best_wear selection

---

## Summary

| Phase | Status | Commit |
|-------|--------|--------|
| Phase 0 (Safety) | DONE | — |
| Phase 1 (Wear-expansion) | DONE | `275ec0b` |
| Phase 2 (Tests) | DONE | `275ec0b` |
| Phase 3 (Calibration) | DONE (analysis only) | — |
| Phase 4 (Combined test) | PENDING | — |

### What was applied

- Wear-expansion mechanism in `cycle_orchestrator.py`
- 5 regression tests

### What was NOT applied (waiting for confirmation)

- **Threshold calibration** — proposed tighter thresholds but NOT applied. Need trade outcome data first.
- **Phase 4 combined test** — needs live bot restart

### What needs user decision

1. **Thresholds:** Tighten now or wait for trade outcome data?
2. **Merge:** Merge `feature/wear-expansion-calibration` into main?
3. **Phase 4:** Run combined live test?

---

**Branch:** `feature/wear-expansion-calibration` (pushed, NOT merged)
**Tag:** `pre-wear-expansion` (rollback point)
**PR:** NOT opened (waiting for review)
