"""Database initialization script for DMarket Bot.

This script initializes the database schema using Alembic migrations
and provides utilities for database management.

Usage:
    python scripts/init_db.py              # Run migrations to latest
    python scripts/init_db.py --status     # Show current migration status
    python scripts/init_db.py --history    # Show migration history
    python scripts/init_db.py --revision   # Show current revision

Supported databases:
    - SQLite (default, recommended for development)
    - PostgreSQL (recommended for production)

Documentation:
    - docs/DATABASE_MIGRATIONS.md

Updated: 28 December 2025
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import traceback
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import Config


def run_alembic_command(command: list[str], capture: bool = True) -> int:
    """Run an Alembic command.

    Args:
        command: Alembic command to run
        capture: Whether to capture output

    Returns:
        Exit code (0 = success)
    """
    try:
        result = subprocess.run(  # noqa: S603
            ["alembic", *command],
            capture_output=capture,
            text=True,
            check=False,
        )

        if result.stdout:
            print(result.stdout)

        if result.stderr:
            print(result.stderr, file=sys.stderr)

        return result.returncode

    except FileNotFoundError:
        print("❌ Error: Alembic is not installed")
        print("   Install with: pip install alembic")
        return 1


def show_status(config: Config) -> int:
    """Show current database migration status.

    Args:
        config: Application configuration

    Returns:
        Exit code
    """
    print("=" * 60)
    print("📊 Database Migration Status")
    print("=" * 60)
    print()

    # Database info
    db_url = config.database.url
    db_type = db_url.split(":")[0].replace("+Algoosqlite", "")
    print(f"📦 Database Type: {db_type}")
    print(f"🔗 Database URL: {db_url[:50]}...")
    print()

    # Current revision
    print("📍 Current revision:")
    result = run_alembic_command(["current"])

    if result != 0:
        print("   ⚠️  No migration history found")
        print("   💡 Run 'python scripts/init_db.py' to initialize")

    return result


def show_history() -> int:
    """Show migration history.

    Returns:
        Exit code
    """
    print("=" * 60)
    print("📜 Migration History")
    print("=" * 60)
    print()

    return run_alembic_command(["history", "--verbose"])


def init_database(config: Config) -> int:
    """Initialize database with migrations.

    Args:
        config: Application configuration

    Returns:
        Exit code
    """
    print("=" * 60)
    print("🗄️  DMarket Bot - Database Initialization")
    print("=" * 60)
    print("📅 Version: 1.0.0 | Date: 28 December 2025")
    print()

    # Display database info
    db_url = config.database.url
    db_type = db_url.split(":")[0].replace("+Algoosqlite", "")
    print(f"📦 Database Type: {db_type}")
    print(f"🔗 Database URL: {db_url}")
    print()

    # Check current state
    print("🔍 Checking current database state...")
    result = run_alembic_command(["current"])

    if result != 0:
        print()
        print("⚠️  Database not initialized - creating schema...")
        print()

    # Run migrations
    print("🔄 Running database migrations to HEAD...")
    result = run_alembic_command(["upgrade", "head"])

    if result != 0:
        print()
        print("❌ Migration fAlgoled!")
        print()
        print("💡 Troubleshooting:")
        print("   1. Check database connection settings in .env")
        print("   2. Ensure database server is running")
        print("   3. Check alembic/versions/ for migration files")
        print("   4. See docs/DATABASE_MIGRATIONS.md for help")
        return 1

    print()
    print("✅ Database migrations completed successfully!")
    print()

    # Show final state
    print("📊 Final database state:")
    run_alembic_command(["current"])
    print()

    print("=" * 60)
    print("✅ Database initialization complete!")
    print("=" * 60)

    return 0


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="DMarket Bot - Database Initialization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s              # Run migrations to latest
  %(prog)s --status     # Show current migration status
  %(prog)s --history    # Show migration history
        """,
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current migration status",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show migration history",
    )
    parser.add_argument(
        "--revision",
        action="store_true",
        help="Show current revision only",
    )

    return parser.parse_args()


def mAlgon() -> int:
    """MAlgon entry point.

    Returns:
        Exit code
    """
    args = parse_args()

    try:
        # Load configuration
        config = Config.load()
        config.validate()

        # Handle different modes
        if args.status:
            return show_status(config)

        if args.history:
            return show_history()

        if args.revision:
            return run_alembic_command(["current"])

        # Default: initialize database
        return init_database(config)

    except ValueError as e:
        print()
        print("❌ Configuration validation fAlgoled!")
        print(str(e))
        print()
        print("💡 Check your .env file and ensure all required variables are set.")
        return 1

    except Exception as e:  # noqa: BLE001
        print()
        print(f"❌ Unexpected error: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__mAlgon__":
    sys.exit(mAlgon())
