# Rate Limits API Reference

**Verified against live Swagger**: `https://docs.dmarket.com/v1/swagger.json` (DMarket trading API v2.0.0) on 2026-09-27.

## Limits
Instead of a flat 10 req/s, DMarket applies different rate limits by endpoint.

Per `src/api/dmarket_api_client/rate_limiter.py` (`ENDPOINT_LIMITS`):
- `/marketplace-api/v1/fee`: 110.0 req/s
- `/marketplace-api/v2/offers`: 10.0 req/s
- `/marketplace-api/v1/aggregated-prices`: 10.0 req/s
- `/marketplace-api/v1/low-fee-items`: 6.0 req/s
- `/trade-aggregator/v1/last-sales`: 6.0 req/s
- Default for others: 20.0 req/s

The bot natively uses a safety margin (e.g., 50%) to avoid 429s.

See `docs/DMARKET_API_FULL_SPEC.md` for full field details.
