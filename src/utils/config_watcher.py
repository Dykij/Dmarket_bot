"""
config_watcher.py — Hot-reload .env changes without restart (v14.5).

Watches .env file for modifications and reloads Config attributes
so parameters like MIN_SPREAD_PCT, MAX_PRICE_USD, STOP_LOSS_PCT
can be changed at runtime without restarting the bot.

Usage: call config_watcher.start() during bot init, modify .env anytime.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from src.config import Config

logger = logging.getLogger("ConfigWatcher")

_ENV_PATH = Path(os.getenv("DOTENV_PATH", str(Path(__file__).parent.parent.parent / ".env")))
_WATCH_INTERVAL = 30  # seconds between checks


class ConfigWatcher:
    """Watches .env for changes and hot-reloads Config attributes."""

    _reloadable_keys = frozenset({
        "MIN_SPREAD_PCT", "MAX_PRICE_USD", "MAX_SNIPING_PRICE_USD",
        "MAX_POSITION_RISK_PCT", "MAX_DAILY_TRADES", "MAX_DAILY_LOSS_USD",
        "STOP_LOSS_PCT", "TAKE_PROFIT_PCT", "STOP_LOSS_ENABLED",
        "TAKE_PROFIT_ENABLED", "SCAN_INTERVAL", "CS2CAP_CACHE_TTL_SECONDS",
        "INTRA_LIST_DISCOUNT", "INTRA_MIN_SPREAD_PCT",
        "KELLY_ENABLED", "KELLY_FRACTION", "DRAWDOWN_FREEZE_ENABLED",
        "DRAWDOWN_FREEZE_THRESHOLD", "LIMIT_ORDER_ENABLED",
        "LIMIT_ORDER_MIN_SPREAD_PCT", "DISCOUNT_THRESHOLD_PCT",
        "USE_DISCOUNT_FILTER", "USE_CATEGORY_FILTER", "USE_CROSS_WEAR_GUARD",
        "SELL_MIN_MARGIN_PCT", "SELL_MAX_OPEN_LISTINGS", "REPRICE_DROP_PCT",
        "AGG_SCAN_TOP_N", "LISTINGS_FETCH_LIMIT",
        "PRICE_RANGE_SCAN_ENABLED", "PRICE_RANGE_MIN_USD",
        "PRICE_RANGE_MAX_USD", "PRICE_RANGE_MAX_TITLES", "PRICE_RANGE_MAX_PAGES",
        "PRICE_RANGE_CYCLE_INTERVAL",
        "CROSS_MARKET_FEE_AWARE", "CROSS_MARKET_DESTINATION_FEE",
        "CROSS_MARKET_TARGET_ENABLED", "CROSS_MARKET_TARGET_MARGIN",
        "CROSS_MARKET_TARGET_MAX_PER_CYCLE",
        "LOW_FEE_ITEMS_SCAN_ENABLED", "LOW_FEE_ITEMS_SCAN_LIMIT",
        "DMARKET_INTERNAL_UNDERPRICED_ENABLED", "DM_UNDERPRICED_SALES_DAYS",
        "DM_UNDERPRICED_PERCENTILE", "DM_UNDERPRICED_MIN_MARGIN_PCT",
        "STRICT_MICROSTRUCTURE_FILTERS",
        "WITHDRAWAL_FEE_RATE", "MIN_TOTAL_SALES", "MIN_BID_ASK_COUNT",
        "OBI_ENABLED", "OFI_ENABLED",
        "MAX_TOTAL_INVENTORY_VALUE", "MAX_TOTAL_INVENTORY_ITEMS", "MAX_SAME_ITEM_HOLDINGS",
    })

    def __init__(self):
        self._last_mtime: float = 0.0
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start watching .env in background."""
        if self._running:
            return
        self._running = True
        self._last_mtime = self._get_mtime()
        self._task = asyncio.create_task(self._watch_loop())
        logger.info(f"[ConfigWatcher] Watching {_ENV_PATH} every {_WATCH_INTERVAL}s")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _watch_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(_WATCH_INTERVAL)
                current_mtime = self._get_mtime()
                if current_mtime > self._last_mtime:
                    self._last_mtime = current_mtime
                    await self._reload()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[ConfigWatcher] Loop error: {e}")

    async def _reload(self) -> None:
        """Re-read .env and update Config attributes."""
        changed = []
        try:
            with open(_ENV_PATH, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if not value:
                        continue
                    if key in self._reloadable_keys:
                        old = getattr(Config, key, None)
                        self._apply(key, value)
                        new = getattr(Config, key, None)
                        if old != new:
                            changed.append(f"{key}={new}")

            if changed:
                logger.info(f"[ConfigWatcher] Reloaded {len(changed)} key(s): {', '.join(changed[:8])}")
        except Exception as e:
            logger.warning(f"[ConfigWatcher] Reload failed: {e}")

    @staticmethod
    def _apply(key: str, value: str) -> None:
        """Apply a single config value to Config class."""
        try:
            if hasattr(Config, key) and isinstance(getattr(Config, key), bool):
                setattr(Config, key, value.lower() in ("true", "1", "yes"))
            elif hasattr(Config, key) and isinstance(getattr(Config, key), int):
                setattr(Config, key, int(float(value)))
            elif hasattr(Config, key) and isinstance(getattr(Config, key), float):
                setattr(Config, key, float(value))
            elif hasattr(Config, key) and isinstance(getattr(Config, key), str):
                setattr(Config, key, value)
        except (ValueError, TypeError):
            pass

    @staticmethod
    def _get_mtime() -> float:
        try:
            return _ENV_PATH.stat().st_mtime
        except OSError:
            return 0.0


config_watcher = ConfigWatcher()
