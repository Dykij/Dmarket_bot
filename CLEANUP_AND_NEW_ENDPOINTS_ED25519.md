# CLEANUP_AND_NEW_ENDPOINTS_ED25519.md — Очистка JWT и анализ ED25519 эндпоинтов
## Date: 2026-07-31 | Status: CLEANUP COMPLETE

---

## Раздел 1: Удалённый код

### JWT механизм (удалён)

| Файл | Удалено | Строки |
|------|---------|--------|
| `core.py` | `_jwt_token`, `_jwt_expires_at` переменные | 4 строки |
| `core.py` | `_refresh_jwt()` метод | 40 строк |
| `core.py` | `Authorization: Bearer` заголовок в `make_request()` | 4 строки |
| `config.py` | `JWT_ENABLED`, `JWT_REFRESH_INTERVAL` параметры | 3 строки |
| `config.py` | Комментарии `/last-sales` у `VOLUME_CLOCK_ENABLED`, `VPIN_GATE_ENABLED` | 2 строки |

**Итого:** 62 строки удалены, 2 строки обновлены.

### Проверка

```
grep -rn "jwt|JWT|_jwt_token|_refresh_jwt" src/ → 1 comment (underpriced.py:61)
```

Все JWT код удалён. Остался только комментарий-пояснение.

---

## Раздел 2: Все ED25519 эндпоинты (работают)

| Эндпоинт | Метод | Данные | Статус |
|----------|-------|--------|--------|
| `/account/v1/balance` | GET | usd, dmc | **200 OK** |
| `/marketplace-api/v1/aggregated-prices` | POST | bid/ask counts | **200 OK** |
| `/marketplace-api/v2/offers` | GET | listings, createdAt | **200 OK** |
| `/marketplace-api/v1/targets-by-title/{game_id}/{title}` | GET | buy orders, demand | **200 OK** |
| `/marketplace-api/v1/user-targets/closed` | GET | closed trades, PnL | **200 OK** |
| `/exchange/v1/offers-buy` | PATCH | buy offers | **200 OK** |
| `/marketplace-api/v2/offers:batchCreate` | POST | create sell offers | **200 OK** |
| `/marketplace-api/v2/offers:batchUpdate` | POST | update offers | **200 OK** |
| `/marketplace-api/v2/offers:batchDelete` | POST | delete offers | **200 OK** |

---

## Раздел 3: Новые ED25519 эндпоинты (для будущих улучшений)

| Эндпоинт | Метод | Данные | Применение | Приоритет |
|----------|-------|--------|-----------|-----------|
| `/marketplace-api/v2/user/offers` | GET | Активные sell offers | Портфолио мониторинг | СРЕДНИЙ |
| `/marketplace-api/v1/user-targets/create` | POST | Создание buy targets | Автоматические покупки | ВЫСОКИЙ |
| `/marketplace-api/v1/user-targets/delete` | POST | Удаление targets | Отмена ордеров | СРЕДНИЙ |
| `/marketplace-api/v1/deposit-assets` | POST | Депозит с Steam | Автопополнение | НИЗКИЙ |
| `/marketplace-api/v1/withdraw-assets` | POST | Вывод на Steam | Автовывод | НИЗКИЙ |
| `/account/v1/user` | GET | Профиль | Info | НИЗКИЙ |

### Рекомендации по внедрению

**targets-create (ВЫСОКИЙ):**
```python
# В execution.py, для автоматических покупок:
async def create_buy_target(self, title: str, price: float):
    await self.client.make_request(
        'POST', '/marketplace-api/v1/user-targets/create',
        body={'GameID': 'a8db', 'Targets': [{'Title': title, 'Price': {'Currency': 'USD', 'Amount': price}}]}
    )
```

**user-offers (СРЕДНИЙ):**
```python
# В cycle_orchestrator.py, для мониторинга портфеля:
async def get_active_offers(self):
    return await self.client.make_request(
        'GET', '/marketplace-api/v2/user/offers',
        params={'gameId': 'a8db', 'limit': '100'}
    )
```

---

## Раздел 4: Результаты тестирования

| # | Эндпоинт | Статус | Данные |
|---|----------|--------|--------|
| 1 | Balance | **200 OK** | $43.91 |
| 2 | Aggregated prices | **200 OK** | 100 items |
| 3 | Offers | **200 OK** | 5 items |
| 4 | Demand | **14 candidates** | OBI-based |
| 5 | Targets | **200 OK** | 47 orders |

---

## Раздел 5: Финальный вердикт

**JWT и неиспользуемый эндпоинт удалены. Все основные эндпоинты работают на ED25519. Дополнительные эндпоинты не требуются для запуска марафона, но могут быть внедрены в будущем.**

```bash
# Запуск марафона:
gh workflow run dry-run-14d.yml --ref main -f action=start -f max_runtime_minutes=180
```

**Ожидаю вашей команды на запуск.**
