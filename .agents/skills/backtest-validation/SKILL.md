---
name: backtest-validation
description: Use before claiming that a Dmarket_bot strategy, signal, algorithm or threshold works or affects trades. Preflight (reachable, enabled, fed with data, order of series), data map, statistics and report format.
---

# Backtest validation (Dmarket_bot)

HARD RULE: never write "works", "passes" or "profitable" without: data source, period, number of events, number of distinct hash_names, control group, 95% CI, and RAW script output. No such evidence -> verdict is INCONCLUSIVE.

## Data map (verified 2026-10-07 on the user's machine; re-check counts before relying on them)
- `data/dmarket_state.db` -> `decision_logs(id, hash_name, decision, reason, details, timestamp)`.
  - `scanned`: details JSON `{obi_norm, ofi, bid_count, ask_count, best_bid, best_ask}`. About 826k rows in August, 141 hashes; events that have a later price span 2026-08-07..08-22 and 100 hashes. Almost nothing after: 40 rows in September.
  - `pass`: two shapes. JSON from demand_strategy (`price, demand_ratio, score, hold_days, obi_norm, ofi, z_score`) and text from filter.py ("Demand opportunity ..."). `skip`: text details only.
  - `ofi` logged before the fix is OBI-vs-EWMA (first observation = OBI), not a flow. Do not use it as a feature without re-reading `_update_obi_history`.
- `data/dmarket_history.db` -> `price_history(hash_name, price, source, recorded_at)`: FROZEN since 2026-07-28 (writers were the oracle modules, removed in commit 2b8dcc0, 2026-08-05). External sources only (marketcsgo, waxpeer, cs2cap...), no DMarket prices, no bid/ask. Always exclude `source IN ('test','dry_run')`.
- `trade_history`: 345 rows, too few for statistics.
- Open every DB read-only: `sqlite3.connect("file:<path>?mode=ro", uri=True)`. Never write into `data/`.

## Preflight: before any claim "algorithm X affects trades" (all four must be shown, else verdict is INCONCLUSIVE)
1. Reachable: imported (statically) from `src.__main__` or `src.telegram.control_bot.__main__` (AST walk: `~/dmarket_audits/archive/2026-10-06/perm/p101_reach.py`; `_archived` excluded; no dynamic imports in src). A module that exists, has tests, and is listed in ALGORITHMS.md may still be unreachable.
2. Enabled: read the flag AND its default in `src/config.py`, then env/`.env`/config.json. `STRICT_MICROSTRUCTURE_FILTERS=False` gates the whole 17-step `microstructure_pipeline` and `compute_microstructure_scores`; `OFI_ENABLED`, `MULTI_LEVEL_OBI_ENABLED`, `QUEUE_IMBALANCE_ENABLED` default False. Also check `DRY_RUN`: a signal that passes in dry run places no orders.
3. Fed: the input is non-empty. Pipeline steps 13-17 need >=20/22/27/40/50 history points; `price_history` has been empty since 2026-07-28, so every history-based step sees nothing.
4. Ordered: `price_db.get_recent_prices` returns NEWEST first (`ORDER BY recorded_at DESC`); `algo_pack` functions document "oldest first". Any caller that passes the DB list straight in inverts the series (proved for PVC and peak-avoidance in demand_strategy; same call pattern found by reading, NOT run, in position_guard ewma_volatility and filter.py `_early_prices`/Kelly vol). Test every new caller with a DESC fixture.
Unit tests that pass on hand-made lists prove the formula only, never the wiring.

## Code you must not trust blindly
- `src/analytics/backtester/` has no callers and no tests; it expects `PriceHistory` objects from `historical_data`, and nothing builds them from SQLite. `src/analytics/backtester.py` is shadowed by the package. Read the code and add tests before using it.
- `src/analysis/backtest/obi_regression.py`: read its input assumptions first.
- Algorithms gated on `price_history` (Bollinger, DEMA, MACD, Hurst, GARCH, PVC, peak-avoidance, bait, Kelly vol) receive an empty history, so their effect cannot be backtested from current logs.
- Unreachable on 2026-10-07 (46 of 179 modules; re-run the walk): algo_pack event_driven/garch/info_theory/ou_process/sell_optimizer/sliding_window/thompson_sampling/vpin, analysis.backtest.obi_regression, risk circuit_breaker_manager/concentration_risk/dynamic_fee/incident_manager/lock_tracker/portfolio_optimizer, core.item_intel. ALGORITHMS.md is not evidence of wiring.

## Method (all mandatory)
1. Entry = `best_ask` at the scan. Costs: sell fee 5.5% (`get_total_fee_rate`, per-item API fees may differ) and no instant sale.
2. Outcome proxies: relist at the median `best_ask` in [t+20h, t+3d] minus fee (optimistic); sell into `best_bid` minus fee (conservative). State which one you report.
3. Events: first scan per (hash_name, 6h bucket). Forward series comes from ALL scans of that hash (never only from `pass` rows: survivorship).
4. Control group is mandatory: all scans / non-pass scans.
5. Events of one hash overlap in time. Use a bootstrap over hash_names (>=2000 resamples) for CI; plain n is not independent sample size.
6. Count the comparisons you ran. One CI that barely excludes 0 among many is a hypothesis, not a result.
7. Choose thresholds on one period, test on a LATER period. Do not tune on the data used to find the effect. Minimum before changing any threshold: 4 weeks and 200+ hashes.
8. Wiring a new algorithm: first shadow mode (compute and log the signal, do not gate trades), then this method on the logged signal, only then enable. Never change a threshold in the same commit that wires it.
9. A backtest is read-only analysis: no API calls, no target creation (`dmarket_*` skills), no config or DRY_RUN changes.

## Report format
Data (source, period, events, hashes) | metric definition | control | result with 95% CI | caveats | verdict: SUPPORTED / NOT SUPPORTED / INCONCLUSIVE + reason.

## Baseline (2026-08-07..22, 6212 events, 100 hashes; only 20 hashes had `pass` events)
- Mean relist return (ask after 20h..3d minus 5.5% fee): all scans -6.13% [-6.31; -5.94]; pass -5.68% [-6.42; -4.84].
- pass minus non-pass: +0.48% [-0.31; +1.42] (not significant). dr>=4 minus dr<1.5: +0.11% [-0.36; +0.54]. ask_cnt>=5 minus <5: +0.59% [+0.02; +1.26] (borderline).
- Reusable read-only scripts: `~/dmarket_audits/archive/2026-10-06/perm/p99_scan_study.py`, `p100_boot.py`. Copy them to scratch before editing.
