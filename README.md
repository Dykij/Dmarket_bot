# 🦅 DMarket Quantitative Engine v15.6

**Algorithmic CS2 skin trading bot for DMarket marketplace + Multi-Source Oracle (4 free external APIs).**

Автономная торговая система на строгих количественных алгоритмах. Стратегия: **Value Detection Scanner** + intra-market spread sniping + cross-market arbitrage — с мгновенной капитализацией спреда (TRADE_LOCK_HOURS=0).

**Ключевое отличие v15.6:** Token bucket rate limiting (0 429 ошибок), Hybrid Kelly+Volatility sizing, Slippage-at-Risk pre-trade filter, GIL release в Rust (4x parallel speedup), structured error handling, dead code cleanup (~3,000 строк удалено).

---

## 🧠 Стратегия — Как работает (v14.9)

### Концепция

Бот сканирует DMarket marketplace в поиске **недооцененных предметов** — тех, у которых редкие атрибуты (float, phase, pattern, stickers) позволяют продать их дороже рыночной цены, или когда текущая цена продавца (`best_ask`) значительно ниже ближайшего bid-ордера (`best_bid`), или когда на внешнем маркетплейсе (Market.CSGO, Waxpeer, CSFloat, Steam) бай-ордер выше DMarket ask. Находит — покупает мгновенно — **немедленно выставляет на продажу** по агрегированным ценам Multi-Source Oracle (4 бесплатных источника) с учётом комиссий.

**Ключевое отличие:** DMarket разрешает мгновенную перепродажу предметов, купленных на marketplace. Steam Trade Protection (7 дней) блокирует только вывод в Steam, не внутриплатформенную торговлю. Бот использует это: capital velocity ~3-5 сделок/день на единицу капитала.

---

## 🎯 Dual-Signal Pipeline (v14.9)

### Primary Signal — Value Scanner

Бот теперь **первично** ищет предметы по rarity signals, а не только по spread:

```
Предмет с редким float/pattern/sticker
    → Оцениваем fair_price = multi_source_price × rarity_premium
    → Если fair_price > ask × (1 + fee + min_margin)
        → BUY (даже если нет natural spread!)
```

| Rarity Signal | Premium | Триггер покупки |
|---|---|---|
| **Float Premium** (FN-0, dirty BS) | 1.08–1.30× | Да, если est_sell > cost |
| **Pattern Premium** (Ruby, Blue Gem) | 1.5–5.0× | Да, если est_sell > cost |
| ** NejdeKAB1-6** | 1.0–3.0× | Да, если est_sell > cost |
| **Filler Tracker** | 1.15× | Да, если est_sell > cost |
| **Round-Float/Date** | 1.08–1.15× | Да, если est_sell > cost |

**Важно:** Value signal **не требует** `best_bid > best_ask`. Предмет может быть куплен даже если `best_bid == best_ask` (no spread), если rarity premium дает профит.

### Secondary Signal — Spread Sniper (fallback)

Для ликвидных предметов без rarity premium — традиционный intra-spread:
```
best_bid > best_ask × (1 + fee + margin) → BUY
```

---

## 🛠 Финансовые инструменты (v14.9)

### Основные (Value Scanner)

| Инструмент | Суть | Для чего |
|---|---|---|
| **Value Signal Evaluator** | rarity_premium × fair_price vs buy_price | Находить недооцененные редкости |
| **Spread Signal Evaluator** | best_bid vs best_ask | Ликвидные предметы с естественным спредом |
| **Multi-Source Oracle** | Market.CSGO + Waxpeer + CSFloat + Steam | Агрегация цен с 4 бесплатных источников |
| **Fair Price Calculator** | Median with outlier removal | Корректная оценка рыночной цены |
| **Dynamic Fee Lookup** | 2/5/7/10% tiers | Корректный профит после комиссий |

### Risk Management

| Инструмент | Суть |
|---|---|
| **Hybrid Kelly+Volatility** | position = capital × kelly × (1 - vol_factor) (arXiv:2508.16598) |
| **Slippage-at-Risk** | Pre-trade liquidity risk filter (arXiv:2603.09164) |
| **Drawdown Freeze** | Стоп покупок при >15% просадке |
| **Lock-Aware Cap** | ≤80% капитала в trade-lock |
| **Capital Velocity** | Мин. 0.5× оборота/неделю |
| **Time-Stop** | Cancel stale buy targets after 90min |
| **Token Bucket Rate Limiter** | Per-endpoint rate limiting (0 429 errors) |

