# Code Review Instructions — DMarket Bot

## What Important means here

Reserve Important for findings that would:
- Lose real money (negative trades, fee miscalculation, balance bypass)
- Break production (crash, data corruption, API failure)
- Compromise security (secret leakage, injection, auth bypass)
- Violate trading invariants (drawdown freeze bypass, idempotency failure)

Style, naming, formatting, and refactoring suggestions are Nit at most.

## Severity mapping

| Finding type | Severity |
|-------------|----------|
| Financial loss | IMPORTANT |
| Production crash | IMPORTANT |
| Security vulnerability | IMPORTANT |
| Performance issue (O(n²)) | IMPORTANT |
| Missing error handling | IMPORTANT |
| Code duplication | NIT |
| Style/naming | NIT |
| Missing documentation | NIT |
| Suggestion | NIT |

## Cap the nits

Report at most 5 Nits per review. If you found more, say "plus N similar items" in the summary instead of posting them inline. If everything you found is a Nit, lead the summary with "No blocking issues."

## Do not report

- Anything CI already enforces: lint, formatting, type errors (ruff, ty)
- Generated files (`.opencode/agents/prompts/*.txt`)
- Test-only code that intentionally violates production rules
- Pre-existing issues that existed before this PR

## Always check

- Balance is checked BEFORE every trade
- Drawdown freeze is enforced (>15% drawdown → only sells)
- Kelly sizing uses Half-Kelly with 3%/10% bounds
- Both buy AND sell fees are accounted in margin calculation
- Idempotency keys are used for all orders
- Circuit breaker halts after 5 consecutive failures
- API rate limits are respected (10 req/s DMarket)
- Secrets are not logged or hardcoded
- SQL queries use parameterized statements

## Verification bar

Require evidence before posting a finding:
- Must have exact file:line reference
- Must explain the trigger condition
- Must explain the financial/production impact
- "This might be wrong" is NOT a finding

## Re-review convergence

After the first review:
- Suppress new Nits
- Post only Important findings
- Auto-resolve threads where the fix is correct

## Summary format

Lead with a one-line tally: "3 Important, 2 Nits"
If no Important issues: "No blocking issues found"

## Output: inline comments

Post findings as inline comments on the specific lines where issues were found.
Use GitHub API to create review comments with suggestion blocks when possible.
