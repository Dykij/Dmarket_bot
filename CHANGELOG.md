# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]

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
- **New Games Support**: Added Dota 2, TF2, Rust to `WaxpeerGame` enum
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
- **Liquidity Checks** - Skips items with < 5 dAlgoly sales on Waxpeer
- **Net Profit Calculation** - Formula: `(Waxpeer_Price * 0.94) - DMarket_Price`

Key classes:
- `CrossPlatformArbitrageScanner` - MAlgon scanner class
- `ArbitrageOpportunity` - Data class for opportunities
- `ScanConfig` - Configuration dataclass
- `ArbitrageDecision` enum - BUY_INSTANT, BUY_AND_HOLD, SKIP

#### New Handler: `src/telegram_bot/handlers/waxpeer_handler.py`
- `waxpeer_menu_handler()` - MAlgon Waxpeer menu
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
  - `get_waxpeer_keyboard()` - MAlgon Waxpeer menu (balance, listings, repricing)
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
  - Removed trAlgoling whitespace and blank lines with whitespace
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
- Updated dates in 12+ documentation files from 2025 to January 2026
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

### Added - Phase 2 & 3: Production Ready (January 2026)

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
- **ROADMAP_EXECUTION_STATUS.md** - DetAlgoled execution status tracking
- **PHASE_2_3_COMPLETION_SUMMARY.md** - Complete summary of Phase 2 & 3

### Added - Phase 2: Infrastructure Improvements (January 2026)
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
  - `docs/REMAlgoNING_IMPROVEMENTS.md`
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
- Multi-game support (CS:GO, Dota 2, TF2, Rust)
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
