# 🔧 Troubleshooting Guide — Все ошибки и их решения (v14.9)

> **Объединённое руководство по устранению неполадок DMarket Quantitative Engine**
> 
> **Последнее обновление:** Июнь 2026 | **Версия:** 14.9

---

## 📋 Содержание

- [Docker](#docker)
- [Установка и настройка](#установка-и-настройка)
- [Telegram Bot](#telegram-bot)
- [DMarket API](#dmarket-api)
- [База данных](#база-данных-и-миграции)
- [v14.4 Balance-Aware](#v144-balance-aware-специфичные-ошибки)
- [Rust модуль](#rust-модуль)
- [Исправленные баги](#исправленные-баги)

---

## 🐳 Docker

### Контейнер не запускается
```bash
docker compose logs dmarket_bot
# Проверьте:
# 1. .env заполнен правильно
# 2. Dockerfile собран (docker compose build)
# 3. Порты не заняты
# 4. curl -sf http://127.0.0.1:9091/healthz (health check)
```

### Ошибка: TelemetryConflictError / terminated by other getUpdates request
**Причина:** Telegram bot работает в polling mode с другим инстансом.
**Решение:** Убедитесь, что только один процесс использует TELEGRAM_BOT_TOKEN.

### Health check failing
```bash
# Проверьте, что HEALTH_PORT=9091 установлен в .env
curl http://127.0.0.1:9091/healthz
# Если нет ответа — бот не запущен или порт занят
```

### Memory limit reached
```yaml
# В docker-compose.yml увеличьте memory limit
deploy:
  resources:
    limits:
      memory: 1G  # было 512M
```

### Docker build fails on ARM64 (Raspberry Pi)
```bash
# Проверьте, что Dockerfile multi-stage компилирует Rust
# Rust работает на ARM64 — dmarket_parser_rs должен собраться
# Если Rust сборка падает — бот запустится в Python fallback режиме
```

### Rust module failed to compile in Docker
Бот автоматически использует Python fallback. Лог покажет:
```
WARNING: Rust Signer not found, using Python (pynacl) fallback.
```
Это не критично — все функции работают, просто медленнее.

---

## Установка и настройка

### Ошибка: ModuleNotFoundError
```bash
pip install -r requirements.txt
# Rust модуль опционален. Его отсутствие — не ошибка.
```

### Ошибка: Rust toolchain not found (при maturin develop)
```bash
# Установить Rust:
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
# Или пропустить — бот работает с Python fallback
```

### Ошибка: Database connection failed
Для SQLite (по умолчанию) — ошибок не бывает. Бот создаёт БД автоматически.

---

## Telegram Bot (v14.9)

### Кнопки не работают / игнорируются
**Проверьте:**
1. `ADMIN_IDS` в Config (не `ADMIN_ID` — множественное число)
2. Telegram bot token жив (@BotFather → /mybots)
3. Нет другого процесса, запущенного с тем же токеном

### Ошибка: entity offset X beyond message length (MarkdownV2)
**Исправлено в v14.4**: все сообщения экранируются через `escape_md()`.

### Кнопка TEST зависает / FSM не завершается
**Исправлено в v14.4**: `cmd_test` разделена на две: команда и кнопка.
После нажатия TEST — отправьте title предмета. CANCEL = выход.

### Команда ANALYZE не отвечает
**Исправлено в v14.4**: добавлен `await` перед `analyze_recent_trades()`.

### Команда SELL-TOP не продаёт
**Исправлено в v14.4**: `sell_inventory_items()` возвращает `list[int]`, сравнение фиксировано.

### /start не работает (Markdown parse error)
**Исправлено в v14.4**: все специальные символы экранируются.

### Ошибка: got an unexpected keyword argument 'title'
При отправке цены/статуса. Проверьте, что кнопка отправляет правильный формат.

---

## DMarket API

### Ошибка: 401 Unauthorized
**Причины:**
1. Истёкшие API ключи
2. Clock drift >120 секунд (авто-синхронизация через ClockSync)
3. Rust подпись не совпадает с Python fallback

**Решение:**
```bash
# Проверьте ключи в .env
# Перегенерируйте в https://dmarket.com/account/api-settings
```

### Ошибка: 429 Rate Limit
**Решение:** Circuit breaker делает exponential backoff (30s → 60s → 120s → 300s). Ждите.

### Ошибка: RetryError / CANCEL_PANIC_OFFER_FAILED
**Сценарий:** Ошибка при отмене ордера через PANIC.
**Не критично.** Транзиторная ошибка DMarket API. Повторите PANIC через цикл.

### Ошибка: RefreshTokenRequiredError / offers v1 migrated to v2
**Решение:** Обновите API ключи. Все эндпоинты на v2.

---

## База данных и миграции

v14.4 использует **Dual SQLite** (state.db + history.db). Создаются автоматически.

### Нет таблиц / пустая БД
Бот создаёт таблицы при первом запуске. Проверьте права на `data/`:
```bash
chmod 600 data/*.db
```

### SQLite database is locked
**Решение:** Исправлено в v14.4 — WAL mode включён для параллельного доступа.

---

## v14.9 Balance-Aware специфичные ошибки

### Бот не покупает — "Drawdown freeze active"
**Причина:** Баланс упал более чем на 15% от пика.
**Решение:** Бот продолжит только продавать. Когда баланс восстановится — покупки возобновятся автоматически.

### Бот не покупает — "Capital velocity too low"
**Причина:** Менее 0.5× оборота капитала в неделю.
**Решение:** Продайте замороженные предметы вручную или подождите естественного оборота.

### Бот не покупает — "Lock-aware cap reached"
**Причина:** Более 80% капитала в trade-lock.
**Решение:** Дождитесь разморозки предметов (7 дней). Уменьшите `LOCK_AWARE_LIQUID_FRACTION`.

### Бот не покупает — "Price exceeds dynamic max"
**Причина:** Цена предмета выше `max($5.00, balance × 10%)`.
**Решение:** Пополните баланс или уменьшите `MAX_SNIPING_PRICE_FLOOR`.

### "Half Kelly: no trade history, using MAX_POSITION_RISK_PCT"
**Причина:** Нет завершённых сделок для расчёта win rate.
**Решение:** После первых 3-5 сделок бот автоматически перейдёт на Kelly sizing.

### Sandbox: "Affordable: X | Missed: Y"
Это нормальный вывод симуляции. Missed — предметы, которые бот мог бы купить при большем балансе.

---

## Rust модуль

### Rust module not found
```bash
cd src/rust_core && maturin develop --release
```
Или просто используйте Python fallback (не требует Rust).

### Rust parse error (aggregated-prices)
```
WARNING: Rust Aggregated Prices parser failed, falling back to Python
```
Не критично. Python работает корректно.

### dmarket_parser_rs ImportError
**Причина:** `.so` файл не собран под вашу архитектуру.
**Решение:** `maturin develop --release` соберёт под текущую платформу.

---

## Исправленные баги (v14.9 changelog)

### Docker
- Новый multi-stage Dockerfile (убрал 432 MB Rust target/ из финального образа)
- Non-root user (uid 1000), tini init, healthcheck
- docker-compose с persistent volumes и memory limits

### Telegram
- `_ADMIN_ID` → `_ADMIN_IDS` (множественное число)
- `CrossMarketOracle` → `MultiSourceOracle` (dead import)
- MarkdownV2 escaping для всех сообщений
- `sqlite3.Row.get()` → `_row_bool()` helper
- `await analyze_recent_trades()` (был пропущенный await)
- `sell_inventory_items()` list → int сравнение
- `cmd_test` split into command + button (FSM fix)

### Core
- Volume-tier fix: title_volume lookup получает реальные данные
- Таблицы SQLite создаются при первом запуске
- Lock-файл защищён SHA-256 хешем

---

## 📚 Полезные ссылки

- [ARCHITECTURE.md](ARCHITECTURE.md) — архитектура v14.9
- [QUICK_START.md](QUICK_START.md) — быстрый старт
- [deployment.md](deployment.md) — Docker + bare metal deployment
- [DMarket API](https://docs.dmarket.com/)
- [Telegram Bot API](https://core.telegram.org/bots/api)


**Версия:** 14.9  
**Создано:** Июнь 2026  


🦅 *DMarket Quantitative Engine | v14.9 | June 2026*
