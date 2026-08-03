# FULL_AUDIT_REPORT.md — Полный файловый аудит + агенты + стикеры
## Date: 2026-08-02 | Branch: feature/full-audit-agents-stickers | READ-ONLY

---

## PHASE 0 — Safety guardrails

| Item | Status |
|------|--------|
| Branch | `feature/full-audit-agents-stickers` ✅ |
| Tag | `pre-full-audit` ✅ |
| DRY_RUN | `true` ✅ |
| PR | NOT opened ✅ |

---

## PHASE 1-2 — Файловый аудит src/ (207 файлов)

### Категория: Торговая логика (core/target_sniping/)

| Файл | Назначение | Из цикла? | Флаг | Статус |
|------|-----------|-----------|------|--------|
| `core.py` | SnipingLoop — main trading loop | Прямой | — | **ACTIVE** |
| `cycle_orchestrator.py` | 6-stage pipeline orchestrator | Прямой | — | **ACTIVE** |
| `filter.py` | _evaluate_candidate — 21 filter stages | Прямой | — | **ACTIVE** |
| `demand_strategy.py` | OBI demand scoring | Прямой | DEMAND_STRATEGY_ENABLED | **ACTIVE** |
| `position_guard.py` | Kelly sizing, drawdown freeze | Прямой | — | **ACTIVE** |
| `microstructure_pipeline.py` | 16 microstructure filters | Прямой | STRICT_MICROSTRUCTURE_FILTERS | **GATED** |
| `ranking.py` | Candidate ranking by score | Прямой | — | **ACTIVE** |
| `pricing.py` | Float/pattern premiums | Прямой | — | **ACTIVE** |
| `scheduler.py` | Cycle scheduling | Прямой | — | **ACTIVE** |
| `item_utils.py` | Item title extraction | Прямой | — | **ACTIVE** |
| `sticker_cache.py` | Luxury sticker rejection | Прямой (filter.py:610) | STICKER_COMBO_ENABLED | **ACTIVE** (v18.1) |
| `stickers_evaluator.py` | Sticker value calculation | Прямой (filter.py:608) | STICKER_COMBO_ENABLED | **ACTIVE** |
| `value_pipelines.py` | Value/spread signal pipeline | **НЕТ вызовов** | VALUE_SCAN_ENABLED | **ORPHANED** |
| `validations.py` | Validation thresholds | Прямой | — | **ACTIVE** |
| `underpriced.py` | Underpriced detection | Прямой (filter.py:438) | — | **ACTIVE** |
| `autonomous_scanner.py` | Background scanner | Прямой | — | **ACTIVE** |

### Категория: Анализ (analysis/)

