# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [12.2.0] - 2026-06-01
### 🛡️ Asset Status + Dynamic Fee + Wash Trading + V2 Batch + ClockSync
#### Phase 2.1: Asset Status Tracking
- New `asset_status` table: tracks `trade_protected`, `reverted`, `active`, `sold`
- `get_user_inventory_detailed()` — fetches inventory with `FinalizationTime` field
- `get_transaction_history()` — detects DMarket rollbacks
- `update_asset_status()`, `is_trade_locked()`, `mark_reverted()` — DB methods
- `_sync_inventory_statuses()` — auto-sync every 20 cycles
- `_skip_if_locked()` — prevents double-buy of reverted/locked items

#### Phase 2.2: Dynamic Fee Per Item (Bulk)
- `get_item_fee_bulk()` — fetches fees for up to 50 items in 1 request
- Replaces per-item `get_item_fee()` calls in main loop
- Reduces API calls from N → N/50

#### Phase 2.3: Trimmed Mean (Wash Trading Detection)
- `get_trimmed_mean()` — removes outliers ±24% from mean
- `detect_wash_trading()` — flags inflated prices (raw >> trimmed)
- Configurable `boost_pct` and `max_outliers`

#### Phase 2.4: Multi-level Liquidity Filter
- `get_liquidity_metrics()` — total_sales, window sales, age of first/last sale
- `passes_liquidity_filter()` — Config-driven thresholds
- 5 thresholds: MIN_TOTAL_SALES, MIN_SALES_IN_WINDOW, MAX_FIRST/LAST_SALE_AGE

#### Phase 2.5: DMarket API v2 Batch Migration
- `batch_create_offers_v2()` — POST /exchange/v1/user-offers/batch-create
- `batch_edit_offers_v2()` — PATCH /exchange/v1/user-offers/batch-edit
- `batch_delete_offers_v2()` — POST /exchange/v1/user-offers/batch-close
- `get_user_offers_v2()` — GET /exchange/v1/user-offers
- Up to 100 items per batch (vs 1 in v1)

#### Phase 3.1: ClockSync (NTP-like) — NEW
- `src/utils/clock_sync.py` — syncs local clock with DMarket server via HEAD request
- Pre-check X-Sign-Date before signing (prevents 401 from clock drift > 120s)
- Refreshes every 6 hours
- Auto-fallback to local time if server unreachable
- Health status reporting (offset, drift, is_healthy)

#### Phase 3.2: v12.2 Audit Sandbox — NEW
- `scratch/sandbox_v12_2_audit.py` — measures impact of new filters
- Compares v12.1 baseline vs v12.2 (with wash trading + liquidity + status)
- Reports filter effectiveness (% rejected by each filter)
- Real-market adjustment analysis

#### Phase 3.3: Documentation Updates
- `docs/STRATEGY_ROADMAP.md` — v12.2 status (all 6 strategies + new defenses)
- `ROADMAP_DMARKET2026.md` — Phase 2.4 (v12.2 Defenses) and Phase 3.2 sections

#### Phase 3.4: Telegram Control Bot — NEW
- `src/telegram/control_bot.py` — full-featured Telegram bot (replaces old bot.py)
- **Main reply keyboard** (10 buttons): Start/Stop, Balance, Status, Inventory, Profits, Test, Settings, Panic, Help
- **Inline keyboards** with state-dependent START/STOP buttons
- **Commands** (13 total): /start, /start_bot, /stop_bot, /panic, /balance, /status, /inventory, /profits, /test, /settings, /clock, /refresh, /help
- **Access control**: only admin (TELEGRAM_ADMIN_ID) can interact
- **Live integration**: starts/stops real `SnipingLoop`, queries real DMarket balance
- **Callbacks**: btn:start, btn:stop, btn:balance, btn:inventory, btn:profits, btn:refresh_status
- **Bot verified live**: @DmarketPayonnerBot (ID: 8585707237), admin 458765683
- `scripts/start_telegram_bot.sh` — one-command launcher
- `scratch/test_telegram_bot.py` — 11 unit tests for keyboards, access, callbacks
- `.env.example` updated with TELEGRAM_ADMIN_ID placeholder
- `scratch/test_sandbox_v9.py` extended with 10 telegram tests (28 async + 10 sync = 38 total)

