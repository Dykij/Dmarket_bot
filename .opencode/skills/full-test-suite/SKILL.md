---
name: full-test-suite
description: Use ONLY when the user asks to run all tests, the full test suite, or verify the bot works. Trigger keywords: "run tests", "run all tests", "test suite", "прогони тесты", "проверь всё", "full test", "все тесты". Runs pytest unit tests + sandbox full cycle + strategy simulation.
---

# Full Test Suite

Run the complete test suite: unit tests (v13 features + risk manager + pump detector), sandbox dry-run, and strategy simulation.

## Prerequisites

- `.env` with DMarket + CS2Cap API keys
- Python venv at `.venv/` with all dependencies
- For production-like sandbox: `ENCRYPTION_KEY` env var

## Run Steps

```bash
source .venv/bin/activate

# 1. Unit tests (v13 features + risk + logging)
python -m pytest tests/test_v13_features.py tests/risk/ tests/test_logging_config.py \
    -v --tb=short -q

# 2. Sandbox full cycle (real DMarket + CS2Cap data)
ENCRYPTION_KEY="test-key" python -m tests.sandbox_full_cycle

# 3. Strategy simulation (real-time market scan)
python -m tests.simulate_strategy
```

## Expected Results

- **Unit tests**: 140+ tests passed (v13 features: 31, risk: 88, logging: ~30)
- **Sandbox**: 7/7 checks passed in <5 seconds
- **Simulation**: Completes without errors, shows profitability report

## What Gets Tested

| Suite | Coverage |
|-------|----------|
| `test_v13_features.py` | Fee tiers, trade lock, funds hold, exclusive flag, stickers, pattern premium, config |
| `risk/test_risk_manager.py` | Pre-trade checks, drawdown halts, Kelly sizing, pump detector, error classification |
| `risk/test_pump_detector.py` | Price spike detection, blacklist management |
| `test_logging_config.py` | Log fixtures, assertions, data generators |
| `sandbox_full_cycle.py` | DMarket API, CS2Cap, aggregated prices, market scan, buy/sell simulation |
| `simulate_strategy.py` | Real-time market data scan with profitability analysis |

## Related Files

- `tests/test_v13_features.py` — Core strategy tests (31 tests)
- `tests/risk/` — Risk management tests (88 tests)
- `tests/sandbox_full_cycle.py` — End-to-end dry run
- `tests/simulate_strategy.py` — Live market simulation
