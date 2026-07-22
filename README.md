<div align="center">

# DMarket Quantitative Engine

### Algorithmic CS2 Skin Trading Bot for DMarket Marketplace

![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)
![Rust](https://img.shields.io/badge/Rust-1.96-000000?logo=rust&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-500%2B%20passed-44CC11?logo=pytest&logoColor=white)
![Architecture](https://img.shields.io/badge/Architecture-Score%200.85-0969DA)
![Security](https://img.shields.io/badge/Semgrep-0%20findings-FF6B35)
![Version](https://img.shields.io/badge/Version-16.2-purple)

*Автономная торговая система на строгих количественных алгоритмах.*
*Value Detection Scanner + Spread Sniping + Algo-Pack (30+ алгоритмов).*

</div>

---

## Содержание

- [Ключевые особенности](#ключевые-особенности)
- [Стратегия](#стратегия)
- [Алгоритмы (algo_pack)](#алгоритмы-algo_pack)
- [Пайплайн (один цикл)](#пайплайн-один-цикл-30-секунд)
- [Финансовые инструменты](#финансовые-инструменты)
- [Архитектура и структура](#архитектура-и-структура)
- [Тестирование](#тестирование)
- [Быстрый старт](#быстрый-старт)
- [Конфигурация](#конфигурация)
- [Мониторинг](#мониторинг)
- [Code Review (v16.2)](#code-review-v162)

---

## Ключевые особенности

| Особенность | Описание |
|---|---|
| **Dual-Signal Pipeline** | Value Detection (rarity) + Spread Sniper (intra-market) |
| **30+ алгоритмов** | GARCH, HMM, OU, Hawkes, Bollinger, DEMA, MACD, Hurst, VPIN, Thompson Sampling, Almgren-Chriss |
| **21 microstructure фильтров** | OBI, OFI, VWAP, VPIN, CVD, Queue Imbalance, Hawkes, Bollinger, DEMA, MACD, Hurst |
| **Multi-Source Oracle** | 5 источников цен (Market.CSGO, Waxpeer, CSFloat, Steam, DMarket) + Data Freshness Guard |
| **Instant Resale** | Покупка -> мгновенная перепродажа без Steam Trade Lock |
| **Bayesian Kelly + GARCH** | Адаптивный размер позиции с учётом волатильности и regime |
| **HMM 4-State Regime** | CRISIS/BEAR/RECOVERY/BULL — блокирует покупки при CRISIS |
| **Thompson Sampling** | Bayesian A/B testing для выбора стратегии (заменяет CanaryMode) |
| **Almgren-Chriss** | Optimal execution trajectory (заменяет TWAP) |
| **State Reconciliation** | Periodic сверка virtual_inventory с реальным DMarket inventory |
| **Capital Ledger** | Atomic balance reservation для параллельных стратегий |
| **Rust Core** | Ed25519 подпись через PyO3 (zero-copy) |

---

## Стратегия

### Концепция

Бот сканирует DMarket marketplace в поиске **недооцененных предметов**. Стратегия работает в **одном рынке (DMarket-only)** — покупает предмет и **немедленно выставляет на продажу**, не выводя в Steam.

**Почему это работает:** DMarket разрешает мгновенную перепродажу предметов, купленных на marketplace. Steam Trade Protection (7 дней) блокирует только вывод в Steam, не внутриплатформенную торговлю.

```
1. Сканировать DMarket (10 req/s)
2. Найти недооцененный предмет (rarity + spread signals)
3. Купить мгновенно (PATCH /exchange/v1/offers-buy)
4. Сразу выставить на продажу по fair_price x 0.97
5. Получить спред как прибыль
```

### Value Detection (Primary Signal)

| Rarity Signal | Premium | Пример |
|---|---|---|
| Float Premium (FN-0, dirty BS) | 1.08-1.30x | AK-47 с float 0.0001 |
| Pattern Premium (Ruby, Sapphire) | 1.5-8.0x | Karambit Ruby Phase 2 |
| Sticker Premium (Katowice 2014) | 1.0-5.0x | AWP с 4x Katowice Holo |
| Filler Tracker | 1.15x | Высокоспросные скины |
| Round-Float / Date | 1.08-1.15x | Float = 0.069420 |

### Spread Sniper (Secondary Signal)

```
best_bid > best_ask x (1 + fee + margin) -> BUY
score = net_margin x sqrt(ask_count + bid_count)
```

---

## Алгоритмы (algo_pack)

30+ алгоритмов в `src/analysis/algo_pack/` и `src/analysis/microstructure/`.

### Core Algorithms (v15.8)

| # | Алгоритм | Файл | Что делает |
|---|---|---|---|
| 1 | **Ternary Search** | `sell_optimizer.py` | Оптимальная скидка продажи (max expected profit) |
| 2 | **LIS** (O(n log n)) | `trend_strength.py` | Детекция тренда через longest increasing subsequence |
| 3 | **EWMA** | `ewma.py` | Предсказание цены + волатильность (RiskMetrics) |
| 4 | **Sliding Window** | `sliding_window.py` | O(1) min/max через monotone deque |
| 5 | **Markov Regime** | `regime_detector.py` | Trending vs Ranging -> адаптивные параметры |
| 6 | **Bayesian Stats** | `bayesian_stats.py` | Beta distribution для win rate + confidence-weighted Kelly |
| 7 | **Binary Search** | `spread_optimizer.py` | Адаптивный MIN_SPREAD из trade history |
| 8 | **Dual EWMA Vol** | `ewma.py` | Volatility regime (expanding/contracting) |

### Quantitative Algorithms (v15.9)

| # | Алгоритм | Файл | Что делает |
|---|---|---|---|
| 9 | **Hawkes Process** | `hawkes.py` | Детекция ажиотажа: >3x intensity -> блокирует покупку |
| 10 | **Bollinger Bands** | `microstructure/volatility.py` | Squeeze detection + %B фильтр перекупленности |
| 11 | **DEMA/TEMA/MACD** | `ewma.py` | Быстрые EMA кросоверы для моментума |
| 12 | **Hurst Exponent** | `regime_detector.py` | H>0.5 тренд, H<0.5 mean-reversion |

### Advanced Algorithms (v16.0)

| # | Алгоритм | Файл | Что делает |
|---|---|---|---|
| 13 | **GARCH(1,1)** | `garch.py` | Volatility forecasting (замена EWMA для >30 наблюдений) |
| 14 | **HMM 4-State** | `hmm_regime.py` | CRISIS/BEAR/RECOVERY/BULL regime detection |
| 15 | **Ornstein-Uhlenbeck** | `ou_process.py` | Mean-reversion Z-score entry/exit |
| 16 | **Event-Driven** | `event_driven.py` | CS2 Major calendar + seasonal patterns |
| 17 | **Pair Trading** | `pair_trading.py` | Cointegration-based arbitrage |
| 18 | **Information Theory** | `info_theory.py` | Shannon Entropy, ApEn, Mutual Information |

### New Algorithms (v16.2)

| # | Алгоритм | Файл | Что делает |
|---|---|---|---|
| 19 | **Thompson Sampling** | `thompson_sampling.py` | Bayesian A/B testing для выбора стратегии |
| 20 | **VPIN** | `vpin.py` | Volume-Synchronized PIN — toxicity of order flow |
| 21 | **Almgren-Chriss** | `strategies/almgren_chriss.py` | Optimal execution trajectory (sinh-based) |
| 22 | **Confidence-Weighted Kelly** | `bayesian_stats.py` | Kelly с учётом GARCH vol + HMM regime + entropy |
| 23 | **Entropy Regime** | `info_theory.py` | Shannon entropy regime в composite score |

### Pipeline (v16.2)

```
Scanner
  -> Rank(spread x vol x regime x trend x bollinger x hurst)
  -> Filter(21 microstructure + HMM regime-adjusted)
     <- OBI, OFI, VWAP, VPIN, CVD, Queue Imbalance
     <- Hawkes (frenzy block), Bollinger (overbought block)
     <- DEMA (bearish block), MACD (bearish block)
     <- HMM CRISIS gate (hard block all buys)
     <- OU Process (mean-reversion), Event-Driven (seasonal)
     <- Entropy Regime (trending/random/mean_reverting)
  -> BayesianKelly(GARCH-vol-adjusted, confidence-weighted)
  -> ValueDetection(float, pattern, sticker)
  -> TernaryOptimalSellPrice
  -> FeeEval + Caps + Fee-Aware Guards
  -> Execute (Almgren-Chriss for large orders)
  -> StateReconciliation (every 10 cycles)
```

### Composite Score

| Компонент | Вес | Что измеряет |
|-----------|-----|-------------|
| `spread` | 2.0 | Ширина спреда |
| `obi` | 1.5 | Давление покупателей |
| `ofi` | 1.0 | Изменение спроса |
| `cvd` | 0.5 | Накопление/распределение |
| `vpin` | 1.0 | Информированная торговля |
| `vwap` | 1.0 | Скидка к VWAP |
| `adverse` | 2.0 | Adverse selection |
| `hawkes` | 1.5 | Ажиотаж (quiet=1.0, frenzy=0.0) |
| `bollinger` | 1.0 | Squeeze + %B signal |
| `dema` | 0.8 | DEMA crossover direction |
| `macd` | 0.8 | MACD momentum |
| `hurst` | 0.5 | Regime strength |
| `entropy` | 1.0 | Predictability (trending/random/mean_reverting) |

---

## Пайплайн (один цикл, ~30 секунд)

```
START CYCLE (run_cycle)
  |
  +-- 1. _stage_prepare
  |      +-- Balance check (effective = total - reserved)
  |      +-- Oracle initialization (Multi-Source refresh)
  |      +-- Cycle counters reset
  |      +-- State Reconciliation (every 10 cycles)
  |
  +-- 2. _stage_scan
  |      +-- DMarket aggregated-prices
  |      +-- Cheapest listings fetch
  |      +-- Float/phase, price-range, low-fee secondary scans
  |
  +-- 3. _stage_prefetch
  |      +-- Bulk fee lookup
  |      +-- Sales cache (trade history)
  |      +-- Pump detection scan
  |      +-- MultiSource oracle fair prices
  |      +-- Data Freshness Guard (staleness check)
  |
  +-- 4. _stage_evaluate (parallel)
  |      +-- Rank candidates by spread
  |      +-- 21 microstructure filters
  |      +-- Value Detection (float, pattern, sticker)
  |      +-- Bayesian Kelly sizing (GARCH volatility + HMM regime)
  |      +-- Ternary search optimal sell price
  |      +-- Fee evaluation + inventory caps
  |      +-- Capital Ledger reservation
  |
  +-- 5. _stage_execute
  |      +-- Slippage protection (pre-trade check)
  |      +-- Risk manager pre-trade check (fee-aware)
  |      +-- PATCH /exchange/v1/offers-buy
  |      +-- Post-buy: virtual inventory tracking
  |      +-- Almgren-Chriss execution (for qty >= 5)
  |
  +-- 6. _stage_postprocess
         +-- Auto-resale (fee-aware margin check)
         +-- Repricing unsold offers
         +-- Telegram notifications
         +-- Telemetry + cycle metrics
         +-- State Reconciliation (periodic)
```

---

## Финансовые инструменты

### Microstructure Filters (21)

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
| 15 | **Event Detection** | `EVENT_DETECTION_ENABLED` | CS2 event monitoring |
| 16 | **Supply Tracking** | `SUPPLY_TRACKING_ENABLED` | Listing count monitoring |
| 17 | **Hawkes Process** | `HAWKES_ENABLED` | Frenzy detection (>3x intensity) |
| 18 | **Bollinger Bands** | `BOLLINGER_ENABLED` | Squeeze + %B overbought filter |
| 19 | **DEMA Crossover** | `DEMA_ENABLED` | Bearish block |
| 20 | **MACD** | `MACD_ENABLED` | Bearish block |
| 21 | **Hurst Exponent** | `HURST_ENABLED` | Regime strength (informational) |

### Risk Management

| Инструмент | Описание |
|---|---|
| **Half Kelly (50%)** | `f* = win_rate - (1 - win_rate) / win_loss_ratio` |
| **Confidence-Weighted Kelly** | Kelly с учётом GARCH vol regime + HMM state + entropy regime |
| **Fee-Aware Stop-Loss** | Включает sell fees в расчёт loss percentage |
| **Fee-Aware Take-Profit** | Включает sell fees в расчёт profit percentage |
| **Drawdown Freeze** | Стоп покупок при >15% просадке от пика |
| **Pump Detector** | 15% spike/1h -> 24h blacklist |
| **Lock-Aware Cap** | <=80% капитала в trade-lock |
| **Capital Velocity** | Мин. 0.5x оборота/неделю |
| **Time-Stop** | Cancel stale buy targets after 90min |
| **Consecutive Loss Halving** | 3+ проигрышей подряд -> размер позиции halved |
| **HMM CRISIS Gate** | Hard block всех покупок при CRISIS regime |
| **Capital Ledger** | Atomic balance reservation для параллельных стратегий |
| **State Reconciliation** | Periodic сверка virtual_inventory с реальным DMarket inventory |
| **Portfolio Concentration** | Collection + category + item-level concentration limits |
| **Lock Tracker** | Force-repricing для items >48h с убытком, opportunity cost |

### Execution

| Инструмент | Описание |
|---|---|
| **Almgren-Chriss** | Optimal execution trajectory: `x_k = X * sinh(κ(T-k)) / sinh(κT)` |
| **Slippage Protection** | Pre-trade slippage estimation + abort threshold |
| **Fee-Aware Guards** | Stop-loss/take-profit/margin с учётом комиссий |

### Multi-Source Oracle (5 источников + Freshness Guard)

| Источник | Тип | Обновление | Freshness |
|---|---|---|---|
| **Market.CSGO** | Buy orders | 5 min | ✅ Staleness check |
| **Waxpeer** | Buy orders | 5 min | ✅ Staleness check |
| **CSFloat** | Market prices | 5 min | ✅ Staleness check |
| **Steam** | Market prices | 30 min | ✅ Staleness check |
| **DMarket** | Real-time | Each cycle | ✅ Always fresh |

---

## Архитектура и структура

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
+-- __main__.py                    # Entry point
+-- config.py                      # Configuration (Pydantic env-based)
+-- inventory_manager.py           # Inventory management + pagination
|
+-- core/
|   +-- target_sniping/
|   |   +-- core.py                # Main SnipingLoop (10 mixins)
|   |   +-- cycle_orchestrator.py  # Pipeline: 6 stages
|   |   +-- filter.py              # Candidate filtering + Kelly sizing
|   |   +-- filter_evaluator.py    # Multi-stage evaluation pipeline
|   |   +-- ranking.py             # Spread ranking + regime + trend
|   |   +-- pricing.py             # Price calculations (float, pattern, fade)
|   |   +-- execution.py           # Buy execution + slippage
|   |   +-- position_guard.py      # Stop-loss/take-profit (fee-aware)
|   |   +-- resale.py              # Resale mixin (DRY/PROD routing)
|   |   +-- resale_prod.py         # Production resale + AS pricing
|   |   +-- resale_dry.py          # DRY_RUN resale simulation
|   |   +-- validations.py         # 16 microstructure checks
|   |   +-- microstructure_pipeline.py  # Microstructure pipeline
|   |   +-- value_pipelines.py     # Value detection (primary signal)
|   |   +-- scheduler.py           # Cycle scheduling + error recovery
|   |   +-- scanner.py             # Market scanner + DOM cache
|   |   +-- inventory.py           # Inventory management
|   |   +-- telemetry.py           # Equity milestone alerts
|   |   +-- sticker_cache.py       # Two-tier sticker evaluation
|   |   +-- underpriced.py         # Underpriced detection
|   +-- state_reconciliation.py    # Virtual vs real inventory sync
|   +-- capital_ledger.py          # Atomic balance reservation
|   +-- event_detection.py         # CS2 event monitoring
|   +-- supply_tracking.py         # Supply monitoring
|   +-- daily_briefing.py          # Daily P&L + risk report
|   +-- live_shadow.py             # Shadow trading engine
|   +-- sandbox.py                 # Sandbox simulation
|
+-- analysis/
|   +-- algo_pack/                  # 30+ algorithms
|   |   +-- garch.py               # GARCH(1,1) volatility
|   |   +-- hmm_regime.py          # HMM 4-state regime detection
|   |   +-- ou_process.py          # Ornstein-Uhlenbeck mean-reversion
|   |   +-- event_driven.py        # Event-driven strategy
|   |   +-- pair_trading.py        # Pair trading (cointegration)
|   |   +-- info_theory.py         # Information theory (entropy, MI)
|   |   +-- hawkes.py              # Hawkes process (frenzy detection)
|   |   +-- ewma.py                # EWMA + DEMA/TEMA/MACD
|   |   +-- bayesian_stats.py      # Bayesian Kelly + confidence-weighted
|   |   +-- regime_detector.py     # Markov regime + Hurst
|   |   +-- sell_optimizer.py      # Ternary search optimal sell
|   |   +-- spread_optimizer.py    # Binary search MIN_SPREAD
|   |   +-- trend_strength.py      # LIS trend detection
|   |   +-- sliding_window.py      # O(1) min/max deque
|   |   +-- thompson_sampling.py   # Thompson Sampling A/B testing
|   |   +-- vpin.py                # VPIN toxicity detection
|   +-- microstructure/             # OBI, OFI, VWAP, VPIN, etc.
|   +-- seasonal.py                 # Seasonal timing
|   +-- stickers_evaluator.py       # Sticker value calculation
|
+-- analytics/
|   +-- knowledge_base.py           # Adaptive market knowledge
|   +-- filler_tracker.py           # Filler skin tracking
|   +-- backtester/                 # Strategy backtesting (walk-forward)
|   +-- self_reflection.py          # Self-reflection engine
|
+-- risk/
|   +-- risk_manager.py             # Risk management (drawdown, limits, Kelly)
|   +-- dynamic_manager.py          # Dynamic risk adjustments
|   +-- price_validator.py          # Price validation
|   +-- concentration_risk.py       # Portfolio concentration risk
|   +-- lock_tracker.py             # Advanced lock tracking + force reprice
|   +-- pump_detector.py            # Pump detection + blacklist
|   +-- security_auditor.py         # Secret leak detection
|   +-- fatal_errors.py             # Error classification (FATAL/TRANSIENT)
|   +-- error_reporter.py           # Error reporting + formatting
|   +-- incident_manager.py         # Incident tracking
|
+-- db/
|   +-- price_history/
|   |   +-- __init__.py             # DB singleton + run_in_thread
|   |   +-- core.py                 # SQLite connection management
|   |   +-- history.py              # Price history queries
|   |   +-- inventory.py            # Virtual inventory CRUD
|   |   +-- analytics_logs.py       # Analytics logging
|   |   +-- low_fee.py              # Low-fee item tracking
|   |   +-- sources.py              # Price source tracking
|   |   +-- db_retry.py             # Retry decorator for SQLite
|   +-- profit_tracker.py           # Profit tracking DB
|
+-- api/
|   +-- dmarket_api_client/         # DMarket API client
|   |   +-- core.py                 # Ed25519 signing, rate limiting
|   |   +-- account.py              # Account/balance API
|   |   +-- trading.py              # Buy/sell/target API
|   |   +-- offers.py               # Offer management
|   |   +-- backoff.py              # Circuit breaker
|   +-- multi_source_oracle.py      # 5-source price oracle + freshness guard
|   +-- oracle_factory.py           # Oracle factory
|   +-- fair_price_calculator.py    # Median-based fair price
|   +-- market_csgo_oracle.py       # Market.CSGO oracle
|   +-- waxpeer_oracle.py           # Waxpeer oracle
|   +-- csfloat_oracle.py           # CSFloat oracle
|   +-- steam_oracle.py             # Steam oracle
|   +-- candle_builder.py           # OHLCV candle builder
|   +-- dmarket_parser.py           # Response parsing
|
+-- strategies/
|   +-- base.py                     # Base strategy + ATR sizing
|   +-- almgren_chriss.py           # Almgren-Chriss optimal execution
|   +-- market_maker.py             # Market making strategy
|   +-- cross_market.py             # Cross-market arbitrage
|   +-- canary_mode.py              # Legacy A/B testing (replaced by Thompson)
|
+-- telegram/
|   +-- notifier.py                 # Trade notifications + throttling
|   +-- control_bot/                # Telegram bot commands
|
+-- utils/
|   +-- vault.py                    # Fernet encryption + Vault client
|   +-- health_server.py            # Health/metrics endpoint
|   +-- rate_limiter.py             # Token bucket rate limiter
|   +-- query_profiler.py           # SQLite query profiling
|   +-- charts.py                   # Chart generation
```

---

## Тестирование

| Suite | Статус | Описание |
|---|---|---|
| **Unit tests** | 207 passed | Individual function/class tests |
| **Risk tests** | ~30 passed | Risk manager, drawdown, Kelly |
| **Algo-pack tests** | ~100 passed | Algorithm modules |
| **Integration tests** | ~40 passed | API, DB, pipeline integration |
| **Telegram tests** | ~30 passed | Notifier, throttling, circuit breaker |
| **Microstructure tests** | ~50 passed | OBI, OFI, VWAP, VPIN filters |
| **New algo tests** | 39 passed | Thompson, VPIN, ACH, Bayesian |

---

## Быстрый старт

### Docker

```bash
git clone https://github.com/Dykij/Dmarket_bot.git
cd Dmarket_bot
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

## Конфигурация

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
MIN_SPREAD_PCT=7.0              # Minimum spread threshold (default safe)
MAX_PRICE_USD=50.0              # Max item price
FEE_RATE=0.05                   # DMarket fee (5%)
WITHDRAWAL_FEE_RATE=0.025       # DMarket withdrawal fee (2.5%)
MAX_POSITION_RISK_PCT=10.0      # Max position size (% of balance)

# Kelly
KELLY_ENABLED=true
KELLY_FRACTION=0.5              # Half Kelly
KELLY_FLOOR_PCT=2.0             # Min Kelly size

# Risk
STOP_LOSS_PCT=15.0              # Stop-loss threshold
TAKE_PROFIT_PCT=20.0            # Take-profit threshold
DRAWDOWN_FREEZE_THRESHOLD=0.15  # Freeze buys at 15% drawdown

# Algo-Pack
GARCH_ENABLED=true
HMM_ENABLED=true
OU_ENABLED=true
HAWKES_ENABLED=true
BOLLINGER_ENABLED=true

# OU Mean-Reversion
OU_ENTRY_Z_SCORE=-1.5
OU_STOP_Z_SCORE=-3.0
OU_MIN_R_SQUARED=0.3

# Pair Trading
PAIR_MIN_CORRELATION=0.5
PAIR_MIN_CINTEGRATION=0.3

# Event-Driven
EVENT_PROXIMITY_WEIGHT=0.6
SEASONAL_WEIGHT=0.4

# Microstructure (all enabled by default)
OBI_ENABLED=true
OFI_ENABLED=true
VWAP_FILTER_ENABLED=true
VPIN_ENABLED=true
CVD_ENABLED=true

# VPIN (v16.2)
VPIN_ENABLED=true
VPIN_BUCKETS=8
VPIN_THRESHOLD=0.8
```

---

## Мониторинг

### Telegram команды

| Команда | Описание |
|---|---|
| `/status` | Баланс, PnL, drawdown, win rate |
| `/positions` | Открытые позиции |
| `/settings` | Текущие настройки |
| `/risk` | Risk metrics |
| `/briefing` | Принудительный daily briefing |
| `/liquidate` | Экстренная ликвидация всех позиций |

### Health endpoint

```bash
curl http://localhost:8080/healthz       # Health check
curl http://localhost:8080/metrics       # Prometheus metrics
```

---

## Code Review (v16.2)

### Проведено: 3 итерации x 16 агентов = 48 проверок

Найдено **~180 багов**, исправлено **22 CRITICAL**.

### Новые алгоритмы (v16.2)

| # | Алгоритм | Файл | Источник | Описание |
|---|---|---|---|---|
| 1 | **Thompson Sampling** | `thompson_sampling.py` | Thompson (1933) | Bayesian A/B testing для выбора стратегии |
| 2 | **VPIN** | `vpin.py` | Easley et al. (2012) | Volume-Synchronized PIN — toxicity detection |
| 3 | **Almgren-Chriss** | `almgren_chriss.py` | Almgren & Chriss (2000) | Optimal execution trajectory |
| 4 | **Confidence-Weighted Kelly** | `bayesian_stats.py` | SSRN (2025) | Kelly с учётом GARCH + HMM + entropy |
| 5 | **Entropy Regime** | `signals.py` | Shannon (1948) | Entropy regime в composite score |
| 6 | **State Reconciliation** | `state_reconciliation.py` | ROADMAP | Virtual vs real inventory sync |
| 7 | **Capital Ledger** | `capital_ledger.py` | ROADMAP | Atomic balance reservation |
| 8 | **Data Freshness Guard** | `multi_source_oracle.py` | ROADMAP | Staleness threshold for oracle data |

### Исправления (v16.1)

| # | Файл | Баг | Исправление | Влияние |
|---|------|-----|-------------|---------|
| 1 | `cycle_orchestrator.py` | `_fetch_float_phase_listings` не существует | Переименован | Float scan работал |
| 2 | `cycle_orchestrator.py` | `action=="buy"` не matches | `buy_offer` check | Покупки работали |
| 3 | `cycle_orchestrator.py` | Ranking return discarded | Захвачен + sort | Оценка по порядку |
| 4 | `info_theory.py` | Population std (Bessel) | Sample std (n-1) | ApEn корректна |
| 5 | `info_theory.py` | Division by zero ApEn | Guard n < m+3 | Нет крашей |
| 6 | `info_theory.py` | High entropy = mean_reverting | Исправлено на random | Правильная классификация |
| 7 | `hmm_regime.py` | Transition ignores time index | Per-timestep gamma | HMM работает |
| 8 | `hmm_regime.py` | M-step single forward prob | Per-timestep weights | Means/stds корректны |
| 9 | `bayesian_stats.py` | Kelly clamp wlr>=1.0 | Убран clamp | Пауза при проигрышах |
| 10 | `position_guard.py` | Stop-loss ignores fees | Fee-aware расчёт | Корректные триггеры |
| 11 | `position_guard.py` | Take-profit ignores fees | Fee-aware расчёт | Корректные триггеры |
| 12 | `limit_orders.py` | `int()` truncation | `round()` | Нет потери центов |
| 13 | `limit_orders.py` | `os.getenv("DRY_RUN")` bypass | `Config.DRY_RUN` | Нет обхода |
| 14 | `resale_prod.py` | Margin ignores sell fee | Добавлен FEE_RATE | Нет продажи в убыток |
| 15 | `daily_briefing.py` | 3 sync DB calls | `run_in_thread` | Event loop свободен |
| 16 | `scheduler.py` | No try/except run_cycle | Try/except + retry | Бот не умирает |
| 17 | `app_notifications.py` | Shutdown no-op | Notifier alert | Оператор предупреждён |
| 18 | `core.py` | Plaintext secret fallback | RuntimeError | Безопасность |
| 19 | `execution.py` | Stale base_price | Update local var | Корректная запись |
| 20 | `execution.py` | Equity log debug | Raised to warning | Видимость ошибок |
| 21 | `config.py` | Missing OU_* fields | Добавлены | OU работает |
| 22 | `test_cycle_orchestrator.py` | action=="buy" test | Updated to buy_offer | Тест актуален |

---

## Развёртывание (Dry Run на сервере)

### Быстрый старт на CityHost NL

```bash
# 1. Заказать KVM-75 NL на cityhost.ua (тест 5 дней за 99 UAH)
# 2. Установить Ubuntu 22.04
# 3. Подключиться по SSH
# 4. Запустить установку:

curl -sSL https://raw.githubusercontent.com/YOUR_USER/Dmarket_bot-main/main/scripts/setup_server.sh | sudo bash

# 5. Настроить Telegram:
nano /opt/dmarket-bot/.env
# Вставить TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID

# 6. Запустить dry run:
systemctl start dmarket-dryrun
systemctl enable dmarket-dryrun

# 7. Проверить статус:
systemctl status dmarket-dryrun
tail -f /var/log/dmarket-bot/dry_run_14d.log
```

### Telegram уведомления

Бот отправляет отчёты каждые **1.5 часа** с информацией:

```
📊 DMarket Bot — Отчёт

⏰ Аптайм: 24.5ч
🔄 Циклов: 2940 (✅2935 ❌5)
⚡ Циклов/час: 120.0

─── 📦 Предметы ───
🔍 Просканировано: 44100
🎯 Найдено: 2940
✅ Прошло фильтры: 1470
🛒 Куплено (симуляция): 588

─── 💰 Финансы ───
💵 Баланс: $1045.20
📈 PnL: $45.20
📊 ROI: 4.52%
📉 Max Drawdown: 2.30%

─── 🖥 Сервер ───
🧠 RAM: 650 MB
❌ Ошибок: 5
```

### Управление

```bash
# Статус
systemctl status dmarket-dryrun

# Логи
tail -f /var/log/dmarket-bot/dry_run_14d.log

# Перезапуск
systemctl restart dmarket-dryrun

# Остановка
systemctl stop dmarket-dryrun

# Отчёт
cat /opt/dmarket-bot/logs/dry_run_14d_report.json
```

### Steam Deck OLED

Можно запустить на Steam Deck в Desktop Mode:

```bash
# 1. Переключиться в Desktop Mode (Start → Switch to Desktop)
# 2. Открыть Konsole (терминал)
# 3. Установить Docker (опционально) или напрямую:

git clone https://github.com/YOUR_USER/Dmarket_bot-main.git
cd Dmarket_bot-main
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Настроить .env
cp .env.example .env
nano .env  # вставить Telegram credentials

# 5. Запустить
PYTHONUNBUFFERED=1 python tests/sandbox/dry_run_14d.py

# 6. Или через tmux (чтобы работало в фоне):
tmux new -s dryrun
PYTHONUNBUFFERED=1 python tests/sandbox/dry_run_14d.py
# Ctrl+B, D —_detach
# tmux attach -t dryrun —_подключиться обратно
```

---

## Лицензия

Proprietary. All rights reserved.

---

<div align="center">

*DMarket Quantitative Engine | v16.2 | July 2026*

</div>
