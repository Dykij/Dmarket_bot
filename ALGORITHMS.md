# 📚 ALGORITHMS.md — Полная документация по алгоритмам DMarket Bot

> **Версия:** v15.9 | **Дата:** 16 июля 2026  
> **Количество алгоритмов:** 20  
> **Тесты:** 48/48 algo_pack + 215/215 risk + 1549 total

---

## Содержание

1. [Обзор](#обзор)
2. [Hawkes Process (v15.9)](#1-hawkes-process-v159)
3. [Bollinger Bands (v15.9)](#2-bollinger-bands-v159)
4. [DEMA/TEMA (v15.9)](#3-dematema-v159)
5. [EMA Crossover (v15.9)](#4-ema-crossover-v159)
6. [MACD (v15.9)](#5-macd-v159)
7. [Hurst Exponent (v15.9)](#6-hurst-exponent-v159)
8. [Markov Regime Detector](#7-markov-regime-detector)
9. [EWMA (Exponentially Weighted Moving Average)](#8-ewma)
10. [Bayesian Stats](#9-bayesian-stats)
11. [Ternary Search (Sell Optimizer)](#10-ternary-search-sell-optimizer)
12. [LIS (Longest Increasing Subsequence)](#11-lis-longest-increasing-subsequence)
13. [Sliding Window (Monotone Deque)](#12-sliding-window-monotone-deque)
14. [Binary Search (Spread Optimizer)](#13-binary-search-spread-optimizer)
15. [Dual EWMA Volatility](#14-dual-ewma-volatility)
16. [Stoikov Micro-Price](#15-stoikov-micro-price)
17. [VPIN (Volume-Synchronized PIN)](#16-vpin-volume-synchronized-pin)
18. [Kyle Lambda + Amihud](#17-kyle-lambda--amihud)
19. [Roll Model](#18-roll-model)
20. [Volume Profile / POC](#19-volume-profile--poc)
21. [Composite Score](#20-composite-score)
22. [Как алгоритмы совмещаются](#как-алгоритмы-совмещаются)
23. [Источники](#источники)

---

## Обзор

DMarket бот использует **20 количественных алгоритмов** для принятия торговых решений. Каждый алгоритм решает конкретную задачу:

| Категория | Алгоритмы | Назначение |
|-----------|-----------|------------|
| **Детекция ажиотажа** | Hawkes Process | Блокировка покупок при FOMO |
| **Волатильность** | Bollinger Bands, Dual EWMA, Parkinson | Squeeze detection, regime classification |
| **Моментум** | DEMA, TEMA, EMA Crossover, MACD | Быстрые кросоверы без лага |
| **Режим рынка** | Markov HMM, Hurst Exponent | Trending vs Ranging, regime strength |
| **Позиционирование** | Bayesian Kelly, Half Kelly | Адаптивный размер позиции |
| **Оптимизация** | Ternary Search, Binary Search | Оптимальные цены продажи и спреды |
| **Microstructure** | OBI, VPIN, VWAP, Kyle, Roll | Анализ стакана и потоков |
| **Скорость** | Sliding Window (Monotone Deque) | O(1) операции |

---

## 1. Hawkes Process (v15.9)

### Что это
Самовозбуждающийся точечный процесс, моделирующий кластеризацию событий. Каждое событие (появление листинга) временно увеличивает вероятность следующего.

### Формула
```
λ(t) = μ + Σ α × e^(-β × (t - tᵢ))

Где:
  λ(t)  = интенсивность в момент t
  μ     = базовая интенсивность (фоновая скорость)
  α     = размер импульса (каждое событие возбуждает следующие)
  β     = скорость затухания (как быстро "забывается" событие)
  tᵢ    = времена предыдущих событий
```

### Где внедрён
- **Файл:** `src/analysis/algo_pack/hawkes.py`
- **Пайплайн:** `microstructure_pipeline.py` → шаг 12
- **Действие:** BLOCK buying при intensity > 3x baseline (frenzy)

### Как работает в боте
```python
# Собираем timestamps из trade records
timestamps = [tr["timestamp"] for tr in trade_records]

# Оцениваем интенсивность
hawkes = HawkesEstimator(baseline=0.01, alpha=0.5, beta=0.1)
for ts in timestamps:
    hawkes.update(ts)

# Проверяем активность
ratio = hawkes.get_intensity_ratio()  # current / baseline
activity = classify_activity_level(ratio)

if activity == "frenzy":  # ratio > 3.0
    return None  # Блокируем покупку
```

### Классификация активности
| Уровень | Ratio | Действие |
|---------|-------|----------|
| `quiet` | < 0.5 | Хорошее время для входа |
| `normal` | 0.5 - 1.5 | Стандартная активность |
| `elevated` | 1.5 - 3.0 | Осторожность |
| `frenzy` | > 3.0 | БЛОКИРОВКА покупок |

### Источник
- Cartea, Jaimungal, Penalva (2015) "Algorithmic and High-Frequency Trading"
- Easley, López de Prado, O'Hara (2012) "Flow Toxicity and Liquidity"

---

## 2. Bollinger Bands (v15.9)

### Что это
Динамический коридор волатильности вокруг скользящей средней. Используется для:
- Обнаружения squeeze (сжатие волатильности → прорыв)
- Определения перекупленности/перепроданности (%B)

### Формула
```
Upper Band = MA(N) + K × σ(N)
Lower Band = MA(N) - K × σ(N)
%B = (Price - Lower) / (Upper - Lower)
Bandwidth = (Upper - Lower) / MA(N)

Где:
  N = 20 (период)
  K = 2.0 (количество стандартных отклонений)
```

### Где внедрён
- **Файл:** `src/analysis/microstructure/volatility.py`
- **Пайплайн:** `microstructure_pipeline.py` → шаг 13
- **Ranking:** `ranking.py` → boost/penalize score
- **Действие:** BLOCK buying при %B > 1.0 (overbought)

### Как работает в боте
```python
# Проверяем squeeze
squeeze = bollinger_squeeze_signal(prices, period=20, squeeze_threshold=0.02)

# Проверяем %B
pctb = bollinger_pctb(prices, current_price, period=20)

# Блокировка при перекупленности
if pctb > 1.0 and squeeze != "squeeze":
    return None  # Overbought

# Boost при squeeze + поддержке
if squeeze == "squeeze" and pctb < 0.3:
    score *= 1.15  # +15% для squeeze near support
```

### Сигналы
| Сигнал | Условие | Действие |
|--------|---------|----------|
| `squeeze` | Bandwidth < 0.02 | Прорыв imminent |
| `expanded` | Bandwidth > 0.06 | Волатильность расширена |
| Overbought | %B > 1.0 | БЛОКИРОВКА |
| Oversold | %B < 0.0 | Boost score +10% |

### Источник
- Bollinger, J. (2002) "Bollinger on Bollinger Bands"

---

## 3. DEMA/TEMA (v15.9)

### Что это
Улучшенные EMA с уменьшенным лагом:
- **DEMA** (Double EMA): -50% lag
- **TEMA** (Triple EMA): -70% lag

### Формула
```
DEMA = 2 × EMA(N) - EMA(EMA(N))
TEMA = 3 × EMA(N) - 3 × EMA(EMA(N)) + EMA(EMA(EMA(N)))
```

### Где внедрён
- **Файл:** `src/analysis/algo_pack/ewma.py`
- **Используется в:** EMA Crossover, MACD

### Зачем
Стандартная EMA с alpha=0.3 реагирует медленно. DEMA с тем же периодом реагирует в 2x быстрее, TEMA в 3x быстрее.

---

## 4. EMA Crossover (v15.9)

### Что это
Сигнал на основе пересечения быстрой и медленной DEMA.

### Формула
```
Fast DEMA(9) vs Slow DEMA(21)

Bullish: fast был ниже slow, теперь выше
Bearish: fast был выше slow, теперь ниже
```

### Где внедрён
- **Файл:** `src/analysis/algo_pack/ewma.py`
- **Пайплайн:** `microstructure_pipeline.py` → шаг 14
- **Действие:** BLOCK buying при bearish crossover

### Как работает в боте
```python
crossover = ema_crossover(prices, fast_period=9, slow_period=21)

if crossover == "bearish":
    return None  # Блокируем покупку
```

---

## 5. MACD (v15.9)

### Что это
Moving Average Convergence/Divergence — моментум индикатор.

### Формула
```
MACD Line = EMA(12) - EMA(26)
Signal Line = EMA(MACD Line, 9)
Histogram = MACD Line - Signal Line
```

### Где внедрён
- **Файл:** `src/analysis/algo_pack/ewma.py`
- **Пайплайн:** `microstructure_pipeline.py` → шаг 15
- **Composite Score:** компонент `macd` (вес 0.8)

### Сигналы
| Сигнал | Условие | Действие |
|--------|---------|----------|
| `bullish` | Histogram > 0 и растёт | Boost score |
| `bearish` | Histogram < 0 и падает | БЛОКИРОВКА |
| `neutral` | Нет явного сигнала | Без изменений |

### Источник
- Appel, G. (1979) "The Moving Average Convergence-Divergence Trading Method"

---

## 6. Hurst Exponent (v15.9)

### Что это
Показатель персистентности временного ряда:
- H > 0.5 → тренд (последовательный)
- H = 0.5 → случайное блуждание
- H < 0.5 → возврат к среднему (антипоследовательный)

### Формула
```
H = log(R/S) / log(N)

Где:
  R = размах кумулятивных отклонений
  S = стандартное отклонение
  N = количество наблюдений
```

### Где внедрён
- **Файл:** `src/analysis/algo_pack/regime_detector.py`
- **Пайплайн:** `microstructure_pipeline.py` → шаг 16 (informational)
- **Ranking:** boost +8% при H > 0.6, +5% при H < 0.4
- **Composite Score:** компонент `hurst` (вес 0.5)

### Как работает в боте
```python
hurst = hurst_exponent(prices, max_lag=20)

if hurst > 0.6:
    # Тренд — подтверждаем momentum стратегии
    score *= 1.08
elif hurst < 0.4:
    # Mean-reversion — подтверждаем reversion стратегии
    score *= 1.05
```

### Двойная верификация
Hurst используется вместе с Markov HMM для подтверждения режима:
```python
regime, hurst, params = regime_with_hurst(detector, prices, change, vol)

# Если HMM и Hurst disagree — снижаем confidence
if regime == "trending" and hurst < 0.4:
    params.kelly_mult *= 0.7  # Conflict!
```

### Источник
- Mandelbrot, B. (1972) "Statistical Methodology for Nonperiodic Cycles"
- Lo, A.W. & MacKinlay, A.C. (1988) "Stock Market Prices Do Not Follow Random Walks"

---

## 7. Markov Regime Detector

### Что это
2-состоятельный Markov chain для определения режима рынка:
- **TRENDING:** высокая волатильность, направленное движение
- **RANGING:** низкая волатильность, возврат к среднему

### Где внедрён
- **Файл:** `src/analysis/algo_pack/regime_detector.py`
- **Ranking:** `regime_mult` для адаптивного спреда

### Параметры
```python
P_TREND_TREND = 0.85   # Тренд остаётся трендом
P_RANGE_RANGE = 0.90   # Рэндж остаётся рэнджем

# Режим-зависимые параметры
Trending: kelly_mult=1.2, take_profit_mult=1.3
Ranging:  kelly_mult=0.8, take_profit_mult=0.8
```

---

## 8. EWMA

### Что это
Экспоненциально взвешенное скользящее среднее для:
- Предсказания цены
- Оценки волатильности (RiskMetrics)
- Адаптивного Kelly

### Формула
```
EMA_t = α × x_t + (1 - α) × EMA_{t-1}

Волатильность (RiskMetrics):
σ²_t = α × r²_t + (1 - α) × σ²_{t-1}
```

### Где внедрён
- **Файл:** `src/analysis/algo_pack/ewma.py`
- **Kelly:** `adaptive_kelly_fraction()` в `filter.py`

---

## 9. Bayesian Stats

### Что это
Байесовская оценка win rate через Beta distribution. Консервативная оценка для малых выборок.

### Формула
```
Prior: Beta(2, 2) — слабо информативный
Posterior: Beta(2 + wins, 2 + losses)
Conservative: нижняя граница 80% credible interval
```

### Где внедрён
- **Файл:** `src/analysis/algo_pack/bayesian_stats.py`
- **Kelly:** `bayesian_kelly()` в `filter.py`

---

## 10. Ternary Search (Sell Optimizer)

### Что это
Поиск оптимальной скидки продажи через ternary search. Максимизирует expected profit = margin × P(fill).

### Где внедрён
- **Файл:** `src/analysis/algo_pack/sell_optimizer.py`
- **Продажа:** `find_optimal_sell_price()` в `filter_evaluator.py`

---

## 11. LIS (Longest Increasing Subsequence)

### Что это
Детекция тренда через длину наибольшей возрастающей подпоследовательности.

### Формула
```
trend_strength = LIS_length / window_length

1.0 = идеальный uptrend
0.5 = random walk
0.0 = идеальный downtrend
```

### Где внедрён
- **Файл:** `src/analysis/algo_pack/trend_strength.py`
- **Ranking:** boost +10% при ts > 0.6

---

## 12. Sliding Window (Monotone Deque)

### Что это
O(1) amortized min/max через монотонный дек. Используется для VWAP, OBI, Volume Profile.

### Где внедрён
- **Файл:** `src/analysis/algo_pack/sliding_window.py`
- **Microstructure:** все оконные операции

---

## 13. Binary Search (Spread Optimizer)

### Что это
Поиск адаптивного MIN_SPREAD через binary search. Находит минимальный спред, дающий целевой win rate.

### Где внедрён
- **Файл:** `src/analysis/algo_pack/spread_optimizer.py`
- **Параметры:** `Config.INTRA_MIN_SPREAD_PCT`

---

## 14. Dual EWMA Volatility

### Что это
Сравнение быстрой и медленной EWMA волатильности для определения regime.

### Сигналы
- Fast > Slow × 1.3 → EXPANDING (опасно)
- Fast < Slow × 0.7 → CONTRACTING (безопасно)

### Где внедрён
- **Файл:** `src/analysis/algo_pack/ewma.py`
- **Risk:** regime detection

---

## 15. Stoikov Micro-Price

### Что это
OBI-adjusted fair price — лучший предсказатель краткосрочного движения цены.

### Формула
```
P_micro = mid_price + c × spread × obi
```

### Где внедрён
- **Файл:** `src/analysis/microstructure/obi.py`

---

## 16. VPIN (Volume-Synchronized PIN)

### Что это
Вероятность информированной торговли. Высокий VPIN = кто-то знает что-то.

### Где внедрён
- **Файл:** `src/analysis/microstructure/volume.py`
- **Фильтр:** блокирует при VPIN > threshold

---

## 17. Kyle Lambda + Amihud

### Что это
- **Kyle Lambda:** чувствительность цены к объёму
- **Amihud:** илликвидность (большее движение цены на доллар объёма)

### Где внедрён
- **Файл:** `src/analysis/microstructure/volatility.py`
- **Фильтр:** adverse selection check

---

## 18. Roll Model

### Что это
Оценка эффективного спреда из ковариации цен.

### Формула
```
s = 2 × sqrt(-cov(Δp_t, Δp_{t-1}))
```

### Где внедрён
- **Файл:** `src/analysis/microstructure/volatility.py`

---

## 19. Volume Profile / POC

### Что это
Point of Control — цена с максимальным объёмом торгов. "Магнит" для цены.

### Где внедрён
- **Файл:** `src/analysis/microstructure/volatility.py`

---

## 20. Composite Score

### Что это
Взвешенная комбинация всех сигналов для ранжирования кандидатов.

### Компоненты (v15.9)
| Компонент | Вес | Что измеряет |
|-----------|-----|--------------|
| `spread` | 2.0 | Ширина спреда |
| `obi` | 1.5 | Давление покупателей |
| `ofi` | 1.0 | Изменение спроса |
| `cvd` | 0.5 | Накопление/распределение |
| `vpin` | 1.0 | Информированная торговля |
| `vwap` | 1.0 | Скидка к VWAP |
| `adverse` | 2.0 | Adverse selection |
| `vol_regime` | 0.5 | Режим волатильности |
| `kyle` | 1.0 | Price impact |
| `hawkes` | 1.5 | Ажиотаж |
| `bollinger` | 1.0 | Squeeze + %B |
| `dema` | 0.8 | Crossover direction |
| `macd` | 0.8 | Моментум |
| `hurst` | 0.5 | Regime strength |

### Где внедрён
- **Файл:** `src/analysis/microstructure/signals.py`
- **Composite Score:** `composite_buy_score()`

---

## Как алгоритмы совмещаются

```
┌─────────────────────────────────────────────────────────────────┐
│                     PIPELINE v15.9                               │
├─────────────────────────────────────────────────────────────────┤
│  Scanner → Fetch listings + order book                          │
│      │                                                           │
│      ▼                                                           │
│  Ranking (pre-filter)                                           │
│      ├─ Markov Regime → regime_mult                             │
│      ├─ LIS Trend → trend boost/penalty                         │
│      ├─ Bollinger Squeeze → breakout boost (v15.9)              │
│      └─ Hurst Exponent → regime strength boost (v15.9)          │
│      │                                                           │
│      ▼                                                           │
│  Filter (21 microstructure checks)                              │
│      ├─ Steps 1-11: Existing filters (OBI, OFI, VWAP, etc.)    │
│      ├─ Step 12: Hawkes Process → block frenzy (v15.9)          │
│      ├─ Step 13: Bollinger Bands → block overbought (v15.9)     │
│      ├─ Step 14: DEMA Crossover → block bearish (v15.9)         │
│      ├─ Step 15: MACD → block bearish (v15.9)                   │
│      └─ Step 16: Hurst Exponent → informational (v15.9)         │
│      │                                                           │
│      ▼                                                           │
│  Composite Score (14 components, weighted)                      │
│      │                                                           │
│      ▼                                                           │
│  Bayesian Kelly (EWMA volatility adjusted)                      │
│      │                                                           │
│      ▼                                                           │
│  Value Detection (float, pattern, sticker)                      │
│      │                                                           │
│      ▼                                                           │
│  Ternary Search Optimal Sell Price                              │
│      │                                                           │
│      ▼                                                           │
│  Fee Evaluation + Caps                                          │
│      │                                                           │
│      ▼                                                           │
│  Execute (Buy + List)                                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Источники

| Алгоритм | Источник |
|----------|----------|
| Hawkes Process | Cartea et al. (2015), Easley et al. (2012) |
| Bollinger Bands | Bollinger (2002) |
| DEMA/TEMA | Trotman (1992), Tilmann (1993) |
| MACD | Appel (1979) |
| Hurst Exponent | Mandelbrot (1972), Lo & MacKinlay (1988) |
| Markov Regime | arXiv regime switching models |
| EWMA | RiskMetrics (1996) |
| Bayesian Stats | Beta-Bayesian conjugate prior |
| Kelly Criterion | Kelly (1956) |
| VPIN | Easley et al. (2012) |
| Kyle Lambda | Kyle (1985) |
| Amihud | Amihud (2002) |
| Roll Model | Roll (1984) |
| Stoikov Micro-Price | Stoikov (2017) |

---

*Последнее обновление: 16 июля 2026*
