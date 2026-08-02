# DEAD_CODE_INTEGRATION_PLAN.md — Полный аудит "что не работает/отключено"
## Date: 2026-08-02 | Branch: feature/dead-code-integration-plan | READ-ONLY

---

## PHASE 0 — Safety guardrails ✅

| Item | Status |
|------|--------|
| Branch | `feature/dead-code-integration-plan` |
| Tag | `pre-dead-code-plan` |
| DRY_RUN | `true` |
| PR | NOT opened |

---

## PHASE 1 — Полная инвентаризация reachability

### ORPHANED FILES (zero calls from trading path)

| # | File | Lines | Status | Recommendation | Priority |
|---|------|-------|--------|---------------|----------|
| 1 | `value_pipelines.py` | 299 | **ORPHANED** | **АРХИВИРОВАТЬ** — дубль filter.py:604-622 + demand_strategy.py. Ноль вызовов. | P2 |
| 2 | `rare_valuation.py` | 92 | **ORPHANED** | **АРХИВИРОВАТЬ** — `self.valuation = RareValuationEngine()` создан в core.py:67, но НИГДЕ не вызывается. Дубль pricing.py. | P2 |
| 3 | `pair_trading.py` | ~200 | **ORPHANED** | **АРХИВИРОВАТЬ** — неприменим к one-asset OBI стратегии. | P2 |
| 4 | `spread_optimizer.py` | ~150 | **ORPHANED** | **АРХИВИРОВАТЬ** — дубль sell_optimizer.py. | P2 |
| 5 | `garch.py` | ~230 | **ORPHANED** | **ОСТАВИТЬ** — кандидат на замену EWMA в position_guard.py. Точка: `position_guard.py:45`. | P1 |
| 6 | `ou_process.py` | ~300 | **ORPHANED** | **ОСТАВИТЬ** — кандидат на mean-reversion сигнал. Точка: `demand_strategy.py:120`. | P1 |
| 7 | `event_driven.py` | ~380 | **ORPHANED** | **ОСТАВИТЬ** — кандидат на сезонную корректировку. Точка: `filter.py:354`. | P2 |
| 8 | `sell_optimizer.py` | ~140 | **ORPHANED** | **ОСТАВИТЬ** — кандидат на оптимизацию list_price. Точка: `filter.py:611`. | P1 |
| 9 | `multi_source_oracle.py` | ~300 | **ORPHANED** (wiring bug) | **ОСТАВИТЬ** — `self.multi_source_oracle = None` в core.py:82. Официально deprecated для demand strategy. | P2 |

**Total orphaned: ~2,093 lines of code**

### DISABLED FLAGS (Config flags = False)

| # | Flag | Default | Used in | Lines of code gated | Effect when ON | Risk | Priority |
|---|------|---------|---------|--------------------|----|------|----------|
| 1 | `STRICT_MICROSTRUCTURE_FILTERS` | **False** | microstructure_pipeline.py:78, filter.py:725 | ~500 lines (16 filters) | Enables VPIN, Hawkes, Bollinger, DEMA, MACD, HMM, Hurst filters | **HIGH** — tested with 10/20 pass rate, may reduce candidates | P1 |
| 2 | `USE_LIQUIDITY_FILTER` | **False** | filter.py:308 | ~20 lines | Enables cross-market liquidity check | LOW — only affects cross-market path | P2 |
| 3 | `ORACLE_ENABLED_FOR_DEMAND` | **False** | config.py:161 | 0 lines (no code uses it) | Nothing — dead flag | NONE | P2 |
| 4 | `VOLUME_CLOCK_ENABLED` | **False** | config.py:171 | 0 lines (no code uses it) | Nothing — dead flag | NONE | P2 |
| 5 | `VPIN_GATE_ENABLED` | **False** | config.py:173 | 0 lines (no code uses it) | Nothing — dead flag | NONE | P2 |

### ENABLED FLAGS (Config flags = True, actively used)

