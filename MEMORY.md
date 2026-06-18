# MEMORY — DMarket Quantitative Engine (v14.4)

## 🧠 Strategic Core
The project has evolved from a heuristic-based AI bot to a high-speed **Quantitative Arbitrage Engine** with **Balance-Aware Capital Management** (v14.4).

### Key Milestones
- **June 2026 (v14.4)**: Balance-aware trading (8 features). Kelly sizing, drawdown freeze, dynamic max price, lock-aware cap, capital velocity. Full architecture restructuring (9+ files split). Docker multi-stage deployment. 289 tests.
- **June 2026 (v13.0)**: Capital velocity unlocked. Trade lock model fixed.
- **April 2026**: Reached v7.0. AI Debt purged.
- **Rules**: Profit > 5%, No Dota2/TF2, Strict Stop-Loss, Balance Gate, Half Kelly.

### Technical Stack
- **Languages**: Python 3.13+ (Asyncio, aiohttp, NumPy), Rust (PyO3, serde, ed25519-dalek).
- **Storage**: SQLite (WAL mode, dual DB — OLTP state + OLAP history).
- **Deployment**: Docker multi-stage (x86_64 + ARM64), docker-compose with volumes.
- **Security**: Fernet vault, Rust Ed25519 signing, log redaction, chmod hardening.

### v14.4 Balance-Aware Trading (8 Features)

#### 1. Dynamic Max Item Price
```
max_price = max(MAX_SNIPING_PRICE_FLOOR, effective_balance × BALANCE_FRACTION)
effective_balance = max(0, total_balance - BALANCE_RESERVE_USD)
```
At $43 → $5 floor. At $500 → $50. At $2000 → $200.

#### 2. Reserve Buffer ($10)
Unspendable safety margin. `BALANCE_RESERVE_USD=10.00`.
Protects against withdrawal requests, fee spikes, pending order holds.

#### 3. Fractional Kelly (Half Kelly)
```
f* = win_rate - (1 - win_rate) / win_loss_ratio
position = capital × KELLY_FRACTION × f*   (KELLY_FRACTION=0.50)
```
Reduces drawdown by ~50%, keeps 85% of growth rate. Fallback to MAX_POSITION_RISK_PCT if no trade history.

#### 4. Lock-Aware Inventory Cap
Dynamic ceiling: max items = (balance × liquid_fraction) / max_item_price.
Prevents all capital being frozen in trade-lock simultaneously. `LOCK_AWARE_LIQUID_FRACTION=0.80`.

#### 5. Capital Velocity Constraint
Minimum 0.5× weekly sell-through rate. Pauses buying if locked items exceed velocity. `CAPITAL_VELOCITY_MIN=0.50`.

#### 6. Drawdown Freeze
If balance drops below peak × (1 - threshold), stop buying. Only sells allowed. `DRAWDOWN_FREEZE_THRESHOLD=0.15`.

#### 7. Balance-Tiered Pre-Filter
`dynamic_max_price` in ranker skips items out of budget before full evaluation.

#### 8. Sandbox Affordable/Missed Report
v14.4 sandbox simulation reports what was affordable vs what was missed due to balance constraints.

### Architecture Restructuring (June 2026)
- **cs2cap_oracle** (959 lines → 5 files, max 373 each): models, client, catalog, prices, utils
- **microstructure** (779 lines → 4 files, max 319 each): obi, volume, volatility, signals
- **target_sniping core** (994 → 562 + scanner + scheduler + telemetry)
- **resale** (737 → 260 + 443 + 91): base, dry, prod
- **filter** extract (700 → 519 + ranking + validations)
- Deprecated: `backtester.py`, `price_analytics.py`, `target_sniping.py` (legacy v10 shims)

### Docker Production (June 2026)
- Multi-stage Dockerfile: Builder → Runtime (~250 MB)
- Supports x86_64 + aarch64/ARM64 (Raspberry Pi 4/5, mini-PCs, Intel Celeron)
- `tini` init, non-root user, health check at `/healthz`
- docker-compose: persistent volumes for data/ and logs/
- Memory limits: 512 MB (main bot), 256 MB (Telegram)

### Telegram Control Bot (June 2026 Fixes)
- 16 admin buttons (8 rows) — STATUS, INVENTORY, BALANCE, SELL-TOP, ANALYZE, TEST, PRICES, CLOCK, REFRESH, PANIC, STOP, START, HELP, LOGOUT, DONATE, CANCEL
- Fixed: `ADMIN_ID` → `ADMIN_IDS`, `CrossMarketOracle` → `CS2CapOracle`, MarkdownV2 escaping, `sqlite3.Row.get()` → `_row_bool()`, missing `await` on async calls
- Split `cmd_test` into command + button handlers for FSM compatibility

### Security (June 2026)
- Full security audit: 18+ vulns fixed (3 Critical, 5 High, 5 Medium, 4 Low)
- Fernet encryption for API keys in memory (XOR-0xAA removed)
- Health server with basic auth middleware
- SecurityAuditor redacts 20+ secret patterns
- Lock file with SHA-256 integrity hash
- Docker: non-root user (uid 1000), `tini` init, memory cgroups

### Research Validated
- Kelly (1956): Position sizing — fractional Kelly as risk-mitigated growth strategy
- Avellaneda & Stoikov (2008): A-S reservation price with inventory skew
- Almgren & Chriss (2000): Slippage gate model
- Easley, López de Prado & O'Hara (2012): VPIN flow toxicity
- Cont, Cucuringu, Zhang (2021): OFI cross-impact of order flow imbalance
- Frontiers AI (2025): LSTM → 20% 6mo vs 5-10% B&H. Mil-Spec mid-tier optimal
- ScienceDirect (2025): 66.9% historical returns. Fees + volatility = main risks
- CS2Cap: 41 marketplaces. Starter $19/mo (50k req). Pro $79. Quant $179

### Environment Variables (v14.4)
New: `BALANCE_RESERVE_USD`, `MAX_SNIPING_PRICE_FLOOR`, `MAX_SNIPING_PRICE_BALANCE_FRACTION`, `KELLY_ENABLED`, `KELLY_FRACTION`, `KELLY_FLOOR_PCT`, `LOCK_AWARE_CAP_ENABLED`, `LOCK_AWARE_LIQUID_FRACTION`, `CAPITAL_VELOCITY_ENABLED`, `CAPITAL_VELOCITY_MIN`, `DRAWDOWN_FREEZE_ENABLED`, `DRAWDOWN_FREEZE_THRESHOLD`

### Known Constraints (2026)
- **API Limits**: CS2Cap Starter = 50K req/month, DMarket circuit breaker at 3 consecutive failures
- **Latency**: Python GIL bottleneck (compensated by Rust module for critical paths)
- **Single-venue**: Execution only on DMarket (CS2Cap used only as oracle)
- **Balance**: Current $43.91 — most items >$5 automatically filtered by dynamic max price


🦅 *DMarket Quantitative Engine | v14.4 | June 2026*
