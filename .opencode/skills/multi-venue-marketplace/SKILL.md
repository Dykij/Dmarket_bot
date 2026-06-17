---
name: multi-venue-marketplace
description: Use when the user asks to add support for a new marketplace (Skinport, CSFloat, BitSkins, etc.) or integrate a new trading API alongside DMarket. Trigger keywords: "add marketplace", "new venue", "Skinport API", "CSFloat API", "BitSkins", "multi-venue", "cross-market". Based on bitskins-api skill (⭐16 on SkillsMP), adapted for DMarket bot architecture.
---

# Multi-Venue Marketplace Integration

Guide for adding new CS2 skin marketplace APIs to the bot. Pattern based on the BitSkins API skill and DMarket's existing integration.

## Venue Registry

Current status:

| Venue | Status | API Type | Integration |
|-------|--------|----------|-------------|
| DMarket | ✅ Production | REST v2 | `src/api/dmarket_api_client/` |
| CS2Cap | ✅ Oracle (prices only) | REST | `src/api/cs2cap_oracle.py` |
| Skinport | 🚧 Planned | REST | Not started |
| CSFloat | 🚧 Planned | REST | Not started |
| BitSkins | 🚧 Planned | REST v2 + WebSocket | Not started |

## Adding a New Venue

### Phase 1: API Client

Create `src/api/<venue>_client.py` following DMarket's pattern:

```python
"""
<Venue> API Client — CS2 skin marketplace.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("<Venue>API")

class <Venue>APIClient:
    BASE_URL = "https://api.<venue>.com"

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._session = None

    async def _request(self, method: str, path: str, **kwargs) -> Dict:
        """Rate-limited API request with retry."""
        ...

    # Market data
    async def search_items(self, game: str, filters: Dict) -> List[Dict]:
        """Search marketplace listings."""
        ...

    async def get_item_price(self, item_id: str) -> float:
        """Get current lowest ask price."""
        ...

    # Trading
    async def buy_item(self, item_id: str, max_price: float) -> Dict:
        """Purchase an item from the marketplace."""
        ...

    async def list_item(self, asset_id: str, price: float) -> Dict:
        """List an item for sale."""
        ...

    # Account
    async def get_balance(self) -> float:
        """Get account balance."""
        ...

    async def get_inventory(self) -> List[Dict]:
        """Get account inventory."""
        ...
```

### Phase 2: Oracle Integration

Add venue to `OracleFactory`:

```python
# src/api/oracle_factory.py
elif venue == "skinport":
    from src.api.skinport_client import SkinportAPIClient
    return SkinportAPIClient(api_key=os.getenv("SKINPORT_API_KEY"))
```

### Phase 3: Strategy Extension

Add cross-market pricing to the strategy engine:

```python
# src/strategies/cross_market.py
class CrossMarketStrategy:
    VENUE_MAP = {
        "dmarket": DMarketAPIClient,
        "skinport": SkinportAPIClient,
        "csfloat": CSFloatAPIClient,
    }

    async def find_arbs(self, title: str) -> List[Dict]:
        """Find arbitrage opportunities across venues."""
        buys = []
        sells = []
        for venue_name, client_cls in self.VENUE_MAP.items():
            price = await self.get_price(venue_name, title)
            buys.append({"venue": venue_name, "price": price["ask"]})
            sells.append({"venue": venue_name, "price": price["bid"]})
        # Sort by cheapest buy, most expensive sell
        return self._match_arbs(buys, sells)
```

### Phase 4: Configuration

Add to `.env`:
```env
# Multi-venue trading
SKINPORT_API_KEY=
CSFLOAT_API_KEY=
BITSKINS_API_KEY=
MULTI_VENUE_ENABLED=false
```

## API Authentication Patterns

| Venue | Auth Method | Header | Key Format |
|-------|------------|--------|------------|
| DMarket | Ed25519 signature | `X-Api-Key` + signature | 64-char hex secret |
| Skinport | API key | `Authorization: Bearer` | sk_live_... |
| CSFloat | API key | `Authorization: Bearer` | csf_... |
| BitSkins | API key | `x-apikey` | bs_... |

## Rate Limiting

All venues implement the bot's standard rate limiter:
```python
from src.api.dmarket_api_client.backoff import CircuitBreaker, jittered_sleep

class <Venue>APIClient:
    def __init__(self, ...):
        self._breaker = CircuitBreaker("<venue>", failure_threshold=3)
        self._request_delay = 1.0
```

## Price Normalization

All prices must be normalized to USD float:
```python
def normalize_price(raw_price: Any, unit: str = "cents") -> float:
    """Normalize venue-specific price format to USD float."""
    if unit == "cents":
        return float(raw_price) / 100.0
    elif unit == "usd":
        return float(raw_price)
    raise ValueError(f"Unknown unit: {unit}")
```

## References

- Source skill: https://github.com/dvcrn/openclaw-skills-marketplace/tree/main/plugins/bluesyparty-src--bitskins/skills/bitskins-api
- SkillsMP: https://skillsmp.com
- DMarket API docs: https://docs.dmarket.com/v1/swagger.html
- CS2Cap API: https://docs.cs2cap.com
