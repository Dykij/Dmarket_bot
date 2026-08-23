---
name: api-integration-specialist
description: 'Use when integrating third-party APIs with proper authentication, error handling, rate limiting, and retry logic. Trigger keywords: "API integration", "API client", "authentication", "OAuth", "API key", "webhook", "REST API". Essential for DMarket API, MultiSourceOracle, Telegram Bot API.'
---

# API Integration Specialist

Expert patterns for integrating third-party APIs with proper authentication, error handling, rate limiting, and retry logic.

## When to Use

- Adding new API integrations to the bot
- Refactoring existing API clients
- Debugging API authentication issues
- Implementing webhook receivers
- Designing API client abstractions

## Core Patterns

### 1. API Client Base Class

```python
import aiohttp
import asyncio
from typing import Any, Optional
from dataclasses import dataclass

@dataclass
class APIConfig:
    base_url: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    timeout: float = 10.0
    max_retries: int = 3
    rate_limit: float = 10.0  # requests per second

class BaseAPIClient:
    def __init__(self, config: APIConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._rate_limiter = asyncio.Semaphore(int(config.rate_limit))

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Any:
        session = await self._get_session()
        url = f"{self.config.base_url}{endpoint}"

        for attempt in range(self.config.max_retries):
            try:
                async with self._rate_limiter:
                    async with session.request(method, url, **kwargs) as resp:
                        if resp.status == 429:
                            retry_after = float(resp.headers.get("Retry-After", 2 ** attempt))
                            await asyncio.sleep(retry_after)
                            continue

                        resp.raise_for_status()
                        return await resp.json()
            except aiohttp.ClientError as e:
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

        raise Exception(f"Max retries exceeded for {method} {endpoint}")
```

### 2. HMAC Authentication (DMarket Pattern)

```python
import hashlib
import hmac
import time

class HMACAuth:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret

    def sign_request(self, method: str, path: str, body: str = "") -> dict:
        timestamp = str(int(time.time()))
        sign_str = timestamp + method + path + body
        signature = hmac.new(
            self.api_secret.encode(),
            sign_str.encode(),
            hashlib.sha256
        ).hexdigest()

        return {
            "X-Api-Key": self.api_key,
            "X-Api-Sign": signature,
            "X-Api-Timestamp": timestamp,
            "Content-Type": "application/json"
        }
```

### 3. Webhook Handler

```python
from aiohttp import web
import hashlib
import hmac

class WebhookHandler:
    def __init__(self, secret: str):
        self.secret = secret

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        expected = hmac.new(
            self.secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def handle(self, request: web.Request) -> web.Response:
        payload = await request.read()
        signature = request.headers.get("X-Signature", "")

        if not self.verify_signature(payload, signature):
            return web.Response(status=401)

        data = await request.json()
        await self.process_event(data)
        return web.Response(status=200)

    async def process_event(self, data: dict):
        # Override in subclass
        pass
```

### 4. Response Caching

```python
import time
from typing import Any, Optional

class APICache:
    def __init__(self, ttl: float = 300.0):  # 5 min default
        self.ttl = ttl
        self._cache: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            timestamp, value = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any):
        self._cache[key] = (time.time(), value)

    def invalidate(self, key: str):
        self._cache.pop(key, None)
```

## DMarket Bot Integration

```python
# DMarket API Client
class DMarketAPI(BaseAPIClient):
    def __init__(self):
        super().__init__(APIConfig(
            base_url="https://api.dmarket.com",
            api_key=os.getenv("DMARKET_API_KEY"),
            api_secret=os.getenv("DMARKET_API_SECRET"),
            rate_limit=10.0
        ))
        self.auth = HMACAuth(self.config.api_key, self.config.api_secret)

    async def get_balance(self) -> dict:
        headers = self.auth.sign_request("GET", "/account/balance")
        return await self.request("GET", "/account/balance", headers=headers)

    async def get_market_items(self, game: str = "cs2", limit: int = 100) -> list:
        params = {"game": game, "limit": limit}
        return await self.request("GET", "/exchange/v2/market/items", params=params)
```

## Anti-patterns

### No timeout on API calls
**Symptom:** Bot hangs indefinitely on network issues
**Fix:** Always set `timeout` in `aiohttp.ClientSession`

### Hardcoded API keys
**Symptom:** Security vulnerability, keys in git history
**Fix:** Use environment variables, never commit keys

### No retry logic
**Symptom:** Single network glitch fails entire operation
**Fix:** Implement exponential backoff with max retries

### Ignoring rate limits
**Symptom:** 429 errors, API key throttled
**Fix:** Use rate limiter (TokenBucket or Semaphore)
