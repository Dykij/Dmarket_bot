# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/v2.0.0.html).


## [14.8.1] - 2026-06-24
### 🦅 v14.8.1 Wide-Net Conveyor + Low-Fee + DMarket-Internal Underpriced

#### Added
- **Low-fee items scan** — `src/api/dmarket_api_client/market.py` now parses the
  `/exchange/v1/customized-fees` `reducedFees` list and `src/core/target_sniping/scanner.py`
  fetches their cheapest listings for the pipeline.
- **DMarket-internal underpriced detection** — `src/core/target_sniping/underpriced.py`
  flags listings cheaper than the local price-history percentile. Falls back to
  DMarket `/last-sales` when available (currently requires JWT auth, so local
  history is the primary source).
- **Unit tests** for underpriced percentile logic and history-based detection
  (`tests/unit/test_underpriced.py`).

#### Changed
- `.env` and `src/config.py` — `AGG_SCAN_TOP_N=100`, `PRICE_RANGE_MAX_PAGES=10`,
  `PRICE_RANGE_MAX_TITLES=200`, `LISTINGS_FETCH_LIMIT=20`,
  `CROSS_MARKET_TARGET_MARGIN=0.02`, `CROSS_MARKET_TARGET_MAX_PER_CYCLE=20`.
- `src/core/limit_orders.py` — cross-market targets are sorted by margin and
  session-level dedup is applied via `_placed_cross_targets`.
- `src/core/target_sniping/filter.py` — uses reduced fee from low-fee scan and
  allows DMarket-internal underpriced as a fourth opportunity gate.
- `src/utils/config_watcher.py` — hot-reload keys for new v14.8.1 settings.
- `tests/unit/test_v12_4_components.py` — updated to reflect that 503 no longer
  trips the circuit breaker.

## [14.8.0] - 2026-06-24
### 🦅 v14.8 Cross-Market Target Discovery — Fix Bot Opportunity Pipeline

#### Fixed
- **DMarket aggregated-prices 503 handling** — `503 Service Unavailable` no longer
  trips the circuit breaker, allowing transient DMarket errors to retry cleanly.
- **Over-strict microstructure filters** — `STRICT_MICROSTRUCTURE_FILTERS` now
  defaults to `false`; OBI/OFI/VWAP/VPIN/Roll/Adverse-Selection/Vol-Regime gates
  are skipped for low-balance CS2 markets where they killed every candidate.
- **Fee model mismatch** — `WITHDRAWAL_FEE_RATE` lowered to `0.5%` and
  `MIN_SPREAD_PCT` to `0.5%` so cross-market edges are not discarded by
  pessimistic cost assumptions.
- **Cross-market buy list_price** — `limit_orders._execute_cross_market_targets`
  now posts DMarket buy targets derived from CS2Cap lowest ask minus fees
  instead of using the DMarket best ask.
- **Cross-market fee validation** — `evaluate_fee_slippage_tod` accepts a
  `cs_ask_price` reference so cross-market discounts are validated against
  the external venue price.

#### Added
- **Cross-market target executor** — `src/core/limit_orders.py`:
  `_execute_cross_market_targets()` posts up to
  `CROSS_MARKET_TARGET_MAX_PER_CYCLE` DMarket buy targets per cycle.
- **CS2Cap batch priming for targets** — `src/core/target_sniping/core.py`
  fetches `CS2Cap` snapshots for aggregated-price titles so cross-market
  targets have fresh reference data.
- **Cross-market underpriced gate** — `src/core/target_sniping/filter.py`
  flags DMarket items priced below CS2Cap ask minus target fee as
  `cross_market_target` candidates.
- **Liquidity gate** — `MIN_BID_ASK_COUNT` filter rejects items with
  insufficient order-book depth.
- **Config hot-reload keys** — `src/utils/config_watcher.py` watches new
  cross-market and filter env vars.
- **Sandbox diagnostic script** — `scripts/sandbox_filter_check.py` simulates
  the full filter/target pipeline with real DMarket + CS2Cap data.
- **API diagnostic script** — `scripts/test_dmarket_api.py` checks DMarket
  balance and aggregated-prices connectivity.

#### Changed
- `src/config.py` — env overrides for `MIN_SPREAD_PCT`,
  `WITHDRAWAL_FEE_RATE`, `MIN_TOTAL_SALES`, `MIN_BID_ASK_COUNT`,
  `INTRA_MIN_SPREAD_PCT=0.3`, and new `CROSS_MARKET_TARGET_*` settings.