| Файл | Назначение | Из цикла? | Флаг | Статус |
|------|-----------|-----------|------|--------|
| `microstructure/obi.py` | OBI/OFI/Queue Imbalance | Прямой (demand_strategy.py) | — | **ACTIVE** |
| `microstructure/vpin.py` | VPIN toxicity | Прямой (microstructure_pipeline.py) | STRICT_MICROSTRUCTURE_FILTERS | **GATED** |
| `microstructure/hawkes.py` | Hawkes process intensity | Прямой (microstructure_pipeline.py) | STRICT_MICROSTRUCTURE_FILTERS | **GATED** |
| `microstructure/bollinger.py` | Bollinger Bands | Прямой (microstructure_pipeline.py) | STRICT_MICROSTRUCTURE_FILTERS | **GATED** |
| `microstructure/dema.py` | DEMA/TEMA crossovers | Прямой (microstructure_pipeline.py) | STRICT_MICROSTRUCTURE_FILTERS | **GATED** |
| `microstructure/macd.py` | MACD signal | Прямой (microstructure_pipeline.py) | STRICT_MICROSTRUCTURE_FILTERS | **GATED** |
| `microstructure/hmm_regime.py` | HMM regime detection | Прямой (microstructure_pipeline.py) | STRICT_MICROSTRUCTURE_FILTERS | **GATED** |
| `algo_pack/ewma.py` | EWMA volatility | Прямой (position_guard.py) | — | **ACTIVE** |
| `algo_pack/garch_forecast.py` | GARCH(1,1) volatility | **НЕТ вызовов** | GARCH_PVC_ENABLED | **ORPHANED** |
| `algo_pack/ou_process.py` | Ornstein-Uhlenbeck mean-reversion | **НЕТ вызовов** | — | **ORPHANED** |
| `algo_pack/pair_trading.py` | Cointegration arbitrage | **НЕТ вызовов** | — | **ORPHANED** |
| `algo_pack/event_driven.py` | CS2 Major/Steam Sale calendar | **НЕТ вызовов** | — | **ORPHANED** |
| `algo_pack/sell_optimizer.py` | Sell price optimization | **НЕТ вызовов** | — | **ORPHANED** |
| `algo_pack/spread_optimizer.py` | Spread optimization | **НЕТ вызовов** | — | **ORPHANED** |
| `algo_pack/bayesian_stats.py` | Bayesian statistics | Прямой (filter.py:177) | — | **ACTIVE** |
| `algo_pack/trend_strength.py` | Trend strength | Прямой (filter.py) | — | **ACTIVE** |
| `algo_pack/regime_detector.py` | Regime detection | Прямой (filter.py) | — | **ACTIVE** |
| `algo_pack/signals.py` | Signal generation | Прямой (filter.py) | — | **ACTIVE** |
| `algo_pack/volatility.py` | Volatility calculation | Прямой (position_guard.py) | — | **ACTIVE** |
| `algo_pack/volume.py` | Volume analysis | Прямой (filter.py) | — | **ACTIVE** |
| `algo_pack/hurst.py` | Hurst exponent | Прямой (microstructure_pipeline.py) | STRICT_MICROSTRUCTURE_FILTERS | **GATED** |
| `seasonal.py` | Seasonal patterns | Прямой (filter.py:358) | — | **ACTIVE** |

### Категория: Аналитика (analytics/)

| Файл | Назначение | Из цикла? | Флаг | Статус |
|------|-----------|-----------|------|--------|
| `stickers_evaluator.py` | Sticker value + combo premium | Прямой (filter.py:608) | STICKER_COMBO_ENABLED | **ACTIVE** |
| `rare_valuation.py` | Float/pattern/phase scoring | **НЕТ вызовов** | — | **ORPHANED** |
| `filler_tracker.py` | Filler item tracking | Прямой (filter.py:576) | — | **ACTIVE** |

### Категория: API (api/)

| Файл | Назначение | Из цикла? | Флаг | Статус |
|------|-----------|-----------|------|--------|
| `dmarket_api_client/core.py` | HTTP client + Ed25519 signing | Прямой | — | **ACTIVE** |
| `dmarket_api_client/market.py` | Market endpoints | Прямой | — | **ACTIVE** |
| `dmarket_api_client/account.py` | Account/balance endpoints | Прямой | — | **ACTIVE** |
| `dmarket_api_client/trading.py` | Buy/sell/reprice endpoints | Прямой | — | **ACTIVE** |
| `multi_source_oracle.py` | Multi-market oracle | **НЕТ вызовов** (wiring bug) | MULTI_SOURCE_ORACLE_ENABLED | **ORPHANED** (wiring bug) |
| `oracle_factory.py` | Oracle factory | Прямой (cycle_orchestrator.py:94) | — | **ACTIVE** |
| `dmarket_parser.py` | Rust parser bridge | Прямой | — | **ACTIVE** |

### Категория: Риск (risk/)

| Файл | Назначение | Из цикла? | Флаг | Статус |
|------|-----------|-----------|------|--------|
| `price_validator.py` | Price validation | Прямой | — | **ACTIVE** |
| `circuit_breaker.py` | Circuit breaker | Прямой | — | **ACTIVE** |
| `lock_tracker.py` | Item lock tracking | Прямой | — | **ACTIVE** |

### Категория: БД (db/)

