# 🦅 DMarket Quantitative Engine v13.0

**High-velocity algorithmic trading for CS2 skins on DMarket marketplace + CS2Cap cross-market oracle (41 marketplaces).**

Автономная торговая система, основанная на строгих математических алгоритмах и подкреплённая академическими исследованиями рынка цифровых активов. Стратегия: **intra-market spread sniping + cross-market arbitrage** с мгновенной капитализацией спреда.

---

## 🧠 Стратегия — Как работает

### Концепция

Бот сканирует DMarket marketplace в поиске моментальных арбитражных возможностей — когда текущая цена продавца (best_ask) значительно ниже ближайшего bid-ордера (best_bid). Находит — покупает мгновенно — **немедленно выставляет на продажу** по ценам CS2Cap (агрегированные цены с 41 marketplace: BUFF163, CSFloat, Skinport, DMarket и др.) с учётом комиссии.

**Ключевое отличие**: стратегия не зависит от долгосрочного удержания активов. DMarket разрешает мгновенную перепродажу предметов, купленных на marketplace. Steam Trade Protection (7 дней) блокирует только вывод в Steam, а не внутриплатформенную торговлю. Бот использует это — capital velocity ≈ 3-5 сделок в день на единицу вложенного капитала.

### Пайплайн (один цикл, ~30 секунд)

```
СТАРТ ЦИКЛА
  │
  ├─ 1. GET /marketplace-api/v1/aggregated-prices (batch 100 titles)
  │      └─ best_ask, best_bid, ask_count, bid_count по каждой позиции
  │
  ├─ 2. Ранжирование: score = spread_$ × √volume
  │      └─ отбор top-N по смеси спреда и ликвидности
  │
  ├─ 3. GET /exchange/v1/market/items (parallel per title)
  │      └─ дешёвый листинг каждого title + атрибуты (float, фаза, стикеры)
  │
  ├─ 4. Fee estimation (volume-based, 4 tiers)
  │      └─ 2% (≥50 vol) / 5% (≥10) / 7% (≥5) / 10% (<5)
  │      └─ low-fee cache: /exchange/v1/customized-fees (hot-fee items 2%)
  │
  ├─ 5. CS2Cap oracle (in-memory cache, 5-min TTL)
  │      └─ POST /prices/batch — lowest_ask across 41 marketplaces
  │      └─ POST /bids/batch — highest_bid across 11 providers
  │
  ├─ 6. Pump detector: блокирует FOMO (>15% spike за 1 час)
  │
  ├─ 7. Parallel evaluation (semaphore=10) per candidate:
  │      │
  │      ├─ Фильтр цены: $0.50 < price < MAX_SNIPING_PRICE_USD
  │      ├─ Проверка на владение (не покупаем дубликат)
  │      ├─ Cross-market arb: bid с другой площадки > DMarket ask
  │      ├─ Ликвидность: min sales, wash-trading detection
  │      ├─ Волатильность: 14-дневный std, Garman-Klass
  │      ├─ Spread gate: spread ≥ fee × 2 + 3%
  │      ├─ List price: CS2Cap min_price × 0.97 или cross_market_bid × 0.97
  │      ├─ Float premium (опционально, off by default)
  │      ├─ Sticker detection: Katowice 2014, Crown Foil, Howl → exclusive keep
  │      ├─ Phase/pattern premium: Doppler Ruby/Sapphire, редкие paintSeed
  │      ├─ Fee-aware profit validation (validate_arbitrage_profit)
  │      ├─ Saturation check: ≤3 одинаковых, ≤30 total items, ≤$100 value
  │      └─ return buy payload → instant_buys[]
  │
  ├─ 8. Slippage protection (parallel, >5% skip)
  │      └─ re-verify listing price перед выполнением
  │
  ├─ 9. Execute instant buys: POST /exchange/v1/market/buy
  │      └─ parse response → add_virtual_item → risk record
  │
  ├─10. Auto-resale (immediate):
  │      ├─ Sync real inventory vs virtual
  │      ├─ Check external sales via /user-offers/closed
  │      ├─ List unlocked non-exclusive items:
  │      │     └─ CS2Cap ask price → batch_create_offers_v2
  │      └─ Skip exclusive (rare float/stickers/phase)
  │
  ├─11. Reprice stale listings (every ~30 min, drop 5%)
  │
  ├─12. Low-fee cache refresh (every ~50 min)
  │
  └─13. Equity report + health metrics
```

### Fairness / Competition Model (DRY_RUN)

В режиме симуляции бот моделирует конкуренцию с другими трейдерами — чем выше маржа, тем выше вероятность, что другой бот перехватит листинг раньше. Это даёт реалистичную оценку стратегии без реальных денег.

---

## 📚 Академическая база (Research-Backed)

Стратегия опирается на рецензированные исследования рынка цифровых активов CS2:

