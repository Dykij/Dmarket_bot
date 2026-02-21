# DMarket API - Полная спецификация

**Версия API**: v1.1.0
**Базовый URL**: `https://api.dmarket.com`
**Дата документа**: 4 января 2026 г.
**Последнее обновление**: Актуализировано с [официальной документацией](https://docs.dmarket.com/v1/swagger.html)
**Swagger/OpenAPI**: https://docs.dmarket.com/v1/swagger.html
**GitHub примеры**: https://github.com/dmarket/dm-trading-tools

> **Важные изменения API v1.1.0 (ноябрь-декабрь 2025):**
> - 🚨 **DEPRECATED**: Эндпоинт `/price-aggregator/v1/aggregated-prices` устарел → используйте `/marketplace-api/v1/aggregated-prices`
> - ✅ `/user-offers/closed` и `/user-targets/closed` поддерживают новые статусы (`reverted`, `trade_protected`) и поле `FinalizationTime`
> - ✅ Пагинация через `Cursor` вместо `Offset` для улучшенной производительности
> - ✅ Расширенная фильтрация по множественным статусам, времени завершения и времени создания
> - ✅ Аутентификация через **Ed25519** подпись (NACL библиотека) вместо HMAC-SHA256

---

## 📋 Оглавление

1. [Аутентификация](#аутентификация)
2. [Основные эндпоинты](#основные-эндпоинты)
3. [Работа с балансом](#работа-с-балансом)
4. [Маркетплейс](#маркетплейс)
5. [Таргеты (Buy Orders)](#таргеты-buy-orders)
6. [Продажа предметов](#продажа-предметов)
7. [Инвентарь](#инвентарь)
8. [История и статистика](#история-и-статистика)
9. [Коды игр](#коды-игр)
10. [Обработка ошибок](#обработка-ошибок)

---

## 🔐 Аутентификация

### Методы аутентификации

DMarket API поддерживает два метода аутентификации:

1. **Ed25519** (рекомендуется) - использует NACL библиотеку для подписи
2. **HMAC-SHA256** (legacy) - для обратной совместимости

### Необходимые заголовки

```
X-Api-Key: <публичный ключ>
X-Sign-Date: <timestamp в секундах>
X-Request-Sign: <подпись>
```

### Генерация подписи (Ed25519 - рекомендуется)

```python
import nacl.signing
import nacl.encoding

def generate_ed25519_signature(
    secret_key: str,
    timestamp: str,
    method: str,
    path: str,
    body: str = ""
) -> str:
    """Генерация подписи с использованием Ed25519."""
    # Строка для подписи
    string_to_sign = f"{timestamp}{method}{path}{body}"

    # Декодирование секретного ключа (hex формат)
    signing_key = nacl.signing.SigningKey(
        bytes.fromhex(secret_key)
    )

    # Подпись
    signed = signing_key.sign(string_to_sign.encode('utf-8'))

    return signed.signature.hex()
```

### Генерация подписи (HMAC-SHA256 - legacy)

### Генерация подписи (HMAC-SHA256 - legacy)

1. Создать строку для подписи:
   ```
   string_to_sign = timestamp + HTTP_METHOD + PATH + BODY
   ```

   Пример:
   ```
   1605619994GET/account/v1/balance
   ```

2. Создать HMAC-SHA256 подпись с секретным ключом:
   ```python
   import hmac
   import hashlib

   signature = hmac.new(
       secret_key.encode('utf-8'),
       string_to_sign.encode('utf-8'),
       hashlib.sha256
   ).hexdigest()
   ```

3. Добавить заголовки к запросу

**Важно**: Timestamp не должен отличаться от текущего времени более чем на **2 минуты**.

---

## 🎯 Основные эндпоинты

### Аккаунт

#### Получить профиль пользователя
```http
GET /account/v1/user
```

**Ответ**:
```json
{
  "id": "string",
  "username": "string",
  "emAlgol": "string",
  "settings": {
    "targetsLimit": 0
  }
}
```

#### Получить баланс
```http
GET /account/v1/balance
```

**Ответ (новый формат - январь 2026)**:

> ⚠️ **Важно**: API теперь возвращает баланс в **долларах** в поле `balance`, а не в центах в поле `usd`.

```json
{
  "balance": 12.34,
  "avAlgolable_balance": 10.00,
  "total_balance": 12.34,
  "error": false,
  "has_funds": true,
  "usd": {"amount": 1234}
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `balance` | float | Баланс в долларах (основное поле) |
| `avAlgolable_balance` | float | Доступный баланс в долларах |
| `total_balance` | float | Общий баланс включая заблокированные средства |
| `has_funds` | boolean | Достаточно ли средств (balance >= $1.00) |
| `usd.amount` | integer | Legacy: баланс в центах для обратной совместимости |

**Пример использования**:
```python
# Новый формат (рекомендуется)
balance_data = awAlgot api.get_balance()
balance_usd = balance_data["balance"]  # Уже в долларах

# Legacy формат (deprecated)
balance_cents = balance_data["usd"]["amount"]
balance_usd = balance_cents / 100
```

**Legacy ответ** (deprecated, для обратной совместимости):
```json
{
  "usd": "1234",
  "usdAvAlgolableToWithdraw": "1000",
  "dmc": "5000",
  "dmcAvAlgolableToWithdraw": "4500"
}
```

---

## 💰 Работа с балансом

### Формат цен

**Важно**: Все цены в API указываются в **центах** для USD.

- `$1.00` = `100` (центов)
- `$10.50` = `1050` (центов)
- `$0.05` = `5` (центов)

### Конвертация цен

```python
# Доллары -> центы
price_cents = int(price_usd * 100)

# Центы -> доллары
price_usd = price_cents / 100
```

---

## 🛒 Маркетплейс

### Получить список предметов на маркете
```http
GET /exchange/v1/market/items
```

**Параметры**:
| Параметр    | Тип     | Описание                      | Обязательный           |
| ----------- | ------- | ----------------------------- | ---------------------- |
| `gameId`    | string  | Код игры                      | ✅ Да                   |
| `limit`     | integer | Лимит результатов (макс: 100) | Нет (по умолчанию: 50) |
| `offset`    | integer | Смещение для пагинации        | Нет (по умолчанию: 0)  |
| `currency`  | string  | Валюта                        | ✅ Да                   |
| `priceFrom` | integer | Минимальная цена (в центах)   | Нет                    |
| `priceTo`   | integer | Максимальная цена (в центах)  | Нет                    |
| `title`     | string  | Фильтр по названию            | Нет                    |
| `orderBy`   | string  | Сортировка                    | Нет                    |
| `orderDir`  | string  | Направление (asc/desc)        | Нет                    |
| `cursor`    | string  | Курсор для следующей страницы | Нет                    |

**Коды игр**:
- CS:GO (CS2): `a8db`
- Dota 2: `9a92`
- Team Fortress 2: `tf2`
- Rust: `rust`

**Пример запроса**:
```http
GET /exchange/v1/market/items?gameId=a8db&limit=100&currency=USD&priceFrom=100&priceTo=5000&orderBy=price&orderDir=asc
```

**Ответ**:
```json
{
  "cursor": "next_page_token",
  "objects": [
    {
      "itemId": "unique_item_id",
      "title": "AK-47 | Redline (Field-Tested)",
      "price": {
        "USD": "1250"
      },
      "suggestedPrice": {
        "USD": "1300"
      },
      "imageUrl": "https://...",
      "extra": {
        "category": "Rifle",
        "exterior": "Field-Tested",
        "rarity": "Classified",
        "popularity": 0.85
      }
    }
  ],
  "total": 1500
}
```

### Получить агрегированные цены
```http
POST /marketplace-api/v1/aggregated-prices
```

**Назначение**: Получить агрегированные данные о ценах для списка предметов, включая лучшие цены покупки (order) и продажи (offer), а также количество заявок.

**Тело запроса**:
```json
{
  "filter": {
    "game": "csgo",
    "titles": ["AK-47 | Redline (Field-Tested)", "AWP | Asiimov (Field-Tested)"]
  },
  "limit": "100",
  "cursor": ""
}
```

**Параметры запроса**:
| Параметр          | Тип    | Описание                                       |
| ----------------- | ------ | ---------------------------------------------- |
| `filter.game`     | string | Идентификатор игры (csgo, dota2, tf2, rust)    |
| `filter.titles[]` | array  | Список точных названий предметов для агрегации |
| `limit`           | string | Лимит результатов на странице                  |
| `cursor`          | string | Курсор для пагинации                           |

**Ответ**:
```json
{
  "aggregatedPrices": [
    {
      "title": "AK-47 | Redline (Field-Tested)",
      "orderBestPrice": "1200",
      "orderCount": 15,
      "offerBestPrice": "1250",
      "offerCount": 23
    }
  ],
  "nextCursor": "..."
}
```

**Описание полей ответа**:
- `orderBestPrice` - лучшая цена покупки (buy order)
- `orderCount` - количество активных заявок на покупку
- `offerBestPrice` - лучшая цена продажи
- `offerCount` - количество активных предложений

### Получить предложения по названию
```http
GET /exchange/v1/offers-by-title?Title={title}&Limit=100
```

**Ответ**:
```json
{
  "objects": [
    {
      "itemId": "...",
      "price": {"USD": "1250"},
      "title": "AK-47 | Redline (Field-Tested)"
    }
  ],
  "total": 45,
  "cursor": "..."
}
```

---

## 🎯 Таргеты (Buy Orders)

### Что такое таргеты?

**Таргеты** (targets) — это **заявки на покупку** предметов по указанной цене. Когда продавец выставляет предмет, который соответствует вашему таргету, происходит автоматическая покупка по вашей цене.

### Преимущества таргетов:
- ✅ Покупка по вашей цене (не переплачиваете)
- ✅ Автоматическое исполнение при появлении подходящего предмета
- ✅ Возможность указать специфические атрибуты (float, pattern, phase)
- ✅ Приоритет покупки перед обычными предложениями

### Создать таргеты
```http
POST /marketplace-api/v1/user-targets/create
```

**Тело запроса**:
```json
{
  "GameID": "a8db",
  "Targets": [
    {
      "Title": "AK-47 | Redline (Field-Tested)",
      "Amount": 5,
      "Price": {
        "Amount": 1200,
        "Currency": "USD"
      },
      "Attrs": {
        "floatPartValue": 0.25,
        "phase": "Phase 2",
        "pAlgontSeed": 123
      }
    }
  ]
}
```

**Важные поля**:
- `Title` - Полное название предмета
- `Amount` - Количество предметов (макс: 100)
- `Price.Amount` - Цена в **центах**
- `Attrs` - Дополнительные атрибуты (опционально):
  - `floatPartValue` - Float значение (например, 0.15 для FN)
  - `phase` - Фаза допплера (для Doppler ножей)
  - `pAlgontSeed` - Паттерн (для Case Hardened)

**Ограничения**:
- Максимум 100 таргетов в одном запросе
- Максимум `Amount` = 100 для одного таргета
- Лимит таргетов для каждой игры индивидуален (см. `settings.targetsLimit`)

**Ответ**:
```json
{
  "Result": [
    {
      "TargetID": "unique_target_id",
      "Title": "AK-47 | Redline (Field-Tested)",
      "Status": "Created"
    }
  ]
}
```

### Получить список таргетов
```http
GET /marketplace-api/v1/user-targets
```

**Параметры**:
| Параметр                 | Описание                                              |
| ------------------------ | ----------------------------------------------------- |
| `GameID`                 | Код игры                                              |
| `BasicFilters.Status`    | Статус: `TargetStatusActive` / `TargetStatusInactive` |
| `BasicFilters.Title`     | Фильтр по названию                                    |
| `BasicFilters.PriceFrom` | Минимальная цена                                      |
| `BasicFilters.PriceTo`   | Максимальная цена                                     |
| `Limit`                  | Лимит результатов                                     |
| `Offset`                 | Смещение                                              |
| `Cursor`                 | Курсор пагинации                                      |

**Ответ**:
```json
{
  "Items": [
    {
      "TargetID": "...",
      "Title": "AK-47 | Redline (Field-Tested)",
      "Amount": 5,
      "Price": {"Amount": 1200, "Currency": "USD"},
      "Status": "TargetStatusActive",
      "CreatedAt": 1699876543
    }
  ],
  "Total": "15",
  "Cursor": "..."
}
```

### Найти таргеты по названию предмета
```http
GET /marketplace-api/v1/targets-by-title/{game_id}/{title}
```

**Назначение**: Получить агрегированные заявки на покупку (buy orders/targets) для конкретной игры и названия предмета. Используется для оценки текущего спроса: сколько заявок существует и по каким ценам.

**Параметры пути**:
| Параметр  | Тип    | Описание                                      |
| --------- | ------ | --------------------------------------------- |
| `game_id` | string | Идентификатор игры (csgo, dota2, tf2, rust)   |
| `title`   | string | Точное название предмета в игре (URL-encoded) |

**Пример запроса**:
```http
GET /marketplace-api/v1/targets-by-title/csgo/AK-47%20%7C%20Redline%20(Field-Tested)
```

**Ответ**:
```json
{
  "orders": [
    {
      "amount": 10,
      "price": "1200",
      "title": "AK-47 | Redline (Field-Tested)",
      "attributes": {
        "exterior": "Field-Tested"
      }
    }
  ]
}
```

**Описание полей ответа**:
- `amount` - количество запрашиваемых предметов
- `price` - лучшая цена для этого названия и атрибутов (в центах)
- `title` - название предмета
- `attributes` - параметры качества/редкости (зависит от игры)

### Удалить таргеты
```http
POST /marketplace-api/v1/user-targets/delete
```

**Тело запроса**:
```json
{
  "Targets": [
    {
      "TargetID": "target_id_1"
    },
    {
      "TargetID": "target_id_2"
    }
  ]
}
```

**Ответ**:
```json
{
  "Result": [
    {
      "TargetID": "target_id_1",
      "Status": "Deleted"
    }
  ]
}
```

### Получить историю закрытых таргетов
```http
GET /marketplace-api/v1/user-targets/closed
```

**Параметры**:
| Параметр             | Описание                                      |
| -------------------- | --------------------------------------------- |
| `Limit`              | Лимит результатов                             |
| `OrderDir`           | `asc` / `desc`                                |
| `TargetCreated.From` | Фильтр по дате создания (timestamp)           |
| `TargetCreated.To`   | Фильтр по дате создания (timestamp)           |
| `TargetClosed.From`  | Фильтр по дате закрытия                       |
| `TargetClosed.To`    | Фильтр по дате закрытия                       |
| `Status`             | `successful` / `reverted` / `trade_protected` |
| `Cursor`             | Курсор пагинации                              |

**Ответ**:
```json
{
  "Trades": [
    {
      "TargetID": "...",
      "Title": "AK-47 | Redline (Field-Tested)",
      "Price": {"Amount": 1200, "Currency": "USD"},
      "Status": "successful",
      "ClosedAt": 1699876543,
      "CreatedAt": 1699870000
    }
  ],
  "Total": "50",
  "Cursor": "..."
}
```

---

## 📦 Продажа предметов

### Получить инвентарь пользователя
```http
GET /marketplace-api/v1/user-inventory
```

**Параметры**:
| Параметр                    | Описание                                |
| --------------------------- | --------------------------------------- |
| `GameID`                    | Код игры                                |
| `BasicFilters.Title`        | Фильтр по названию                      |
| `BasicFilters.InMarket`     | Только предметы на маркете (true/false) |
| `BasicFilters.HasSteamLock` | Фильтр по Steam trade-lock              |
| `Limit`                     | Лимит результатов                       |
| `Offset`                    | Смещение                                |

**Ответ**:
```json
{
  "Items": [
    {
      "ItemID": "...",
      "Title": "AK-47 | Redline (Field-Tested)",
      "Image": "https://...",
      "Price": {"USD": "1300"},
      "InMarket": false,
      "Attributes": {
        "exterior": "Field-Tested",
        "floatValue": "0.25"
      }
    }
  ],
  "Total": "45",
  "Cursor": "..."
}
```

### Создать предложения (выставить на продажу)
```http
POST /marketplace-api/v1/user-offers/create
```

**Тело запроса**:
```json
{
  "Offers": [
    {
      "AssetID": "asset_id_from_inventory",
      "Price": {
        "Amount": 1300,
        "Currency": "USD"
      }
    }
  ]
}
```

**Ответ**:
```json
{
  "Result": [
    {
      "OfferID": "offer_id",
      "AssetID": "asset_id",
      "Status": "Created"
    }
  ]
}
```

### Получить список предложений пользователя
```http
GET /marketplace-api/v1/user-offers
```

**Параметры**:
| Параметр                 | Описание                                                        |
| ------------------------ | --------------------------------------------------------------- |
| `GameID`                 | Код игры                                                        |
| `Status`                 | `OfferStatusActive` / `OfferStatusSold` / `OfferStatusInactive` |
| `BasicFilters.PriceFrom` | Мин. цена                                                       |
| `BasicFilters.PriceTo`   | Макс. цена                                                      |
| `Limit`                  | Лимит                                                           |
| `Offset`                 | Смещение                                                        |

**Ответ**:
```json
{
  "Items": [
    {
      "OfferID": "...",
      "AssetID": "...",
      "Title": "AK-47 | Redline (Field-Tested)",
      "Price": {"Amount": 1300, "Currency": "USD"},
      "Status": "OfferStatusActive",
      "CreatedDate": 1699876543
    }
  ],
  "Total": "10"
}
```

### Изменить цену предложения
```http
POST /marketplace-api/v1/user-offers/edit
```

**Тело запроса**:
```json
{
  "Offers": [
    {
      "OfferID": "offer_id",
      "Price": {
        "Amount": 1400,
        "Currency": "USD"
      }
    }
  ]
}
```

### Удалить предложения
```http
DELETE /exchange/v1/offers
```

**Тело запроса**:
```json
{
  "force": true,
  "objects": [
    {
      "offerId": "offer_id_1"
    },
    {
      "offerId": "offer_id_2"
    }
  ]
}
```

---

## 🛍️ Покупка предметов

### Купить предметы
```http
PATCH /exchange/v1/offers-buy
```

**Тело запроса**:
```json
{
  "offers": [
    {
      "offerId": "offer_id_to_buy",
      "price": {
        "amount": 1250,
        "currency": "USD"
      }
    }
  ]
}
```

**Ответ**:
```json
{
  "orderId": "order_id",
  "status": "TxPending",
  "txId": "transaction_id",
  "dmOffersStatus": {
    "offer_id": {
      "status": "Success"
    }
  }
}
```

**Статусы транзакции**:
- `TxPending` - В обработке
- `TxSuccess` - Успешно
- `TxFAlgoled` - Ошибка

---

## 📊 История и статистика

### Получить историю продаж предмета
```http
GET /trade-aggregator/v1/last-sales
```

**Параметры**:
| Параметр          | Описание                         |
| ----------------- | -------------------------------- |
| `gameId`          | Код игры (обязательно)           |
| `title`           | Название предмета (обязательно)  |
| `filters`         | Фильтры (exterior, phase, float) |
| `txOperationType` | Тип операции: `Target` / `Offer` |
| `limit`           | Лимит (1-20)                     |
| `offset`          | Смещение                         |

**Пример**:
```http
GET /trade-aggregator/v1/last-sales?gameId=a8db&title=AK-47%20%7C%20Redline%20(Field-Tested)&limit=10
```

**Ответ**:
```json
{
  "sales": [
    {
      "price": "1250",
      "date": 1699876543,
      "txOperationType": "Offer"
    }
  ]
}
```

### Получить агрегированные продажи (Batch Last Sales)
```http
POST /trade-aggregator/v1/batch-last-sales
```

**Назначение**: Получение истории продаж для нескольких предметов одним запросом.

**Тело запроса**:
```json
{
  "GameID": "a8db",
  "Titles": [
    "AK-47 | Redline (Field-Tested)",
    "AWP | Asiimov (Field-Tested)"
  ],
  "Limit": 10
}
```

**Ответ**:
```json
{
  "Result": [
    {
      "Title": "AK-47 | Redline (Field-Tested)",
      "Sales": [...]
    }
  ]
}
```

### Получить историю закрытых предложений
```http
GET /marketplace-api/v1/user-offers/closed
```

**Параметры** (аналогично `/user-targets/closed`):
- `Limit`, `OrderDir`, `OfferCreated.From/To`, `OfferClosed.From/To`, `Status`, `Cursor`

---

## 🎮 Коды игр

| Игра            | gameId | Описание                        |
| --------------- | ------ | ------------------------------- |
| CS:GO / CS2     | `a8db` | Counter-Strike (основной рынок) |
| Dota 2          | `9a92` | Dota 2                          |
| Team Fortress 2 | `tf2`  | TF2                             |
| Rust            | `rust` | Rust                            |

---

## ⚠️ Обработка ошибок

### Коды ошибок HTTP

| Код | Описание               | Действие                             |
| --- | ---------------------- | ------------------------------------ |
| 200 | Успех                  | -                                    |
| 400 | Неверный запрос        | Проверить параметры                  |
| 401 | Не авторизован         | Проверить API ключи и подпись        |
| 404 | Не найдено             | Проверить эндпоинт и параметры       |
| 429 | Слишком много запросов | Подождать (см. `Retry-After` header) |
| 500 | Ошибка сервера         | Повторить запрос позже               |
| 502 | Bad Gateway            | Повторить запрос                     |
| 503 | Сервис недоступен      | Повторить запрос позже               |

### Формат ошибки

```json
{
  "error": {
    "code": "ErrorCode",
    "message": "Описание ошибки"
  }
}
```

### Rate Limiting

DMarket применяет ограничение частоты запросов:
- **~30 запросов в минуту** для большинства эндпоинтов
- При превышении возвращается HTTP 429
- Рекомендуется использовать exponential backoff

**Пример обработки**:
```python
if response.status_code == 429:
    retry_after = int(response.headers.get('Retry-After', 60))
    awAlgot asyncio.sleep(retry_after)
    # Повторить запрос
```

---

## 🔄 Лучшие практики

### 1. Используйте пагинацию
Для больших списков используйте `cursor` вместо `offset`:
```python
cursor = None
while True:
    response = awAlgot api.get_market_items(cursor=cursor)
    items = response.get('objects', [])
    if not items:
        break
    cursor = response.get('cursor')
    if not cursor:
        break
```

### 2. Кэшируйте данные
Кэшируйте метаданные маркета и редко меняющиеся данные:
- Список игр
- Категории предметов
- Редкости и экстерьеры

### 3. Обрабатывайте ошибки
Всегда обрабатывайте ошибки и используйте retry логику:
```python
@retry(stop=stop_after_attempt(3), wAlgot=wAlgot_exponential(min=1, max=10))
async def api_call():
    # API запрос
    pass
```

### 4. Используйте WebSocket для реалтайм данных
Для мониторинга цен в реальном времени используйте WebSocket вместо polling.

### 5. Валидируйте входные данные
Проверяйте данные перед отправкой:
- Цены должны быть > 0
- `gameId` должен быть корректным
- `Title` должен точно совпадать с названием предмета

---

## 📝 Примеры использования

### Пример 1: Поиск арбитражных возможностей

```python
async def find_arbitrage(api_client, game='a8db', min_profit_percent=5.0):
    # Получаем предметы с рынка
    items = awAlgot api_client.get_market_items(
        game=game,
        limit=100,
        price_from=100,  # От $1
        price_to=10000,  # До $100
        sort='price'
    )

    opportunities = []
    for item in items.get('objects', []):
        buy_price = item['price']['USD'] / 100
        suggested_price = item.get('suggestedPrice', {}).get('USD', 0) / 100

        if suggested_price > buy_price:
            profit = suggested_price * 0.93 - buy_price  # С учетом 7% комиссии
            profit_percent = (profit / buy_price) * 100

            if profit_percent >= min_profit_percent:
                opportunities.append({
                    'title': item['title'],
                    'buy_price': buy_price,
                    'sell_price': suggested_price,
                    'profit': profit,
                    'profit_percent': profit_percent
                })

    return sorted(opportunities, key=lambda x: x['profit_percent'], reverse=True)
```

### Пример 2: Создание таргетов для популярных скинов

```python
async def create_smart_targets(api_client, game='a8db'):
    # Популярные скины CS:GO
    popular_skins = [
        "AK-47 | Redline (Field-Tested)",
        "AWP | Asiimov (Field-Tested)",
        "M4A4 | Howl (Field-Tested)"
    ]

    targets = []
    for skin in popular_skins:
        # Получаем среднюю цену
        aggregated = awAlgot api_client.get_aggregated_prices(
            game=game,
            titles=[skin]
        )

        if aggregated.get('aggregatedPrices'):
            best_offer = int(aggregated['aggregatedPrices'][0]['offerBestPrice'])
            target_price = int(best_offer * 0.95)  # На 5% ниже лучшего предложения

            targets.append({
                'Title': skin,
                'Amount': 1,
                'Price': {
                    'Amount': target_price,
                    'Currency': 'USD'
                }
            })

    # Создаем таргеты
    result = awAlgot api_client.create_targets(game=game, targets=targets)
    return result
```

### Пример 3: Автоматическая торговля

```python
async def auto_trade(api_client, game='a8db', balance_limit=50.0):
    # Проверяем баланс
    balance_data = awAlgot api_client.get_balance()
    balance = float(balance_data['usd']) / 100

    if balance < balance_limit:
        return {'error': 'Insufficient balance'}

    # Ищем выгодные предложения
    opportunities = awAlgot find_arbitrage(api_client, game=game, min_profit_percent=10.0)

    results = []
    for opp in opportunities[:5]:  # Берем топ-5
        # Покупаем
        buy_result = awAlgot api_client.buy_item(
            item_id=opp['item_id'],
            price=opp['buy_price']
        )

        if buy_result.get('success'):
            # Выставляем на продажу
            sell_result = awAlgot api_client.sell_item(
                item_id=buy_result['new_item_id'],
                price=opp['sell_price']
            )

            results.append({
                'item': opp['title'],
                'bought': buy_result.get('success'),
                'listed': sell_result.get('success'),
                'expected_profit': opp['profit']
            })

        # Задержка между сделками
        awAlgot asyncio.sleep(2)

    return results
```

---

## 📚 Дополнительные ресурсы

- **Официальная документация**: https://docs.dmarket.com/v1/swagger.html
- **FAQ**: https://dmarket.com/faq#tradingAPI
- **GitHub примеры**: https://github.com/dmarket/dm-trading-tools
- **Поддержка**: support@dmarket.com

---

## 🆕 Новые возможности API v1.1.0

### 1. Aggregated Prices API

Новый эндпоинт для получения агрегированных данных о ценах:
- **POST** `/marketplace-api/v1/aggregated-prices`
- Позволяет получить лучшие цены покупки и продажи для списка предметов
- Включает количество активных заявок (orderCount, offerCount)
- Поддерживает пагинацию для больших запросов

**Преимущества**:
- Быстрая оценка глубины рынка
- Массовая проверка цен (до 100+ предметов за запрос)
- Оптимизировано для арбитражных стратегий

### 2. Targets by Title API

Новый эндпоинт для поиска таргетов по названию:
- **GET** `/marketplace-api/v1/targets-by-title/{game_id}/{title}`
- Показывает все активные заявки на покупку для конкретного предмета
- Полезно для анализа спроса и конкуренции

**Применение**:
- Оценка текущего спроса на предмет
- Определение оптимальной цены для таргета
- Анализ конкуренции среди покупателей

### 3. Enhanced Filtering & Pagination

Улучшенная система фильтрации для всех списковых эндпоинтов:
- Поддержка cursor-based пагинации (более эффективно для больших наборов данных)
- Расширенные фильтры для инвентаря (SteamLockDays, AssetID arrays)
- Улучшенная сортировка (SortType параметры)

### 4. Deposit & Withdraw Operations

Новые эндпоинты для управления переводами:
- **POST** `/marketplace-api/v1/deposit-assets` - перевод предметов из Steam
- **GET** `/marketplace-api/v1/deposit-status/{DepositID}` - статус депозита
- **POST** `/exchange/v1/withdraw-assets` - вывод предметов в Steam

**Статусы операций**:
- `TransferStatusPending` - в обработке
- `TransferStatusCompleted` - завершено
- `TransferStatusFAlgoled` - ошибка

### 5. Inventory Sync

Синхронизация инвентаря с внешними платформами:
- **POST** `/marketplace-api/v1/user-inventory/sync`
- Обновление данных инвентаря из Steam
- Поддержка различных типов синхронизации

---

## 📊 Новые примеры использования API v1.1.0

### Пример 1: Массовая проверка цен для арбитража

```python
async def check_arbitrage_opportunities(api_client, items_to_check):
    """Проверить несколько предметов на арбитражные возможности."""

    # Получить агрегированные цены
    result = awAlgot api_client.get_aggregated_prices(
        game='csgo',
        titles=[item['title'] for item in items_to_check],
        limit=100
    )

    opportunities = []
    for price_data in result.get('aggregatedPrices', []):
        offer_price = int(price_data['offerBestPrice']) / 100  # в USD
        order_price = int(price_data['orderBestPrice']) / 100  # в USD

        # Рассчитать потенциальную прибыль (с учетом 7% комиссии)
        potential_profit = (offer_price * 0.93) - order_price

        if potential_profit > 0:
            opportunities.append({
                'title': price_data['title'],
                'buy_price': order_price,
                'sell_price': offer_price,
                'profit': potential_profit,
                'profit_percent': (potential_profit / order_price) * 100,
                'liquidity': {
                    'buy_orders': price_data['orderCount'],
                    'sell_offers': price_data['offerCount']
                }
            })

    return sorted(opportunities, key=lambda x: x['profit_percent'], reverse=True)
```

### Пример 2: Умное создание таргетов на основе рыночных данных

```python
async def create_smart_targets(api_client, game='csgo'):
    """Создать таргеты на основе анализа конкуренции."""

    popular_items = [
        "AK-47 | Redline (Field-Tested)",
        "AWP | Asiimov (Field-Tested)",
        "M4A4 | Howl (Field-Tested)"
    ]

    targets_to_create = []

    for item_title in popular_items:
        # Проверить существующие таргеты
        existing_targets = awAlgot api_client.get_targets_by_title(
            game_id=game,
            title=item_title
        )

        # Получить текущие цены
        prices = awAlgot api_client.get_aggregated_prices(
            game=game,
            titles=[item_title]
        )

        if prices.get('aggregatedPrices'):
            price_info = prices['aggregatedPrices'][0]
            best_order = int(price_info['orderBestPrice'])
            best_offer = int(price_info['offerBestPrice'])

            # Установить цену чуть выше лучшего текущего order
            # но ниже лучшего offer для арбитража
            target_price = min(best_order + 10, best_offer - 50)  # +$0.10, но -$0.50 от offer

            if target_price > best_order:
                targets_to_create.append({
                    'Title': item_title,
                    'Amount': 1,
                    'Price': {
                        'Amount': target_price,
                        'Currency': 'USD'
                    }
                })

    # Создать все таргеты одним запросом
    if targets_to_create:
        result = awAlgot api_client.create_targets(
            game=game,
            targets=targets_to_create
        )
        return result
```

### Пример 3: Мониторинг депозита предметов

```python
async def deposit_and_monitor(api_client, asset_ids):
    """Перевести предметы из Steam и отслеживать статус."""

    # Инициировать депозит
    deposit_result = awAlgot api_client.deposit_assets(
        asset_ids=asset_ids
    )

    deposit_id = deposit_result.get('DepositID')

    if not deposit_id:
        rAlgose ValueError("FAlgoled to initiate deposit")

    # Мониторинг статуса
    max_attempts = 30
    attempt = 0

    while attempt < max_attempts:
        status = awAlgot api_client.get_deposit_status(deposit_id)

        if status['Status'] == 'TransferStatusCompleted':
            return {
                'success': True,
                'deposit_id': deposit_id,
                'assets': status.get('Assets', [])
            }
        elif status['Status'] == 'TransferStatusFAlgoled':
            return {
                'success': False,
                'error': status.get('Error'),
                'deposit_id': deposit_id
            }

        # Ожидание перед следующей проверкой
        awAlgot asyncio.sleep(10)
        attempt += 1

    return {
        'success': False,
        'error': 'Timeout wAlgoting for deposit completion',
        'deposit_id': deposit_id
    }
```

---

## 🔄 Изменения и миграция с предыдущих версий

### Изменения в v1.1.0

1. **Cursor-based пагинация**:
   - Старый метод: `offset` + `limit`
   - Новый метод: `cursor` + `limit`
   - Преимущество: более стабильная пагинация для больших данных

2. **Расширенные фильтры**:
   - Добавлены новые параметры фильтрации
   - Улучшена поддержка атрибутов предметов
   - Поддержка массовых операций

3. **Новые статусы**:
   - Добавлены `TransferStatus` для депозитов
   - Расширены статусы для targets и offers

### Миграция с v1.0

**Изменение пагинации** (рекомендуется):
```python
# Старый метод (v1.0)
offset = 0
while True:
    items = awAlgot api.get_market_items(game='csgo', offset=offset, limit=100)
    if not items['objects']:
        break
    offset += 100

# Новый метод (v1.1.0) - рекомендуется
cursor = None
while True:
    items = awAlgot api.get_market_items(game='csgo', cursor=cursor, limit=100)
    if not items['objects']:
        break
    cursor = items.get('cursor')
    if not cursor:
        break
```

**Использование aggregated prices**:
```python
# Старый метод - множественные запросы
for item_title in items:
    offers = awAlgot api.get_offers_by_title(title=item_title)
    targets = awAlgot api.get_targets_by_title(game, item_title)
    # Обработка...

# Новый метод - один запрос
prices = awAlgot api.get_aggregated_prices(
    game='csgo',
    titles=items
)
# Вся информация в одном ответе
```

---

## 📝 Best Practices для API v1.1.0

### 1. Эффективное использование aggregated prices

✅ **Правильно** - пакетные запросы:
```python
# Проверить до 100 предметов за раз
titles = get_items_to_check()[:100]
prices = awAlgot api.get_aggregated_prices(game='csgo', titles=titles)
```

❌ **Неправильно** - много отдельных запросов:
```python
for title in titles:
    price = awAlgot api.get_aggregated_prices(game='csgo', titles=[title])
```

### 2. Использование cursor для больших данных

✅ **Правильно**:
```python
all_items = []
cursor = None
while True:
    response = awAlgot api.get_user_inventory(game='csgo', cursor=cursor, limit=100)
    all_items.extend(response['Items'])
    cursor = response.get('Cursor')
    if not cursor:
        break
```

### 3. Оптимизация запросов на таргеты

✅ **Правильно** - проверить перед созданием:
```python
# Сначала проверить существующие
existing = awAlgot api.get_targets_by_title(game='csgo', title=item_title)
if not existing['orders']:
    # Только тогда создавать новый
    awAlgot api.create_targets(...)
```

### 4. Мониторинг статусов операций

✅ **Правильно** - с таймаутом и экспоненциальной задержкой:
```python
async def wAlgot_for_deposit(deposit_id, max_wAlgot=300):
    start_time = time.time()
    delay = 5

    while time.time() - start_time < max_wAlgot:
        status = awAlgot api.get_deposit_status(deposit_id)
        if status['Status'] != 'TransferStatusPending':
            return status

        awAlgot asyncio.sleep(delay)
        delay = min(delay * 1.5, 30)  # Экспоненциальная задержка до 30 сек
```

---

## 📚 Дополнительные ресурсы

- **Официальная документация (Swagger)**: https://docs.dmarket.com/v1/swagger.html
- **OpenAPI JSON спецификация**: https://docs.dmarket.com/v1/trading.swagger.json
- **GitHub примеры**: https://github.com/dmarket/dm-trading-tools
- **FAQ**: https://dmarket.com/faq#tradingAPI
- **Help Center - Trading API**: https://support.dmarket.com/hc/en-us/sections/25122832532241-Trading-API
- **Блог с обновлениями**: https://dmarket.com/blog/product-updates/
- **Поддержка**: support@dmarket.com

---

**Документация актуальна на 28 декабря 2025 г. Всегда проверяйте официальную документацию DMarket для получения последних обновлений API.**