- `.env` — `DRY_RUN=true`, relaxed spreads/fees, enabled price-range scan,
  limit orders, and cross-market targets.
- `tests/unit/test_v12_selective_cs2cap.py` — isolated from `.env` so unit
  tests are deterministic.
- `ANALYSIS_REPORT.md` — removed; analysis was performed and converted into
  these code changes.

## [14.6.0] - 2026-06-21
### 🦅 v14.6 Value Detection Layers — TA Site Analysis Integration

#### Added — v14.6 Value Detection (9 layers)
- **Float Premium (ENABLED)** — `FLOAT_PREMIUM_ENABLED=true` now default.
  Premiums: FN double-zero 1.25×, FN-0 1.20×, FT-0 1.15× (trade-up demand),
  MW-0 1.08×, dirty BS (0.95+) 1.30×.
- **Round-Float Detection** — Collectors pay premium for floats at 0.125, 0.25,
  0.375, 0.5, 0.625, 0.75, 0.875 (+15%).
- **Float-Date Detection** — `0.DDMMYYYYxxxxx` encodes dates (e.g.
  0.21021992xxxx = 21 Feb 1992). +8% premium for date floats.
- **Pattern Premium** — Doppler phases (Ruby/Sapphire 5×, Emerald/Black Pearl
  4×, Phase 2 1.5×, Phase 4 1.3×), Blue Gem Case Hardened (3×), Fire & Ice
  Marble Fade (5×), Crimson Web 3+ webs (2×), Fade %.
- **Sticker Combo Calculator** — 4 identical stickers = +100% of one sticker,
  same team/event 3+ stickers = +10%, Katowice 2014 (28 variants, special
  15% handling), worn stickers = 0.
- **Filler Skin Tracker** — 35 well-known filler skins get +15% demand
  multiplier (higher trade-up contract demand).
- **Seasonal Timing Engine** — Dynamic spread threshold based on:
  - Seasonal: spring +10%, summer −10%, autumn +8%, year-end −8%
  - Weekly: Wednesday +5% (drop reset dip)
  - Hourly: daytime +3% (selling pressure), nighttime −3% (buying pressure)
- **Commission Optimizer** — Items with 2% fee get +15% score boost in ranker.
  Filler skins get +8% score boost (faster turnover).
- **Dirty BS, Round-Float, Float-Date** integrated into `list_price` in filter
  pipeline (all trigger adjusted value for sell pricing).

#### Changed
- **`src/config.py`** — `FLOAT_PREMIUM_ENABLED=true` by default,
  `BOT_VERSION=v14.6.0`, 8 new env-configurable v14.6 flags.
- **`src/core/target_sniping/pricing.py`** — Complete rewrite: expanded float
  premium table, phase/paint premium dictionaries with Blue Gem, Fire & Ice,
  Crimson Web seeds, Fade % estimator, `_is_float_date()`, `is_dirty_bs()`.
- **`src/core/target_sniping/filter.py`** — Added 5 value detection layers
  between honest-listing and is_rare flag. Seasonal timing applied to
  `INTRA_MIN_SPREAD_PCT`. Filler/sticker/float-date bonuses in list_price.
- **`src/core/target_sniping/ranking.py`** — Commission optimizer (+15% for
  low-fee items, +8% for filler skins) in `rank_candidates_by_spread()`.
- **`src/analytics/stickers_evaluator.py`** — Complete rewrite: combo premium
  (4× stick, team/event match, Katowice 2014), 28 Katowice 2014 sticker prices,
  `calculate_combo_premium()` method.

#### Added — New Modules
- **`src/analysis/seasonal.py`** — Seasonal/weekly/hourly timing multipliers.
  Composite `get_timing_multiplier()` for dynamic spread threshold.
- **`src/analytics/filler_tracker.py`** — 35 filler skin names + `is_filler()`
  and `get_filler_multiplier()` helpers.
- **`tests/test_v14_6_value_detection.py`** — 52 unit tests covering all new
  layers (float, pattern, sticker, seasonal, filler, dirty BS, round float).

#### Fixed
- **`tests/sandbox_full_cycle.py`** — Added missing `_print_micro_summary()`
  and `_print_bottleneck()` report helper functions. Updated to v14.6 with
  value detection in market scan step.

