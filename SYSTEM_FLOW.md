# SYSTEM_FLOW - DMarket Quantitative Engine (v14.4)

Этот документ описывает логическую цепочку работы бота в режиме **v14.4 (Balance-Aware Quantitative Engine)**.

---

## 🔄 Основной торговый цикл (30s pipeline)

```mermaid
graph TD
    A[Start Cycle] --> B[Aggregated Prices batch 100]
    B --> C[Rank: spread × sqrt(bid+ask count)]
    C --> D[Top-20: honest listings + DOM cache]
    D --> E[Bulk fee 4 tiers + CS2Cap cache]
    E --> F{Balance Gate}
    F -- balance OK --> G{15 filters pipeline}
    G -- pass --> H[Kelly position sizing]
    H --> I[Execute instant-buy]
    I --> J[Auto-resale immediate]
    J --> K[Reprice stale every 200 cycles]
    K --> A

    F -- balance low --> L[Skip: drawdown freeze]
    G -- fail --> L
    L --> A
```

### v14.4 Balance-Aware Gates (new in cycle)

```
BALANCE GATE:
  effective = max(0, balance - BALANCE_RESERVE_USD)
  max_price = max(MAX_SNIPING_PRICE_FLOOR, effective * 0.10)
  if item.price > max_price → SKIP

DRAWDOWN GATE:
  if balance < peak_balance * 0.85 → FREEZE (sell-only mode)

KELLY GATE:
  f* = win_rate - (1 - win_rate) / win_loss_ratio
  position_size = capital * 0.50 * f*  (Half Kelly)

VELOCITY GATE:
  weekly_sales / avg_balance < 0.5 → PAUSE BUYING

LOCK-AWARE CAP:
  if trade-locked items > 80% of max → SKIP new buys
```

---

## 🛡 Компоненты защиты

### 1. Balance Gate (v14.4)
Dynamic max price, reserve buffer, drawdown freeze. Адаптация под текущий баланс DMarket.

### 2. Trend Guard (SQLite)
Сверяет текущую цену с последними 10 записями в базе данных. Если цена ниже скользящей средней (SMA-5) более чем на 10%, покупка блокируется.

### 3. Event Shield
Считывает `data/cs2_events.json`. Если текущая дата попадает в интервал Major или Steam Sale, маржинальный порог автоматически повышается до 10% для компенсации волатильности.

### 4. Kelly Position Sizing (v14.4)
Fractional Half Kelly: `KELLY_FRACTION=0.50`. Снижает просадку на ~50% при 85% от полного роста.

### 5. Pydantic Gate
Каждый объект сделки проходит через схему валидации, которая блокирует некорректные типы данных, отрицательные цены и предметы не из белого списка (CS2).

---

## 📡 Сетевой уровень

- **Transport**: `aiohttp` (Asynchronous HTTP).
- **Security**: Ed25519 NACL signatures with Rust (fast) or pynacl (fallback).
- **Speed**: Пакетная обработка (`Batching`) до 100 таргетов в одном запросе.
- **Quota**: CS2Cap Starter tier (50K req/mo) с in-memory cache (5 min TTL).

---

## 🐳 Docker Deployment

- **Multi-stage build**: Builder (Rust + Python) → Runtime (~250 MB)
- **Architectures**: x86_64 + aarch64/ARM64 (Raspberry Pi 4/5, mini-PCs)
- **Health check**: `/healthz` на порту 9091
- **Persistence**: Docker volumes для `data/` (SQLite) и `logs/`
- **Memory limits**: 512 MB (main), 256 MB (Telegram)


---

🦅 *DMarket Quantitative Engine | v14.4 | June 2026*
