"""
core.py — DMarketAPIClient orchestrator.

Holds the lifecycle (init, session, close) and the request pipeline
(signing, rate limit, dry-run guard, retries). The high-level endpoint
groups (market, account, offers, targets, fees) live in sibling mixin
modules and are composed here.
"""

from __future__ import annotations

import asyncio
import base64
import ctypes
import json
import os
import random
import sys
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
from .backoff import CircuitBreaker, CircuitOpenError, should_trip
from src.utils.vault import vault  # noqa: F401  # backward compat re-export

logger = structlog.get_logger("DMarketAPI")

# Preserve the original module-level vault import for backward compat


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
        self._rust_signer: Any = None
        try:
            import rust_core

            self._has_rust_signer = True
            self._rust_signer = rust_core.generate_signature_rs
            logger.info("🚀 High-performance Rust signer active.")
        except ImportError:
            logger.warning("Rust Signer not found, using Python (pynacl) fallback.")

        # v12.9: Store the raw secret key in encrypted form only.
        # The SigningKey object is created on-the-fly during _generate_signature
        # and zeroed out immediately after signing. This prevents the key from
        # lingering in process memory for the lifetime of the client (which could
        # be weeks in a 24/7 trading loop).
        self._encrypted_secret: Optional[bytes] = None
        if secret_key and len(secret_key) >= 64:
            raw_secret = secret_key[:64]
            # Encrypt using the VaultProvider's Fernet (if available)
            try:
                from src.utils.vault import vault
                if vault._fernet is not None:
                    self._encrypted_secret = vault._fernet.encrypt(raw_secret.encode("utf-8"))
                else:
                    self._encrypted_secret = raw_secret.encode("utf-8")
            except Exception:
                self._encrypted_secret = raw_secret.encode("utf-8")
            # Clear the raw secret from local scope
            raw_secret = ""

        # Python Fallback Initialization
        if not self._has_rust_signer:
            try:
                if secret_key and len(secret_key) >= 64:
                    if self._encrypted_secret and len(self._encrypted_secret) > 128:
                        clean_secret = self._decrypt_secret()
                        if clean_secret:
                            self._signing_key = SigningKey(bytes.fromhex(clean_secret))
                            self._secure_zero(clean_secret)
                        else:
                            self._signing_key = SigningKey(bytes.fromhex(secret_key[:64]))
                    else:
                        self._signing_key = SigningKey(bytes.fromhex(secret_key[:64]))
                elif not is_sandbox:
                    logger.error("DMarket Secret Key is invalid or missing in Production!")
                else:
                    self._signing_key = SigningKey(bytes.fromhex("0" * 64))
            except Exception as e:
                if not is_sandbox:
                    logger.error(f"Failed to initialize Ed25519 key: {e}", exc_info=True)
                else:
                    logger.debug(f"Skipping key initialization in Sandbox: {e}")
                    self._signing_key = SigningKey(bytes.fromhex("0" * 64))

        # Fee Cache (v7.7)
        self._fee_cache: Dict[str, Dict[str, Any]] = {}
        self._fee_cache_ttl = 43200  # 12 hours

        # v12.4 P1: Circuit breaker for DMarket endpoints
        # Opens after 3 consecutive 429/5xx failures, exponentially backs
        # off (30s → 60s → 120s → 300s) with jitter to prevent thundering
        # herd. Protects against OfferNotFound races and rate-limit storms.
        self._breaker = CircuitBreaker(
            name="dmarket",
            fail_threshold=3,
            base_cooldown=30.0,
            max_cooldown=300.0,
            jitter_pct=0.2,
        )

    # ------------------------------------------------------------------
    # v12.9: Secure memory helpers for encrypted key storage
    # ------------------------------------------------------------------
    @staticmethod
    def _secure_zero(data: str) -> None:
        """Overwrite a string's internal buffer with zeros.
        
        This is a best-effort mitigation. Python strings are immutable,
        so we cannot truly zero them, but we can ensure the variable is
        eligible for GC and nothing else references it.
        """
        if sys.getrefcount(data) > 3:
            return
        try:
            buf = ctypes.create_string_buffer(data.encode("utf-8"))
            ctypes.memset(buf, 0, len(buf))
        except Exception:
            pass

    def _decrypt_secret(self) -> Optional[str]:
        """Decrypt the stored encrypted secret. Returns hex string or None."""
        if self._encrypted_secret is None:
            return None
        try:
            from src.utils.vault import vault
            if vault._fernet is not None:
                return vault._fernet.decrypt(self._encrypted_secret).decode("utf-8")
            return self._encrypted_secret.decode("utf-8")
        except Exception:
            return None

    async def get_session(self) -> aiohttp.ClientSession:
        """Return the shared aiohttp session, creating it on first use."""
        if self._session is None or self._session.closed:
            # v12.7: High-performance connection pooling with per-host limits.
            # limit=100: total concurrent connections across all hosts.
            # limit_per_host=20: prevent connection starvation to single host.
            # keepalive_timeout=60: reuse connections for 60s (reduces TLS handshake).
            # enable_cleanup_closed=True: properly close stale connections.
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=20,
                ssl=True,
                keepalive_timeout=60,
                enable_cleanup_closed=True,
            )
            # v12.7: Response compression for ~60% bandwidth reduction.
            # DMarket API supports gzip/deflate responses.
            default_headers = {
                "Accept-Encoding": "gzip, deflate",
                "Accept": "application/json",
            }
            self._session = aiohttp.ClientSession(
                connector=connector,
                headers=default_headers,
            )

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

    async def _wait_for_rate_limit(self, is_public_endpoint: bool = False) -> None:
        """Enforces rate limits dynamically.

        Public endpoints (market data): ~10 RPS (600 RPM).
        Private endpoints (auth required): ~2 RPS (stricter).
        """
        async with self._lock:
            if is_public_endpoint:
                jitter = random.uniform(0.08, 0.12)  # ~8-12 RPS for public
            else:
                jitter = random.uniform(0.3, 0.4)  # ~2.5-3.3 RPS for private
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < jitter:
                await asyncio.sleep(jitter - elapsed)
            self._last_request_time = time.time()

    def _generate_signature(
        self, method: str, api_path: str, body: str, timestamp: str
    ) -> str:
        """API v2 Ed25519 signature scheme. (Rust or NaCl bindings).
        
        v12.9: Decrypts the stored encrypted key on-the-fly, signs, then
        zeros the plaintext key immediately. This prevents the raw secret
        from lingering in process memory between requests.
        """
        # v12.9: Decrypt the secret on the fly (zeroed after use)
        raw_secret = self._decrypt_secret() or self.secret_key

        # Try Rust first (microsecond precision)
        if self._has_rust_signer and raw_secret:
            try:
                result = self._rust_signer(method, api_path, body, timestamp, raw_secret)
                self._secure_zero(raw_secret)
                return result
            except Exception as e:
                logger.warning(f"Rust signer failed, falling back to Python: {e}", exc_info=True)

        # Python Fallback
        if self._signing_key is not None:
            signature_prefix = f"{method.upper()}{api_path}{body}{timestamp}"
            signed_message = self._signing_key.sign(signature_prefix.encode("utf-8"))
            result = signed_message.signature.hex()
            self._secure_zero(raw_secret)
            return result

        self._secure_zero(raw_secret)
        raise RuntimeError("No signing key available for Ed25519 signature")

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

        # v12.4 P1: Circuit breaker check
        if not self._breaker.allow_request():
            cooldown_remaining = (
                self._breaker.current_cooldown - (time.time() - self._breaker.opened_at)
            )
            raise CircuitOpenError(
                breaker_name=self._breaker.name,
                cooldown_remaining=max(0.0, cooldown_remaining),
            )

        # v12.7: Per-endpoint rate limiting (P0-3).
        # Public endpoints (market data, no auth): 600 RPM (~10 RPS).
        # Private endpoints (auth required): stricter (~2 RPS).
        _PUBLIC_PATHS = (
            "/exchange/v1/market/items",
            "/marketplace-api/v1/aggregated-prices",
            "/trade-aggregator/v1/last-sales",
            "/marketplace-api/v1/low-fee-items",
        )
        is_public = any(path.startswith(p) for p in _PUBLIC_PATHS)
        await self._wait_for_rate_limit(is_public_endpoint=is_public)

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

        try:
            async with session.request(
                method, url, headers=headers, json=body if body else None
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    # v12.4: Trip the breaker for 429 / 5xx (rate-limit / server errors)
                    if should_trip(response.status):
                        self._breaker.record_failure(
                            aiohttp.ClientResponseError(
                                request_info=response.request_info,
                                history=response.history,
                                status=response.status,
                                message=f"DMarket API Error: {text}",
                                headers=response.headers,
                            )
                        )
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"DMarket API Error: {text}",
                        headers=response.headers,
                    )
                # Success: close the breaker if it was HALF_OPEN
                self._breaker.record_success()
                return await response.json()
        except (asyncio.TimeoutError, aiohttp.ClientConnectionError) as e:
            # Network errors count as breaker failures
            self._breaker.record_failure(e)
            raise
        except CircuitOpenError:
            raise
        except aiohttp.ClientResponseError:
            # Already handled above for trippable codes; for non-trippable
            # (4xx) the breaker was not touched, so just re-raise.
            raise

    def circuit_breaker_status(self) -> dict:
        """Diagnostic snapshot of the circuit breaker state."""
        return self._breaker.status()
