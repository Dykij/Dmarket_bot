# 🦅 DMarket Quantitative Engine v14.4

**Algorithmic CS2 skin trading bot for DMarket marketplace + CS2Cap multi-market oracle (41 marketplaces).**

Автономная торговая система на строгих количественных алгоритмах. Стратегия: intra-market spread sniping + cross-market arbitrage + order book microstructure — с мгновенной капитализацией спреда (TRADE_LOCK_HOURS=0).

---

## 🧠 Стратегия — Как работает

### Концепция

Бот сканирует DMarket marketplace в поиске моментальных арбитражных возможностей — когда текущая цена продавца (`best_ask`) значительно ниже ближайшего bid-ордера (`best_bid`) или когда на внешнем маркетплейсе (CSFloat, Skinport, Buff163) бай-ордер выше DMarket ask. Находит — покупает мгновенно — **немедленно выставляет на продажу** по агрегированным ценам CS2Cap (41 маркетплейс) с учётом комиссий.

**Ключевое отличие:** DMarket разрешает мгновенную перепродажу предметов, купленных на marketplace. Steam Trade Protection (7 дней) блокирует только вывод в Steam, не внутриплатформенную торговлю. Бот использует это: capital velocity ~3-5 сделок/день на единицу капитала.

### v14.4 Balance-Aware Trading

Начиная с v14.4, все лимиты адаптируются динамически под баланс DMarket:

- **Dynamic Max Item Price** — чем больше баланс, тем дороже позиции бот может открывать: `max($5.00, balance × 10%)`. При $43 → $5, при $500 → $50
- **Reserve Buffer** — $10 на счёте всегда неприкосновенны (для форс-мажоров/выводов)
- **Fractional Kelly** — Half Kelly (50%) для размера позиции: снижает просадку на ~50% при сохранении 85% профита
- **Lock-Aware Inventory Cap** — не более 80% капитала в trade-lock одновременно
- **Capital Velocity Constraint** — минимум 0.5× оборота капитала в неделю; если заморожено — пауза покупок
- **Drawdown Freeze** — при просадке >15% от пика баланса — только продажи, без покупок

### Финансовые инструменты (v14.x)

Бот использует набор рыночно-микроструктурных инструментов, работающих через DMarket API (0 квоты CS2Cap):

