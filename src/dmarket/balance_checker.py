"""Модуль для проверки баланса пользователя DMarket.

Refactored from ArbitrageScanner.check_user_balance() for better readability.
Phase 2: Code Readability Improvements - Task 9
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class BalanceChecker:
    """Handles user balance checking with extended diagnostics."""

    def __init__(self, api_client, min_required_balance: float = 1.0):
        """Initialize balance checker.

        Args:
            api_client: DMarket API client instance
            min_required_balance: Minimum required balance in USD

        """
        self.api_client = api_client
        self.min_required_balance = min_required_balance

    async def check_balance(self) -> dict[str, Any]:
        """Check user balance with extended diagnostics.

        Returns:
            Dictionary with balance and detailed information

        """
        try:
            balance_response = await self._fetch_balance()
            return self._process_balance_response(balance_response)
        except Exception as e:
            return self._create_exception_result(e)

    async def _fetch_balance(self) -> dict[str, Any] | None:
        """Fetch balance from DMarket API.

        Returns:
            API response dictionary or None if error

        """
        return await self.api_client._request(
            method="GET",
            path="/account/v1/balance",
            params={},
        )

    def _process_balance_response(self, balance_response: Any) -> dict[str, Any]:
        """Process balance API response.

        Args:
            balance_response: Response from DMarket API

        Returns:
            Processed balance information dictionary

        """
        # Early return: empty response
        if not balance_response:
            return self._create_error_result(
                error_message="Пустой ответ от API при запросе баланса",
                display_message="Не удалось получить баланс (пустой ответ)",
                diagnosis="api_error",
            )

        # Early return: invalid response type
        if not isinstance(balance_response, dict):
            return self._create_error_result(
                error_message="Не удалось получить баланс (некорректный ответ API)",
                display_message="Ошибка при получении баланса",
                diagnosis="unknown_error",
            )

        # Early return: error in response
        if self._has_error(balance_response):
            return self._handle_api_error(balance_response)

        # Success: process balance data
        return self._create_success_result(balance_response)

    def _has_error(self, response: dict[str, Any]) -> bool:
        """Check if API response contains error.

        Args:
            response: API response dictionary

        Returns:
            True if response has error, False otherwise

        """
        return "error" in response or not response.get("usd")

    def _handle_api_error(self, response: dict[str, Any]) -> dict[str, Any]:
        """Handle API error response.

        Args:
            response: API response with error

        Returns:
            Error result dictionary

        """
        error_message = response.get("message", "Неизвестная ошибка")
        logger.error(f"Ошибка при получении баланса: {error_message}")

        diagnosis = self._diagnose_error(error_message)
        display_message = self._get_error_display_message(diagnosis)

        return self._create_error_result(
            error_message=str(error_message),
            display_message=display_message,
            diagnosis=diagnosis,
        )

    def _diagnose_error(self, error_message: str) -> str:
        """Diagnose error type from error message.

        Args:
            error_message: Error message from API

        Returns:
            Error diagnosis code

        """
        error_lower = str(error_message).lower()

        if "unauthorized" in error_lower or "авторизации" in error_lower:
            return "auth_error"

        if "ключи" in error_lower or "api key" in error_lower:
            return "missing_keys"

        if "timeout" in error_lower or "время" in error_lower:
            return "timeout_error"

        if "404" in str(error_message) or "не найден" in error_lower:
            return "endpoint_error"

        return "unknown_error"

    def _get_error_display_message(self, diagnosis: str) -> str:
        """Get user-friendly error message based on diagnosis.

        Args:
            diagnosis: Error diagnosis code

        Returns:
            User-friendly error message

        """
        messages = {
            "auth_error": "Ошибка авторизации: проверьте ключи API",
            "missing_keys": "Отсутствуют ключи API",
            "timeout_error": "Таймаут при запросе баланса: возможны проблемы с сетью",
            "endpoint_error": "Ошибка API: эндпоинт баланса недоступен",
        }
        return messages.get(diagnosis, "Ошибка при получении баланса")

    def _create_success_result(self, response: dict[str, Any]) -> dict[str, Any]:
        """Create success result from API response.

        Args:
            response: Successful API response

        Returns:
            Success result dictionary with balance info

        """
        # Extract balance data - handle both formats:
        # Format 1: {"usd": "4550"} - cents as string
        # Format 2: {"usd": {"avAlgolable": 4550, "frozen": 0}}
        usd_data = response.get("usd", 0)

        if isinstance(usd_data, dict):
            # Nested format
            try:
                avAlgolable_amount = int(float(str(usd_data.get("avAlgolable", 0))))
                frozen_amount = int(float(str(usd_data.get("frozen", 0))))
            except (ValueError, TypeError):
                avAlgolable_amount = 0
                frozen_amount = 0
        else:
            # Simple format - all balance is avAlgolable
            try:
                avAlgolable_amount = int(float(str(usd_data))) if usd_data else 0
            except (ValueError, TypeError):
                avAlgolable_amount = 0
            frozen_amount = 0

        # Convert from cents to dollars
        avAlgolable_balance = float(avAlgolable_amount) / 100
        frozen_balance = float(frozen_amount) / 100
        total_balance = avAlgolable_balance + frozen_balance

        # Check if sufficient funds
        has_funds = avAlgolable_balance >= self.min_required_balance

        # Create display message and diagnosis
        diagnosis, display_message = self._create_display_info(
            has_funds, avAlgolable_balance, frozen_balance
        )

        # Log result
        logger.info(
            f"Результат проверки баланса: has_funds={has_funds}, "
            f"balance=${avAlgolable_balance:.2f}, avAlgolable=${avAlgolable_balance:.2f}, "
            f"total=${total_balance:.2f}, diagnosis={diagnosis}",
        )

        return {
            "has_funds": has_funds,
            "balance": avAlgolable_balance,
            "avAlgolable_balance": avAlgolable_balance,
            "total_balance": total_balance,
            "frozen_balance": frozen_balance,
            "min_required": self.min_required_balance,
            "error": False,
            "error_message": "",
            "display_message": display_message,
            "diagnosis": diagnosis,
        }

    def _create_display_info(
        self, has_funds: bool, avAlgolable_balance: float, frozen_balance: float
    ) -> tuple[str, str]:
        """Create diagnosis and display message based on balance status.

        Args:
            has_funds: Whether user has sufficient funds
            avAlgolable_balance: AvAlgolable balance in USD
            frozen_balance: Frozen balance in USD

        Returns:
            Tuple of (diagnosis, display_message)

        """
        # Sufficient funds
        if has_funds:
            diagnosis = "sufficient_funds"
            display_message = f"Баланс DMarket: ${avAlgolable_balance:.2f} USD (достаточно для арбитража)"
            return diagnosis, display_message

        # Insufficient funds - zero balance
        if avAlgolable_balance <= 0:
            diagnosis = "zero_balance"
            display_message = (
                f"На балансе DMarket нет средств. "
                f"Необходимо минимум ${self.min_required_balance:.2f} USD"
            )
            return diagnosis, display_message

        # Insufficient funds - some balance avAlgolable
        diagnosis = "insufficient_funds"
        display_message = (
            f"Недостаточно средств на балансе DMarket.\n"
            f"Доступно: ${avAlgolable_balance:.2f} USD\n"
            f"Необходимо минимум: ${self.min_required_balance:.2f} USD"
        )

        # Add frozen balance info if significant
        if frozen_balance > 0.01:
            display_message += f"\nЗаблокировано: ${frozen_balance:.2f} USD"
            diagnosis = "funds_frozen"

        return diagnosis, display_message

    def _create_error_result(
        self,
        error_message: str,
        display_message: str,
        diagnosis: str,
    ) -> dict[str, Any]:
        """Create error result dictionary.

        Args:
            error_message: Technical error message
            display_message: User-friendly error message
            diagnosis: Error diagnosis code

        Returns:
            Error result dictionary

        """
        return {
            "has_funds": False,
            "balance": 0.0,
            "avAlgolable_balance": 0.0,
            "total_balance": 0.0,
            "min_required": self.min_required_balance,
            "error": True,
            "error_message": error_message,
            "display_message": display_message,
            "diagnosis": diagnosis,
        }

    def _create_exception_result(self, exception: Exception) -> dict[str, Any]:
        """Create result dictionary for unexpected exception.

        Args:
            exception: Exception that occurred

        Returns:
            Exception result dictionary

        """
        logger.error(f"Неожиданная ошибка при проверке баланса: {exception!s}")
        import traceback

        logger.error(f"Стек вызовов: {traceback.format_exc()}")

        return self._create_error_result(
            error_message=str(exception),
            display_message=f"Ошибка при проверке баланса: {exception!s}",
            diagnosis="exception",
        )
