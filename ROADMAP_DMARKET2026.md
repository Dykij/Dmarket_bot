# ROADMAP_DMARKET2026: Производительность и Smart Market Making

Этот документ определяет вектор развития **DMarket Bot** на 2026 год, фокусируясь на достижении минимальных задержек (Low Latency), пакетной обработке операций и внедрении строго математически обоснованных торговых стратегий.

> **Last updated:** 2026-06-01
> **Current version:** v12.2 (Phase 2 + 3.1 + 3.2 complete)
> **Status:** Production-ready (28/28 tests passing)

## Фаза 1: Переход на High-Performance Стек (Q1-Q2 2026)

### 1.1 Миграция на Rust/Go
- [ ] **Core Rewrite**: Переписывание критических узлов сетевого взаимодействия и парсинга API на Rust или Go для устранения задержек GIL и минимизации потребления RAM.
- [ ] **Zero-Copy Parsing**: Внедрение высокоскоростной десериализации JSON для мгновенной обработки тяжелых ответов от `/v2/offers`.
- [ ] **Asynchronous Workers**: Использование горутин (Go) или асинхронных рантаймов (Rust Tokyo) для параллельной поддержки сотен WebSocket-соединений.
- [x] **(Optional) Rust signer**: Optional Rust signer in `rust_core_src/` for microsecond signing (v7.8+)

### 1.2 Оптимизация DMarket API v2
- [x] **Batch Operations Mastery**: Полный переход на `batchCreate`, `batchUpdate`, `batchDelete`. Реализация механизма накопления и мгновенного вброса пакетов ордеров. **(v12.2 Phase 2.5)**
- [x] **Rate Limit Governor**: Интеллектуальное управление лимитами через распределенные очереди, предотвращающее 429 ошибки при Quantitative-нагрузке.
- [x] **Bulk Fee Fetching**: `get_item_fee_bulk()` — 50 items per call (v12.2 Phase 2.2)
- [x] **ClockSync (NTP-like)**: `src/utils/clock_sync.py` — prevents 401 from clock drift (v12.2 Phase 3.1)

---

## Фаза 2: Алгоритмический Трейдинг (Q2-Q3 2026)

### 2.1 Внедрение Smart Market Making стратегий
- [x] **Market Microstructure Analysis**: Реализация парсеров истории продаж и стаканов для выявления скрытой ликвидности.
- [x] **Arbitrage Engine**: Разработка модулей межбанковского и внутрибиржевого арбитража на основе количественных моделей (Lopez de Prado).
- [x] **Target Sniping**: Алгоритмическая математическая оценка флоатов и комбинаций стикеров для поиска недооцененных лотов и выставления ордеров с маржинальностью >5%.

### 2.2 Бэктестинг и Верификация
- [x] **Backtrader Integration**: Создание среды для прогона стратегий на исторических данных DMarket перед запуском в продакшен.
- [x] **Slippage Control**: Учет проскальзываний и комиссий в реальном времени для динамической коррекции целевой маржи.
- [x] **Multi-day Sandbox**: `scratch/sandbox_v12_1.py` — 7-day lifecycle simulation with variance test (5 seeds)
- [x] **v12.2 Filter Audit**: `scratch/sandbox_v12_2_audit.py` — measures impact of new filters

### 2.3 Внешние Оракулы Цен
- [x] **CSFloat → CS2Cap Migration**: Replaced CSFloat with CS2Cap (BUFF163 + 41 markets) (v12.0)
- [x] **Data Fetching Limits**: Интеграция с экспоненциальной задержкой (Exponential Backoff), чтобы избежать блокировок (HTTP 429) и банов аккаунта за парсинг.
- [x] **Intra-Market Flipping**: Использование CS2Cap *только* для оценки рыночной цены предмета. Выкуп и последующая продажа (переворот) должны происходить **внутри DMarket без вывода в Steam**, чтобы избежать критической блокировки ликвидности из-за 7-дневного трейд-бана CS2. Межбиржевой Quantitative-арбитраж (Купить DMarket -> Продать CSFloat) **невозможен** математически для быстрых сделок.

### 2.4 v12.2 Defenses (NEW)
- [x] **Asset Status Tracking**: `asset_status` table, `get_user_inventory_detailed()` with FinalizationTime, `get_transaction_history()` for rollback detection
- [x] **Wash Trading Detection**: `get_trimmed_mean()` with iterative outlier removal (±24%, max 3 outliers)
- [x] **Multi-level Liquidity Filter**: 5 thresholds (80 sales, 23 days, 11 in window, 20d first, 3d last)
- [x] **Float Premium (Phase 1.2)**: FN-0 1.20x, FN 1.10x, FT-0 1.15x, WW 0.95x, BS 0.90x
- [x] **Low-Fee Filter (Phase 1.1)**: prefer items with 2-3% fee vs 5% default

---

## Фаза 3: Инфраструктура и Масштабирование (Q3-Q4 2026)

### 3.1 Контейнеризация и Оркестрация
- [x] **Microservices Architecture**: Оформление компонентов бота в виде независимых микросервисов.
- [x] **Multi-Instance Support**: Настройка Docker Compose для запуска изолированных инстансов под разные игры (CS2, Rust) на одной машине, исключая Dota 2 и TF2.

### 3.2 Безопасность и Секреты
- [ ] **HashiCorp Vault Integration**: Вынос API-ключей и приватных ключей NACL в защищенное хранилище.
- [x] **Signature Hardening**: Оптимизация процесса подписи `X-Request-Sign` для работы в микросекундном диапазоне.
- [x] **MockMemoryVault (dev)**: `src/utils/vault.py` for local development
- [x] **ClockSync (v12.2)**: Server-time sync for X-Sign-Date (prevents 401 from drift)

---

## Методология Profit-First
- **Continuous Integration**: Каждый торговый алгоритм проходит автоматический аудит и математические юнит-тесты перед деплоем.
- **Fail-Fast Circuit Breakers**: Автоматическая остановка торгов при достижении лимита просадки (Drawdown).

## v12.2 Verification
- **28/28 tests passing** (was 17/17 in v12.0)
- **8 new tests** for v12.2 features (status, fee bulk, trimmed mean, liquidity, v2 batch, clocksync)
- **Realistic projection:** $411/year on $44 (5-seed average, v12.1 baseline)
- **Defenses:** wash trading, reverted items, illiquid items, clock drift

> [!IMPORTANT]
> Главная цель 2026: Стать самым быстрым и эффективным инструментом на рынке DMarket, используя синергию Rust-перформанса и строгих математических алгоритмов без использования сложных ИИ и LLM-пайплайнов.

## What's NOT Implemented (and why)
- **Strategy B (Last Sales)**: 3h effort, but backtest first (2h) to validate worth
- **Strategy D (Stickers)**: 8h effort for 1-3 events/week, ROI too low for $44 balance
- **Strategy F (Volume)**: ❌ Roadmap explicitly says not recommended for $43.91
- **Rust core rewrite**: out of scope (Python is fast enough for current scale)
- **HashiCorp Vault**: planned (Q3-Q4 2026), low priority (MockMemoryVault is sufficient for dev)


---
🦅 *DMarket Quantitative engine | v12.2 | 2026*

----- 
🦅 *DMarket Quantitative Engine | v12.2 | 2026*