# Architecture Overview (v2.0)

## Layers

### 1. Presentation Layer (Telegram)
- **Path:** `src/telegram_bot`
- **Role:** Handles user interaction via aiogram 3.x.
- **Components:** Handlers, Keyboards, Middleware.
- **Status:** Modular, but relies heavily on global services.

### 2. Service Layer (Business Logic)
- **Path:** `src/dmarket` (Legacy Monolith) & `src/trading` (New)
- **Role:** Trading algorithms, arbitrage, buying/selling logic.
- **Tech Debt:** `src/dmarket` violates SRP. Contains API clients, db logic, and complex algos mixed together.
- **Goal:** Extract clean services into `src/trading`.

### 3. Data Layer (Persistence)
- **Path:** `src/models`
- **Role:** SQLAlchemy ORM models.
- **Key Models:** `MarketData` (Numeric prices), `User`.
- **Status:** Migrated to Alembic. `MarketData` synced with Pydantic schemas.

### 4. API Layer (DMarket)
- **Path:** `src/dmarket/api`
- **Role:** HTTP Client, Authentication, Pydantic Validation.
- **Status:** Refactored (market.py + schemas.py). Robust error handling.

## Tech Debt & Refactoring Candidates

### High Priority
- **`src/dmarket` Monolith:** Needs decomposition.
- **`src/dmarket/auto_buyer.py`:** Too complex. Should be split into `MarketScannerService` and `OrderExecutionService`.
- **Validation:** Ensure all API responses pass through `src/dmarket/schemas.py`.

## SkillSMP Alignment
- **Service Layer Pattern:** Move business logic from Handlers/API to dedicated Services.
- **Repository Pattern:** Abstract DB access (currently raw SQLAlchemy sessions).

### Recent Refactoring (v2.0)
- **AutoBuyer:** Split into Controller (src/dmarket/auto_buyer.py) and Service (src/trading/engine.py).
- **Models:** MarketData uses Numeric for precision.
