# 🦅 DMarket Quantitative Engine v15.7

**Algorithmic CS2 skin trading bot for DMarket marketplace + Multi-Source Oracle (5 free external APIs).**

Автономная торговая система на строгих количественных алгоритмах. Стратегия: **Value Detection Scanner** + intra-market spread sniping + cross-market arbitrage — с мгновенной капитализацией спреда (TRADE_LOCK_HOURS=0).

**Ключевое отличие v15.7:** Msgspec serialization (5-10x faster JSON), 16 microstructure filters (OBI, OFI, VWAP, VPIN, CVD, Queue Imbalance, Multi-Level OBI, Adverse Selection, Vol Regime, Roll Model, Volume Profile, Slippage Gate, Micro Price, Composite Score, Event Detection, Supply Tracking), KnowledgeBase adaptive learning, QueryProfiler, IncidentManager, 1,501 tests passing.

---

## 🧠 Стратегия — Как работает (v15.7)

### Концепция

Бот сканирует DMarket marketplace в поиске **недооцененных предметов** — тех, у которых редкие атрибуты (float, phase, pattern, stickers) позволяют продать их дороже рыночной цены, или когда текущая цена продавца (`best_ask`) значительно ниже ближайшего bid-ордера (`best_bid`), или когда на внешнем маркетплейсе (Market.CSGO, Waxpeer, CSFloat, Steam) бай-ордер выше DMarket ask. Находит — покупает мгновенно — **немедленно выставляет на продажу** по агрегированным ценам Multi-Source Oracle (5 бесплатных источников) с учётом комиссий.

**Ключевое отличие:** DMarket разрешает мгновенную перепродажу предметов, купленных на marketplace. Steam Trade Protection (7 дней) блокирует только вывод в Steam, не внутриплатформенную торговлю. Бот использует это: capital velocity ~3-5 сделок/день на единицу капитала.

---

## 🎯 Dual-Signal Pipeline (v15.7)

### Primary Signal — Value Scanner

Бот **первично** ищет предметы по rarity signals, а не только по spread:

```
Предмет с редким float/pattern/sticker
    → Оцениваем fair_price = multi_source_price × rarity_premium
    → Если fair_price > ask × (1 + fee + min_margin)
        → BUY (даже если нет natural spread!)
```

| Rarity Signal | Premium | Триггер покупки |
|---|---|---|
| **Float Premium** (FN-0, dirty BS) | 1.08–1.30× | Да, если est_sell > cost |
| **Pattern Premium** (Ruby 5×, Sapphire 5×, Emerald 8×, Blue Gem 3×, Fire & Ice 5×) | 1.5–8.0× | Да, если est_sell > cost |
| **Sticker Premium** (value-based, capped 5×) | 1.0–5.0× | Да, если est_sell > cost |
| **Filler Tracker** | 1.15× | Да, если est_sell > cost |
| **Round-Float/Date** | 1.08–1.15× | Да, если est_sell > cost |

### Secondary Signal — Spread Sniper (fallback)

Для ликвидных предметов без rarity premium — традиционный intra-spread:
```
best_bid > best_ask × (1 + fee + margin) → BUY
```

---

## 🛠 Финансовые инструменты (v15.7)

### Microstructure Filters (16 фильтров)

