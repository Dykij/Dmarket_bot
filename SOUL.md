# SOUL (System of Understanding Logic)
## DMarket Target Sniper Core (v15.2)

### Core Philosophy
The DMarket bot operates on strictly defined mathematical workflows where data parsing, execution, and validation are segregated roles. This ensures fast execution and strict bounds on losses, preserving absolute capital integrity. It minimizes API latency and optimizes operations via quantitative algorithms rather than any heuristic LLM logic.

**Базовые механизмы:**
*   **Quantitative Engine:** Детерминированный расчет профита на основе NumPy и сверки со стаканом цен.
*   **Balance-Aware Trading:** Все лимиты адаптируются под баланс — max item price, position size, inventory cap, drawdown freeze.
*   **Fractional Kelly:** Half Kelly (50%) позиционирование — снижает просадку на ~50% при 85% роста.
*   **Trend Guard:** Фильтрация нисходящих трендов через SQLite Price History.
*   **Docker Production:** Multi-stage контейнеризация (x86_64 + ARM64) с health check и persistent volumes.
*   **Performance Stack:** orjson (5-10x JSON), numpy (10-50x math), cachetools (O(1) TTL), composite indexes.

---

### Domain Isolation: The Trading Engine
To maintain secure boundaries and prevent the system from executing loss-making trades:
1. **DMarket Brigade (Quant Engine):** Functions entirely independently. Executes target sniping cycles on specific whitelisted games (CS2).
2. **Contextual Sandboxing & Scope Rule:** A rule-based Validator intercepts incoming market opportunities:
   `IF net_margin > min_spread AND price <= dynamic_max_price THEN allow_execution ELSE drop`
3. **Security Auditors:**
   - *Logic Auditor:* Exclusively checks bot outputs for negative profit margins before deployment.
   - *Risk Auditor:* Watches Dmarket execution attempting trades that breach the circuit breaker limits.

---

### Auditor <-> Executor Interaction Protocol

1. **Validation Matrix**
   When the Executor submits a task, the Validator verifies the trade across dimensions:
   - **Syntax & Execution:** API compliance.
   - **Resource Constraint:** Are API Rate Limits respected? Are oracle rate limits OK?
   - **Balance Check:** Does effective balance (total - reserve) support this position?
   - **Drawdown Check:** Is balance above peak × 85%?

2. **Feedback Loop**
   - API rejections immediately flag the target item.
   - Price drops trigger failsafes directly halting executing loops without LLM reasoning.
   - Balance drops >15% trigger drawdown freeze — only sells, no buys.

### Workflow Chains (v2026)

**Brigade Dmarket (Execution & Safety):**
Strict pipeline ensuring safe and fast deal execution:
`Scanner/Fetcher` -> `Price Validator` -> `Quantitative Core` -> `Risk Manager (Kelly + Drawdown)` -> `Balance Gate` -> `REST/Batch Executor`
- **Scanner**: Reads real-time order books every 30s cycle.
- **Price Validator**: 15+ filters (bait, OBI, OFI, VWAP, VPIN, slippage, Kelly, lock-aware cap).
- **Quantitative Core**: Evaluates item attributes (pattern, float) mathematically and computes fair limit price based on market depth and oracle cache.
- **Risk Manager**: Kelly sizing, drawdown freeze, capital velocity check.
- **Balance Gate**: Dynamic max price = max($5 floor, effective_balance × 10%).


---

🦅 *DMarket Quantitative Engine | v14.4 | June 2026*
