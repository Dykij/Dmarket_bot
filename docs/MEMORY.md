# Project Memory (MEMORY.md)

## Current State & Recent Accomplishments
- **Test Suite Performance:** Full test suite (1900+ tests) takes ~5.5-6 minutes. Binary search and `--durations=15` profiling confirm there are no hanging tests or deadlocks (slowest test is 3.23s, average is ~0.17s). The duration is objectively long but not pathological.
- **Oracle Removal:** Fully removed external oracles (Market.CSGO, Waxpeer, CSFloat, Steam) in commit `2b8dcc0`. Strategy now exclusively depends on DMarket API.
- **filter.py Fix:** Replaced oracle validation with DMarket `agg_prices`.
- **has_reference_discount:** Diagnosed as tautological (cs_price always 0 post-oracle-removal, condition always False). Definition and all 3 usages REMOVED in commit 21e489a on feature/remove-oracles-formula-audit. Not merged to main.
- **OBI-Calibration:** Tested on 39,259 records across 5 heterogeneous titles. Result: диапазон реальных значений R² от 1e-6 до 0.000649 (Макс. R²: 0.000649, 10 Year Birthday Sticker Capsule). Диапазон p-value для OBI-регрессии beta-коэффициента: 0.051–0.930. Вывод: статистически нулевой результат, OBI работает как risk-gate фильтр (существующая v17.3 архитектура), а не как самостоятельный торговый сигнал. Branch feature/garch-ou-calibration NOT merged, kept as documented negative result.

*(Полное RAW-подтверждение всех пунктов: см. `docs/reports/memory_evidence.md`)*

## Active Branches
- `main` (infra-perimeter only).
- Active development isolated to `src/core/target_sniping/`.

## Guardrails & Enforcement Status
- **Git Push Protection:** Guardrail is active. However, its enforcement status is **SOFT** (OS-level wrapper), not HARD (no SELinux/container enforcement). Bypassing is possible but strictly forbidden without explicit reasoning logged.
- **Destructive Commands / Virtual Inventory:** Soft enforcement, relies on AI explicit confirmation and checking rules.
- **Terminal Sandbox:** The Antigravity built-in sandbox (`enableTerminalSandbox`) is physically broken on the host (`connection reset by peer`), meaning hard OS-level isolation is not functioning. All tools are forced to use `BypassSandbox: true`. We rely purely on the OS wrappers mentioned above.

## Known Technical Debt & Test Failures (Date: 2026-08-26)
- **test_value_pipelines_module_importable**: `tests/unit/test_core_pipeline.py::TestValuePipelines::test_value_pipelines_module_importable` fails with:
  `ImportError: cannot import name 'value_pipelines' from 'src.core.target_sniping' (/home/deck/dmarket/Dmarket_bot-main/src/core/target_sniping/__init__.py)`
  Command to reproduce: `.venv/bin/pytest tests/unit/test_core_pipeline.py`
- **test_run_cycle_with_no_oracle_skips**: `tests/unit/test_core_sniping_loop.py::TestRunCycle::test_run_cycle_with_no_oracle_skips` fails with:
  `TypeError: 'coroutine' object is not iterable` in `_stage_prefetch` iterating over `ctx.agg_prices.items()`, leading to another `TypeError: unsupported format string passed to AsyncMock.__format__`.
  Command to reproduce: `.venv/bin/pytest tests/unit/test_core_sniping_loop.py`

