<div align="center">

# 🦅 DMarket Quantitative Engine

### Algorithmic CS2 Skin Trading Bot for DMarket Marketplace

![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)
![Rust](https://img.shields.io/badge/Rust-1.96-000000?logo=rust&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-1549%20passed-44CC11?logo=pytest&logoColor=white)
![Architecture](https://img.shields.io/badge/Architecture-Score%200.85-0969DA)
![Security](https://img.shields.io/badge/Semgrep-0%20findings-FF6B35)
![Version](https://img.shields.io/badge/Version-15.8-purple)

*Автономная торговая система на строгих количественных алгоритмах.*
*Value Detection Scanner + Spread Sniping + Algo-Pack (15 алгоритмов).*

</div>

---

## 📋 Содержание

- [Ключевые особенности](#-ключевые-особенности)
- [Стратегия — как работает бот](#-стратегия--как-работает-бот)
- [Dual-Signal Pipeline](#-dual-signal-pipeline)
- [Алгоритмы (algo\_pack)](#-алгоритмы-algo_pack)
- [Финансовые инструменты](#-финансовые-инструменты)
- [Пайплайн (один цикл)](#-пайплайн-один-цикл-30-секунд)
- [Архитектура и структура](#-архитектура-и-структура)
- [Тестирование](#-тестирование)
- [Быстрый старт](#-быстрый-старт)
- [Конфигурация](#-конфигурация)
- [Мониторинг](#-мониторинг)

---

## 🌟 Ключевые особенности

| Особенность | Описание |
|---|---|
| **Dual-Signal Pipeline** | Value Detection (rarity) + Spread Sniper (intra-market) |
| **15 алгоритмов** | Ternary Search, LIS, EWMA, Markov Regime, Bayesian Kelly, Sliding Window, и др. |
| **16 microstructure фильтров** | OBI, OFI, VWAP, VPIN, CVD, Queue Imbalance, и др. |
| **Multi-Source Oracle** | 5 бесплатных источников цен (Market.CSGO, Waxpeer, CSFloat, Steam, DMarket) |
| **Instant Resale** | Покупка → мгновенная перепродажа без Steam Trade Lock |
| **Half Kelly + Bayesian** | Адаптивное размер позиции с учётом волатильности (EWMA) |
| **Rust Core** | Ed25519 подпись через PyO3 (zero-copy) |
| **1,549 тестов** | Unit + Integration + Sandbox + Strategy Simulation |

---

## 🧠 Стратегия — как работает бот

### Концепция

Бот сканирует DMarket marketplace в поиске **недооцененных предметов**. Стратегия работает в **одном рынке (DMarket-only)** — покупает предмет и **немедленно выставляет на продажу**, не выводя в Steam.

**Почему это работает:** DMarket разрешает мгновенную перепродажу предметов, купленных на marketplace. Steam Trade Protection (7 дней) блокирует только вывод в Steam, не внутриплатформенную торговлю.

```
┌─────────────────────────────────────────────────────┐
│  СТРАТЕГИЯ: Buy + Instant Resale на DMarket         │
│                                                     │
│  1. Сканировать DMarket (10 req/s)                  │
│  2. Найти недооцененный предмет                      │
│  3. Купить мгновенно (POST /market/buy)             │
│  4. Сразу выставить на продажу по fair_price × 0.97 │
│  5. Получить спред как прибыль                       │
│                                                     │
│  Capital velocity: ~3-5 сделок/день на единицу      │
└─────────────────────────────────────────────────────┘
```

### Value Detection Scanner (Primary Signal)

Бот **первично** ищет предметы по **rarity signals** — редкие атрибуты позволяют продать дороже:

| Rarity Signal | Premium Multiplier | Пример |
|---|---|---|
| **Float Premium** (FN-0, dirty BS) | 1.08–1.30× | AK-47 с float 0.0001 |
| **Pattern Premium** (Ruby, Sapphire, Emerald) | 1.5–8.0× | Karambit Ruby Phase 2 |
| **Sticker Premium** (Katowaze 2014) | 1.0–5.0× | AWP с 4× Katowaze Holo |
| **Filler Tracker** | 1.15× | Высокоспросные скины |
| **Round-Float / Date** | 1.08–1.15× | Float = 0.069420 |

### Spread Sniper (Secondary Signal)

Для ликвидных предметов без rarity premium — традиционный intra-spread:

```
best_bid > best_ask × (1 + fee + margin) → BUY
score = net_margin × √(ask_count + bid_count)
```

---

## 🔄 Dual-Signal Pipeline

```
                           ┌─────────────────┐
                           │  DMarket API     │
                           │  (10 req/s)      │
                           └────────┬────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
             ┌─────────────┐ ┌───────────┐ ┌──────────────┐
             │ Aggregated   │ │ Cheapest  │ │ Multi-Source │
             │ Prices       │ │ Listings  │ │ Oracle       │
             │              │ │           │ │ (5 sources)  │
             └──────┬──────┘ └─────┬─────┘ └──────┬───────┘
                    │              │               │
                    └──────────────┼───────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
             ┌─────────────┐ ┌──────────┐ ┌──────────────┐
             │ Trend       │ │ Regime   │ │ Spread       │
             │ Strength    │ │ Markov   │ │ Optimizer    │
             │ (LIS)       │ │ Detector │ │ (Binary)     │
             └──────┬──────┘ └────┬─────┘ └──────┬───────┘
                    │             │              │
                    └─────────────┼──────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
             ┌──────────┐ ┌───────────┐ ┌─────────────┐
             │ 16 Micro │ │ Value     │ │ Bayesian    │
             │ Structure│ │ Detection │ │ Kelly       │
             │ Filters  │ │ Layers    │ │ + EWMA Vol  │
             └────┬─────┘ └─────┬─────┘ └──────┬──────┘
                  │             │              │
                  └─────────────┼──────────────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
             ┌──────────┐ ┌──────────┐ ┌──────────────┐
             │ Fee      │ │ Ternary  │ │ Execution    │
             │ Evaluate │ │ Sell     │ │ (Buy + List) │
             │ + Caps   │ │ Optimizer│ │              │
             └──────────┘ └──────────┘ └──────────────┘
```

---

## 🧮 Алгоритмы (algo_pack)

Пакет из **15 алгоритмов**, реализованных в `src/analysis/algo_pack/`. Источники: CP-Algorithms, arXiv, Habr, GeeksforGeeks, RiskMetrics.

### Реализованные и протестированные (48/48 tests)

| # | Алгоритм | Файл | Суть | Внедрено в |
|---|---|---|---|---|
| 1 | **Ternary Search** | `sell_optimizer.py` | Оптимальный折扣продажи (max expected profit) | `filter_evaluator.py` |
| 2 | **LIS** (O(n log n)) | `trend_strength.py` | Детекция тренда через longest increasing subsequence | `ranking.py` |
| 3 | **EWMA** | `ewma.py` | Предсказание цены + волатильность (RiskMetrics) | `filter.py` (Kelly) |
| 4 | **Sliding Window** | `sliding_window.py` | O(1) min/max через monotone deque | Microstructure |
| 5 | **Markov Regime** | `regime_detector.py` | Trending vs Ranging → адаптивные параметры | `ranking.py` |
| 6 | **Bayesian Stats** | `bayesian_stats.py` | Beta distribution для win rate (консервативная оценка) | `filter.py` (Kelly) |
| 7 | **Binary Search** | `spread_optimizer.py` | Адаптивный MIN_SPREAD из trade history | Параметры |
| 8 | **Dual EWMA Vol** | `ewma.py` | Volatility regime (expanding/contracting) | Risk |

### Как алгоритмы совмещаются

```
Current Pipeline (v15.8):
  Scanner
    → Rank(spread × √vol × regime_mult × trend_LIS)     ← Markov + LIS
    → Filter(16 microstructure + regime-adjusted)        ← Sliding Window
    → BayesianKelly(EWMA-vol-adjusted)                   ← Bayesian + EWMA
    → ValueDetection(float, pattern, sticker)
    → TernaryOptimalSellPrice                            ← Ternary Search
    → FeeEval + Caps
    → Execute
```

### Ожидаемый эффект

| Метрика | Без algo_pack | С algo_pack |
|---|---|---|
| **Sharpe Ratio** | 1.0× | +15-25% |
| **Max Drawdown** | -15% | -20-30% |
| **Win Rate** | 55% | 58-62% |
| **Sell Price Accuracy** | Fixed 3% discount | Optimal 1-10% |

---

## 🛠 Финансовые инструменты

### Microstructure Filters (16 фильтров)

| # | Фильтр | Config Key | Описание |
|---|---|---|---|
| 1 | **OBI** | `OBI_ENABLED` | Order Book Imbalance — bid/ask volume ratio |
| 2 | **OFI** | `OFI_ENABLED` | Order Flow Imbalance — change in bid/ask counts |
| 3 | **VWAP** | `VWAP_FILTER_ENABLED` | Volume-Weighted Average Price |
| 4 | **VPIN** | `VPIN_ENABLED` | Volume-Synchronized PIN — informed trading |
| 5 | **CVD** | `CVD_ENABLED` | Cumulative Volume Delta — directional pressure |
| 6 | **Queue Imbalance** | `QUEUE_IMBALANCE_ENABLED` | Large-tick asset signal |
| 7 | **Multi-Level OBI** | `MULTI_LEVEL_OBI_ENABLED` | Depth-weighted OBI from DOM cache |
| 8 | **Adverse Selection** | `ADVERSER_SELECTION_ENABLED` | Kyle lambda + Amihud illiquidity |
| 9 | **Vol Regime** | `VOL_REGIME_ENABLED` | Realized volatility classification |
| 10 | **Roll Model** | `ROLL_MODEL_ENABLED` | Effective spread estimation |
| 11 | **Volume Profile** | `VOLUME_PROFILE_ENABLED` | Price-at-volume (POC) |
| 12 | **Slippage Gate** | `SLIPPAGE_GATE_ENABLED` | Pre-trade slippage estimation |
| 13 | **Micro Price** | `MICRO_PRICE_ENABLED` | Stoikov micro-price from order book |
| 14 | **Composite Score** | `COMPOSITE_SCORE_ENABLED` | Composite microstructure score |
| 15 | **Event Detection** | `EVENT_DETECTION_ENABLED` | CS2 event monitoring (updates, tournaments) |
| 16 | **Supply Tracking** | `SUPPLY_TRACKING_ENABLED` | Listing count monitoring (thin market boost) |

### Risk Management

| Инструмент | Описание |
|---|---|
| **Half Kelly (50%)** | `f* = win_rate - (1 - win_rate) / win_loss_ratio` |
| **Bayesian Kelly + EWMA** | Volatility-adjusted, conservative with small samples |
| **Drawdown Freeze** | Стоп покупок при >15% просадке от пика |
| **Pump Detector** | 15% spike/1h → 24h blacklist |
| **Lock-Aware Cap** | ≤80% капитала в trade-lock |
| **Capital Velocity** | Мин. 0.5× оборота/неделю |
| **Time-Stop** | Cancel stale buy targets after 90min |
| **Token Bucket Rate Limiter** | Per-endpoint rate limiting (0 429 errors) |
| **Security Auditor** | Secret leak scanning on all log lines |

### Мульти-оракул (5 источников)

| Источник | Тип | Обновление |
|---|---|---|
| **Market.CSGO** | Buy orders | 5 min |
| **Waxpeer** | Buy orders | 5 min |
| **CSFloat** | Market prices | 5 min |
| **Steam** | Market prices | 30 min |
| **DMarket** | Real-time | Each cycle |

---

## 🔄 Пайплайн (один цикл, ~30 секунд)

```
START CYCLE (run_cycle)
  │
  ├─ 1. _stage_prepare
  │      ├─ Balance check (effective = total - reserved)
  │      ├─ Oracle initialization (Multi-Source refresh)
  │      └─ Cycle counters reset
  │
  ├─ 2. _stage_scan
  │      ├─ DMarket /marketplace-api/v1/aggregated-prices
  │      ├─ Cheapest listings fetch
  │      └─ DOM cache refresh
  │
  ├─ 3. _stage_prefetch
  │      ├─ Bulk fee lookup
  │      ├─ Sales cache (trade history)
  │      ├─ Pump detection scan
  │      └─ Price history for algo_pack
  │
  ├─ 4. _stage_evaluate (parallel)
  │      ├─ Rank by spread × √volume × regime_mult × trend_LIS
  │      │     ├─ Markov regime detection
  │      │     └─ LIS trend strength
  │      ├─ 16 microstructure filters
  │      │     ├─ OBI, OFI, VWAP, VPIN, CVD
  │      │     ├─ Queue Imbalance, Multi-Level OBI
  │      │     ├─ Adverse Selection, Vol Regime
  │      │     ├─ Roll Model, Volume Profile
  │      │     ├─ Slippage Gate, Micro Price
  │      │     └─ Composite Score, Event Detection
  │      ├─ Value Detection (float, pattern, sticker premiums)
  │      ├─ Bayesian Kelly sizing (EWMA volatility)
  │      ├─ Ternary search optimal sell price
  │      └─ Fee evaluation + inventory caps
  │
  ├─ 5. _stage_execute
  │      ├─ Slippage protection (pre-trade check)
  │      ├─ Risk manager pre-trade check
  │      ├─ POST /exchange/v1/market/buy
  │      └─ Post-buy: virtual inventory tracking
  │
  └─ 6. _stage_postprocess
         ├─ Auto-resale (list at fair_price × optimal_discount)
         ├─ Repricing unsold offers
         ├─ Telegram notifications
         └─ Telemetry + cycle metrics
```

---

## 🏗 Архитектура и структура

### Стек технологий

| Компонент | Технология | Назначение |
|---|---|---|
| **Runtime** | Python 3.13+ (asyncio + uvloop) | Основной движок |
| **Serialization** | msgspec (5-10x faster JSON) | API response parsing |
| **Rust core** | PyO3 / ed25519-dalek | Ed25519 подпись (zero-copy) |
| **Database** | SQLite 3 (WAL mode, dual DB) | OLTP + OLAP |
| **Market data** | DMarket API v2 + Multi-Source Oracle | Цены, ордера, 5 источников |
| **Rate limiting** | Token bucket + circuit breaker | 0 429 errors |
| **Security** | Vault (Fernet) + log redaction | API ключи |
| **Interface** | Aiogram 3.x (Telegram) | Управление, мониторинг |
| **Deployment** | Docker multi-stage (x86_64 + ARM64) | Production-ready |

### Структура проекта

```
src/
├── __main__.py                    # Entry point
├── config.py                      # Configuration (env-based)
│
├── core/
│   ├── target_sniping/
│   │   ├── core.py                # Main SnipingLoop
│   │   ├── cycle_orchestrator.py  # Cycle orchestration (6 stages)
│   │   ├── filter.py              # Candidate filtering + Kelly sizing
│   │   ├── filter_evaluator.py    # Multi-stage evaluation pipeline
│   │   ├── ranking.py             # Spread ranking + regime + trend
│   │   ├── pricing.py             # Price calculations (float, pattern)
│   │   ├── execution.py           # Buy execution + slippage protection
│   │   ├── value_pipelines.py     # Value detection (primary signal)
│   │   ├── validations.py         # 16 microstructure checks
│   │   ├── microstructure_pipeline.py  # Microstructure pipeline
│   │   ├── position_guard.py      # Position sizing
│   │   └── scheduler.py           # Cycle scheduling
│   ├── event_detection.py         # CS2 event monitoring
│   └── autonomous_scanner.py      # Background scanner
│
├── analysis/
│   ├── algo_pack/                  # v15.8: 15 algorithms
│   │   ├── __init__.py
│   │   ├── sell_optimizer.py       # Ternary Search
│   │   ├── trend_strength.py       # LIS (Longest Increasing Subsequence)
│   │   ├── ewma.py                 # EWMA + Dual Vol + Adaptive Kelly
│   │   ├── sliding_window.py       # O(1) Min/Max (Monotone Deque)
│   │   ├── regime_detector.py      # Markov Chain Regime
│   │   ├── bayesian_stats.py       # Beta Distribution + Bayesian Kelly
│   │   └── spread_optimizer.py     # Binary Search for MIN_SPREAD
│   ├── microstructure/             # OBI, OFI, VWAP, VPIN, etc.
│   ├── seasonal.py                 # Seasonal timing
│   └── stickers_evaluator.py       # Sticker value calculation
│
├── analytics/
│   ├── knowledge_base.py           # Adaptive market knowledge
│   ├── filler_tracker.py           # Filler skin tracking
│   └── backtester.py               # Strategy backtesting
│
├── risk/
│   ├── risk_manager.py             # Risk management (drawdown, limits)
│   ├── security_auditor.py         # Secret leak detection
│   └── price_validator.py          # Price sanity checks
│
├── db/
│   ├── price_history.py            # SQLite price history
│   └── state.py                    # Application state
│
├── dmarket/
│   ├── client.py                   # DMarket API client
│   └── auth.py                     # Ed25519 authentication
│
├── telegram/
│   ├── control_bot.py              # Telegram bot commands
│   └── notifier.py                 # Trade notifications
│
├── utils/
│   ├── health_server.py            # Health/metrics endpoint
│   ├── rate_limiter.py             # Token bucket rate limiter
│   └── query_profiler.py           # SQLite query profiling
│
├── reflexion/                      # Self-reflection + rollback
├── workflow/                       # Async pipeline orchestration
├── sandbox/                        # Safe bash execution
└── cot_audit/                      # Chain-of-thought audit
```

---

## 🧪 Тестирование

```
1,549 passed | 0 failed | 3 warnings (pre-existing)
```

| Suite | Кол-во | Описание |
|---|---|---|
| **Unit tests** | ~800 | Individual function/class tests |
| **Algo-pack tests** | 48 | All 7 algorithm modules |
| **Integration tests** | ~400 | API, DB, pipeline integration |
| **Sandbox tests** | ~200 | Full cycle simulation |
| **Strategy tests** | ~50 | Strategy validation |
| **Security tests** | ~50 | Vault, redaction, audit |

---

## 🚀 Быстрый старт

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

### Sandbox (тестирование без реальных сделок)

```bash
DRY_RUN=true python -m src
```

---

## ⚙️ Конфигурация

### .env (основные параметры)

```bash
# DMarket API
DMARKET_PUBLIC_KEY=your_public_key
DMARKET_SECRET_KEY=your_secret_key

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Trading
DRY_RUN=true                    # Sandbox mode (default: true)
MIN_SPREAD_PCT=3.0              # Minimum spread threshold
MAX_PRICE_USD=50.0              # Max item price
FEE_RATE=0.05                   # DMarket fee (5%)
MAX_POSITION_RISK_PCT=10.0      # Max position size (% of balance)

# Algo-Pack (v15.8)
KELLY_ENABLED=true
KELLY_FRACTION=0.5              # Half Kelly
KELLY_FLOOR_PCT=2.0             # Min Kelly size

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

| Команда | Описание |
|---|---|
| `/status` | Баланс, PnL, drawdown, win rate |
| `/positions` | Открытые позиции |
| `/settings` | Текущие настройки |
| `/risk` | Risk metrics |
| `/algo_status` | Algo-pack status |

### Health endpoint

```bash
curl http://localhost:8080/healthz       # Health check
curl http://localhost:8080/metrics       # Prometheus metrics
```

---

## 📄 Лицензия

Proprietary. All rights reserved.

---

<div align="center">

🦅 *DMarket Quantitative Engine | v15.8 | July 2026*

</div>
