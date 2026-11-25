"""
exceptions.py — Exceptions raised by the DMarket API client.
"""

from __future__ import annotations

from typing import Any

import aiohttp


class SecurityViolation(Exception):
    """Raised when request parameters violate safety allowlists."""

    pass


class DMarketResponseError(aiohttp.ClientResponseError):
    """HTTP error response from DMarket API with parsed JSON body fields."""

    def __init__(
        self,
        *args: Any,
        dm_code: str | None = None,
        dm_message: str | None = None,
        dm_body: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.dm_code = dm_code
        self.dm_message = dm_message
        self.dm_body = {} if dm_body is None else dm_body