---

## 🔄 Пайплайн (один цикл, ~30 секунд)

```
СТАРТ ЦИКЛА (run_cycle)
  │
  ├─ 1. DMarket aggregated-prices (batch 100 titles)
  │      └─ best_ask, best_bid, ask_count, bid_count
  │
  ├─ 2. Multi-Source Oracle refresh (Market.CSGO + Waxpeer + CSFloat + Steam)
  │      └─ Fair Price Calculator: median with outlier removal
  │
  ├─ 3. Fetch cheapest listings per title (parallel)
  │      └─ GET /market/items?title=X&limit=30
  │
  ├─ 4. Value Detection Pipeline (v14.9, for each item):
  │      ├─ Оценка float premium (1.08-1.30×)
  │      ├─ Оценка pattern/phase premium (1.0-5.0×)
  │      ├─ Оценка sticker combo (+50-100%)
  │      ├─ Оценка filler demand (1.15×)
  │      ├─ est_sell = fair_price × premium_mult
  │      └─ BUY если est_sell > ask × (1 + fee + margin)
  │
  ├─ 5. Spread Fallback Pipeline (если value не прошёл):
  │      └─ best_bid > best_ask × (1 + fee + margin)
  │
  ├─ 6. Execute buys → POST /exchange/v1/market/buy
  │
  ├─ 7. Auto-resale (A-S reservation price)
  │      └─ List at min(fair_price × 0.97, rarity_adjusted_price)
  │
  └─ 8. Equity report + health metrics
```

---

## 🏗 Архитектура

### Стек

| Компонент | Технология | Назначение |
|---|---|---|
| **Runtime** | Python 3.13+ (asyncio + uvloop) | Основной движок (2-4x faster event loop) |
| **Rust core** | PyO3 0.23 / ed25519-dalek | Ed25519 подпись (5-10× быстрее Python), GIL release |
| **Database** | SQLite 3 (WAL mode, dual DB) | OLTP: состояние. OLAP: история цен |
| **Market data** | DMarket API v2 + Multi-Source Oracle | Цены, ордера, листинги, комиссии |
| **Price sources** | Market.CSGO, Waxpeer, CSFloat, Steam | Бесплатные внешние источники цен |
| **Rate limiting** | Token bucket + circuit breaker | Per-endpoint rate limiting (0 429 errors) |
| **Security** | Vault (Fernet) + log redaction | API ключи |
| **Interface** | Aiogram 3.x (Telegram) | Управление, мониторинг, FSM settings |
| **Deployment** | Docker multi-stage (x86_64 + ARM64) | Production-ready, BuildKit cache |

### Структура модулей (v15.6)

```
src/
├── api/                           # Внешние API
│   ├── dmarket_api_client/        # DMarket REST v2
│   │   ├── core.py                # Token bucket rate limiter
│   │   ├── backoff.py             # Circuit breaker + exponential backoff
│   │   ├── rate_limiter.py        # ⭐ v15.6: Per-endpoint token bucket
│   │   └── ...
│   ├── multi_source_oracle.py     # Multi-Source Oracle (4 free APIs)
│   ├── market_csgo_oracle.py      # Market.CSGO price oracle (rate limited)
│   ├── waxpeer_oracle.py          # Waxpeer price oracle (rate limited)
│   ├── csfloat_oracle.py          # CSFloat price oracle (dynamic adaptive)
│   ├── steam_oracle.py            # Steam Community Market oracle
│   ├── fair_price_calculator.py   # Median price aggregation
│   └── candle_builder.py          # OHLCV candles from DMarket
│
├── core/target_sniping/           # Основной торговый пайплайн
│   ├── core.py                    # SnipingLoop orchestrator
│   ├── filter.py                  # Legacy spread filters
│   ├── value_pipelines.py         # ⭐ v14.9: Dual-signal eval
│   ├── scanner.py                 # Parallel listing fetcher (rate limited)
│   ├── execution.py               # Instant-buy execution
│   ├── pricing.py                 # Float/pattern/sticker premium
│   ├── validations.py             # ⭐ v15.6: Slippage-at-Risk filter
│   ├── position_guard.py          # ⭐ v15.6: Time-stop for stale positions
│   └── resale.py                  # Auto-resale logic
│
├── risk/                          # Risk management
│   ├── risk_manager.py            # Drawdown, Kelly, etc.
│   ├── dynamic_manager.py         # ⭐ v15.6: Hybrid Kelly+Volatility
│   ├── price_validator.py         # ⭐ v15.6: Double-sided fee validation
│   ├── pump_detector.py           # FOMO spike detection
│   └── security_auditor.py        # Log redaction
│
├── telegram/                      # Telegram Admin Panel
│   ├── control_bot/               # aiogram 3.x commands
│   │   ├── error_handling.py      # ⭐ v15.6: Structured error handling
│   │   ├── callback_data.py       # ⭐ v15.6: Type-safe CallbackData factory
│   │   ├── settings_fsm.py        # ⭐ v15.6: FSM for settings management
│   │   └── ...
│   └── notifier.py                # Push notifications
│
├── db/                            # Database layer
│   ├── price_history/             # Bifurcated SQLite (state + history)
│   └── profit_tracker.py          # Trades + P&L tracking
│
├── rust_core/                     # Rust extension (PyO3 0.23)
│   └── src/lib.rs                 # GIL release, benchmarks
│
└── config.py                      # Single source of truth
```

