"""
health_server.py — HTTP /healthz, /readyz, /metrics endpoints for the bot.

Why:
The watchdog previously relied on a file timestamp to detect a hung bot.
That's coarse — it only tells us "the bot wrote something in the last
5 min", not "is the bot actually doing work, or stuck in a deadlock
with the GIL?".

The aiohttp server here gives the watchdog (or any operator with curl)
real-time visibility into the bot's health and risk state.

Endpoints:
  GET /healthz    → 200 always if process is up. JSON body has detailed
                    metrics. Returns 503 if process is shutting down.
  GET /readyz     → 200 if the bot is healthy AND not in a global halt
                    (trading would be allowed). 503 otherwise.
  GET /metrics    → Prometheus text exposition format (for Grafana etc.)

Design:
- HealthState is a process-wide singleton. The trading loop updates
  metrics (last_cycle_ts, equity, etc.) at the end of every cycle.
- The aiohttp app binds to 127.0.0.1:<port> by default (NOT 0.0.0.0).
  External exposure would be a security issue; the watchdog runs on the
  same host.
- v12.9: Optional basic auth via HEALTH_USERNAME / HEALTH_PASSWORD env vars.
  If HEALTH_PASSWORD is set, all endpoints require HTTP basic auth.
  Without it, endpoints are unauthenticated (safe on localhost only).
- All handlers are sync (return JSON) — no I/O, no DB.
- Failure mode: if the aiohttp server fails to bind (port in use),
  the bot logs a warning and continues without it. Health is degraded
  but trading is not affected.
"""

from __future__ import annotations

import base64
import logging
import os
import time
from typing import Any, Dict, Optional

try:
    from aiohttp import web
except ImportError:  # pragma: no cover
    # aiohttp is already a hard dep (used by DMarketAPIClient), but we
    # guard here so unit tests can import this module without crashing
    # if a future refactor breaks that assumption.
    web = None  # type: ignore[assignment]

logger = logging.getLogger("HealthServer")


# =====================================================================
# HealthState — process-wide singleton
# =====================================================================

class HealthState:
    """
    Mutable container of bot metrics. The trading loop calls setters
    (set_equity, mark_cycle, etc.) on every cycle; the HTTP handlers
    read them on demand.

    Not thread-safe (the bot is single-threaded asyncio), but the
    values are scalar so even torn reads just give slightly stale data.
    """

    def __init__(self) -> None:
        self._boot_ts: float = time.time()
        self._last_cycle_ts: float = 0.0
        self._cycle_count: int = 0
        self._current_equity_usd: float = 0.0
        self._peak_equity_usd: float = 0.0
        self._drawdown_pct: float = 0.0
        self._daily_pnl_usd: float = 0.0
        self._daily_trade_count: int = 0
        self._soft_halt_active: bool = False
        self._daily_halt_active: bool = False
        self._pump_blacklist_size: int = 0
        self._pump_total_detections: int = 0
        self._cs2cap_quota_pct: Optional[float] = None
        self._shutting_down: bool = False
        self._last_error: Optional[str] = None
        self._dmarket_cb: Optional[Dict[str, Any]] = None
        self._cs2cap_cb: Optional[Dict[str, Any]] = None

    # ----- setters (called by the trading loop) -----
    def mark_cycle(self, equity_usd: float, peak_equity_usd: float,
                   drawdown_pct: float) -> None:
        self._last_cycle_ts = time.time()
        self._cycle_count += 1
        self._current_equity_usd = equity_usd
        self._peak_equity_usd = peak_equity_usd
        self._drawdown_pct = drawdown_pct

    def set_daily_stats(self, pnl_usd: float, trade_count: int) -> None:
        self._daily_pnl_usd = pnl_usd
        self._daily_trade_count = trade_count

    def set_halts(self, soft_halt: bool, daily_halt: bool) -> None:
        self._soft_halt_active = soft_halt
        self._daily_halt_active = daily_halt

    def set_pump_stats(self, blacklist_size: int, total_detections: int) -> None:
        self._pump_blacklist_size = blacklist_size
        self._pump_total_detections = total_detections

    def set_cs2cap_quota_pct(self, pct: Optional[float]) -> None:
        self._cs2cap_quota_pct = pct

    def set_circuit_breakers(self, dmarket_cb: Optional[Dict[str, Any]] = None,
                             cs2cap_cb: Optional[Dict[str, Any]] = None) -> None:
        """v12.7: Track circuit breaker states for diagnostics (P4-2)."""
        self._dmarket_cb = dmarket_cb
        self._cs2cap_cb = cs2cap_cb

    def record_error(self, error: str) -> None:
        """Track the most recent fatal/non-fatal error (for diagnostics)."""
        self._last_error = error[:500]

    def set_shutting_down(self, value: bool = True) -> None:
        self._shutting_down = value

    # ----- getters (called by HTTP handlers) -----
    def snapshot(self) -> Dict[str, Any]:
        """JSON-friendly snapshot. Always returns a fresh dict."""
        return {
            "status": "shutting_down" if self._shutting_down else "ok",
            "uptime_s": round(time.time() - self._boot_ts, 1),
            "process": {
                "cycle_count": self._cycle_count,
                "last_cycle_ts": self._last_cycle_ts,
                "seconds_since_last_cycle": (
                    round(time.time() - self._last_cycle_ts, 1)
                    if self._last_cycle_ts > 0
                    else None
                ),
            },
            "equity": {
                "current_usd": round(self._current_equity_usd, 2),
                "peak_usd": round(self._peak_equity_usd, 2),
                "drawdown_pct": round(self._drawdown_pct, 2),
            },
            "daily": {
                "pnl_usd": round(self._daily_pnl_usd, 2),
                "trade_count": self._daily_trade_count,
            },
            "halts": {
                "soft_halt_active": self._soft_halt_active,
                "daily_halt_active": self._daily_halt_active,
            },
            "pump_detector": {
                "active_blacklist_size": self._pump_blacklist_size,
                "total_detections": self._pump_total_detections,
            },
            "cs2cap": {
                "monthly_quota_used_pct": (
                    round(self._cs2cap_quota_pct, 2)
                    if self._cs2cap_quota_pct is not None
                    else None
                ),
            },
            "circuit_breakers": {
                "dmarket": self._dmarket_cb or {"state": "unknown"},
                "cs2cap": self._cs2cap_cb or {"state": "unknown"},
                "telegram": self._get_telegram_cb_status(),
            },
            "last_error": self._last_error,
        }

    def is_ready(self) -> bool:
        """True if the bot is healthy AND willing to trade."""
        if self._shutting_down:
            return False
        if self._daily_halt_active:
            return False
        # Soft halt is OK (the bot still trades at half size).
        return True

    def _get_telegram_cb_status(self) -> Dict[str, Any]:
        """v12.7: Get Telegram notifier circuit breaker status."""
        try:
            from src.telegram.notifier import notifier
            return notifier.stats().get("circuit_breaker", {"state": "unknown"})
        except Exception:
            return {"state": "unknown"}


