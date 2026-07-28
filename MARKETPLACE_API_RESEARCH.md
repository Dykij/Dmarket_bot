# MARKETPLACE_API_RESEARCH.md — Анализ API аналогичных площадок
## Date: 2026-07-28 | Purpose: OBI signal enhancement potential

---

## Сводная таблица

| Площадка | API доступно | Bid/Ask Count | Volume | Цена | Rate Limit | Авторизация | Полезность для OBI |
|----------|-------------|---------------|--------|------|------------|-------------|-------------------|
| **DMarket** | ✅ Публичный | **ДА** | Нет | best_bid, best_ask | 10 RPS | API key | **ОСНОВНОЙ** |
| **Buff163** | ⚠️ Ограниченный | Нет | Да (продажи) | min_price, max_price | 10 req/min | Китайский номер | НИЗКАЯ |
| **Skinport** | ✅ Публичный | Нет | Да (продажи) | min_price, median_price | 60 req/min | API key | НИЗКАЯ |
| **Steam** | ⚠️ Неофициальный | Нет | Да (продажи) | lowest_price, median_price | ~20 req/min | Нет | НИЗКАЯ |
| **CSFloat** | ✅ Публичный | Нет | Нет | price | ~30 req/min | API key | НИЗКАЯ |
| **Market.CSGO** | ✅ Публичный | Нет | Да (продажи) | price | 10 req/s | Нет | НИЗКАЯ |
| **Waxpeer** | ✅ Публичный | Нет | Да (продажи) | price | 10 req/s | Нет | НИЗКАЯ |

---

## Детальный анализ

### DMarket (основная площадка)

**Эндпоинт:** `POST /marketplace-api/v1/aggregated-prices`

**Данные:**
- `best_bid` — лучшая цена покупки
- `best_ask` — лучшая цена продажи
- `bid_count` — количество ордеров на покупку
- `ask_count` — количество ордеров на продажу

**Полезность:** **МАКСИМАЛЬНАЯ** — единственный источник bid/ask count для OBI.

---

### Buff163 (buff.163.com)

**API:** `https://buff.163.com/api/market/goods`

**Данные:**
- `sell_min_price` — минимальная цена продажи
- `buy_max_price` — максимальная цена покупки
- `sell_num` — количество предложений на продажу
- `buy_num` — количество предложений на покупку

**Ограничения:**
- Требует китайский номер телефона для регистрации
- API не полностью публичное
- Rate limit: ~10 запросов в минуту
- Данные только для китайского рынка

**Полезность:** **СРЕДНЯЯ** — `sell_num` и `buy_num` аналогичны `ask_count` и `bid_count`. Но авторизация сложная.

---

### Skinport

**API:** `https://api.skinport.com/v1/items`

**Данные:**
- `min_price` — минимальная цена
- `median_price` — медианная цена
- `quantity` — количество предметов на продажу

**Ограничения:**
- Нет bid/ask count (только общее количество)
- Rate limit: 60 запросов в минуту
- API key required

**Полезность:** **НИЗКАЯ** — нет данных о спросе (bid count).

---

### Steam Community Market

**API:** `https://steamcommunity.com/market/priceoverview/`

**Данные:**
- `lowest_price` — минимальная цена
- `median_price` — медианная цена
- `volume` — количество продаж за 24 часа

**Ограничения:**
- Неофициальный API (может быть заблокирован)
- Нет bid/ask count
- Rate limit: ~20 запросов в минуту
- Нет авторизации (публичный)

**Полезность:** **НИЗКАЯ** — только исторические данные о продажах.

---

### CSFloat

**API:** `https://csfloat.com/api/v1/listings`

**Данные:**
- `price` — цена
- `stickers` — данные о стикерах

**Ограничения:**
- Требует API key (403 без авторизации)
- Нет bid/ask count
- Rate limit: ~30 запросов в минуту

**Полезность:** **НИЗКАЯ** — только цена и стикеры.

---

### Market.CSGO

**API:** `https://market.csgo.com/api/v2/prices/USD.json`

**Данные:**
- `price` — цена
- `volume` — количество продаж

**Ограничения:**
- Нет bid/ask count
- Rate limit: 10 запросов в секунду
- Нет авторизации

**Полезность:** **НИЗКАЯ** — только цена и volume.

---

### Waxpeer

**API:** `https://api.waxpeer.com/v1/prices`

**Данные:**
- `price` — цена
- `count` — количество предложений

**Ограничения:**
- Нет bid/ask count (только общее количество)
- Rate limit: 10 запросов в секунду
- Нет авторизации

**Полезность:** **НИЗКАЯ** — только цена и count.

---

## Вывод

**Только DMarket предоставляет bid_count и ask_count** — единственные данные, необходимые для OBI-стратегии.

**Buff163** — единственная площадка с аналогичными данными (sell_num/buy_num), но требует китайский номер телефона.

**Все остальные площадки** предоставляют только цену и/или volume (исторические продажи), что не полезно для OBI-сигналов.

---

## Потенциальная интеграция Buff163 (будущее)

Если Buff163 API станет доступно:

```python
# Гипотетическая интеграция
async def get_buff_obi(title: str) -> dict:
    """Get OBI data from Buff163 for cross-platform confirmation."""
    data = await buff_client.get_goods(title)
    return {
        "bid_count": data.get("buy_num", 0),
        "ask_count": data.get("sell_num", 0),
        "obi": (data["buy_num"] - data["sell_num"]) / (data["buy_num"] + data["sell_num"]),
    }
```

**Статус:** Не внедрять сейчас. Требует дальнейшего исследования авторизации Buff163.
