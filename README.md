# 🦅 DMarket Intra-Spread Engine (v12.0)

**High-Performance Intra-DMarket Arbitrage Engine for CS2 Skins.**

Автономная торговая система, эксплуатирующая bid-ask спреды **внутри DMarket** (без межбиржевого арбитража). Полностью перешла с CSFloat на CS2Cap (BUFF163 + 41 markets).

---

## 🚀 Основные Возможности

### 1. 📈 Strategy A: Intra-DMarket Spread
- **Buy at best_ask, sell at best_bid - $0.01**: Спред между заявками на покупку и продажу — это профит.
- **Aggregated Prices API**: 1 запрос = best_bid + best_ask для 100 предметов.
- **CS2Cap Oracle Validation**: BUFF163 цена как sanity check (отсекает переоценённые предметы).
- **Instant Execution**: Без 7d trade lock на стороне продажи.

### 2. 🛡️ Protection Layer
- **Trend Guard**: Блокировка покупок при падающем тренде (3 последовательных снижения).
- **Event Shield (2026)**: Динамическая корректировка риск-множителей (1.0x обычные, 2.0x во время мажоров/сейлов).
- **Position Risk Cap**: Максимум 30% баланса на одну позицию.
- **Volatility Filter**: Отклоняет предметы с волатильностью > 20%.
- **Slippage Guard**: Максимум 2% отклонения от ожидаемой цены.

### 3. ⚡ High-Frequency Pipeline
- **Bifurcated SQLite**: Раздельные БД для state (OLTP) и history (OLAP).
- **Async I/O**: aiohttp + asyncio для 4-5 RPS без блокировок.
- **Ed25519 NaCL**: Аутентификация DMarket через Python (pynacl) или Rust signer.
- **Telegram Interface**: Управление и мониторинг через защищённого бота.

### 4. 🔄 Sell Pipeline
- **create_offer()**: Листинг одной позиции
- **batch_create_offers()**: Пакетный листинг
- **delete_offers()**: Снятие нескольких офферов
- **edit_offer()**: Переоценка нераспроданных позиций
- **reprice_unsold_offers()**: Автоматический снижение цены каждые 6ч

---

## 🏗 Технический Стек

| Компонент | Технология |
| :--- | :--- |
| **Logic Core** | Python 3.11+, AsyncIO |
| **Oracle** | CS2Cap (BUFF163 + 41 markets) |
| **Market Data** | DMarket Aggregated Prices API |
| **Database** | SQLite 3 (Bifurcated: state + history) |
| **Security** | Ed25519 NaCL (pynacl или Rust) |
| **Interface** | Aiogram 3.x (Telegram) |

---

## 🛠 Установка и Запуск

### Быстрый старт
1. Клонировать репозиторий:
   ```bash
   git clone https://github.com/Dykij/Dmarket_bot.git
   cd Dmarket_bot
   ```
2. Установить зависимости:
   ```bash
   pip install -r requirements.txt
   ```
3. Скопировать и настроить `.env`:
   ```bash
   cp .env.example .env
   # Отредактируйте DMARKET_PUBLIC_KEY, DMARKET_SECRET_KEY, CS2C_API_KEY
   ```
4. Запустить тесты:
   ```bash
   PYTHONPATH=. python3 scratch/test_sandbox_v9.py
   # Должно быть 14/14 passing
   ```
5. Запустить sandbox audit:
   ```bash
   PYTHONPATH=. python3 scratch/sandbox_audit.py
   ```
6. Запустить движок:
   ```bash
   python -m src
   ```

---

## 📊 Стратегия "Intra-Spread"

Бот использует **стратегию A** (intra-DMarket spread arbitrage):

1. Сканирует 50 предметов через `/exchange/v1/market/items`
2. Запрашивает aggregated prices (best_bid + best_ask) для всех 50
3. Фильтрует: `best_bid > best_ask * 1.05` (5%+ спред)
4. Валидирует через CS2Cap (BUFF163): если DMarket цена > BUFF163 * 1.5 — skip (переоценён)
5. Покупает по `best_ask`, выставляет по `best_bid - 0.01`
6. Каждые 6ч переоценивает нераспроданные позиции

**Ожидаемая доходность** на балансе $44: **$3-9/день (7-20% daily ROI)**

Полный роадмап всех 6 стратегий (A-F) — в `docs/STRATEGY_ROADMAP.md`.

---

## 🧪 Тестирование

```bash
# 14 unit tests (все должны проходить)
PYTHONPATH=. python3 scratch/test_sandbox_v9.py

# 50-item sandbox audit (Strategy A simulation)
PYTHONPATH=. python3 scratch/sandbox_audit.py
```

Типичный результат audit:
- 50 предметов просканировано
- 5-10 profitable opportunities найдено (10-20% hit rate)
- $1-5 profit potential per cycle
- $30-40 capital deployed

---

## 📁 Структура проекта

```
Dmarket_bot/
├── src/
│   ├── api/
│   │   ├── cs2cap_oracle.py       # CS2Cap oracle (BUFF163)
│   │   ├── dmarket_api_client.py  # DMarket API v2 client
│   │   ├── market_data_fetcher.py # Public order book
│   │   └── oracle_factory.py      # Multi-game factory
│   ├── core/
│   │   ├── target_sniping.py      # Main trading loop
│   │   ├── event_shield.py        # Event-driven margin multiplier
│   │   └── sandbox_scenarios.py   # Market scenario simulator
│   ├── db/
│   │   └── price_history.py       # Bifurcated SQLite
│   ├── risk/
│   │   ├── price_validator.py     # TVM + slippage + volatility
│   │   └── liquidity_manager.py   # Daily spend cap
│   ├── analytics/
│   │   ├── rare_valuation.py      # Rare items (Howl, Katowice)
│   │   └── stickers_evaluator.py  # Sticker value
│   ├── telegram/                  # Telegram bot interface
│   └── config.py                  # All tunables
├── scratch/
│   ├── test_sandbox_v9.py         # 14-test verification
│   └── sandbox_audit.py           # Full pipeline simulation
├── data/
│   ├── dmarket_state.db           # OLTP (orders, inventory)
│   ├── dmarket_history.db         # OLAP (price history)
│   └── cs2_events.json            # 17 events calendar
├── docs/
│   ├── STRATEGY_ROADMAP.md        # All 6 strategies (A-F)
│   ├── API_COMPLETE_REFERENCE.md
│   ├── DMARKET_API_FULL_SPEC.md
│   └── ...
├── .env.example                   # Template
├── .env                           # Real credentials (gitignored)
└── requirements.txt
```

---

## 🔐 Безопасность

- `.env` файл **НЕ** коммитится (в `.gitignore`)
- Все API ключи только в `.env`
- DRY_RUN=true по умолчанию (никаких реальных сделок)
- Ed25519 подпись для всех DMarket API запросов
- 5% chance of simulated API errors в sandbox для resilience testing

---

## 📜 Лицензия

См. [LICENSE](LICENSE).

---

🦅 *DMarket Intra-Spread Engine | v12.0 | 2026*