#### Phase 3.5: Telegram Bot Hardening (resilience & error recovery)
- **sys.path auto-fix** (variant 4 from plan): bot works from any cwd
- **No sys.exit() at import time**: missing token logs error but doesn't kill the process
- **`safe_call` decorator**: wraps every handler — any uncaught exception is reported to user via Telegram, never crashes the dispatcher
- **`@router.errors()`** global handler: catches anything that slips through
- **`retry_async` utility**: exponential backoff (1s → 2s → 4s → 8s) for retriable errors (TimeoutError, ConnectionError, OSError, aiohttp.ClientError); non-retriable errors fail fast
- **`BotState` class**: thread-safe with `asyncio.Lock`; one place to manage sniping loop, client, flags
- **PANIC button** now reuses the running bot's client (no more duplicate API calls)
- **/test FSM flow**: pressing the button (vs. typing `/test <item>`) now enters a state waiting for the item name; /cancel exits
- **Graceful shutdown** on SIGTERM / SIGINT: `dp.stop_polling()` + state cleanup + admin notification; cleans up PID file
- **Logs to file** (`logs/telegram_bot.log`) + stdout; aiogram log noise reduced to WARNING
- **Old `bot.py` archived** as `bot_legacy_broken.py.bak` (had hardcoded Windows path)
- **Launcher hardening** (variant 1 from plan):
  - Auto-detects project root from any cwd (5 strategies: scripts-relative, common paths, walk-up)
  - Validates Python ≥ 3.11
  - Prefers local `.venv/bin/python` over system `python3`
  - Validates `.env` has all required keys (without exposing values)
  - Refuses to start if a stale PID file points to a live process
  - DRY_RUN defaults to `true` (safe) with explicit confirmation for LIVE mode
  - Color-coded status output
  - Writes PID to `.run/telegram_bot.pid` and cleans it up on exit
  - `set -u` (not `set -e`) for graceful error messages
- **19 telegram tests** in `scratch/test_telegram_bot.py` (was 11): added tests for safe_call, retry_async, BotState lock, no-sys.exit, FSM, signal handlers
- **46/46 tests passing** (was 38/38)

#### Bug Fixes
- Fixed pre-existing dead code in `_calculate_float_premium` (BS case was unreachable)
- Fixed `not x is False` boolean logic in `_sync_inventory_statuses`
- Added missing `cleanup_old_targets()` method to `PriceHistoryDB`

#### Tests
- 28/28 tests passing (was 17/17 in v12.0)
- 11 new tests: trade_protected, reverted, FinalizationTime, bulk_fee, trimmed_mean,
  liquidity, v2 batch create/edit, clocksync init/offset/status

## [12.0.0] - 2026-06-01
### 🚀 Intra-Spread Engine: Strategy A
- **CSFloat → CS2Cap Oracle Migration**: BUFF163 + 41 markets price reference
- **Strategy A (Intra-DMarket Spread)**: Buy at best_ask, sell at best_bid - 0.01
- **New API Endpoints**:
  - `get_aggregated_prices()` — batch best_bid+best_ask for 100 items
  - `get_last_sales()` — real DMarket sale transactions
  - `get_low_fee_items()` — daily low-fee items (2-3% vs 5%)
  - `create_offer()`, `batch_create_offers()`, `delete_offers()`, `edit_offer()` — sell pipeline
- **Refactored target_sniping.py**: bid-based filter (5%+ spread), CS2Cap oracle validation
- **New docs/STRATEGY_ROADMAP.md**: Full A-F strategy comparison
- **Verification Suite**: 17/17 tests passing
- **Sandbox Audit**: 6/50 opportunities → $8.62 profit on $41.35 risk (+62% with Low-Fee + Float)

