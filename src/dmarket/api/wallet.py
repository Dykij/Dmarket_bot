"""Wallet and account operations for DMarket API."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

class WalletMixin:
    """Methods for managing balance and account details."""

    async def get_balance(self) -> dict[str, Any]:
        """Get user balance using various endpoints for compatibility."""
        try:
            # Standard endpoint
            response = await self._request("GET", "/account/v1/balance")
            
            # Simplified parsing for the mixin (actual logic in main class for now)
            if "usd" in response:
                usd = float(response.get("usd", 0))
                return {
                    "balance": usd / 100,
                    "available_balance": usd / 100,
                    "total_balance": usd / 100,
                    "has_funds": usd > 0,
                    "error": False
                }
            return response
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return {"error": True, "message": str(e), "balance": 0.0}

    async def get_account_details(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/account/details")

    def _parse_balance_from_response(self, response: dict[str, Any]) -> tuple[float, float, float]:
        usd_amount = usd_available = usd_total = 0.0
        try:
            if "usd" in response:
                usd_amount = float(response.get("usd", "0"))
                usd_available = usd_amount - float(response.get("usdTradeProtected", "0"))
                usd_total = usd_amount
        except: pass
        return usd_amount, usd_available, usd_total

    def _create_error_response(self, error_message: str, status_code: int = 500, error_code: str = "ERROR") -> dict[str, Any]:
        return {"balance": 0.0, "error": True, "error_message": error_message, "status_code": status_code, "code": error_code}

    def _create_balance_response(self, usd_amount: float, usd_available: float, usd_total: float, **kwargs) -> dict[str, Any]:
        return {"balance": usd_amount / 100, "available_balance": usd_available / 100, "total_balance": usd_total / 100, "error": False}
