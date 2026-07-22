# ANALYSIS_STAGE2.md — Глубокий анализ кодовой базы

**Дата:** 2026-07-22 | **Версия проекта:** v16.2

---

## 1. DMarket API Core (`src/api/dmarket_api_client/`)

### core.py — Оркестратор API клиента
| Проверка | Статус | Детали |
|----------|--------|--------|
| Ed25519 подпись | ✅ CORRECT | Rust signer (PyO3) + Python fallback (pynacl). Формат: `dmar ed25519 {signature}` |
| Шифрование ключа | ✅ CORRECT | Fernet encryption через Vault, дешифровка на лету, secure zero после подписи |
| Rate limiting | ✅ CORRECT | Per-endpoint token bucket (50% safety margin), adaptive 429 handling |
| Circuit breaker | ✅ CORRECT | 3 failures → OPEN, exponential backoff 30-300s, jitter 20% |
| DRY_RUN guard | ✅ CORRECT | Write operations (POST/PUT/DELETE/PATCH) симулируются, read-only POST (aggregated-prices) пропускается |
| Retry logic | ✅ CORRECT | 3 attempts, exponential backoff 2-10s, retry only on transient (timeout, connection, 5xx) |
| Clock sync | ✅ CORRECT | Sync with DMarket server to prevent 401 from clock drift > 120s |
| msgspec | ✅ CORRECT | 5-10x faster JSON parsing vs stdlib json |

### targets.py — Buy-side targets
| Проверка | Статус | Детали |
|----------|--------|--------|
| buy_items endpoint | ✅ CORRECT | PATCH /exchange/v1/offers-buy (verified 2026-06-06) |
| Idempotency | ✅ CORRECT | clientOrderId = `{item_id}_{timestamp}_{sha256_hash[:12]}` |
| batch_create_targets | ✅ CORRECT | POST /marketplace-api/v1/user-targets/create |

### offers.py — Sell-side offers
| Проверка | Статус | Детали |
|----------|--------|--------|
| batch_create_offers_v2 | ✅ CORRECT | POST /marketplace-api/v2/offers:batchCreate, priceCents = int(round(usd*100)) |
| batch_edit_offers_v2 | ✅ CORRECT | POST /marketplace-api/v2/offers:batchUpdate |
| batch_delete_offers_v2 | ✅ CORRECT | POST /marketplace-api/v2/offers:batchDelete |
| Idempotency | ✅ CORRECT | clientOrderId for each offer |

### rate_limiter.py — Token Bucket
| Проверка | Статус | Детали |
|----------|--------|--------|
| Per-endpoint limits | ✅ CORRECT | Market: 10 RPS, Fee: 110 RPS, Last sales: 6 RPS, Other: 20 RPS |
| Safety margin | ✅ CORRECT | 50% of documented limit (conservative) |
| Adaptive margin | ✅ CORRECT | Adjusts based on 429 rate (0.3-0.7 range) |
| Token bucket algorithm | ✅ CORRECT | Refill rate = rate, capacity = rate, acquire() with wait |

---

## 2. Oracle Integrations (`src/api/`)

### Market.CSGO Oracle (`market_csgo_oracle.py`)
| Проверка | Статус | Детали |
|----------|--------|--------|
| Endpoint | ✅ CORRECT | `https://market.csgo.com/api/v2/prices/USD.json` |
| Response parsing | ✅ CORRECT | `items[].market_hash_name`, `items[].price` (USD float), `items[].volume` (int) |
| Rate limiting | ✅ CORRECT | 5 RPS documented, 2.5 RPS safe (50% margin), lock-based throttle |
| 429 handling | ✅ CORRECT | Retry-After header parsing, exponential backoff |
| Cache | ✅ CORRECT | 15 min TTL, in-memory cache |
| SQLite persist | ✅ CORRECT | `price_db.record_price(f"marketcsgo:{name}", price, source="marketcsgo")` |

### Waxpeer Oracle (`waxpeer_oracle.py`)
| Проверка | Статус | Детали |
|----------|--------|--------|
| Endpoint | ✅ CORRECT | `https://api.waxpeer.com/v1/prices?game=csgo` |
| Response parsing | ✅ CORRECT | `items[].name`, `items[].min` (mills), `items[].count`, `items[].steam_price` (mills) |
| Price conversion | ✅ CORRECT | `float(min_cents) / 1000.0` — mills to USD |
| Rate limiting | ✅ CORRECT | ~1 RPS community estimate, 0.5 RPS safe |
| 429 handling | ✅ CORRECT | Retry-After + exponential backoff |

