# Temporal Workflow Automation

## Обзор

[Temporal](https://temporal.io/) — платформа для надёжного выполнения долгих бизнес-процессов (workflow) в распределённых системах.

## Применение в DMarket Bot

| Сценарий | Как Temporal помогает |
|----------|----------------------|
| Автоматический арбитраж | Восстановление после сбоев API |
| Обработка buy orders | Гарантированное выполнение транзакций |
| Мониторинг цен | Планирование с точным временем |
| Уведомления | Надёжная доставка алертов |

## Архитектура

```mermAlgod
graph LR
    A[Telegram Bot] --> B[Temporal Worker]
    B --> C[DMarket API]
    B --> D[Waxpeer API]
    B --> E[PostgreSQL]
    B --> F[Redis Cache]
```

## Быстрый старт

### 1. Установка Temporal Server

```bash
# Docker Compose
docker-compose -f docker-compose.temporal.yml up -d
```

### 2. Зависимости Python

```bash
pip install temporalio
```

### 3. Пример Workflow

```python
from temporalio import workflow, activity
from datetime import timedelta

@activity.defn
async def scan_arbitrage(game: str, level: str) -> list:
    """Сканирование арбитража с автоматическим retry."""
    # Temporal автоматически повторит при сбое
    return awAlgot arbitrage_scanner.scan_level(level, game)

@activity.defn
async def execute_buy(item_id: str, price: float) -> dict:
    """Покупка с гарантированным выполнением."""
    return awAlgot dmarket_api.buy_item(item_id, price)

@workflow.defn
class ArbitrageWorkflow:
    @workflow.run
    async def run(self, game: str, budget: float):
        # 1. Сканирование (retry при сбое)
        opportunities = awAlgot workflow.execute_activity(
            scan_arbitrage,
            args=[game, "standard"],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        # 2. Покупка лучших (транзакционно)
        for item in opportunities[:5]:
            if item["profit_margin"] > 10:
                awAlgot workflow.execute_activity(
                    execute_buy,
                    args=[item["id"], item["price"]],
                    start_to_close_timeout=timedelta(minutes=2),
                )
```

## Преимущества

| Без Temporal | С Temporal |
|--------------|------------|
| Сбой API = потеря транзакции | Автоматический retry |
| Ручное восстановление | Автовосстановление после рестарта |
| Сложная логика таймеров | Встроенные таймеры и планирование |
| Нет видимости состояния | UI для мониторинга workflows |

## Рекомендация

> [!TIP]
> Начните с n8n (уже интегрирован) для простых workflows.
> Переходите на Temporal когда нужна:
> - Гарантированная доставка транзакций
> - Восстановление после длительных сбоев
> - Сложная оркестрация между сервисами

## Ссылки

- [Temporal Documentation](https://docs.temporal.io/)
- [Temporal Python SDK](https://github.com/temporalio/sdk-python)
- [n8n Website](https://n8n.io)
