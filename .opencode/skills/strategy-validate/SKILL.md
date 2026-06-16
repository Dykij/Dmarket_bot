---
name: strategy-validate
description: Use ONLY when the user asks to validate, check, or verify the trading strategy profitability. Trigger keywords: "validate strategy", "validate", "проверь стратегию", "check strategy", "how profitable", "sandbox", "находит ли бот", "сколько заработает", "profitability check". Runs the sandbox test and reports the number of profitable candidates found.
---

# Strategy Validation

Validate the bot's trading strategy by running the sandbox dry-run against real DMarket + CS2Cap market data. Shows how many profitable candidates the bot finds and calculates potential profit.

## Prerequisites

- `.env` with `DMARKET_PUBLIC_KEY`, `DMARKET_SECRET_KEY`, `CS2CAP_API_KEY`
- `DRY_RUN=false` for the sandbox (reads are real, buys are simulated)
- `ENCRYPTION_KEY` set in env

## Run

```bash
source .venv/bin/activate
ENCRYPTION_KEY="validate-key" python -m tests.sandbox_full_cycle
```

## What It Shows

1. **DMarket Connection** — Balance check
2. **CS2Cap Oracle** — 41 marketplace connection
3. **Aggregated Prices** — Top 100 most-traded titles with bid/ask
4. **Profitable Candidates** — Items where `(spread > fee*2+3%) AND net_profit > 0`
5. **Market Scan** — 500 items sampled from marketplace
6. **Buy Simulation** — Virtual buys within balance/cap limits
7. **Sell Simulation** — Virtual listings with PnL

## Interpreting Results

- **0 candidates**: Spread threshold too high or market too efficient. Lower `MIN_SPREAD_PCT` in `.env`
- **1-5 candidates**: Expected for $50 balance at 13% spread minimum. Normal
- **10+ candidates**: Excellent market conditions
- **Avg margin < 3%**: Fees eating profits. Enable `FLOAT_PREMIUM_ENABLED=false`, check `FEE_RATE`

## Key Config Knobs (in `.env`)

| Env var | Default | Effect |
|---------|---------|--------|
| `FEE_RATE` | 0.05 | DMarket sell fee (lower = more candidates) |
| `MIN_SPREAD_PCT` | 5.0 | Minimum gross spread to consider |
| `MAX_SNIPING_PRICE_USD` | 5.00 | Max buy price per item |
| `MAX_TOTAL_INVENTORY_ITEMS` | 30 | Max concurrent holdings |
| `WITHDRAWAL_FEE_RATE` | 0.02 | Withdrawal fee in net PnL |

## Related Files

- `tests/sandbox_full_cycle.py` — The validation script
- `src/config.py` — All strategy parameters
- `src/core/target_sniping/filter.py` — Candidate evaluation logic
