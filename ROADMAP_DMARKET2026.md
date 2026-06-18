# ROADMAP_DMARKET2026: Производительность и Smart Market Making

Этот документ определяет вектор развития **DMarket Bot** на 2026 год, фокусируясь на достижении минимальных задержек (Low Latency), пакетной обработке операций и внедрении строго математически обоснованных торговых стратегий.

## Фаза 1: Переход на High-Performance Стек (Q1-Q2 2026)

### 1.1 Миграция на Rust/Go
- [x] **Rust Core**: Критические узлы (Ed25519 подпись, JSON парсинг) на Rust через PyO3.
- [x] **Zero-Copy Parsing**: Rust serde для мгновенной десериализации aggregated-prices.
- [ ] **Advanced Rust Workers**: Полный перевод торгового цикла на Rust для микросекундных задержек.

### 1.2 Оптимизация DMarket API v2
- [x] **Batch Operations Mastery**: Полный переход на `batchCreate`, `batchUpdate`, `batchDelete`.
- [x] **Rate Limit Governor**: Интеллектуальное управление лимитами через circuit breaker и adaptive throttle.

---

## Фаза 2: Алгоритмический Трейдинг (Q2-Q3 2026)

### 2.1 Внедрение Smart Market Making стратегий
- [x] **Market Microstructure Analysis**: OBI, OFI, CVD, VPIN, VWAP, A-S — 12 инструментов.
- [x] **Arbitrage Engine**: Intra-market spread sniping + cross-market arb через CS2Cap многорыночный оракул.
- [x] **Target Sniping**: Математическая оценка флоатов и стикеров с Half Kelly позиционированием.

### 2.2 Бэктестинг и Верификация
- [x] **Sandbox Simulation**: Полная среда с balance-aware отчётом Affordable/Missed.
- [x] **Slippage Control**: Almgren-Chriss проскальзывание с динамическим порогом.

### 2.3 Внешние Оракулы Цен (CS2Cap)
- [x] **Selective Validation**: top-K стратегия (5 предметов/цикл) для Starter-квоты.
- [x] **In-Memory Cache**: 5-минутный TTL, 200 предметов, sub-ms hot path.
- [x] **CS2Cap Subpackage**: Split into models/client/catalog/prices/utils.

---

## Фаза 3: Инфраструктура и Масштабирование (Q3-Q4 2026)

### 3.1 Контейнеризация и Оркестрация
- [x] **Multi-stage Docker**: x86_64 + ARM64, Rust build, tini, health check.
- [x] **Docker Compose**: Persistent volumes, memory limits, Telegram service profile.
- [x] **Raspberry Pi Support**: Полная поддержка aarch64/ARM64 для бюджетных серверов.

### 3.2 Безопасность и Секреты
- [x] **Signature Hardening**: Rust Ed25519 подпись с Fernet-шифрованием ключей в памяти.
- [ ] **HashiCorp Vault Integration**: Вынос API-ключей в защищенное хранилище (next phase).
- [x] **SecurityAuditor**: Log redaction 20+ secret pattern, chmod 600 на все БД.

---

## Фаза 4: Balance-Aware Capital Management (v14.4 — June 2026)

### 4.1 Dynamic Position Sizing
- [x] **Fractional Kelly**: Half Kelly (50%) позиционирование.
- [x] **Dynamic Max Price**: `max($5.00, balance × 10%)` — адаптация под капитал.
- [x] **Reserve Buffer**: $10 неприкосновенного резерва для форс-мажоров.

### 4.2 Risk Controls
- [x] **Drawdown Freeze**: Авто-стоп покупок при просадке >15% от пика.
- [x] **Lock-Aware Inventory Cap**: Не более 80% капитала в trade-lock.
- [x] **Capital Velocity**: Минимум 0.5× оборота/неделю.

### 4.3 Testing & Verification
- [x] **289 unit + bottleneck tests**.
- [x] **102 bottleneck tests**: microstructure, validators, quota, DB stress.
- [x] **Sandbox v14.4**: Balance-aware Affordable/Missed report.

---

## Методология Profit-First
- **Continuous Integration**: Каждый торговый алгоритм проходит автоматический аудит и математические юнит-тесты перед деплоем.
- **Fail-Fast Circuit Breakers**: Автоматическая остановка торгов при достижении лимита просадки (Drawdown).
- **48h Sandbox Rule**: Любой новый алгоритм — минимум 48 часов в симуляции перед live.

> [!IMPORTANT]
> Главная цель 2026: Стать самым быстрым и эффективным инструментом на рынке DMarket, используя синергию Rust-перформанса и строгих математических алгоритмов баланс-ориентированного управления капиталом без AI/LLM.


🦅 *DMarket Quantitative Engine | v14.4 | June 2026*
