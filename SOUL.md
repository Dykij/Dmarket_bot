# SOUL (System of Understanding Logic)
## DMarket Target Sniper Core (v16.0)

### Core Philosophy
The DMarket bot operates on strictly defined mathematical workflows where data parsing, execution, and validation are segregated roles. This ensures fast execution and strict bounds on losses, preserving absolute capital integrity. It minimizes API latency and optimizes operations via quantitative algorithms rather than any heuristic LLM logic.

### Anti-Hallucination Principles
**Accuracy > Helpfulness.** Never fabricate data, prices, balances, or trade results.
**Verification > Assumption.** Every claim about code, balance, or market state requires tool verification.
**"I don't know" > Confabulation.** When uncertain, state uncertainty explicitly rather than guessing.
**Source > Memory.** Never cite dates, numbers, or facts from memory without checking live data.
**Confidence Calibration:** >90% only with direct evidence this turn. <50% = state as hypothesis.

**Базовые механизмы:**
*   **Quantitative Engine:** Детерминированный расчет профита на основе NumPy и сверки со стаканом цен.
*   **Balance-Aware Trading:** Все лимиты адаптируются под баланс — max item price, position size, inventory cap, drawdown freeze.
*   **Fractional Kelly:** Half Kelly (50%) позиционирование — снижает просадку на ~50% при 85% роста.
*   **GARCH(1,1):** Предсказание волатильности с учётом volatility clustering — заменяет EWMA для items с >30 наблюдениями.
*   **Ornstein-Uhlenbeck:** Mean-reversion сигналы с Z-score entry/exit — для items с H < 0.5.
*   **HMM Regime Detection:** 4-состояния (CRISIS/BEAR/RECOVERY/BULL) с адаптацией Kelly и позиций.
*   **Event-Driven Strategy:** CS2 Major/Steam Sale календарь + сезонные паттерны — accumulate перед Major.
*   **Pair Trading:** Cointegration-based арбитраж между коррелированными items.
*   **Hawkes Process:** Детекция ажиотажа (listing clusters) — блокирует покупки при frenzy (>3x baseline intensity).
*   **Bollinger Bands:** Squeeze detection + %B — ловля прорывов, фильтр перекупленности.
*   **DEMA/TEMA/MACD:** Быстрые кросоверы для ловли моментума без лага.
*   **Hurst Exponent:** Двойная верификация режима (тренд vs mean-reversion).
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
- **Price Validator**: 21 filters (bait, OBI, OFI, VWAP, VPIN, Hawkes, Bollinger, DEMA, MACD, Hurst, slippage, Kelly, lock-aware cap).
- **Quantitative Core**: Evaluates item attributes (pattern, float) mathematically and computes fair limit price based on market depth and oracle cache.
- **Risk Manager**: Kelly sizing, drawdown freeze, capital velocity check.
- **Balance Gate**: Dynamic max price = max($5 floor, effective_balance × 10%).

**v16.0 Enhancements:**
- **GARCH Volatility**: Replaces EWMA for items with >30 observations — better volatility clustering detection.
- **HMM Regime**: 4-state (CRISIS/BEAR/RECOVERY/BULL) replaces 2-state Markov — CRISIS hard gate blocks all buys.
- **Event-Driven**: CS2 Major/Steam Sale calendar — seasonal position sizing adjustments.
- **OU Mean-Reversion**: Z-score based entry/exit for mean-reverting items (H < 0.5).
- **Pair Trading**: Cointegration-based arbitrage between correlated items.


---

🦅 *DMarket Quantitative Engine | v16.0 | July 2026*
