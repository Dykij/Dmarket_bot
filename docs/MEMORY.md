# Project Memory (MEMORY.md)

## Current State & Recent Accomplishments
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

## Known Technical Debt & Test Failures (Date: 2026-08-24)
- **test_value_pipelines_module_importable**: `tests/unit/test_core_pipeline.py::TestValuePipelines::test_value_pipelines_module_importable` fails with:
  `ImportError: cannot import name 'value_pipelines' from 'src.core.target_sniping' (/home/deck/dmarket/Dmarket_bot-main/src/core/target_sniping/__init__.py)`
  Command to reproduce: `.venv/bin/pytest tests/unit/test_core_pipeline.py`
- **test_run_cycle_with_no_oracle_skips**: `tests/unit/test_core_sniping_loop.py::TestRunCycle::test_run_cycle_with_no_oracle_skips` fails with:
  `TypeError: 'coroutine' object is not iterable` in `_stage_prefetch` iterating over `ctx.agg_prices.items()`, leading to another `TypeError: unsupported format string passed to AsyncMock.__format__`.
  Command to reproduce: `.venv/bin/pytest tests/unit/test_core_sniping_loop.py`


- **mcp-server-sqlite is broken**: Fails with `AttributeError: 'Server' object has no attribute 'list_resources'`. Disabled in MCP config as `_sqlite_disabled_known_broken_see_MEMORY_md`. Waiting for an upstream fix or alternative.