# Module-level singleton, importable as:
#   from src.utils.health_server import health_state, start_health_server
health_state = HealthState()


# =====================================================================
# HTTP handlers
# =====================================================================

async def _handle_healthz(_request: "web.Request") -> "web.Response":
    """Liveness: returns 200 if the process is alive, 503 if shutting down."""
    snap = health_state.snapshot()
    status = snap["status"]
    if status == "shutting_down":
        return web.json_response(snap, status=503)
    return web.json_response(snap, status=200)


async def _handle_readyz(_request: "web.Request") -> "web.Response":
    """Readiness: 200 if bot is willing to trade, 503 if halted."""
    snap = health_state.snapshot()
    ready = health_state.is_ready()
    return web.json_response(
        {**snap, "ready": ready},
        status=200 if ready else 503,
    )


async def _handle_metrics(_request: "web.Request") -> "web.Response":
    """Prometheus text exposition format (best-effort)."""
    snap = health_state.snapshot()
    lines: list[str] = []

    # Process metrics
    lines.append("# HELP bot_uptime_seconds Seconds since bot process started.")
    lines.append("# TYPE bot_uptime_seconds gauge")
    lines.append(f"bot_uptime_seconds {snap['uptime_s']}")

    lines.append("# HELP bot_cycle_count_total Total scan cycles completed.")
    lines.append("# TYPE bot_cycle_count_total counter")
    lines.append(f"bot_cycle_count_total {snap['process']['cycle_count']}")

    sc = snap["process"]["seconds_since_last_cycle"]
    if sc is not None:
        lines.append("# HELP bot_seconds_since_last_cycle Seconds since last scan cycle.")
        lines.append("# TYPE bot_seconds_since_last_cycle gauge")
        lines.append(f"bot_seconds_since_last_cycle {sc}")

    # Equity metrics
    lines.append("# HELP bot_equity_usd Current equity in USD.")
    lines.append("# TYPE bot_equity_usd gauge")
    lines.append(f"bot_equity_usd {snap['equity']['current_usd']}")
    lines.append(f"bot_equity_peak_usd {snap['equity']['peak_usd']}")
    lines.append(f"bot_equity_drawdown_pct {snap['equity']['drawdown_pct']}")

    # Daily stats
    lines.append("# HELP bot_daily_pnl_usd Realized PnL for current UTC day.")
    lines.append("# TYPE bot_daily_pnl_usd gauge")
    lines.append(f"bot_daily_pnl_usd {snap['daily']['pnl_usd']}")
    lines.append(f"bot_daily_trade_count {snap['daily']['trade_count']}")

    # Halts (1/0)
    lines.append("# HELP bot_soft_halt_active 1 if soft-halt is active, else 0.")
    lines.append("# TYPE bot_soft_halt_active gauge")
    lines.append(f"bot_soft_halt_active {1 if snap['halts']['soft_halt_active'] else 0}")
    lines.append(f"bot_daily_halt_active {1 if snap['halts']['daily_halt_active'] else 0}")

    # Pump detector
    lines.append("# HELP bot_pump_blacklist_size Active pump-blacklisted items.")
    lines.append("# TYPE bot_pump_blacklist_size gauge")
    lines.append(f"bot_pump_blacklist_size {snap['pump_detector']['active_blacklist_size']}")
    lines.append(f"bot_pump_total_detections_total {snap['pump_detector']['total_detections']}")

    # CS2Cap quota
    quota = snap["cs2cap"]["monthly_quota_used_pct"]
    if quota is not None:
        lines.append("# HELP bot_cs2cap_quota_used_pct Percent of CS2Cap monthly quota used.")
        lines.append("# TYPE bot_cs2cap_quota_used_pct gauge")
        lines.append(f"bot_cs2cap_quota_used_pct {quota}")

    return web.Response(
        text="\n".join(lines) + "\n",
        content_type="text/plain; version=0.0.4",
    )


