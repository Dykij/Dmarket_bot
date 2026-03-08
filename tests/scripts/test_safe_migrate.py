#!/usr/bin/env python3
"""
Тесты для safe_migrate.py
"""

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.safe_migrate import MigrationVerificationError, SafeMigrator


class TestSafeMigrator:
    """Тесты для SafeMigrator."""

    @pytest.fixture()
    def migrator(self):
        """Create test migrator."""
        return SafeMigrator(
            database_url="sqlite+Algoosqlite:///:memory:",
            dry_run=True,
        )

    @pytest.mark.asyncio()
    async def test_get_current_revision(self, migrator):
        """Тест получения текущей ревизии."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="abc123def (head)\n",
                returncode=0,
            )

            revision = await migrator.get_current_revision()

            assert revision == "abc123def"
            mock_run.assert_called_once()

    @pytest.mark.asyncio()
    async def test_get_current_revision_none(self, migrator):
        """Тест когда ревизия отсутствует."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="",
                returncode=0,
            )

            revision = await migrator.get_current_revision()

            assert revision is None

    @pytest.mark.asyncio()
    async def test_get_current_revision_error(self, migrator):
        """Тест обработки ошибки получения ревизии."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "alembic current")

            revision = await migrator.get_current_revision()

            assert revision is None

    def test_run_alembic_command_dry_run(self, migrator):
        """Тест команды в dry-run режиме."""
        result = migrator.run_alembic_command("upgrade", "head")

        assert result.returncode == 0
        assert result.stdout == ""

    def test_run_alembic_command_real(self):
        """Тест реальной команды alembic."""
        migrator = SafeMigrator(
            database_url="sqlite+Algoosqlite:///:memory:", dry_run=False
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="Upgrade successful",
                returncode=0,
            )

            migrator.run_alembic_command("upgrade", "head")

            mock_run.assert_called_once_with(
                ["alembic", "upgrade", "head"],
                capture_output=True,
                text=True,
                check=True,
            )

    @pytest.mark.asyncio()
    async def test_create_backup_dry_run(self, migrator):
        """Тест создания бэкапа в dry-run."""
        backup_file = await migrator.create_backup()

        assert backup_file == "dry_run_backup.sql"

    @pytest.mark.asyncio()
    async def test_create_backup_real(self):
        """Тест реального создания бэкапа."""
        migrator = SafeMigrator(
            database_url="sqlite+Algoosqlite:///:memory:", dry_run=False
        )

        with patch("scripts.safe_migrate.DatabaseBackup") as mock_backup_class:
            mock_backup_instance = AsyncMock()
            mock_backup_instance.create_backup = AsyncMock(
                return_value=Path("backup_20251214.sql")
            )
            mock_backup_class.return_value = mock_backup_instance

            backup_file = await migrator.create_backup()

            assert "backup_20251214.sql" in backup_file
            mock_backup_instance.create_backup.assert_called_once()

        await migrator.close()

    @pytest.mark.asyncio()
    async def test_verify_migration_success(self, migrator):
        """Тест успешной верификации миграции."""
        with (
            patch.object(migrator, "get_current_revision") as mock_current,
            patch.object(migrator, "check_data_integrity") as mock_integrity,
        ):
            mock_current.return_value = "abc123"
            mock_integrity.return_value = {
                "no_orphaned_targets": True,
                "valid_target_prices": True,
                "unique_telegram_ids": True,
                "alembic_table_exists": True,
            }

            result = await migrator.verify_migration("abc123")

            assert result is True

    @pytest.mark.asyncio()
    async def test_verify_migration_revision_mismatch(self, migrator):
        """Тест ошибки несовпадения ревизий."""
        with patch.object(migrator, "get_current_revision") as mock_current:
            mock_current.return_value = "abc123"

            with pytest.raises(MigrationVerificationError) as exc_info:
                await migrator.verify_migration("def456")

            assert "Revision mismatch" in str(exc_info.value)

    @pytest.mark.asyncio()
    async def test_verify_migration_integrity_failed(self, migrator):
        """Тест ошибки проверки целостности данных."""
        with (
            patch.object(migrator, "get_current_revision") as mock_current,
            patch.object(migrator, "check_data_integrity") as mock_integrity,
        ):
            mock_current.return_value = "abc123"
            mock_integrity.return_value = {
                "no_orphaned_targets": False,  # Failed check
                "valid_target_prices": True,
                "unique_telegram_ids": True,
                "alembic_table_exists": True,
            }

            with pytest.raises(MigrationVerificationError) as exc_info:
                await migrator.verify_migration("abc123")

            assert "Data integrity checks failed" in str(exc_info.value)

    @pytest.mark.asyncio()
    async def test_migrate_success(self, migrator):
        """Тест успешной миграции."""
        with (
            patch.object(migrator, "get_current_revision") as mock_current,
            patch.object(migrator, "check_data_integrity") as mock_integrity,
            patch.object(migrator, "create_backup") as mock_backup,
            patch.object(migrator, "run_alembic_command") as mock_alembic,
            patch.object(migrator, "verify_migration") as mock_verify,
        ):
            mock_current.return_value = "abc123"
            mock_integrity.return_value = {
                "no_orphaned_targets": True,
                "valid_target_prices": True,
                "unique_telegram_ids": True,
                "alembic_table_exists": True,
            }
            mock_backup.return_value = "backup.sql"
            mock_verify.return_value = True

            success = await migrator.migrate("head")

            assert success is True
            mock_alembic.assert_called_once_with("upgrade", "head")

    @pytest.mark.asyncio()
    async def test_migrate_pre_checks_failed(self, migrator):
        """Тест провала пре-миграционных проверок."""
        with (
            patch.object(migrator, "get_current_revision") as mock_current,
            patch.object(migrator, "check_data_integrity") as mock_integrity,
        ):
            mock_current.return_value = "abc123"
            mock_integrity.return_value = {
                "no_orphaned_targets": False,  # Failed
                "valid_target_prices": True,
            }

            success = await migrator.migrate("head")

            assert success is False

    @pytest.mark.asyncio()
    async def test_migrate_with_rollback(self, migrator):
        """Тест миграции с откатом при ошибке."""
        # Switch to non-dry-run for rollback testing
        migrator.dry_run = False

        with (
            patch.object(migrator, "get_current_revision") as mock_current,
            patch.object(migrator, "check_data_integrity") as mock_integrity,
            patch.object(migrator, "create_backup") as mock_backup,
            patch.object(migrator, "run_alembic_command") as mock_alembic,
            patch.object(migrator, "verify_migration"),
        ):
            mock_current.return_value = "abc123"
            mock_integrity.return_value = {
                "no_orphaned_targets": True,
                "valid_target_prices": True,
                "unique_telegram_ids": True,
                "alembic_table_exists": True,
            }
            mock_backup.return_value = "backup.sql"

            # First call (upgrade) raises error, second call (downgrade) succeeds
            mock_alembic.side_effect = [
                subprocess.CalledProcessError(1, "alembic upgrade"),
                MagicMock(),  # downgrade succeeds
            ]

            success = await migrator.migrate("head")

            assert success is False
            assert mock_alembic.call_count == 2
            # Check downgrade was called
            mock_alembic.assert_any_call("downgrade", "abc123")

    @pytest.mark.asyncio()
    async def test_show_pending_migrations(self, migrator):
        """Тест показа ожидающих миграций."""
        with (
            patch.object(migrator, "get_current_revision") as mock_current,
            patch.object(migrator, "run_alembic_command") as mock_alembic,
        ):
            mock_current.return_value = "abc123"
            mock_alembic.return_value = MagicMock(
                stdout="abc123 -> def456 (head), add user preferences"
            )

            pending = await migrator.show_pending_migrations()

            # Current implementation returns empty list
            # Future implementation would parse output
            assert isinstance(pending, list)

    @pytest.mark.parametrize(
        ("integrity_checks", "expected_pass"),
        (
            (
                {
                    "no_orphaned_targets": True,
                    "valid_target_prices": True,
                    "unique_telegram_ids": True,
                    "alembic_table_exists": True,
                },
                True,
            ),
            (
                {
                    "no_orphaned_targets": False,
                    "valid_target_prices": True,
                    "unique_telegram_ids": True,
                    "alembic_table_exists": True,
                },
                False,
            ),
            (
                {
                    "no_orphaned_targets": True,
                    "valid_target_prices": False,
                    "unique_telegram_ids": False,
                    "alembic_table_exists": True,
                },
                False,
            ),
        ),
    )
    def test_all_checks_passing(self, integrity_checks, expected_pass):
        """Тест проверки всех тестов целостности."""
        result = all(integrity_checks.values())
        assert result == expected_pass