| Файл | Назначение | Из цикла? | Флаг | Статус |
|------|-----------|-----------|------|--------|
| `price_history.py` | SQLite price history + decision_logs | Прямой | — | **ACTIVE** |

### Категория: Telegram (telegram/)

| Файл | Назначение | Из цикла? | Флаг | Статус |
|------|-----------|-----------|------|--------|
| `reporter.py` | Telegram notifications | Прямой | — | **ACTIVE** |
| `control_bot/` | Bot control commands | Прямой | — | **ACTIVE** |

### Категория: Utils (utils/)

| Файл | Назначение | Из цикла? | Флаг | Статус |
|------|-----------|-----------|------|--------|
| `vault.py` | Secret management | Прямой | — | **ACTIVE** |
| `clock_sync.py` | Clock synchronization | Прямой | — | **ACTIVE** |
| `health_server.py` | Health check endpoint | Прямой | — | **ACTIVE** |
| `decimal_helpers.py` | Decimal utilities | Прямой | — | **ACTIVE** |
| `notifier.py` | Notification abstraction | Прямой | — | **ACTIVE** |

---

## Summary: ORPHANED modules (7 файлов)

| Файл | Назначение | Рекомендация |
|------|-----------|-------------|
| `value_pipelines.py` | Value/spread signal pipeline | **АРХИВИРОВАТЬ** — дубль filter.py:604-622 (sticker value) + demand_strategy.py (OBI). Ноль вызовов из торгового пути. |
| `rare_valuation.py` | Float/pattern/phase scoring | **АРХИВИРОВАТЬ** — дубль pricing.py::get_float_premium + get_pattern_premium. Ноль вызовов. |
| `algo_pack/garch_forecast.py` | GARCH(1,1) volatility | **ОСТАВИТЬ** — кандидат на замену EWMA в position_guard.py. Пометить как "planned integration". |
| `algo_pack/ou_process.py` | OU mean-reversion | **ОСТАВИТЬ** — кандидат на mean-reversion сигнал в demand_strategy.py. |
| `algo_pack/pair_trading.py` | Cointegration arbitrage | **АРХИВИРОВАТЬ** — неприменим к one-asset OBI стратегии. |
| `algo_pack/event_driven.py` | CS2 Major calendar | **ОСТАВИТЬ** — кандидат на сезонную корректировку. |
| `algo_pack/sell_optimizer.py` | Sell price optimization | **ОСТАВИТЬ** — кандидат на замену list_price = best_bid - discount. |
| `algo_pack/spread_optimizer.py` | Spread optimization | **АРХИВИРОВАТЬ** — дубль sell_optimizer. |
| `multi_source_oracle.py` | Multi-market oracle | **ОСТАВИТЬ** — wiring bug (self.multi_source_oracle = None). Официально deprecated для demand strategy. |

---

## PHASE 3 — Агент-скины: RAW данные

### Top-12 agents by demand score

| # | Title | Bid | Ask | BC | AC | Spread | Q | Score |
|---|-------|-----|-----|----|----|--------|---|-------|
| 1 | **Sir Bloody Skullhead Darryl** | $34.71 | $35.58 | 432 | 90 | 2.4% | **4.8** | **1336** |
| 2 | Bloody Darryl The Strapped | $32.10 | $33.14 | 308 | 73 | 3.1% | 4.2 | 754 |
| 3 | Sir Bloody Loudmouth Darryl | $55.23 | $56.86 | 267 | 69 | 2.9% | 3.9 | 559 |
| 4 | Getaway Sally | $71.73 | $75.45 | 257 | 67 | 4.9% | 3.8 | 530 |
| 5 | Safecracker Voltzmann | $17.38 | $18.00 | 324 | 99 | 3.4% | 3.3 | 503 |
| 6 | Sir Bloody Silent Darryl | $32.12 | $33.10 | 336 | 115 | 3.0% | 2.9 | 428 |
| 7 | Soldier \| Phoenix | $4.56 | $4.94 | 380 | 153 | 7.7% | 2.5 | 365 |
| 8 | 1st Lieutenant Farlow | $8.69 | $9.20 | 231 | 190 | 5.5% | 1.2 | 0 |
| 9 | Operator \| FBI SWAT | $9.80 | $9.99 | 240 | 264 | 1.9% | 0.9 | 0 |
| 10 | Enforcer \| Phoenix | $4.97 | $5.14 | 299 | 152 | 3.3% | 2.0 | 0 |
| 11 | Seal Team 6 Soldier | $9.85 | $10.21 | 131 | 149 | 3.5% | 0.9 | 0 |
| 12 | Number K | $46.29 | $47.89 | 411 | 252 | 3.3% | 1.6 | 0 |

