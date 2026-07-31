# REAL_MODE_GUIDE.md — Инструкция по переходу в реальный режим
## Date: 2026-07-31

---

## Что такое DRY_RUN

| Режим | Покупки | Продажи | Баланс |
|-------|---------|---------|--------|
| `DRY_RUN=true` | Симуляция | Симуляция | Не тратится |
| `DRY_RUN=false` | **Реальные** | **Реальные** | **Тратится** |

В `DRY_RUN=true` бот читает реальные данные с DMarket, но не отправляет запросы на покупку/продажу.

---

## Как перейти к реальному режиму

### Шаг 1: Завершить dry-run тест

Убедиться что:
- [ ] Бот стабильно работает 24+ часов без ошибок
- [ ] Находит 15-30 кандидатов за цикл
- [ ] Win rate > 50% (в simulated сделках)
- [ ] Telegram уведомления приходят корректно
- [ ] Нет критических ошибок 401/429

### Шаг 2: Проверить API эндпоинты

```bash
# Проверить buy endpoint
.venv/bin/python -c "
import asyncio
from src.api.dmarket_api_client.core import DMarketAPIClient
from src.config import Config
async def test():
    client = DMarketAPIClient(public_key=Config.DMARKET_PUBLIC_KEY, secret_key=Config.DMARKET_SECRET_KEY)
    try:
        await client.make_request('PATCH', '/exchange/v1/offers-buy', body={'offers': []})
        print('BUY endpoint: OK')
    except Exception as e:
        print(f'BUY endpoint: {e}')
    await client.close()
asyncio.run(test())
"
```

### Шаг 3: Отключить DRY_RUN

**Вариант A: Локально**
```bash
# В .env файле:
DRY_RUN=false
```

**Вариант B: GitHub Actions**
```bash
gh secret set DRY_RUN --body "false"
```

### Шаг 4: Рекомендуемый порядок

| Неделя | Баланс | DRY_RUN | Ожидание |
|--------|--------|---------|----------|
| 1-2 | $43.91 | true | Сбор статистики, проверка стратегии |
| 3 | $50 | **false** | Реальные сделки, малый объём |
| 4 | $100 | false | Увеличение объёма |
| 5+ | $200 | false | Полный автоматический цикл |

---

## Что произойдёт после отключения DRY_RUN

1. **Бот начнёт покупать** — отправит реальный `PATCH /exchange/v1/offers-buy`
2. **Бот начнёт продавать** — отправит реальный `POST /marketplace-api/v2/offers:batchCreate`
3. **Баланс будет тратиться** — реальные деньги на реальные покупки
4. **PnL будет реальным** — прибыль и убытки отражаются на балансе

---

## Безопасность

- **Stop-loss**: Автоматическая продажа при падении цены > 10%
- **Time-based stop**: Продажа через 3 дня (динамический)
- **Peak avoidance**: Не покупает на пиках (15% выше медианы)
- **Kelly sizing**: Ограничивает размер позиции (max 10% от баланса)
- **Drawdown freeze**: Остановка покупок при просадке > 15%

---

## Рекомендация

**Завершить 14-дневный dry-run тест, убедиться в стабильности, затем постепенно переходить к реальному режиму.**