### Phase 1.1: Low-Fee Filter (v12.0)
- **24h cached low-fee items list**: avoids 1 API call per cycle
- **Auto-refresh every 100 cycles** in `target_sniping._refresh_low_fee_cache()`
- **Helper methods**: `save_low_fee_items`, `get_low_fee_rate`, `low_fee_cache_size`
- **DB migration**: new `low_fee_cache` table in state DB
- **Effect**: 20% of items get 2.5% fee instead of 5% → +1-2% margin

### Phase 1.2: Float Premium (v12.0)
- **FN-0 (float <0.01)**: 1.20x premium
- **FN (0.01-0.07)**: 1.10x premium
- **FT-0 (0.15-0.18)**: 1.15x premium
- **MW/FT (default)**: 1.0x
- **WW (0.38-0.45)**: 0.95x
- **BS (≥0.45)**: 0.90x
- **Method**: `SnipingLoop._calculate_float_premium(attrs)`
- **Effect**: +$1-2/day additional profit on FN-0/FT-0 items


## [11.0.0] - 2026-05
### CS2Cap Migration
- Initial migration from CSFloat to CS2Cap


## [7.0.0] - 2026-04-14
### 🚀 The Quantitative Awakening
- **Полная трансформация**: Переход от экспериментальной ИИ-архитектуры к строгому количественному движку (Pure Quantitative Engine).
- **Удаление AI Debt**: Полностью вырезаны модули Markov Chains, CUDA/CuPy и нейронные предикторы для минимизации задержек.
- **SQLite Интеграция**: Добавлена персистентная база данных истории цен для точного анализа трендов.
- **DMarket API v1.1.0 Sync**: Полная синхронизация эндпоинтов с `/marketplace-api/v1/`.
- **Защитные механизмы**: Реализованы `Trend Guard` (защита от падения цены) и `Event Shield` (календарь ивентов 2026).
- **Документация**: Глобальный рефакторинг всех MD-файлов. Публикация полной спецификации API (4,000 строк).

### Updated - API Documentation (January 4, 2026)

#### DMarket API (`docs/DMARKET_API_FULL_SPEC.md`)
- Updated date to January 4, 2026
- Verified alignment with https://docs.dmarket.com/v1/swagger.html

#### Telegram Bot API (`docs/TELEGRAM_BOT_API.md`)
- Updated date to January 4, 2026
- Confirmed Bot API 9.2 features documented

#### DMarket API Client (`src/dmarket/dmarket_api.py`)
- **New method `get_offers_by_title()`** - Search offers by item title
- **New method `get_closed_offers()`** - Get closed offers with filters:
  - `status`: "successful", "reverted", "trade_protected"
  - `closed_from` / `closed_to`: Timestamp filters
  - Supports new `FinalizationTime` field from API v1.1.0
- Updated docstring with API version v1.1.0

#### Telegram Utils (`src/telegram_bot/utils/api_helper.py`)
- Added `send_message_with_reply()` helper for Bot API 9.2 reply parameters

### Added - Waxpeer API Documentation (January 4, 2026)

#### Documentation: `docs/WAXPEER_API_SPEC.md`
Comprehensive Waxpeer API documentation based on https://docs.waxpeer.com/:

- **Endpoints Reference**: All API endpoints with parameters and responses
- **Authentication**: API key usage guide
- **Price Conversion**: Mils to USD (1000 mils = $1)
- **Commission Info**: 6% sell commission calculation
- **Rate Limits**: Per-endpoint limits
- **Error Codes**: Complete error reference
- **Code Examples**: Python async examples

#### Waxpeer API Client Updates (`src/waxpeer/waxpeer_api.py`)
- **New Games Support**: Added CS2, Rust to `WaxpeerGame` enum
- **New `WaxpeerPriceInfo` dataclass** with:
  - `price_mils`, `price_usd`, `count` (liquidity)
  - `is_liquid` property (count >= 5)