### Вердикт по агентам

**7/12 агентов имеют score > 0.** Ликвидность сопоставима с дешёвым оружием:
- Spreads: 2-8% (tight)
- Volume: BC131-432, AC 67-264 (decent)
- Top scorer: Sir Bloody Skullhead Darryl ($35, Q=4.8, score=1336)

**Рекомендация: ДОБАВИТЬ агентов как категорию в diversity-scan.** Ликвидность достаточная. Агенты — отдельная категория предметов на DMarket, не weapon skins.

---

## PHASE 4a — Sticker premium: tier analysis

### Existing code (stickers_evaluator.py:354-396)

```python
def calculate_added_value(self, stickers, weapon_name=""):
    for s in stickers:
        unapplied_price = self._sticker_price(s)
        spp = self.spp_rare_bonus if unapplied_price > 1000.0 else self.spp_base
        # spp_base = 0.05, spp_rare_bonus = 0.10
```

**Finding:** The code already differentiates by tier:
- `unapplied_price > $1000` → `spp_rare_bonus = 0.10` (10% of sticker value)
- `unapplied_price <= $1000` → `spp_base = 0.05` (5% of sticker value)

**But:** There's NO lower bound. A $0.05 sticker gets the same 5% treatment as a $50 sticker. This means:
- $0.05 sticker → $0.0025 added value (negligible)
- $50 sticker → $2.50 added value (meaningful)

**The current logic is CORRECT** — cheap stickers contribute negligible value. No change needed.

---

## PHASE 4b — Stickers как отдельный товар: RAW данные

### Top-15 non-luxury stickers by volume

| # | Title | Bid | Ask | BC | AC | Spread | Q | Score |
|---|-------|-----|-----|----|----|--------|---|-------|
| 1 | Paris 2023 Contenders Capsule | $0.12 | $0.15 | 458 | 8730 | 20.0% | — | 0 |
| 2 | Rainbow Route (Holo) | $1.67 | $1.30 | 376 | 580 | -28.5% | — | 0 |
| 3 | Say Cheese (Holo) | $0.77 | $0.92 | 372 | 292 | 16.3% | — | 0 |
| 4 | Winding Scorch | $0.23 | $0.25 | 211 | 375 | 8.0% | — | 0 |
| 5 | **Bolt Strike** | $0.15 | $0.17 | 330 | 158 | 11.8% | **2.1** | **118** |
| 6 | Quick Peek | $0.30 | $0.49 | 239 | 222 | 38.8% | — | 0 |
| 7 | paiN Gaming \| Austin 2025 | $0.02 | $0.05 | 33 | 367 | 60.0% | — | 0 |
| 8 | 3DMAX \| Austin 2025 | $0.02 | $0.05 | 97 | 298 | 60.0% | — | 0 |
| 9 | Hydro Wave | $0.27 | $0.37 | 115 | 238 | 27.0% | — | 0 |
| 10 | Eternal Fire \| Copenhagen 2024 | $0.08 | $0.12 | 230 | 102 | 33.3% | — | 0 |
| 11 | Evidence (Holo) | $0.65 | $0.84 | 136 | 185 | 22.6% | — | 0 |
| 12 | Tyloo (Holo) \| Stockholm 2021 | $8.16 | $10.45 | 301 | 17 | 21.9% | — | 0 |
| 13 | Cloud9 (Holo) \| Antwerp 2022 | $9.79 | $11.10 | 149 | 147 | 11.8% | — | 0 |
| 14 | Austin 2025 Challengers Capsule | $0.25 | $0.40 | 60 | 216 | 37.5% | — | 0 |
| 15 | **Movistar Riders (Holo) \| Stockholm** | $9.01 | $10.15 | 229 | 20 | 11.2% | **11.4** | **1584** |

