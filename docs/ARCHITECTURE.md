# Architecture of DMarket Telegram Bot (2026 Edition)

## Overview
The project is built using a modular, mixin-based architecture to ensure scalability and maintainability.

## Core Components

### 1. DMarket API (`src/dmarket/api/`)
The API client is split into functional mixins:
- `client.py`: Base HTTP client, signing (Ed25519), and rate limiting.
- `market.py`: Marketplace search and suggested prices.
- `wallet.py`: Balance and account details.
- `trading.py`: Buy, sell, and basic target operations.
- `inventory.py`: User inventory management.
- `extended.py`: Compliance with DMarket API v1.1.0 (deposits, history, etc.).

### 2. Arbitrage Scanner (`src/dmarket/scanner/`)
The scanning engine is decoupled from filtering logic:
- `engine.py`: Main `ArbitrageScanner` orchestration.
- `filters.py`: Advanced liquidity and competition filters.
- `cache.py`: Efficient caching of API responses.

### 3. Telegram UI (`src/telegram_bot/handlers/`)
Keyboard handlers are split into logical parts:
- `keyboard_parts/trading.py`: Auto-trading controls.
- `keyboard_parts/targets.py`: Buy order management.
- `keyboard_parts/info.py`: Balance and inventory views.
- `keyboard_parts/ml_ai.py`: Machine learning training and status.

### 4. Agent Skills (`.github/skills/`)
AI-compatible modular extensions following the 2026 SkillsMP.com standard.

## Data Persistence
State management has been migrated from `.pickle` files to a robust **PostgreSQL/SQLite** backend using **SQLAlchemy 2.0**.