- **New methods**:
  - `get_item_price_info()` - Returns `WaxpeerPriceInfo`
  - `get_bulk_prices()` - Efficient mass price fetch
  - `get_my_inventory()` - Steam inventory for listing
  - `check_tradelink()` - Trade link validation
- **Improved `get_balance()`** - Now includes `can_trade` status
- **Added `MILS_PER_USD` constant** (1000)

#### Handler Updates (`src/telegram_bot/handlers/waxpeer_handler.py`)
- `waxpeer_balance_handler()` now fetches real balance via API

### Added - Cross-Platform Arbitrage (January 4, 2026)

#### New Module: `src/dmarket/cross_platform_arbitrage.py`
Implements advanced DMarket ↔ Waxpeer arbitrage scanner based on analysis:

- **Full Market Scanning** - No `best_deals` filter, sees ALL items
- **Balance-Aware Purchasing** - Uses `priceTo=balance` to filter affordable items
- **Trade Lock Analysis** - Supports items with lock up to 8 days (15% min ROI)
- **Liquidity Checks** - Skips items with < 5 daily sales on Waxpeer
- **Net Profit Calculation** - Formula: `(Waxpeer_Price * 0.94) - DMarket_Price`

Key classes:
- `CrossPlatformArbitrageScanner` - Main scanner class
- `ArbitrageOpportunity` - Data class for opportunities
- `ScanConfig` - Configuration dataclass
- `ArbitrageDecision` enum - BUY_INSTANT, BUY_AND_HOLD, SKIP

#### New Handler: `src/telegram_bot/handlers/waxpeer_handler.py`
- `waxpeer_menu_handler()` - Main Waxpeer menu
- `waxpeer_balance_handler()` - Balance display
- `waxpeer_settings_handler()` - Settings management
- `route_waxpeer_callback()` - Callback router

#### Waxpeer API Enhancements (`src/waxpeer/waxpeer_api.py`)
- Added `get_items_list()` method for price comparison
- Used by CrossPlatformArbitrageScanner

### Added - Waxpeer Integration (January 4, 2026)

#### Configuration
- **Added Waxpeer API configuration** (`src/utils/config.py`):
  - New `WaxpeerConfig` dataclass with all Waxpeer settings
  - Environment variable loading for all Waxpeer options
  - Default values for markup (10%), rare markup (25%), ultra markup (40%)
- **Updated `.env` file** with Waxpeer API key and settings:
  - `WAXPEER_ENABLED=true`
  - `WAXPEER_API_KEY` configured
  - Markup, repricing, and shadow listing settings

#### Keyboards
- **Added Waxpeer keyboards** (`src/telegram_bot/keyboards/arbitrage.py`):
  - `get_waxpeer_keyboard()` - Main Waxpeer menu (balance, listings, repricing)
  - `get_waxpeer_settings_keyboard()` - Settings with toggles for reprice/shadow/hold
  - `get_waxpeer_listings_keyboard()` - Paginated listings view
- **Updated `get_modern_arbitrage_keyboard()`** with "💎 Waxpeer P2P" button

#### Features Enabled
- Waxpeer P2P integration for CS2 skin reselling
- Automatic undercut repricing every 30 minutes
- Smart pricing based on market scarcity
- Tiered markup system (normal/rare/ultra)

### Fixed - Code Quality (January 4, 2026)

#### Linting Fixes
- **Fixed undefined variable errors (F821)**:
  - `src/dmarket/auto_buyer.py` - Added TYPE_CHECKING import for TradingPersistence
  - `src/dmarket/intramarket_arbitrage.py` - Fixed duplicate code with key_parts/composite_key
  - `src/dmarket/price_anomaly_detector.py` - Made `_init_api_client` async