# =====================================================================
# Optional Basic Auth (v12.9)
# =====================================================================

def _check_auth(request: "web.Request") -> bool:
    """Check HTTP basic auth against HEALTH_USERNAME / HEALTH_PASSWORD.
    
    If HEALTH_PASSWORD is not set, auth is disabled (localhost-only mode).
    Returns True if auth passes or is disabled.
    """
    expected_user = os.getenv("HEALTH_USERNAME", "")
    expected_pass = os.getenv("HEALTH_PASSWORD", "")
    if not expected_pass:
        return True  # No password set = localhost-only, no auth needed
    
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        return False
    
    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        user, _, password = decoded.partition(":")
        return user == expected_user and password == expected_pass
    except Exception:
        return False


@web.middleware
async def _auth_middleware(request: "web.Request", handler: Any) -> "web.Response":
    """Apply basic auth to all health endpoints if HEALTH_PASSWORD is set."""
    if not _check_auth(request):
        return web.Response(
            status=401,
            text='{"error":"unauthorized"}',
            content_type="application/json",
            headers={"WWW-Authenticate": 'Basic realm="health metrics"'},
        )
    return await handler(request)


# =====================================================================
# Server lifecycle
# =====================================================================

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9090


async def start_health_server(
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> "Optional[web.AppRunner]":
    """
    Start the aiohttp health server. Returns the AppRunner (for shutdown)
    or None if aiohttp is not available / port is busy.

    The server runs as a background task on the bot's event loop. It
    binds to 127.0.0.1 by default (localhost only) — exposing it
    externally would leak the bot's risk state to anyone on the network.

    To enable, set HEALTH_PORT in the bot's environment. Default is OFF
    (returns None immediately) to keep the production blast radius small.
    """
    if web is None:
        logger.warning("[health_server] aiohttp not available; health server disabled")
        return None

    use_port = int(os.getenv("HEALTH_PORT", "0")) if port is None else int(port)
    if use_port <= 0:
        # Disabled — operator hasn't set HEALTH_PORT.
        return None

    use_host = os.getenv("HEALTH_HOST", DEFAULT_HOST) if host is None else host

    app = web.Application(middlewares=[_auth_middleware])
    app.router.add_get("/healthz", _handle_healthz)
    app.router.add_get("/readyz", _handle_readyz)
    app.router.add_get("/metrics", _handle_metrics)

    runner = web.AppRunner(app)
    try:
        await runner.setup()
        site = web.TCPSite(runner, use_host, use_port)
        await site.start()
    except OSError as e:
        logger.warning(
            f"[health_server] could not bind {use_host}:{use_port}: {e}. "
            f"Bot continues without health server.",
            exc_info=True,
        )
        await runner.cleanup()
        return None

    logger.info(
        f"[health_server] listening on http://{use_host}:{use_port} "
        f"(endpoints: /healthz /readyz /metrics)"
    )
    return runner


async def stop_health_server(runner: Optional["web.AppRunner"]) -> None:
    """Cleanly shut down the health server (called on bot exit)."""
    if runner is None:
        return
    try:
        await runner.cleanup()
    except Exception as e:
        logger.debug(f"[health_server] cleanup error: {e}")


def is_enabled() -> bool:
    """True if HEALTH_PORT is set in the environment (server will start)."""
    return int(os.getenv("HEALTH_PORT", "0") or "0") > 0