| Фильтр | Config Key | По умолчанию | Описание |
|---|---|---|---|
| **OBI** | `OBI_ENABLED` | ✅ ВКЛ | Order Book Imbalance — bid/ask volume ratio |
| **OFI** | `OFI_ENABLED` | ✅ ВКЛ | Order Flow Imbalance — change in bid/ask counts |
| **VWAP** | `VWAP_FILTER_ENABLED` | ✅ ВКЛ | Volume-Weighted Average Price |
| **VPIN** | `VPIN_ENABLED` | ✅ ВКЛ | Volume-Synchronized PIN — informed trading |
| **CVD** | `CVD_ENABLED` | ✅ ВКЛ | Cumulative Volume Delta — directional pressure |
| **Queue Imbalance** | `QUEUE_IMBALANCE_ENABLED` | ✅ ВКЛ | Large-tick asset signal |
| **Multi-Level OBI** | `MULTI_LEVEL_OBI_ENABLED` | ✅ ВКЛ | Depth-weighted OBI from DOM cache |
| **Adverse Selection** | `ADVERSER_SELECTION_ENABLED` | ✅ ВКЛ | Kyle λ + Amihud illiquidity |
| **Vol Regime** | `VOL_REGIME_ENABLED` | ✅ ВКЛ | Realized volatility classification |
| **Roll Model** | `ROLL_MODEL_ENABLED` | ✅ ВКЛ | Effective spread estimation |
| **Volume Profile** | `VOLUME_PROFILE_ENABLED` | ✅ ВКЛ | Price-at-volume (POC) |
| **Slippage Gate** | `SLIPPAGE_GATE_ENABLED` | ✅ ВКЛ | Pre-trade slippage estimation |
| **Micro Price** | `MICRO_PRICE_ENABLED` | ✅ ВКЛ | Micro-price from order book |
| **Composite Score** | `COMPOSITE_SCORE_ENABLED` | ✅ ВКЛ | Composite microstructure score |
| **Event Detection** | `EVENT_DETECTION_ENABLED` | ✅ ВКЛ | CS2 event monitoring (updates, tournaments) |
| **Supply Tracking** | `SUPPLY_TRACKING_ENABLED` | ✅ ВКЛ | Listing count monitoring (thin market boost) |

### Risk Management

| Инструмент | Суть |
|---|---|
| **Half Kelly (50%)** | `f* = win_rate - (1 - win_rate) / win_loss_ratio` |
| **Hybrid Kelly+Volatility** | position = capital × kelly × (1 - vol_factor) |
| **Slippage-at-Risk** | Pre-trade liquidity risk filter |
| **Drawdown Freeze** | Стоп покупок при >15% просадке |
| **Pump Detector** | 15% spike/1h → 24h blacklist |
| **Lock-Aware Cap** | ≤80% капитала в trade-lock |
| **Capital Velocity** | Мин. 0.5× оборота/неделю |
| **Time-Stop** | Cancel stale buy targets after 90min |
| **Token Bucket Rate Limiter** | Per-endpoint rate limiting (0 429 errors) |

### New Modules (v15.7)

| Модуль | Описание | Польза |
|---|---|---|
| **KnowledgeBase** | Adaptive market knowledge | Запоминает паттерны, адаптирует пороги |
| **QueryProfiler** | SQLite query profiling | Находит медленные запросы |
| **IncidentManager** | Incident tracking & alerting | Post-mortem, Telegram alerts |
| **EventDetector** | CS2 event monitoring | Volume spikes, new items |
| **SupplyTracker** | Listing count monitoring | Thin market margin boost |

---

## 🔄 Пайплайн (один цикл, ~30 секунд)

```
СТАРТ ЦИКЛА (run_cycle)
  │
  ├─ 1. _stage_prepare: Balance, oracle init, counters
  │
  ├─ 2. _stage_scan: Aggregated prices + cheapest listings
  │      └─ DMarket /marketplace-api/v1/aggregated-prices
  │
  ├─ 3. _stage_prefetch: Bulk fees, sales cache, pump detection
  │      └─ Multi-Source Oracle refresh (5 sources)
  │
  ├─ 4. _stage_evaluate: Parallel candidate evaluation
  │      ├─ 16 microstructure filters (OBI, OFI, VWAP, VPIN, CVD, ...)
  │      ├─ Value Detection (float, pattern, sticker premiums)
  │      ├─ Spread fallback
  │      └─ Kelly position sizing
  │
  ├─ 5. _stage_execute: Instant-buy + slippage protection
  │      └─ POST /exchange/v1/market/buy
  │
  └─ 6. _stage_postprocess: Resale, repricing, telemetry
         └─ Auto-resale at fair_price × 0.97
```

