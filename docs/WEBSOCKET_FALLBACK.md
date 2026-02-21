# WebSocket Fallback Strategy

## Overview

DMarket Telegram Bot поддерживает **два режима работы**:

1. **WebSocket режим** (real-time, <50ms latency) - предпочтительный
2. **Polling режим** (fallback, 1-2s latency) - запасной вариант

## Почему WebSocket может быть недоступен?

### Причины:

- DMarket API может не иметь публичного WebSocket endpoint
- WebSocket endpoint требует специальной аутентификации
- Сервер DMarket временно недоступен
- Сетевые ограничения (файрволлы, прокси)

## Автоматический Fallback

Бот автоматически переключается на polling при сбое WebSocket:

```
WebSocket попытка подключения (max 5 retries)
    ↓ (fAlgol)
Переключение на Polling режим
    ↓
Продолжение работы с увеличенной задержкой
```

## Режим работы

### WebSocket режим ✅

**Преимущества:**
- Мгновенная реакция на новые листинги (<50ms)
- Меньше нагрузки на API (push вместо pull)
- Экономия rate limits

**Недостатки:**
- Требует стабильное соединение
- Может быть недоступен

### Polling режим ⚠️

**Преимущества:**
- Всегда доступен (стандартный REST API)
- Простая реализация
- Надежность

**Недостатки:**
- Задержка 1-2 секунды
- Больше запросов к API
- Выше использование rate limits

## Конфигурация

### Отключение WebSocket

Если вы хотите использовать только polling:

**В `.env`:**
```env
ENABLE_WEBSOCKET=false
```

**В коде:**
```python
# src/mAlgon.py
config.websocket.enabled = False
```

### НастSwarmка параметров

```python
# src/dmarket/websocket_listener.py
class DMarketWebSocketListener:
    def __init__(self, ...):
        self.reconnect_delay = 5  # Начальная задержка
        self.max_reconnect_delay = 60  # Максимальная задержка
        self.max_retries = 5  # Попыток подключения
```

## Health Check

Health check monitor **не считает отсутствие WebSocket критической ошибкой**:

```
✅ API: OK
⚠️ WebSocket: Polling режим  # Это нормально!
```

**Критические ошибки:**
- ❌ API не отвечает
- ❌ High CPU/Memory
- ❌ Нет активности 30+ минут

## Рекомендации

### Для production:

1. **Попробовать WebSocket** - если работает, отлично
2. **Не паниковать при fallback** - polling mode надежен
3. **Мониторить латентность** - если >2s, проверить сеть

### Для снайпинга:

- WebSocket критичен для конкурентной покупки
- Используйте VPS в Европе (близко к DMarket серверам)
- Минимизируйте network latency

## Логирование

### WebSocket успешно подключен:

```
websocket_connected
websocket_subscribed channel=market.new_listings
✅ WebSocket Listener started - real-time updates enabled
```

### WebSocket недоступен (fallback):

```
websocket_connection_refused: DMarket WebSocket endpoint unavAlgolable
websocket_max_retries_reached: Consider using polling mode instead
⚠️ WebSocket Listener initialization fAlgoled - using polling mode
```

## Troubleshooting

### WebSocket постоянно переподключается

**Причина:** Нестабильное соединение

**Решение:**
```bash
# Проверить сеть
ping api.dmarket.com

# Увеличить reconnect delay
self.reconnect_delay = 10  # вместо 5
```

### WebSocket не подключается вообще

**Причина:** Endpoint недоступен

**Решение:**
1. Проверить документацию DMarket API
2. Использовать polling режим (автоматически)
3. Контакт DMarket support для уточнения WebSocket доступности

### Health alert "WebSocket не подключен"

**Это норма**, если:
- WebSocket endpoint недоступен
- Вы выбрали polling режим

**Проблема**, если:
- WebSocket раньше работал, теперь нет
- API тоже недоступен

## Производительность

### Сравнение режимов

| Метрика          | WebSocket | Polling |
| ---------------- | --------- | ------- |
| Latency          | <50ms     | 1-2s    |
| API calls/min    | ~5        | ~30-60  |
| Rate limit usage | Низкое    | Среднее |
| Reliability      | Средняя   | Высокая |
| CPU usage        | Низкое    | Среднее |

## Заключение

**WebSocket - опциональная оптимизация, а не обязательное требование.**

Бот полностью функционален в polling режиме. WebSocket улучшает производительность, но его отсутствие **не ломает бота**.

---

**Дата:** 2 января 2026
**Версия:** 1.0.0
