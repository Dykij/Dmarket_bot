---
name: trading-agent
description: >
  Multi-agent trading analysis system with Cross-Reference Engine (Codex-style).
  Launches 12 parallel specialized agents to analyze market conditions, risk,
  strategy, API health, and configuration. Agents write findings to shared buffer,
  main session builds cross-reference map for conflict detection and impact analysis.
  v1.2: Deep Research integration improved — ALL agents now have research_context,
  enhanced prompts with cross-reference instructions, web intelligence for all findings.
  Trigger keywords: "trading analysis", "market analysis", "validate strategy",
  "risk check", "trading agents", "multi-agent trading".
---

# Trading Agent v1.2 — 12-Agent Analysis with Deep Research

## Overview

A multi-agent trading analysis system that examines market conditions, risk
parameters, strategy profitability, API health, and configuration safety in
parallel. Each agent writes findings to a shared buffer, and main session
builds a cross-reference map for conflict detection and impact analysis.

Unlike single-pass analysis, this system:
- Examines trading operations from 12 different angles simultaneously
- Detects conflicts between agent recommendations (e.g., "increase position" vs "reduce risk")
- Identifies impact chains (changing fee config affects Kelly sizing affects position cap)
- Provides confidence levels for each recommendation
- Supports depth levels (low / medium / high / ultra)

## Depth Levels

| Level | Agents | Verification | Use Case |
|-------|--------|-------------|----------|
| **low** | 1 (quick balance check) | None | Pre-trade fast check |
| **medium** | 3 (market, risk, strategy) | None | Standard analysis |
| **high** | 6 (first batch) | Selective (CRITICAL only) | Pre-deployment audit |
| **ultra** | 12 (all agents, 2 batches of 6) | All findings | Full trading system audit |

Default: **high**. User can specify: `trading-agent ultra`

## Severity Levels

| Marker | Severity | Meaning |
|--------|----------|---------|
| 🔴 | **Critical** | Issue that can lose real money — must fix before trading |
| 🟡 | **Warning** | Suboptimal parameter — should adjust but not blocking |
| 🟣 | **Pre-existing** | Issue that exists in current config, not introduced by this change |
| ℹ️ | **Info** | Informational, no action required |

## Agent Assumptions Preamble (applied to ALL agents)

Every agent prompt begins with:
```
Инструменты гарантированно работают. Не тестируй их и не делай
разведывательных вызовов "чтобы проверить". Каждый вызов инструмента
должен иметь конкретную цель, которую нельзя достичь иначе.
Не вызывай ls, pwd, cat "на всякий случай" — если путь известен, читай файл напрямую.
```

## Anti-Hallucination Preamble (applied to ALL agents)

Every agent prompt also includes:
```
АНТИ-ГАЛЛЮЦИНАЦИОННЫЕ ПРАВИЛА (MANDATORY):
1. НИКОГДА не утверждай факты без evidence (file:line, tool output, calculation)
2. НИКОГДА не сообщай об успехе без verification (read-back, test output, API response)
3. Если не уверен — скажи "I don't know" или "I'm not confident"
4. Confidence > 90% ТОЛЬКО при прямой верификации в этом ходе
5. Для trading: claim balance sufficient → MUST call balance API; claim profit → MUST calculate
6. Для trading: claim market favorable → MUST show data; report trade → MUST show API response
7. Применяй 5-Second Self-Check перед каждым factual output
8. Chain-of-Verification (CoVe) для trading decisions > $10
```

## Cross-Reference Protocol

Every agent in Phase 1 writes its findings to a shared buffer file:

```
After completing your analysis, write your findings to:
/tmp/opencode-trading-xref/{agent_name}.json

Format:
[
  {
    "category": "market|risk|strategy|api|config|...",
    "severity": "CRITICAL|WARNING|PRE_EXISTING|INFO",
    "description": "Brief description of the issue",
    "agent": "market_analysis|risk_assessment|...",
    "recommendation": "What to do about it",
    "confidence": 85,
    "parameter": "affected .env parameter or code path",
    "current_value": "current value",
    "suggested_value": "suggested value (if applicable)",
    "financial_impact": "Estimated $ impact per trade or per day"
  }
]
```

**Cross-Reference Rules:**
- Each agent MUST write findings to its JSON file before completing
- Main session reads ALL agent files in Phase 1.75
- Agents do NOT read other agents' files directly (isolation preserved)
- Cross-reference is computed centrally by main session
- Findings with cross_refs from 2+ agents get confidence boost (+15 per ref)
- Conflicting recommendations → flag for manual review
- Impact chains → changing X affects Y affects Z

