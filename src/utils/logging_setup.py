"""logging_setup.py — Shared logging configuration for all entry points.

Every bot entry point (__main__.py, control_bot/__main__.py, bot.py)
must call configure_logging() so SecurityAuditor redaction is active
everywhere, not just when launched through __main__.py.

Usage:
    from src.utils.logging_setup import configure_logging
    configure_logging(component="control_bot")

CVE-2026-27003 / CVE-2026-32982: Without the SecurityAuditor logging
filter, Telegram bot tokens and other secrets could appear unredacted
in log files when running stand-alone entry points.
"""

from __future__ import annotations

import logging
import sys
from typing import TextIO


def configure_logging(
    *,
    component: str = "bot",
    level: str | int = logging.INFO,
    stream: TextIO | None = None,
    log_file: str | None = None,
) -> None:
    """Configure root logger with console + optional file handler.

    Installs the SecurityAuditor logging filter on all handlers so
    that secrets (API keys, tokens, passwords) are redacted at the
    log-emission level.

    Args:
        component: Human-readable component name (for log prefix).
        level: Logging level (default: INFO).
        stream: Output stream (default: stderr).
        log_file: Optional path to a log file (e.g. "logs/bot.log").
    """
    if stream is None:
        stream = sys.stderr

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(
        f"%(asctime)s [{component}] %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(stream)
    console.setFormatter(formatter)
    root.addHandler(console)

    # File handler (optional)
    if log_file:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # Install SecurityAuditor redaction filter on ALL handlers
    from src.risk.security_auditor import SecurityAuditor
    audit_filter = SecurityAuditor.as_logging_filter()
    for handler in root.handlers:
        handler.addFilter(audit_filter)

    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured (component=%s, level=%s, file=%s)",
        component,
        logging.getLevelName(level),
        log_file or "(none)",
    )
