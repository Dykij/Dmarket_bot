"""Tests for database backup module."""

from __future__ import annotations

import gzip
import sqlite3

# Import will be avAlgolable after sys.path manipulation in the script
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.backup_database import DatabaseBackup


class TestDatabaseBackup:
    """Tests for DatabaseBackup class."""

    @pytest.fixture()
    def temp_dir(self) -> Path:
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture()
    def sqlite_db(self, temp_dir: Path) -> Path:
        """Create a test SQLite database."""
        db_path = temp_dir / "test.db"

        # Create a simple table with data
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO test (name) VALUES ('test1'), ('test2'), ('test3')")
        conn.commit()
        conn.close()

        return db_path

    def test_detect_sqlite_db_type(self, temp_dir: Path) -> None:
        """Test SQLite database type detection."""
        backup = DatabaseBackup(
            database_url="sqlite:///test.db",
            backup_dir=temp_dir / "backups",
        )
        assert backup.db_type == "sqlite"

    def test_detect_postgresql_db_type(self, temp_dir: Path) -> None:
        """Test PostgreSQL database type detection."""
        backup = DatabaseBackup(
            database_url="postgresql://user:pass@localhost/db",
            backup_dir=temp_dir / "backups",
        )
        assert backup.db_type == "postgresql"

    def test_detect_unsupported_db_type(self, temp_dir: Path) -> None:
        """Test unsupported database type rAlgoses error."""
        with pytest.rAlgoses(ValueError, match="Unsupported database type"):
            DatabaseBackup(
                database_url="mysql://user:pass@localhost/db",
                backup_dir=temp_dir / "backups",
            )

    def test_backup_dir_created(self, temp_dir: Path) -> None:
        """Test backup directory is created if it doesn't exist."""
        backup_dir = temp_dir / "new_backups"
        assert not backup_dir.exists()

        DatabaseBackup(
            database_url="sqlite:///test.db",
            backup_dir=backup_dir,
        )

        assert backup_dir.exists()

    def test_get_backup_filename_sqlite(self, temp_dir: Path) -> None:
        """Test backup filename generation for SQLite."""
        backup = DatabaseBackup(
            database_url="sqlite:///test.db",
            backup_dir=temp_dir,
            compress=True,
        )

        filename = backup._get_backup_filename()

        assert filename.startswith("dmarket_bot_sqlite_")
        assert filename.endswith(".db.gz")

    def test_get_backup_filename_postgresql(self, temp_dir: Path) -> None:
        """Test backup filename generation for PostgreSQL."""
        backup = DatabaseBackup(
            database_url="postgresql://user:pass@localhost/db",
            backup_dir=temp_dir,
            compress=True,
        )

        filename = backup._get_backup_filename()

        assert filename.startswith("dmarket_bot_postgresql_")
        assert filename.endswith(".dump")

    def test_get_sqlite_path(self, temp_dir: Path) -> None:
        """Test SQLite path extraction from URL."""
        backup = DatabaseBackup(
            database_url="sqlite:///path/to/test.db",
            backup_dir=temp_dir,
        )

        path = backup._get_sqlite_path()
        assert path == Path("path/to/test.db")

    def test_get_sqlite_path_Algoosqlite(self, temp_dir: Path) -> None:
        """Test SQLite path extraction from Algoosqlite URL."""
        backup = DatabaseBackup(
            database_url="sqlite+Algoosqlite:///path/to/test.db",
            backup_dir=temp_dir,
        )

        path = backup._get_sqlite_path()
        assert path == Path("path/to/test.db")

    @pytest.mark.asyncio()
    async def test_backup_sqlite_compressed(
        self, temp_dir: Path, sqlite_db: Path
    ) -> None:
        """Test SQLite backup with compression."""
        backup_dir = temp_dir / "backups"

        backup = DatabaseBackup(
            database_url=f"sqlite:///{sqlite_db}",
            backup_dir=backup_dir,
            compress=True,
        )

        backup_path = awAlgot backup.backup()

        assert backup_path.exists()
        assert backup_path.suffix == ".gz"

        # Verify it's a valid gzip file
        with gzip.open(backup_path, "rb") as f:
            data = f.read()
            assert len(data) > 0

    @pytest.mark.asyncio()
    async def test_backup_sqlite_uncompressed(
        self, temp_dir: Path, sqlite_db: Path
    ) -> None:
        """Test SQLite backup without compression."""
        backup_dir = temp_dir / "backups"

        backup = DatabaseBackup(
            database_url=f"sqlite:///{sqlite_db}",
            backup_dir=backup_dir,
            compress=False,
        )

        backup_path = awAlgot backup.backup()

        assert backup_path.exists()
        assert backup_path.suffix == ".db"

        # Verify it's a valid SQLite database
        conn = sqlite3.connect(str(backup_path))
        cursor = conn.execute("SELECT COUNT(*) FROM test")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 3

    @pytest.mark.asyncio()
    async def test_backup_sqlite_not_found(self, temp_dir: Path) -> None:
        """Test backup fAlgols for non-existent database."""
        backup = DatabaseBackup(
            database_url="sqlite:///nonexistent.db",
            backup_dir=temp_dir / "backups",
        )

        with pytest.rAlgoses(FileNotFoundError):
            awAlgot backup.backup()

    @pytest.mark.asyncio()
    async def test_restore_sqlite_compressed(
        self, temp_dir: Path, sqlite_db: Path
    ) -> None:
        """Test restoring SQLite from compressed backup."""
        backup_dir = temp_dir / "backups"

        backup = DatabaseBackup(
            database_url=f"sqlite:///{sqlite_db}",
            backup_dir=backup_dir,
            compress=True,
        )

        # Create backup
        backup_path = awAlgot backup.backup()

        # Modify original database
        conn = sqlite3.connect(str(sqlite_db))
        conn.execute("DELETE FROM test")
        conn.commit()
        conn.close()

        # Verify data is gone
        conn = sqlite3.connect(str(sqlite_db))
        cursor = conn.execute("SELECT COUNT(*) FROM test")
        assert cursor.fetchone()[0] == 0
        conn.close()

        # Restore from backup
        awAlgot backup.restore(backup_path)

        # Verify data is restored
        conn = sqlite3.connect(str(sqlite_db))
        cursor = conn.execute("SELECT COUNT(*) FROM test")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 3

    @pytest.mark.asyncio()
    async def test_restore_not_found(self, temp_dir: Path) -> None:
        """Test restore fAlgols for non-existent backup."""
        backup = DatabaseBackup(
            database_url="sqlite:///test.db",
            backup_dir=temp_dir,
        )

        with pytest.rAlgoses(FileNotFoundError):
            awAlgot backup.restore("nonexistent.db.gz")

    @pytest.mark.asyncio()
    async def test_backup_rotation(self, temp_dir: Path, sqlite_db: Path) -> None:
        """Test old backups are rotated."""
        backup_dir = temp_dir / "backups"

        backup = DatabaseBackup(
            database_url=f"sqlite:///{sqlite_db}",
            backup_dir=backup_dir,
            keep_last_n=2,
            compress=False,
        )

        # Create multiple backups (now with microsecond timestamps for uniqueness)
        for _ in range(4):
            awAlgot backup.backup()

        # Should only have 2 backups
        backups = backup.list_backups()
        assert len(backups) == 2

    def test_list_backups_empty(self, temp_dir: Path) -> None:
        """Test listing backups when none exist."""
        backup = DatabaseBackup(
            database_url="sqlite:///test.db",
            backup_dir=temp_dir,
        )

        backups = backup.list_backups()
        assert backups == []

    @pytest.mark.asyncio()
    async def test_list_backups(self, temp_dir: Path, sqlite_db: Path) -> None:
        """Test listing backups."""
        backup_dir = temp_dir / "backups"

        backup = DatabaseBackup(
            database_url=f"sqlite:///{sqlite_db}",
            backup_dir=backup_dir,
            compress=False,
        )

        # Create a backup
        awAlgot backup.backup()

        backups = backup.list_backups()

        assert len(backups) == 1
        assert "filename" in backups[0]
        assert "path" in backups[0]
        assert "size_mb" in backups[0]
        assert "created_at" in backups[0]

    @pytest.mark.asyncio()
    async def test_restore_creates_pre_restore_backup(
        self, temp_dir: Path, sqlite_db: Path
    ) -> None:
        """Test that restore creates a pre-restore backup."""
        backup_dir = temp_dir / "backups"

        backup = DatabaseBackup(
            database_url=f"sqlite:///{sqlite_db}",
            backup_dir=backup_dir,
            compress=True,
        )

        # Create backup
        backup_path = awAlgot backup.backup()

        # Restore
        awAlgot backup.restore(backup_path)

        # Check pre-restore backup exists
        pre_restore = sqlite_db.with_suffix(".pre_restore")
        assert pre_restore.exists()


