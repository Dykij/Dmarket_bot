#!/usr/bin/env python3
"""
Безопасная миграция базы данных с автоматическим rollback.

Использование:
    python scripts/safe_migrate.py
    python scripts/safe_migrate.py --target head
    python scripts/safe_migrate.py --target abc123
    python scripts/safe_migrate.py --dry-run
"""

import argparse
import asyncio
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.backup_database import DatabaseBackup
from src.utils.config import Config

logger = structlog.get_logger(__name__)


class MigrationError(Exception):
    """Base exception for migration errors."""


class MigrationVerificationError(MigrationError):
    """Raised when post-migration verification fails."""


class SafeMigrator:
    """Безопасный мигратор базы данных."""

    def __init__(self, database_url: str | None = None, dry_run: bool = False):
        """
        Initialize migrator.

        Args:
            database_url: Database connection URL
            dry_run: If True, only show what would be done
        """
        config = Config()
        self.database_url = database_url or config.database.url
        self.dry_run = dry_run
        self.engine = create_async_engine(self.database_url, echo=False)
        self.async_session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def get_current_revision(self) -> str | None:
        """
        Get current alembic revision.

        Returns:
            Current revision or None if no migrations applied
        """
        try:
            result = subprocess.run(
                ["alembic", "current"],
                capture_output=True,
                text=True,
                check=True,
            )
            # Parse output like "abc123 (head)"
            output = result.stdout.strip()
            if output:
                return output.split()[0]
            return None
        except subprocess.CalledProcessError as e:
            logger.exception("failed_to_get_current_revision", error=str(e))
            return None

    async def check_data_integrity(self) -> dict[str, bool]:
        """
        Check data integrity before/after migration.

        Returns:
            Dictionary of check results
        """
        checks = {}

        async with self.async_session() as session:
            try:
                # Check 1: No orphaned targets
                result = await session.execute(
                    text("""
                        SELECT COUNT(*)
                        FROM targets
                        WHERE telegram_id NOT IN (SELECT telegram_id FROM users)
                    """)
                )
                checks["no_orphaned_targets"] = result.scalar() == 0

                # Check 2: All prices are positive
                result = await session.execute(text("SELECT COUNT(*) FROM targets WHERE price < 0"))
                checks["valid_target_prices"] = result.scalar() == 0

                # Check 3: Unique telegram_id in users
                result = await session.execute(
                    text("""
                        SELECT telegram_id, COUNT(*) as cnt
                        FROM users
                        GROUP BY telegram_id
                        HAVING COUNT(*) > 1
                    """)
                )
                checks["unique_telegram_ids"] = len(result.all()) == 0

                # Check 4: Alembic version table exists
                result = await session.execute(
                    text("""
                        SELECT COUNT(*)
                        FROM information_schema.tables
                        WHERE table_name = 'alembic_version'
                    """)
                )
                checks["alembic_table_exists"] = result.scalar() > 0

                logger.info("data_integrity_checks", checks=checks)

            except Exception as e:
                logger.exception("integrity_check_failed", error=str(e))
                checks["error"] = str(e)

        return checks

    async def get_table_count(self, table_name: str) -> int:
        """
        Get row count for table.

        Args:
            table_name: Name of the table

        Returns:
            Number of rows
        """
        async with self.async_session() as session:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            return result.scalar()

    def run_alembic_command(self, command: str, *args: str) -> subprocess.CompletedProcess:
        """
        Run alembic command.

        Args:
            command: Alembic command (upgrade, downgrade, etc.)
            *args: Additional arguments

        Returns:
            Completed process

        Raises:
            subprocess.CalledProcessError: If command fails
        """
        cmd = ["alembic", command, *args]
        logger.info("running_alembic_command", command=cmd)

        if self.dry_run:
            logger.info("dry_run_mode", command=cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        return subprocess.run(cmd, capture_output=True, text=True, check=True)

    async def create_backup(self) -> str:
        """
        Create database backup.

        Returns:
            Path to backup file
        """
        logger.info("creating_backup")
        if self.dry_run:
            return "dry_run_backup.sql"

        backup_dir = Path("backups/migrations")
        backup_dir.mkdir(parents=True, exist_ok=True)

        backup_manager = DatabaseBackup(database_url=self.database_url, backup_dir=backup_dir)
        backup_file = await backup_manager.create_backup(keep=5)

        logger.info("backup_created", file=str(backup_file))
        return str(backup_file)

    async def verify_migration(self, target_revision: str) -> bool:
        """
        Verify migration completed successfully.

        Args:
            target_revision: Target revision to verify

        Returns:
            True if verification passed

        Raises:
            MigrationVerificationError: If verification fails
        """
        logger.info("verifying_migration", target=target_revision)

        # Check 1: Current revision matches target
        current = await self.get_current_revision()
        if target_revision not in {current, "head"}:
            raise MigrationVerificationError(
                f"Revision mismatch: expected {target_revision}, got {current}"
            )

        # Check 2: Data integrity
        integrity_checks = await self.check_data_integrity()
        failed_checks = [k for k, v in integrity_checks.items() if not v]

        if failed_checks:
            raise MigrationVerificationError(f"Data integrity checks failed: {failed_checks}")

        logger.info("migration_verified", revision=current)
        return True

    async def migrate(self, target_revision: str = "head") -> bool:
        """
        Perform safe migration with automatic rollback on failure.

        Args:
            target_revision: Target revision (default: 'head')

        Returns:
            True if migration successful, False if rolled back

        Raises:
            MigrationError: If migration fails and rollback also fails
        """
        start_time = datetime.now()

        # Step 1: Get current state
        current_revision = await self.get_current_revision()
        logger.info(
            "starting_migration",
            current=current_revision,
            target=target_revision,
            dry_run=self.dry_run,
        )

        # Step 2: Pre-migration checks
        logger.info("running_pre_migration_checks")
        integrity_before = await self.check_data_integrity()

        if not all(integrity_before.values()):
            logger.error("pre_migration_checks_failed", checks=integrity_before)
            return False

        # Step 3: Create backup
        backup_file = await self.create_backup()

        try:
            # Step 4: Run migration
            logger.info("applying_migration", target=target_revision)
            self.run_alembic_command("upgrade", target_revision)

            # Step 5: Post-migration verification
            logger.info("running_post_migration_verification")
            await self.verify_migration(target_revision)

            # Step 6: Final integrity check
            integrity_after = await self.check_data_integrity()
            if not all(integrity_after.values()):
                raise MigrationVerificationError(
                    f"Post-migration integrity check failed: {integrity_after}"
                )

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                "migration_successful",
                target=target_revision,
                duration_seconds=duration,
                backup=backup_file,
            )

            return True

        except Exception as e:
            logger.exception(
                "migration_failed",
                error=str(e),
                error_type=type(e).__name__,
            )

            # Step 7: Automatic rollback
            if current_revision and not self.dry_run:
                logger.warning("attempting_rollback", target=current_revision)

                try:
                    self.run_alembic_command("downgrade", current_revision)
                    logger.info("rollback_command_completed")

                    # Verify rollback
                    rollback_integrity = await self.check_data_integrity()
                    if all(rollback_integrity.values()):
                        logger.info("rollback_successful")
                    else:
                        logger.critical(
                            "rollback_verification_failed",
                            checks=rollback_integrity,
                            backup=backup_file,
                        )
                        raise MigrationError(
                            f"Rollback verification failed. Manual intervention required. Backup: {backup_file}"
                        )

                except Exception as rollback_error:
                    logger.critical(
                        "rollback_failed",
                        error=str(rollback_error),
                        backup=backup_file,
                    )
                    raise MigrationError(
                        f"Migration failed AND rollback failed. Manual intervention required. Backup: {backup_file}"
                    ) from rollback_error

            return False

    async def show_pending_migrations(self) -> list[str]:
        """
        Show pending migrations.

        Returns:
            List of pending migration revisions
        """
        try:
            result = self.run_alembic_command("history", "--verbose")
            output = result.stdout

            current = await self.get_current_revision()
            logger.info("current_revision", revision=current)
            logger.info("migration_history", output=output)

            # Parse pending migrations
            # This is simplified - actual implementation would parse alembic output
            return []

        except subprocess.CalledProcessError as e:
            logger.exception("failed_to_get_migrations", error=str(e))
            return []

    async def close(self):
        """Close database connections."""
        await self.engine.dispose()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Safe database migration with automatic rollback")
    parser.add_argument(
        "--target",
        default="head",
        help="Target revision (default: head)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it",
    )
    parser.add_argument(
        "--database-url",
        help="Database URL (default: from config)",
    )

    args = parser.parse_args()

    migrator = SafeMigrator(
        database_url=args.database_url,
        dry_run=args.dry_run,
    )

    try:
        # Show pending migrations
        await migrator.show_pending_migrations()

        # Confirm migration
        if not args.dry_run:
            confirm = input(f"\nApply migration to '{args.target}'? (yes/no): ").lower()
            if confirm != "yes":
                logger.info("migration_cancelled_by_user")
                return

        # Run migration
        success = await migrator.migrate(target_revision=args.target)

        if success:
            logger.info("✅ Migration completed successfully")
            sys.exit(0)
        else:
            logger.error("❌ Migration failed and was rolled back")
            sys.exit(1)

    except MigrationError as e:
        logger.critical("critical_migration_error", error=str(e))
        sys.exit(2)

    finally:
        await migrator.close()


if __name__ == "__main__":
    asyncio.run(main())
