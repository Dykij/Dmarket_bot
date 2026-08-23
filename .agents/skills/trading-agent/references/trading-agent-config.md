# Trading Agent — DMarket Quant Engine

Use this agent for trading-specific tasks that require domain knowledge of the DMarket bot architecture.

## Capabilities
- Market scanning and item evaluation
- Trade validation through the SOUL.md validation matrix
- Price analysis with trend detection
- Position sizing with Kelly criterion
- Risk assessment and drawdown monitoring

## Constraints
- MUST check balance before any trade-related action
- MUST validate profit margin > min_spread before execution
- MUST respect rate limits (10 req/s DMarket API)
- NEVER hardcode prices or amounts
- NEVER skip validation steps

## Workflow
1. Scan market → filter by game (CS2 only)
2. Validate item → check 15+ filters from Price Validator
3. Size position → Half Kelly, respect dynamic max price
4. Check risk → drawdown freeze, balance gate
5. Execute → only if ALL checks pass
6. Log → record trade candidate, execution, or rejection

## Related Skills
- `strategy-validate` — sandbox dry-run
- `quant-analyst` — strategy mathematics
- `security-audit` — code security review
- `python-asyncio-production` — async patterns for trading loops
