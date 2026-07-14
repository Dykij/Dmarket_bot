# MEMORY — DMarket Quantitative Engine (v14.9)

## 🧠 Strategic Core
The project has evolved from a heuristic-based AI bot to a **Value Detection Scanner + Spread Sniper** with **Balance-Aware Capital Management** (v14.9).

### Key Milestones
- **June 2026 (v14.9)**: Value Detection Scanner refactor. Dual-signal pipeline (VALUE + SPREAD).
  - Relaxed HFT microstructure filters (disabled by default)
  - Expanded scan coverage (500 titles, 50 oracle validations)
  - Vault security fix (Fernet key generation)
  - README + docs updated
- **June 2026 (v14.4)**: Balance-aware trading (8 features). Kelly sizing, drawdown freeze, dynamic max price, lock-aware cap, capital velocity. Full architecture restructuring (9+ files split). Docker multi-stage deployment. 289 tests.
- **June 2026 (v13.0)**: Capital velocity unlocked. Trade lock model fixed.
- **April 2026**: Reached v7.0. AI Debt purged.
- **Rules**: Profit > 5%, No Dota2/TF2, Strict Stop-Loss, Balance Gate, Half Kelly.

### v14.9 Value Detection Scanner (New)

**Primary Signal — VALUE:**
```
rarity_mult × oracle_ask > ask × (1 + FEE_RATE + WITHDRAWAL_FEE + MIN_MARGIN)
```
- Float premium: FN-0 1.20×, dirty BS 1.30×
- Pattern premium: Ruby 5×, Blue Gem 3×, Fire & Ice 5×
- Sticker combo: 4× same = +100%
- Filler demand: +15%

**Secondary Signal — SPREAD:**
```
best_bid > best_ask × (1 + FEE_RATE + WITHDRAWAL_FEE + MIN_MARGIN)
```

**Key Changes:**
- `STRICT_MICROSTRUCTURE_FILTERS=false` (HFT filters off for value scanner)
- `OBI_ENABLED=false`, `OFI_ENABLED=false`, `VWAP_FILTER_ENABLED=false` (etc.)
- `ORACLE_TOP_K_VALIDATE=50` (was 5)
- `MIN_TOTAL_SALES=3` (was 5)
- `BALANCE_RESERVE_USD=5.00` (was $10)
- `FEE_RATE=0.05` (realistic for CS2)

### Technical Stack
- **Languages**: Python 3.13+ (Asyncio, aiohttp, NumPy), Rust (PyO3, serde, ed25519-dalek).
- **Storage**: SQLite (WAL mode, dual DB — OLTP state + OLAP history).
- **Deployment**: Docker multi-stage (x86_64 + ARM64), docker-compose with volumes.
- **Security**: Fernet vault (fixed in v14.9), Rust Ed25519 signing, log redaction.

### v14.4 Balance-Aware Trading (8 Features)

#### 1. Dynamic Max Item Price (v14.4)
```
max_price = max(MAX_SNIPING_PRICE_FLOOR, effective_balance × BALANCE_FRACTION)
effective_balance = max(0, total_balance - BALANCE_RESERVE_USD)
```
At $43 → $5 floor. At $500 → $50. At $2000 → $200.

#### 2. Reserve Buffer ($5) (reduced in v14.9 from $10)
Unspendable safety margin. `BALANCE_RESERVE_USD=5.00`.

#### 3. Fractional Kelly (Half Kelly)
```
f* = win_rate - (1 - win_rate) geopolitical / win_loss_ratio
position = capital × KELLY_FRACTION × f*   (KELLY_FRACTION=0.50)
```

#### 4. Lock-Aware Inventory Cap
Dynamic ceiling: max items = (balance × liquid_fraction) / max_item_price.
`LOCK_AWARE_LIQUID_FRACTION=0.80`.

#### 5. Capital Velocity Constraint
Minimum 0.5× weekly sell-through rate. Pauses buying if locked items exceed velocity.

#### 6. Drawdown Freeze
If balance drops below peak × (1 - threshold), stop buying. `DRAWDOWN_FREEZE_THRESHOLD=0.15`.