---

## [14.4.0] - 2026-06-17
### 🐳 Docker + v14.4 Balance-Aware Trading + Full Restructuring

#### Added — v14.4 Balance-Aware Trading (8 features)
- **Dynamic Max Item Price**: `max($5.00 floor, balance × 10%)` adapts to account size.
  At $43 → $5, at $500 → $50, at $2000 → $200.
- **Reserve Buffer**: `BALANCE_RESERVE_USD=$10` unspendable safety margin.
  `effective_balance = max(0, balance - reserve)`.
- **Fractional Kelly Position Sizing**: Half Kelly (KELLY_FRACTION=0.50).
  Reduces drawdown by ~50% while keeping 85% of growth rate.
  Config: `KELLY_ENABLED`, `KELLY_FRACTION`, `KELLY_FLOOR_PCT`.
- **Lock-Aware Inventory Cap**: `≤80% capital in trade-lock simultaneously`.
  Formula: `max_items = (balance × liquid_fraction) / max_item_price`.
  Config: `LOCK_AWARE_CAP_ENABLED`, `LOCK_AWARE_LIQUID_FRACTION`.
- **Capital Velocity Constraint**: Minimum 0.5× weekly sell-through rate.
  Pauses buying if locked items exceed velocity threshold.
  Config: `CAPITAL_VELOCITY_ENABLED`, `CAPITAL_VELOCITY_MIN`.
- **Drawdown-Aware Spending Freeze**: Stop buying at >15% drawdown from peak balance.
  Only sells allowed until recovery. Config: `DRAWDOWN_FREEZE_ENABLED`,
  `DRAWDOWN_FREEZE_THRESHOLD`.
- **Balance-Tiered Pre-Filter**: `dynamic_max_price` in ranker skips items out of budget.
- **Sandbox Affordable/Missed Report**: v14.4 balance-aware simulation output.

#### Added — Docker Production Deployment
- **Multi-stage Dockerfile**: Builder (Rust + Python deps) → Runtime (~250 MB).
  Supports x86_64 + aarch64/ARM64 (Raspberry Pi 4/5, mini-PCs).
  `tini` init, non-root user, health check via `/healthz`.
- **docker-compose.yml**: Single-service + optional Telegram admin bot.
  Volume mounts for `data/` (SQLite) and `logs/` (persistent).
  Memory limits: 512M (main), 256M (telegram).
- **.dockerignore**: +Rust target/ exclusion (saves 432 MB).

#### Changed — Architecture Restructuring (9+ files split)
- **`src/core/target_sniping/core.py`** (994→562 lines): extracted `_ScannerMixin`,
  `_SchedulerMixin`, `_TelemetryMixin` into separate files.
- **`src/api/cs2cap_oracle.py`** (959→subpackage): split into `models.py`,
  `client.py`, `catalog.py`, `prices.py`, `utils.py` (max 373 lines).
- **`src/analysis/microstructure.py`** (779→subpackage): split into `obi.py`,
  `volume.py`, `volatility.py`, `signals.py` (max 319 lines).
- **`src/core/target_sniping/resale.py`** (737→260+443+91): split into
  `resale.py`, `resale_dry.py`, `resale_prod.py`.
- **`src/core/target_sniping/filter.py`** (700→519): extracted `ranking.py`,
  `validations.py`.
- **Deprecated shims**: `backtester.py`, `price_analytics.py`,
  `target_sniping.py` (legacy v10) kept as re-export stubs.

#### Fixed — Telegram Control Bot (Total Refactoring)
- Fixed `Config.ADMIN_ID` → `Config.ADMIN_IDS` in facade and all commands.
- Fixed `CrossMarketOracle` dead import → `CS2CapOracle` in `views.py`.
- Fixed `format_status()` MarkdownV2 entity parsing at offset 419.
- Fixed `format_inventory_summary()` `sqlite3.Row.get()` → `_row_bool()` helper.
- Fixed `cmd_sell_top`/`cb_sell_top` list-vs-int comparison.
- Fixed `cb_analyze`/`cmd_analyze` missing `await` on async `analyze_recent_trades()`.
- Added `BTN_TEST`, `BTN_PRICES`, `BTN_CLOCK`, `BTN_REFRESH` buttons (16 total, 8 rows).
- Split `cmd_test` into `cmd_test` (command) + `cmd_test_btn` (button) to fix FSM injection.
- Consolidated duplicate `_fetch_balance_data()` into `resilience.py`.