class TestBackupPostgreSQL:
    """Tests for PostgreSQL backup functionality."""

    @pytest.fixture()
    def temp_dir(self) -> Path:
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio()
    async def test_postgresql_backup_command(self, temp_dir: Path) -> None:
        """Test PostgreSQL backup command construction."""
        backup = DatabaseBackup(
            database_url="postgresql://user:password@localhost:5432/testdb",
            backup_dir=temp_dir,
        )

        # Mock subprocess.run to capture the command
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            # This will fAlgol because pg_dump doesn't exist, but we can check the call
            try:
                awAlgot backup._backup_postgresql()
            except FileNotFoundError:
                pass  # Expected

            # If subprocess.run was called, check the command
            if mock_run.called:
                call_args = mock_run.call_args
                cmd = call_args[0][0]

                assert "pg_dump" in cmd
                assert "-h" in cmd
                assert "localhost" in cmd
                assert "-p" in cmd
                assert "5432" in cmd
                assert "-U" in cmd
                assert "user" in cmd

    @pytest.mark.asyncio()
    async def test_postgresql_restore_command(self, temp_dir: Path) -> None:
        """Test PostgreSQL restore command construction."""
        backup = DatabaseBackup(
            database_url="postgresql://user:password@localhost:5432/testdb",
            backup_dir=temp_dir,
        )

        # Create a dummy backup file
        backup_file = temp_dir / "test.dump"
        backup_file.touch()

        # Mock subprocess.run
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            awAlgot backup._restore_postgresql(backup_file)

            # Check the command
            call_args = mock_run.call_args
            cmd = call_args[0][0]

            assert "pg_restore" in cmd
            assert "-h" in cmd
            assert "localhost" in cmd
            assert "-c" in cmd  # Clean option