#### 7. Balance-Tiered Pre-Filter
`dynamic_max_price` in ranker skips items out of budget before full evaluation.

#### 8. Sandbox Affordable/Missed Report
v14.4 sandbox simulation reports what was affordable vs what was missed due to balance constraints.

### Architecture Restructuring (June 2026 → v14.9)
- **multi_source_oracle** (959 lines → 5 files, max 373 each): models, client, catalog, prices, utils
- **microstructure** (779 lines → 4 files, max 319 each): obi, volume, volatility, signals
- **target_sniping core** (994 → 562 + scanner + scheduler + telemetry)
- **resale** (737 → 260 + 443 + 91): base, dry, prod
- **filter** extract (700 → 519 + ranking + validations)
- **NEW v14.9: value_pipelines.py** — Dual-signal evaluation (VALUE + SPREAD)
- Deprecated: `backtester.py`, `price_analytics.py`, `target_sniping.py` (legacy v10 shims)

### Docker Production (June 2026)
- Multi-stage Dockerfile: Builder → Runtime (~250 MB)
- Supports x86_64 + aarch64/ARM64 (Raspberry Pi 4/5, mini-PCs, Intel Celeron)
- `tini` init, non-root user, health check at `/healthz`
- docker-compose: persistent volumes for data/ and logs/
- Memory limits: 512 MB (main bot), 256 MB (Telegram)

### Telegram Control Bot (June 2026 Fixes)
- 16 admin buttons (8 rows) — STATUS, INVENTORY, BALANCE, SELL-TOP, ANALYZE, TEST, PRICES, CLOCK, REFRESH, PANIC, STOP, START, HELP, LOGOUT, DONATE, CANCEL
- Fixed: `ADMIN_ID` → `ADMIN_IDS`, `CrossMarketOracle` → `MultiSourceOracle`, MarkdownV2 escaping

### Security (June 2026 → v14.9)
- Full security audit: 18+ vulns fixed (3 Critical, 5 High, 5 Medium, 4 Low)
- Fernet encryption for API keys in memory (fixed in v14.9 — proper base64 generation)
- Health server with basic auth middleware
- SecurityAuditor redacts 20+ secret patterns
- Lock file with SHA-256 integrity hash
- `.env` backup files removed (v14.9)

### Research Validated
- Kelly (1956): Position sizing — fractional Kelly as risk-mitigated growth strategy
- Avellaneda & Stoikov (2008): A-S reservation price with inventory skew
- Almgren & Chriss (2000): Slippage gate model
- Easley, López de Prado & O'Hara (2012): VPIN flow toxicity
- Cont, Cucuringu, Zhang (2021): OFI cross-impact of order flow imbalance
- Frontiers AI (2025): LSTM → 20% 6mo vs 5-10% B&H. Mil-Spec mid-tier optimal
- ScienceDirect (2025): 66.9% historical returns. Fees + volatility = main risks
- MultiSourceOracle: free oracles (Market.CSGO + Waxpeer + CSFloat + Steam)

### Environment Variables (v14.9)
New v14.9:
- `VALUE_SCAN_ENABLED=true`
- `VALUE_SCAN_MIN_PREMIUM=1.05`
- `VALUE_SCAN_MIN_PROFIT_PCT=0.5`
- `VALUE_SCAN_MIN_PROFIT_USD=0.20`

Changed v14.9:
- `STRICT_MICROSTRUCTURE_FILTERS=false`
- `OBI_ENABLED=false`
- `OFI_ENABLED=false`
- `VWAP_FILTER_ENABLED=false`
- `ORACLE_TOP_K_VALIDATE=50`
- `MIN_TOTAL_SALES=3`
- `BALANCE_RESERVE_USD=5.00`
- `FEE_RATE=0.05`

### Known Constraints (2026)
- **API Limits**: Oracle rate limits, DMarket circuit breaker at 3 consecutive failures
- **Value Scanner**: Requires real DMarket data (rare items in listings). Sandbox may not find value signals.
- **Single-venue**: Execution only on DMarket (MultiSourceOracle used only as oracle)
- **Balance**: Current $43.91 → dynamic max price ~$5


🦅 *DMarket Quantitative Engine | v14.9 | June 2026*
