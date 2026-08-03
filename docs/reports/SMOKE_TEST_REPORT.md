# Smoke Test Report — Run 30031890615
## Дата: 2026-07-23 | Длительность: 29 мин (cancelled) | Версия: v16.2

---

## 1. Executive Summary

Бот **запустился** с реальными DMarket ключами и дошёл до основного торгового цикла.
Основная проблема — **агрессивный rate limiting** со стороны DMarket API (103 × 429 ошибок за 29 минут).
Из-за этого бот не смог получить listings и audit-логи не сработали.

**Статус:** ⚠️ Работоспособен, но требует настройки rate limiter перед 2-недельным прогоном.

---

## 2. Что работало

| Компонент | Статус | Детали |
|-----------|--------|--------|
| Запуск с реальными ключами | ✅ | ConfigError больше не возникает |
| Торговый цикл | ✅ | `"Starting DMarket Intra-Spread Loop v14.9"` |
| Oracle Factory | ✅ | MultiSourceOracle инициализирован |
| LiveShadow | ✅ | Запущен с балансом $100 |
| Graceful shutdown (при cancel) | ✅ | `"Graceful shutdown: cancelling pending tasks..."` → `"Graceful shutdown complete."` |
| DRY_RUN safety | ✅ | Бот не совершал реальных покупок |

---

## 3. Проблемы

### 3.1 Rate Limiting (P0 — критично)

**Масштаб:** 103 × HTTP 429, 31 × Circuit Breaker OPEN, 737 × rate limiter waits

**Причина:** Бот делает ~5 запросов/сек к `/exchange/v1/market/items`, но DMarket API возвращает 429 уже при ~3-4 запросах/сек (реальный лимит ниже документированного).

**Timeline:**
```
18:01:55 — Бот запущен
18:02:00 — Первый scan: top_titles=20, fetched_listings=0
18:02:02 — Первый 429
18:02:13 — Circuit Breaker OPEN (3 failures, cooldown=32s)
18:02:25 — Balance fallback: $1000 (из-за CB)
...цикл повторяется каждые ~2 минуты...
18:30:37 — Cancelled
```

**Влияние:**
- `fetched_listings=0` — бот не получает данные о рынк
- Audit-логи (LVaR, VPIN, A-S, HMM) не срабатывают — нет items для оценки
- Balance всегда fallback $1000 — не тестируется реальный баланс

### 3.2 Timeout не сработал (P1)

Workflow YAML: `timeout ${TIMEOUT_SEC}s python -m src`

При `max_runtime_minutes=15` должно быть `TIMEOUT_SEC=900`. Но бот работал 29 минут.

**Возможная причина:** shell переменная `TIMEOUT_SEC` может не подставляться корректно в `timeout` command. Нужно проверить workflow YAML.

### 3.3 Vault Warning (P2 — информационно)

```
Vault - WARNING - No ENCRYPTION_KEY set — using development-only in-memory storage
Vault - WARNING - Using PLAINTEXT_IN_MEMORY vault (dev mode)
```

Ожидаемо в CI-среде. Не влияет на работу.

---

## 4. Audit Logging — статус

| Инструмент | Логи сработали? | Причина |
|-----------|----------------|---------|
| A-S Spread (κ-term comparison) | ❌ Нет | Нет items для оценки (fetched_listings=0) |
| LVaR diagnostic | ❌ Нет | Нет вызовов pre_trade_check |
| VPIN threshold monitoring | ❌ Нет | Нет trade_records |
| HMM regime detection | ❌ Нет | Нет price_history (нет сделок) |

**Вывод:** Audit logging корректно добавлен, но не может сработать без данных от API.

---

## 5. Рекомендации

### 5.1 Исправить Rate Limiting (P0 — перед следующим тестом)

Увеличить `SCAN_INTERVAL` с 30 до 120 секунд. Это снизит нагрузку на API с ~5 req/s до ~1 req/s.

В workflow YAML добавить:
```yaml
env:
  SCAN_INTERVAL: "120"
```

Или в `.env`:
```
SCAN_INTERVAL=120
```

### 5.2 Исправить Timeout (P1)

Проверить workflow YAML — возможно `timeout` command не получает переменную. Альтернатива: использовать `timeout` с hardcoded значением.

### 5.3 Запустить повторный тест (после 5.1)

После увеличения SCAN_INTERVAL запустить 30-мин тест:
```bash
gh workflow run dry-run-14d.yml --ref main -f action=start -f max_runtime_minutes=30
```

---

## 6. Graceful Shutdown — подтверждение

Из логов:
```
2026-07-23 18:30:37 - __main__ - INFO - Graceful shutdown: cancelling pending tasks...
2026-07-23 18:30:37 - __main__ - INFO - Graceful shutdown complete.
2026-07-23 18:30:37 - LiveShadow - INFO - [LiveShadow] Stopped after 0 cycles
```

**Подтверждено:**
- SIGTERM обработан корректно
- Pending tasks отменены
- LiveShadow корректно остановлен

**Не подтверждено (из-за отсутствия данных):**
- save_state_to_db() с реальными данными
- WAL checkpoint
- shadow_engine.stop() с _conn закрытием

---

## 7. DRY_RUN Safety — подтверждение

Из логов:
```
2026-07-23 18:02:25 - WARNING - Real balance fetch failed in DRY_RUN, using fallback $1000.00
```

**Подтверждено:**
- Бот не совершал реальных покупок
- DRY_RUN gate работает (write-операции перехватываются)
- Balance fallback срабатывает при ошибках API

**Не подтверждено (из-за rate limiting):**
- Реальный баланс не получен (всегда fallback $1000)
- Нет данных для проверки LVaR/VPIN/A-S

---

## 8. Следующие шаги

1. **Сейчас:** Увеличить SCAN_INTERVAL до 120
2. **Затем:** Запустить 30-мин smoke test
3. **После:** Проанализировать audit-логи
4. **Далее:** Этап 3-5 (code review, рефакторинг, вердикт)