| # | Flag | Default | Used in | Status |
|---|------|---------|---------|--------|
| 1 | `DEMAND_STRATEGY_ENABLED` | True | demand_strategy.py, cycle_orchestrator.py | **ACTIVE** — primary strategy |
| 2 | `STICKER_COMBO_ENABLED` | True | filter.py:608, sticker_cache.py | **ACTIVE** — luxury rejection + value calc |
| 3 | `KELLY_ENABLED` | True | position_guard.py | **ACTIVE** — position sizing |
| 4 | `DRAWDOWN_FREEZE_ENABLED` | True | position_guard.py | **ACTIVE** — risk management |
| 5 | `SPREAD_ENTROPY_ENABLED` | True | microstructure_pipeline.py | **ACTIVE** — spread filter |
| 6 | `PVC_ENABLED` | True | demand_strategy.py | **ACTIVE** — price-volume correlation |
| 7 | `GARCH_PVC_ENABLED` | True | config.py:181 ONLY | **DEAD FLAG** — default=True but zero code checks it |
| 8 | `HMM_VPIN_ENABLED` | True | config.py:183 ONLY | **DEAD FLAG** — default=True but zero code checks it |
| 9 | `HAWKES_ENTROPY_ENABLED` | True | config.py:184 ONLY | **DEAD FLAG** — default=True but zero code checks it |
| 10 | `SEASONAL_TIMING_ENABLED` | True | filter.py:354 | **ACTIVE** — seasonal adjustment |
| 11 | `FILLER_TRACKING_ENABLED` | True | filter.py:576 | **ACTIVE** — filler detection |
| 12 | `FLOAT_PREMIUM_ENABLED` | True | pricing.py | **ACTIVE** — float premium |
| 13 | `PATTERN_PREMIUM_ENABLED` | True | pricing.py | **ACTIVE** — pattern premium |

### NOT DUPLICATES (confirmed)

| Component A | Component B | Are they duplicates? |
|-------------|-------------|---------------------|
| `RiskManager.record_trade_outcome()` | `ProfitTracker.record_buy/record_sell()` | **NO** — different purposes: RiskManager tracks PnL for risk limits (drawdown, circuit breaker); ProfitTracker stores persistent history for calibration |
| `stickers_evaluator.py` | `sticker_cache.py` | **NO** — different layers: evaluator calculates USD value; cache adds luxury rejection + premium multiplier |
| `demand_strategy.py` OBI | `microstructure_pipeline.py` OBI | **YES (partial)** — both calculate OBI. demand_strategy is always-active; microstructure is gated by STRICT_MICROSTRUCTURE_FILTERS. Need consolidation. |

---

## PHASE 2 — Формулы и алгоритмы: включены, но не откалиброваны

### Hardcoded constants requiring calibration

| File | Constant | Current value | Last calibrated | Trade outcome data? | Notes |
|------|----------|---------------|-----------------|---------------------|-------|
| `demand_strategy.py:54` | `min_demand_ratio` (tier <$2) | 1.5 | Never (hardcoded) | **NOW AVAILABLE** via profit_tracker | p50=3.16, threshold at p10 level |
| `demand_strategy.py:61` | `min_demand_ratio` (tier $2-5) | 2.0 | Never | **NOW AVAILABLE** | p50=4.13, threshold at p10 level |
| `demand_strategy.py:68` | `min_demand_ratio` (tier >$5) | 2.5 | Never | **NOW AVAILABLE** | p50=16.71, threshold at p10 level |
| `demand_strategy.py:147` | `min_liquidity` (cheap) | 3 | Never | **NOW AVAILABLE** | |
| `demand_strategy.py:149` | `min_liquidity` (mid) | 5 | Never | **NOW AVAILABLE** | |
| `demand_strategy.py:151` | `min_liquidity` (expensive) | 10 | Never | **NOW AVAILABLE** | |
| `filter.py:268` | `MIN_BID_ASK_COUNT` | Config | Never | **NOW AVAILABLE** | |
| `pricing.py:22` | `_FLOAT_PREMIUM_TABLE` | 6 tiers | Never | No | Float premiums (0.5x-5.0x) |
| `pricing.py:40` | `_PHASE_PREMIUM` | 6 phases | Never | No | Ruby/Sapphire/Emerald premiums |
| `position_guard.py` | `KELLY_FRACTION` | 0.5 (Half Kelly) | Never | **NOW AVAILABLE** | |
| `filter.py:611` | `sticker_value * 0.5` | 50% | Never | No | Sticker value applied to list price |

### Calibration readiness

**After 20-30 real trades** (via profit_tracker), can calibrate:
- `min_demand_ratio` per tier — correlate Q with actual profit/loss
- `min_liquidity` per tier — correlate volume with trade success
- `KELLY_FRACTION` — optimize based on actual win rate

**Cannot calibrate yet** (no trade outcome data):
- Float/pattern premiums — need sold items with float data
- Sticker value discount (50%) — need sold items with sticker data

---

## PHASE 3 — План интеграции

### P0 — Влияет на прибыльность напрямую

**(Нет P0 элементов — все критические компоненты уже активны)**

### P1 — Улучшает качество сигнала

| # | Element | Integration point | Expected effect | Risk | Lines |
|---|---------|-------------------|-----------------|------|-------|
| 1 | **GARCH volatility** | `position_guard.py:45` — replace EWMA with GARCH for items with >30 obs | Better volatility clustering detection, tighter stop-losses | LOW — fallback to EWMA if <30 obs | ~230 |
| 2 | **OU mean-reversion** | `demand_strategy.py:120` — add reversion signal to demand score | Catches mean-reverting items (H < 0.5) that OBI misses | MEDIUM — new signal type, needs testing | ~300 |
| 3 | **Sell optimizer** | `filter.py:611` — replace `list_price = best_bid - discount` with ternary search | Optimal sell price via demand curve estimation | LOW — only affects list_price calculation | ~140 |
| 4 | **STRICT_MICROSTRUCTURE_FILTERS** | Already wired at `microstructure_pipeline.py:78` | Enables 16 microstructure filters (VPIN, Hawkes, Bollinger, etc.) | **HIGH** — tested with 10/20 pass rate. May reduce candidates significantly. Enable via .env.local, NOT default. | ~500 |

