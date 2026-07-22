# Анализ базы данных — DMarket Bot (v16.2)

## 1. Архитектура БД

### Схема хранения (4 базы данных, 19 таблиц)

```
dmarket_state.db (OLTP)              dmarket_history.db (OLAP)
├── schema_version                   ├── schema_version
├── scanning_state                   ├── price_history
├── virtual_inventory                └── trade_history
├── missed_opportunities
├── decision_logs
├── active_targets
├── low_fee_cache
├── asset_status
├── equity_snapshots
├── risk_events
└── pump_blacklist

dmarket_trading.db                   dmarket_shadow.db
├── trades                           ├── shadow_inventory
└── daily_pnl                        ├── shadow_snapshots
                                     └── shadow_strategies
```

### Разделение OLTP/OLAP

| Характеристика | OLTP (state) | OLAP (history) | Trading | Shadow |
|---------------|-------------|----------------|---------|--------|
| Паттерн записи | Частые мелкие INSERT/UPDATE | Редкие массовые INSERT | Средние | Средние |
| Паттерн чтения | Точка SELECT по ключу | Агрегаты (AVG, SUM, COUNT) | Агрегаты | Агрегаты |
| Размер | ~1-10 MB | ~10-100 MB | ~1-5 MB | ~1-5 MB |
| Retention | Текущее состояние | История 30+ дней | Постоянно | Постоянно |

---

## 2. Полная схема таблиц

### 2.1 dmarket_state.db (11 таблиц)

**`schema_version`** — Tracking миграций
| Column | Type | Constraints |
|--------|------|-------------|
| version | INTEGER | PRIMARY KEY |
| description | TEXT | NOT NULL |
| applied_at | REAL | NOT NULL |

**`scanning_state`** — Cursor persistence (key/value)
| Column | Type | Constraints |
|--------|------|-------------|
| key | TEXT | PRIMARY KEY |
| value | TEXT | NOT NULL |
| updated_at | REAL | NOT NULL |

**`virtual_inventory`** — Tracked buy/sell items (core table)
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK AUTOINCREMENT |
| hash_name | TEXT | NOT NULL |
| buy_price | REAL | NOT NULL |
| sell_price | REAL | nullable |
| fee_paid | REAL | nullable |
| profit | REAL | nullable |
| status | TEXT | NOT NULL DEFAULT 'idle' |
| acquired_at | REAL | NOT NULL |
| unlock_at | REAL | NOT NULL DEFAULT 0 |
| sold_at | REAL | nullable |
| dm_item_id | TEXT | nullable |
| dm_offer_id | TEXT | nullable |
| listed_at | REAL | nullable |
| list_error | TEXT | nullable |
| funds_hold_until | REAL | nullable |
| rollback_refund | INTEGER | NOT NULL DEFAULT 0 |
| exclusive | INTEGER | NOT NULL DEFAULT 0 |

Индексы: `idx_vinv_dm_item(dm_item_id)`, `idx_vinv_dm_offer(dm_offer_id)`, `idx_vinv_status(status)`, `idx_vinv_status_acquired(status, acquired_at)`, `idx_vinv_name_status(hash_name, status)`

**`missed_opportunities`** — Skipped profitable items
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK AUTOINCREMENT |
| hash_name | TEXT | NOT NULL |
| price | REAL | NOT NULL |
| expected_sell | REAL | NOT NULL |
| reason | TEXT | NOT NULL |
| timestamp | REAL | NOT NULL |

Индексы: `idx_missed_ts(timestamp)`, `idx_missed_name(hash_name)`

**`decision_logs`** — Bot decision audit trail
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK AUTOINCREMENT |
| hash_name | TEXT | NOT NULL |
| decision | TEXT | NOT NULL |
| reason | TEXT | NOT NULL |
| details | TEXT | nullable |
| timestamp | REAL | NOT NULL |

Индексы: `idx_decision_ts(timestamp)`, `idx_decision_name(hash_name)`

**`active_targets`** — Placed buy orders
| Column | Type | Constraints |
|--------|------|-------------|
| item_id | TEXT | PRIMARY KEY |
| hash_name | TEXT | NOT NULL |
| price | REAL | NOT NULL |
| created_at | REAL | NOT NULL |

Индексы: `idx_targets_created(created_at)`

**`low_fee_cache`** — Daily low-fee items cache
| Column | Type | Constraints |
|--------|------|-------------|
| title | TEXT | PRIMARY KEY |
| fee_rate | REAL | NOT NULL |
| fetched_at | REAL | NOT NULL |

**`asset_status`** — Trade protection tracking
| Column | Type | Constraints |
|--------|------|-------------|
| item_id | TEXT | PRIMARY KEY |
| title | TEXT | NOT NULL |
| status | TEXT | NOT NULL DEFAULT 'active' |
| finalization_time | REAL | NOT NULL DEFAULT 0 |
| created_at | REAL | NOT NULL |
| updated_at | REAL | NOT NULL |

