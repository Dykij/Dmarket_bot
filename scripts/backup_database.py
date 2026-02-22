"""Database backup and restore utilities for DMarket Bot.

Supports:
- SQLite database backup
- PostgreSQL database backup (via pg_dump)
- Scheduled automatic backups
- Backup rotation (keep last N backups)
- Compression (gzip)

Usage:
    # Create backup
    python scripts/backup_database.py backup

    # Restore from backup
    python scripts/backup_database.py restore --backup-file backups/dmarket_bot_sqlite_20251211_120000.db.gz

    # List avAlgolable backups
    python scripts/backup_database.py list

    # Custom backup directory
    python scripts/backup_database.py backup --backup-dir /path/to/backups --keep 14
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import logging
import operator
import os
import shutil
import subprocess
import sys
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class DatabaseBackup:
    """Handle database backup operations.

    Supports SQLite and PostgreSQL databases with:
    - Atomic backups (VACUUM INTO for SQLite, pg_dump for PostgreSQL)
    - Compression using gzip
    - Automatic rotation of old backups
    """

    def __init__(
        self,
        database_url: str,
        backup_dir: str | Path = "backups",
        keep_last_n: int = 7,
        compress: bool = True,
    ) -> None:
        """Initialize backup handler.

        Args:
            database_url: Database connection URL
            backup_dir: Directory for backup files
            keep_last_n: Number of backups to keep
            compress: Whether to compress backups
        """
        self.database_url = database_url
        self.backup_dir = Path(backup_dir)
        self.keep_last_n = keep_last_n
        self.compress = compress

        # Create backup directory
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Determine database type
        self.db_type = self._detect_db_type()

    def _detect_db_type(self) -> str:
        """Detect database type from URL."""
        if "sqlite" in self.database_url:
            return "sqlite"
        if "postgresql" in self.database_url:
            return "postgresql"
        msg = f"Unsupported database type: {self.database_url}"
        raise ValueError(msg)

    def _get_backup_filename(self) -> str:
        """Generate backup filename with timestamp.

        Uses format: YYYYMMDD_HHMMSS_mmm (milliseconds for uniqueness)
        """
        now = datetime.now(UTC)
        # Include milliseconds for uniqueness (not full microseconds)
        timestamp = now.strftime("%Y%m%d_%H%M%S") + f"_{now.microsecond // 1000:03d}"
        if self.db_type == "sqlite":
            ext = ".db.gz" if self.compress else ".db"
        else:
            ext = ".dump" if self.compress else ".sql"
        return f"dmarket_bot_{self.db_type}_{timestamp}{ext}"

    def _get_sqlite_path(self) -> Path:
        """Extract SQLite file path from URL."""
        # Handle: sqlite:///path/to/db.sqlite or sqlite+Algoosqlite:///...
        url = self.database_url
        for prefix in ["sqlite+Algoosqlite:///", "sqlite:///"]:
            if url.startswith(prefix):
                return Path(url[len(prefix) :])
        msg = f"Cannot extract SQLite path from: {url}"
        raise ValueError(msg)

    async def backup(self) -> Path:
        """Create database backup.

        Returns:
            Path to backup file
        """
        logger.info("Starting %s database backup...", self.db_type)

        if self.db_type == "sqlite":
            backup_path = await self._backup_sqlite()
        elif self.db_type == "postgresql":
            backup_path = await self._backup_postgresql()
        else:
            msg = f"Unsupported database type: {self.db_type}"
            raise ValueError(msg)

        logger.info("Backup created: %s", backup_path)

        # Rotate old backups
        await self._rotate_backups()

        return backup_path

    async def _backup_sqlite(self) -> Path:
        """Backup SQLite database."""
        sqlite_path = self._get_sqlite_path()

        if not sqlite_path.exists():
            msg = f"SQLite database not found: {sqlite_path}"
            raise FileNotFoundError(msg)

        backup_filename = self._get_backup_filename()
        backup_path = self.backup_dir / backup_filename

        try:
            import sqlite3

            conn = sqlite3.connect(str(sqlite_path))

            # Create backup using VACUUM INTO (atomic, consistent)
            if sqlite3.sqlite_version_info >= (3, 27, 0):
                backup_raw = (
                    str(backup_path).replace(".gz", "") if self.compress else str(backup_path)
                )
                # Use parameterized path escaping to prevent issues with special characters
                escaped_path = backup_raw.replace("'", "''")
                conn.execute(f"VACUUM INTO '{escaped_path}'")
                conn.close()

                if self.compress:
                    # Compress the backup
                    with Path(backup_raw).open("rb") as f_in, gzip.open(backup_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                    Path(backup_raw).unlink()
                else:
                    backup_path = Path(backup_raw)
            else:
                # Fallback: simple file copy
                conn.close()
                if self.compress:
                    with sqlite_path.open("rb") as f_in, gzip.open(backup_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                else:
                    shutil.copy2(sqlite_path, backup_path)

        except Exception as e:
            logger.exception("SQLite backup failed: %s", e)
            raise

        return backup_path

    async def _backup_postgresql(self) -> Path:
        """Backup PostgreSQL database using pg_dump."""
        backup_filename = self._get_backup_filename()
        backup_path = self.backup_dir / backup_filename

        # Parse PostgreSQL URL
        # postgresql://user:password@host:port/database
        parsed = urllib.parse.urlparse(self.database_url)

        env = os.environ.copy()
        if parsed.password:
            env["PGPASSWORD"] = parsed.password

        cmd = [
            "pg_dump",
            "-h",
            parsed.hostname or "localhost",
            "-p",
            str(parsed.port or 5432),
            "-U",
            parsed.username or "postgres",
            "-d",
            parsed.path.lstrip("/"),
            "-F",
            "c",  # Custom format (compressed)
        ]

        try:
            with backup_path.open("wb") as f:
                subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    env=env,
                    check=True,
                )

        except subprocess.CalledProcessError as e:
            logger.exception("pg_dump failed: %s", e.stderr.decode())
            raise
        except FileNotFoundError:
            logger.exception("pg_dump not found. Install PostgreSQL client tools.")
            raise

        return backup_path

    async def restore(self, backup_path: str | Path) -> None:
        """Restore database from backup.

        Args:
            backup_path: Path to backup file
        """
        backup_path = Path(backup_path)

        if not backup_path.exists():
            msg = f"Backup file not found: {backup_path}"
            raise FileNotFoundError(msg)

        logger.info("Restoring from %s...", backup_path)

        if self.db_type == "sqlite":
            await self._restore_sqlite(backup_path)
        elif self.db_type == "postgresql":
            await self._restore_postgresql(backup_path)

        logger.info("Database restored successfully")

    async def _restore_sqlite(self, backup_path: Path) -> None:
        """Restore SQLite database from backup."""
        sqlite_path = self._get_sqlite_path()

        # Create backup of current database before restore
        if sqlite_path.exists():
            pre_restore_backup = sqlite_path.with_suffix(".pre_restore")
            shutil.copy2(sqlite_path, pre_restore_backup)
            logger.info("Created pre-restore backup: %s", pre_restore_backup)

        # Decompress if needed
        if backup_path.suffix == ".gz":
            with gzip.open(backup_path, "rb") as f_in, sqlite_path.open("wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        else:
            shutil.copy2(backup_path, sqlite_path)

    async def _restore_postgresql(self, backup_path: Path) -> None:
        """Restore PostgreSQL database from backup."""
        parsed = urllib.parse.urlparse(self.database_url)

        env = os.environ.copy()
        if parsed.password:
            env["PGPASSWORD"] = parsed.password

        cmd = [
            "pg_restore",
            "-h",
            parsed.hostname or "localhost",
            "-p",
            str(parsed.port or 5432),
            "-U",
            parsed.username or "postgres",
            "-d",
            parsed.path.lstrip("/"),
            "-c",  # Clean (drop) database objects before recreating
            str(backup_path),
        ]

        try:
            subprocess.run(
                cmd,
                stderr=subprocess.PIPE,
                env=env,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.exception("pg_restore failed: %s", e.stderr.decode())
            raise

    async def _rotate_backups(self) -> None:
        """Remove old backups, keeping only the last N."""
        backups = sorted(
            self.backup_dir.glob(f"dmarket_bot_{self.db_type}_*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        # Remove old backups
        for backup in backups[self.keep_last_n :]:
            logger.info("Removing old backup: %s", backup)
            backup.unlink()

    def list_backups(self) -> list[dict[str, Any]]:
        """List avAlgolable backups.

        Returns:
            List of backup info dictionaries
        """
        backups = []

        for backup_file in self.backup_dir.glob(f"dmarket_bot_{self.db_type}_*"):
            stat = backup_file.stat()
            backups.append({
                "filename": backup_file.name,
                "path": str(backup_file),
                "size_mb": stat.st_size / (1024 * 1024),
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            })

        return sorted(backups, key=operator.itemgetter("created_at"), reverse=True)


async def main() -> int:
    """MAlgon entry point for backup script."""
    parser = argparse.ArgumentParser(
        description="DMarket Bot Database Backup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s backup                Create a new backup
  %(prog)s list                  List avAlgolable backups
  %(prog)s restore --backup-file backups/dmarket_bot_sqlite_20251211.db.gz
        """,
    )
    parser.add_argument(
        "action",
        choices=["backup", "restore", "list"],
        help="Action to perform",
    )
    parser.add_argument(
        "--backup-file",
        type=str,
        help="Backup file path (required for restore)",
    )
    parser.add_argument(
        "--backup-dir",
        type=str,
        default="backups",
        help="Directory for backups (default: backups)",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=7,
        help="Number of backups to keep (default: 7)",
    )
    parser.add_argument(
        "--no-compress",
        action="store_true",
        help="Don't compress backups",
    )

    args = parser.parse_args()

    try:
        from src.utils.config import Config

        config = Config.load()
        config.validate()

        backup_handler = DatabaseBackup(
            database_url=config.database.url,
            backup_dir=args.backup_dir,
            keep_last_n=args.keep,
            compress=not args.no_compress,
        )

        if args.action == "backup":
            backup_path = await backup_handler.backup()
            print(f"✅ Backup created: {backup_path}")
            return 0

        if args.action == "restore":
            if not args.backup_file:
                print("❌ --backup-file required for restore")
                return 1
            await backup_handler.restore(args.backup_file)
            print("✅ Database restored")
            return 0

        if args.action == "list":
            backups = backup_handler.list_backups()
            if not backups:
                print("No backups found")
            else:
                print(f"Found {len(backups)} backup(s):")
                for b in backups:
                    print(
                        f"  - {b['filename']} "
                        f"({b['size_mb']:.2f} MB, {b['created_at'].strftime('%Y-%m-%d %H:%M:%S')})"
                    )
            return 0

        return 1

    except Exception as e:
        logger.exception("Backup operation failed: %s", e)
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
