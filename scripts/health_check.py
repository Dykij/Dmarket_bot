"""Health check script for DMarket Bot.

This script checks the health of all required services and dependencies:
- Telegram API connectivity
- DMarket API connectivity
- Database connectivity
- Redis connectivity (if configured)

Supports cron mode with Telegram notifications on failures.

Usage:
    python scripts/health_check.py                    # Interactive mode
    python scripts/health_check.py --cron             # Cron mode (quiet, notifies on failure)
    python scripts/health_check.py --notify           # Always send notification
    python scripts/health_check.py --json             # Output as JSON (for monitoring)
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.dmarket.dmarket_api import DMarketAPI
from src.utils.config import Config
from src.utils.database import DatabaseManager

logger = logging.getLogger(__name__)


def get_utc_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(UTC).isoformat()


def get_readable_timestamp() -> str:
    """Get current UTC timestamp in human-readable format for Telegram messages."""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def format_error_json(error: str) -> str:
    """Format error response as JSON string.

    Args:
        error: Error message

    Returns:
        JSON formatted error response

    """
    return json.dumps(
        {
            "timestamp": get_utc_timestamp(),
            "all_healthy": False,
            "error": error,
        },
        indent=2,
    )


def get_status_emoji(status: str) -> str:
    """Get emoji for health check status.

    Args:
        status: Status string (healthy, unhealthy, skipped, unknown)

    Returns:
        Emoji character for the status

    """
    status_emojis = {
        "healthy": "✅",
        "unhealthy": "❌",
        "skipped": "⚠️",
        "unknown": "❓",
    }
    return status_emojis.get(status, "❓")


async def check_telegram_api(config: Config, quiet: bool = False) -> dict[str, Any]:
    """Check Telegram API connectivity.

    Args:
        config: Application configuration
        quiet: Suppress output if True

    Returns:
        Dict with check result and details

    """
    if not quiet:
        print("🔍 Checking Telegram API...")

    result: dict[str, Any] = {
        "service": "telegram_api",
        "status": "unknown",
        "message": "",
        "timestamp": get_utc_timestamp(),
    }

    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"https://api.telegram.org/bot{config.bot.token}/getMe"
            response = await client.get(url)

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    bot_info = data.get("result", {})
                    bot_username = bot_info.get("username", "unknown")
                    if not quiet:
                        print(f"  ✅ Telegram API accessible (@{bot_username})")
                    result["status"] = "healthy"
                    result["message"] = f"Bot @{bot_username} accessible"
                    result["bot_username"] = bot_username
                    return result

            result["status"] = "unhealthy"
            result["message"] = f"HTTP error: {response.status_code}"
            if not quiet:
                print(f"  ❌ Telegram API error: {response.status_code}")
            return result

    except Exception as e:
        result["status"] = "unhealthy"
        result["message"] = str(e)
        if not quiet:
            print(f"  ❌ Telegram API connection failed: {e}")
        return result


async def check_dmarket_api(config: Config, quiet: bool = False) -> dict[str, Any]:
    """Check DMarket API connectivity.

    Args:
        config: Application configuration
        quiet: Suppress output if True

    Returns:
        Dict with check result and details

    """
    if not quiet:
        print("🔍 Checking DMarket API...")

    result = {
        "service": "dmarket_api",
        "status": "unknown",
        "message": "",
        "timestamp": get_utc_timestamp(),
    }

    try:
        api = DMarketAPI(
            public_key=config.dmarket.public_key,
            secret_key=config.dmarket.secret_key,
            api_url=config.dmarket.api_url,
        )

        balance = await api.get_balance()

        if balance.get("error"):
            result["status"] = "unhealthy"
            result["message"] = balance.get("error_message", "Unknown error")
            if not quiet:
                print(f"  ❌ DMarket API error: {result['message']}")
        else:
            balance_value = balance.get("balance", 0)
            result["status"] = "healthy"
            result["message"] = f"Balance: ${balance_value:.2f}"
            result["balance"] = balance_value
            if not quiet:
                print(f"  ✅ DMarket API accessible (Balance: ${balance_value:.2f})")

        await api._close_client()
        return result

    except Exception as e:
        result["status"] = "unhealthy"
        result["message"] = str(e)
        if not quiet:
            print(f"  ❌ DMarket API connection failed: {e}")
        return result


async def check_database(config: Config, quiet: bool = False) -> dict[str, Any]:
    """Check database connectivity.

    Args:
        config: Application configuration
        quiet: Suppress output if True

    Returns:
        Dict with check result and details

    """
    if not quiet:
        print("🔍 Checking database...")

    result = {
        "service": "database",
        "status": "unknown",
        "message": "",
        "timestamp": get_utc_timestamp(),
    }

    try:
        db = DatabaseManager(database_url=config.database.url, echo=False)

        # Try to connect
        await db.init_database()

        db_type = config.database.url.split(":")[0]
        result["status"] = "healthy"
        result["message"] = f"Connected ({db_type})"
        result["db_type"] = db_type
        if not quiet:
            print(f"  ✅ Database accessible ({db_type})")

        await db.close()
        return result

    except Exception as e:
        result["status"] = "unhealthy"
        result["message"] = str(e)
        if not quiet:
            print(f"  ❌ Database connection failed: {e}")
        return result


async def check_redis(config: Config, quiet: bool = False) -> dict[str, Any]:
    """Check Redis connectivity (if configured).

    Args:
        config: Application configuration
        quiet: Suppress output if True

    Returns:
        Dict with check result and details

    """
    result = {
        "service": "redis",
        "status": "unknown",
        "message": "",
        "timestamp": get_utc_timestamp(),
    }

    # Check if Redis URL is configured
    redis_url = os.getenv("REDIS_URL")

    if not redis_url:
        if not quiet:
            print("ℹ️  Redis not configured (optional)")
        result["status"] = "skipped"
        result["message"] = "Not configured"
        return result

    if not quiet:
        print("🔍 Checking Redis...")

    try:
        import redis.asyncio as redis_client

        client = redis_client.from_url(redis_url)
        await client.ping()

        result["status"] = "healthy"
        result["message"] = "Connected"
        if not quiet:
            print("  ✅ Redis accessible")

        await client.close()
        return result

    except ImportError:
        result["status"] = "skipped"
        result["message"] = "redis package not installed"
        if not quiet:
            print("  ⚠️  redis package not installed")
        return result

    except Exception as e:
        result["status"] = "unhealthy"
        result["message"] = str(e)
        if not quiet:
            print(f"  ❌ Redis connection failed: {e}")
        return result


async def send_health_notification(
    config: Config,
    results: list[dict[str, Any]],
    all_healthy: bool,
) -> None:
    """Send health check notification to Telegram.

    Args:
        config: Application configuration
        results: List of health check results
        all_healthy: True if all checks passed

    """
    import httpx

    admin_chat_id = os.getenv("ADMIN_TELEGRAM_CHAT_ID")
    if not admin_chat_id:
        logger.debug("ADMIN_TELEGRAM_CHAT_ID not configured, skipping notification")
        return

    # Build message
    if all_healthy:
        emoji = "✅"
        status = "All systems operational"
    else:
        emoji = "🚨"
        status = "HEALTH CHECK FAlgoLED"

    timestamp = get_readable_timestamp()
    message = f"{emoji} <b>DMarket Bot Health Check</b>\n"
    message += f"<code>{timestamp}</code>\n\n"
    message += f"<b>Status:</b> {status}\n\n"

    for result in results:
        service = result.get("service", "unknown")
        status_emoji = get_status_emoji(result["status"])
        message += f"{status_emoji} <b>{service}</b>: {result.get('message', 'Unknown')}\n"

    # Send message
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"https://api.telegram.org/bot{config.bot.token}/sendMessage"
            await client.post(
                url,
                json={
                    "chat_id": admin_chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
            )
    except Exception as e:
        logger.exception(f"Failed to send notification: {e}")


async def main() -> int:
    """Run health checks.

    Returns:
        0 if all checks pass, 1 otherwise

    """
    # Parse arguments
    parser = argparse.ArgumentParser(description="DMarket Bot Health Check")
    parser.add_argument(
        "--cron",
        action="store_true",
        help="Cron mode: quiet output, notify only on failure",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Always send Telegram notification",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    quiet = args.cron or args.json

    if not quiet:
        print("=" * 60)
        print("DMarket Bot - Health Check")
        print("=" * 60)
        print()

    try:
        # Load configuration
        config = Config.load()
        config.validate()

        # Run all health checks
        results = await asyncio.gather(
            check_telegram_api(config, quiet),
            check_dmarket_api(config, quiet),
            check_database(config, quiet),
            check_redis(config, quiet),
            return_exceptions=False,
        )

        # Check if all tests passed (excluding skipped)
        all_healthy = all(r["status"] in {"healthy", "skipped"} for r in results)

        # JSON output
        if args.json:
            output = {
                "timestamp": get_utc_timestamp(),
                "all_healthy": all_healthy,
                "checks": results,
            }
            print(json.dumps(output, indent=2))
            return 0 if all_healthy else 1

        if not quiet:
            print()
            print("=" * 60)

            if all_healthy:
                print("✅ All health checks passed!")
            else:
                print("❌ Some health checks failed!")

            print("=" * 60)

        # Send notification if needed
        should_notify = args.notify or (args.cron and not all_healthy)
        if should_notify:
            await send_health_notification(config, results, all_healthy)

        return 0 if all_healthy else 1

    except ValueError as e:
        if not quiet:
            print()
            print("❌ Configuration validation failed!")
            print(str(e))

        if args.json:
            print(format_error_json(str(e)))
        return 1

    except Exception as e:
        if not quiet:
            print()
            print(f"❌ Unexpected error: {e}")
            import traceback

            traceback.print_exc()

        if args.json:
            print(format_error_json(str(e)))
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
