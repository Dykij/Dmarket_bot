"""
Rust fallback module for DMarket Core.
This module mimics the interface of dmarket_rust_core when the Rust extension is not available.
"""
import hmac
import hashlib
import time


def version() -> str:
    return "python-fallback-0.1.0"


def sign_request(
    api_key: str,
    secret_key: str,
    method: str,
    path: str,
    body: str = "",
    timestamp: str | None = None
) -> dict[str, str]:
    """
    Fallback implementation of request signing using Python's HMAC.
    """
    if timestamp is None:
        timestamp = str(int(time.time()))

    string_to_sign = f"{method}{path}{body}{timestamp}"
    signature = hmac.new(
        secret_key.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return {
        "X-Api-Key": api_key,
        "X-Request-Sign": signature,
        "X-Sign-Date": timestamp,
        "Content-Type": "application/json",
    }
