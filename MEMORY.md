# MEMORY - DMarket Quantitative Engine (v7.0)

## 🧠 Strategic Core
The project has evolved from a heuristic-based AI bot to a high-speed **Quantitative Arbitrage Engine**. 

### Key Milestones
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

### Known Constraints (2026)
- **7-day Trade Ban**: Cross-exchange flipping is discouraged; intra-exchange flipping is preferred.
- **API Limits**: Strict Rate Limit Governor (aiometer) is active.
- **Latency**: Python GIL is the current bottleneck.

---
🦅 *DMarket Quantitative Engine | v7.0 | 2026*
