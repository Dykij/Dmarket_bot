# SOUL (System of Understanding Logic)
## DMarket Target Sniper Core

### Core Philosophy
The DMarket bot operates on strictly defined mathematical workflows where data parsing, execution, and validation are segregated roles. This ensures fast execution and strict bounds on losses, preserving absolute capital integrity. It minimizes API latency and optimizes operations via quantitative algorithms rather than any heuristic LLM logic.

**Базовые механизмы:**
*   **Target Engine:** Использование Markov Chains для отсеивания аномалий спреда и целевых вычислений профита стикеров/флоатов.
*   **Context Compression:** Пакетный сбор данных через асинхронные сокеты.
*   **Deterministic Feedback:** Код должен проходить строгие unit-тесты (Target Sniping margin > 5%).

---

### Domain Isolation: The Trading Engine
To maintain secure boundaries and prevent the system from executing loss-making trades:
1. **DMarket Brigade (Quant Engine):** Functions entirely independently. Executes target sniping cycles on specific whitelisted games (CS2, Rust).
2. **Contextual Sandboxing & Scope Rule:** A rule-based Validator intercepts incoming market opportunities:
   `IF net_margin > 0.05 AND price <= max_budget THEN allow_execution ELSE drop`
3. **Security Auditors:**
   - *Logic Auditor:* Exclusively checks bot outputs for negative profit margins before deployment.
   - *Risk Auditor:* Watches Dmarket execution attempting trades that breach the circuit breaker limits.

---

### Auditor <-> Executor Interaction Protocol

1. **Validation Matrix**
   When the Executor submits a task, the Validator verifies the trade across dimensions:
   - **Syntax & Execution:** API compliance.
   - **Resource Constraint:** Are API Rate Limits respected?
   - **Role-Specific Checks:** For HFT tasks, does execution time fall within microsecond thresholds? Are stop-losses rigorously enforced?

2. **Feedback Loop**
   - API rejections immediately flag the target item.
   - Price drops trigger failsafes directly halting executing loops without LLM reasoning.

### Workflow Chains (v2026)

**Brigade Dmarket (Execution & Safety):**
Strict pipeline ensuring safe and fast deal execution:
`Scanner/Fetcher` -> `Price Validator` -> `Target Sniping Logic` -> `Risk Manager` -> `REST/Batch Executor`
- **Scanner**: Reads real-time order books.
- **Price Validator**: Scans for price anomalies, scientific notations, bait orders.
- **Target Logic**: Evaluates item attributes (pattern, float) mathematically and computes fair limit price.
- **Risk Manager**: Performs final checks against Dmarket constraints and account balances (5% bounds).