- **Fixed unused variable warnings (F841)**:
  - Properly marked unused but intentional variables with underscore prefix
  - Updated files: `item_value_evaluator.py`, `price_analyzer.py`, `command_center.py`
  - Updated handlers: `extended_stats_handler.py`, `market_sentiment_handler.py`
  - Updated utils: `collectors_hold.py`
- **Fixed type comparison issues (E721)**:
  - `src/utils/env_validator.py` - Changed `==` to `is` for type comparisons
- **Fixed import order (E402)**:
  - `src/telegram_bot/dependencies.py` - Moved TypeVar import to top
- **Fixed whitespace issues (W291, W293)**:
  - Removed trailing whitespace and blank lines with whitespace
- **Fixed mypy syntax error**:
  - `src/utils/prometheus_metrics.py` - Fixed inline type comment causing syntax error

#### Test Fixes
- **Fixed MCP Server tests**:
  - Corrected patch paths for `ArbitrageScanner` and `TargetManager`
  - Fixed test accessing internal `_request_handlers` attribute
- **Fixed price_anomaly_detector tests**:
  - Made `_init_api_client` function async to match test expectations

#### Code Formatting
- 99 files reformatted with `ruff format`
- 47 import sorting issues fixed automatically

#### Documentation Updates
- Updated dates in 12+ documentation files from 2025 to April 2026
- Updated README.md with correct test count (7654+)
- Updated copilot-instructions.md with correct test count

#### Code Quality Improvements
- Reduced linting errors from 33 to 0 (critical errors)
- All 571 unit tests passing
- All 7 smoke tests passing

### Changed - Keyboard Refactoring (January 2, 2026)

#### Updated Keyboards
- **Постоянная клавиатура (ReplyKeyboard)** - упрощена до 4 кнопок:
  - ⚡ Упрощенное меню - быстрый доступ к `/simple`
  - 📊 Полное меню - возврат к полному функционалу
  - 💰 Баланс - мгновенная проверка через `balance_simple()`
  - 📈 Статистика - детальный отчет через `stats_simple()`
- **Inline клавиатура** - добавлена кнопка "⚡ Упрощенное меню" в главное меню

#### Updated Handlers
- `src/telegram_bot/handlers/commands.py`:
  - `start_command()` - обновлен текст приветствия с объяснением режимов
  - `handle_text_buttons()` - добавлена обработка новых кнопок
- `src/telegram_bot/handlers/callbacks.py`:
  - `button_callback_handler()` - добавлен callback "simple_menu"

#### Cleanup & Archive
- **Архивировано 9 файлов** в `archive_old_docs/`:
  - Документы по завершенным этапам разработки
  - Устаревшие руководства (Poetry, старые тесты)
  - Отчеты по реструктуризации и рефакторингу
- Создан `archive_old_docs/README.md` с описанием архива

#### UX Improvements
- ✅ Одна кнопка для доступа к упрощенному меню (вместо команды `/simple`)
- ✅ Быстрый переключение между режимами (полное ↔ упрощенное)
- ✅ Прямой доступ к балансу и статистике с клавиатуры
- ✅ Inline кнопка в главном меню для быстрого доступа

### Added - Simplified Menu Interface (January 2, 2026)

#### New Features
- **🚀 Упрощенное меню бота** (`/simple`) - быстрый интерфейс для основных операций
  - `src/telegram_bot/handlers/simplified_menu_handler.py` - ConversationHandler с 4 основными действиями
  - 🔍 **Арбитраж**: Все игры сразу или ручной режим (по одной игре)
  - 🎯 **Таргеты**: Ручной (ввод названия) и автоматический режим
  - 💰 **Баланс**: Мгновенная проверка USD/DMC
  - 📊 **Статистика**: Детальный отчет (на продаже/продано/профит)
  - **Постоянная клавиатура** для быстрого доступа
  - **24 теста** с покрытием 72.19%

#### Documentation
- `docs/SIMPLIFIED_MENU_GUIDE.md` - Полное руководство по упрощенному меню (393 строки)
- `docs/SIMPLIFIED_MENU_EXAMPLES.md` - Практические примеры использования (320 строк)
- `README.md` - Добавлена секция "Интерфейс бота" с ссылкой на упрощенное меню
- `docs/README.md` - Добавлен раздел "Быстрый старт" с упрощенным меню