### CSFloat Oracle (`csfloat_oracle.py`)
| Проверка | Статус | Детали |
|----------|--------|--------|
| Endpoint | ✅ CORRECT | `https://csfloat.com/api/v1/listings` |
| Response parsing | ✅ CORRECT | `data[0].price / 100.0` — cents to USD |
| Authorization | ✅ CORRECT | `Authorization: {api_key}` header |
| 429 handling | ✅ CORRECT | tenacity retry with exponential backoff, adaptive delay in State DB |
| Sales history | ✅ CORRECT | `/history` endpoint, price_cents / 100.0 |
| Filtered listings | ✅ CORRECT | `/listings` with min_float, max_float, paint_seed, paint_index params |

### Steam Oracle (`steam_oracle.py`)
| Проверка | Статус | Детали |
|----------|--------|--------|
| Endpoint | ✅ CORRECT | `https://steamcommunity.com/market/priceoverview/` |
| Params | ✅ CORRECT | appid=730, currency=1 (USD), market_hash_name |
| Price parsing | ✅ CORRECT | `$12.34` format → `float(cleaned)` |
| Cash conversion | ✅ CORRECT | `price * 0.85` — Steam Wallet to cash-equivalent |
| Rate limiting | ✅ CORRECT | 0.15s delay (~6-7 req/sec) |
| Retry | ✅ CORRECT | 3 attempts with exponential backoff |

### Multi-Source Oracle (`multi_source_oracle.py`)
| Проверка | Статус | Детали |
|----------|--------|--------|
| Source combination | ✅ CORRECT | PriceReference with per-source prices + volumes |
| Circuit breaker | ✅ CORRECT | 5 failures → OPEN, 60s recovery, half-open retry |
| Data Freshness Guard | ✅ CORRECT | marketcsgo: 10min, waxpeer: 10min, csfloat: 10min, steam: 30min |
| Dynamic TTL | ✅ CORRECT | Stable: 30min, Normal: 15min, Volatile: 5min |
| Cache | ✅ CORRECT | 15 min default TTL, per-title cache |
| Batch parallel | ✅ CORRECT | Semaphore(10) for concurrent oracle calls |

### Fair Price Calculator (`fair_price_calculator.py`)
| Проверка | Статус | Детали |
|----------|--------|--------|
| Outlier removal | ✅ CORRECT | Min removed if < 0.3× median of others; Max removed if > 2.0× median |
| Median calculation | ✅ CORRECT | `statistics.median(price_values)` |
| Margin tiers | ✅ CORRECT | 3%-15% based on volume (100→3%, 50→5%, 20→7%, 5→10%, 0→15%) |
| STEAM_ADJUSTMENT | ✅ CORRECT | = 1.0 (identity) — Steam oracle already applies 0.85 |
| Min margin | ✅ CORRECT | `max(sell_price, dmarket_buy_price * 1.03)` — at least 3% profit |
| Confidence | ✅ CORRECT | ≥3 sources → "high", 2 → "medium", 1 → "low" |

---

## 3. Pricing Logic Flow

### Oracle → Fair Price → Trading Decision
1. `MultiSourceOracle.get_fair_price(title)` → queries all 4 oracles
2. `FairPriceCalculator.calculate()` → outlier removal → median → margin
3. `filter.py:_evaluate_candidate()` → compares DMarket ask vs oracle price
4. `filter.py` → `has_oracle_discount = base_price < cs_price * (1 - required_margin)`
5. List price set to `cs_ask_price * 0.97` or `best_bid - discount`

### Edge Cases Handled
- ✅ All sources return 0 → `confidence="none"`, `fair_price=0.0`
- ✅ Only 1 source → `confidence="low"`, no outlier removal
- ✅ Source circuit breaker OPEN → skipped, not included in median
- ✅ Source data stale → excluded by Freshness Guard
- ✅ DMarket price 50%+ above oracle → skip (overpriced)

---

## 4. Strategy Engine

### Trading Pipeline (cycle_orchestrator.py)
| Stage | Статус | Детали |
|-------|--------|--------|
| 1. _stage_prepare | ✅ CORRECT | Balance check, Oracle init, State Reconciliation |
| 2. _stage_scan | ✅ CORRECT | DMarket aggregated-prices, cheapest listings |
| 3. _stage_prefetch | ✅ CORRECT | Bulk fee, sales cache, pump detection, MultiSource oracle |
| 4. _stage_evaluate | ✅ CORRECT | Rank + 21 filters + Value Detection + Kelly |
| 5. _stage_execute | ✅ CORRECT | Slippage check, Risk manager, buy_items |
| 6. _stage_postprocess | ✅ CORRECT | Auto-resale, repricing, Telegram, telemetry |

