---
name: audit-trade
description: Validate a proposed trade against the SOUL.md validation matrix. Checks price, risk, balance, and drawdown constraints before execution. Trigger keywords: "audit trade", "validate trade", "check trade", "проверь сделку".
---

# /audit-trade — Validate Trade Against SOUL.md Matrix

Run a proposed trade through the full validation matrix from SOUL.md.

## Usage
```
/audit-trade <item-id> <price> <side>
```

## Validation Matrix (from SOUL.md)
1. **Syntax & Execution**: API compliance check
2. **Resource Constraint**: Rate limits respected? Oracle rate limits OK?
3. **Balance Check**: Does effective balance (total - reserve) support this position?
4. **Drawdown Check**: Is balance above peak × 85%?
5. **Profit Check**: Is net_margin > min_spread after fees?
6. **Trend Check**: Is item in uptrend or neutral (not downtrend)?

## What it does
1. Fetches current balance via `dmarket_api_balance`
2. Fetches item price history via `dmarket_api_price_history`
3. Runs all 6 checks
4. Outputs pass/fail for each check
5. Final verdict: **EXECUTE** / **REJECT** (with reason)

## Rules
- ALL 6 checks must pass for EXECUTE verdict
- If any check fails, output which check failed and why
- Never skip balance check — even for "small" amounts
- Log audit result to `memory/YYYY-MM-DD.md`