#### Tests
- `tests/telegram_bot/handlers/test_simplified_menu_handler.py` - 24 теста (500+ строк)
  - TestKeyboards: Тесты клавиатур (4 теста)
  - TestStartMenu: Тесты стартового меню (2 теста)
  - TestBalance: Тесты баланса (2 теста)
  - TestStats: Тесты статистики (1 тест)
  - TestArbitrage: Тесты арбитража (7 тестов)
  - TestTargets: Тесты таргетов (6 тестов)
  - TestIntegration: Интеграционные тесты (2 теста)

### Added - Phase 2 & 3: Production Ready (April 2026)

#### Phase 2: Code Readability & Infrastructure
- **Refactored 15+ Core Modules** with early returns pattern
  - `src/dmarket/dmarket_api.py` - `_request` method optimization
  - `src/dmarket/arbitrage_scanner.py` - `scan_level`, `calculate_profit`
  - `src/dmarket/market_analysis.py` - `analyze_market_depth`
  - `src/dmarket/targets.py` - `create_target`, `validate_target`
  - `src/telegram_bot/handlers/*` - scanner, targets, callbacks refactored
- **Performance Infrastructure**
  - `scripts/profile_scanner.py` - py-spy profiling script
  - `scripts/monitor_performance.py` - continuous monitoring
  - Batch processing implementation (~3x speed improvement)
  - Connection pooling optimization (httpx, database, redis)
- **Documentation**
  - `docs/PHASE_2_REFACTORING_GUIDE.md` - Refactoring patterns guide
  - `docs/PERFORMANCE_OPTIMIZATION_GUIDE.md` - Performance best practices
  - `docs/MIGRATION_GUIDE.md` - Module migration instructions
  - `docs/TESTING_STRATEGY.md` - Comprehensive testing approach

#### Phase 3: Production Improvements
- **Health & Monitoring**
  - `src/api/health.py` - Health check endpoints (/health, /ready)
  - `src/utils/metrics.py` - Prometheus metrics integration
  - `src/utils/pool_monitor.py` - Connection pool monitoring
  - `prometheus.yml` - Metrics scraping configuration
- **Security**
  - `src/utils/secrets_manager.py` - AES-256 secrets encryption
  - `scripts/rotate_keys.py` - Automated key rotation script
  - `src/utils/env_validator.py` - Environment validation
  - `src/telegram_bot/middleware/rate_limit.py` - Enhanced rate limiting
- **Infrastructure**
  - `src/utils/shutdown_handler.py` - Graceful shutdown handling
  - `src/utils/database.py` - Optimized database pooling
  - `src/utils/redis_cache.py` - Redis connection management
  - `docker-compose.prod.yml` - Production Docker configuration

#### Testing
- **E2E Tests**: New end-to-end test suite for critical workflows
  - `tests/e2e/test_arbitrage_flow.py` - Complete arbitrage workflow testing (395 lines)
  - `tests/e2e/test_target_management_flow.py` - Target management E2E tests (450+ lines)
  - `tests/e2e/test_notification_flow.py` - Notification delivery flow
  - Tests cover: scanning, trade execution, notifications, multi-level/multi-game flows
- **Integration Tests**
  - `tests/integration/test_dmarket_integration.py` - DMarket API integration tests
- **Test Infrastructure**
  - Fixed virtualenv issues (use `poetry run pytest`)
  - Reduced test collection errors from 17 to 6 (65% improvement)
  - Renamed duplicate test file (`test_api_client.py` → `test_telegram_api_client.py`)

#### Project Management
- **ROADMAP.md** - Unified project roadmap with Phase 4 plan
- **ROADMAP_EXECUTION_STATUS.md** - Detailed execution status tracking
- **PHASE_2_3_COMPLETION_SUMMARY.md** - Complete summary of Phase 2 & 3