### 48 Additional Pre-existing Test Failures and 7 Errors
Isolated via regression-isolator and confirmed to exist on commit 935ba8d (before Phase 0 dead code marking):
- tests/test_module_manifest.py::test_manifest_files_exist
- tests/test_new_algo_modules.py::TestPairTrading::test_calibrate_detects_cointegration
- tests/test_new_algo_modules.py::TestPairTrading::test_calibrate_low_correlation_not_cointegrated
- tests/test_new_algo_modules.py::TestPairTrading::test_calibrate_insufficient_data_returns_defaults
- tests/test_new_algo_modules.py::TestPairTrading::test_update_low_spread_gives_long_signal
- tests/test_new_algo_modules.py::TestPairTrading::test_update_before_calibrate_returns_hold
- tests/test_new_algo_modules.py::TestPairTrading::test_update_identical_prices_returns_hold
- tests/test_resale_pipeline.py::TestResalePipeline::test_calculate_sell_price_basic
- tests/test_resale_pipeline.py::TestResalePipeline::test_calculate_sell_price_min_margin
- tests/test_resale_pipeline.py::TestResalePipeline::test_calculate_sell_price_oracle_zero
- tests/test_resale_pipeline.py::TestResalePipeline::test_calculate_sell_price_with_cross_data
- tests/test_resale_pipeline.py::TestFullFlow::test_evaluate_item_for_purchase
- tests/test_resale_pipeline.py::TestOracleStrategyIntegration::test_cross_market_data_feeds_into_strategy
- tests/test_resale_pipeline.py::TestConfigIntegration::test_all_new_config_params
- tests/unit/test_demand_strategy_v17.py::TestWearExpansionBatchFetch::test_batch_fetch_called_with_correct_titles
- tests/unit/test_filter.py::TestKellySizing::test_kelly_enabled_reduces_max_price
- tests/unit/test_filter_evaluator.py::TestEvalContext::test_default_values
- tests/unit/test_filter_evaluator.py::TestEvalContext::test_custom_values
- tests/unit/test_filter_evaluator.py::TestStageRiskGates::test_rejects_empty_title
- tests/unit/test_filter_evaluator.py::TestStageRiskGates::test_rejects_zero_price
- tests/unit/test_filter_evaluator.py::TestStageRiskGates::test_rejects_already_placed
- tests/unit/test_filter_evaluator.py::TestStageRiskGates::test_rejects_locked_item
- tests/unit/test_filter_evaluator.py::TestStageMicrostructure::test_rejects_zero_bid
- tests/unit/test_filter_evaluator.py::TestStageMicrostructure::test_rejects_zero_ask
- tests/unit/test_filter_evaluator.py::TestStageMicrostructure::test_passes_valid_data
- tests/unit/test_filter_evaluator.py::TestStageValueLayers::test_basic_list_price
- tests/unit/test_filter_evaluator.py::TestStageValueLayers::test_float_premium_applied
- tests/unit/test_filter_evaluator.py::TestStageFeeAndCaps::test_rejects_low_margin
- tests/unit/test_filter_evaluator.py::TestStageAssemble::test_returns_buy_payload
- tests/unit/test_filter_evaluator.py::TestStageAssemble::test_strategy_intra_spread
- tests/unit/test_filter_evaluator.py::TestStageAssemble::test_strategy_cross_market
- tests/unit/test_financial_instruments.py::TestCircuitBreakerManager::test_default_components_created
- tests/unit/test_new_modules.py::TestADFCointegration::test_stationary_series_high_score
- tests/unit/test_new_modules.py::TestADFCointegration::test_random_walk_low_score
- tests/unit/test_new_modules.py::TestADFCointegration::test_short_series_returns_zero
- tests/unit/test_new_modules.py::TestADFCointegration::test_constant_series
- tests/unit/test_price_history_db.py::TestPumpBlacklist::test_add_and_get_active
- tests/unit/test_price_history_db.py::TestPumpBlacklist::test_pump_blacklist_expired_not_returned
- tests/unit/test_price_history_db.py::TestPumpBlacklist::test_cleanup_expired
- tests/unit/test_price_history_db.py::TestPumpBlacklist::test_delete_entry
- tests/unit/test_price_history_db.py::TestInventory::test_add_virtual_item_exclusive
- tests/unit/test_selective_ranking.py::TestRankCandidatesBySpread::test_sorts_by_net_margin_descending
- tests/unit/test_selective_ranking.py::TestRankCandidatesBySpread::test_filters_zero_bid_or_ask
- tests/unit/test_selective_ranking.py::TestRankCandidatesBySpread::test_filters_unprofitable_after_fees
- tests/unit/test_selective_ranking.py::TestRankCandidatesBySpread::test_skips_items_without_agg_entry
- tests/unit/test_selective_ranking.py::TestRankCandidatesBySpread::test_top_k_selection
- tests/unit/test_strategies.py::TestMarketMaker::test_spread_calculation
- tests/utils/test_http_health_endpoints.py::TestHealthState::test_set_oracle_sources_active
- ERROR tests/utils/test_http_health_endpoints.py::test_healthz_returns_200_happy_path
- ERROR tests/utils/test_http_health_endpoints.py::test_healthz_returns_503_when_shutting_down
- ERROR tests/utils/test_http_health_endpoints.py::test_readyz_returns_200_when_ready
- ERROR tests/utils/test_http_health_endpoints.py::test_readyz_returns_503_when_daily_halt
- ERROR tests/utils/test_http_health_endpoints.py::test_readyz_returns_503_when_shutting_down
- ERROR tests/utils/test_http_health_endpoints.py::test_metrics_returns_prometheus_format
- ERROR tests/utils/test_http_health_endpoints.py::test_metrics_omits_quota_when_none

