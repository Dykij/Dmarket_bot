# Session Log (SESSION_LOG.md)

## [2026-08-23] Session Retrospective
- **Что сделано:** 
  - Создана слоистая система инструкционных файлов: `AGENTS.md` (универсальные факты и правила) и `GEMINI.md` (Engineering Rigor Protocol и Subagent Delegation).
  - Сформированы 5 субагентов для специализированных проверок (`raw-evidence-auditor`, `regression-isolator`, `scope-auditor`, `stats-skeptic`, `code-auditor`).
  - Созданы файлы постоянной памяти `docs/MEMORY.md` и `docs/SESSION_LOG.md` для трекинга состояния проекта и изменений.
  - Подготовлена база для проверки и настройки hooks (lifecycle-событий) для автоматического логгирования будущих сессий.
- **Что решено:**
  - `AGENTS.md` служит источником правды для базовых правил.
  - Guardrails зафиксированы как `soft` enforcement.
- **Что осталось открытым:**
  - Тестирование и валидация срабатывания Lifecycle Hooks в текущей версии Antigravity (ФАЗА 4-7).
- 2026-08-30: Устранили блокировку Catch-22, запустили тесты, исправили баг бесконечного цикла в verdict_gate.sh

## 2026-08-30
- Fixed systemic hook lockups (`Error 127`) by resolving relative path issues in `.agents/hooks.json`.
- Implemented robust `verdict_gate.sh` parsing using `jq` to exclude `SYSTEM_MESSAGE` checkpoints, solving the phantom `FAIL` loop.
- Adjusted `lazy_work_guard.sh` to safely skip markdown files and avoid self-triggering on literal marker strings.
- Added 4 new specialized subagents (`lsp-mcp-integration-auditor`, `python-asyncio-auditor`, `rust-auditor`, `stop-criteria-guard`).
- Restructured `cclsp.json` with absolute paths.
- Committed all infrastructure v2 changes to `feature/rust-core-fixes` (Commit: 3b0f39f).

## 2026-08-31
- Added `Message Regeneration Integrity` rule to `GEMINI.md` to prevent content loss upon stop hook triggers.
- [WARNING] Code is NOT ready for production. TRACKED_TITLES requires backtesting.

## 2026-09-05
- Fixed regression in `ranking.py` by restoring `spread = best_bid - best_ask` formula for target-sniping logic.
- Updated `Config.TRACKED_TITLES` to use a curated list of 40 liquid CS2 items instead of blind top-100 scan.
- Removed dead synthetic candidate generators (`wear-`, `demand-`, `diversity-`) from `cycle_orchestrator.py`.
- Updated subagent rules for `stop-criteria-guard` (checking `git log` to catch historical regressions) and others (independent recalculation).
- Committed agent infrastructure scripts, rules, and hooks to enforce anti-hallucination protocols.
- (Pending) Subagent prompts (code-auditor, raw-evidence-auditor, stats-skeptic, stop-criteria-guard) updated with recalculation rules, pending commit.
- Успешная консолидация веток: безопасно удалены 14 локальных и удалённых (GitHub) веток. Оставлены только `main` и новая синхронизированная `testing/backtest-validation`. Ни один коммит не утерян.
- Проведен полный аудит всех 9 суб-агентов. Добавлен универсальный preamble во все файлы (строгие RAW-правила, защита от слепого доверия). 
- Внедрены 5 профильных ролевых улучшений для ключевых агентов (regression-isolator, scope-auditor, lsp-mcp-integration-auditor, raw-evidence-auditor, stop-criteria-guard) на основе реальных уроков этой сессии.
- 2026-09-05: Completed architecture analysis, cross-validation with code-graph-mcp and archy, and prepared decomposition plans for filter.py, execution.py, and resale.py.
- 2026-09-05: Fully updated `docs/otsebyatina_patterns_registry.md` with complete catalog of patterns A-H (including H1-H7) from the multi-round audit session.

## Терминальная песочница — известный рецидивирующий баг
Ошибка "sbox: installing certificate: open /etc/ssl/cert.pem: read-only file system"
повторяется независимо от прав chrome-sandbox (подтверждено корректными -rwsr-xr-x
root root при повторном сбое 2026-09-06). SUID-фикс либо решил проблему тогда
случайно, либо это два независимых механизма (chrome-sandbox — Chromium sandbox,
sbox — собственный слой Antigravity для terminal). Дальнейшая диагностика прав
файлов бесполезна. Принято решение: использовать pre_bypass_gate.sh с ежедневным
файлом-одобрением от пользователя вместо повторной диагностики каждый раз.
- 2026-09-07: Fixed stop_gate.sh Walkthrough Guard for subagents and tested Phase 6.
- 2026-09-07: Investigated native `SubagentStop` lifecycle event support in Antigravity. Confirmed it is NOT supported natively in the current version. We must continue using the `IS_SUBAGENT` heuristic based on the absence of `task.md`.
