# MEMORY - DMarket Quantitative Engine (v12.0)

## 🧠 Strategic Core
The project is now a high-speed **Intra-DMarket Arbitrage Engine** that exploits
bid-ask spreads within DMarket (no cross-market arbitrage).

### Key Milestones
- **June 2026**: Reached v12.0. CS2Cap replaces CSFloat. Strategy A (intra-spread) live.
- **April 2026**: Reached v7.0. AI Debt purged.
- **Architecture**: Async Python with native aiohttp. Rust signer optional (faster).
- **Rules**: Spread > 5%, MAX_POSITION 30%, MAX_INVENTORY 30 items.

### Technical Stack
- **Languages**: Python 3.11+ (Asyncio, Httpx, NumPy, Pandas).
- **Storage**: SQLite Bifurcated (state DB + history DB).
- **Oracle**: CS2Cap (BUFF163 + 41 markets).
- **Security**: Ed25519 NaCL signing (Python or Rust).

### Known Constraints (2026)
- **7-day Trade Protection**: After DMarket buy, item is locked for 7 days.
- **7-day Trade Lock**: Steam deposit → DMarket → withdraw = 14 days total.
- **DMarket API Limits**: 4-5 RPS, 0.22s minimum interval.
- **CS2Cap Free Tier**: 1K req/month, no bids endpoint (403).
- **CS2Cap Starter ($19/mo)**: 10K req + bids + batch.
- **CS2Cap Pro ($79/mo)**: 100K req + candles + history.

### Strategy A: Intra-DMarket Spread
1. Scan 50 items via `/exchange/v1/market/items`
2. Get aggregated prices (best_bid, best_ask) via `/marketplace-api/v1/aggregated-prices`
3. Filter: `best_bid > best_ask * 1.05` (5%+ spread)
4. Validate with CS2Cap oracle (BUFF163 price sanity check)
5. Buy at `best_ask`, list at `best_bid - 0.01`
6. Reprice unsold offers every 6h

### File Structure
- `src/api/cs2cap_oracle.py` — CS2Cap oracle (BUFF163)
- `src/api/dmarket_api_client.py` — DMarket API v2 (read + write)
- `src/api/market_data_fetcher.py` — DMarket public order book
- `src/api/oracle_factory.py` — Multi-game oracle factory
- `src/core/target_sniping.py` — Main trading loop
- `src/db/price_history.py` — Bifurcated SQLite
- `docs/STRATEGY_ROADMAP.md` — All 6 strategies (A-F)

### Verified
- 14/14 tests passing (`scratch/test_sandbox_v9.py`)
- 6/50 opportunities → $4.57 profit on $38.85 risk (sandbox audit)
- Real DMarket balance: $43.91
- Real CS2Cap API key: stored in `.env` (gitignored)
- Real DMarket keys in `.env` (gitignored)

---
🦅 *DMarket Intra-Spread Engine | v12.0 | 2026*
