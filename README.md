# 🦅 DMarket Quantitative Engine v14.10

**Algorithmic CS2 skin trading bot for DMarket marketplace + Multi-Source Oracle (4 free external APIs).**

Автономная торговая система на строгих количественных алгоритмах. Стратегия: **Value Detection Scanner** + intra-market spread sniping + cross-market arbitrage — с мгновенной капитализацией спреда (TRADE_LOCK_HOURS=0).

**Ключевое отличие v14.10:** Async-safe SQLite (все DB-операции вынесены из event loop в thread pool), исправлены dead validators, устранены undefined name баги, Config singleton test isolation через `reset_config()`.

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
| **Half Kelly Sizing** | position = capital × 0.5 × f* |
| **Drawdown Freeze** | Стоп покупок при >15% просадке |
| **Lock-Aware Cap** | ≤80% капитала в trade-lock |
| **Capital Velocity** | Мин. 0.5× оборота/неделю |

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
| **Runtime** | Python 3.13+ (asyncio) | Основной движок |
| **Rust core** | PyO3 / ed25519-dalek | Ed25519 подпись (5-10× быстрее Python) |
| **Database** | SQLite 3 (WAL mode, dual DB) | OLTP: состояние. OLAP: история цен |
| **Market data** | DMarket API v2 + Multi-Source Oracle | Цены, ордера, листинги, комиссии |
| **Price sources** | Market.CSGO, Waxpeer, CSFloat, Steam | Бесплатные внешние источники цен |
| **Rate limiting** | Adaptive throttle + circuit breaker | API quota management |
| **Security** | Vault (Fernet) + log redaction | API ключи |
| **Interface** | Aiogram 3.x (Telegram) | Управление, мониторинг |
| **Deployment** | Docker multi-stage (x86_64 + ARM64) | Production-ready |

### Структура модулей (v14.9)

```
src/
├── api/                           # Внешние API
│   ├── dmarket_api_client/        # DMarket REST v2
│   ├── multi_source_oracle/       # Multi-Source Oracle (4 free APIs)
│   ├── market_csgo_oracle.py      # Market.CSGO price oracle
│   ├── waxpeer_oracle.py          # Waxpeer price oracle
│   ├── csfloat_oracle.py          # CSFloat price oracle
│   ├── steam_oracle.py            # Steam Community Market oracle
│   ├── fair_price_calculator.py   # Median price aggregation
│   └── candle_builder.py          # OHLCV candles from DMarket
│
├── core/target_sniping/           # Основной торговый пайплайн
│   ├── core.py                    # SnipingLoop orchestrator
│   ├── filter.py                  # Legacy spread filters
│   ├── value_pipelines.py         # ⭐ NEW v14.9: Dual-signal eval
│   ├── scanner.py                 # Parallel listing fetcher
│   ├── execution.py               # Instant-buy execution
│   ├── pricing.py                 # Float/pattern/sticker premium
│   └── resale.py                  # Auto-resale logic
│
├── reflexion/                     # ⭐ NEW v14.9: State snapshots
│   └── core.py                    # Git-based rollback
│
├── workflow/                      # ⭐ NEW v14.9: Async pipelines
│   └── chains.py                  # Conductor pattern
│
├── sandbox/                       # ⭐ NEW v14.9: Shell execution
│   └── core.py                    # Timeout & security checks
│
├── cot_audit/                     # ⭐ NEW v14.9: CoT formatting
│   └── core.py                    # Markdown/numbered styles
│
├── integration/                   # ⭐ NEW v14.9: Unified facade
│   └── agent_facade.py            # safe_bash(), create_snapshot()
│
├── risk/                          # Risk management
│   ├── risk_manager.py            # Drawdown, Kelly, etc.
│   ├── pump_detector.py           # FOMO spike detection
│   └── security_auditor.py        # Log redaction
│
├── telegram/                      # Telegram Admin Panel
│   └── control_bot/
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

## 📊 Текущее состояние (v14.9)

| Свойство | Статус |
|---|---|
| **Версия** | v14.9 |
| **Стратегия** | Value Detection Scanner + Spread Sniper (dual-signal) |
| **DMarket API** | v2 batch endpoints |
| **Price Oracle** | Multi-Source (Market.CSGO + Waxpeer + CSFloat + Steam) |
| **Value Signals** | Float, Pattern, Sticker, Filler (9 layers total) |
| **Balance-aware** | Dynamic max price, Kelly sizing, drawdown freeze |
| **Fee model** | 4-tier dynamic (2/5/7/10%) + hot-fee cache |
| **Risk manager** | Drawdown, Kelly, pump detector |
| **Security** | Fernet vault, log redaction |
| **Docker** | Multi-stage build (x86_64 + ARM64) |
| **Tests** | 817+ tests (unit + integration + sandbox) |

---

## 📋 Changelog (v14.10)

### Async SQLite Safety
- Все синхронные `sqlite3.execute()` вызовы в async контексте обёрнуты в `await price_db.run_in_thread()`
- Bounded `ThreadPoolExecutor(max_workers=2)` для DB-операций
- Затронуты: execution.py, resale_prod.py, core.py, daily_briefing.py, self_reflection.py, bot.py

### Bug Fixes
- `config.py`: Dead validators `validate_max_price` и `validate_night_end` теперь реально проверяют значения
- `filter.py`: `is_sandbox` (undefined name) → `Config.DRY_RUN`
- `scanner.py`: `Optional[str]` → `str | None` (missing import)
- `signals.py`: spread component clamp — не выходит за [0, 1]
- `cs2cap_cache.py`: CS2CAP_* → ORACLE_* миграция Config атрибутов

### Test Infrastructure
- `conftest.py`: autouse `_reset_config_singleton` fixture для изоляции тестов
- `config.py`: `reset_config()` функция для переинициализации singleton

### Code Quality
- 8 unused imports удалены (ruff F401)
- 4 unused variables исправлены (F841)
- 8 unsorted imports исправлены (I001)
- `_secure_zero` документирован честно (не обнуляет память)

---

## ⚠️ Дисклеймер

Экспериментальное торговое ПО. Рынок CS2 скинов волатилен. Никакая стратегия не гарантирует прибыль. Используйте на свой страх и риск. **Начинайте с DRY_RUN=true** и малого капитала ($20-50).

```
🦅 DMarket Quantitative Engine | v14.10 | July 2026
```