| Источник | Ключевой вывод | Применение в боте |
|---|---|---|
| **Frontiers in AI** (Guede-Fernández et al., 2025) | LSTM/NHiTS модели → 20% за 6 мес vs 5-10% buy&hold. Mil-Spec (mid-tier) — оптимальный класс активов | Фокус на Mil-Spec/Restricted, диверсификация 30-50 позиций |
| **Finance Research Letters** (Reichenbach, 2025) | 66.9% историческая годовая доходность (2015-2025). Главные риски: комиссии + волатильность | 4-х уровневая модель комиссий, pump detector, volatility gate |
| **DMarket API docs** (March 2026) | v1 deprecated 31.03.2026. v2 batchCreate/Update/Delete + aggregated-prices новый эндпоинт | Полная миграция на v2 batch endpoints |
| **DMarket Trade Protection** (Sep 2025) | Trade Protection ≠ блокировка перепродажи. Marketplace items можно листить сразу | TRADE_LOCK_HOURS=0, мгновенная перепродажа |
| **SkinEdge** (2026) | Сравнение комиссий 12 marketplace. Arbitrage: buy cheap → sell where net revenue highest | CS2Cap cross-market bids, withdrawal fee в net PnL |
| **CS2Cap** (41 marketplace) | Унификация цен с 41 площадки. BUFF163, CSFloat, Skinport, DMarket, Waxpeer и др. | Основной оракул цен. Starter $19/mo (50k req) |

---

## 🏗 Техническая архитектура

### Стек

| Компонент | Технология | Назначение |
|---|---|---|
| **Runtime** | Python 3.13+ (asyncio) | Основной движок |
| **Rust core** | PyO3 / Serde | Высокоскоростной парсинг JSON, верификация |
| **Database** | SQLite 3 (WAL mode) | История цен, виртуальный инвентарь, стейт |
| **Market data** | DMarket API v2 + CS2Cap REST | Цены, ордера, листинги, комиссии |
| **Rate limiting** | Adaptive throttle + circuit breaker | API quota management |
| **Security** | Vault (hvac) + Fernet encryption + SHA-256 lock | API ключи, integrity check |
| **Interface** | Aiogram 3.x (Telegram) | Управление, мониторинг, нотификации |
| **Health** | HTTP /healthz, /readyz, /metrics | Мониторинг состояния |

### Структура модулей

```
src/
├── api/
│   ├── dmarket_api_client/    # DMarket REST client (v2 batch endpoints)
│   │   ├── core.py            # rate limiter + HTTP transport
│   │   ├── market.py          # aggregated-prices, listings, last-sales, low-fee
│   │   ├── offers.py          # batchCreate/Update/Delete v2, user-offers
│   │   └── fees.py            # dynamic fee estimation (4 tiers, 12h cache)
│   └── cs2cap_oracle.py       # CS2Cap — 41 marketplace prices/bids/candles
├── core/
│   └── target_sniping/        # v13.0 основной пайплайн
│       ├── core.py            # Main loop orchestrator (SnipingLoop)
│       ├── filter.py          # Per-item candidate evaluation
│       ├── execution.py       # Instant-buy execution + slippage
│       ├── resale.py          # Auto-listing + reprice + sales detection
│       ├── pricing.py         # Float/pattern premium + low-fee cache
│       └── inventory.py       # Trade status sync (trade_protected/reverted)
├── db/
│   └── price_history/         # SQLite persistence layer
│       ├── core.py            # Schema + migrations
│       ├── inventory.py       # Virtual inventory + exclusive flag
│       ├── history.py         # Price history storage
│       └── state.py           # Bot state (cursors, counters)
├── risk/                      # Risk management
│   ├── risk_manager.py        # Pre-trade checks, Kelly sizing, drawdown halts
│   ├── pump_detector.py       # FOMO protection (>15%/1h spike → blacklist)
│   ├── price_validator.py     # Profit/loss, volatility, slippage validation
│   ├── fatal_errors.py        # Error classifier (fatal vs transient)
│   └── security_auditor.py    # Log redaction, integrity checks
├── strategies/                # Multi-strategy engine
│   ├── base.py                # Base strategy class
│   ├── cross_market.py        # Cross-market arbitrage via CS2Cap
│   └── market_maker.py        # Spread-based market making
├── telegram/                  # Telegram bot interface
│   ├── bot.py                 # Main bot (notifications)
│   └── control_bot/           # Admin control panel
├── analytics/                 # Self-reflection + backtesting
│   ├── self_reflection.py     # Parameter auto-tuning
│   └── stickers_evaluator.py  # Rare sticker value calculator
└── config.py                  # Single source of truth — все параметры
```

### Модель данных (SQLite)

```sql
-- Виртуальный инвентарь
virtual_inventory (
    id, hash_name, buy_price, sell_price, fee_paid, profit,
    status,          -- idle | listed | selling | sold | failed
    exclusive,       -- 0=auto-sell  | 1=keep-forever
    acquired_at, unlock_at, sold_at,
    dm_item_id, dm_offer_id, listed_at, list_error
)

-- Агрегированные цены
aggregated_prices (title, best_bid, best_ask, ask_count, bid_count, timestamp)

-- Статусы активов (от DMarket)
asset_status (item_id, title, status, finalization_time)
-- status: active | trade_protected | reverted

-- История цен (для volatility + трендов)
price_history (title, price, sale_date)

-- Low-fee кеш
low_fee_items (title, fee_rate, cached_at)

-- Pump blacklist
pump_blacklist (title, detected_at, peak_price, spike_pct)

-- Decision logs + missed opportunities (для self-reflection)
```

