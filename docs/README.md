# 📚 DMarket Quantitative Engine Documentation (v14.4)

**Версия:** 14.4 | **Последнее обновление:** Июнь 2026

## Состав документации

| Документ | Описание |
|----------|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Архитектура v14.4 Balance-Aware Engine |
| [DMARKET_API_FULL_SPEC.md](DMARKET_API_FULL_SPEC.md) | Полная спецификация DMarket API v2 (Ed25519, Endpoints) |
| [API_COMPLETE_REFERENCE.md](API_COMPLETE_REFERENCE.md) | Краткий справочник всех API эндпоинтов |
| [STEAM_API_REFERENCE.md](STEAM_API_REFERENCE.md) | Справочник Steam Web API для инспекции предметов |
| [TELEGRAM_BOT_API.md](TELEGRAM_BOT_API.md) | Документация Telegram Bot API (общая) |
| [SECURITY.md](SECURITY.md) | Руководство по безопасности и защите ключей |
| [QUICK_START.md](QUICK_START.md) | Быстрый старт (Docker + bare metal) |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Решение типичных проблем (v14.4) |
| [deployment.md](deployment.md) | Развёртывание (Docker, Raspberry Pi, Mini-PC) |
| [STRATEGY_ROADMAP.md](STRATEGY_ROADMAP.md) | Стратегия и roadmap v14.4 |

## Стратегия бота (v14.4)

Бот работает как **Balance-Aware Quantitative Arbitrage Engine**:
1. Сканирует DMarket REST API через async HTTP/2 пул каждые 30с.
2. Валидирует цены через CS2Cap oracle (41 marketplace).
3. Применяет математические фильтры: OBI, OFI, VWAP, VPIN, slippage, Kelly, bait detection.
4. **Адаптирует все лимиты под баланс**: Dynamic max price, Half Kelly, drawdown freeze.
5. **Деплой**: Docker multi-stage (x86_64 + ARM64), docker-compose с volumes.

> **Примечание:** Этот бот НЕ использует AI, ML, LLM или нейросети. Все решения — чистая математика + balance-aware risk management.


🦅 *DMarket Quantitative Engine | v14.4 | June 2026*
