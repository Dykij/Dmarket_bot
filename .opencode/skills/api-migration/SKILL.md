---
name: api-migration
description: Use when the user asks to update, migrate, or fix DMarket API endpoints. Trigger keywords: "api migration", "update API", "update endpoint", "deprecated endpoint", "new endpoint", "миграция API", "обнови API", "API v2". Searches for deprecated endpoint paths and replaces them with current v2 equivalents.
---

# DMarket API Migration

Migrate deprecated DMarket API endpoints to their current v2 equivalents.

## Known Deprecations (March 2026)

| Deprecated | Replacement |
|---|---|
| `POST /marketplace-api/v1/user-offers/create` | `POST /marketplace-api/v2/offers:batchCreate` |
| `POST /marketplace-api/v1/user-offers/edit` | `POST /marketplace-api/v2/offers:batchUpdate` |
| `DELETE /exchange/v1/offers` | `POST /marketplace-api/v2/offers:batchDelete` |
| `/price-aggregator/v1/aggregated-prices` | `/marketplace-api/v1/aggregated-prices` |

## Migration Steps

### 1. Find deprecated endpoints

```bash
source .venv/bin/activate
grep -rn "marketplace-api/v1/user-offers/create\|marketplace-api/v1/user-offers/edit\|exchange/v1/offers\|price-aggregator/v1/aggregated-prices" src/ --include="*.py"
```

### 2. Check for v2 format compliance

Current v2 format:
```json
{"requests": [{"assetId": "...", "priceCents": 12345}]}
```

NOT the old v1 format:
```json
{"offers": [{"assetId": "...", "price": {"amount": "123.45", "currency": "USD"}}]}
```

### 3. Verify affected files

Key files that use DMarket API endpoints:
- `src/api/dmarket_api_client/offers.py` — Offer CRUD operations
- `src/api/dmarket_api_client/market.py` — Market data reads
- `src/api/dmarket_api_client/account.py` — Account operations
- `src/api/dmarket_api_client/targets.py` — Target/bid operations

### 4. Run sandbox to verify

```bash
source .venv/bin/activate
ENCRYPTION_KEY="test" python -m tests.sandbox_full_cycle
```

## Related Files

- `src/api/dmarket_api_client/offers.py` — v2 batch endpoints
- `src/api/dmarket_api_client/market.py` — aggregated-prices endpoint
- `src/api/dmarket_api_client/core.py` — Base HTTP client
- [DMarket API Updates Blog](https://dmarket.com/blog/dmarket-public-api-updates/) — Official migration guide