Индексы: `idx_asset_status(status, updated_at)`

**`equity_snapshots`** — Daily equity for crash recovery
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK AUTOINCREMENT |
| taken_at | REAL | NOT NULL |
| snapshot_date | TEXT | NOT NULL (YYYY-MM-DD) |
| cash | REAL | NOT NULL |
| assets | REAL | NOT NULL |
| total | REAL | NOT NULL |
| realized_pnl | REAL | NOT NULL DEFAULT 0 |
| note | TEXT | nullable |

Индексы: `idx_equity_date(snapshot_date)`

**`risk_events`** — Kill-switch and risk event log
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK AUTOINCREMENT |
| ts | REAL | NOT NULL |
| event_type | TEXT | NOT NULL |
| severity | TEXT | NOT NULL DEFAULT 'warning' |
| details | TEXT | NOT NULL |

Индексы: `idx_risk_ts(ts)`

**`pump_blacklist`** — FOMO protection blacklist
| Column | Type | Constraints |
|--------|------|-------------|
| hash_name | TEXT | PRIMARY KEY |
| old_price | REAL | NOT NULL |
| new_price | REAL | NOT NULL |
| pct_change | REAL | NOT NULL |
| detected_at | REAL | NOT NULL |
| expires_at | REAL | NOT NULL |
| alerted | INTEGER | NOT NULL DEFAULT 0 |

Индексы: `idx_pump_expires(expires_at)`

### 2.2 dmarket_history.db (3 таблицы)

**`schema_version`** — Tracking миграций (same schema as state)

**`price_history`** — Oracle price observations
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK AUTOINCREMENT |
| hash_name | TEXT | NOT NULL |
| price | REAL | NOT NULL |
| source | TEXT | NOT NULL DEFAULT 'oracle' |
| recorded_at | REAL | NOT NULL |

Индексы: `idx_price_recorded(recorded_at)`, `idx_price_name(hash_name)`, `idx_price_name_time(hash_name, recorded_at DESC)`

**`trade_history`** — DMarket last-sales accumulation
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK AUTOINCREMENT |
| hash_name | TEXT | NOT NULL |
| price | REAL | NOT NULL |
| trade_date | TEXT | nullable |
| recorded_at | REAL | NOT NULL |
| source | TEXT | NOT NULL DEFAULT 'dmarket_last_sales' |

Индексы: `idx_trade_name(hash_name)`, `idx_trade_time(recorded_at)`, `idx_trade_unique(hash_name, price, trade_date)` [UNIQUE]

### 2.3 dmarket_trading.db (2 таблицы)

**`trades`** — Completed round-trip trades
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK AUTOINCREMENT |
| item_name | TEXT | NOT NULL |
| buy_price | REAL | NOT NULL |
| sell_price | REAL | NOT NULL |
| fee_amount | REAL | NOT NULL |
| net_profit | REAL | NOT NULL |
| trade_date | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

Индексы: `idx_trades_date(trade_date)`, `idx_trades_item(item_name)`

**`daily_pnl`** — Aggregated daily P&L
| Column | Type | Constraints |
|--------|------|-------------|
| date | DATE | PRIMARY KEY |
| total_profit | REAL | DEFAULT 0 |
| trades_count | INTEGER | DEFAULT 0 |

### 2.4 dmarket_shadow.db (3 таблицы)

**`shadow_inventory`** — Shadow positions
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK AUTOINCREMENT |
| title | TEXT | NOT NULL |
| buy_price | REAL | NOT NULL |
| current_price | REAL | DEFAULT 0 |
| sell_price | REAL | DEFAULT 0 |
| fee_paid | REAL | DEFAULT 0 |
| status | TEXT | DEFAULT 'idle' |
| strategy | TEXT | DEFAULT 'MarketMaker' |
| category | TEXT | DEFAULT 'other' |
| bought_at | REAL | NOT NULL |
| sold_at | REAL | nullable |

**`shadow_snapshots`** — Shadow equity snapshots
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK AUTOINCREMENT |
| ts | REAL | NOT NULL |
| cash | REAL | NOT NULL |
| assets | REAL | NOT NULL |
| total | REAL | NOT NULL |
| cycle | INTEGER | DEFAULT 0 |

**`shadow_strategies`** — Per-strategy stats
| Column | Type | Constraints |
|--------|------|-------------|
| name | TEXT | PRIMARY KEY |
| trades | INTEGER | DEFAULT 0 |
| wins | INTEGER | DEFAULT 0 |
| losses | INTEGER | DEFAULT 0 |
| total_pnl | REAL | DEFAULT 0 |
| peak_equity | REAL | DEFAULT 0 |
| max_drawdown_pct | REAL | DEFAULT 0 |
| sharpe | REAL | DEFAULT 0 |
| avg_profit | REAL | DEFAULT 0 |