### Added - Phase 2: Infrastructure Improvements (April 2026)
- **E2E Tests**: New end-to-end test suite for critical workflows
  - `tests/e2e/test_arbitrage_flow.py` - Complete arbitrage workflow testing (395 lines)
  - `tests/e2e/test_target_management_flow.py` - Target management E2E tests (450+ lines)
  - Tests cover: scanning, trade execution, notifications, multi-level/multi-game flows
- **Updated Copilot Instructions**: Version 5.0 with Phase 2 guidelines
  - Added Code Readability Guidelines section
  - Early returns pattern examples
  - E2E testing best practices
  - Performance optimization guidance (profiling, batching, caching)
  - Function complexity limits (max 50 lines, max 3 nesting levels)
- **Documentation improvements**: Updated dates to January 1, 2026
  - Improved README.md with project status
  - All docs/ files updated with Phase 2 information

### Changed - Phase 2 & 3
- **Code Architecture**
  - Reduced function nesting from 5+ to <3 levels (early returns pattern)
  - Split 100+ line functions into <50 line functions
  - Improved function naming and documentation
- **Test Coverage Goal**: Increased from 85% to 90% (Phase 2 target)
- **Performance**
  - Scanner optimization: ~3x faster with batch processing
  - Connection pooling enabled for all I/O operations
  - Caching strategy improved (TTL-based + Redis persistence)
- **Deployment**
  - Docker images optimized for production
  - Environment variable validation added
  - Health checks integrated with orchestration

### Removed - Cleanup
- Redundant session documentation files (5 files)
  - `docs/ALL_PHASES_COMPLETE.md`
  - `docs/COMMIT_CHECKLIST.md`
  - `docs/WHATS_NEXT.md`
  - `docs/REmainING_IMPROVEMENTS.md`
  - `docs/PHASE_3_PLAN.md`

### Fixed
- Test collection errors reduced from 17 to 6 (65% improvement)
- Virtualenv issues fixed (documented: use `poetry run pytest`)
- File mismatch error for duplicate test files
- Import errors for optional dependencies handled gracefully

### Changed
- **Test Coverage Goal**: Increased from 85% to 90% (Phase 2 target)
- **Code Style**: Enforcing early returns pattern to reduce nesting
- **Performance Focus**: Profiling required before optimization

### Improved
- **Code Readability**:
  - Function length limit enforced (50 lines max)
  - Nesting depth limit (3 levels max)
  - Descriptive variable names required
  - Docstrings for complex functions (>3 params)
- **Testing Strategy**:
  - E2E tests for critical user flows
  - Pytest markers properly configured (e2e, unit, integration)
  - Parallel test execution support

## [1.0.0] - 2025-12-14

### Added
- Initial release of DMarket Telegram Bot
- Multi-level arbitrage scanning (5 levels)
- Target management system (Buy Orders)
- Real-time price monitoring via WebSocket
- Multi-game support (CS:GO, CS2, Rust)
- Market analytics and liquidity analysis
- Internationalization (RU, EN, ES, DE)
- API key encryption and security
- Rate limiting and circuit breaker
- Sentry integration for monitoring
- Comprehensive test suite (372 test files)
- Portfolio management system with P&L tracking
- Backtesting framework for trading strategies
- High-frequency trading mode with balance-stop mechanism
- Discord webhook integration for notifications
- Auto-seller with dynamic pricing and stop-loss

### Security
- API key encryption for user credentials
- Rate limiting to prevent abuse
- Circuit breaker for API protection
- DRY_RUN mode for safe testing

[Unreleased]: https://github.com/Dykij/DMarket-Telegram-Bot/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Dykij/DMarket-Telegram-Bot/releases/tag/v1.0.0


---
🦅 *DMarket Quantitative engine | v7.0 | 2026*

----- 
🦅 *DMarket Quantitative Engine | v7.0 | 2026*