### Модель данных (SQLite)

```sql
-- Виртуальный инвентарь (OLTP — state.db)
virtual_inventory (
    id, hash_name, buy_price, sell_price, fee_paid, profit,
    status,        -- idle | listed | selling | sold | failed
    exclusive,     -- 1 = keep-forever (rare float/stickers/phase)
    acquired_at, unlock_at, sold_at,
    dm_item_id, dm_offer_id, value_signal_type, -- "float","pattern","sticker","spread"
)
```

---

## 🔧 Быстрый старт

### Docker (рекомендовано)

```bash
# 1. Клонировать репо
git clone https://github.com/Dykij/Dmarket_bot.git
cd Dmarket_bot

# 2. Создать .env
cp .env.example .env
# Заполнить ключи: DMARKET_PUBLIC_KEY, DMARKET_SECRET_KEY, TELEGRAM_BOT_TOKEN

# 3. Запустить в DRY_RUN (без торговли)
docker compose up -d

# 4. Смотреть логи
docker compose logs -f
```

### .env (v14.9 ключевые параметры)

```env
# ===== РЕЖИМ =====
DRY_RUN=true                     # Сначала DRY_RUN=true!

# ===== v14.9 VALUE SCANNER =====
VALUE_SCAN_ENABLED=true
VALUE_SCAN_MIN_PREMIUM=1.05      # 5% minimum rarity premium
VALUE_SCAN_MIN_PROFIT_PCT=0.5    # 0.5% min profit margin
VALUE_SCAN_MIN_PROFIT_USD=0.20   # $0.20 min absolute profit

# ===== v14.9 MICROSTRUCTURE (off by default for Value Scanner) =====
STRICT_MICROSTRUCTURE_FILTERS=false
OBI_ENABLED=true
OFI_ENABLED=false
VWAP_FILTER_ENABLED=true
CVD_ENABLED=false
VPIN_ENABLED=false

# ===== v14.9 PRICE RANGE SCAN (wide-net) =====
PRICE_RANGE_SCAN_ENABLED=true
PRICE_RANGE_MIN_USD=0.50
PRICE_RANGE_MAX_USD=20.00
PRICE_RANGE_MAX_TITLES=500       # Scan more items per cycle

# ===== MULTI-SOURCE ORACLE (free, no API keys required) =====
# Market.CSGO, Waxpeer, CSFloat, Steam — all free
# Optional: CSFLOAT_API_KEY for higher rate limits
# Optional: STEAM_API_KEY for Steam Community Market

# ===== КЛЮЧИ =====
DMARKET_PUBLIC_KEY=your_public_key
DMARKET_SECRET_KEY=your_secret_key
TELEGRAM_BOT_TOKEN=your_bot_token
```

---

## 📊 Текущее состояние (v15.6)