- **mcp-server-sqlite is broken**: Fails with `AttributeError: 'Server' object has no attribute 'list_resources'`. Disabled in MCP config as `_sqlite_disabled_known_broken_see_MEMORY_md`. Waiting for an upstream fix or alternative.
- **XML-тегирование секции Mandatory Artifacts**: Протестировано, значимого эффекта на однократном прогоне не обнаружено (агент всё ещё не читает MEMORY.md на старте и не создаёт plan/task). Гипотеза не подтверждена для данной версии Gemini/Antigravity.

## Incidents: AsyncIO Blocking Violations (Date: 2026-08-26)
- **Incident 1: Blocking SQLite cleanup (Severity: ВЫСОКО)**
  Location: `src/core/target_sniping/cycle_orchestrator.py`
  Description: Synchronous SQLite `wal_checkpoint` and `optimize` called directly in `async def _stage_postprocess`. This severely blocks the main asyncio event loop during I/O.
  RAW Evidence:
  ```python
  631:         if self.deep_scan_counter % 1000 == 0:
  632:             try:
  633:                 price_db.wal_checkpoint()
  634:                 price_db.optimize()
  635:                 price_db.cleanup_old_prices(days=30)
  636:                 price_db.cleanup_old_trades(days=90)
  ```
  Remediation: Wrap in `run_in_thread`.

- **Incident 2: Blocking DB write on execution (Severity: ВЫСОКО)**
  Location: `src/core/target_sniping/execution.py`
  Description: Synchronous write `profit_db.record_buy` called directly in `async def _execute_instant_buys`, blocking the event loop precisely when speed matters most (after a buy).
  RAW Evidence:
  ```python
  542:                 try:
  543:                     from src.db.profit_tracker import db as profit_db
  544:                     profit_db.record_buy(title, float(base_price), offer_id=item_id)
  ```
  Remediation: Wrap in `run_in_thread`.

## Dead Code Investigation: Rust Parser (Date: 2026-08-26)
- **Rust `parse_aggregated_prices_rs` is dead code**: Conclusive RAW evidence shows `market.py` explicitly uses `parse_aggregated_prices_from_dict` instead of the Rust function. `grep -rn "parse_aggregated_prices_rs" logs/bot_24_7.log` confirms zero usage in production logs.
- **Process Lesson**: Весь цикл фиксов lib.rs (P0 bid/ask, GIL release, zeroize, price parsing) применялся к коду, который не исполнялся в бою. Урок: перед глубоким аудитом конкретного модуля стоит сначала подтвердить (grep call sites + логи), что модуль реально используется в runtime path, а не только существует в дереве кода.

## Resolved Architectural Debates
- **SQLite Cross-Thread Segfault Risk**: A multi-agent audit initially flagged cross-thread cursor usage (with `check_same_thread=False`) as a critical risk leading to `sqlite3.ProgrammingError` or segfaults/memory corruption.
  - **Resolution**: Risk was severely overestimated. Tests with `sqlite3.threadsafety == 3` (Serialized mode) and `THREADSAFE=1` show Python fully disables thread checks, and the underlying SQLite engine handles interleaved fetch/insert without crashing or data corruption. The `execute_and_fetchone` helper is safe but not strictly necessary for preventing crashes.