### Модель комиссий (2026, верифицировано через DMarket Help Center)

| Game / Operation | Ставка | Бот |
|---|---|---|
| CS2 Sell (liquid, ≥50 vol) | 2% | 2% |
| CS2 Sell (medium, 10-49 vol) | ~5% | 5% |
| CS2 Sell (low, 5-9 vol) | ~7% | 7% |
| CS2 Sell (illiquid, <5 vol) | ~10% | 10% |
| CS2 Sell (hot-fee items) | 2-3% | через `/customized-fees` API |
| Dota 2 / TF2 / Rust Sell | 5% | 5% |
| Withdrawal (net PnL) | 1-3% | 2% |
| Trade fee (targets/bids) | 2.5% | не используется (instant-buy, 0%) |

---

## 🔧 Быстрый старт

### Требования

- Python 3.13+
- Rust toolchain (для `maturin`)
- DMarket аккаунт + API ключи
- CS2Cap аккаунт (Starter: $19/mo, Pro: $79/mo)

### Установка

```bash
git clone https://github.com/Dykij/Dmarket_bot.git
cd Dmarket_bot
pip install -r requirements.txt
cd src/rust_core && maturin develop --release && cd ../..
```

### Конфигурация

Создать `.env`:
```env
# DMarket API
DMARKET_PUBLIC_KEY=your_public_key
DMARKET_SECRET_KEY=your_secret_key

# CS2Cap (41 marketplace oracle)
CS2CAP_API_KEY=your_api_key
CS2CAP_TIER=starter          # free | starter | pro | quant

# Режим работы
DRY_RUN=true                 # false = реальные деньги
TRADE_LOCK_HOURS=0           # 0 = мгновенная перепродажа (marketplace)

# Капитал + риски
MAX_PRICE_USD=20.00          # макс. цена покупки (общий лимит)
MAX_SNIPING_PRICE_USD=5.00   # макс. цена instant-buy
MAX_POSITION_RISK_PCT=5.0    # макс. % капитала на одну позицию
MAX_TOTAL_INVENTORY_VALUE=100.0  # макс. $ стоимость всего инвентаря
MAX_TOTAL_INVENTORY_ITEMS=30     # макс. количество предметов

# Опционально
FLOAT_PREMIUM_ENABLED=false  # наценка за float (off — DMarket цены уже включают)
```

### Запуск

```bash
# Основной пайплайн
python -m src

# Только Telegram control bot (без торговли)
python -m src.telegram.control_bot
```

---

## 📊 Текущее состояние

| Свойство | Статус |
|---|---|
| **Версия** | v13.0 |
| **DMarket API** | v2 batch endpoints (мигрировано с v1) |
| **CS2Cap** | Starter tier, 41 marketplace, batch prices/bids |
| **Стратегия A** (Intra-spread sniping) | ✅ Продакшн |
| **Стратегия C** (Cross-market arb) | ✅ Активен |
| **Fee model** | 4-tier dynamic (2/5/7/10%) + hot-fee cache |
| **Capital velocity** | Мгновенная перепродажа (TRADE_LOCK_HOURS=0) |
| **Risk manager** | Pre-trade checks, Kelly sizing, drawdown halts |
| **Pump detector** | >15%/1h spike → автоматический blacklist |
| **Error policy** | Fatal (stop) vs Transient (retry) классификация |
| **Watchdog** | External health check + auto-restart |
| **Security** | Vault encryption, log redaction, integrity hash |
| **Тесты** | 88 unit tests на RiskManager + PumpDetector |

---

## 🚧 Roadmap (ближайшие шаги)

- [ ] Multi-venue execution (Skinport/CSFloat sell-side)
- [ ] Buff163 price feed (CS2Cap Quant tier или партнёрский API)
- [ ] ML price forecasting (LSTM на CS2Cap Pro candles, 365 дней истории)
- [ ] Portfolio covariance matrix + Kelly-optimal sizing
- [ ] WebSocket streaming prices (CS2Cap Quant webhooks)
- [ ] Production hardening: canary deploy $100, 2 недели

---

## 📄 Документация

- `CHANGELOG.md` — полная история версий
- `MEMORY.md` — стратегический контекст, lessons learned
- `docs/` — спецификации DMarket API, Telegram Bot API
- `SOUL.md` — identity бота
- `SECURITY.md` — модель безопасности

---

## ⚠️ Дисклеймер

Это экспериментальное торговое ПО. Рынок CS2 скинов волатилен. Никакая стратегия не гарантирует прибыль. Используйте на свой страх и риск. Начинайте с DRY_RUN=true и малого капитала.

---

🦅 *DMarket Quantitative Engine | v13.0 | June 2026*