---

## 🏗 Архитектура

### Стек

| Компонент | Технология | Назначение |
|---|---|---|
| **Runtime** | Python 3.13+ (asyncio + uvloop) | Основной движок |
| **Serialization** | msgspec (5-10x faster JSON) | API response parsing |
| **Rust core** | PyO3 / ed25519-dalek | Ed25519 подпись |
| **Database** | SQLite 3 (WAL mode, dual DB) | OLTP + OLAP |
| **Market data** | DMarket API v2 + Multi-Source Oracle | Цены, ордера |
| **Price sources** | Market.CSGO, Waxpeer, CSFloat, Steam, DMarket | 5 бесплатных источников |
| **Rate limiting** | Token bucket + circuit breaker | 0 429 errors |
| **Security** | Vault (Fernet) + log redaction | API ключи |
| **Interface** | Aiogram 3.x (Telegram) | Управление, мониторинг |
| **Deployment** | Docker multi-stage (x86_64 + ARM64) | Production-ready |

### OpenCode Toolchain (v15.7)

| Тип | Количество | Компоненты |
|---|---|---|
| **MCP серверы** | 16 | sequential-thinking, filesystem, fetch, git, sqlite, memory, web-search, archy, playwright, github, context7, semgrep, shellcheck, kratos-memory, in-memoria, fouradata-scraping |
| **Плагины** | 18 | vibeguard, rate-limit-retry, notificator, dynamic-context-pruning, goal-plugin, scheduler, conductor, background-agents, arise, autotitle, handoff, envsitter-guard, pty, supermemory, froggy, agent-memory, worktree, notify |
| **LSP серверы** | 5 | ruff-lsp, bash-language-server, pyright, basedpyright, taplo |
| **Skills** | 25 | api-integration, archy-check, checkpoint-manager, code-reviewer, commit-changelog, docker-deployment, exchange-rate-limiting, full-test-suite, git-gate, logging-observability, monitoring-alerting, pre-deploy-audit, python-asyncio-check, python-asyncio-pitfalls, python-asyncio-production, quant-analyst, rust-build, rust-performance, security-audit, skill-workflow-integrator, sqlite-database-expert, strategy-validate, telegram-module-dev |

### Тестирование

```
1,501 passed | 0 skipped | 3 warnings
```

---

## 📦 Быстрый старт

### Docker

```bash
git clone https://github.com/your-repo/dmarket-bot.git
cd dmarket-bot
cp .env.example .env
# Заполнить .env (DMARKET_PUBLIC_KEY, DMARKET_SECRET_KEY, etc.)
docker compose up -d
```

### Локально

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Заполнить .env
python -m src
```

### Конфигурация (.env)

```bash
# DMarket API
DMARKET_PUBLIC_KEY=your_public_key
DMARKET_SECRET_KEY=your_secret_key

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Trading
DRY_RUN=true
MIN_SPREAD_PCT=3.0
MAX_PRICE_USD=50.0
FEE_RATE=0.05

# Microstructure (all enabled by default)
STRICT_MICROSTRUCTURE_FILTERS=true
OBI_ENABLED=true
OFI_ENABLED=true
VWAP_FILTER_ENABLED=true
VPIN_ENABLED=true
CVD_ENABLED=true
```

---

## 📊 Мониторинг

### Telegram команды

- `/status` — баланс, PnL, drawdown, win rate
- `/positions` — открытые позиции
- `/settings` — текущие настройки
- `/risk` — risk metrics

### Health endpoint

```bash
curl http://localhost:8080/healthz
curl http://localhost:8080/metrics  # Prometheus format
```

---

## 📄 Лицензия

Proprietary. All rights reserved.

---

🦅 *DMarket Quantitative Engine | v15.7 | July 2026*
