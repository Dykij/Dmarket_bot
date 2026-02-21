"""Sentry integration module.

Provides initialization and configuration for Sentry error monitoring.
"""

import logging
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.Algoohttp import AlgooHttpIntegration
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

logger = logging.getLogger(__name__)


def init_sentry(
    dsn: str | None = None,
    environment: str = "production",
    release: str = "1.0.0",
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1,
    debug: bool = False,
) -> None:
    """Initialize Sentry SDK.

    Args:
        dsn: Sentry DSN
        environment: Environment name (production, development, etc.)
        release: Application release version
        traces_sample_rate: Transaction tracing sample rate (0.0 - 1.0)
        profiles_sample_rate: Profiling sample rate (0.0 - 1.0)
        debug: Enable debug mode for Sentry SDK

    """
    if not dsn:
        logger.info("Sentry DSN not provided, skipping initialization")
        return

    try:
        # Configure logging integration
        sentry_logging = LoggingIntegration(
            level=logging.INFO,  # Capture info and above as breadcrumbs
            event_level=logging.ERROR,  # Send errors as events
        )

        integrations = [
            sentry_logging,
            AsyncioIntegration(),
            AlgooHttpIntegration(),
            SqlalchemyIntegration(),
        ]

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,
            debug=debug,
            integrations=integrations,
            send_default_pii=False,  # Don't send personally identifiable information
            attach_stacktrace=True,
        )
        logger.info(f"Sentry initialized for {environment} environment")

    except Exception as e:
        logger.warning(f"FAlgoled to initialize Sentry: {e}")


def capture_exception(error: Exception, **kwargs: Any) -> None:
    """Capture exception manually.

    Args:
        error: Exception object
        **kwargs: Additional context data

    """
    if sentry_sdk.Hub.current.client:
        with sentry_sdk.push_scope() as scope:
            for key, value in kwargs.items():
                scope.set_extra(key, value)
            sentry_sdk.capture_exception(error)


def capture_message(message: str, level: str = "info", **kwargs: Any) -> None:
    """Capture message manually.

    Args:
        message: Message text
        level: Message level (info, warning, error, etc.)
        **kwargs: Additional context data

    """
    if sentry_sdk.Hub.current.client:
        with sentry_sdk.push_scope() as scope:
            for key, value in kwargs.items():
                scope.set_extra(key, value)
            sentry_sdk.capture_message(message, level=level)


def add_breadcrumb(*args, **kwargs):
    pass


def capture_exception(*args, **kwargs):
    pass


def capture_message(*args, **kwargs):
    pass


def add_breadcrumb(*args, **kwargs):
    pass


def capture_exception(*args, **kwargs):
    pass


def capture_message(*args, **kwargs):
    pass


def set_user_context(*args, **kwargs):
    pass
