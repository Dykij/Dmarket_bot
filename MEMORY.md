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

### Known Constraints (2026)
- **7-day Trade Ban**: Cross-exchange flipping is discouraged; intra-exchange flipping is preferred.
- **API Limits**: Strict Rate Limit Governor (aiometer) is active.
- **Latency**: Python GIL is the current bottleneck.

---
🦅 *DMarket Quantitative Engine | v7.0 | 2026*