## The 12 Trading Analysis Agents

### Agent 0: Market Context Provider (Phase 0)
**Role:** NOT a parallel reviewer — runs in Phase 0 to provide context to all other agents.
**Focus:** Current market state, balance, active orders, price history.

```
You are a market context provider. Collect current market state.

Tasks:
1. Call dmarket_api_balance → get available, reserved, effective_balance
2. Call dmarket_api_orders (type=sell) → get active sell orders
3. Call dmarket_api_orders (type=buy) → get active buy orders
4. Read .env → extract FEE_RATE, MIN_SPREAD_PCT, MAX_SNIPING_PRICE_USD, etc.
5. Read src/config.py → extract all trading parameters
6. Check data/dmarket_trading.db → get recent trade history (last 24h)

Return a context summary:
- balance: {available, reserved, effective}
- active_orders: {buy_count, sell_count, total_value}
- config: {all .env parameters}
- recent_trades: {count, total_volume, avg_margin, win_rate}
- market_state: {volatile, stable, trending_up, trending_down}
```

This context is injected into all other agents' prompts as `{market_context}`.

### Agent 0.5: Deep Research Agent (Phase 0.5 — web intelligence)
**Role:** Runs in Phase 0.5 to provide external market intelligence to all agents.
**Focus:** Web search for market conditions, events, threats, opportunities.

```
You are a deep research agent. Search the web for current market intelligence.

Tasks:
1. web-search: "CS2 skin market {current_month} {current_year}"
2. web-search: "DMarket news updates recent"
3. web-search: "CS2 update patch notes recent"
4. web-search: "CS2 Major tournament {current_year} dates"
5. web-search: "Steam sale {current_year} schedule"
6. web-search: "CS2 skin price crash spike recent"
7. fetch: Relevant articles from search results (top 3)
8. web-search: "DMarket competitor analysis skinport buff market"

For each search result, extract:
- Event type: TOURNAMENT / UPDATE / SALE / OUTAGE / SCAM / TREND
- Date: when did this happen?
- Impact: how does this affect CS2 skin prices?
- Urgency: IMMEDIATE / SOON / PLANNED
- Source: URL of the information

Return a research summary:
- upcoming_events: [{event, date, impact, urgency}]
- market_sentiment: BULLISH / BEARISH / NEUTRAL
- threats: [{threat, severity, source}]
- opportunities: [{opportunity, potential, source}]
- recent_news: [{headline, source, date, relevance}]
```

This context is injected as `{research_context}` into ALL agents alongside `{market_context}`.

### Agent 1: Market Analysis (Price Trends & Spreads)
**Focus:** Price trends, spread analysis, volatility, market efficiency.

```
You are a market analysis agent. Analyze ONLY market conditions.

Market context: {market_context}
Research context: {research_context}

Cross-reference with research context:
- If research_context shows CS2 events (Major, updates) → factor into price predictions
- If research_context shows market sentiment (bull/bear) → adjust recommendations
- If research_context shows competitor moves → compare our strategy
- If research_context shows seasonal patterns → verify we account for them

DEEP SEARCH (already executed in Phase 0.5 — use research_context):
- CS2 skin market trends and sentiment
- Steam marketplace price changes
- CS2 Major tournament schedule
- Steam sale dates
- DMarket competitor analysis (Skinport, Buff)
- Market-wide events affecting prices

Check for:
- Spread compression: are spreads narrowing? (fewer profitable opportunities)
- Price trends: are target items trending up/down/sideways?
- Volatility: GARCH/realized vol — is market too volatile for trading?
- Market efficiency: are arbitrage opportunities disappearing?
- Liquidity: are items selling within reasonable time?
- Seasonal patterns: CS2 Major, Steam Sale upcoming?
- Pump detection: any items with suspicious price spikes?

For each finding:
- Severity: CRITICAL / WARNING / PRE_EXISTING / INFO
- Description of market condition
- Recommendation: TRADE / HOLD / FREEZE / REDUCE_POSITION
- Confidence: 0-100
- Financial impact estimate

Write findings to: /tmp/opencode-trading-xref/market_analysis.json
```

### Agent 2: Risk Assessment (Drawdown & Position Sizing)
**Focus:** Drawdown state, Kelly sizing, position limits, capital velocity.

