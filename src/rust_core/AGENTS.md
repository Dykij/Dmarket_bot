# Rust Core (`src/rust_core`) — Subsystem Knowledge

## Known Bugs & Anti-Patterns
- **[P0] Bid/Ask Inversion (Fixed)**: `best_bid` and `best_ask` were previously inverted during JSON parsing. This caused catastrophic failures in trading logic. This has been fixed, but any changes to price parsing MUST verify the correct mapping.
- **[P1] $0.00 on Parse Failure (Open)**: If price data is missing or malformed, the parser returns `$0.00`. This is caused by the systemic anti-pattern `unwrap_or(0.0)` in this file. This can lead to false signals downstream.

## Dead Code Paths
- **`parse_aggregated_prices_rs`**: This specific parsing path is marked as `UNUSED IN PRODUCTION`. P0/P1 findings within it remain relevant ONLY if the path is ever wired into the runtime.

## Agent Instructions
- **Do NOT** use `unwrap_or(0.0)` for prices or critical metrics. Propagate `Option<f64>` or `Result` so the Python layer knows the data is missing, rather than substituting `0.0`.
- All changes in `.rs` files require delegation to `rust-auditor`.
- Before modifying parsing logic, consult `docs/ARCHITECTURE.md` to understand how these values flow into Python.
