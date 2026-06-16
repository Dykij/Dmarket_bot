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

import logging
logger = logging.getLogger("DMarketAuth")
logger.warning(
    "DMarketAuth is DEPRECATED. Use src.api.dmarket_api_client.DMarketAPIClient directly."
)


class DMarketAuth:
    """DEPRECATED — kept for backward compat only. Do not use."""

    def __init__(self):
        from src.config import Config
        self.public_key = Config.PUBLIC_KEY or ""
        self.secret_key = ""

    def generate_headers(self, method: str, path: str, body: str = "") -> dict:
        logger.error("DMarketAuth.generate_headers called — this class is deprecated.")
        return {}
