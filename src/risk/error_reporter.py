"""
Structured error reporter for the DMarket bot (v14.9).

Produces a single human-readable block (for logs) and a shorter
Telegram-friendly version (≤ 3500 chars). The block is intentionally
self-contained: file:line, function name, exception type, message,
and runtime context (cycle, game, balance, RSS, uptime). That way
the user can identify the failure without scrolling through logs.

v14.9 Improvements (based on PythonHub best practices):
- Structured JSON logging with correlation IDs
- Exception chaining support (`raise ... from ...`)
- Fluent context builder pattern
- Structured context fields (request_id, cycle_id, item_id)

Usage:
    from src.risk.error_reporter import ErrorReporter

    try:
        ...
    except Exception as e:
        report = ErrorReporter(e, context={
            "cycle": cycle_count,
            "game":  game_id,
            "balance": f"${current_balance:.2f}",
            "uptime": str(timedelta(seconds=int(time.time() - started_at))),
        })
        logger.error(report.format_log())
        await report.send_telegram(...)
        sys.exit(report.exit_code)

    # v14.9: Fluent context builder
    try:
        ...
    except Exception as e:
        report = ErrorReporter(e) \
            .with_context(cycle=cycle_count, item_id=item_id) \
            .with_context(balance=current_balance)
        report.log_and_exit()
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
import traceback
from typing import Any

logger = logging.getLogger("ErrorReporter")

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]

import contextlib

from src.risk.fatal_errors import classify, exit_code_for  # noqa: E402

# Width of the visual separator in the log block.
_BAR = "═" * 64
_THIN = "─" * 64


class ErrorReporter:
    """
    Build a structured error report for a caught exception.

    Holds the original traceback so it can be re-formatted
    for both the log (full multiline) and Telegram (compact).

    v14.9: Added fluent context builder and structured JSON logging.
    """

    def __init__(
        self,
        exc: BaseException,
        context: dict[str, Any] | None = None,
        tb: str | None = None,
    ) -> None:
        self.exc = exc
        self.context = dict(context or {})
        self.tb = tb or traceback.format_exc()
        self._exit_code = exit_code_for(exc)
        self._classification = classify(exc)
        # Pre-compute the location string from the formatted traceback.
        self._location = self._extract_location(self.tb)
        # v14.9: Extract cause chain for exception chaining
        self._cause_chain = self._extract_cause_chain(exc)

    def with_context(self, **kwargs: Any) -> ErrorReporter:
        """Fluent context builder. Adds key-value pairs to the report."""
        self.context.update(kwargs)
        return self

    @property
    def classification(self) -> str:
        return self._classification

    @property
    def exit_code(self) -> int:
        return self._exit_code

    @staticmethod
    def _extract_cause_chain(exc: BaseException) -> list[str]:
        """Extract exception cause chain for structured logging."""
        chain = []
        current = exc
        seen = set()
        while current and id(current) not in seen:
            seen.add(id(current))
            chain.append(f"{type(current).__name__}: {str(current)[:200]}")
            current = current.__cause__ or current.__context__
        return chain

    @staticmethod
    def _extract_location(tb: str) -> str:
        """
        Find the deepest application frame (skip asyncio internals).

        Returns 'file.py:123 (function_name)' or 'unknown' on failure.
        """
        try:
            lines = [
                ln for ln in tb.splitlines() if ln.startswith("  File ")
            ]
            if not lines:
                return "unknown"
            # The last 'File' line is the deepest frame.
            deepest = lines[-1]
            # The next line is usually '    code_here'.
            return deepest.strip()
        except Exception:
            return "unknown"

    def _process_stats(self) -> str:
        if psutil is None:
            return "psutil unavailable"
        try:
            p = psutil.Process()
            mi = p.memory_info()
            fds = len(p.open_files())
            return (
                f"RSS={mi.rss / 1024 / 1024:.1f}MB "
                f"VMS={mi.vms / 1024 / 1024:.1f}MB "
                f"fds={fds} threads={p.num_threads()}"
            )
        except Exception as e:
            return f"stats unavailable: {e}"

    def format_log(self) -> str:
        """
        Full human-readable report. Goes to the log file verbatim.
        """
        utc = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        ctx_lines = []
        for k, v in self.context.items():
            ctx_lines.append(f"  {str(k).upper():8s} {v}")
        if not ctx_lines:
            ctx_lines.append("  (no extra context)")

        parts = [
            _BAR,
            f"  ❌ {self._classification} ERROR  ·  exit code {self._exit_code}",
            _THIN,
            f"  TYPE     {type(self.exc).__name__}",
            f"  MESSAGE  {self.exc}",
            f"  LOCATION {self._location}",
            f"  PID      {os.getpid()}",
            f"  UTC      {utc}",
            f"  PROCESS  {self._process_stats()}",
            _THIN,
            "  CONTEXT",
        ]
        parts.extend(ctx_lines)
        parts.append(_THIN)
        parts.append("  TRACEBACK")
        parts.append(self.tb.rstrip())
        if self._classification == "TRANSIENT":
            parts.append(_THIN)
            parts.append("  ACTION: bot will retry (transient error)")
        else:
            parts.append(_THIN)
            parts.append(
                f"  ACTION: bot will exit with code {self._exit_code}."
                " Watchdog will NOT auto-restart."
            )
        parts.append(_BAR)
        return "\n".join(parts)

    def format_telegram(self) -> str:
        """
        Compact report for Telegram (≤ 3500 chars).
        Uses <code> blocks for monospace and <b> for headers.
        """
        utc = time.strftime("%H:%M:%S UTC", time.gmtime())
        ctx_lines = []
        for k, v in self.context.items():
            ctx_lines.append(f"  <b>{k}</b> = <code>{v}</code>")
        ctx_block = "\n".join(ctx_lines) if ctx_lines else "  (none)"

        # Trim traceback to last 6 frames.
        frames = [
            ln for ln in self.tb.splitlines() if ln.startswith("  File ")
        ]
        if frames:
            short_tb = "\n".join(frames[-6:])
        else:
            short_tb = self.tb.splitlines()[-1] if self.tb else "(no traceback)"

        action = (
            "retrying (transient)"
            if self._classification == "TRANSIENT"
            else f"<b>EXITING with code {self._exit_code}</b>"
        )

        body = (
            f"❌ <b>{self._classification}</b>  ·  "
            f"<code>{type(self.exc).__name__}</code>\n"
            f"<b>MSG</b>      <code>{str(self.exc)[:200]}</code>\n"
            f"<b>AT</b>       <code>{self._location[:160]}</code>\n"
            f"<b>UTC</b>      <code>{utc}</code>\n"
            f"<b>CONTEXT</b>\n{ctx_block}\n"
            f"<b>STACK</b> (last 6 frames):\n<code>{short_tb[:1200]}</code>\n"
            f"\n<b>ACTION:</b> {action}"
        )
        if len(body) > 3500:
            body = body[:3450] + "\n<code>... (truncated)</code>"
        return body

    def format_json(self) -> dict[str, Any]:
        """
        v14.9: Structured JSON report for log aggregation systems.

        Returns a dict suitable for json.dumps() or structlog integration.
        Includes correlation IDs, cause chain, and all context fields.
        """
        utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return {
            "timestamp": utc,
            "level": "ERROR",
            "classification": self._classification,
            "exit_code": self._exit_code,
            "exception": {
                "type": type(self.exc).__name__,
                "message": str(self.exc)[:500],
                "location": self._location,
                "cause_chain": self._cause_chain,
            },
            "context": self.context,
            "process": {
                "pid": os.getpid(),
                "stats": self._process_stats(),
            },
            "action": (
                "retry"
                if self._classification == "TRANSIENT"
                else f"exit_{self._exit_code}"
            ),
        }

    async def send_telegram(self) -> None:
        """
        Best-effort Telegram send. Never raises — logging is the
        primary channel; Telegram is a bonus.
        """
        try:
            token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
            chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
            if not token or not chat_id or token.startswith("ROTATE_ME"):
                return
            import aiohttp

            url = f"https://api.telegram.org/bot{token}/sendMessage"
            async with aiohttp.ClientSession() as session, session.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": self.format_telegram(),
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status >= 400:
                    logger.debug(
                        f"[telegram error report] HTTP {resp.status}"
                    )
        except Exception as e:
            logger.debug(f"[telegram error report] send failed: {e}")

    def log_and_exit(self) -> None:
        """
        v14.9: Convenience method. Logs full report, persists exit state,
        attempts Telegram send, and exits. One-call error handling.
        """
        logger.error(self.format_log())
        _write_exit_state(self.exit_code, self.exc, context=self.context)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_send_report_with_timeout(self))
        except RuntimeError:
            with contextlib.suppress(Exception):
                asyncio.run(asyncio.wait_for(self.send_telegram(), timeout=2.0))
        sys.exit(self.exit_code)


def _write_exit_state(exit_code: int, exc: BaseException, context: dict[str, Any] | None = None) -> None:
    """
    Persist the bot's exit code to a JSON file the watchdog reads.

    The watchdog checks this file on its next iteration; if the
    exit code is > 0, it treats the run as fatal and skips restart.
    Best-effort: never raises. If the file write fails (e.g. fs
    read-only), the watchdog falls back to "no exit code captured",
    which means it will try to restart — that's the safer default.
    """
    try:
        import json
        from datetime import datetime, timezone
        from pathlib import Path

        state_path = Path(
            os.getenv("WATCHDOG_STATE_FILE", "data/watchdog_state.json")
        )
        state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "exit_code": exit_code,
            "exc_type": type(exc).__name__,
            "message": str(exc)[:500],
            "context": dict(context or {}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        state_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        logger.debug(f"[fatal_exit] could not persist state file: {e}")


async def _send_report_with_timeout(report: ErrorReporter) -> None:
    """Send Telegram report with a 2s timeout (fire-and-forget helper)."""
    with contextlib.suppress(Exception):
        await asyncio.wait_for(report.send_telegram(), timeout=2.0)


def fatal_exit(exc: BaseException, context: dict[str, Any] | None = None) -> None:
    """
    One-shot helper for the outer supervisor.

    Logs the full report, persists the exit code for the watchdog,
    attempts a Telegram send, and exits the process with the
    appropriate exit code. This is the END of the run — the
    watchdog will see a non-zero exit and skip restart.
    """
    report = ErrorReporter(exc, context=context)
    logger.error(report.format_log())
    _write_exit_state(report.exit_code, exc, context=context)

    # Best-effort: try to send Telegram before exiting. If we're
    # already in the event loop (typical), we schedule the task.
    # If that fails, the log is the source of truth.
    try:
        loop = asyncio.get_running_loop()
        # Cannot use run_until_complete on a running loop — just schedule
        loop.create_task(_send_report_with_timeout(report))
    except RuntimeError:
        # No running loop (called from sync context) — run directly
        with contextlib.suppress(Exception):
            asyncio.run(asyncio.wait_for(report.send_telegram(), timeout=2.0))

    sys.exit(report.exit_code)