| Свойство | Статус |
|---|---|
| **Версия** | v15.6 |
| **Стратегия** | Value Detection Scanner + Spread Sniper (dual-signal) |
| **DMarket API** | v2 batch endpoints, token bucket rate limiter |
| **Price Oracle** | Multi-Source (Market.CSGO + Waxpeer + CSFloat + Steam) |
| **Value Signals** | Float, Pattern, Sticker, Filler (9 layers total) |
| **Balance-aware** | Dynamic max price, Kelly sizing, drawdown freeze |
| **Fee model** | 4-tier dynamic (2/5/7/10%) + hot-fee cache, double-sided validation |
| **Risk manager** | Hybrid Kelly+Volatility, drawdown, pump detector, time-stop |
| **Rate limiting** | Token bucket per-endpoint (0 429 errors) |
| **Security** | Fernet vault, log redaction, timing-safe auth, structured error handling |
| **Docker** | Multi-stage build (x86_64 + ARM64), BuildKit cache, STOPSIGNAL SIGTERM |
| **Tests** | 817+ tests (unit + integration + sandbox) |
| **Performance** | uvloop (2-4x async), orjson (5-10x JSON), Rust GIL release (4x parallel) |
| **Dead code** | ~3,000 строк удалено, 32 файла |
| **Telegram** | CallbackData factory, FSM settings, structured error handling |

---

## 📋 Changelog (v15.6)

### Critical Fixes (v15.6)
- **Inverted spread calculation** fixed — лимитные ордера теперь реально работают
- **Double-sided fee validation** — комиссия считается и с покупки, и с продажи
- **Idempotency keys** — нет дублей ордеров при retry
- **Year 2026 hardcoded** fixed — float-date детекция работает в 2027+
- **Kelly sizing** теперь реально вызывается (был dead code)
- **Plaintext API secret** removed — ключ больше не шлётся в открытом виде

### High Priority Fixes (v15.6)
- **Circuit breaker race condition** fixed — `_probe_pending` flag
- **Oracle HTTP timeouts** — 15s total, 5s connect (5 oracle files)
- **Sample variance** вместо population variance — точнее волатильность
- **Steam oracle retry** — 3x exponential backoff на 429
- **429 fallback URL** removed — несуществующий URL убран
- **NaN/Inf guard** в pump detector
- **Volume check** в pump detector — нет false positive на thin markets
- **CS2 budget limit** — 10% per trade для CS2

### Performance Optimization (v15.6)
- **uvloop** для event loop (2-4x faster async)
- **Token bucket rate limiter** — per-endpoint, 0 429 errors
- **Rust GIL release** — `py.allow_threads()` для parallel parsing
- **PyO3 0.23** — newer API, abi3 support
- **Composite indexes** — `(hash_name, status)` на virtual_inventory
- **atexit handlers** — clean WAL checkpoint при выходе
- **BuildKit cache mounts** — 2-5 min faster Docker rebuilds

### Security (v15.6)
- **Structured error handling** — 8 error categories, 4 severity levels
- **HTML escaping** в notifier.error()/crash()
- **CallbackData factory** — type-safe callbacks
- **Dead code cleanup** — ~3,000 строк удалено, 32 файла

### Telegram Module (v15.6)
- **6 багов исправлено** — cb_sell_top, escape_md, cmd_chart, cmd_liquidate, notifier HTML
- **CallbackData factory** — type-safe callbacks вместо raw strings
- **FSM для настроек** — /set command для изменения настроек через бота
- **Structured error handling** — ErrorHandler с категоризацией

### Oracle Improvements (v15.6)
- **Market.CSGO** — rate limiter (2.5 RPS) + 429 handling
- **Waxpeer** — rate limiter (0.5 RPS) + 429 handling
- **CSFloat** — dynamic adaptive rate limiting
- **Steam** — 429 retry with exponential backoff
- **Multi-Source** — per-source circuit breaker

### Dependencies
- **uvloop** добавлен для faster event loop
- **PyO3 0.23** вместо 0.21 (Rust core)
- **maturin** для Rust сборки

---

## ⚠️ Дисклеймер

Экспериментальное торговое ПО. Рынок CS2 скинов волатилен. Никакая стратегия не гарантирует прибыль. Используйте на свой страх и риск. **Начинайте с DRY_RUN=true** и малого капитала ($20-50).

```
🦅 DMarket Quantitative Engine | v15.2 | July 2026
```