# Анализ API — DMarket Bot

## 1. Типы анализа API

### 1.1 Анализ доступности (Availability Analysis)
**Что делает:** Проверяет, доступен ли API endpoint и отвечает ли он.

**Методы:**
- Health check запросы (GET /health)
- Ping/pong мониторинг
- Uptime tracking (SLI/SLO)

**Метрики:**
| Метрика | Формула | Целевое значение |
|---------|---------|-----------------|
| Availability | uptime / total_time × 100% | >99.5% |
| Error rate | errors / total_requests × 100% | <1% |
| Latency P50 | 50-й перцентиль ответа | <200ms |
| Latency P99 | 99-й перцентиль ответа | <2000ms |

---

### 1.2 Анализ rate limiting
**Что делает:** Отслеживает потребление квоты и предотвращает 429 ошибки.

**Методы:**
- Token bucket алгоритм
- Sliding window counter
- Adaptive backoff на Retry-After header

**Стратегии:**
| Стратегия | Описание | Когда использовать |
|-----------|----------|-------------------|
| Fixed window | N запросов в минуту | Простые API |
| Token bucket | Накопление токенов | Burst-tolerant API |
| Sliding window | Скользящее окно | Точные лимиты |
| Adaptive | Динамическая подстройка | Когда API сигнализирует 429 |

---

### 1.3 Анализ ошибок (Error Pattern Analysis)
**Что делает:** Классифицирует ошибки по типам и частоте.

**Классификация ошибок:**
| Код | Тип | Действие | Пример |
|-----|-----|----------|--------|
| 400 | Bad Request | Исправить запрос | Невалидные параметры |
| 401 | Unauthorized | Проверить ключи | Истёкший токен |
| 403 | Forbidden | Проверить права | Нет доступа к ресурсу |
| 404 | Not Found | Проверить endpoint | Несуществующий ресурс |
| 409 | Conflict | Проверить состояние | Дубликат заказа |
| 429 | Rate Limit | Exponential backoff | Превышен лимит |
| 500 | Server Error | Retry с backoff | Внутренняя ошибка |
| 502 | Bad Gateway | Retry с backoff | Gateway недоступен |
| 503 | Service Unavailable | Retry с backoff | Сервис перегружен |

---

### 1.4 Анализ идемпотентности (Idempotency Analysis)
**Что делает:** Проверяет, что повторные запросы не создают дубликаты.

**Методы:**
- Уникальный `client_order_id` для каждой операции
- Формат: `{item_id}_{timestamp}_{hash}`
- При дубликате — treat as success

---

### 1.5 Анализ кеширования (Cache Analysis)
**Что делает:** Оценивает эффективность кеша оракулов.

**Метрики:**
| Метрика | Формула | Целевое значение |
|---------|---------|-----------------|
| Hit rate | hits / (hits + misses) × 100% | >80% |
| Staleness | avg(age of cached data) | <1h |
| Eviction rate | evictions / total_entries | <10% |

---

## 2. Типы ошибок API в DMarket Bot

### 2.1 Ошибки DMarket API
| Ошибка | Причина | Решение |
|--------|---------|---------|
| 401 Unauthorized | Невалидный ключ | Проверить DMARKET_PUBLIC_KEY/SECRET_KEY |
| 429 Rate Limit | Превышен лимит (10 req/s) | Exponential backoff + circuit breaker |
| 409 Conflict | Дубликат target | Использовать уникальный order_id |
| 500 Server Error | Внутренняя ошибка DMarket | Retry 3 раза с backoff |
| Timeout | Медленный ответ | Увеличить timeout до 30s |

### 2.2 Ошибки MultiSourceOracle
| Ошибка | Причина | Решение |
|--------|---------|---------|
| Timeout | Медленный ответ оракула | Использовать кеш (fallback) |
| No data | Предмет не найден | Пропустить предмет, залогировать |
| Stale data | Устаревшие цены | Проверять max_age_seconds |

### 2.3 Ошибки Steam API
| Ошибка | Причина | Решение |
|--------|---------|---------|
| 429 Rate Limit | Превышен лимит Steam | Кешировать ответы |
| 502 Bad Gateway | Steam перегружен | Retry с backoff |
| Null price | Предмет не торгуется | Пропустить предмет |

---

## 3. Методологии устранения ошибок API

### 3.1 Exponential Backoff
```
attempt 1: immediate
attempt 2: wait 1s
attempt 3: wait 2s
attempt 4: wait 4s
attempt 5: HALT, alert human
```

### 3.2 Circuit Breaker
```
CLOSED → (5 failures) → OPEN → (60s timeout) → HALF-OPEN → (1 success) → CLOSED
```

### 3.3 Fallback Chain
```
Primary API → Cache → Fallback API → Default value → Error
```

### 3.4 Retry-After Respect
```python
if response.status == 429:
    retry_after = int(response.headers.get("Retry-After", "60"))
    await asyncio.sleep(retry_after)
```

### 3.5 Graceful Degradation
```python
try:
    price = await oracle.get_price(item)
except OracleTimeout:
    price = cache.get(item)  # Fallback to cache
except Exception:
    price = None  # Skip item
```

---

## 4. API Safety Patterns в DMarket Bot

### 4.1 Balance Gate
Перед каждой сделкой проверяется баланс:
```python
effective_balance = available - reserved
if trade_amount > effective_balance * 0.10:
    REJECT
```

### 4.2 Drawdown Freeze
При просадке >15% — только продажи:
```python
if current_balance < peak_balance * 0.85:
    FREEZE_ALL_BUYS
```

### 4.3 Position Sizing (Half Kelly)
```python
kelly_fraction = 0.5  # Half Kelly
position_size = min(
    kelly_fraction * (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win,
    max_position_pct * effective_balance
)
```

### 4.4 Rate Limit Coordination
```python
# Public endpoints: 10 RPS
# Private endpoints: 2 RPS
# Use adaptive delay based on X-RateLimit-Remaining header
```
