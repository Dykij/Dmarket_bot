"""
core.py — DMarketAPIClient orchestrator.

Holds the lifecycle (init, session, close) and the request pipeline
(signing, rate limit, dry-run guard, retries). The high-level endpoint
groups (market, account, offers, targets, fees) live in sibling mixin
modules and are composed here.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import time
import urllib.parse
from typing import Any, Dict, Optional

import aiohttp
import structlog
from nacl.signing import SigningKey
from tenacity import retry, stop_after_attempt, wait_exponential

from .account import _AccountMixin
from .exceptions import SecurityViolation  # noqa: F401  (re-exported)
from .fees import _FeesMixin
from .market import _MarketMixin
from .offers import _OffersMixin
from .targets import _TargetsMixin

logger = structlog.get_logger("DMarketAPI")

# Preserve the original module-level vault import for backward compat
from src.utils.vault import vault  # noqa: F401


class DMarketAPIClient(  # type: ignore[misc]
    _MarketMixin,
    _AccountMixin,
    _OffersMixin,
    _TargetsMixin,
    _FeesMixin,
):
    """DMarket Trading API v2 Client (TargetSniper Optimized Async)."""

    BASE_URL = "https://api.dmarket.com"

    def __init__(
        self,
        public_key: str,
        secret_key: str,
        base_url: str = "https://api.dmarket.com",
    ) -> None:
        self.public_key = public_key
        self.secret_key = secret_key
        self.BASE_URL = base_url
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._rate_limit_delay = 0.22  # 4-5 requests per second

        # --- PHASE 7.8: Safe Key Initialization ---
        self._signing_key = None
        is_sandbox = os.getenv("DRY_RUN", "true").lower() == "true"

        # Performance: Check for Rust core (v7.8)
        self._has_rust_signer = False
        self._rust_signer = None
        try:
            import rust_core

            self._has_rust_signer = True
            self._rust_signer = rust_core.generate_signature_rs
            logger.info("🚀 High-performance Rust signer active.")
        except ImportError:
            logger.warning("Rust Signer not found, using Python (pynacl) fallback.")

        # Python Fallback Initialization
        if not self._has_rust_signer:
            try:
                if secret_key and len(secret_key) >= 64:
                    clean_secret = secret_key[:64]
                    self._signing_key = SigningKey(bytes.fromhex(clean_secret))
                elif not is_sandbox:
                    logger.error("DMarket Secret Key is invalid or missing in Production!")
                else:
                    # In sandbox, we use a dummy signing key if none is provided
                    self._signing_key = SigningKey(bytes.fromhex("0" * 64))
            except Exception as e:
                if not is_sandbox:
                    logger.error(f"Failed to initialize Ed25519 key: {e}")
                else:
                    logger.debug(f"Skipping key initialization in Sandbox: {e}")
                    self._signing_key = SigningKey(bytes.fromhex("0" * 64))

        # Fee Cache (v7.7)
        self._fee_cache: Dict[str, Dict[str, Any]] = {}
        self._fee_cache_ttl = 43200  # 12 hours

    async def get_session(self) -> aiohttp.ClientSession:
        """Return the shared aiohttp session, creating it on first use."""
        if self._session is None or self._session.closed:
            # High-performance connection pooling
            connector = aiohttp.TCPConnector(limit=100, ssl=False, keepalive_timeout=60)
            self._session = aiohttp.ClientSession(connector=connector)

            # v12.2: Initial clock sync with DMarket server
            from src.utils.clock_sync import clock_sync

            await clock_sync.sync_with_dmarket(self._session)
            status = clock_sync.get_status()
            if status["is_healthy"]:
                logger.info(f"🕐 ClockSync OK: offset={status['offset_seconds']}s")
            else:
                logger.warning(
                    f"🕐 ClockSync drift: offset={status['offset_seconds']}s "
                    f"(may cause 401 errors)"
                )

        return self._session

    async def close(self) -> None:
        """Close the shared aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _wait_for_rate_limit(self) -> None:
        """Enforces <= 2 RPS dynamically."""
        async with self._lock:
            jitter = random.uniform(0.3, 0.4)  # Slightly faster due to async pipeline
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < jitter:
                await asyncio.sleep(jitter - elapsed)
            self._last_request_time = time.time()
            self._last_request_time = time.time()

    def _generate_signature(
        self, method: str, api_path: str, body: str, timestamp: str
    ) -> str:
        """API v2 Ed25519 signature scheme. (Rust or NaCl bindings)."""
        # Try Rust first (microsecond precision)
        if self._has_rust_signer and self.secret_key:
            try:
                # Rust expects the full hex secret
                return self._rust_signer(method, api_path, body, timestamp, self.secret_key)
            except Exception as e:
                logger.warning(f"Rust signer failed, falling back to Python: {e}")

        # Python Fallback
        signature_prefix = f"{method.upper()}{api_path}{body}{timestamp}"
        signed_message = self._signing_key.sign(signature_prefix.encode("utf-8"))
        return signed_message.signature.hex()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def make_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute API request with Dry Run support ($0.00 Risk)."""
        method = method.upper()

        # --- SANDBOX GUARD ---
        is_write_op = method in ["POST", "PUT", "DELETE", "PATCH"]
        if is_write_op and os.getenv("DRY_RUN", "true").lower() == "true":
            logger.info(f"🧪 [DRY RUN] Simulating {method} to {path}")
            # Mock success response for write operations to keep simulation loop running
            if (
                "batch" in path
                or "create" in path
                or "delete" in path
                or "close" in path
                or "edit" in path
            ):
                return {"status": "success", "simulated": True, "message": "Simulation Mode Active"}
            return {}

        await self._wait_for_rate_limit()

        # v12.2: Use server-corrected time for X-Sign-Date
        # Sync with DMarket if needed (prevents 401 from clock drift > 120s)
        from src.utils.clock_sync import clock_sync

        await clock_sync.ensure_synced()

        timestamp = str(int(clock_sync.now()))

        api_path = path
        if params:
            query_string = urllib.parse.urlencode(params)
            api_path = f"{path}?{query_string}"

        body_str = json.dumps(body) if body else ""
        signature = self._generate_signature(method, api_path, body_str, timestamp)

        headers = {
            "X-Api-Key": self.public_key,
            "X-Sign-Date": timestamp,
            "X-Request-Sign": f"dmar ed25519 {signature}",
            "Content-Type": "application/json",
        }

        url = f"{self.BASE_URL}{api_path}"
        session = await self.get_session()

        async with session.request(
            method, url, headers=headers, json=body if body else None
        ) as response:
            if response.status != 200:
                text = await response.text()
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message=f"DMarket API Error: {text}",
                    headers=response.headers,
                )
            return await response.json()
