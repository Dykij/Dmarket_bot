# MEMORY - DMarket Quantitative Engine (v13.0)

## 🧠 Strategic Core
The project has evolved from a heuristic-based AI bot to a high-speed **Quantitative Arbitrage Engine**.

### Key Milestones
- **June 2026 (v13.0)**: Capital velocity unlocked. Trade lock model fixed — DMarket marketplace allows instant resale.
- **April 2026**: Reached v7.0. AI Debt purged.
- **Architecture**: Microservices (Python Async). Next goal: Rust/Go migration.
- **Rules**: Profit > 5%, No Dota2/TF2, Strict Stop-Loss, Slippage Control < 2%.

### Technical Stack
- **Languages**: Python (Asyncio, Httpx, NumPy, Pandas).
- **Storage**: SQLite (History), Redis (Cache), PostgreSQL (Backend).
- **Security**: Local obfuscated vault (MockMemoryVault). Needs HashiCorp Vault.

### Security Milestones (June 2026)
- **Full security audit**: 18+ vulns found, all fixed (3 Critical, 5 High, 5 Medium, 4 Low)
- **Encryption**: XOR-0xAA removed → Fernet + HashiCorp Vault (hvac). ENCRYPTION_KEY enforced at DRY_RUN=false
- **Health server**: Added basic auth middleware (HEALTH_USERNAME/HEALTH_PASSWORD)
- **Admin access**: @_admin_only on all handlers + centralized router filter + ThrottlingMiddleware (0.5s cooldown)
- **Log security**: SecurityAuditor redacts 20+ secret patterns at log emission. Notifier uses _redacted_url to avoid CVE-2026-27003
- **Vault discipline**: All DMarketAPIClient construction goes through vault (state.py, resilience.py, test.py)
- **Webhook secret validation**: Documented but deferred until webhook mode is implemented (currently polling)
- **Lock file**: SHA-256 integrity hash prevents PID tampering
- **BOT_VERSION**: Removed from public Telegram commands (/start, /settings)
- **pip-audit**: Added to pre-commit hooks

### v13.0 Critical Correction (June 2026)
- **Trade Lock Model Fixed**: DMarket marketplace allows IMMEDIATE re-listing of bought items.
  Steam Trade Protection blocks withdrawal to Steam only, NOT re-selling on DMarket marketplace.
  Previous 168h (7-day) lock was WRONG — artificially freezing capital. `TRADE_LOCK_HOURS=0`.
- **Fee Model**: 2-10% DMarket sell fee (liquidity-based). 4 tiers: 2% (≥50vol), 5% (≥10), 7% (≥5), 10% (<5).
  Withdrawal fee 2% added to net PnL. Hot-fee items at 2-3% via `/sell-items-promo`.
- **Capital Velocity**: `resale_cycle_limit=1`, auto-resale after every buy. Cash-to-cash cycle target <24h.
- **Exclusive Inventory**: Items with rare floats (FN-0), expensive stickers (>$2), or rare phases (Ruby/Sapphire)
  are auto-marked `exclusive` and skipped during resale.
- **Fee-Aware Strategy**: Min spread = `total_fee * 2 + 3%`. Skip items where gross spread can't cover fees.
- **CS2Cap Ask Reference**: List price now uses CS2Cap lowest ask across 41 marketplaces (not DMarket bid).
- **Float Premium Off**: DMarket prices already incorporate float. `FLOAT_PREMIUM_ENABLED=false` by default.

### Research Validated
- Frontiers AI (2025): LSTM/NHiTS → 20% 6mo return vs 5-10% B&H. Mil-Spec mid-tier optimal.
- ScienceDirect (2025): 66.9% historical returns. Fees + volatility = main risks. Diversified portfolios outperform.
- CS2Cap: 41 marketplaces. Starter $19/mo (50k req). Pro $79 (candles+history). Quant $179 (arb scanner).

### Known Constraints (2026)
- **API Limits**: Strict Rate Limit Governor (aiometer) is active.
- **Latency**: Python GIL is the current bottleneck.
- **Single-venue**: Execution only on DMarket. Multi-venue (Skinport/CSFloat) is next step.

---
🦅 *DMarket Quantitative Engine | v13.0 | 2026*
