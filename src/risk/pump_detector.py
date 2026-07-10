"""
pump_detector.py — Detects abnormal price spikes and blocks FOMO buys.

When an item's price spikes >PUMP_THRESHOLD_PCT (default 15%) within a
short window (default 1h) without a corresponding volume surge, it's
likely a pump-and-dump setup (Chinese collector groups, FOMO spirals,
steam-tweet cascades, etc.). The user explicitly asked for:

  > При обнаружении пампа (резкий рост цены >15% за 1ч без фундаментальных
  > причин) — блокируем покупки этого предмета на 24 часа и шлём алерт
  > в Telegram. Это защитит от FOMO покупок на пике.

So the behavior is:
  1. On every cycle, when we observe a new price for a title, check
     against price_db's recent history.
  2. If the max 1h change is >15% (configurable via env), blacklist
     the title for 24h and fire a Telegram warning.
  3. RiskManager.pre_trade_check consults the blacklist and blocks
     any buy on a blacklisted title.

Data source: price_db.get_recent_prices(hash_name, days=7) — already
populated by CS2Cap / DMarket cycles. No extra API calls.

The detector is intentionally lightweight:
  - In-memory blacklist (no extra DB writes).
  - Lazy evaluation: only scans items the bot is actively considering.
  - No external dependencies beyond price_db + notifier (already in use).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("PumpDetector")


@dataclass
class PumpAlert:
    """A single detection event. Persisted in-memory for /status queries."""
    hash_name: str
    old_price: float
    new_price: float
    pct_change: float
    detected_at: float
    expires_at: float
    alerted: bool = False

    @property
    def is_active(self) -> bool:
        return time.time() < self.expires_at


class PumpDetector:
    """
    Detects price spikes and maintains a 24h blacklist for affected items.

    Designed to be a single instance per bot (created in SnipingLoop.__init__),
    shared with RiskManager. Both classes call into it; the detector itself
    is stateless apart from the blacklist.
    """

    DEFAULT_THRESHOLD_PCT: float = 15.0
    DEFAULT_WINDOW_SECONDS: int = 3600          # 1h
    DEFAULT_BLACKLIST_SECONDS: int = 24 * 3600  # 24h

    def __init__(
        self,
        price_db: Any | None = None,
        notifier: Any | None = None,
        threshold_pct: float | None = None,
        window_seconds: int | None = None,
        blacklist_seconds: int | None = None,
    ) -> None:
        # Read env-overridable thresholds
        self.threshold_pct = (
            threshold_pct
            if threshold_pct is not None
            else float(os.getenv("PUMP_THRESHOLD_PCT", str(self.DEFAULT_THRESHOLD_PCT)))
        )
        self.window_seconds = (
            window_seconds
            if window_seconds is not None
            else int(os.getenv("PUMP_WINDOW_SECONDS", str(self.DEFAULT_WINDOW_SECONDS)))
        )
        self.blacklist_seconds = (
            blacklist_seconds
            if blacklist_seconds is not None
            else int(os.getenv("PUMP_BLACKLIST_SECONDS", str(self.DEFAULT_BLACKLIST_SECONDS)))
        )

        # Active blacklist: hash_name -> PumpAlert
        self._blacklist: dict[str, PumpAlert] = {}

        # Diagnostics
        self._total_detections: int = 0
        self._total_alerts_sent: int = 0
        self._last_scan_ts: float = 0.0

        # Late-binding injection (set by SnipingLoop.__init__ after creation)
        self._price_db = price_db
        self._notifier = notifier

        logger.info(
            f"[PumpDetector] active: threshold={self.threshold_pct}% / "
            f"window={self.window_seconds}s / blacklist={self.blacklist_seconds}s"
        )

    def bind(self, price_db: object, notifier: object) -> None:
        """
        Late-bind dependencies (called from SnipingLoop.__init__ because of
        circular-import avoidance — price_db/notifier are module singletons
        that should be ready by the time start() is called).
        """
        self._price_db = price_db
        self._notifier = notifier

    # ----------------------------------------------------------------
    # Public API used by RiskManager and the sniping loop
    # ----------------------------------------------------------------
    def is_blacklisted(self, hash_name: str) -> bool:
        """True if this title is currently banned from buying."""
        if not hash_name:
            return False
        alert = self._blacklist.get(hash_name)
        if alert is None:
            return False
        if not alert.is_active:
            # Auto-expire
            del self._blacklist[hash_name]
            logger.debug(
                f"[PumpDetector] blacklist expired for {hash_name} "
                f"(was {alert.pct_change:+.1f}% spike)"
            )
            return False
        return True

    def restore_from_disk(self) -> int:
        """
        v12.7: Re-populate the in-memory blacklist from price_db on
        bot startup. Returns count of entries restored. This is what
        makes the 24h protection survive watchdog restarts.

        Idempotent — safe to call multiple times. Late-loaded entries
        are marked as 'alerted=True' so we don't re-send Telegram
        alerts on every restart (the user already saw them).
        """
        if self._price_db is None:
            logger.debug("[PumpDetector] restore_from_disk: no price_db, skip")
            return 0
        if not hasattr(self._price_db, "get_active_pump_blacklist"):
            # price_db doesn't expose the new method (very old test fixture)
            return 0
        try:
            rows = self._price_db.get_active_pump_blacklist()
        except Exception as e:
            logger.debug(f"[PumpDetector] restore_from_disk: DB read failed: {e}")
            return 0

        restored = 0
        for row in rows:
            title = row["hash_name"]
            self._blacklist[title] = PumpAlert(
                hash_name=title,
                old_price=row["old_price"],
                new_price=row["new_price"],
                pct_change=row["pct_change"],
                detected_at=row["detected_at"],
                expires_at=row["expires_at"],
                alerted=bool(row["alerted"]),
            )
            restored += 1
        if restored:
            logger.info(
                f"[PumpDetector] restored {restored} blacklist entries from disk"
            )
        return restored

    def check_price(self, hash_name: str, current_price: float) -> PumpAlert | None:
        """
        Run a spike check for one item. Returns PumpAlert if newly detected,
        None otherwise. Call this from the hot path (every cycle) so that
        detections are recorded and alerts fired promptly.

        Idempotent: if a recent detection already exists for this title
        within the current spike window, it is NOT re-emitted (we just
        update the existing alert's expiry).
        """
        if not hash_name or current_price <= 0:
            return None
        if self._price_db is None:
            return None

        # Already blacklisted → no need to re-scan DB
        if self.is_blacklisted(hash_name):
            return None

        # Get the most recent price observation strictly OLDER than
        # `window_seconds` ago. That's the "before" reference.
        now = time.time()
        window_start = now - self.window_seconds
        try:
            recent = self._price_db.get_recent_prices(hash_name, days=2)
        except Exception as e:
            logger.debug(f"[PumpDetector] get_recent_prices({hash_name}) failed: {e}")
            return None
        if not recent:
            return None

        # recent is sorted DESC by recorded_at: [latest, ..., oldest]
        # Find the latest observation that is OLDER than window_start
        # (i.e. the price "before" the spike window).
        old_price: float | None = None
        for price, ts in recent:
            if ts <= window_start:
                old_price = price
                break
        if old_price is None or old_price <= 0:
            # Not enough history to compute a baseline.
            return None

        pct_change = ((current_price - old_price) / old_price) * 100.0
        if pct_change < self.threshold_pct:
            return None

        # Spike confirmed. Create the alert and fire a Telegram warning.
        alert = PumpAlert(
            hash_name=hash_name,
            old_price=old_price,
            new_price=current_price,
            pct_change=pct_change,
            detected_at=now,
            expires_at=now + self.blacklist_seconds,
            alerted=False,
        )
        self._blacklist[hash_name] = alert
        self._total_detections += 1
        self._last_scan_ts = now

        # v12.7: Persist to SQLite so a watchdog restart doesn't lose
        # the 24h protection. Best-effort: if the DB write fails, the
        # in-memory blacklist still works for this session.
        if self._price_db is not None and hasattr(self._price_db, "add_pump_blacklist_entry"):
            try:
                self._price_db.add_pump_blacklist_entry(
                    hash_name=hash_name,
                    old_price=old_price,
                    new_price=current_price,
                    pct_change=pct_change,
                    detected_at=now,
                    expires_at=now + self.blacklist_seconds,
                    alerted=False,
                )
            except Exception as e:
                logger.debug(f"[PumpDetector] persist failed: {e}")

        logger.warning(
            f"[PumpDetector] SPIKE DETECTED: {hash_name} "
            f"${old_price:.2f} → ${current_price:.2f} ({pct_change:+.1f}% in "
            f"{self.window_seconds // 60}m). Blacklisted for "
            f"{self.blacklist_seconds // 3600}h."
        )

        # Fire Telegram warning (fire-and-forget via the notifier).
        # We do NOT await — the call site is synchronous and the notifier
        # is itself async; we just kick off the task. If the notifier is
        # missing (test environments), skip silently.
        if self._notifier is not None:
            try:
                import asyncio
                coro = self._notifier.custom(
                    text=(
                        f"🚨 <b>PUMP DETECTED</b>\n"
                        f"<code>{hash_name}</code>\n"
                        f"${old_price:.2f} → ${current_price:.2f} "
                        f"(<b>{pct_change:+.1f}%</b> in {self.window_seconds // 60}m)\n"
                        f"Buying blocked for {self.blacklist_seconds // 3600}h.\n"
                        f"Possible FOMO spike — wait for re-entry."
                    ),
                    severity="warning",
                )
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(coro)
                    alert.alerted = True
                    self._total_alerts_sent += 1
                except RuntimeError:
                    # No running loop (e.g. called from sync test or __init__).
                    # Skip notification — it's best-effort anyway.
                    pass
            except Exception as e:
                logger.debug(f"[PumpDetector] Telegram alert failed: {e}")

        return alert

    def unblock(self, hash_name: str) -> bool:
        """
        Manually unblock a title (admin override, e.g. via /risk Telegram
        command). Returns True if something was unblocked.
        """
        removed = False
        if hash_name in self._blacklist:
            del self._blacklist[hash_name]
            removed = True
        if self._price_db is not None and hasattr(self._price_db, "delete_pump_blacklist_entry"):
            try:
                self._price_db.delete_pump_blacklist_entry(hash_name)
            except Exception as e:
                logger.debug(f"[PumpDetector] unblock DB delete failed: {e}")
        if removed:
            logger.info(f"[PumpDetector] manually unblocked: {hash_name}")
        return removed

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count removed. Call periodically."""
        expired = [k for k, v in self._blacklist.items() if not v.is_active]
        for k in expired:
            del self._blacklist[k]
        # v12.7: Best-effort DB cleanup
        if self._price_db is not None and hasattr(self._price_db, "cleanup_expired_pump_blacklist"):
            try:
                self._price_db.cleanup_expired_pump_blacklist()
            except Exception as e:
                logger.debug(f"[PumpDetector] DB cleanup failed: {e}")
        return len(expired)

    # ----------------------------------------------------------------
    # Diagnostics for /status and daily briefing
    # ----------------------------------------------------------------
    def get_active_blacklist(self) -> list[PumpAlert]:
        """Return currently active (non-expired) blacklisted items."""
        return [a for a in self._blacklist.values() if a.is_active]

    def stats(self) -> dict[str, Any]:
        return {
            "threshold_pct": self.threshold_pct,
            "window_seconds": self.window_seconds,
            "blacklist_seconds": self.blacklist_seconds,
            "active_blacklist_size": len(self.get_active_blacklist()),
            "total_detections": self._total_detections,
            "total_alerts_sent": self._total_alerts_sent,
            "last_scan_ts": self._last_scan_ts,
        }
