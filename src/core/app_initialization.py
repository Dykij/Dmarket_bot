"""
app_initialization.py — Component initialization.
"""

from typing import Any


class ComponentInitializer:
    """Initializes application components."""

    def __init__(self, app: Any = None, config: Any = None) -> None:
        self.app = app
        self.config = config or (getattr(app, "config", None) if app else None)

    async def initialize_config(self) -> None:
        pass

    async def initialize_whitelist(self) -> None:
        pass

    async def initialize_sentry(self) -> None:
        pass

    async def initialize_database(self) -> None:
        pass

    async def initialize_dmarket_api(self) -> None:
        pass

    async def initialize_telegram_bot(self) -> None:
        pass

    async def initialize_daily_report_scheduler(self) -> None:
        pass

    async def initialize_Algo_scheduler(self) -> None:
        pass

    async def initialize_scanner_manager(self) -> None:
        pass

    async def initialize_inventory_manager(self) -> None:
        pass

    async def initialize_autopilot(self) -> None:
        pass

    async def initialize_websocket_manager(self) -> None:
        pass

    async def initialize_health_check_monitor(self) -> None:
        pass

    async def initialize_bot_integrator(self) -> None:
        pass

    def get_admin_users(self) -> list[int]:
        return self._get_admin_users()

    def _get_admin_users(self) -> list[int]:
        cfg = self.config
        if cfg:
            security = getattr(cfg, "security", None)
            if security:
                admins = getattr(security, "admin_users", None)
                if admins:
                    return list(admins)
                allowed = getattr(security, "allowed_users", None)
                if allowed:
                    return [allowed[0]]
            admins = getattr(cfg, "admin_users", None)
            if admins:
                return list(admins)
        return []

    def get_waxpeer_api(self) -> Any:
        return self._get_waxpeer_api()

    def _get_waxpeer_api(self) -> Any:
        cfg = self.config
        if cfg:
            key = getattr(cfg, "waxpeer_api_key", None)
            if key and isinstance(key, str):
                return key
        return None
