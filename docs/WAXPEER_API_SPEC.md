# Waxpeer API Documentation

> Справочник по Waxpeer API для интеграции с DMarket Telegram Bot.
> Версия: 1.0 | Обновлено: 4 января 2026

## 📋 Содержание

1. [Обзор](#обзор)
2. [Аутентификация](#аутентификация)
3. [Базовый URL](#базовый-url)
4. [Endpoints](#endpoints)
5. [Модели данных](#модели-данных)
6. [Примеры использования](#примеры-использования)
7. [Rate Limits](#rate-limits)
8. [Коды ошибок](#коды-ошибок)

---

## Обзор

Waxpeer — это P2P маркетплейс для торговли скинами CS2 (CS:GO), Dota 2, TF2 и Rust. API позволяет:

- 📦 Выставлять предметы на продажу
- 💰 Получать баланс и историю сделок
- 📊 Получать рыночные цены для арбитража
- 🔄 Автоматический репрайсинг
- 📈 Анализ ликвидности

### Поддерживаемые игры

| Игра      | ID             | Статус    |
| --------- | -------------- | --------- |
| CS2/CS:GO | `csgo` / `cs2` | ✅ Активно |
| Dota 2    | `dota2`        | ✅ Активно |
| TF2       | `tf2`          | ✅ Активно |
| Rust      | `rust`         | ✅ Активно |

---

## Аутентификация

Все запросы требуют API ключ, передаваемый через query параметр `api`.

```
GET https://api.waxpeer.com/v1/user?api=YOUR_API_KEY
```

### Получение API ключа

1. Зайдите на [waxpeer.com/settings](https://waxpeer.com/settings)
2. Перейдите в раздел API
3. Сгенерируйте новый ключ
4. Сохраните ключ в `.env` файл

```env
WAXPEER_API_KEY=your_api_key_here
WAXPEER_ENABLED=true
```

⚠️ **Важно**: API ключ дает полный доступ к аккаунту. Держите его в секрете!

---

## Базовый URL

```
https://api.waxpeer.com/v1
```

Все endpoints ниже относительны к этому URL.

---

## Endpoints

### Пользователь и Баланс

#### `GET /user`

Получение информации о пользователе и баланса.

**Параметры:**
| Параметр | Тип    | Обязательный | Описание |
| -------- | ------ | ------------ | -------- |
| `api`    | string | ✅            | API ключ |

**Ответ:**
```json
{
  "success": true,
  "user": {
    "id": "76561198012345678",
    "name": "Username",
    "avatar": "https://...",
    "wallet": 15000,
    "can_trade": true,
    "tradelink": "https://steamcommunity.com/tradeoffer/new/?partner=..."
  }
}
```

**Примечания:**
- `wallet` — баланс в **милах** (1 доллар = 1000 мил)
- `can_trade` — готов ли пользователь к торговле
- Для конвертации: `wallet / 1000 = USD`

---

### Рыночные данные

#### `GET /get-items-list`

Получение списка предметов с ценами.

**Параметры:**
| Параметр    | Тип    | Обязательный | Описание                                 |
| ----------- | ------ | ------------ | ---------------------------------------- |
| `api`       | string | ✅            | API ключ                                 |
| `names`     | string | ❌            | Названия предметов через запятую         |
| `game`      | string | ❌            | Игра (`csgo`, `dota2`, `tf2`, `rust`)    |
| `sort`      | string | ❌            | Сортировка (`price`, `name`, `discount`) |
| `order`     | string | ❌            | Порядок (`asc`, `desc`)                  |
| `min_price` | int    | ❌            | Мин. цена в милах                        |
| `max_price` | int    | ❌            | Макс. цена в милах                       |
| `skip`      | int    | ❌            | Пропустить N записей                     |
| `limit`     | int    | ❌            | Максимум записей (макс. 100)             |

**Ответ:**
```json
{
  "success": true,
  "items": [
    {
      "name": "AK-47 | Redline (Field-Tested)",
      "price": 12500,
      "count": 156,
      "steam_price": 14200,
      "avg_price": 13000,
      "min_price": 11500
    }
  ]
}
```

**Примечания:**
- `price` — минимальная цена на Waxpeer (в милах)
- `count` — количество предметов в продаже (индикатор ликвидности)
- `steam_price` — цена в Steam Market (в милах)
- Для арбитража важен параметр `count` >= 5

---

#### `GET /prices`

Массовое получение цен (до 500 предметов).

**Параметры:**
| Параметр | Тип    | Обязательный | Описание                   |
| -------- | ------ | ------------ | -------------------------- |
| `api`    | string | ✅            | API ключ                   |
| `game`   | string | ❌            | Игра (по умолчанию `csgo`) |

**Ответ:**
```json
{
  "success": true,
  "items": {
    "AK-47 | Redline (Field-Tested)": {
      "price": 12500,
      "count": 156
    },
    "AWP | Asiimov (Field-Tested)": {
      "price": 28000,
      "count": 89
    }
  }
}
```

---

### Мои предметы

#### `GET /my-items`

Получение своих выставленных предметов.

**Параметры:**
| Параметр | Тип    | Обязательный | Описание             |
| -------- | ------ | ------------ | -------------------- |
| `api`    | string | ✅            | API ключ             |
| `skip`   | int    | ❌            | Пропустить N записей |
| `limit`  | int    | ❌            | Максимум записей     |

**Ответ:**
```json
{
  "success": true,
  "items": [
    {
      "item_id": "12345678901",
      "name": "AK-47 | Redline (Field-Tested)",
      "price": 12500,
      "steam_price": 14200,
      "float": 0.2534,
      "status": "active",
      "listed_at": "2026-01-04T10:00:00Z"
    }
  ]
}
```

---

### Листинг предметов

#### `POST /list-items-steam`

Выставление предметов на продажу.

**Тело запроса:**
```json
{
  "items": [
    {
      "item_id": "12345678901",
      "price": 12500
    }
  ]
}
```

**Параметры item:**
| Поле      | Тип    | Обязательный | Описание                  |
| --------- | ------ | ------------ | ------------------------- |
| `item_id` | string | ✅            | Asset ID предмета в Steam |
| `price`   | int    | ✅            | Цена в милах              |

**Ответ:**
```json
{
  "success": true,
  "listed": 1,
  "fAlgoled": 0
}
```

---

#### `POST /edit-items`

Изменение цены выставленных предметов.

**Тело запроса:**
```json
{
  "items": [
    {
      "item_id": "12345678901",
      "price": 11500
    }
  ]
}
```

**Ответ:**
```json
{
  "success": true,
  "updated": 1
}
```

---

#### `POST /remove-items`

Снятие предметов с продажи.

**Тело запроса:**
```json
{
  "items": ["12345678901", "12345678902"]
}
```

**Ответ:**
```json
{
  "success": true,
  "removed": 2
}
```

---

#### `POST /remove-all`

Снятие всех предметов с продажи.

**Ответ:**
```json
{
  "success": true,
  "removed": 15
}
```

---

### История торговли

#### `GET /history`

Получение истории сделок.

**Параметры:**
| Параметр  | Тип    | Обязательный | Описание                            |
| --------- | ------ | ------------ | ----------------------------------- |
| `api`     | string | ✅            | API ключ                            |
| `skip`    | int    | ❌            | Пропустить N записей                |
| `limit`   | int    | ❌            | Максимум записей (по умолчанию 100) |
| `partner` | string | ❌            | Steam ID партнера                   |

**Ответ:**
```json
{
  "success": true,
  "history": [
    {
      "id": "abc123",
      "item_id": "12345678901",
      "name": "AK-47 | Redline (Field-Tested)",
      "price": 12500,
      "fee": 750,
      "status": "sold",
      "sold_at": "2026-01-04T12:00:00Z",
      "buyer": "76561198012345678"
    }
  ]
}
```

**Статусы:**
- `sold` — продано
- `cancelled` — отменено
- `pending` — ожидает

---

### Steam инвентарь

#### `GET /get-my-inventory`

Получение инвентаря Steam для листинга.

**Параметры:**
| Параметр | Тип    | Обязательный | Описание                   |
| -------- | ------ | ------------ | -------------------------- |
| `api`    | string | ✅            | API ключ                   |
| `game`   | string | ❌            | Игра (по умолчанию `csgo`) |
| `skip`   | int    | ❌            | Пропустить                 |
| `limit`  | int    | ❌            | Лимит                      |

**Ответ:**
```json
{
  "success": true,
  "items": [
    {
      "item_id": "12345678901",
      "name": "AK-47 | Redline (Field-Tested)",
      "market_name": "AK-47 | Redline (Field-Tested)",
      "tradable": true,
      "steam_price": 14200
    }
  ]
}
```

---

### Trades (P2P)

#### `GET /check-tradelink`

Проверка валидности Trade Link.

**Параметры:**
| Параметр    | Тип    | Обязательный | Описание                |
| ----------- | ------ | ------------ | ----------------------- |
| `api`       | string | ✅            | API ключ                |
| `tradelink` | string | ✅            | Trade Link для проверки |

**Ответ:**
```json
{
  "success": true,
  "valid": true,
  "steam_id": "76561198012345678"
}
```

---

## Модели данных

### Цены

Все цены в Waxpeer API указаны в **милах** (mils):

| Значение | Милы  | USD   |
| -------- | ----- | ----- |
| $1.00    | 1000  | 1.00  |
| $10.50   | 10500 | 10.50 |
| $0.05    | 50    | 0.05  |

**Конвертация:**
```python
# Милы в доллары
usd = mils / 1000

# Доллары в милы
mils = int(usd * 1000)
```

### Комиссии

| Операция | Комиссия    |
| -------- | ----------- |
| Продажа  | **6%**      |
| Покупка  | 0%          |
| Вывод    | Варьируется |

**Расчет чистой прибыли:**
```python
# Формула: (Цена_продажи * 0.94) - Цена_покупки
net_profit = (sell_price * 0.94) - buy_price
```

---

## Примеры использования

### Python (httpx)

```python
import httpx

API_KEY = "your_api_key"
BASE_URL = "https://api.waxpeer.com/v1"

async def get_balance():
    async with httpx.AsyncClient() as client:
        response = awAlgot client.get(
            f"{BASE_URL}/user",
            params={"api": API_KEY}
        )
        data = response.json()
        wallet_mils = data["user"]["wallet"]
        return wallet_mils / 1000  # В долларах

async def get_item_price(item_name: str):
    async with httpx.AsyncClient() as client:
        response = awAlgot client.get(
            f"{BASE_URL}/get-items-list",
            params={
                "api": API_KEY,
                "names": item_name
            }
        )
        data = response.json()
        if data["success"] and data["items"]:
            return data["items"][0]["price"] / 1000
        return None

async def list_item(item_id: str, price_usd: float):
    price_mils = int(price_usd * 1000)
    async with httpx.AsyncClient() as client:
        response = awAlgot client.post(
            f"{BASE_URL}/list-items-steam",
            params={"api": API_KEY},
            json={
                "items": [{"item_id": item_id, "price": price_mils}]
            }
        )
        return response.json()
```

### Cross-Platform Arbitrage

```python
from decimal import Decimal

WAXPEER_COMMISSION = Decimal("0.06")  # 6%

async def check_arbitrage(dmarket_price: Decimal, item_name: str):
    """Проверка арбитражной возможности DMarket -> Waxpeer."""

    # Получаем цену на Waxpeer
    waxpeer_price = awAlgot get_item_price(item_name)

    if not waxpeer_price:
        return None

    waxpeer_price = Decimal(str(waxpeer_price))

    # Расчет чистой прибыли
    # (Цена Waxpeer * 0.94) - Цена DMarket
    net_profit = (waxpeer_price * Decimal("0.94")) - dmarket_price

    # ROI
    roi = (net_profit / dmarket_price) * 100

    return {
        "dmarket_price": dmarket_price,
        "waxpeer_price": waxpeer_price,
        "net_profit": net_profit,
        "roi_percent": roi,
        "profitable": net_profit > Decimal("0.30")  # Мин. 30 центов
    }
```

---

## Rate Limits

| Endpoint            | Лимит | Период |
| ------------------- | ----- | ------ |
| `/user`             | 60    | минута |
| `/get-items-list`   | 30    | минута |
| `/prices`           | 10    | минута |
| `/list-items-steam` | 20    | минута |
| `/history`          | 30    | минута |

**Рекомендации:**
- Кэшируйте результаты `/prices` на 1-5 минут
- Используйте batch запросы вместо индивидуальных
- Добавляйте задержку 2-3 секунды между запросами

---

## Коды ошибок

| Код | Сообщение               | Описание                |
| --- | ----------------------- | ----------------------- |
| 400 | `Bad Request`           | Неверные параметры      |
| 401 | `Invalid API key`       | Неверный API ключ       |
| 403 | `Access denied`         | Доступ запрещен         |
| 429 | `Rate limit exceeded`   | Превышен лимит запросов |
| 500 | `Internal server error` | Ошибка сервера          |

**Обработка ошибок:**
```python
try:
    data = awAlgot waxpeer_api.get_user()
except WaxpeerRateLimitError:
    awAlgot asyncio.sleep(60)  # Подождать минуту
except WaxpeerAuthError:
    logger.error("Invalid API key")
except WaxpeerAPIError as e:
    logger.error(f"API error: {e}")
```

---

## Интеграция с ботом

### Конфигурация (.env)

```env
# Waxpeer P2P Integration
WAXPEER_ENABLED=true
WAXPEER_API_KEY=your_api_key_here

# НастSwarmки наценок
WAXPEER_MARKUP=10       # Обычные скины (%)
WAXPEER_RARE_MARKUP=25  # Редкие скины (%)
WAXPEER_ULTRA_MARKUP=40 # JACKPOT скины (%)
WAXPEER_MIN_PROFIT=5    # Мин. прибыль (%)

# Авто-репрайсинг
WAXPEER_REPRICE=true
WAXPEER_REPRICE_INTERVAL=30  # Минуты

# Shadow Listing
WAXPEER_SHADOW=true
WAXPEER_SCARCITY=3      # Порог дефицита
```

### Использование в коде

```python
from src.waxpeer.waxpeer_api import WaxpeerAPI
from src.utils.config import Config

config = Config.load()

async with WaxpeerAPI(api_key=config.waxpeer.api_key) as api:
    # Получить баланс
    balance = awAlgot api.get_balance()
    print(f"Баланс: ${balance.wallet}")

    # Получить цены
    prices = awAlgot api.get_items_list(["AK-47 | Redline (Field-Tested)"])

    # Выставить предмет
    awAlgot api.list_single_item("12345", price_usd=10.50)
```

---

## См. также

- [DMarket API Spec](DMARKET_API_FULL_SPEC.md)
- [Cross-Platform Arbitrage](../src/dmarket/cross_platform_arbitrage.py)
- [Waxpeer API Client](../src/waxpeer/waxpeer_api.py)

---

*Документация создана на основе [docs.waxpeer.com](https://docs.waxpeer.com/) и анализа API.*
