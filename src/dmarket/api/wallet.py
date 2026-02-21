"""Wallet and account operations for DMarket API."""

import logging
from typing import Any

from src.dmarket.models.pydantic_api import BalanceResponse

logger = logging.getLogger(__name__)


class WalletMixin:
    """Methods for managing balance and account details using Pydantic v2."""

    async def get_balance(self) -> BalanceResponse:
        """Get user balance using various endpoints for compatibility.

        Returns:
            BalanceResponse: Pydantic model with validated balance data.
        """
        try:
            # Standard endpoint
            response = await self._request("GET", "/account/v1/balance")

            if "usd" in response:
                usd = float(response.get("usd", 0))
                return BalanceResponse(
                    balance=usd / 100,
                    available_balance=usd / 100,
                    total_balance=usd / 100,
                    has_funds=usd > 0,
                    error=False,
                )

            # Fallback for unexpected formats
            return BalanceResponse(
                balance=0.0,
                available_balance=0.0,
                total_balance=0.0,
                error=True,
                error_message="Unexpected balance format",
            )

        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return BalanceResponse(
                balance=0.0,
                available_balance=0.0,
                total_balance=0.0,
                error=True,
                error_message=str(e),
            )

    async def get_account_details(self) -> dict[str, Any]:
        """Retrieve full account details from DMarket."""
        return await self._request("GET", "/api/v1/account/details")


# Alias for backward compatibility
WalletOperationsMixin = WalletMixin
