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
- v15.2: Uses prometheus_client for proper metric types and formatting.
"""

from __future__ import annotations

import base64
import logging
import os
import time
from typing import Any

try:
    from aiohttp import web
except ImportError:  # pragma: no cover
    # aiohttp is already a hard dep (used by DMarketAPIClient), but we
    # guard here so unit tests can import this module without crashing
    # if a future refactor breaks that assumption.
    web = None  # type: ignore[assignment]

# v15.2: prometheus_client for proper metric types
try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

logger = logging.getLogger("HealthServer")


# =====================================================================
# Prometheus Metrics (v15.2)
# =====================================================================

if HAS_PROMETHEUS:
    METRIC_UPTIME = Gauge("bot_uptime_seconds", "Seconds since bot process started")
    METRIC_CYCLES = Counter("bot_cycle_count_total", "Total scan cycles completed")
    METRIC_SECONDS_SINCE_CYCLE = Gauge("bot_seconds_since_last_cycle", "Seconds since last scan cycle")
    METRIC_EQUITY = Gauge("bot_equity_usd", "Current equity in USD")
    METRIC_EQUITY_PEAK = Gauge("bot_equity_peak_usd", "Peak equity in USD")
    METRIC_DRAWDOWN = Gauge("bot_equity_drawdown_pct", "Current drawdown percentage")
    METRIC_DAILY_PNL = Gauge("bot_daily_pnl_usd", "Realized PnL for current UTC day")
    METRIC_DAILY_TRADES = Gauge("bot_daily_trade_count", "Trade count for current UTC day")
    METRIC_SOFT_HALT = Gauge("bot_soft_halt_active", "1 if soft-halt is active")
    METRIC_DAILY_HALT = Gauge("bot_daily_halt_active", "1 if daily halt is active")
    METRIC_PUMP_BLACKLIST = Gauge("bot_pump_blacklist_size", "Active pump-blacklisted items")
    METRIC_PUMP_DETECTIONS = Gauge("bot_pump_total_detections_total", "Total pump detections")
    METRIC_ORACLE_SOURCES = Gauge("bot_oracle_sources_active", "Number of active oracle sources")


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
        self._oracle_sources_active: float | None = None
        self._shutting_down: bool = False
        self._last_error: str | None = None
        self._dmarket_cb: dict[str, Any] | None = None
        self._oracle_cb: dict[str, Any] | None = None

    # ----- setters (called by the trading loop) -----
    def mark_cycle(self, equity_usd: float, peak_equity_usd: float,
                   drawdown_pct: float) -> None:
        self._last_cycle_ts = time.time()
        self._cycle_count += 1
        self._current_equity_usd = equity_usd
        self._peak_equity_usd = peak_equity_usd
        self._drawdown_pct = drawdown_pct

        # v15.2: Update prometheus metrics
        if HAS_PROMETHEUS:
            METRIC_CYCLES.inc()
            METRIC_EQUITY.set(equity_usd)
            METRIC_EQUITY_PEAK.set(peak_equity_usd)
            METRIC_DRAWDOWN.set(drawdown_pct)

    def set_daily_stats(self, pnl_usd: float, trade_count: int) -> None:
        self._daily_pnl_usd = pnl_usd
        self._daily_trade_count = trade_count
        # v15.2: Update prometheus metrics
        if HAS_PROMETHEUS:
            METRIC_DAILY_PNL.set(pnl_usd)
            METRIC_DAILY_TRADES.set(trade_count)

    def set_halts(self, soft_halt: bool, daily_halt: bool) -> None:
        self._soft_halt_active = soft_halt
        self._daily_halt_active = daily_halt
        # v15.2: Update prometheus metrics
        if HAS_PROMETHEUS:
            METRIC_SOFT_HALT.set(1 if soft_halt else 0)
            METRIC_DAILY_HALT.set(1 if daily_halt else 0)

    def set_pump_stats(self, blacklist_size: int, total_detections: int) -> None:
        self._pump_blacklist_size = blacklist_size
        self._pump_total_detections = total_detections
        # v15.2: Update prometheus metrics
        if HAS_PROMETHEUS:
            METRIC_PUMP_BLACKLIST.set(blacklist_size)
            METRIC_PUMP_DETECTIONS.set(total_detections)

    def set_oracle_sources_active(self, pct: float | None) -> None:
        self._oracle_sources_active = pct
        # v15.2: Update prometheus metrics
        if HAS_PROMETHEUS and pct is not None:
            METRIC_ORACLE_SOURCES.set(pct)

    def set_circuit_breakers(self, dmarket_cb: dict[str, Any] | None = None,
                             oracle_cb: dict[str, Any] | None = None) -> None:
        """v12.7: Track circuit breaker states for diagnostics (P4-2)."""
        self._dmarket_cb = dmarket_cb
        self._oracle_cb = oracle_cb

    def record_error(self, error: str) -> None:
        """Track the most recent fatal/non-fatal error (for diagnostics)."""
        self._last_error = error[:500]

    def set_shutting_down(self, value: bool = True) -> None:
        self._shutting_down = value

    # ----- getters (called by HTTP handlers) -----
    def snapshot(self) -> dict[str, Any]:
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
            "oracle": {
                "sources_active": (
                    round(self._oracle_sources_active, 2)
                    if self._oracle_sources_active is not None
                    else None
                ),
            },
            "circuit_breakers": {
                "dmarket": self._dmarket_cb or {"state": "unknown"},
                "oracle": self._oracle_cb or {"state": "unknown"},
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

    def _get_telegram_cb_status(self) -> dict[str, Any]:
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

async def _handle_healthz(_request: web.Request) -> web.Response:
    """Liveness: returns 200 if the process is alive, 503 if shutting down."""
    snap = health_state.snapshot()
    status = snap["status"]
    if status == "shutting_down":
        return web.json_response(snap, status=503)
    return web.json_response(snap, status=200)


async def _handle_readyz(_request: web.Request) -> web.Response:
    """Readiness: 200 if bot is willing to trade, 503 if halted."""
    snap = health_state.snapshot()
    ready = health_state.is_ready()
    return web.json_response(
        {**snap, "ready": ready},
        status=200 if ready else 503,
    )


async def _handle_metrics(_request: web.Request) -> web.Response:
    """Prometheus metrics endpoint.
    
    v15.2: Uses prometheus_client.generate_latest() for proper formatting.
    Falls back to manual text if prometheus_client is not installed.
    """
    # Update uptime metric
    if HAS_PROMETHEUS:
        METRIC_UPTIME.set(time.time() - health_state._boot_ts)
        sc = time.time() - health_state._last_cycle_ts if health_state._last_cycle_ts > 0 else 0
        METRIC_SECONDS_SINCE_CYCLE.set(sc)

        return web.Response(
            text=generate_latest().decode("utf-8"),
            content_type="text/plain; version=0.0.4",
            charset="utf-8",
        )

    # Fallback: manual text format (if prometheus_client not installed)
    snap = health_state.snapshot()
    lines: list[str] = []
    lines.append(f"bot_uptime_seconds {snap['uptime_s']}")
    lines.append(f"bot_cycle_count_total {snap['process']['cycle_count']}")
    return web.Response(
        text="\n".join(lines) + "\n",
        content_type="text/plain; version=0.0.4",
    )


# =====================================================================
# Optional Basic Auth (v12.9)
# =====================================================================

def _check_auth(request: web.Request) -> bool:
    """Check HTTP basic auth against HEALTH_USERNAME / HEALTH_PASSWORD.
    
    If HEALTH_PASSWORD is not set, auth is disabled (localhost-only mode).
    Returns True if auth passes or is disabled.
    """
    import hmac

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
        # v15.2: Timing-safe comparison to prevent side-channel attacks
        return hmac.compare_digest(user, expected_user) and hmac.compare_digest(password, expected_pass)
    except Exception:
        return False


@web.middleware
async def _auth_middleware(request: web.Request, handler: Any) -> web.Response:
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
    host: str | None = None,
    port: int | None = None,
) -> web.AppRunner | None:
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


async def stop_health_server(runner: web.AppRunner | None) -> None:
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
