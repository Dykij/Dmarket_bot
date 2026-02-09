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
- **Status:** Fully refactored (v2.0). All files (client.py, market.py, extended.py) comply with PEP8. Pandera schemas updated.

## Tech Debt & Refactoring Candidates

### High Priority
- **`src/dmarket` Monolith:** Needs decomposition.
- **`src/dmarket/auto_buyer.py`:** Too complex. Should be split into `MarketScannerService` and `OrderExecutionService`.
- **Validation:** Ensure all API responses pass through `src/dmarket/schemas.py`.

### Completed (v2.0)
- **PEP8 Compliance:** Removed "Multiple statements on one line" and "Bare except" from core API modules.
- **Imports:** Fixed circular dependencies and deprecated imports (pandera).
- **Database:** Standardized connection string to `sqlite:///data/bot_database.db` across all configs.

## SkillSMP Alignment
- **Service Layer Pattern:** Move business logic from Handlers/API to dedicated Services.
- **Repository Pattern:** Abstract DB access (currently raw SQLAlchemy sessions).

### Recent Refactoring (v2.0)
- **AutoBuyer:** Split into Controller (src/dmarket/auto_buyer.py) and Service (src/trading/engine.py).
- **Models:** MarketData uses Numeric for precision.
- **API Client:** Cleaned up legacy code in `client.py` and `extended.py`.

