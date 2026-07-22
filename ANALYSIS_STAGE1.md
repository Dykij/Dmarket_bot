# ANALYSIS_STAGE1.md — Анализ README и документации

**Дата:** 2026-07-22 | **Версия проекта:** v16.2

---

## 1. Используемые алгоритмы (30+)

### Core Algorithms (v15.8)
| # | Алгоритм | Файл | Назначение |
|---|----------|------|------------|
| 1 | Ternary Search | `sell_optimizer.py` | Оптимальная скидка продажи (max expected profit) |
| 2 | LIS (O(n log n)) | `trend_strength.py` | Детекция тренда через longest increasing subsequence |
| 3 | EWMA | `ewma.py` | Предсказание цены + волатильность (RiskMetrics) |
| 4 | Sliding Window | `sliding_window.py` | O(1) min/max через monotone deque |
| 5 | Markov Regime | `regime_detector.py` | Trending vs Ranging → адаптивные параметры |
| 6 | Bayesian Stats | `bayesian_stats.py` | Beta distribution для win rate + confidence-weighted Kelly |
| 7 | Binary Search | `spread_optimizer.py` | Адаптивный MIN_SPREAD из trade history |
| 8 | Dual EWMA Vol | `ewma.py` | Volatility regime (expanding/contracting) |

### Quantitative Algorithms (v15.9)
| # | Алгоритм | Файл | Назначение |
|---|----------|------|------------|
| 9 | Hawkes Process | `hawkes.py` | Детекция ажиотажа: >3x intensity → блокирует покупку |
| 10 | Bollinger Bands | `microstructure/volatility.py` | Squeeze detection + %B фильтр перекупленности |
| 11 | DEMA/TEMA/MACD | `ewma.py` | Быстрые EMA кросоверы для моментума |
| 12 | Hurst Exponent | `regime_detector.py` | H>0.5 тренд, H<0.5 mean-reversion |

### Advanced Algorithms (v16.0)
| # | Алгоритм | Файл | Назначение |
|---|----------|------|------------|
| 13 | GARCH(1,1) | `garch.py` | Volatility forecasting (замена EWMA для >30 наблюдений) |
| 14 | HMM 4-State | `hmm_regime.py` | CRISIS/BEAR/RECOVERY/BULL regime detection |
| 15 | Ornstein-Uhlenbeck | `ou_process.py` | Mean-reversion Z-score entry/exit |
| 16 | Event-Driven | `event_driven.py` | CS2 Major calendar + seasonal patterns |
| 17 | Pair Trading | `pair_trading.py` | Cointegration-based arbitrage |
| 18 | Information Theory | `info_theory.py` | Shannon Entropy, ApEn, Mutual Information |

### New Algorithms (v16.2)
| # | Алгоритм | Файл | Назначение |
|---|----------|------|------------|
| 19 | Thompson Sampling | `thompson_sampling.py` | Bayesian A/B testing для выбора стратегии |
| 20 | VPIN | `vpin.py` | Volume-Synchronized PIN — toxicity of order flow |
| 21 | Almgren-Chriss | `strategies/almgren_chriss.py` | Optimal execution trajectory (sinh-based) |
| 22 | Confidence-Weighted Kelly | `bayesian_stats.py` | Kelly с учётом GARCH vol + HMM regime + entropy |
| 23 | Entropy Regime | `info_theory.py` | Shannon entropy regime в composite score |

### Microstructure Filters (21)
OBI, OFI, VWAP, VPIN, CVD, Queue Imbalance, Multi-Level OBI, Adverse Selection, Vol Regime, Roll Model, Volume Profile, Slippage Gate, Micro Price, Composite Score, Event Detection, Supply Tracking, Hawkes Process, Bollinger Bands, DEMA Crossover, MACD, Hurst Exponent.

---

## 2. Финансовые инструменты и площадки

