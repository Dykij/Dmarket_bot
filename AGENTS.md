# AGENTS.md - Cross-Instrument Truth

## Stack & Architecture
- **Language Stack:** Python (venv located in `.venv/`), Rust (located in `src/rust_core` integrated via PyO3).
- **Core Integration:** DMarket API is the sole trading platform.
- **Architectural Borders:** 
  - `main` branch is strictly for the infra-perimeter.
  - Trading logic lives exclusively in `src/core/target_sniping/`.
  - Any formula changes require a full backtest before deployment.

## Execution Commands
- **Tests:** Run via `pytest tests/unit/...`
- **Linters:** Use `ruff` and `basedpyright`.
- **Rust Build:** Compile the Rust extension via `maturin develop`.

## Permanent Constraints & Rules
- Do NOT remove `DRY_RUN` without explicit confirmation.
- `git push` requires manual user review (raw push is forbidden).
- Do NOT seed `virtual_inventory`.
- **Check Call Sites First:** Before deep auditing/refactoring, verify the code is actually called in prod (e.g. via grep & logs) to avoid fixing dead code.

*Note: This file must be kept under ~150 lines. Granular details should be placed in `skills/`.*