#### Tests
- **102 bottleneck tests** (`tests/test_bottlenecks.py`): microstructure validation,
  quota tracking, DB stress, validator coverage.
- **289 total tests** passing (unit + bottleneck + sandbox).
- Sandbox updated to v14.4 with balance-aware Affordable/Missed report.

#### Documentation
- **README.md**: Updated to v14.4. Added Docker deployment section, Raspberry Pi /
  mini-PC compatibility, balance-aware trading docs, new architecture diagrams,
  full environment variable reference.


## [13.0.0] - 2026-06-17
### 🔓 Capital Velocity Unlocked — Instant Marketplace Resale

#### Critical Fix — DMarket Trade Protection Model
- **TRADE_LOCK_HOURS=0**: DMarket allows IMMEDIATE re-listing of marketplace-bought items.
  Steam Trade Protection blocks withdrawal to Steam only, not re-selling on DMarket.
  Previous hardcoded 168h (7-day) lock was artificially freezing capital.
  ([DMarket Trade Protection blog Sep 2025](https://dmarket.com/blog/steam-trade-protection-dmarket-update/))
- **Config.TRADE_LOCK_HOURS**: env-configurable, default 0. Set to positive hours if items
  come from Steam deposits (not marketplace instant-buys).
- **resale_cycle_limit = 1**: resale EVERY cycle, not every 10 cycles.
- **auto_resale() after every execution**: items are listed within seconds of purchase.

#### Fee System Overhaul
- **10% fee tier** for illiquid items (volume < 5). DMarket actual range: 2-10%.
  Previous: 2%/5%/7% with 5% fallback. Now: 2%/5%/7%/10%.
- **title_volume bug fixed**: `get_item_fee_bulk()` now receives `item_id_to_title` mapping
  from core.py. Previous: volume lookup always returned 0 (5% fallback).
  Now: uses `agg_prices` volume to estimate per-item liquidity fee.
- **Withdrawal fee** (2%) added to `validate_arbitrage_profit()` in filter.py.
  Config: `WITHDRAWAL_FEE_RATE = 0.02`.
- **Fee-aware minimum spread gate**: skip items where `spread < total_fee * 2 + 3%`.
  Prevents buy on items whose gross spread can't cover fees.

#### Pricing & Listing Fixes
- **CS2Cap ask price as list reference**: `list_price = cs2cap_min_price * 0.97` when
  CS2Cap data available. Previous: used only DMarket bid. Matches user strategy
  "цена CS2Cap + комиссия".
- **Float premium off by default**: `FLOAT_PREMIUM_ENABLED=false`. DMarket prices
  already incorporate float discount → applying premium was double-counting.
  Enable via env `FLOAT_PREMIUM_ENABLED=true`.

#### Inventory Management
- **Exclusive (keep-forever) flag**: column `exclusive` in `virtual_inventory`.
  Auto-detection: FN-0 float, expensive stickers (>$2), rare phase/pattern.
  Exclusive items are skipped during `auto_resale`.
- **Total inventory cap**: `MAX_TOTAL_INVENTORY_VALUE` ($100) and
  `MAX_TOTAL_INVENTORY_ITEMS` (30). Prevents unbounded inventory growth.

#### Strategy Integration (from research)
- **StickerEvaluator** integrated into v13 filter pipeline. Detects rare stickers
  (Katowice 2014, Crown Foil, Howl) → flags item as exclusive if value >$2.
- **Pattern/phase premium**: `_calculate_pattern_premium()` for Doppler Ruby/Sapphire,
  Emerald, Black Pearl, Phase 2/4. `has_rare_phase_or_pattern()` for exclusive flag.
- **lock_days=0** in all `validate_arbitrage_profit()` calls. TVM penalty was
  incorrect for marketplace-to-marketplace trading.

#### Research-Backed
- Frontiers AI paper (Guede-Fernández 2025): LSTM/NHiTS → 20% 6mo return,
  Mil-Spec mid-tier optimal, diversification improves Sharpe.
- ScienceDirect (Reichenbach 2025): 66.9% historical returns, fees + volatility = main risks.
- CS2Cap pricing: Starter $19 (50k req), Pro $79 (candles + history), Quant $179 (arb scanner).


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