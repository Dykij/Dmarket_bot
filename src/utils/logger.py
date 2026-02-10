"""Logging configuration with Google Cloud support."""

import logging
import os
import sys
from typing import Any

import structlog

# Try to import Google Cloud Logging
try:
    import google.cloud.logging
    from google.cloud.logging.handlers import CloudLoggingHandler
    HAS_GOOGLE_CLOUD = True
except ImportError:
    HAS_GOOGLE_CLOUD = False


def setup_logger(name: str = "dmarket_bot", level: str = "INFO") -> Any:
    """Configure structured logging with Cloud integration."""
    
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # JSON renderer for production/cloud
    if os.getenv("ENVIRONMENT", "dev") == "production" or HAS_GOOGLE_CLOUD:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        cache_logger_on_first_use=True,
    )

    logger = structlog.get_logger(name)

    # Setup Google Cloud Logging if available and not in dev
    if HAS_GOOGLE_CLOUD and os.getenv("ENVIRONMENT") != "dev_local":
        try:
            client = google.cloud.logging.Client()
            handler = CloudLoggingHandler(client, name=name)
            
            # Add handler to root logger for standard library compatibility
            root_logger = logging.getLogger()
            root_logger.setLevel(level)
            root_logger.addHandler(handler)
            
            # Specific label for trade opportunities
            def log_opportunity(event_dict):
                if event_dict.get("event") == "trade_opportunity":
                    # Add specific label/tag for metrics
                    event_dict["labels"] = {"type": "trade_opportunity"}
                return event_dict
                
            # Note: Structlog integration with standard logging handler is implicit 
            # if we use standard library logger factory, but here we use PrintFactory.
            # Ideally for Cloud Logging we want stdlib integration.
            
        except Exception as e:
            print(f"Failed to setup Cloud Logging: {e}")

    return logger


# Global logger instance
logger = setup_logger()