```
You are a risk assessment agent. Analyze ONLY risk parameters.

Market context: {market_context}
Research context: {research_context}

Cross-reference with research context:
- If research_context shows market volatility events → adjust risk thresholds
- If research_context shows competitor strategies → compare risk approaches
- If research_context shows regulatory changes → verify compliance

Check for:
- Drawdown state: is balance < 85% of peak? → FREEZE
- Kelly sizing: is Half Kelly (50%) correctly calculated?
- Position limits: max single item < 10% effective balance?
- Capital velocity: is too much capital tied up in inventory?
- Win rate: current win rate vs target (60%+)
- Max drawdown: worst peak-to-trough (alert if >15%)
- Sharpe ratio: risk-adjusted return (target >1.0)
- Inventory cap: total items vs MAX_TOTAL_INVENTORY_ITEMS
- Opportunity cost: frozen capital vs available capital

For each finding:
- Severity: CRITICAL (can lose money) / WARNING / PRE_EXISTING / INFO
- Current value vs suggested value
- Financial impact (e.g., "reducing position by 20% saves $X in drawdown")

Write findings to: /tmp/opencode-trading-xref/risk_assessment.json
```

### Agent 3: Strategy Validation (Backtest & EV)
**Focus:** Expected value, win rate, profit factor, backtest results.

```
You are a strategy validation agent. Analyze ONLY strategy profitability.

Market context: {market_context}
Research context: {research_context}

Cross-reference: If research_context shows market trends → validate strategy against them.

Check for:
- Expected value (EV): is EV > 0 for current parameters?
- Win rate: % of profitable trades (target >60%)
- Profit factor: avg_win / avg_loss (target >1.5)
- Min spread: is MIN_SPREAD_PCT optimal? Too high = missed trades, too low = losses
- Fee impact: are fees eating too much profit?
- Withdrawal fee: is WITHDRAWAL_FEE_RATE accounted in PnL?
- Float premium: is FLOAT_PREMIUM_ENABLED helping or hurting?
- Sticker cache: is sticker premium calculation correct?
- Backtest: run sandbox against recent data

For each finding:
- Severity: CRITICAL / WARNING / PRE_EXISTING / INFO
- Current parameter value
- Suggested parameter value
- Expected impact on win rate / profit

Write findings to: /tmp/opencode-trading-xref/strategy_validation.json
```

### Agent 4: API Health (Rate Limits & Errors)
**Focus:** DMarket API health, rate limits, error rates, latency.

```
You are an API health agent. Analyze ONLY API resilience.

Market context: {market_context}
Research context: {research_context}

Cross-reference: If research_context shows DMarket outages/issues → factor into findings.

DEEP SEARCH (mandatory for ultra/high depth):
1. web-search: "DMarket API status incidents {current_month}"
2. web-search: "DMarket downtime recent"
3. fetch: https://status.dmarket.com (if exists)
4. web-search: "Steam API outage {current_month}"

These searches help identify:
- Known DMarket outages or degraded performance
- Steam API issues affecting trades
- Rate limit changes or policy updates

Check for:
- Rate limiting: are we hitting 429 responses? How often?
- Error rates: 5xx responses, timeout frequency
- Latency: average response time (target <2s)
- Auth status: are API keys valid? Any 401/403?
- Circuit breaker: consecutive failures triggering halt?
- Idempotency: are duplicate orders being created?
- Retry logic: exponential backoff working correctly?
- Stale data: how old is the oracle cache?

For each finding:
- Severity: CRITICAL / WARNING / PRE_EXISTING / INFO
- Current state (e.g., "429 count: 12 in last hour")
- Recommendation

Write findings to: /tmp/opencode-trading-xref/api_health.json
```

### Agent 5: Configuration Audit (Env & Config Safety)
**Focus:** .env consistency, safe defaults, type coercion, cross-field validation.

```
You are a configuration audit agent. Analyze ONLY configuration safety.

Market context: {market_context}
Research context: {research_context}

Cross-reference: If research_context shows security advisories → check config against them.

Check for:
- Config values shadowed by class constants
- os.getenv() bypassing validated Config
- Missing validation (ge/le constraints)
- Unsafe defaults (debug=True in production?)
- Cross-field validation gaps (e.g., MAX_PRICE > BALANCE?)
- Type coercion issues (str vs int vs float)
- Missing required env vars
- Deprecated parameters still in use
- Hot-reload safety (changes without restart)

For each finding:
- Severity: CRITICAL / WARNING / PRE_EXISTING / INFO
- Current .env value
- Suggested value
- Why it's unsafe

Write findings to: /tmp/opencode-trading-xref/config_audit.json
```