### Risk Management (risk_manager.py)
| Проверка | Статус | Детали |
|----------|--------|--------|
| Pre-trade check | ✅ CORRECT | Drawdown freeze, daily loss, trade count, pump blacklist |
| Drawdown freeze | ✅ CORRECT | Balance < peak × 0.85 → FREEZE (sell-only mode) |
| Daily loss limit | ✅ CORRECT | Configurable ($10 default) |
| Kelly sizing | ✅ CORRECT | Bayesian win rate + EWMA volatility + Half Kelly (50%) |
| Consecutive losses | ✅ CORRECT | 3+ losses → position size halved |

### Position Guard (position_guard.py)
| Проверка | Статус | Детали |
|----------|--------|--------|
| Stop-loss | ✅ CORRECT | Fee-aware: `loss_pct + fee_pct >= STOP_LOSS_PCT` |
| Take-profit | ✅ CORRECT | Fee-aware: `profit_pct - fee_pct >= TAKE_PROFIT_PCT` |
| Time-stop | ✅ CORRECT | Cancel stale buy targets after 90min |
| Emergency liquidation | ✅ CORRECT | Batch sell all unlocked items at best bid |

### Execution (execution.py)
| Проверка | Статус | Детали |
|----------|--------|--------|
| Slippage protection | ✅ CORRECT | Re-verify price before buy, 5% max slippage |
| Inventory cap | ✅ CORRECT | Cumulative tracking to prevent TOCTOU |
| Saturation check | ✅ CORRECT | Max N units of same item |
| Lock-aware cap | ✅ CORRECT | ≤80% capital in trade-lock |
| Balance decrement | ✅ CORRECT | `available_balance -= base_price` after each buy |

---

## 5. Архитектурная проверка: Операции вне DMarket

### РЕЗУЛЬТАТ: ✅ НЕТ операций buy/sell/list/withdraw на площадках, отличных от DMarket

Проверено:
- `src/api/market_csgo_oracle.py` — только GET запросы (read-only)
- `src/api/waxpeer_oracle.py` — только GET запросы (read-only)
- `src/api/csfloat_oracle.py` — только GET запросы (read-only)
- `src/api/steam_oracle.py` — только GET запросы (read-only)
- `src/strategies/cross_market.py` — использует oracle данные для оценки, НЕ выполняет сделки на других площадках

**Все торговые операции (buy/sell/list) проходят ТОЛЬКО через `src/api/dmarket_api_client/`.**

---

## 6. Расхождения с документацией оракулов

### Market.CSGO
- ✅ Endpoint: `https://market.csgo.com/api/v2/prices/USD.json` — соответствует документации
- ✅ Response format: `items[].market_hash_name`, `items[].price`, `items[].volume` — корректно
- ✅ Rate limit: 5 RPS documented → 2.5 RPS safe — корректно

### Waxpeer
- ✅ Endpoint: `https://api.waxpeer.com/v1/prices?game=csgo` — соответствует документации
- ✅ Price unit: mills (1/1000 USD) — корректно конвертируется
- ✅ Response format: `items[].name`, `items[].min`, `items[].count`, `items[].steam_price` — корректно

### CSFloat
- ✅ Endpoint: `https://csfloat.com/api/v1/listings` — соответствует документации
- ✅ Price unit: cents → /100.0 — корректно
- ✅ Authorization: API key header — корректно

### Steam
- ✅ Endpoint: `https://steamcommunity.com/market/priceoverview/` — соответствует документации
- ✅ Params: appid=730, currency=1 — корректно
- ✅ Cash conversion: 0.85 factor — корректно (Steam Wallet prices ~15% higher)

---

## 7. Найденные потенциальные проблемы (для Stage 3)

1. **execution.py:445-455** — `asyncio.create_task()` без ожидания (fire-and-forget для Telegram уведомлений). Хотя task reference сохраняется в `_background_tasks`, это может привести к проблемам при shutdown.

2. **position_guard.py:59** — `__import__("time").time()` вместо `import time` в начале файла. Не критично, но стилистически плохо.

3. **filter.py:198-199** — Kelly fallback: `kelly_f = max(0.0, min(0.25, kelly_f))` — clamp to 0.25 may be too aggressive for some risk profiles.

4. **multi_source_oracle.py:210-215** — Sequential oracle calls (not parallel) despite comment saying "serialized automatically". Each oracle has its own rate limiter, so they COULD run in parallel.

5. **fair_price_calculator.py:133-150** — Outlier removal only removes ONE outlier (either min OR max), not both. If both min and max are outliers, only one gets removed.