| Инструмент | Суть | Откуда данные | API-запросов |
|---|---|---|---|
| **OBI** (Order Book Imbalance) | Давление покупателей/продавцов из `askCount`/`bidCount` | aggregated-prices | 0 |
| **OFI** (Order Flow Imbalance) | Дельта спроса между циклами (30с) | aggregated-prices | 0 |
| **A-S** (Avellaneda-Stoikov) | Reservation price с учётом инвентаря | price_db + CS2Cap cache | 0 |
| **VWAP** (Volume-Weighted Avg Price) | Сравнение best_ask со средневзвешенной ценой сделок | trade_history (накопленная) | 0* |
| **Slippage gate** (Almgren-Chriss) | Ожидаемое проскальзывание от participation rate | aggregated-prices volume | 0 |
| **CVD** (Cumulative Volume Delta) | Дивергенция объёма и цены | trade_history | 0* |
| **VPIN** (Volume-Sync'd Prob. Informed Trading) | Токсичность потока ордеров | trade_history | 0* |
| **ToD** (Time-of-Day) | Сезонность: ночью агрессивнее покупка | system clock | 0 |
| **DOM Gap** | Листинг в ценовые разрывы стакана | market/items listings | 0 |
| **Micro-Price** | Volume-adjusted fair price для листинга | CS2Cap cache | 0 |
| **Bait Detection** | Нестабильные листинги-приманки | price_db history | 0 |
| **Kelly sizing** ⭐v14.4 | Fractional Kelly позиционирование (Half Kelly) | win/loss history | 0 |
| **Drawdown freeze** ⭐v14.4 | Авто-стоп покупок при просадке >15% | balance history | 0 |

`*` Использует `get_last_sales` (DMarket API, 5 запросов/цикл), сохраняет в `trade_history`.

### Пайплайн (один цикл, ~30 секунд)

```
СТАРТ ЦИКЛА (run_cycle)
  │
  ├─ 1. DMarket aggregated-prices (batch 100 titles)
  │      └─ best_ask, best_bid, ask_count, bid_count
  │
  ├─ 2. Ранжирование: score = spread_$ × √(ask+bid_count)
  │      └─ отбор top-N (20) по volume-weighted spread
  │
  ├─ 3. Честные листинги (parallel)
  │      ├─ GET /market/items?title=X&limit=30 → cheapest listing
  │      ├─ Перебор floatPart=FN-0..MW-1 для low-float
  │      └─ Перебор phase=ruby/sapphire/emerald для Doppler
  │      └─ Сохранение ВСЕХ 30 листингов в DOM cache
  │
  ├─ 4. Параллельная оценка комиссий (bulk fee, 4 tiers)
  │      └─ 2% (≥50 vol) / 5% (≥10) / 7% (≥5) / 10% (<5)
  │
  ├─ 5. CS2Cap кэш (in-memory, 5-min TTL)
  │      └─ POST /prices/batch + POST /bids/batch (100 items each)
  │      └─ Hot path: sub-ms dict lookup
  │
  ├─ 6. === ФИЛЬТРЫ (v14.4 pipeline, _evaluate_candidate) ===
  │      │
  │      ├─ 🆕 Dynamic max price: max(floor, balance * fraction) ⭐v14.4
  │      ├─ 🆕 Drawdown freeze: balance < peak * 85% → skip buying ⭐v14.4
  │      ├─ 🆕 Capital velocity: weekly sales < 0.5x → pause ⭐v14.4
  │      ├─ 🟢 Bait Detection: >3 изменений цены за 5 мин → skip
  │      ├─ 🟢 OBI: bid_volume/ask_volume < 0.7 → skip (seller-dominated)
  │      ├─ 🟢 OFI: delta(bid-ask) < -10 → skip (falling demand)
  │      ├─ Price range: $0.50 < price < dynamic_max (v14.4)
  │      ├─ Cross-market arb: provider bid > DMarket ask × 1.025
  │      ├─ Volatility: 14d std < 60% annualized (Garman-Klass)
  │      ├─ Crash guard: price_db.is_crashing()
  │      ├─ Liquidity: min sales count, wash-trading detection
  │      ├─ 🟢 VWAP: best_ask < VWAP(30d) × 0.90 → buy signal
  │      │         best_ask > VWAP → skip (overpriced)
  │      ├─ 🟢 VPIN: toxic flow > 0.8 → skip
  │      ├─ Spread gate: spread ≥ fee × 2 + 3%
  │      ├─ 🟢 Slippage gate: expected slippage > 50% edge → skip
  │      ├─ Profit: validate_arbitrage_profit (fee + withdrawal)
  │      ├─ 🆕 Kelly sizing: position = Half Kelly × capital ⭐v14.4
  │      ├─ 🆕 Lock-aware cap: ≤80% capital in trade-lock ⭐v14.4
  │      ├─ Saturation: ≤3 same item, ≤dynamic_max items, ≤$100 total
  │      └─ Rare flags: stickers >$2, Ruby/Sapphire, FN-0 → exclusive
  │
  ├─ 7. Slippage protection (parallel re-verify prices)
  │
  ├─ 8. Execute instant-buys → POST /exchange/v1/market/buy
  │
  ├─ 9. Auto-resale (immediate, each cycle)
  │      ├─ 🟢 A-S: reservation_price с inventory skew
  │      ├─ 🟢 Micro-Price: volume-adjusted fair price
  │      ├─ 🟢 DOM Gap: вставка в ценовые разрывы
  │      └─ Batch listing: POST /v2/offers:batchCreate
  │
  ├─10. Reprice stale listings (every 200 cycles, drop 5%)
  │
  └─11. 🟢 Cleanup trade_history >90 days (every 200 cycles)
```

---

## 🔬 Финансовые инструменты — детально

### OBI (Order Book Imbalance)

**Формула:** `OBI = (best_bid × bidCount) / (best_ask × askCount)`

Число больше 1.0 = доминируют покупатели (цена вероятно пойдёт вверх). Меньше 0.7 = доминируют продавцы — пропускаем позицию. Это **leading indicator** — предсказывает направление цены до того, как оно отразится в спреде.

### OFI (Order Flow Imbalance)

**Формула:** `OFI = (curr_bid_cnt - prev_bid_cnt) - (curr_ask_cnt - prev_ask_cnt)`

Дельта между циклами. Положительное число = растущий спрос. Отрицательное = растущее предложение. Отсекает позиции, где спред выглядит привлекательно, но спрос падает.

### A-S (Avellaneda-Stoikov) Reservation Price

**Формула:** `r = mid_price - (inv/target) × gamma × σ² × T/365`

Классическая модель inventory-aware market making. Если у бота много одинаковых предметов — цена листинга смещается вниз (продать быстрее). Если нет — стоит чуть выше рынка (лучшая маржа).

### VWAP (Volume-Weighted Average Price)

**Формула:** `VWAP = Σ(price_i × amount_i) / Σ(amount_i)`

Сравнивает текущую best_ask с накопленной средневзвешенной ценой сделок за 30 дней. Если best_ask < VWAP × 0.90 — предмет реально undervalued. Если best_ask > VWAP — цена завышена, пропускаем.

### Slippage Gate (Almgren-Chriss)

**Формула:** `slippage = α_temp × participation + α_perm × (qty / daily_vol)`

Моделирует, насколько наша покупка сдвинет цену. В тонких стаканах DMarket одна сделка может сдвинуть best_ask на 5-10%. Если slippage > 50% от ожидаемого профита — сделку не выполняем.

### Kelly Position Sizing ⭐v14.4

**Формула:** `f* = win_rate - (1 - win_rate) / win_loss_ratio`

Half Kelly (KELLY_FRACTION=0.50): режет просадку на ~50%, сохраняя 85% growth rate. Размер позиции = capital × f* × 0.5. При отсутствии истории — использует MAX_POSITION_RISK_PCT как fallback.

### Drawdown Freeze ⭐v14.4

**Формула:** `current_balance < peak_balance × (1 - DRAWDOWN_FREEZE_THRESHOLD)`

При просадке >15% от пика — бот перестаёт покупать (только продажи). Возобновляется автоматически при восстановлении баланса выше порога.

### CVD (Cumulative Volume Delta)

Кумулятивная разница buy-initiated и sell-initiated сделок. Дивергенция CVD и цены:
- Цена растёт, CVD падает → рост не подкреплён объёмом → не покупаем
- Цена падает, CVD растёт → накопление → возможный разворот → покупаем

### VPIN (Volume-Synchronized Probability of Informed Trading)

Измеряет «токсичность» потока ордеров. Высокий VPIN (>0.8) → высокая вероятность, что в рынке инсайдер → приостанавливаем агрессивные покупки. Основан на работе Easley, López de Prado & O'Hara (2012).

### ToD (Time-of-Day Seasonality)

Ночь (04:00-10:00 UTC, ~00:00-06:00 EST): низкий спрос, продавцы демпингуют → порог спреда снижается на 15% (агрессивнее покупаем). День: нормальный режим.

---

## 🏗 Архитектура

### Стек

| Компонент | Технология | Назначение |
|---|---|---|
| **Runtime** | Python 3.13+ (asyncio) | Основной движок |
| **Rust core** | PyO3 / ed25519-dalek / Serde | Ed25519 подпись + JSON парсинг (5-10x быстрее Python) |
| **Database** | SQLite 3 (WAL mode, dual DB) | OLTP: состояние сделок. OLAP: история цен + trade_history |
| **Market data** | DMarket API v2 + CS2Cap REST | Цены, ордера, листинги, комиссии |
| **Rate limiting** | Adaptive throttle + circuit breaker | API quota management |
| **Security** | Vault (Fernet) + log redaction + chmod hardening | API ключи, integrity check |
| **Interface** | Aiogram 3.x (Telegram) | Управление, мониторинг, нотификации |
| **Health** | HTTP /healthz, /readyz, /metrics | Мониторинг состояния |
| **Deployment** | Docker multi-stage (x86_64 + ARM64) | Production-ready контейнеризация |

### Структура модулей

```
src/
├── api/                           # Внешние API
│   ├── dmarket_api_client/        # DMarket REST v2 (batch endpoints)
│   │   ├── core.py                # HTTP transport, Ed25519 подпись, circuit breaker
│   │   ├── market.py              # aggregated-prices, listings, last-sales, low-fee
│   │   ├── offers.py              # batchCreate/Update/Delete v2
│   │   ├── targets.py             # batch-create/delete buy targets
│   │   ├── fees.py                # Volume-based dynamic fee (4 tiers)
│   │   └── account.py             # Balance, inventory, transactions
│   ├── cs2cap_oracle/             # CS2Cap REST subpackage (v14.4 split)
│   │   ├── models.py              # Pydantic models
│   │   ├── client.py              # HTTP client + rate limiting
│   │   ├── catalog.py             # Item catalog cache
│   │   ├── prices.py              # /prices/batch, /bids/batch
│   │   └── utils.py               # Helpers
│   ├── cs2cap_cache.py            # In-memory cache (5-min TTL, 200 items)
│   └── oracle_factory.py          # Router: CS2Cap → CSFloat fallback
│
├── core/target_sniping/           # Основной торговый пайплайн (v14.4 split)
│   ├── core.py                    # SnipingLoop orchestrator (562 lines)
│   ├── scanner.py                 # _ScannerMixin: listings + DOM
│   ├── scheduler.py               # _SchedulerMixin: quota-aware delay
│   ├── telemetry.py               # _TelemetryMixin: Prometheus metrics
│   ├── filter.py                  # _evaluate_candidate: 15+ фильтров
│   ├── ranking.py                 # spread-based candidate ranking
│   ├── validations.py             # 10 validation functions (profit/slippage/vol)
│   ├── execution.py               # Instant-buy + slippage protection
│   ├── resale.py                  # _ResaleMixin base
│   ├── resale_dry.py              # _ResaleDryMixin (DRY_RUN mode)
│   ├── resale_prod.py             # _ResaleProdMixin (production mode)
│   ├── pricing.py                 # Float/pattern premium, low-fee cache
│   ├── sandbox.py                 # Sandbox simulation
│   └── inventory.py               # Trade status sync (trade_protected/reverted)
│
├── analysis/microstructure/       # Микроструктурный анализ (v14.4 split)
│   ├── obi.py                     # Order Book Imbalance
│   ├── volume.py                  # CVD, Volume Profile, VWAP
│   ├── volatility.py              # Garman-Klass, Parkinson, Roll's Model
│   └── signals.py                 # OFI, VPIN, ToD, A-S, Slippage
│
├── db/price_history/              # SQLite слой (dual DB)
│   ├── core.py                    # Schema, migrations, chmod hardening
│   ├── history.py                 # price_history + trade_history
│   ├── inventory.py               # virtual_inventory, decision_logs, snapshots
│   ├── state.py                   # Сканирование state (cursor, counters)
│   ├── targets.py                 # active_targets
│   ├── asset_status.py            # trade_protected / reverted tracking
│   ├── low_fee.py                 # low-fee cache (daily refresh)
│   └── pump_blacklist.py          # FOMO blacklist (persistent)
│
├── risk/                          # Управление рисками
│   ├── risk_manager.py            # Pre-trade checks, Kelly sizing, drawdown freeze ⭐v14.4
│   ├── pump_detector.py           # >15%/1h spike → 24h blacklist
│   ├── price_validator.py         # Profit/loss, volatility, slippage
│   ├── fatal_errors.py            # Fatal vs transient классификация
│   └── security_auditor.py        # Log redaction, integrity checks
│
├── strategies/                    # Multi-strategy engine
│   ├── base.py                    # Base: volatility, position sizing, Sharpe
│   ├── cross_market.py            # Cross-market arb via CS2Cap
│   └── market_maker.py            # Spread-based market making
│
├── telegram/control_bot/          # Telegram Admin Panel
│   ├── bot.py                     # Router + ThrottlingMiddleware
│   ├── filters.py                 # Admin ID gate
│   ├── keyboards.py               # 16-button inline keyboard
│   ├── formatters.py              # Markdown escaping, safe formatting
│   ├── resilience.py              # fetch_balance_data() consolidated
│   ├── callbacks.py               # All button callbacks
│   └── commands/                  # /start, /status, /balance, /panic, etc.
│
├── analytics/                     # Самоанализ и бэктестинг
│   ├── self_reflection.py         # Параметрическая автонастройка
│   ├── stickers_evaluator.py      # Katowice 2014, Crown Foil и др.
│   └── telemetry.py              # Prometheus /metrics (127.0.0.1:9190)
│
├── utils/                         # Системные утилиты
│   ├── vault.py                   # Fernet-шифрование ключей
│   ├── vault_client.py            # HashiCorp Vault client
│   ├── health_server.py           # /healthz, /readyz (127.0.0.1:9091)
│   └── clock_sync.py              # NTP синхронизация для Ed25519 подписи
│
└── config.py                      # Single source of truth — все параметры
```

### Модель данных (SQLite)

```sql
-- Виртуальный инвентарь (OLTP — state.db)
virtual_inventory (
    id, hash_name, buy_price, sell_price, fee_paid, profit,
    status,        -- idle | listed | selling | sold | failed
    exclusive,     -- 1 = keep-forever (rare float/stickers/phase)
    funds_hold_until, rollback_refund,
    acquired_at, unlock_at, sold_at,
    dm_item_id, dm_offer_id, listed_at, list_error
)

-- История цен (OLAP — history.db)
price_history (
    hash_name, price, source, recorded_at
) -- Снапшоты цен каждые 5 мин от CS2Cap

-- История сделок для CVD/VPIN/VWAP (OLAP — history.db)
trade_history (
    hash_name, price, trade_date, recorded_at
) -- Накопление из get_last_sales каждые 30с
-- UNIQUE(hash_name, price, trade_date) — дедупликация
-- Хранится 90 дней, автоматическая очистка

-- Статусы активов
asset_status (item_id, title, status, finalization_time)
-- status: active | trade_protected | reverted

-- Кэш низких комиссий
low_fee_cache (title, fee_rate, fetched_at)

-- Pump blacklist (24h FOMO protection)
pump_blacklist (hash_name, old_price, new_price, pct_change,
               detected_at, expires_at)
```

### Модель комиссий (2026)

| Game / Liquidity | Ставка | Как определяется |
|---|---|---|
| CS2 Sell (liquid, ≥50 vol) | 2% | volume tier |
| CS2 Sell (medium, 10-49 vol) | ~5% | volume tier |
| CS2 Sell (low, 5-9 vol) | ~7% | volume tier |
| CS2 Sell (illiquid, <5 vol) | ~10% | volume tier |
| CS2 Sell (hot-fee items) | 2-3% | `/customized-fees` API |
| Withdrawal (net PnL) | ~2% | константа |
| Trade fee (targets) | 2.5% | не используется (instant-buy) |

---

## 🛡 Безопасность

### Ключи и секреты

- **Vault** — Fernet-шифрование секретных ключей в памяти (`ENCRYPTION_KEY` в `.env`)
- **Config.SECRET_KEY** — удалён из module-level переменной, идёт через vault
- **Log redaction** — SecurityAuditor фильтр вырезает ключи из логов
- **In-code hardening** — `os.chmod(0o600)` на БД при создании
- **Блокировка legacy** — `bot.py` не импортируется (RuntimeError guard)
- **Docker security** — non-root пользователь, tini init, memory limits

### Файловая система

| Ресурс | Права | Механизм |
|---|---|---|
| `.env` | 600 | .gitignore + chmod |
| `data/*.db` | 600 | in-code chmod на init |
| `logs/*.log` | 600 | chmod после создания |
| `requirements.txt` | pinned | 187 пакетов с версиями |

### Сеть

| Сервис | Порт | Интерфейс | Аутентификация |
|---|---|---|---|
| Health server | 9091 | 127.0.0.1 | Basic auth (опционально) |
| Telemetry | 9190 | 127.0.0.1 | Нет (localhost-only) |
| Telegram | outbound | api.telegram.org | Bot token |
| DMarket API | outbound | api.dmarket.com | Ed25519 + IP whitelist (рекомендовано) |

---

## 🐳 Docker (рекомендованный способ деплоя)

### Быстрый старт с Docker

```bash
# 1. Клонировать репо
git clone https://github.com/Dykij/Dmarket_bot.git
cd Dmarket_bot

# 2. Создать .env из примера
cp .env.example .env
# Заполнить ключи в .env:
#   DMARKET_PUBLIC_KEY=...
#   DMARKET_SECRET_KEY=...
#   CS2CAP_API_KEY=...
#   TELEGRAM_BOT_TOKEN=...
#   ENCRYPTION_KEY=...

# 3. Запустить бота
docker compose up -d

# 4. Смотреть логи
docker compose logs -f

# 5. Опционально: запустить Telegram admin bot
docker compose --profile telegram up -d
```

### Требования к хосту

| Параметр | Минимум | Рекомендация |
|---|---|---|
| **CPU** | 1 ядро (любая архитектура) | 2+ ядра |
| **RAM** | 512 MB | 1+ GB |
| **Диск** | 2 GB свободно | 10+ GB (для логов и БД) |
| **ОС** | Linux с Docker 20.10+ | Debian 12, Ubuntu 22.04, Raspberry Pi OS |
| **Архитектура** | x86_64 или aarch64/ARM64 | Поддерживаются обе |

### Что внутри Docker

Multi-stage Dockerfile (две стадии):

1. **Builder** — устанавливает Rust, компилирует `dmarket_parser_rs`, ставит Python-зависимости
2. **Runtime** — минимальный образ (~250 MB) с только необходимым:
   - Python 3.13 с откомпилированным Rust `.so`
   - `tini` для корректной обработки сигналов
   - Non-root пользователь `bot`
   - Health check через `/healthz`
   - Memory limit: 512 MB

### Docker Compose сервисы

```yaml
# Основной бот (торговый цикл)
dmarket_bot:
  profiles: [default]
  command: python -m src
  volumes: ./data → /app/data (SQLite persistence)
           ./logs → /app/logs (log persistence)
  memory: 512M limit / 128M reservation

# Telegram админ-панель (опционально)
telegram_bot:
  profiles: [telegram]
  command: python -m src.telegram.control_bot
  memory: 256M limit / 64M reservation
```

### Совместимость с Raspberry Pi / Мини-ПК

Dockerfile протестирован на:
- **x86_64** — Steam Deck, Intel Celeron, старые ноутбуки, серверы
- **aarch64/ARM64** — Raspberry Pi 4, Pi 5, Pi 400, Apple Silicon
- Rust крейты (`ed25519-dalek`, `pyo3`) компилируются на обеих архитектурах
- Python-зависимости — все имеют ARM64 wheels (через piwheels)
- m.2 / SD карта — Docker volume маунты защищают от износа (WAL-mode SQLite)

---

## 🔧 Быстрый старт (без Docker)

### Требования

- Python 3.13+ (или 3.11+ с небольшими изменениями)
- Rust toolchain (только для `maturin` — опционально, есть Python-fallback)
- DMarket аккаунт + API ключи
- CS2Cap аккаунт (Starter: $19/mo, Pro: $79/mo)

### Установка

```bash
git clone https://github.com/Dykij/Dmarket_bot.git
cd Dmarket_bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd src/rust_core && maturin develop --release && cd ../..
```

### Конфигурация (`.env`)

```env
# ===== КЛЮЧИ =====
DMARKET_PUBLIC_KEY=your_public_key
DMARKET_SECRET_KEY=your_secret_key
CS2CAP_API_KEY=your_cs2cap_key
TELEGRAM_BOT_TOKEN=your_bot_token
ENCRYPTION_KEY=your_fernet_key

# ===== РЕЖИМ =====
DRY_RUN=true                     # false для реальной торговли
MARKETPLACE_INSTANT_RESALE=true  # мгновенная перепродажа
TRADE_LOCK_HOURS=0               # 0 = нет блокировки (DMarket marketplace)

# ===== v14.4 DYNAMIC BALANCE-AWARE =====
MAX_SNIPING_PRICE_FLOOR=5.00     # мин. цена при малом балансе
MAX_SNIPING_PRICE_BALANCE_FRACTION=0.10  # % баланса → макс. цена
BALANCE_RESERVE_USD=10.00        # неприкосновенный резерв

# ===== v14.4 KELLY POSITION SIZING =====
KELLY_ENABLED=true
KELLY_FRACTION=0.50              # 0.50 = Half Kelly
KELLY_FLOOR_PCT=3.0              # мин. % капитала на позицию

# ===== v14.4 LOCK-AWARE INVENTORY =====
LOCK_AWARE_CAP_ENABLED=true
LOCK_AWARE_LIQUID_FRACTION=0.80  # макс. % капитала в trade-lock

# ===== v14.4 CAPITAL VELOCITY =====
CAPITAL_VELOCITY_ENABLED=true
CAPITAL_VELOCITY_MIN=0.50        # мин. оборотов/неделю

# ===== v14.4 DRAWDOWN FREEZE =====
DRAWDOWN_FREEZE_ENABLED=true
DRAWDOWN_FREEZE_THRESHOLD=0.15   # 15% просадка = стоп покупок

# ===== КАПИТАЛ И РИСКИ =====
MAX_SNIPING_PRICE_USD=5.00       # макс. instant-buy (оверрайд)
MAX_POSITION_RISK_PCT=5.0        # макс. % капитала на позицию
MAX_TOTAL_INVENTORY_VALUE=100.0  # макс. $ в инвентаре
MAX_TOTAL_INVENTORY_ITEMS=30     # макс. количество предметов

# ===== МИКРОСТРУКТУРА =====
OBI_ENABLED=true                 # Order Book Imbalance
VWAP_FILTER_ENABLED=true         # VWAP undervaluation check
AS_ENABLED=true                  # Avellaneda-Stoikov reservation price
CVD_ENABLED=true                 # Cumulative Volume Delta
VPIN_ENABLED=true                # VPIN flow toxicity
TOD_ENABLED=true                 # Time-of-day seasonality

# ===== CS2CAP =====
CS2CAP_TIER=starter              # free | starter | pro | quant
CS2CAP_TOP_K_VALIDATE=5          # top-K items validated per cycle
CS2CAP_CACHE_TTL_SECONDS=300     # 5 min in-memory cache TTL

# ===== HEALTH SERVER =====
HEALTH_PORT=9091                 # HTTP /healthz для Docker healthcheck
```

### Запуск

```bash
# Полный пайплайн (торговля + Telegram)
python -m src

# Только Telegram control bot (без торговли)
python -m src.telegram.control_bot

# Тестовая песочница с v14.4 balance-aware отчётом
python tests/sandbox_full_cycle.py
```

---

## 📊 Текущее состояние

| Свойство | Статус |
|---|---|
| **Версия** | v14.4 |
| **DMarket API** | v2 batch endpoints (полная миграция) |
| **CS2Cap** | Starter tier, 41 marketplace, batch prices/bids |
| **Rust module** | Ed25519 signing + aggregated-prices parser (x86_64 + ARM64) |
| **Стратегии** | Intra-spread sniping + Cross-market arb |
| **Микроструктура** | OBI, OFI, A-S, VWAP, Slippage, CVD, VPIN, ToD, DOM, Micro-Price, Bait |
| **Balance-aware** ⭐ | Dynamic max price, Kelly sizing, lock-aware cap, capital velocity, drawdown freeze |
| **Fee model** | 4-tier dynamic (2/5/7/10%) + hot-fee cache |
| **Capital velocity** | Мгновенная перепродажа + A-S inventory skew |
| **Risk manager** | Pre-trade checks, Half Kelly sizing, drawdown halts, VPIN |
| **Pump detector** | >15%/1h spike → 24h blacklist (SQLite-persistent) |
| **Telegram panel** | 16-button admin keyboard, all tested and fixed |
| **Safety** | DRY_RUN=true, circuit breaker, slippage protection |
| **Security** | Fernet vault, log redaction, chmod hardening, legacy locked |
| **Telemetry** | Prometheus /metrics (127.0.0.1:9190) |
| **Docker** ⭐ | Multi-stage build (x86_64 + ARM64), docker compose, health check |
| **Тесты** | 289 tests (unit + bottleneck + sandbox) |
| **Database** | Dual SQLite (OLTP + OLAP) with WAL, 90d trade history |

---

## 🚧 Roadmap

- [x] **Half Kelly sizing** — fractional Kelly position sizing (v14.4)
- [x] **Balance-aware limits** — dynamic max price + reserve buffer (v14.4)
- [x] **Docker deployment** — multi-stage build, ARM64 support (v14.4)
- [ ] **Sticker Value DB** — парсинг CSFloat для оценки наклеек (Katowice, Crown, Howl)
- [ ] **Multi-venue sell-side** — Skinport/CSFloat как доп. площадки для ресейла
- [ ] **RL execution** — обучение PPO-агента в симуляторе ABIDES
- [ ] **TWAP/MPC** — дробление крупных позиций по времени
- [ ] **Cross-skin OFI** — корреляционные лид-лаг сигналы между скинами
- [ ] **Production canary** — $100, 2 недели

---

## 📚 Академическая база

| Источник | Применение в боте |
|---|---|
| **Kelly** (1956) — A New Interpretation of Information Rate | Fractional Kelly position sizing (v14.4) |
| **Avellaneda & Stoikov** (2008) — Market Making via Inventory Control | A-S reservation price (resale.py) |
| **Almgren & Chriss** (2000) — Optimal Execution of Portfolio Transactions | Slippage gate (microstructure) |
| **Easley, López de Prado, O'Hara** (2012) — VPIN / Flow Toxicity | VPIN filter (microstructure) |
| **Cont, Cucuringu, Zhang** (2021) — Cross-Impact of Order Flow Imbalance | OFI aggregator (filter.py) |
| **Frontiers in AI** (Guede-Fernández, 2025) — LSTM for CS2 skin trading | Mil-Spec focus, diversification |
| **Finance Research Letters** (Reichenbach, 2025) — 66.9% historical returns | Fee model, volatility gate |
| **arXiv:2210.07970** — Market Interventions in Virtual Economies | Event shield, supply shock detection |

---

## 📄 Документация

- `CHANGELOG.md` — полная история версий
- `MEMORY.md` — стратегический контекст, решения, уроки
- `docs/` — спецификации DMarket API, Telegram Bot API
- `SOUL.md` — identity и философия бота
- `AGENTS.md` — инструкции для AI-агентов
- `.opencode/skills/` — 10 OpenCode skills для разработки

---

## ⚠️ Дисклеймер

Экспериментальное торговое ПО. Рынок CS2 скинов волатилен. Никакая стратегия не гарантирует прибыль. Используйте на свой страх и риск. Начинайте с `DRY_RUN=true` и малого капитала ($20-50).

```
🦅 DMarket Quantitative Engine | v14.4 | June 2026
```
