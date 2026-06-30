# 🦅 DMarket Quantitative Engine v14.9

**Algorithmic CS2 skin trading bot for DMarket marketplace + CS2Cap multi-market oracle (41 marketplaces).**

Автономная торговая система на строгих количественных алгоритмах. Стратегия: **Value Detection Scanner** + intra-market spread sniping + cross-market arbitrage — с мгновенной капитализацией спреда (TRADE_LOCK_HOURS=0).

**Ключевое отличие v14.9:** Бот теперь использует **dual-signal pipeline** — Value Scanner (primary) и Spread Sniper (secondary). Это позволяет находить недооцененные предметы по rarity (float, pattern, sticker) даже без естественного bid/ask спреда.

---

## 🧠 Стратегия — Как работает (v14.9)

### Концепция

Бот сканирует DMarket marketplace в поиске **недооцененных предметов** — тех, у которых редкие атрибуты (float, phase, pattern, stickers) позволяют продать их дороже рыночной цены, или когда текущая цена продавца (`best_ask`) значительно ниже ближайшего bid-ордера (`best_bid`), или когда на внешнем маркетплейсе (CSFloat, Skinport, Buff163) бай-ордер выше DMarket ask. Находит — покупает мгновенно — **немедленно выставляет на продажу** по агрегированным ценам CS2Cap (41 маркетплейс) с учётом комиссий.

**Ключевое отличие:** DMarket разрешает мгновенную перепродажу предметов, купленных на marketplace. Steam Trade Protection (7 дней) блокирует только вывод в Steam, не внутриплатформенную торговлю. Бот использует это: capital velocity ~3-5 сделок/день на единицу капитала.

---

## 🎯 Dual-Signal Pipeline (v14.9)

### Primary Signal — Value Scanner

Бот теперь **первично** ищет предметы по rarity signals, а не только по spread:

```
Предмет с редким float/pattern/sticker
    → Оцениваем fair_price = cs2cap_ask × rarity_premium
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
| **Value Signal Evaluator** | rarity_premium × cs2cap_ask vs buy_price | Находить недооцененные редкости |
| **Spread Signal Evaluator** | best_bid vs best_ask | Ликвидные предметы с естественным спредом |
| **CS2Cap Cache** | In-memory 5-min TTL | Быстрый lookup цен без API calls |
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
  ├─ 2. CS2Cap Cache refresh (in-memory, if needed)
  │      └─ POST /prices/batch + /bids/batch
  │
  ├─ 3. Fetch cheapest listings per title (parallel)
  │      └─ GET /market/items?title=X&limit=30
  │
  ├─ 4. Value Detection Pipeline (v14.9, for each item):
  │      ├─ Оценка float premium (1.08-1.30×)
  │      ├─ Оценка pattern/phase premium (1.0-5.0×)
  │      ├─ Оценка sticker combo (+50-100%)
  │      ├─ Оценка filler demand (1.15×)
  │      ├─ est_sell = cs2cap_ask × premium_mult
  │      └─ BUY если est_sell > ask × (1 + fee + margin)
  │
  ├─ 5. Spread Fallback Pipeline (если value не прошёл):
  │      └─ best_bid > best_ask × (1 + fee + margin)
  │
  ├─ 6. Execute buys → POST /exchange/v1/market/buy
  │
  ├─ 7. Auto-resale (A-S reservation price)
  │      └─ List at min(cs2cap_ask × 0.97, rarity_adjusted_price)
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
| **Market data** | DMarket API v2 + CS2Cap REST | Цены, ордера, листинги, комиссии |
| **Rate limiting** | Adaptive throttle + circuit breaker | API quota management |
| **Security** | Vault (Fernet) + log redaction | API ключи |
| **Interface** | Aiogram 3.x (Telegram) | Управление, мониторинг |
| **Deployment** | Docker multi-stage (x86_64 + ARM64) | Production-ready |

### Структура модулей (v14.9)

```
src/
├── api/                           # Внешние API
│   ├── dmarket_api_client/        # DMarket REST v2
│   ├── cs2cap_oracle/             # CS2Cap REST
│   └── cs2cap_cache.py            # In-memory cache
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
# Заполнить ключи в ._CI: DMARKET_PUBLIC_KEY, DMARKET_SECRET_KEY, CS2CAP_API_KEY, TELEGRAM_BOT_TOKEN

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
OBI_ENABLED=false
OFI_ENABLED=false
VWAP_FILTER_ENABLED=false
CVD_ENABLED=false
VPIN_ENABLED=false

# ===== v14.9 PRICE RANGE SCAN (wide-net) =====
PRICE_RANGE_SCAN_ENABLED=true
PRICE_RANGE_MIN_USD=0.50
PRICE_RANGE_MAX_USD=20.00
PRICE_RANGE_MAX_TITLES=500       # Scan more items per cycle
CS2CAP_TOP_K_VALIDATE=50         # Validate 50 items vs CS2Cap

# ===== КЛЮЧИ =====
DMARKET_PUBLIC_KEY=your_public_key
DMARKET_SECRET_KEY=your_secret_key
CS2CAP_API_KEY=your_cs2cap_key
TELEGRAM_BOT_TOKEN=your_bot_token
```

---

## 📊 Текущее состояние (v14.9)

| Свойство | Статус |
|---|---|
| **Версия** | v14.9 |
| **Стратегия** | Value Detection Scanner + Spread Sniper (dual-signal) |
| **DMarket API** | v2 batch endpoints |
| **CS2Cap** | Starter tier, 41 marketplace |
| **Value Signals** | Float, Pattern, Sticker, Filler (9 layers total) |
| **Balance-aware** | Dynamic max price, Kelly sizing, drawdown freeze |
| **Fee model** | 4-tier dynamic (2/5/7/10%) + hot-fee cache |
| **Risk manager** | Drawdown, Kelly, pump detector |
| **Security** | Fernet vault, log redaction |
| **Docker** | Multi-stage build (x86_64 + ARM64) |
| **Tests** | 289 tests (unit + bottleneck + sandbox) |

---

## ⚠️ Дисклеймер

Экспериментальное торговое ПО. Рынок CS2 скинов волатилен. Никакая стратегия не гарантирует прибыль. Используйте на свой страх и риск. **Начинайте с DRY_RUN=true** и малого капитала ($20-50).

```
🦅 DMarket Quantitative Engine | v14.9 | June 2026
```