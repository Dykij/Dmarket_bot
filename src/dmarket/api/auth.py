"""Signature generation for DMarket API authentication.

This module provides signature generation using Ed25519 (recommended) and HMAC-SHA256 (legacy).

DMarket API Authentication:
- Ed25519 is the RECOMMENDED method using NACL library
- HMAC-SHA256 is supported for backward compatibility
- Timestamp must be within 2 minutes of server time

Required Headers:
- X-Api-Key: Your public API key
- X-Sign-Date: Timestamp in seconds
- X-Request-Sign: Signature in format "dmar ed25519 {signature}"

Documentation: https://docs.dmarket.com/v1/swagger.html
"""

import base64
import hashlib
import hmac
import logging
import time
import traceback

import nacl.signing

logger = logging.getLogger(__name__)


def generate_signature_ed25519(
    public_key: str,
    secret_key: str,
    method: str,
    path: str,
    body: str = "",
) -> dict[str, str]:
    """Generate Ed25519 signature for DMarket API requests.

    DMarket API uses Ed25519 for request signing.
    Format: timestamp + method + path + body

    Args:
        public_key: DMarket API public key
        secret_key: DMarket API secret key
        method: HTTP method ("GET", "POST", etc.)
        path: Request path (e.g., "/account/v1/balance")
        body: Request body (JSON string)

    Returns:
        dict: Headers with signature and API key
    """
    if not public_key or not secret_key:
        return {"Content-Type": "application/json"}

    try:
        # Generate timestamp
        timestamp = str(int(time.time()))

        # Build string to sign: METHOD + PATH + BODY + TIMESTAMP
        string_to_sign = f"{method.upper()}{path}"
        if body:
            string_to_sign += body
        string_to_sign += timestamp

        logger.debug(f"String to sign: {string_to_sign}")

        # Convert secret key from string to bytes
        secret_key_bytes = _convert_secret_key(secret_key)

        # Create Ed25519 signing key
        signing_key = nacl.signing.SigningKey(secret_key_bytes)

        # Sign the message
        signed = signing_key.sign(string_to_sign.encode("utf-8"))

        # Extract signature in hex format
        signature = signed.signature.hex()

        logger.debug(f"Generated signature: {signature[:20]}...")

        # Return headers with signature in DMarket format
        return {
            "X-Api-Key": public_key,
            "X-Request-Sign": f"dmar ed25519 {signature}",
            "X-Sign-Date": timestamp,
            "Content-Type": "application/json",
        }

    except Exception as e:
        logger.exception(f"Error generating Ed25519 signature: {e}")
        logger.exception(f"Traceback: {traceback.format_exc()}")
        # Fallback to HMAC method
        return generate_signature_hmac(
            public_key, secret_key.encode("utf-8"), method, path, body
        )


def _convert_secret_key(secret_key: str) -> bytes:
    """Convert secret key string to bytes.

    Args:
        secret_key: Secret key in various formats

    Returns:
        bytes: Secret key as 32-byte array
    """
    # Format 1: HEX format (64 chars = 32 bytes)
    if len(secret_key) == 64:
        try:
            result = bytes.fromhex(secret_key)
            logger.debug("Using HEX format secret key (32 bytes)")
            return result
        except ValueError as e:
            logger.debug(f"HEX decode failed: {e}")

    # Format 2: Base64 format
    if len(secret_key) == 44 or "=" in secret_key:
        try:
            result = base64.b64decode(secret_key)
            logger.debug(f"Using Base64 format secret key ({len(result)} bytes)")
            return result
        except Exception as e:
            logger.debug(f"Base64 decode failed: {e}")

    # Format 3: Long HEX - take first 64 chars
    if len(secret_key) >= 64:
        try:
            result = bytes.fromhex(secret_key[:64])
            logger.debug("Using first 32 bytes of long HEX key")
            return result
        except ValueError as e:
            logger.debug(f"Long HEX decode failed: {e}")

    # Fallback: encode string to bytes and pad/truncate to 32
    logger.warning("Secret key format unknown, using padded bytes")
    return secret_key.encode("utf-8")[:32].ljust(32, b"\0")


def generate_signature_hmac(
    public_key: str,
    secret_key: bytes,
    method: str,
    path: str,
    body: str = "",
) -> dict[str, str]:
    """Generate HMAC-SHA256 signature (legacy format).

    Args:
        public_key: DMarket API public key
        secret_key: DMarket API secret key as bytes
        method: HTTP method
        path: Request path
        body: Request body

    Returns:
        dict: Headers with HMAC signature
    """
    timestamp = str(int(time.time()))
    string_to_sign = timestamp + method + path

    if body:
        string_to_sign += body

    signature = hmac.new(
        secret_key,
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return {
        "X-Api-Key": public_key,
        "X-Request-Sign": signature,
        "X-Sign-Date": timestamp,
        "Content-Type": "application/json",
    }
