# 📚 DMarket TargetSniper Documentation

**Версия:** 6.0 | **Последнее обновление:** Апрель 2026

## Состав документации

| Документ | Описание |
|----------|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Текущая архитектура Quantitative Arbitrage Engine v7.0 |
| [DMARKET_API_FULL_SPEC.md](DMARKET_API_FULL_SPEC.md) | Полная спецификация DMarket API v2 (Ed25519, Endpoints) |
| [API_COMPLETE_REFERENCE.md](API_COMPLETE_REFERENCE.md) | Краткий справочник всех API эндпоинтов |
| [STEAM_API_REFERENCE.md](STEAM_API_REFERENCE.md) | Справочник Steam Web API для инспекции предметов |
| [TELEGRAM_BOT_API.md](TELEGRAM_BOT_API.md) | Документация Telegram Bot интерфейса |
| [SECURITY.md](SECURITY.md) | Руководство по безопасности и защите ключей |
| [QUICK_START.md](QUICK_START.md) | Руководство по первому запуску бота |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Решение типичных проблем |
| [deployment.md](deployment.md) | Руководство по развёртыванию (Docker, VPS, Cloud) |

## Стратегия бота

Бот работает как **детерминистический Quantitative Arbitrage Engine**:
1. Сканирует DMarket REST API (`/exchange/v1/market/items`) через async HTTP/2 пул.
2. Валидирует цены через **CSFloat Oracle** (Reference Price).
3. Применяет математический фильтр: минимальная маржа >5% после комиссий.
4. Секреты защищены через **In-Memory Vault** (XOR-маскирование в heap).

> **Примечание:** Этот бот НЕ использует AI, ML, LLM или нейросети. Все решения принимаются чистой математикой.


---
🦅 *DMarket Quantitative engine | v7.0 | 2026*

----- 
🦅 *DMarket Quantitative Engine | v7.0 | 2026*