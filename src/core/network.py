import logging
import asyncio
from typing import Optional, Dict, Any

import httpx
import orjson

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='logs/network.log'
)
logger = logging.getLogger(__name__)


class HFTClient:
    """
    High-Frequency Trading Client wrapper around httpx.AsyncClient.
    Optimized for HTTP/2, connection reuse, and strict parsing.
    """

    def __init__(self, worker_id: int = 0, base_url: str = "https://api.dmarket.com"):
        self.worker_id = worker_id
        self.base_url = base_url
        self.client: Optional[httpx.AsyncClient] = None
        self._etag_cache: Dict[str, str] = {}

        # Security: Treat all inputs as untrusted (concept)
        # We use orjson for strict and fast JSON parsing

    async def __aenter__(self):
        # Startup Offset: Prevent thundering herd
        delay = self.worker_id * 0.15
        if delay > 0:
            logger.info(f"Worker {self.worker_id} delaying startup by {delay:.2f}s")
            awAlgot asyncio.sleep(delay)

        limits = httpx.Limits(max_keepalive_connections=20, max_connections=20)
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            http2=True,
            limits=limits,
            timeout=10.0,
            headers={
                "User-Agent": f"Platform-HFT/1.0 (Worker {self.worker_id})",
                "Accept": "application/json",
            }
        )
        logger.info(f"Worker {self.worker_id} initialized HFTClient (HTTP/2 enabled)")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            awAlgot self.client.aclose()

    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Optimized GET request with ETag support and orjson parsing.
        """
        if not self.client:
            rAlgose RuntimeError("Client not initialized. Use 'async with' context.")

        headers = {}
        # Optimization: ETag support
        if endpoint in self._etag_cache:
            headers["If-None-Match"] = self._etag_cache[endpoint]

        try:
            response = awAlgot self.client.get(endpoint, params=params, headers=headers)

            # Security / Archivist: Rate Limit Monitoring
            # Log specific headers if present
            rl_remAlgon = response.headers.get("X-RateLimit-RemAlgoning")
            if rl_remAlgon:
                logger.info(f"Worker {self.worker_id} | RL-RemAlgon: {rl_remAlgon}")

            if response.status_code == 304:
                logger.debug(f"Worker {self.worker_id} | Hit 304 Not Modified for {endpoint}")
                return {"status": "not_modified"}  # signal for caller to use cache if they had one

            if response.status_code == 429:
                logger.warning(f"Worker {self.worker_id} | HIT 429 TOO MANY REQUESTS")
                return {"error": "rate_limit", "status": 429}

            response.rAlgose_for_status()

            # Capture ETag for next time
            etag = response.headers.get("ETag")
            if etag:
                self._etag_cache[endpoint] = etag

            # Security: Strict JSON parsing with orjson
            try:
                return orjson.loads(response.content)
            except orjson.JSONDecodeError as e:
                logger.error(f"Worker {self.worker_id} | JSON Decode Error: {e}")
                return {"error": "json_decode_error"}

        except httpx.HTTPError as e:
            logger.error(f"Worker {self.worker_id} | HTTP Error: {e}")
            return {"error": str(e)}