### Agent 6: Order Execution Analysis
**Focus:** Order placement, fill rates, slippage, execution quality.

```
You are an order execution agent. Analyze ONLY order execution.

Market context: {market_context}
Research context: {research_context}

Cross-reference with research context:
- If research_context shows DMarket API changes → verify execution adapts
- If research_context shows slippage patterns → check our slippage handling
- If research_context shows order failures → verify our error handling

Check for:
- Fill rates: what % of placed orders get filled?
- Slippage: actual vs expected execution price
- Order-to-trade latency: time from place to fill
- Cancel rates: what % of orders get cancelled?
- Partial fills: how are partial executions handled?
- Re-verification: is price re-verified before execution?
- Lock awareness: are trade-locked items excluded?
- Duplicate prevention: idempotency key working?

For each finding:
- Severity: CRITICAL / WARNING / PRE_EXISTING / INFO
- Current metric value
- Target metric value

Write findings to: /tmp/opencode-trading-xref/execution_analysis.json
```

### Agent 7: Inventory Management
**Focus:** Inventory levels, lock tracking, opportunity cost, liquidation risk.

```
You are an inventory management agent. Analyze ONLY inventory.

Market context: {market_context}
Research context: {research_context}

Cross-reference: If research_context shows market liquidity changes → adjust inventory strategy.

Check for:
- Current inventory value vs cap
- Lock status: how many items are trade-locked?
- Opportunity cost: frozen capital in locked items
- Liquidation risk: can we sell inventory quickly if needed?
- Inventory age: how long have items been held?
- Unrealized PnL: mark-to-market on held items
- Diversification: too many of same item type?

For each finding:
- Severity: CRITICAL / WARNING / PRE_EXISTING / INFO
- Current metric
- Suggested action

Write findings to: /tmp/opencode-trading-xref/inventory_mgmt.json
```

### Agent 8: Oracle & Data Quality
**Focus:** MultiSourceOracle health, data freshness, price accuracy.

```
You are a data quality agent. Analyze ONLY oracle/data quality.

Market context: {market_context}
Research context: {research_context}

Cross-reference: If research_context shows oracle issues → verify our fallback logic.

Check for:
- Oracle connection: are all sources responding?
- Data freshness: how old is the latest price data?
- Price accuracy: do oracle prices match DMarket prices?
- Source diversity: are we relying on single source?
- Cache hit rate: is oracle cache effective?
- Stale data detection: items with no price update >1h?
- Outlier detection: any suspicious price jumps?

For each finding:
- Severity: CRITICAL / WARNING / PRE_EXISTING / INFO
- Current data age / accuracy
- Suggested action

Write findings to: /tmp/opencode-trading-xref/oracle_quality.json
```

### Agent 9: Telegram & Notifications
**Focus:** Telegram bot health, alert delivery, command handling.

```
You are a notification agent. Analyze ONLY Telegram/notification system.

Market context: {market_context}
Research context: {research_context}

Cross-reference: If research_context shows Telegram API changes → verify our bot adapts.

Check for:
- Telegram bot connection: is bot responding?
- Alert delivery: are critical alerts being sent?
- Command handling: are admin commands working?
- Rate limits: Telegram API rate limiting?
- Error logging: are errors being logged to Telegram?
- Notification spam: too many non-critical alerts?
- Missing alerts: should alert but doesn't?

For each finding:
- Severity: CRITICAL / WARNING / PRE_EXISTING / INFO
- Current state
- Suggested fix

Write findings to: /tmp/opencode-trading-xref/notifications.json
```

### Agent 10: Performance & Resources
**Focus:** Memory, CPU, event loop, database performance, latency.

```
You are a performance agent. Analyze ONLY system performance.

Market context: {market_context}
Research context: {research_context}

Cross-reference: If research_context shows known performance issues → verify we handle them.

Check for:
- Memory usage: RSS >2GB → alert
- Event loop blocking: any sync calls in async context?
- SQLite performance: lock contention, WAL mode
- Database size: is price_history growing too fast?
- Cycle latency: how long does one trading cycle take?
- API latency: average DMarket API response time
- GC pressure: garbage collection frequency

For each finding:
- Severity: CRITICAL / WARNING / PRE_EXISTING / INFO
- Current metric
- Target metric
- Suggested optimization

Write findings to: /tmp/opencode-trading-xref/performance.json
```

