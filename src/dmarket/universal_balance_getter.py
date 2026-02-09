"""Модуль для получения баланса пользователя DMarket через универсальный метод.

Refactored from DMarketAPI.get_balance() for better readability.
Phase 2: Code Readability Improvements - Task 10
"""

import logging
import traceback
from typing import Any

logger = logging.getLogger(__name__)


class UniversalBalanceGetter:
    """Handles balance retrieval using multiple methods for maximum compatibility."""

    # Known balance endpoints
    ENDPOINT_BALANCE = "/account/v1/balance"
    ENDPOINT_BALANCE_LEGACY = "/api/v1/account/balance"
    ENDPOINT_WALLET_BALANCE = "/api/v1/account/wallet/balance"
    ENDPOINT_EXCHANGE_BALANCE = "/exchange/v1/user/balance"

    def __init__(self, api_client):
        """Initialize balance getter.

        Args:
            api_client: DMarket API client instance

        """
        self.api_client = api_client
        self.public_key = getattr(api_client, "public_key", None)
        self.secret_key = getattr(api_client, "secret_key", None)

    async def get_balance(self) -> dict[str, Any]:
        """Get user balance using multiple methods for maximum compatibility.

        Returns:
            Balance information dictionary

        """
        logger.debug("Запрос баланса пользователя DMarket через универсальный метод")

        # Early return: missing API keys
        if not self._has_valid_credentials():
            return self._create_error_response(
                "API ключи не настроены",
                status_code=401,
                error_code="MISSING_API_KEYS",
            )

        try:
            # Try direct REST API request first
            direct_result = await self._try_direct_request()
            if direct_result:
                return direct_result

            # Fallback to internal API client with multiple endpoints
            return await self._try_internal_endpoints()

        except Exception as e:
            return self._handle_exception(e)

    def _has_valid_credentials(self) -> bool:
        """Check if API credentials are configured.

        Returns:
            True if credentials are valid, False otherwise

        """
        if not self.public_key or not self.secret_key:
            logger.error("Ошибка: API ключи не настроены (пустые значения)")
            return False
        return True

    async def _try_direct_request(self) -> dict[str, Any] | None:
        """Try to get balance via direct REST API request.

        Returns:
            Balance response dict if successful, None if failed

        """
        try:
            logger.debug("🔍 Trying to get balance via direct REST API request...")
            direct_response = await self.api_client.direct_balance_request()
            logger.debug(f"🔍 Direct API response: {direct_response}")

            # Early return: unsuccessful direct request
            if not direct_response or not direct_response.get("success", False):
                error_message = (
                    direct_response.get("error", "Unknown error")
                    if direct_response
                    else "No response"
                )
                logger.warning(f"⚠️ Direct REST API request failed: {error_message}")
                logger.debug(f"🔍 Full error response: {direct_response}")
                return None

            # Success: process direct response
            logger.info("✅ Successfully got balance via direct REST API request")
            return self._process_direct_response(direct_response)

        except Exception as e:
            logger.warning(f"⚠️ Error during direct REST API request: {e!s}")
            logger.exception(f"📋 Exception details: {e}")
            return None

    def _process_direct_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Process successful direct API response.

        Args:
            response: Direct API response

        Returns:
            Formatted balance response

        """
        balance_data = response.get("data", {})
        logger.debug(f"📊 Balance data: {balance_data}")

        # Extract amounts (convert from USD to cents)
        usd_amount = balance_data.get("balance", 0) * 100
        usd_available = balance_data.get("available", balance_data.get("balance", 0)) * 100
        usd_total = balance_data.get("total", balance_data.get("balance", 0)) * 100
        usd_locked = balance_data.get("locked", 0) * 100
        usd_trade_protected = balance_data.get("trade_protected", 0) * 100

        result = self._create_balance_response(
            usd_amount=usd_amount,
            usd_available=usd_available,
            usd_total=usd_total,
            locked_balance=usd_locked / 100,
            trade_protected_balance=usd_trade_protected / 100,
            additional_info={
                "method": "direct_request",
                "raw_response": balance_data,
            },
        )

        logger.info(
            f"💰 Final balance (direct request): ${result['balance']:.2f} USD "
            f"(available: ${result['available_balance']:.2f}, locked: ${result.get('locked_balance', 0):.2f})"
        )
        return result

    async def _try_internal_endpoints(self) -> dict[str, Any]:
        """Try to get balance using internal API client with multiple endpoints.

        Returns:
            Balance response dictionary

        """
        endpoints = self._get_balance_endpoints()

        response, successful_endpoint, last_error = await self._try_endpoints_for_balance(endpoints)

        # Early return: no response from any endpoint
        if not response:
            error_message = (
                str(last_error) if last_error else "Failed to get balance from any endpoint"
            )
            logger.error(f"Critical error getting balance: {error_message}")
            return self._create_error_from_message(error_message)

        # Early return: API error in response
        if self._response_has_error(response):
            return self._handle_api_error(response)

        # Success: process response
        return self._process_successful_response(response, successful_endpoint)

    def _get_balance_endpoints(self) -> list[str]:
        """Get list of balance endpoints to try.

        Returns:
            List of endpoint URLs

        """
        return [
            self.ENDPOINT_BALANCE,  # Current endpoint according to documentation
            self.ENDPOINT_WALLET_BALANCE,  # Alternative possible endpoint
            self.ENDPOINT_EXCHANGE_BALANCE,  # Possible exchange endpoint
            self.ENDPOINT_BALANCE_LEGACY,  # Legacy endpoint (backward compatibility)
        ]

    async def _try_endpoints_for_balance(
        self, endpoints: list[str]
    ) -> tuple[dict[str, Any] | None, str | None, Exception | None]:
        """Try multiple endpoints to get balance.

        Args:
            endpoints: List of endpoint URLs to try

        Returns:
            Tuple of (response, successful_endpoint, last_error)

        """
        last_error = None

        for endpoint in endpoints:
            try:
                logger.debug(f"Trying endpoint: {endpoint}")
                response = await self.api_client._request(
                    method="GET",
                    path=endpoint,
                    params={},
                )

                if response and not self._response_has_error(response):
                    logger.info(f"✅ Successfully got balance from {endpoint}")
                    return response, endpoint, None

            except Exception as e:
                logger.debug(f"Failed to get balance from {endpoint}: {e!s}")
                last_error = e

        return None, None, last_error

    def _response_has_error(self, response: dict[str, Any]) -> bool:
        """Check if response contains an error.

        Args:
            response: API response

        Returns:
            True if response has error, False otherwise

        """
        return "error" in response or "code" in response

    def _handle_api_error(self, response: dict[str, Any]) -> dict[str, Any]:
        """Handle API error response.

        Args:
            response: API response with error

        Returns:
            Error response dictionary

        """
        error_code = response.get("code", "unknown")
        error_message = response.get("message", response.get("error", "Unknown error"))
        status_code = response.get("status", response.get("status_code", 500))

        logger.error(
            f"DMarket API error getting balance: {error_code} - {error_message} (HTTP {status_code})"
        )

        # Handle authorization error
        if self._is_auth_error(error_code, status_code):
            logger.error(
                "Problem with API keys. Please check correctness and validity of DMarket API keys"
            )
            return self._create_error_response(
                "Authorization error: invalid API keys",
                status_code=401,
                error_code="UNAUTHORIZED",
            )

        return self._create_error_response(error_message, status_code, error_code)

    def _is_auth_error(self, error_code: str, status_code: int) -> bool:
        """Check if error is authorization related.

        Args:
            error_code: Error code from API
            status_code: HTTP status code

        Returns:
            True if auth error, False otherwise

        """
        return error_code == "Unauthorized" or status_code == 401

    def _process_successful_response(
        self, response: dict[str, Any], endpoint: str
    ) -> dict[str, Any]:
        """Process successful API response.

        Args:
            response: API response
            endpoint: Successful endpoint URL

        Returns:
            Formatted balance response

        """
        logger.info(f"🔍 RAW BALANCE API RESPONSE (get_balance): {response}")
        logger.info(f"Analyzing balance response from {endpoint}: {response}")

        usd_amount, usd_available, usd_total = self._parse_balance_from_response(response)

        # Warn if unable to parse
        if usd_amount == 0 and usd_available == 0 and usd_total == 0:
            logger.warning(f"Could not parse balance data from known formats: {response}")

        result = self._create_balance_response(
            usd_amount=usd_amount,
            usd_available=usd_available,
            usd_total=usd_total,
            additional_info={"endpoint": endpoint},
        )

        logger.info(
            f"Final balance: ${result['balance']:.2f} USD "
            f"(available: ${result['available_balance']:.2f}, total: ${result['total_balance']:.2f})"
        )
        return result

    def _parse_balance_from_response(self, response: dict[str, Any]) -> tuple[float, float, float]:
        """Parse balance amounts from API response.

        Args:
            response: API response

        Returns:
            Tuple of (amount, available, total) in cents

        """
        # Try parsing from different response formats
        if "usd" in response and isinstance(response["usd"], dict):
            usd_data = response["usd"]
            usd_amount = usd_data.get("amount", 0)
            usd_available = usd_data.get("available", usd_amount)
            usd_total = usd_data.get("total", usd_amount)
        elif "balance" in response:
            usd_amount = response.get("balance", 0)
            usd_available = response.get("available", usd_amount)
            usd_total = response.get("total", usd_amount)
        else:
            usd_amount = 0
            usd_available = 0
            usd_total = 0

        return usd_amount, usd_available, usd_total

    def _create_balance_response(
        self,
        usd_amount: float,
        usd_available: float,
        usd_total: float,
        locked_balance: float = 0.0,
        trade_protected_balance: float = 0.0,
        additional_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create formatted balance response.

        Args:
            usd_amount: Balance amount in cents
            usd_available: Available balance in cents
            usd_total: Total balance in cents
            locked_balance: Locked balance in dollars
            trade_protected_balance: Trade protected balance in dollars
            additional_info: Additional information to include

        Returns:
            Formatted balance response dictionary

        """
        balance_usd = usd_amount / 100
        available_usd = usd_available / 100
        total_usd = usd_total / 100

        result = {
            "usd": {"amount": usd_amount},
            "has_funds": balance_usd >= 1.0,
            "balance": balance_usd,
            "available_balance": available_usd,
            "total_balance": total_usd,
            "error": False,
            "error_message": "",
        }

        if locked_balance > 0:
            result["locked_balance"] = locked_balance

        if trade_protected_balance > 0:
            result["trade_protected_balance"] = trade_protected_balance

        if additional_info:
            result.update(additional_info)

        return result

    def _create_error_response(
        self, error_message: str, status_code: int, error_code: str
    ) -> dict[str, Any]:
        """Create error response dictionary.

        Args:
            error_message: Error message
            status_code: HTTP status code
            error_code: Error code

        Returns:
            Error response dictionary

        """
        return {
            "usd": {"amount": 0},
            "has_funds": False,
            "balance": 0.0,
            "available_balance": 0.0,
            "total_balance": 0.0,
            "error": True,
            "error_message": error_message,
            "status_code": status_code,
            "error_code": error_code,
        }

    def _create_error_from_message(self, error_message: str) -> dict[str, Any]:
        """Create error response from error message.

        Args:
            error_message: Error message

        Returns:
            Error response dictionary

        """
        status_code = self._determine_status_code(error_message)
        error_code = self._determine_error_code(error_message)
        return self._create_error_response(error_message, status_code, error_code)

    def _determine_status_code(self, error_message: str) -> int:
        """Determine HTTP status code from error message.

        Args:
            error_message: Error message

        Returns:
            HTTP status code

        """
        error_lower = error_message.lower()

        if "404" in error_message or "not found" in error_lower:
            return 404

        if "401" in error_message or "unauthorized" in error_lower:
            return 401

        return 500

    def _determine_error_code(self, error_message: str) -> str:
        """Determine error code from error message.

        Args:
            error_message: Error message

        Returns:
            Error code string

        """
        error_lower = error_message.lower()

        if "404" in error_message or "not found" in error_lower:
            return "NOT_FOUND"

        if "401" in error_message or "unauthorized" in error_lower:
            return "UNAUTHORIZED"

        return "REQUEST_FAILED"

    def _handle_exception(self, exception: Exception) -> dict[str, Any]:
        """Handle unexpected exception.

        Args:
            exception: Exception that occurred

        Returns:
            Error response dictionary

        """
        logger.error(f"Unexpected error getting balance: {exception!s}")
        logger.error(f"Stack trace: {traceback.format_exc()}")

        error_str = str(exception)
        status_code = self._determine_status_code(error_str)
        error_code = "EXCEPTION"

        if status_code == 404:
            error_code = "NOT_FOUND"
        elif status_code == 401:
            error_code = "UNAUTHORIZED"

        return self._create_error_response(error_str, status_code, error_code)
