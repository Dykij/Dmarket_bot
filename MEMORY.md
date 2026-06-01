# MEMORY - DMarket Quantitative Engine (v12.2)

## 🧠 Strategic Core
The project is a high-speed **Intra-DMarket Arbitrage Engine** that exploits
bid-ask spreads within DMarket (no cross-market arbitrage). As of v12.2, the bot
includes production-grade defenses against wash trading, asset reverts, and
unliquid items — plus DMarket API v2 batch endpoints.

### Key Milestones
- **June 2026 (v12.2)**: Asset status tracking, dynamic fee bulk, trimmed mean, liquidity filters, v2 batch APIs
- **June 2026 (v12.0)**: CS2Cap replaces CSFloat. Strategy A (intra-spread) live. 17/17 tests.
- **April 2026 (v7.0)**: AI Debt purged.

### Architecture
- Async Python with native aiohttp. Rust signer optional (faster).
- Bifurcated SQLite: state DB (OLTP) + history DB (OLAP).
- CS2Cap oracle (BUFF163 + 41 markets) for price validation.

### v12.2 New Filters (per Gemini analysis)
1. **Trade Lock Detection**: tracks `trade_protected` and `reverted` statuses
2. **Dynamic Fee**: per-item fee via bulk endpoint (50 items/call)
3. **Trimmed Mean**: detects wash trading (outliers ±24% from mean)
4. **Multi-level Liquidity**: 5 thresholds (80 sales, 23 days, 11 in window, 20d first, 3d last)
5. **API v2 Batch**: 100 items/call for create/edit/delete

### Strategy A: Intra-DMarket Spread
1. Scan 50 items via `/exchange/v1/market/items`
2. Get aggregated prices (best_bid, best_ask) via `/marketplace-api/v1/aggregated-prices`
3. **NEW v12.2**: Bulk fee fetch for all candidates (50/call)
4. Filter: 5%+ spread + liquidity + wash-trading check
5. Validate with CS2Cap oracle (BUFF163 price sanity check)
6. Buy at `best_ask`, list at `best_bid - 0.01` × float premium
7. Track asset status (trade_protected for 7d)
8. Reprice unsold offers every 6h
9. **NEW v12.2**: Sync inventory statuses every 20 cycles

### Constraints
- 7-day Trade Protection: After DMarket buy, item is locked for 7 days.
- 7-day Trade Lock: Steam deposit → DMarket → withdraw = 14 days total.
- DMarket API Limits: 4-5 RPS, 0.22s minimum interval.
- CS2Cap Free Tier: 1K req/month, no bids endpoint (403).

### File Structure
- `src/api/cs2cap_oracle.py` — CS2Cap oracle (BUFF163)
- `src/api/dmarket_api_client.py` — DMarket v1 + v2 endpoints
- `src/core/target_sniping.py` — Main trading loop with all v12.2 filters
- `src/db/price_history.py` — Bifurcated SQLite + asset_status table
- `docs/STRATEGY_ROADMAP.md` — All 6 strategies (A-F)

### Verified
- 25/25 tests passing (`scratch/test_sandbox_v9.py`) — was 17/17 in v12.0
- Real DMarket balance: $43.91
- Real CS2Cap API key: stored in `.env` (gitignored)
- Real DMarket keys in `.env` (gitignored)

---
🦅 *DMarket Intra-Spread Engine | v12.2 | 2026*
