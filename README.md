<div align="center">

# DMarket Quantitative Engine

### Order Book Imbalance (OBI) Trading Bot for DMarket Marketplace

![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)
![Rust](https://img.shields.io/badge/Rust-1.96-000000?logo=rust&logoColor=white)
![Strategy](https://img.shields.io/badge/Strategy-OBI%20Demand-44CC11)
![Version](https://img.shields.io/badge/Version-17.2-purple)

*Автономная торговая система на основе Order Book Imbalance (OBI) сигналов.*
*Покупка предметов с высоким спросом, удержание 1-3 дня, продажа при росте цены.*

</div>

---

## Содержание

- [О проекте](#о-проекте)
- [Торговая стратегия](#торговая-стратегия)
- [Установка и настройка](#установка-и-настройка)
- [Мониторинг](#мониторинг)
- [Конфигурация](#конфигурация)
- [Архитектура](#архитектура)
- [Лицензия](#лицензия)

---

## О проекте

DMarket Quantitative Engine — это автономный торговый бот для площадки DMarket,
использующий **Order Book Imbalance (OBI)** стратегию для поиска прибыльных предметов.

### Ключевые особенности

| Особенность | Описание |
|---|---|
| **OBI Strategy** | Queue Imbalance (Gould & Bonart 2016) + Stoikov Micro-Price (2017) |
| **Demand-Based** | Покупка при высоком спросе (bid_count / ask_count > 2.0) |
| **Adaptive Thresholds** | Динамические пороги по ценовым сегментам ($0.50-$15) |
| **Dynamic Stop-Loss** | EWMA-волатильность + instant stop при падении >5% |
| **Peak Avoidance** | Медианная оценка + проверка тренда (не покупать на пике) |
| **30+ алгоритмов** | GARCH, HMM, OU, Hawkes, Bollinger, DEMA, MACD, Hurst, VPIN |
| **21 microstructure фильтров** | OBI, OFI, VWAP, VPIN, CVD, Queue Imbalance, Hawkes |
| **Rust Core** | Ed25519 подпись через PyO3 (zero-copy) |

### Стек технологий

| Компонент | Технология |
|-----------|-----------|
| Язык | Python 3.13+ |
| Подпись | Rust (PyO3) + Ed25519 |
| БД | SQLite (WAL mode) |
| API | DMarket REST API v2 |
| Логирование | structlog |
| Мониторинг | Telegram Bot (aiogram 3.x) |

---

## Торговая стратегия

### Академическое обоснование

Стратегия основана на **Order Book Imbalance (OBI)** — микроструктурном сигнале,
который предсказывает краткосрочное движение цены на основе соотношения
покупателей и продавцов в стакане.

**Источники:**
- **Gould, M. & Bonart, J.** (2016). "Queue Imbalance as a One-Tick-Ahead Price Predictor"
- **Stoikov, S.** (2017). "The Micro-Price: A High Frequency Estimator of Future Prices"
- **Cont, R., Kukanov, A., Stoikov, S.** (2014). "The Price Impact of Order Book Events"
- **Avellaneda, M., Stoikov, S.** (2008). "High-Frequency Trading in a Limit Order Book"

### Как работает стратегия

```
1. Получить агрегированные данные DMarket (bid_count, ask_count, best_bid, best_ask)
2. Рассчитать Queue Imbalance: Q = bid_count / ask_count
3. Если Q > 2.0 (в 2 раза больше покупателей) — сигнал BUY
4. Рассчитать OBI (volume-weighted): obi = (V_bid - V_ask) / (V_bid + V_ask)
5. Оценить справедливую цену: P_micro = mid + c × spread × OBI
6. Применить peak avoidance: штраф 15% если цена >15% выше 7-дневной медианы
7. Купить по текущей цене ask
8. Удерживать 1-3 дня (динамический stop-loss по EWMA волатильности)
9. Продать при достижении целевой цены или time-based stop
```

### Параметры стратегии

| Параметр | Значение | Описание |
|----------|----------|----------|
| `min_demand_ratio` | 1.5-2.5x | Минимальный Q (адаптивно по цене) |
| `min_volume` | 5-15 | Минимальное количество ордеров |
| `max_hold_days` | 2-6 дней | Максимум удержания (динамический) |
| `instant_stop` | -5% | Мгновенный стоп при падении цены |
| `peak_penalty` | 15% | Штраф если цена >15% выше медианы |

### Адаптивные пороги по цене

| Цена предмета | Min Q | Min Volume | Max Hold |
|--------------|-------|------------|----------|
| < $2.00 | 1.5x | 5 | 10 дней |
| $2.00 - $5.00 | 2.0x | 10 | 7 дней |
| > $5.00 | 2.5x | 15 | 5 дней |

---

## Установка и настройка

### Требования

- Python 3.13+
- Rust (для компиляции PyO3 модуля)
- DMarket API ключи

### Установка

```bash
# Клонировать репозиторий
git clone https://github.com/your-repo/Dmarket_bot-main.git
cd Dmarket_bot-main

# Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Собрать Rust модуль
cd rust_core && maturin develop --release && cd ..
```

### Настройка

Создать `.env` файл:

```bash
# DMarket API
DMARKET_PUBLIC_KEY=your_public_key
DMARKET_SECRET_KEY=your_secret_key

# Telegram (опционально)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ADMIN_IDS=your_user_id

# Режим работы
DRY_RUN=true
ENVIRONMENT=development
```

### Запуск

```bash
# DRY RUN режим (без реальных сделок)
DRY_RUN=true python -m src

# Production режим
DRY_RUN=false python -m src
```

---

## Мониторинг

### Telegram команды

| Команда | Описание |
|---------|----------|
| `/status` | Текущий статус бота, баланс, количество кандидатов |
| `/positions` | Открытые позиции (включая demand items) |
| `/pnl` | Прибыль/убыток по стратегиям |
| `/stop` | Остановить бота |
| `/start` | Возобновить работу |

### Метрики

| Метрика | Целевое значение | Описание |
|---------|-----------------|----------|
| Кандидаты/цикл | 10-15 | Найденные OBI возможности |
| Demand ratio | >5x | Средний Q (покупатели/продавцы) |
| OBI value | >0.5 | Volume-weighted imbalance |
| Hold days | 1-3 дня | Время удержания позиции |
| Win rate | >55% | Процент прибыльных сделок |

---

## Конфигурация

### Основные параметры

| Параметр | Значение по умолчанию | Описание |
|----------|----------------------|----------|
| `DEMAND_STRATEGY_ENABLED` | `True` | Включить OBI стратегию |
| `DEMAND_MAX_HOLD_DAYS` | `3.0` | Максимум дней удержания |
| `DEMAND_ADAPTIVE_THRESHOLDS` | `True` | Адаптивные пороги по цене |
| `ORACLE_ENABLED_FOR_DEMAND` | `False` | Оракулы не используются |
| `MAX_SNIPING_PRICE_USD` | `10.00` | Максимальная цена предмета |
| `MIN_SPREAD_PCT` | `1.5` | Минимальный спред (%) |
| `FEE_RATE` | `0.025` | Комиссия DMarket (2.5%) |
| `WITHDRAWAL_FEE_RATE` | `0.005` | Комиссия вывода (0.5%) |

### Параметры риск-менеджмента

| Параметр | Значение | Описание |
|----------|----------|----------|
| `STOP_LOSS_PCT` | `10.0` | Стоп-лосс (%) |
| `TAKE_PROFIT_PCT` | `15.0` | Тейк-профит (%) |
| `BALANCE_RESERVE_USD` | `5.00` | Резерв баланса |
| `KELLY_ENABLED` | `True` | Kelly Criterion для размера позиции |
| `KELLY_FRACTION` | `0.50` | Half Kelly (50%) |

---

## Архитектура

### Структура проекта

```
src/
├── analysis/                    # Алгоритмы и индикаторы
│   ├── algo_pack/              # GARCH, HMM, OU, Hawkes, etc.
│   └── microstructure/         # OBI, OFI, VWAP, VPIN
├── api/                        # API клиенты
│   └── dmarket_api_client/     # DMarket REST API v2
├── core/
│   └── target_sniping/         # Торговый пайплайн
│       ├── demand_strategy.py  # OBI стратегия (v17.2)
│       ├── filter.py           # Фильтрация кандидатов
│       ├── position_guard.py   # Stop-loss, take-profit
│       └── execution.py        # Исполнение сделок
├── db/                         # SQLite база данных
├── risk/                       # Риск-менеджмент
└── telegram/                   # Telegram бот мониторинга
```

### Пайплайн (один цикл, ~30 секунд)

```
Scanner → Aggregated Prices → OBI Filter → Demand Score → Peak Check → Execute
   │           │                  │              │             │           │
   │     bid/ask counts     Q > 2.0?      score calc    median check   buy/sell
   │           │                  │              │             │           │
   └───────────┴──────────────────┴──────────────┴─────────────┴───────────┘
```

---

## Лицензия

MIT License — см. [LICENSE](LICENSE) для деталей.

---

<div align="center">

**DMarket Quantitative Engine v17.2** | Order Book Imbalance Strategy

</div>
