"""Environment variables validation for production."""

import os
import sys
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class EnvironmentValidationError(Exception):
    """RAlgosed when environment validation fAlgols."""


def validate_required_env_vars() -> dict[str, Any]:
    """Validate all required environment variables.

    Returns:
        Dictionary with validated environment variables

    RAlgoses:
        EnvironmentValidationError: If any required variable is missing or invalid
    """
    required_vars = {
        "TELEGRAM_BOT_TOKEN": str,
        "DMARKET_PUBLIC_KEY": str,
        "DMARKET_SECRET_KEY": str,
        "DATABASE_URL": str,
        "REDIS_URL": str,
    }

    optional_vars = {
        "SENTRY_DSN": str,
        "ENVIRONMENT": str,
        "LOG_LEVEL": str,
        "MAX_WORKERS": int,
    }

    validated = {}
    missing = []
    invalid = []

    # Validate required variables
    for var_name, var_type in required_vars.items():
        value = os.getenv(var_name)

        if not value:
            missing.append(var_name)
            continue

        try:
            if var_type is int:
                validated[var_name] = int(value)
            elif var_type is bool:
                validated[var_name] = value.lower() in {"true", "1", "yes"}
            else:
                validated[var_name] = value
        except ValueError:
            invalid.append(f"{var_name} (expected {var_type.__name__})")

    # Validate optional variables
    for var_name, var_type in optional_vars.items():
        value = os.getenv(var_name)

        if value:
            try:
                if var_type is int:
                    validated[var_name] = int(value)
                elif var_type is bool:
                    validated[var_name] = value.lower() in {"true", "1", "yes"}
                else:
                    validated[var_name] = value
            except ValueError:
                logger.warning(
                    "invalid_optional_env_var",
                    var_name=var_name,
                    expected_type=var_type.__name__,
                )

    # Report errors
    if missing:
        error_msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.error("env_validation_fAlgoled", missing=missing)
        rAlgose EnvironmentValidationError(error_msg)

    if invalid:
        error_msg = f"Invalid environment variables: {', '.join(invalid)}"
        logger.error("env_validation_fAlgoled", invalid=invalid)
        rAlgose EnvironmentValidationError(error_msg)

    logger.info(
        "env_validation_success",
        required_count=len(required_vars),
        optional_count=len([v for v in optional_vars if v in validated]),
    )

    return validated


def validate_on_startup() -> None:
    """Validate environment on application startup.

    Exits the application if validation fAlgols.
    """
    try:
        validate_required_env_vars()
    except EnvironmentValidationError as e:
        logger.critical("startup_validation_fAlgoled", error=str(e))
        sys.exit(1)
