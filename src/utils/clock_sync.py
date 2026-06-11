"""
Clock Sync — NTP-like sync with DMarket server (v12.2+).

Solves the X-Sign-Date 2-minute validity window problem.
DMarket rejects requests with timestamps > 120s out of sync.

Strategy:
1. On startup, send HEAD request to DMarket API
2. Parse the 'Date' header to get server time
3. Calculate offset between local time and server time
4. Cache the offset (refresh every 6h)
5. Provide `now()` function returning server-corrected time

This is more reliable than external NTP because we sync to the
exact server we're talking to, eliminating network drift.

Falls back to local time if server is unreachable.
"""

import asyncio
import time
import logging
from typing import Optional
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import aiohttp

logger = logging.getLogger("ClockSync")


class ClockSync:
    """
    Synchronizes local clock with DMarket server time.

    DMarket's X-Sign-Date must be within 2 minutes of server time.
    Local clock drift can cause silent 401 errors — this prevents that.
    """

    # DMarket base URL (HEAD request works without auth)
    DMARKET_URL = "https://api.dmarket.com"
    # Refresh interval: 6 hours (DMarket servers typically don't drift)
    REFRESH_INTERVAL_SECONDS = 6 * 3600
    # Max acceptable drift before warning
    WARN_DRIFT_SECONDS = 30
    # Max acceptable drift before failing
    MAX_DRIFT_SECONDS = 120

    def __init__(self):
        self._offset: float = 0.0
        self._last_sync: float = 0.0
        self._sync_count: int = 0
        self._drift_warnings: int = 0
        self._lock = asyncio.Lock()

    @property
    def offset(self) -> float:
        """Returns current clock offset in seconds (server - local)."""
        return self._offset

    @property
    def last_sync_time(self) -> float:
        """Returns Unix timestamp of last successful sync."""
        return self._last_sync

    @property
    def sync_count(self) -> int:
        """Returns number of successful syncs performed."""
        return self._sync_count

    @property
    def drift_warnings(self) -> int:
        """Returns number of drift warnings emitted."""
        return self._drift_warnings

    def now(self) -> float:
        """
        Returns server-corrected Unix timestamp.
        Use this for X-Sign-Date and any time-sensitive operations.

        Falls back to local time if no sync has been performed.
        """
        return time.time() + self._offset

    def now_iso(self) -> str:
        """Returns server-corrected ISO 8601 timestamp."""
        ts = self.now()
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    def needs_refresh(self) -> bool:
        """Returns True if sync is stale and should be refreshed."""
        if self._last_sync == 0.0:
            return True
        return (time.time() - self._last_sync) > self.REFRESH_INTERVAL_SECONDS

    async def sync_with_dmarket(self, session: Optional[aiohttp.ClientSession] = None) -> bool:
        """
        Sync local clock with DMarket server via HEAD request.

        Args:
            session: Optional aiohttp session (creates one if not provided)

        Returns:
            True if sync was successful, False otherwise
        """
        own_session = False
        if session is None:
            session = aiohttp.ClientSession()
            own_session = True

        try:
            async with self._lock:
                # Send HEAD request to DMarket — minimal payload
                # DMarket returns Date header in RFC 2822 format
                async with session.head(
                    f"{self.DMARKET_URL}/account/v1/balance",
                    allow_redirects=True,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if "Date" not in resp.headers:
                        logger.warning("ClockSync: DMarket response missing Date header")
                        return False

                    # Parse RFC 2822 date string
                    date_str = resp.headers["Date"]
                    try:
                        server_dt = parsedate_to_datetime(date_str)
                        if server_dt.tzinfo is None:
                            # Assume UTC if no timezone
                            server_dt = server_dt.replace(tzinfo=timezone.utc)
                        server_ts = server_dt.timestamp()
                    except (TypeError, ValueError) as e:
                        logger.warning(f"ClockSync: Failed to parse Date header '{date_str}': {e}", exc_info=True)
                        return False

                # Calculate offset
                local_ts_before = time.time()
                # Use the average of before/after to account for round-trip
                local_ts_after = time.time()
                local_ts = (local_ts_before + local_ts_after) / 2.0

                new_offset = server_ts - local_ts
                self._offset = new_offset
                self._last_sync = time.time()
                self._sync_count += 1

                abs_drift = abs(new_offset)
                if abs_drift > self.WARN_DRIFT_SECONDS:
                    self._drift_warnings += 1
                    if abs_drift > self.MAX_DRIFT_SECONDS:
                        logger.error(
                            f"ClockSync: CRITICAL drift {new_offset:.2f}s detected — "
                            f"DMarket may reject X-Sign-Date (>120s window)"
                        )
                    else:
                        logger.warning(
                            f"ClockSync: Drift {new_offset:.2f}s detected "
                            f"(DMarket allows ±120s)"
                        )
                else:
                    logger.info(
                        f"ClockSync: Synced with DMarket (offset={new_offset:.2f}s)"
                    )

                return True

        except asyncio.TimeoutError:
            logger.warning("ClockSync: DMarket HEAD request timed out")
            return False
        except aiohttp.ClientError as e:
            logger.warning(f"ClockSync: Network error: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.warning(f"ClockSync: Unexpected error: {e}", exc_info=True)
            return False
        finally:
            if own_session:
                await session.close()

    async def ensure_synced(self, session: Optional[aiohttp.ClientSession] = None) -> bool:
        """
        Ensures we have a recent sync. Performs sync if needed.

        Returns True if we have a valid sync (< MAX_DRIFT_SECONDS or just synced).
        """
        if not self.needs_refresh():
            return True
        return await self.sync_with_dmarket(session)

    def get_status(self) -> dict:
        """
        Returns diagnostic info about clock sync state.
        Useful for logging and monitoring.
        """
        age = time.time() - self._last_sync if self._last_sync > 0 else None
        return {
            "offset_seconds": round(self._offset, 3),
            "last_sync_ago_seconds": round(age, 1) if age is not None else None,
            "sync_count": self._sync_count,
            "drift_warnings": self._drift_warnings,
            "needs_refresh": self.needs_refresh(),
            "is_healthy": abs(self._offset) < self.MAX_DRIFT_SECONDS,
        }


# Singleton instance
clock_sync = ClockSync()


# Convenience function for quick time
def get_server_time() -> float:
    """
    Returns server-corrected Unix timestamp.
    If no sync has been performed yet, returns local time (with offset=0).
    """
    return clock_sync.now()
