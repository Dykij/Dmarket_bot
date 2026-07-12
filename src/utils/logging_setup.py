"""logging_setup.py — Shared logging configuration for all entry points.

Every bot entry point (__main__.py, control_bot/__main__.py, bot.py)
must call configure_logging() so SecurityAuditor redaction is active
everywhere, not just when launched through __main__.py.

v15.1: Added JSON formatter for structured logging (ELK/Loki compatible).
v15.2: Integrated structlog for structured context binding.

Usage:
    from src.utils.logging_setup import configure_logging
    configure_logging(component="control_bot")
    configure_logging(component="bot", json_format=True)  # JSON logs
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import TextIO


class JSONFormatter(logging.Formatter):
    """v15.1: Structured JSON log formatter for ELK/Loki/Grafana.

    Output format:
        {"ts": "2026-07-12T08:47:00", "level": "INFO", "logger": "SnipingBot",
         "component": "bot", "msg": "Cycle complete", "extra": {...}}
    """

    def __init__(self, component: str = "bot") -> None:
        super().__init__()
        self.component = component

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "component": self.component,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data
        return json.dumps(log_entry, ensure_ascii=False)


def _configure_structlog(json_format: bool = False, component: str = "bot") -> None:
    """v15.2: Configure structlog to integrate with stdlib logging.
    
    This makes structlog.log.get_logger() produce log entries that
    flow through the same handlers/filters (including SecurityAuditor).
    """
    try:
        import structlog

        shared_processors: list[structlog.types.Processor] = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
        ]

        if json_format:
            renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
        else:
            renderer = structlog.dev.ConsoleRenderer(colors=False)

        structlog.configure(
            processors=[
                *shared_processors,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        # Set up the formatter for structlog entries
        formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
            foreign_pre_chain=shared_processors,
        )

        return formatter
    except ImportError:
        return None


def configure_logging(
    *,
    component: str = "bot",
    level: str | int = logging.INFO,
    stream: TextIO | None = None,
    log_file: str | None = None,
    json_format: bool = False,
) -> None:
    """Configure root logger with console + optional file handler.

    Installs the SecurityAuditor logging filter on all handlers so
    that secrets (API keys, tokens, passwords) are redacted at the
    log-emission level.

    v15.2: Integrates structlog for structured context binding.

    Args:
        component: Human-readable component name (for log prefix).
        level: Logging level (default: INFO).
        stream: Output stream (default: stderr).
        log_file: Optional path to a log file (e.g. "logs/bot.log").
        json_format: If True, use JSON formatter (for ELK/Loki).
    """
    if stream is None:
        stream = sys.stderr

    root = logging.getLogger()
    root.setLevel(level)

    # v15.2: Try to configure structlog integration
    structlog_formatter = _configure_structlog(json_format=json_format, component=component)

    if structlog_formatter is not None:
        formatter = structlog_formatter
    elif json_format:
        formatter = JSONFormatter(component=component)
    else:
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
    try:
        from src.risk.security_auditor import SecurityAuditor
        audit_filter = SecurityAuditor.as_logging_filter()
        for handler in root.handlers:
            handler.addFilter(audit_filter)
    except Exception as e:
        logging.getLogger(__name__).warning(
            "SecurityAuditor filter not installed: %s", e
        )

    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured (component=%s, level=%s, file=%s, json=%s, structlog=%s)",
        component,
        logging.getLevelName(level),
        log_file or "(none)",
        json_format,
        structlog_formatter is not None,
    )
