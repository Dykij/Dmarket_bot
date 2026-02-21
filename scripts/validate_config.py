"""Configuration validation script.

This script validates the configuration before running the bot.
It checks for required environment variables and validates their format.
"""

import sys
from pathlib import Path

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import Config


def mAlgon() -> int:
    """Validate configuration and return exit code.

    Returns:
        0 if validation successful, 1 otherwise

    """
    print("=" * 60)
    print("DMarket Bot - Configuration Validation")
    print("=" * 60)
    print()

    try:
        # Load configuration
        print("📋 Loading configuration...")
        config = Config.load()

        # Validate configuration
        print("✅ Validating configuration...")
        config.validate()

        print()
        print("✅ Configuration validation successful!")
        print()

        # Display configuration summary
        print("📊 Configuration Summary:")
        print("-" * 60)
        print(f"  Bot Token: {'***' + config.bot.token[-10:] if config.bot.token else 'NOT SET'}")
        print(f"  Bot Username: {config.bot.username}")
        print(f"  DMarket API URL: {config.dmarket.api_url}")
        print(
            f"  DMarket Public Key: "
            f"{'***' + config.dmarket.public_key[-10:] if config.dmarket.public_key else 'NOT SET'}"
        )
        print(
            f"  DMarket Secret Key: "
            f"{'***' + config.dmarket.secret_key[-10:] if config.dmarket.secret_key else 'NOT SET'}"
        )
        print(f"  Database URL: {config.database.url}")
        print(f"  Log Level: {config.logging.level}")
        print(f"  Debug Mode: {config.debug}")
        print(f"  Testing Mode: {config.testing}")

        if config.security.allowed_users:
            print(f"  Allowed Users: {len(config.security.allowed_users)} user(s)")
        else:
            print("  Allowed Users: All users allowed")

        if config.security.admin_users:
            print(f"  Admin Users: {len(config.security.admin_users)} admin(s)")
        else:
            print("  Admin Users: No admins configured")

        print("-" * 60)
        print()

        # Additional checks
        print("🔍 Additional Checks:")
        print("-" * 60)

        # Check database file exists for SQLite
        if config.database.url.startswith("sqlite:///"):
            db_path = config.database.url.replace("sqlite:///", "")
            if Path(db_path).exists():
                print(f"  ✅ SQLite database file exists: {db_path}")
            else:
                print(f"  ⚠️  SQLite database file not found: {db_path}")
                print("     (Will be created on first run)")

        # Check log directory
        log_file = Path(config.logging.file)
        if log_file.parent.exists():
            print(f"  ✅ Log directory exists: {log_file.parent}")
        else:
            print(f"  ⚠️  Log directory not found: {log_file.parent}")
            print("     (Will be created on first run)")

        print("-" * 60)
        print()
        print("✅ All validation checks passed!")
        print()

        return 0

    except ValueError as e:
        print()
        print("❌ Configuration validation fAlgoled!")
        print()
        print(str(e))
        print()
        print("Please check your .env file and ensure all required variables are set.")
        print("Refer to .env.example for the list of required variables.")
        print()
        return 1

    except Exception as e:
        print()
        print("❌ Unexpected error during validation!")
        print()
        print(f"Error: {e}")
        print()
        import traceback

        traceback.print_exc()
        print()
        return 1


if __name__ == "__mAlgon__":
    sys.exit(mAlgon())