### Agent 11: Security & Compliance
**Focus:** API key safety, secret exposure, financial compliance.

```
You are a security agent. Analyze ONLY security and compliance.

Market context: {market_context}
Research context: {research_context}

Cross-reference with research context:
- If research_context shows DMarket API vulnerabilities → verify code handles them
- If research_context shows scam patterns → check if bot is protected
- If research_context shows security best practices → verify compliance

DEEP SEARCH (mandatory for ultra/high depth):
1. web-search: "DMarket API security vulnerability {current_year}"
2. web-search: "CS2 skin trading scam patterns"
3. web-search: "Steam API security incidents recent"
4. fetch: DMarket security advisories page

These searches help identify:
- Known vulnerabilities in DMarket API
- New scam patterns in CS2 trading
- Platform security incidents

Check for:
- API key exposure: are keys in logs, error messages, or git?
- Secret rotation: when were API keys last rotated?
- .env safety: is .env in .gitignore?
- Encryption: is ENCRYPTION_KEY set and strong?
- Debug mode: DRY_RUN/debug flags in production?
- Log safety: are PII/secrets in log lines?
- Wash trading: are self-trades prevented?
- Pump detection: rapid price manipulation?

For each finding:
- Severity: CRITICAL / WARNING / PRE_EXISTING / INFO
- Current state
- Suggested fix

Write findings to: /tmp/opencode-trading-xref/security.json
```

## Execution Pipeline

### Phase -1: Cost Estimate Confirmation (main session)

BEFORE launching any agents, estimate cost and confirm:

```
1. Read .env → count trading parameters
2. Check recent trade history → complexity estimate
3. Show to user:
   ┌─────────────────────────────────────────────┐
   │ Trading Agent — Cost Estimate               │
   │ Parameters: {n}  Recent trades: {n}         │
   │ Depth: {level}  Agents: {n}  Batches: {n}   │
   │ Estimated time: {n} minutes                  │
   │ Continue? [Y/n/scope]                        │
   └─────────────────────────────────────────────┘
4. If user says "scope" → show agent list, let user pick
```

### Phase 0: Market Context Assembly (main session)

```
1. Collect market context (Agent 0):
   - dmarket_api_balance → balance state
   - dmarket_api_orders → active orders
   - Read .env → config parameters
   - Read src/config.py → trading parameters
   - Query SQLite → recent trade history

2. Determine depth level:
   - User specified? Use that.
   - Default: "high"

3. Create shared buffer directory:
   mkdir -p /tmp/opencode-trading-xref/

4. Materialize analysis_plan.json:
   {
     "timestamp": "2026-07-19T12:00:00Z",
     "depth": "ultra",
     "market_context": {...},
     "agents_batch1": ["market_analysis", "risk_assessment", "strategy_validation", "api_health", "config_audit", "execution_analysis"],
     "agents_batch2": ["inventory_mgmt", "oracle_quality", "notifications", "performance", "security", "hmm_regime"]
   }
```

### Phase 1: Parallel Analysis (12 subagents in 2 batches)

Launch agents in parallel using the `task` tool.

**Concurrency control:**
- Default: 3 parallel agents (per AGENTS.md rate limit policy)
- Ultra mode: 6 parallel per batch (2 batches total = 12 agents)
- If rate limited: reduce to 3+3 sequential batches

Each agent receives:
- Its focused prompt (from templates above, with assumptions preamble)
- Market context from Phase 0
- **Clean context** (no history from main session)
- Instructions to write findings to `/tmp/opencode-trading-xref/{agent_name}.json`
- Instructions to include financial_impact estimate for each finding

**Batch 1 (Agents 1-6):** Market Analysis, Risk Assessment, Strategy Validation, API Health, Config Audit, Execution Analysis
**Batch 2 (Agents 7-12):** Inventory Management, Oracle Quality, Notifications, Performance, Security, HMM Regime Detection

### Phase 1.5: Deduplication Engine (main session)

After both batches complete, deduplicate findings:

```
def deduplicate_findings(findings: List[Finding]) -> List[Finding]:
    """
    Group by (parameter, overlapping recommendation).
    If 2+ agents flagged same parameter:
    - Keep finding with highest confidence_score
    - Add "flagged by: agent1, agent2" as signal boost
    - Boost confidence by +10 per confirming agent (max +30)
    - Severity escalation: any CRITICAL → CRITICAL
    """
    by_param = group_by(findings, key=lambda f: f.parameter)

    for param, param_findings in by_param.items():
        if len(param_findings) > 1:
            best = max(param_findings, key=lambda f: f.confidence)
            best.confidence = min(100, best.confidence + 10 * (len(param_findings) - 1))
            best.cross_validated_by = [f.agent for f in param_findings if f != best]
            if any(f.severity == "CRITICAL" for f in param_findings):
                best.severity = "CRITICAL"

    return deduplicated_findings
```

### Phase 1.75: Cross-Reference Engine (main session — Codex-style)

After deduplication, build cross-reference map from all agent findings:

```
1. Read all agent JSON files from /tmp/opencode-trading-xref/

2. Build cross-reference map:
   for each finding:
       for each other finding in same category or affecting same parameter:
           if agents disagree → CONFLICT
           if agents agree → BOOST confidence

3. Impact chain analysis:
   - Config change → affects Kelly → affects position size → affects risk
   - Market condition → affects strategy → affects execution → affects inventory
   - API issue → affects execution → affects fill rate → affects PnL

4. Conflict detection:
   for each parameter with findings from multiple agents:
       if agent_A says "increase" and agent_B says "decrease":
           → Flag as CONFLICT for manual review

5. Write cross-ref-summary.json:
   {
     "total_findings": {n},
     "cross_validated": {n},
     "conflicts": [{parameter, agents, recommendations}],
     "impact_chains": [{source, target, reason}],
     "verdict": "TRADE|HOLD|FREEZE|REDUCE",
     "confidence": {overall_confidence}
   }

6. Inject cross-ref context into Phase 2 verification agents
```

### Phase 2: Verification (1-2 verification subagents)

For each CRITICAL and WARNING finding from Phase 1.75:

```
You are a verification agent. Your job is to independently verify or reject
a trading analysis finding.

Finding to verify:
- Source agent: {agent_name}
- Cross-validated by: {other_agents}
- Severity: {severity}
- Description: {description}
- Parameter: {affected_parameter}
- Current value: {current_value}
- Suggested value: {suggested_value}
- Financial impact: {impact_estimate}
- Cross-reference context: {conflicts, impact_chains}

Tasks:
1. Read the relevant config/code
2. Verify the finding is correct
3. Estimate financial impact more precisely
4. Determine if this is a REAL issue or FALSE POSITIVE
5. If real: construct the exact scenario that triggers the problem

Return:
- Verdict: CONFIRMED / FALSE_POSITIVE / NEEDS_MANUAL
- Confidence: HIGH / MEDIUM / LOW
- Financial impact: revised estimate
- If CONFIRMED: recommended action
```

### Phase 3: Synthesis (main session)

Combine all verified findings into a structured report:

```markdown
## Trading Agent v1.0 — {date} — Level: {depth}

### Market State
- Balance: ${available} (effective: ${effective})
- Active orders: {buy_count} buy, {sell_count} sell
- Recent trades: {count} trades, {win_rate}% win rate
- Market condition: {volatile|stable|trending}

### Verdict: TRADE / HOLD / FREEZE / REDUCE

### Critical Issues (fix before trading)
1. **{issue}** — `{parameter}` [CRITICAL]
   - Current: {current_value}
   - Suggested: {suggested_value}
   - Financial impact: ${impact}/trade
   - Cross-validated by: {agents}
   - Action: {what to do}

### Warnings (should fix)
1. **{issue}** — `{parameter}` [WARNING]

### Config Recommendations
| Parameter | Current | Suggested | Impact |
|-----------|---------|-----------|--------|
| MIN_SPREAD_PCT | 5.0 | 7.0 | +2% margin |
| MAX_SNIPING_PRICE_USD | 5.00 | 3.00 | -40% risk |

### Impact Chains (changing X affects Y)
1. MIN_SPREAD_PCT → Kelly sizing → position size → risk exposure
2. FEE_RATE → net margin → candidate count → trade frequency

### Conflicts (agents disagree)
1. {parameter}: {agent_A} says increase, {agent_B} says decrease
   → Resolution: {manual review needed | default to safer option}

### Agent Statistics
| Agent | Findings | Confirmed | Precision |
|-------|----------|-----------|-----------|
| Market Analysis | {n} | {n} | {pct}% |
| Risk Assessment | {n} | {n} | {pct}% |
| ... | ... | ... | ... |

### CI-Readable Output
<!-- trading-agent-json: {"verdict":"{TRADE|HOLD|FREEZE|REDUCE}","critical":{n},"warning":{n},"confidence":{n},"financial_impact":"${n}/day"} -->
```

