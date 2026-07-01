# 📚 DMarket Quantitative Engine Documentation (v14.9)

**Версия:** 14.9 | **Последнее обновление:** Июнь 2026

## Состав документации

| Документ | Описание |
|----------|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Архитектура v14.9 Value Scanner Engine |
| [DMARKET_API_FULL_SPEC.md](DMARKET_API_FULL_SPEC.md) | Полная спецификация DMarket API v2 |
| [API_COMPLETE_REFERENCE.md](API_COMPLETE_REFERENCE.md) | Краткий справочник всех API эндпоинтов |
| [STEAM_API_REFERENCE.md](STEAM_API_REFERENCE.md) | Справочник Steam Web API |
| [TELEGRAM_BOT_API.md](TELEGRAM_BOT_API.md) | Документация Telegram Bot API |
| [SECURITY.md](SECURITY.md) | Руководство по безопасности |
| [QUICK_START.md](QUICK_START.md) | Быстрый старт (Docker + bare metal) |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Решение типичных проблем |
| [deployment.md](deployment.md) | Развёртывание |
| [STRATEGY_ROADMAP.md](STRATEGY_ROADMAP.md) | Стратегия и roadmap v14.9 |

## Стратегия бота (v14.9)

Бот работает как **Value Detection Scanner + Spread Sniper**:

1. **Value Scanner (Primary):**
   - Поиск редких предметов (float, pattern, stickers) на DMarket
   - Оценка fair_price = cs2cap_ask × rarity_premium
   - Покупка если fair_price > ask × (1 + fee + margin)

2. **Spread Sniper (Secondary):**
   - Классический intra-market spread arbitrage
   - Fallback когда Value signal не сработает

### Dual-Signal Pipeline

```
Item Scanned
    ├── Value Signal:
    │   ├── Float premium? (FN-0, dirty BS)
    │   ├── Pattern premium? (Ruby, Blue Gem)
    │   ├── Sticker combo? (4× same)
    │   └── est_sell = cs2cap × premium_mult
    │       └── BUY if est_sell > ask × cost
    │
    └── Spread Signal (fallback):
        └── best_bid > best_ask × margin
            └── BUY at ask, list at bid
```

### Отключённые HFT-фильтры (v14.9)

Для Value Scanner стратегии строгие микроструктурные фильтры отключены:
- OBI, OFI, VWAP, CVD, VPIN, Roll, Adverse Selection, Vol Regime
- Эти фильтры применимы только к HFT/спред-стратегиям
- Для Value Scanner они искусственно ограничивают находки

### Включённые фильтры (v14.9)

- Bait/Spoof Detection
- Liquidity (MIN_TOTAL_SALES=3)
- Pump Detection
- Drawdown Freeze
- Kelly Sizing
- Lock-Aware Cap
- Capital Velocity

## Новые модули (v14.9)

### NIM Orchestrator (`src/nim_orchestrator/`)
Оркестратор NVIDIA NIM с 121+ бесплатными моделями, circuit breaker и ротацией API ключей.

### Reflexion Layer (`src/reflexion/`)
State/Snapshot паттерн с rollback через git или content-based backup.

### Workflow Chains (`src/workflow/`)
Async pipeline с Conductor паттерном для декомпозиции на подагенты.

### Bash Sandbox (`src/sandbox/`)
Безопасное выполнение shell команд с timeout и фильтрацией.

### CoT Audit (`src/cot_audit/`)
Форматирование chain-of-thought рассуждений и инкрементальный кэш метаданных.

### Integration Facade (`src/integration/`)
Единый интерфейс для всех подсистем: `safe_bash()`, `get_cot_markdown()`, `create_snapshot()`.


🦅 *DMarket Quantitative Engine | v14.9 | June 2026*