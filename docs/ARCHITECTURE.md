# DMarket TargetSniper - Technical Architecture (v7.0)

## 1. System Overview
The TargetSniper is a high-performance quantitative arbitrage engine designed specifically for CS2 and Rust markets on DMarket. It operates as a deterministic state machine, eliminating all legacy AI/ML latency in favor of mathematical precision and SQLite-backed historical analysis.

## 2. API Layer (Verified v2026)
All DMarket interactions use the signing-header authentication (Ed25519 NaCL).

| Endpoint Category | Method | Path |
|-------------------|--------|------|
| **Account**       | `GET`  | `/account/v1/balance` |
| **Market Data**   | `GET`  | `/exchange/v1/market/items` |
| **Inventory**     | `GET`  | `/marketplace-api/v1/user-inventory` |
| **Active Offers** | `GET`  | `/marketplace-api/v1/user-offers` |
| **Targets (Buy)** | `POST` | `/marketplace-api/v1/user-targets/create` |
| **Targets Delete**| `POST` | `/marketplace-api/v1/user-targets/delete` |

## 3. Core Logic (The Protection Layer)
The bot enforces a multi-tier safety check before any capital commitment:

1.  **Event Shield**: Checks `data/cs2_events.json`. Multiplies required profit margin (e.g., 5% -> 10% during Majors) and blacklists risky categories (Stickers/Souvenirs).
2.  **Trend Guard**: Queries `PriceHistoryDB` (SQLite). If the last 3 price observations are strictly falling, the commit is aborted.
3.  **Quantitative Validator**: Enforces a strict 5% minimum net profit margin after all platform fees (DMarket 5% default).
4.  **CSFloat Oracle Validation**: Real-time cross-reference with CSFloat lowest listing prices to ensure DMarket "Estimated Value" matches reality.

## 4. Storage & Persistence
- **PriceHistoryDB**: SQLite database storing persistent price observations for trend and average price analysis.
- **Profit Tracker**: SQLite storage for completed trades and PnL reporting.
- **Vault**: XOR-obfuscated in-memory storage for sensitive API keys.

## 5. Deployment
Optimized for `python:3.11-slim` Docker environments. Hand-tuned Garbage Collection (GC) ensures minimal latency during market scans.