---

## 3. Индексы (полный список, 17+)

| Таблица | Индекс | Покрывает | Тип |
|---------|--------|-----------|-----|
| virtual_inventory | `idx_vinv_dm_item` | dm_item_id | B-tree |
| virtual_inventory | `idx_vinv_dm_offer` | dm_offer_id | B-tree |
| virtual_inventory | `idx_vinv_status` | status | B-tree |
| virtual_inventory | `idx_vinv_status_acquired` | status, acquired_at | Composite |
| virtual_inventory | `idx_vinv_name_status` | hash_name, status | Composite |
| missed_opportunities | `idx_missed_ts` | timestamp | B-tree |
| missed_opportunities | `idx_missed_name` | hash_name | B-tree |
| decision_logs | `idx_decision_ts` | timestamp | B-tree |
| decision_logs | `idx_decision_name` | hash_name | B-tree |
| active_targets | `idx_targets_created` | created_at | B-tree |
| asset_status | `idx_asset_status` | status, updated_at | Composite |
| equity_snapshots | `idx_equity_date` | snapshot_date | B-tree |
| risk_events | `idx_risk_ts` | ts | B-tree |
| pump_blacklist | `idx_pump_expires` | expires_at | B-tree |
| price_history | `idx_price_recorded` | recorded_at | B-tree |
| price_history | `idx_price_name` | hash_name | B-tree |
| price_history | `idx_price_name_time` | hash_name, recorded_at DESC | Composite |
| trade_history | `idx_trade_name` | hash_name | B-tree |
| trade_history | `idx_trade_time` | recorded_at | B-tree |
| trade_history | `idx_trade_unique` | hash_name, price, trade_date | UNIQUE |
| trades | `idx_trades_date` | trade_date | B-tree |
| trades | `idx_trades_item` | item_name | B-tree |

---

## 4. Безопасность

### 4.1 SQL-инъекции
**Статус:** ✅ ВСЕ запросы параметризованы (`?` placeholders). Нет f-string SQL.

### 4.2 WAL Mode
| БД | WAL | busy_timeout | synchronous |
|----|-----|--------------|-------------|
| dmarket_state.db | ✅ | 5000ms | NORMAL |
| dmarket_history.db | ✅ | 5000ms | NORMAL |
| dmarket_trading.db | ✅ | 5000ms | NORMAL |
| dmarket_shadow.db | ✅ | 5000ms | (default FULL) |

### 4.3 Retry Pattern
```python
@with_db_retry(max_attempts=3)
def write_operation():
    conn.execute("INSERT ...")
    conn.commit()
```
Backoff: 50ms → 100ms → 200ms (max 3 attempts)

### 4.4 File Permissions
State и History БД создаются с `0o600` (owner read/write only) — `core.py:115-116`.

### 4.5 Batch Operations
`executemany` используется для `low_fee_cache`, `trade_history`. Single-row inserts для остальных (низкочастотные записи).

---

## 5. Schema Migration

### Текущий подход (v15.1+)
```python
# schema_version table tracks applied migrations
# Whitelist-validated column names in ALTER TABLE
for col, typedef in _ALLOWED_COLUMNS.items():
    try:
        conn.execute(f"ALTER TABLE [{table}] ADD COLUMN [{col}] {typedef}")
    except sqlite3.OperationalError:
        pass  # Column already exists
```

**Версионирование:** Таблица `schema_version` в каждой core БД (state + history). Записывает номер версии и описание при каждом применении миграции.

---

## 6. PRAGMA настройки

| PRAGMA | Значение | Эффект |
|--------|----------|--------|
| journal_mode=WAL | Включён | Concurrent reads during writes |
| synchronous=NORMAL | Включён | Быстрее, чем FULL |
| cache_size=-64000 | 64MB | Кеш страниц в памяти |
| temp_store=MEMORY | Включён | Временные таблицы в RAM |
| mmap_size=268435456 | 256MB | Memory-mapped I/O |
| busy_timeout=5000 | 5 сек | Ожидание при locked |

---

## 7. ThreadPoolExecutor

| Параметр | Значение | Файл |
|----------|----------|------|
| max_workers | **4** | `core.py:50` |
| thread_name_prefix | "db" | `core.py:50` |

---

## 8. Мониторинг

### Query Profiler
```python
# src/utils/query_profiler.py
profiler = QueryProfiler()
profiler.start()
result = conn.execute(query)
profiler.stop(query_name="get_latest_price")
# → Логирует медленные запросы (>100ms)
```

### WAL Checkpoint
```python
# Периодический checkpoint для очистки WAL файла
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
```

---

🦅 *Database Analysis | v16.2 | 2026-07-22*
