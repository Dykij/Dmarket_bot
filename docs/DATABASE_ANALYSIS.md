# Анализ базы данных — DMarket Bot

## 1. Архитектура БД

### Схема хранения
```
dmarket_state.db (OLTP)        dmarket_history.db (OLAP)
├── scanning_state              ├── price_history
├── active_targets              └── trade_history
├── virtual_inventory
├── asset_status
├── low_fee_cache
└── pump_blacklist

dmarket_trading.db
├── trades
└── daily_pnl
```

### Разделение OLTP/OLAP
| Характеристика | OLTP (state) | OLAP (history) |
|---------------|-------------|----------------|
| Паттерн записи | Частые мелкие INSERT/UPDATE | Редкие массовые INSERT |
| Паттерн чтения | Точка SELECT по ключу | Агрегаты (AVG, SUM, COUNT) |
| Размер | ~1-10 MB | ~10-100 MB |
| Retention | Текущее состояние | История 30+ дней |

---

## 2. Типы анализа БД

### 2.1 Анализ SQL-инъекций
**Что делает:** Проверяет все SQL запросы на использование параметризованных запросов.

**Метод проверки:**
```python
# ПРАВИЛЬНО (параметризованный):
cursor.execute("SELECT * FROM t WHERE id = ?", (item_id,))

# НЕПРАВИЛЬНО (инъекция):
cursor.execute(f"SELECT * FROM t WHERE id = {item_id}")
```

**Статус в DMarket Bot:** ✅ ВСЕ запросы параметризованы (подтверждено аудитом).

---

### 2.2 Анализ индексов
**Что делает:** Проверяет, что часто используемые WHERE/ORDER BY покрыты индексами.

**Текущие индексы:**
| Таблица | Индекс | Покрывает |
|---------|--------|-----------|
| price_history | idx_hash_name_time | hash_name, recorded_at |
| trade_history | idx_trade_hash_time | hash_name, recorded_at |
| virtual_inventory | idx_inv_status | status |
| pump_blacklist | idx_pump_expires | expires_at |
| active_targets | idx_target_created | created_at |

**Потенциальные проблемы:**
- `virtual_inventory` — нет индекса по `hash_name` (используется в SELECT)
- `asset_status` — нет индекса по `item_id` (частый WHERE)

---

### 2.3 Анализ блокировок
**Что делает:** Проверяет contention и deadlock scenarios.

**Механизмы:**
| Механизм | Описание | Статус |
|----------|----------|--------|
| WAL mode | Читатели не блокируют писателей | ✅ Включён |
| busy_timeout | Ожидание 5с при locked | ✅ Настроен |
| @with_db_retry | Retry при "locked"/"busy" | ✅ На всех записях |
| ThreadPoolExecutor | max_workers=2 | ⚠️ Потенциальное узкое место |

**Потенциальная проблема:**
```python
# core.py:45 — только 2 воркера для ВСЕХ БД операций
_db_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="db")
```
При высокой нагрузке (>2 concurrent DB операций) — очередь будет расти.

---

### 2.4 Анализ миграций
**Что делает:** Проверяет безопасность схемных изменений.

**Текущий подход:**
```python
# Migration via try/except ALTER TABLE
for col, typedef in _ALLOWED_COLUMNS.items():
    try:
        conn.execute(f"ALTER TABLE [{table}] ADD COLUMN [{col}] {typedef}")
    except sqlite3.OperationalError:
        pass  # Column already exists
```

**Проблемы:**
- Нет версионирования миграций
- Нет rollback механизма
- `ALTER TABLE` не идемпотентен для других типов изменений

---

### 2.5 Анализ производительности
**Что делает:** Находит медленные запросы и N+1 проблемы.

**PRAGMA настройки:**
| PRAGMA | Значение | Эффект |
|--------|----------|--------|
| journal_mode=WAL | Включён | Concurrent reads during writes |
| synchronous=NORMAL | Включён | Быстрее, чем FULL |
| cache_size=-64000 | 64MB | Кеш страниц в памяти |
| temp_store=MEMORY | Включён | Временные таблицы в RAM |
| mmap_size=268435456 | 256MB | Memory-mapped I/O |
| busy_timeout=5000 | 5 сек | Ожидание при locked |

**Проблемы производительности:**
| Проблема | Файл | Описание |
|----------|------|----------|
| N+1 в run_cycle | core.py | Цикл по items с DB запросами внутри |
| Missing ANALYZE | core.py | Нет автоматического ANALYZE |
| Large DELETE | history.py | `DELETE FROM trade_history WHERE recorded_at < ?` без LIMIT |

---

### 2.6 Анализ целостности данных
**Что делает:** Проверяет constraints, foreign keys, уникальность.

**Constraints:**
| Таблица | Constraint | Тип |
|---------|-----------|-----|
| price_history | hash_name + recorded_at | UNIQUE |
| trade_history | hash_name + trade_date | UNIQUE (INSERT OR IGNORE) |
| scanning_state | key | PRIMARY KEY (INSERT OR REPLACE) |
| active_targets | item_id + created_at | UNIQUE |
| pump_blacklist | hash_name | PRIMARY KEY (INSERT OR REPLACE) |

**Отсутствующие constraints:**
- `virtual_inventory` — нет UNIQUE на `hash_name + acquired_at`
- Нет FOREIGN KEY между таблицами

---

## 3. Методология устранения ошибок БД

### 3.1 Retry Pattern
```python
@with_db_retry(max_attempts=3)
def write_operation():
    conn.execute("INSERT ...")
    conn.commit()
```
Backoff: 50ms → 100ms → 200ms (max 500ms)

### 3.2 Connection Safety
```python
conn = sqlite3.connect(path, check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")
```

### 3.3 Batch Operations
```python
# ПРАВИЛЬНО (batch):
conn.executemany("INSERT OR REPLACE INTO t VALUES (?, ?, ?)", rows)
conn.commit()

# НЕПРАВИЛЬНО (по одному):
for row in rows:
    conn.execute("INSERT INTO t VALUES (?, ?, ?)", row)
    conn.commit()
```

### 3.4 Schema Migration
```python
# Текущий подход (try/except):
try:
    conn.execute("ALTER TABLE t ADD COLUMN new_col TEXT")
except sqlite3.OperationalError:
    pass  # Already exists

# Рекомендуемый подход (version tracking):
if current_version < 3:
    conn.execute("ALTER TABLE t ADD COLUMN new_col TEXT")
    conn.execute("UPDATE schema_version SET version = 3")
```

---

## 4. Мониторинг БД

### 4.1 Query Profiler
```python
# src/utils/query_profiler.py
profiler = QueryProfiler()
profiler.start()
result = conn.execute(query)
profiler.stop(query_name="get_latest_price")
# → Логирует медленные запросы (>100ms)
```

### 4.2 Health Checks
```python
def check_db_health():
    try:
        conn.execute("SELECT 1")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

### 4.3 WAL Checkpoint
```python
# Периодический checkpoint для очистки WAL файла
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
```
