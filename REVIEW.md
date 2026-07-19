# Review Instructions — DMarket Trading Bot

## What Important means here

Reserve Important for findings that would break behavior, leak data,
or block a rollback:
- Incorrect trading logic (wrong fee calc, missing balance check)
- SQL injection or hardcoded secrets
- Race conditions in order placement
- Drawdown freeze bypass
- Financial loss potential ($1+ per trade)

Style, naming, and refactoring suggestions are Nit at most.

## Cap the nits

Report at most five Nits per review. If you found more, say "plus N
similar items" in the summary instead of posting them inline. If
everything you found is a Nit, lead the summary with "No blocking
issues."

## Do not report

- Anything CI already enforces: lint, formatting, type errors
- Generated files under `src/gen/` and any `*.lock` file
- Test-only code that intentionally violates production rules
- `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`
- `node_modules/`, `vendor/`, `third_party/`

## Always check

- New API routes have an integration test
- Log lines don't include email addresses, user IDs, or request bodies
- Database queries are parameterized (no f-strings in SQL)
- Balance is checked BEFORE every trade
- Drawdown freeze is respected (balance < 85% of peak → no buys)
- Kelly sizing uses Half Kelly (50%), never full Kelly
- All trades have idempotent client_order_id
- Rate limiting is respected (10 req/s DMarket API)
- Error handling doesn't swallow exceptions silently
- Async code doesn't have blocking calls (time.sleep, requests, open())

## Re-review behavior

After the first review, suppress new Nits and post Important findings only.
This prevents round-7 on style alone.

## Verification bar

Each finding MUST include:
- file:line reference to SOURCE code (not just naming)
- Direct code citation supporting the claim
- NOT: "this function looks like it might..."
- YES: "line 142: `if balance:` — missing zero-check"

## Domain-specific rules

This is a CS2 skin trading bot. Flag as Important:
- Any code path that could lose real money
- Missing balance validation before trade execution
- Incorrect fee calculation (buy fee OR sell fee missing)
- Race conditions in concurrent order placement
- Stale price data used for trade decisions
- Missing idempotency on order creation