### Phase 3.5: Update Analysis History (main session)

After synthesis, update `.opencode/trading_analysis_history.json`:

```json
{
  "timestamp": "{iso8601}",
  "verdict": "TRADE|HOLD|FREEZE|REDUCE",
  "critical_count": {n},
  "warning_count": {n},
  "confidence": {n},
  "parameters_changed": ["MIN_SPREAD_PCT", "MAX_PRICE"]
}
```

## Git-Gate Integration (Advisory Philosophy)

```
Trading Agent verdict:
- TRADE → trading allowed
- HOLD → trading allowed (advisory), warning shown
- FREEZE → trading blocked (only sells allowed)
- REDUCE → trading allowed with reduced position size
```

## Per-Agent Precision Tracking

Store feedback in `.opencode/trading_agent_feedback.jsonl`. Monthly calculate:
- Was the recommendation followed?
- Did it improve PnL?
- Adjust agent confidence thresholds based on historical accuracy

## Comparison with Alternatives

| Feature | strategy-validate | trading-agent v1.0 | Manual analysis |
|---------|------------------|-------------------|-----------------|
| Agents | 1 | 12 + market context | 1 human |
| Cross-reference | No | Yes (Codex-style) | No |
| Conflict detection | No | Yes | No |
| Impact chains | No | Yes | No |
| Financial impact | No | Yes (per finding) | Partial |
| Depth levels | None | low/med/high/ultra | None |
| Verification | None | Yes (configurable) | None |
| Parameter tuning | No | Yes (current vs suggested) | Yes |
| Market context | No | Yes (balance, orders, history) | Yes |
| CI-readable output | No | Yes (JSON comment) | No |
| Time | ~30s | ~2-5 min | ~30-60 min |

## Usage Examples

### Basic usage (high depth)
```
skill("trading-agent")
```

### Ultra depth
```
Run trading-agent ultra
```

### Quick pre-trade check
```
Run trading-agent low — just check balance and risk
```

### Specific agents only
```
Run trading-agent with agents: market_analysis, risk_assessment
```

## Limitations

- **No live market data**: Uses cached oracle data, not real-time WebSocket
- **No backtest engine**: Cannot run actual backtests, only parameter analysis
- **No ML predictions**: No GARCH/OU model training, only current state analysis
- **Token cost**: 6-12x of single-agent analysis
- **Rate limits**: 6 parallel agents may hit provider limits

## Future Improvements

1. **Live market feed**: WebSocket connection for real-time prices
2. **Backtest integration**: Run actual backtests against historical data
3. **ML model integration**: GARCH, OU, HMM predictions
4. **Auto-optimization**: Automatically adjust parameters based on findings
5. **Portfolio analysis**: Multi-item portfolio optimization
6. **Risk dashboard**: Real-time risk metrics visualization
7. **Paper trading**: Simulate trades with findings applied
8. **Alert integration**: Send findings to Telegram automatically

## Changelog

### v1.2 (2026-07-19)
- Improved research_context injection into ALL agents (6-10 now have it)
- Enhanced prompts with cross-reference instructions for all agents
- Market Analysis agent now uses research_context instead of inline web-search
- All agents now have deep research integration
- 34 research_context references across 14 agents

### v1.1 (2026-07-19)
- Added Phase 0.5: Deep Research Agent (market intelligence, event research)
- Added research_context injection into ALL agents (1-11)
- Added cross-reference with web sources for all findings
- Market event detection (CS2 Major, Steam Sale, DMarket outages)
- Vulnerability research via web-search
- Competitor analysis (Skinport, Buff market)
- Best practices verification from web sources

### v1.0 (2026-07-19)
- Initial release with 12 specialized trading agents
- Cross-Reference Engine (Codex-style)
- Shared findings buffer (/tmp/opencode-trading-xref/)
- Conflict detection between agent recommendations
- Impact chain analysis
- Financial impact estimates per finding
- Parameter tuning recommendations (current vs suggested)
- CI-readable output format
- Integration with DMarket API tools
- Depth levels: low/medium/high/ultra
