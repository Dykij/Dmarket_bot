# HyperSkill: DMarket API

## 1. Documentation Summary
DMarket API v1.1 using Ed25519 signatures. Core endpoints: /marketplace-api/v1/items, /account/v1/balance. Supports WebSocket for real-time inventory updates. Rate limits: 10/sec.

## 2. API Limits & Constraints
- Rate Limits: 10 requests/sec (Standard)
- Token Quota: 1M per minute (Internal Gemini)

## 3. Pydantic Models (Example)
```python
from pydantic import BaseModel
class DMarketAPIItem(BaseModel):
    id: str
    price: float
    currency: str = "USD"
```

## 4. Code Snippets (Best Practices)
```python
# Async Implementation
async def fetch_data():
    pass
```

## 5. Typical Errors & Anti-Patterns
- **429 Too Many Requests**: Handle with exponential backoff.
- **Synchronous I/O**: Never use 'requests' inside async handlers.