### Торговая площадка (ЕДИНСТВЕННАЯ)
- **DMarket** (https://api.dmarket.com) — единственная площадка, где совершаются реальные сделки (покупка/продажа/выставление лота)

### Оракулы цен (READ-ONLY)
| Оракул | URL | Назначение | Обновление |
|--------|-----|------------|------------|
| Market.CSGO | https://market.csgo.com/en/api | Buy orders, 26K+ items | 5 min |
| Waxpeer | https://docs.waxpeer.com/ | Buy orders, 21K+ items | 5 min |
| CSFloat | https://docs.csfloat.com/#introduction | Market prices | 5 min |
| Steam | Community Market | Median prices | 30 min |

**ВАЖНО:** Все оракулы — ИСКЛЮЧИТЕЛЬНО read-only запросы цен. Никаких операций buy/sell/list/withdraw.

---

## 3. Торговая стратегия и логика принятия решений

### Стратегия: Spread Sniping + Value Detection (DMarket-only)

**Концепция:** Бот сканирует DMarket marketplace в поисках недооценённых предметов. Покупает и **немедленно выставляет на продажу** без вывода в Steam.

### Dual-Signal Pipeline
1. **VALUE SIGNAL (primary):** rarity_mult × oracle_ask > ask × (1 + FEE_RATE + WITHDRAWAL_FEE + MIN_MARGIN)
   - Float premium (1.08-1.30×)
   - Pattern/phase premium (1.0-5.0×)
   - Sticker combo (+50-100%)
   - Filler demand (1.15×)

2. **SPREAD SIGNAL (fallback):** best_bid > best_ask × (1 + FEE_RATE + WITHDRAWAL_FEE + MIN_MARGIN)

### Пайплайн (один цикл, ~30 секунд)
```
1. _stage_prepare: Balance check, Oracle init, State Reconciliation
2. _stage_scan: DMarket aggregated-prices, cheapest listings, float/phase
3. _stage_prefetch: Bulk fee, sales cache, pump detection, MultiSource oracle
4. _stage_evaluate: Rank + 21 filters + Value Detection + Kelly + Ternary sell
5. _stage_execute: Slippage check, Risk manager, POST /exchange/v1/offers-buy
6. _stage_postprocess: Auto-resale, repricing, Telegram, telemetry
```

### Composite Score (14 components, weighted)
spread(2.0), obi(1.5), ofi(1.0), cvd(0.5), vpin(1.0), vwap(1.0), adverse(2.0), hawkes(1.5), bollinger(1.0), dema(0.8), macd(0.8), hurst(0.5), entropy(1.0)

---

## 4. Алгоритм расчёта справедливой цены (Fair Price)

### Источник: `src/api/fair_price_calculator.py` + `src/api/multi_source_oracle.py`

**Алгоритм:**
1. Собрать цены от всех доступных источников (Market.CSGO, Waxpeer, CSFloat, Steam)
2. Удалить выбросы (min и max если >2 источников; min удаляется если < 0.3× медианы остальных; max удаляется если > 2.0× медианы остальных)
3. Вычислить **медиану** оставшихся цен
4. Применить динамический маржинал на основе ликвидности:
   - ≥100 лотов → 3%
   - ≥50 лотов → 5%
   - ≥20 лотов → 7%
   - ≥5 лотов → 10%
   - <5 лотов → 15%
5. sell_price = fair_price × (1 + margin_pct / 100)
6. Минимальная маржа: не менее 3% над buy price

### Уровень доверия
- ≥3 источника → "high"
- 2 источника → "medium"
- 1 источник → "low"

### Data Freshness Guard (v16.3)
- Market.CSGO: 10 min threshold
- Waxpeer: 10 min threshold
- CSFloat: 10 min threshold
- Steam: 30 min threshold

### Circuit Breaker per source
- 5 последовательных ошибок → circuit OPEN на 60 секунд
- Half-open: одна попытка после таймаута

### Динамический TTL кэша
- Stable items (vol < 5%) → 30 min
- Normal items → 15 min
- Volatile items (vol > 20%) → 5 min

---

## 5. Risk Management

| Инструмент | Описание |
|------------|----------|
| Half Kelly (50%) | Fractional Kelly sizing |
| Confidence-Weighted Kelly | Kelly с учётом GARCH vol + HMM state + entropy |
| Fee-Aware Stop-Loss/Take-Profit | Включает sell fees в расчёт |
| Drawdown Freeze | Стоп покупок при >15% просадке от пика |
| Pump Detector | 15% spike/1h → 24h blacklist |
| Lock-Aware Cap | ≤80% капитала в trade-lock |
| Capital Velocity | Мин. 0.5x оборота/неделю |
| Time-Stop | Cancel stale buy targets after 90min |
| HMM CRISIS Gate | Hard block всех покупок при CRISIS regime |
| Capital Ledger | Atomic balance reservation |
| State Reconciliation | Periodic сверка virtual vs real inventory |

---

## 6. Ключевые наблюдения

1. **Архитектура чётко разделена:** DMarket = торговая площадка, все остальные = оракулы цен
2. **Fair price = медиана** с удалением выбросов, а не цена одной площадки
3. **30+ алгоритмов** в algo_pack — от классических (EWMA, MACD) до продвинутых (GARCH, HMM, Hawkes)
4. **21 microstructure фильтр** — многоуровневая система фильтрации
5. **Кроссплатформенная торговля НЕ предусмотрена** — только DMarket
6. **CrossMarketStrategy** (`src/strategies/cross_market.py`) — НЕ выполняет сделки на других площадках, а использует данные оракулов для оценки арбитражных возможностей на DMarket
