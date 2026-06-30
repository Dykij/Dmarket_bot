"""
DEPRECATED — This module is kept for backward compatibility only.

All signing logic has been consolidated into `src.api.dmarket_api_client.core`.
This class is no longer imported by any module. It exists solely so that
legacy code referencing `DMarketAuth` does not crash on import.

The standalone .env load here was problematic (C-3): it looked for .env
relative to this file's directory rather than the project root, causing
silent config drift. The centralized .env loading in `src.config` is the
single source of truth.
"""

import hashlib
import hmac
import logging
import os
import time
from typing import Optional

import nacl.signing

logger = logging.getLogger("DMarketAuth")
logger.warning(
    "DMarketAuth is DEPRECATED. Use src.api.dmarket_api_client.DMarketAPIClient directly."
)


class DMarketAuth:
    """DEPRECATED — kept for backward compat only. Generates Ed25519 signatures."""

    def __init__(self):
        from src.config import Config
        self.public_key = Config.PUBLIC_KEY or ""
        self.secret_key = Config.SECRET_KEY or ""
        self._signing_key: Optional[nacl.signing.SigningKey] = None
        if self.secret_key:
            try:
                raw_bytes = bytes.fromhex(self.secret_key)
                if len(raw_bytes) >= 32:
                    seed = raw_bytes[:32]
                    self._signing_key = nacl.signing.SigningKey(seed)
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to initialize Ed25519 signing key: {e}")

    def generate_headers(self, method: str, path: str, body: str = "") -> dict:
        if not self._signing_key or not self.public_key:
            logger.error("DMarketAuth.generate_headers called but signing key not initialized")
            return {}
        timestamp = str(int(time.time()))
        signature_prefix = f"{method.upper()}{path}{body}{timestamp}"
        try:
            signed = self._signing_key.sign(signature_prefix.encode("utf-8"))
            signature = signed.signature.hex()
        except Exception as e:
            logger.error(f"Signing failed: {e}")
            return {}
        return {
            "X-Api-Key": self.public_key,
            "X-Request-Sign": f"dmar ed25519 {signature}",
            "X-Sign-Date": timestamp,
        }