### P2 — Nice to have, низкий эффект

| # | Element | Integration point | Expected effect | Risk | Lines |
|---|---------|-------------------|-----------------|------|-------|
| 5 | **Event-driven** | `filter.py:354` — seasonal adjustment already active; event calendar would add Major/Sale awareness | Position sizing adjustment before CS2 Majors | LOW — informational only | ~380 |
| 6 | **USE_LIQUIDITY_FILTER** | `filter.py:308` — already wired | Cross-market liquidity check | LOW — only affects cross-market path | ~20 |
| 7 | **Dead flags cleanup** | `config.py` — remove ORACLE_ENABLED_FOR_DEMAND, VOLUME_CLOCK_ENABLED, VPIN_GATE_ENABLED | Cleaner config, less confusion | NONE — flags do nothing | 3 lines |

### Архивировать (безусловно)

| # | File | Lines | Reason |
|---|------|-------|--------|
| 1 | `value_pipelines.py` | 299 | Zero calls, duplicate of filter.py + demand_strategy.py |
| 2 | `rare_valuation.py` | 92 | Imported but never called, duplicate of pricing.py |
| 3 | `pair_trading.py` | ~200 | Not applicable to one-asset OBI strategy |
| 4 | `spread_optimizer.py` | ~150 | Duplicate of sell_optimizer.py |

**Total to archive: ~741 lines**

---

## PHASE 4 — Итоговая матрица

### Summary by category

| Category | Files | Lines | Action |
|----------|-------|-------|--------|
| **Active (working)** | 25 | ~4,500 | Keep as is |
| **Gated (flag=OFF, code exists)** | 3 | ~520 | Enable selectively |
| **Orphaned (zero calls, planned)** | 5 | ~1,470 | Keep for future integration |
| **Orphaned (zero calls, archive)** | 4 | ~741 | Archive to `_archived/` |
| **Dead flags (no code)** | 3 | 3 | Remove from config |

### Integration roadmap

```
Phase 1 (now): Archive 4 dead files (value_pipelines, rare_valuation, pair_trading, spread_optimizer)
Phase 2 (after 20-30 trades): Calibrate demand thresholds using profit_tracker data
Phase 3 (after calibration): Integrate GARCH + sell_optimizer + OU process
Phase 4 (selective): Enable STRICT_MICROSTRUCTURE_FILTERS via .env.local (NOT default)
Phase 5 (optional): Event-driven calendar integration
```

### What was already resolved in previous sessions

- **Agent skins**: Analysis complete, recommend adding to diversity-scan (see FULL_AUDIT_REPORT.md)
- **Wear-expansion**: Implemented in feature/wear-expansion-calibration (commit 275ec0b)
- **Weapon diversity**: Implemented in feature/weapon-diversity-stickers (commit 0c6712c)
- **Sticker premium**: Current logic correct — $0.05 sticker → $0.0025 added (negligible). No change needed.
- **Luxury rejection**: Connected in v18.1 (filter.py:610)
- **Trade history**: Implemented in feature/trade-history-tracking (commit 44f07b2)

---

## ОТЧЁТ: Что можно безопасно архивировать vs подключить vs калибровать

### Безопасно архивировать (нет риска)
- `value_pipelines.py` — zero calls, full duplicate
- `rare_valuation.py` — imported but never called
- `pair_trading.py` — not applicable
- `spread_optimizer.py` — duplicate of sell_optimizer

### Стоит подключить (после тестирования)
- `garch.py` → position_guard.py (P1, LOW risk)
- `sell_optimizer.py` → filter.py (P1, LOW risk)
- `ou_process.py` → demand_strategy.py (P1, MEDIUM risk)

### Требует калибровки перед подключением
- `STRICT_MICROSTRUCTURE_FILTERS` — tested 10/20 pass rate, may reduce candidates
- Demand thresholds (min_demand_ratio, min_liquidity) — need trade outcome data
- Kelly fraction — need win rate data

### Не трогать (deprecated/неактуально)
- `multi_source_oracle.py` — wiring bug, officially deprecated for demand strategy
- `ORACLE_ENABLED_FOR_DEMAND` — dead flag, no code uses it

---

**Branch:** `feature/dead-code-integration-plan` (pushed, NOT merged)
**PR:** NOT opened (waiting for review)
