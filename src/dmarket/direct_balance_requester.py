"""Direct Balance Request module - refactored from dmarket_api.py.

This module provides direct balance request functionality with Ed25519 signing,
refactored following Phase 2 guidelines for improved code readability.

Author: DMarket Telegram Bot
Created: 2026-01-01
Phase: 2 (Week 3-4)
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Any

import nacl.signing
import structlog
from circuitbreaker import CircuitBreakerError

from src.utils.api_circuit_breaker import call_with_circuit_breaker

logger = structlog.get_logger(__name__)


class DirectBalanceRequester:
    """Handles direct balance requests with Ed25519 signing."""

    ENDPOINT_BALANCE = "/account/v1/balance"

    def __init__(self, api_url: str, public_key: str, secret_key: str, get_client_func):
        """Initialize requester with API credentials.

        Args:
            api_url: Base API URL
            public_key: DMarket public API key
            secret_key: DMarket secret key (hex/base64 encoded)
            get_client_func: Async function to get HTTP client
        """
        self.api_url = api_url
        self.public_key = public_key
        self._secret_key = secret_key
        self._get_client = get_client_func

    async def request(self) -> dict[str, Any]:
        """Execute direct balance request via REST API using Ed25519.

        This method is an alternative way to get balance in case
        of problems with the main method.

        Returns:
            Dictionary with balance result or error

        Example:
            >>> requester = DirectBalanceRequester(api_url, key, secret, client_func)
            >>> result = await requester.request()
            >>> if result["success"]:
            ...     print(f"Balance: ${result['data']['balance']:.2f}")
        """
        try:
            full_url, headers = self._prepare_request()

            client = await self._get_client()

            response = await call_with_circuit_breaker(
                client.get, full_url, headers=headers, timeout=10
            )

            return self._process_response(response)

        except CircuitBreakerError as e:
            logger.exception("circuit_breaker_open_for_balance", error=str(e))
            return self._error_result(f"Circuit breaker open: {e}")

        except Exception as e:
            logger.exception("direct_balance_request_failed", error=str(e))
            return self._error_result(str(e))

    def _prepare_request(self) -> tuple[str, dict[str, str]]:
        """Prepare request URL and headers with signature."""
        full_url = f"{self.api_url}{self.ENDPOINT_BALANCE}"
        timestamp = str(int(time.time()))

        signature = self._generate_signature(timestamp)

        headers = {
            "X-Api-Key": self.public_key,
            "X-Sign-Date": timestamp,
            "X-Request-Sign": f"dmar ed25519 {signature}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        logger.debug("direct_balance_request_prepared", endpoint=self.ENDPOINT_BALANCE)

        return full_url, headers

    def _generate_signature(self, timestamp: str) -> str:
        """Generate Ed25519 signature for request.

        Falls back to HMAC-SHA256 if Ed25519 fails.
        """
        string_to_sign = f"GET{self.ENDPOINT_BALANCE}{timestamp}"

        logger.debug("generating_signature", string_to_sign=string_to_sign)

        try:
            return self._sign_with_ed25519(string_to_sign)
        except Exception as e:
            logger.warning("ed25519_signing_failed_fallback_to_hmac", error=str(e))
            return self._sign_with_hmac(string_to_sign)

    def _sign_with_ed25519(self, message: str) -> str:
        """Sign message with Ed25519.

        Raises:
            Exception: If signing fails
        """
        secret_key_bytes = self._parse_secret_key()

        signing_key = nacl.signing.SigningKey(secret_key_bytes)
        signed = signing_key.sign(message.encode("utf-8"))

        signature = signed.signature.hex()

        logger.debug("ed25519_signature_generated")

        return signature

    def _parse_secret_key(self) -> bytes:
        """Parse secret key from various formats (hex/base64).

        Returns:
            Secret key as bytes (32 bytes for Ed25519)

        Raises:
            Exception: If key format is invalid
        """
        secret_key_str = self._secret_key

        # Format 1: HEX format (64 chars = 32 bytes)
        if len(secret_key_str) == 64:
            return bytes.fromhex(secret_key_str)

        # Format 2: Base64 format
        if len(secret_key_str) == 44 or "=" in secret_key_str:
            return base64.b64decode(secret_key_str)

        # Format 3: Take first 64 hex chars
        if len(secret_key_str) >= 64:
            return bytes.fromhex(secret_key_str[:64])

        # Fallback: pad/truncate to 32 bytes
        return secret_key_str.encode("utf-8")[:32].ljust(32, b"\0")

    def _sign_with_hmac(self, message: str) -> str:
        """Sign message with HMAC-SHA256 (fallback)."""
        secret_key = self._secret_key.encode("utf-8")

        return hmac.new(
            secret_key,
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _process_response(self, response) -> dict[str, Any]:
        """Process HTTP response and extract balance data."""
        if response.status_code == 200:
            return self._process_success_response(response)

        if response.status_code == 401:
            return self._auth_error_result()

        return self._http_error_result(response)

    def _process_success_response(self, response) -> dict[str, Any]:
        """Process successful (200) response."""
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            logger.warning("json_decode_error", response_text=response.text)
            return self._error_result("JSON decode error")

        if not response_data:
            return self._error_result("Empty response")

        logger.info("balance_request_success", raw_response=response_data)

        balance_data = self._parse_balance_data(response_data)

        return {
            "success": True,
            "data": balance_data,
        }

    def _parse_balance_data(self, response_data: dict[str, Any]) -> dict[str, float]:
        """Parse balance data from API response.

        API returns values in cents (USD) and dimoshi (DMC) as strings.
        """
        usd_str = response_data.get("usd", "0")
        usd_available_str = response_data.get("usdAvailableToWithdraw", "0")
        usd_trade_protected_str = response_data.get("usdTradeProtected", "0")

        try:
            balance_cents = float(usd_str)
            available_cents = float(usd_available_str)
            trade_protected_cents = float(usd_trade_protected_str)

            # Convert cents to dollars
            balance = balance_cents / 100
            available = available_cents / 100
            trade_protected = trade_protected_cents / 100

            locked = balance - available - trade_protected
            total = balance

            logger.info(
                "balance_parsed",
                balance=balance,
                available=available,
                locked=locked,
                trade_protected=trade_protected,
            )

            return {
                "balance": balance,
                "available": available,
                "total": total,
                "locked": locked,
                "trade_protected": trade_protected,
            }

        except (ValueError, TypeError) as e:
            logger.exception(
                "balance_conversion_error",
                error=str(e),
                usd=usd_str,
                usd_available=usd_available_str,
            )

            return {
                "balance": 0.0,
                "available": 0.0,
                "total": 0.0,
                "locked": 0.0,
                "trade_protected": 0.0,
            }

    def _auth_error_result(self) -> dict[str, Any]:
        """Return authentication error result."""
        logger.error("authentication_error_401")

        return {
            "success": False,
            "status_code": 401,
            "error": "Authentication error: invalid API keys",
        }

    def _http_error_result(self, response) -> dict[str, Any]:
        """Return HTTP error result."""
        logger.warning(
            "http_error_in_balance_request",
            status_code=response.status_code,
            response_text=response.text,
        )

        return {
            "success": False,
            "status_code": response.status_code,
            "error": f"HTTP {response.status_code}: {response.text}",
        }

    def _error_result(self, error: str) -> dict[str, Any]:
        """Return generic error result."""
        return {
            "success": False,
            "error": error,
        }