### Вердикт по стикерам как товару

**Только 2/25 стикеров имеют score > 0.** Проблема:
- Spreads слишком широкие (8-60%) — стикеры illiquid
- Большинство стикеров: Q < 1.5 (больше продавцов чем покупателей)
- Капсульные стикеры (capsules) — отдельная категория, не подходит для demand trading

**Рекомендация: НЕ добавлять стикеры как отдельную категорию.** Объём слишком мал, spreads слишком широкие. Стикеры — collector items, не trading items.

---

## PHASE 5 — Итоговые предложения

### 1. Агент-скины: ДОБАВИТЬ в diversity-scan

**Обоснование:** 7/12 агентов имеют score > 0, tight spreads (2-8%), decent volume. Агенты — отдельная категория на DMarket, не weapon skins.

**План:** Добавить "Agents" в `_CATEGORY_PATTERNS` в `cycle_orchestrator.py`:
```python
"Agents": [" | SWAT", " | Phoenix", " | FBI", " | SEAL", " | Professionals"],
```

### 2. Value pipelines: АРХИВИРОВАТЬ

**Обоснование:** `value_pipelines.py` (299 lines) — ноль вызовов из торгового пути. Дубль `filter.py:604-622` (sticker value) + `demand_strategy.py` (OBI). `rare_valuation.py` (92 lines) — дубль `pricing.py`.

**Рекомендация:** Переместить в `src/analysis/algo_pack/_archived/`.

### 3. Sticker premium: ОСТАВИТЬ как есть

**Обоснование:** Текущая логика (`stickers_evaluator.py:354-396`) уже корректно обрабатывает tiers:
- $0.05 sticker → $0.0025 added (negligible)
- $50 sticker → $2.50 added (meaningful)
- Luxury rejection работает (v18.1)

**НЕ нужно менять** — система работает правильно.

### 4. Stickers как товар: НЕ добавлять

**Обоснование:** 2/25 стикеров имеют score > 0. Spreads 8-60%. Объём слишком мал. Стикеры — collector items, не trading items.

---

## ORPHANED modules: финальный список

| Файл | Lines | Рекомендация | Причина |
|------|-------|-------------|---------|
| `value_pipelines.py` | 299 | **АРХИВИРОВАТЬ** | Ноль вызовов, дубль filter.py + demand_strategy.py |
| `rare_valuation.py` | 92 | **АРХИВИРОВАТЬ** | Ноль вызовов, дубль pricing.py |
| `algo_pack/pair_trading.py` | ~200 | **АРХИВИРОВАТЬ** | Неприменим к one-asset OBI |
| `algo_pack/spread_optimizer.py` | ~150 | **АРХИВИРОВАТЬ** | Дубль sell_optimizer |
| `algo_pack/garch_forecast.py` | ~200 | **ОСТАВИТЬ** | Planned: замена EWMA |
| `algo_pack/ou_process.py` | ~150 | **ОСТАВИТЬ** | Planned: mean-reversion сигнал |
| `algo_pack/event_driven.py` | ~100 | **ОСТАВИТЬ** | Planned: сезонная корректировка |
| `algo_pack/sell_optimizer.py` | ~150 | **ОСТАВИТЬ** | Planned: list_price optimization |
| `multi_source_oracle.py` | ~300 | **ОСТАВИТЬ** | Deprecated для demand, но код preserved |

---

**Branch:** `feature/full-audit-agents-stickers` (pushed, NOT merged)
**PR:** NOT opened (waiting for review)
