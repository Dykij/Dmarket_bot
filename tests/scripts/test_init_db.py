#!/usr/bin/env python3
"""Tests for init_db.py script.

Version: 1.0.0
Updated: 28 December 2025
"""

from unittest.mock import MagicMock, patch

from scripts.init_db import (
    init_database,
    parse_args,
    run_alembic_command,
    show_history,
    show_status,
)


class TestRunAlembicCommand:
    """Tests for run_alembic_command function."""

    def test_run_alembic_command_success(self) -> None:
        """Test successful alembic command execution."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="Success output",
                stderr="",
                returncode=0,
            )

            result = run_alembic_command(["current"])

            assert result == 0
            mock_run.assert_called_once()

    def test_run_alembic_command_failure(self) -> None:
        """Test alembic command failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="",
                stderr="Error message",
                returncode=1,
            )

            result = run_alembic_command(["upgrade", "head"])

            assert result == 1

    def test_run_alembic_command_not_found(self) -> None:
        """Test alembic not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("alembic not found")

            result = run_alembic_command(["current"])

            assert result == 1


class TestShowStatus:
    """Tests for show_status function."""

    def test_show_status_success(self) -> None:
        """Test successful status display."""
        mock_config = MagicMock()
        mock_config.database.url = "sqlite:///test.db"

        with patch("scripts.init_db.run_alembic_command") as mock_alembic:
            mock_alembic.return_value = 0

            result = show_status(mock_config)

            assert result == 0
            mock_alembic.assert_called_once_with(["current"])

    def test_show_status_no_history(self) -> None:
        """Test status when no migration history exists."""
        mock_config = MagicMock()
        mock_config.database.url = "postgresql://localhost/test"

        with patch("scripts.init_db.run_alembic_command") as mock_alembic:
            mock_alembic.return_value = 1

            result = show_status(mock_config)

            assert result == 1


class TestShowHistory:
    """Tests for show_history function."""

    def test_show_history_success(self) -> None:
        """Test successful history display."""
        with patch("scripts.init_db.run_alembic_command") as mock_alembic:
            mock_alembic.return_value = 0

            result = show_history()

            assert result == 0
            mock_alembic.assert_called_once_with(["history", "--verbose"])


class TestInitDatabase:
    """Tests for init_database function."""

    def test_init_database_success(self) -> None:
        """Test successful database initialization."""
        mock_config = MagicMock()
        mock_config.database.url = "sqlite:///test.db"

        with patch("scripts.init_db.run_alembic_command") as mock_alembic:
            # First call: current (returns 1 = no history)
            # Second call: upgrade head (returns 0 = success)
            # Third call: current (returns 0 = show final state)
            mock_alembic.side_effect = [1, 0, 0]

            result = init_database(mock_config)

            assert result == 0
            assert mock_alembic.call_count == 3

    def test_init_database_migration_failure(self) -> None:
        """Test database initialization with migration failure."""
        mock_config = MagicMock()
        mock_config.database.url = "sqlite:///test.db"

        with patch("scripts.init_db.run_alembic_command") as mock_alembic:
            # First call: current (returns 0)
            # Second call: upgrade head (returns 1 = failure)
            mock_alembic.side_effect = [0, 1]

            result = init_database(mock_config)

            assert result == 1

    def test_init_database_postgresql(self) -> None:
        """Test database initialization with PostgreSQL."""
        mock_config = MagicMock()
        mock_config.database.url = "postgresql://user:pass@localhost:5432/testdb"

        with patch("scripts.init_db.run_alembic_command") as mock_alembic:
            mock_alembic.side_effect = [0, 0, 0]

            result = init_database(mock_config)

            assert result == 0


class TestParseArgs:
    """Tests for parse_args function."""

    def test_parse_args_default(self) -> None:
        """Test default arguments."""
        with patch("sys.argv", ["init_db.py"]):
            args = parse_args()

            assert args.status is False
            assert args.history is False
            assert args.revision is False

    def test_parse_args_status(self) -> None:
        """Test --status argument."""
        with patch("sys.argv", ["init_db.py", "--status"]):
            args = parse_args()

            assert args.status is True

    def test_parse_args_history(self) -> None:
        """Test --history argument."""
        with patch("sys.argv", ["init_db.py", "--history"]):
            args = parse_args()

            assert args.history is True

    def test_parse_args_revision(self) -> None:
        """Test --revision argument."""
        with patch("sys.argv", ["init_db.py", "--revision"]):
            args = parse_args()

            assert args.revision is True
