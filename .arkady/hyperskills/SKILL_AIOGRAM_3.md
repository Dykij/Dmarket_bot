# HyperSkill: Aiogram 3

## 1. Documentation Summary
Asynchronous framework for Telegram Bot API. Uses context-based handlers and middleware.

## 2. API Limits & Constraints
- Rate Limits: 10 requests/sec (Standard)
- Token Quota: 1M per minute (Internal Gemini)

## 3. Pydantic Models (Example)
```python
from pydantic import BaseModel
class Aiogram3Item(BaseModel):
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
