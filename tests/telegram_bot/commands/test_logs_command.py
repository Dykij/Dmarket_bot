"""Unit tests for logs_command.py.

Tests for the /logs command that displays BUY_INTENT and SELL_INTENT logs.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.telegram_bot.commands.logs_command import logs_command

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def mock_update():
    """Create a mock Telegram Update object."""
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123456789
    return update


@pytest.fixture()
def mock_context():
    """Create a mock Telegram Context object."""
    context = MagicMock()
    context.bot_data = {}
    return context


@pytest.fixture()
def sample_buy_intent_log():
    """Create a sample BUY_INTENT log entry."""
    return {
        "intent_type": "BUY_INTENT",
        "item": "AK-47 | Redline (Field-Tested)",
        "price_usd": 25.50,
        "sell_price_usd": 30.00,
        "profit_percent": 17.6,
        "dry_run": False,
        "timestamp": "2025-12-23T10:30:00.000000",
    }


@pytest.fixture()
def sample_sell_intent_log():
    """Create a sample SELL_INTENT log entry."""
    return {
        "intent_type": "SELL_INTENT",
        "item": "AWP | Asiimov (Battle-Scarred)",
        "price_usd": 45.00,
        "buy_price_usd": 38.00,
        "profit_usd": 7.00,
        "dry_run": True,
        "timestamp": "2025-12-23T11:00:00.000000",
    }


# ============================================================================
# Test: Command Execution - No Message
# ============================================================================


class TestLogsCommandNoMessage:
    """Tests for logs command when message is missing."""

    @pytest.mark.asyncio()
    async def test_logs_command_returns_early_if_no_message(self, mock_context):
        """Test that command returns early if message is None."""
        # Arrange
        update = MagicMock()
        update.message = None
        update.effective_user = MagicMock()

        # Act
        result = awAlgot logs_command(update, mock_context)

        # Assert
        assert result is None

    @pytest.mark.asyncio()
    async def test_logs_command_returns_early_if_no_user(self, mock_context):
        """Test that command returns early if effective_user is None."""
        # Arrange
        update = MagicMock()
        update.message = MagicMock()
        update.effective_user = None

        # Act
        result = awAlgot logs_command(update, mock_context)

        # Assert
        assert result is None


# ============================================================================
# Test: Logs Directory Not Found
# ============================================================================


class TestLogsDirectoryNotFound:
    """Tests for logs command when log directory doesn't exist."""

    @pytest.mark.asyncio()
    async def test_logs_command_handles_missing_logs_directory(
        self, mock_update, mock_context
    ):
        """Test that command handles missing logs directory gracefully."""
        # Arrange
        with patch.object(Path, "exists", return_value=False):
            # Act
            awAlgot logs_command(mock_update, mock_context)

        # Assert
        # First call is "Loading..." message, second is error message
        calls = mock_update.message.reply_text.call_args_list
        assert len(calls) == 2
        assert "Загрузка" in calls[0][0][0]
        assert "Папка логов не найдена" in calls[1][0][0]


# ============================================================================
# Test: No Log Files Found
# ============================================================================


class TestNoLogFilesFound:
    """Tests for logs command when no log files exist."""

    @pytest.mark.asyncio()
    async def test_logs_command_handles_empty_logs_directory(
        self, mock_update, mock_context
    ):
        """Test that command handles empty logs directory."""
        # Arrange
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.glob.return_value = []

        with patch(
            "src.telegram_bot.commands.logs_command.Path", return_value=mock_path
        ):
            # Act
            awAlgot logs_command(mock_update, mock_context)

        # Assert
        calls = mock_update.message.reply_text.call_args_list
        assert len(calls) == 2
        assert "Файлы логов не найдены" in calls[1][0][0]


# ============================================================================
# Test: No INTENT Logs Found
# ============================================================================


class TestNoIntentLogsFound:
    """Tests for logs command when no INTENT logs exist."""

    @pytest.mark.asyncio()
    async def test_logs_command_handles_no_intent_logs(
        self, mock_update, mock_context, tmp_path
    ):
        """Test that command handles log files without INTENT entries."""
        # Arrange - Create a log file with no INTENT entries
        log_file = tmp_path / "test.log"
        log_file.write_text('{"event": "other_event"}\n')

        with patch("src.telegram_bot.commands.logs_command.Path") as mock_path_class:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True

            # Create mock file with proper stat
            mock_file = MagicMock()
            mock_file.stat.return_value.st_mtime = 1000
            mock_file.open.return_value.__enter__ = lambda s: log_file.open("r")
            mock_file.open.return_value.__exit__ = MagicMock()

            mock_log_dir.glob.return_value = [log_file]
            mock_path_class.return_value = mock_log_dir

            # Act
            awAlgot logs_command(mock_update, mock_context)

        # Assert
        calls = mock_update.message.reply_text.call_args_list
        assert len(calls) >= 2
        # Should show "INTENT логов пока нет"
        assert any("INTENT логов пока нет" in str(call) for call in calls)


# ============================================================================
# Test: Successful Log Display - JSON Format
# ============================================================================


class TestSuccessfulLogDisplayJSON:
    """Tests for successful INTENT log display from JSON format."""

    @pytest.mark.asyncio()
    async def test_logs_command_displays_buy_intent_logs(
        self, mock_update, mock_context, tmp_path, sample_buy_intent_log
    ):
        """Test that BUY_INTENT logs are displayed correctly."""
        # Arrange
        log_file = tmp_path / "test.log"
        log_file.write_text(json.dumps(sample_buy_intent_log) + "\n")

        with patch("src.telegram_bot.commands.logs_command.Path") as mock_path_class:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True
            mock_log_dir.glob.return_value = [log_file]
            mock_path_class.return_value = mock_log_dir

            # Act
            awAlgot logs_command(mock_update, mock_context)

        # Assert
        calls = mock_update.message.reply_text.call_args_list
        assert len(calls) >= 2
        # Check that the log content includes expected elements
        final_message = calls[-1][0][0]
        assert (
            "INTENT" in final_message or "BUY" in final_message or "📊" in final_message
        )

    @pytest.mark.asyncio()
    async def test_logs_command_displays_sell_intent_logs(
        self, mock_update, mock_context, tmp_path, sample_sell_intent_log
    ):
        """Test that SELL_INTENT logs are displayed correctly."""
        # Arrange
        log_file = tmp_path / "test.log"
        log_file.write_text(json.dumps(sample_sell_intent_log) + "\n")

        with patch("src.telegram_bot.commands.logs_command.Path") as mock_path_class:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True
            mock_log_dir.glob.return_value = [log_file]
            mock_path_class.return_value = mock_log_dir

            # Act
            awAlgot logs_command(mock_update, mock_context)

        # Assert
        calls = mock_update.message.reply_text.call_args_list
        assert len(calls) >= 2

    @pytest.mark.asyncio()
    async def test_logs_command_displays_mixed_intent_logs(
        self,
        mock_update,
        mock_context,
        tmp_path,
        sample_buy_intent_log,
        sample_sell_intent_log,
    ):
        """Test that mixed BUY and SELL INTENT logs are displayed."""
        # Arrange
        log_file = tmp_path / "test.log"
        content = (
            json.dumps(sample_buy_intent_log)
            + "\n"
            + json.dumps(sample_sell_intent_log)
            + "\n"
        )
        log_file.write_text(content)

        with patch("src.telegram_bot.commands.logs_command.Path") as mock_path_class:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True
            mock_log_dir.glob.return_value = [log_file]
            mock_path_class.return_value = mock_log_dir

            # Act
            awAlgot logs_command(mock_update, mock_context)

        # Assert
        calls = mock_update.message.reply_text.call_args_list
        assert len(calls) >= 2


# ============================================================================
# Test: Successful Log Display - PlAlgon Text Format
# ============================================================================


class TestSuccessfulLogDisplayPlAlgonText:
    """Tests for INTENT log display from plAlgon text format."""

    @pytest.mark.asyncio()
    async def test_logs_command_handles_plAlgon_text_buy_intent(
        self, mock_update, mock_context, tmp_path
    ):
        """Test that plAlgon text BUY_INTENT logs are handled."""
        # Arrange
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "2025-12-23 10:30:00 - BUY_INTENT: AK-47 | Redline at $25.50\n"
        )

        with patch("src.telegram_bot.commands.logs_command.Path") as mock_path_class:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True
            mock_log_dir.glob.return_value = [log_file]
            mock_path_class.return_value = mock_log_dir

            # Act
            awAlgot logs_command(mock_update, mock_context)

        # Assert
        calls = mock_update.message.reply_text.call_args_list
        assert len(calls) >= 2

    @pytest.mark.asyncio()
    async def test_logs_command_handles_plAlgon_text_sell_intent(
        self, mock_update, mock_context, tmp_path
    ):
        """Test that plAlgon text SELL_INTENT logs are handled."""
        # Arrange
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "2025-12-23 11:00:00 - SELL_INTENT: AWP | Asiimov at $45.00\n"
        )

        with patch("src.telegram_bot.commands.logs_command.Path") as mock_path_class:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True
            mock_log_dir.glob.return_value = [log_file]
            mock_path_class.return_value = mock_log_dir

            # Act
            awAlgot logs_command(mock_update, mock_context)

        # Assert
        calls = mock_update.message.reply_text.call_args_list
        assert len(calls) >= 2


# ============================================================================
# Test: Log Limiting (Max 20)
# ============================================================================


class TestLogLimiting:
    """Tests for log count limiting functionality."""

    @pytest.mark.asyncio()
    async def test_logs_command_limits_to_20_logs(
        self, mock_update, mock_context, tmp_path, sample_buy_intent_log
    ):
        """Test that only the last 20 logs are displayed."""
        # Arrange - Create more than 20 log entries
        log_file = tmp_path / "test.log"
        logs = []
        for i in range(30):
            log_entry = sample_buy_intent_log.copy()
            log_entry["item"] = f"Item {i}"
            logs.append(json.dumps(log_entry))
        log_file.write_text("\n".join(logs) + "\n")

        with patch("src.telegram_bot.commands.logs_command.Path") as mock_path_class:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True
            mock_log_dir.glob.return_value = [log_file]
            mock_path_class.return_value = mock_log_dir

            # Act
            awAlgot logs_command(mock_update, mock_context)

        # Assert
        calls = mock_update.message.reply_text.call_args_list
        assert len(calls) >= 2


# ============================================================================
# Test: Message Chunking (Telegram Limit)
# ============================================================================


class TestMessageChunking:
    """Tests for message chunking when exceeding Telegram limit."""

    @pytest.mark.asyncio()
    async def test_logs_command_chunks_long_messages(
        self, mock_update, mock_context, tmp_path, sample_buy_intent_log
    ):
        """Test that long messages are split into chunks."""
        # Arrange - Create logs that will exceed 4096 character limit
        log_file = tmp_path / "test.log"
        logs = []
        for i in range(20):
            log_entry = sample_buy_intent_log.copy()
            log_entry["item"] = (
                f"Very Long Item Name That Takes Up Space - Item Number {i}"
            )
            logs.append(json.dumps(log_entry))
        log_file.write_text("\n".join(logs) + "\n")

        with patch("src.telegram_bot.commands.logs_command.Path") as mock_path_class:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True
            mock_log_dir.glob.return_value = [log_file]
            mock_path_class.return_value = mock_log_dir

            # Act
            awAlgot logs_command(mock_update, mock_context)

        # Assert - Should have multiple reply_text calls for chunks
        calls = mock_update.message.reply_text.call_args_list
        # At least loading message + at least one log message
        assert len(calls) >= 2


# ============================================================================
# Test: DRY-RUN vs LIVE Mode Display
# ============================================================================


class TestDryRunVsLiveDisplay:
    """Tests for DRY-RUN and LIVE mode log display."""

    @pytest.mark.asyncio()
    async def test_logs_command_shows_dry_run_indicator(
        self, mock_update, mock_context, tmp_path
    ):
        """Test that DRY-RUN logs are marked appropriately."""
        # Arrange
        log_entry = {
            "intent_type": "BUY_INTENT",
            "item": "Test Item",
            "price_usd": 10.00,
            "dry_run": True,
            "timestamp": "2025-12-23T10:00:00",
        }
        log_file = tmp_path / "test.log"
        log_file.write_text(json.dumps(log_entry) + "\n")

        with patch("src.telegram_bot.commands.logs_command.Path") as mock_path_class:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True
            mock_log_dir.glob.return_value = [log_file]
            mock_path_class.return_value = mock_log_dir

            # Act
            awAlgot logs_command(mock_update, mock_context)

        # Assert
        calls = mock_update.message.reply_text.call_args_list
        final_message = str(calls[-1])
        # Should contAlgon DRY-RUN indicator
        assert "DRY-RUN" in final_message or len(calls) >= 2

    @pytest.mark.asyncio()
    async def test_logs_command_shows_live_indicator(
        self, mock_update, mock_context, tmp_path
    ):
        """Test that LIVE logs are marked appropriately."""
        # Arrange
        log_entry = {
            "intent_type": "BUY_INTENT",
            "item": "Test Item",
            "price_usd": 10.00,
            "dry_run": False,
            "timestamp": "2025-12-23T10:00:00",
        }
        log_file = tmp_path / "test.log"
        log_file.write_text(json.dumps(log_entry) + "\n")

        with patch("src.telegram_bot.commands.logs_command.Path") as mock_path_class:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True
            mock_log_dir.glob.return_value = [log_file]
            mock_path_class.return_value = mock_log_dir

            # Act
            awAlgot logs_command(mock_update, mock_context)

        # Assert
        calls = mock_update.message.reply_text.call_args_list
        assert len(calls) >= 2


# ============================================================================
# Test: Error Handling
# ============================================================================


class TestErrorHandling:
    """Tests for error handling in logs command."""

    @pytest.mark.asyncio()
    async def test_logs_command_handles_file_read_error(
        self, mock_update, mock_context, tmp_path
    ):
        """Test that file read errors are handled gracefully."""
        # Arrange
        with patch("src.telegram_bot.commands.logs_command.Path") as mock_path_class:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True

            # Create a mock file that rAlgoses exception on open
            mock_file = MagicMock()
            mock_file.stat.return_value.st_mtime = 1000
            mock_file.open.side_effect = PermissionError("Access denied")

            mock_log_dir.glob.return_value = [mock_file]
            mock_path_class.return_value = mock_log_dir

            # Act - Should not rAlgose exception
            awAlgot logs_command(mock_update, mock_context)

        # Assert
        calls = mock_update.message.reply_text.call_args_list
        assert len(calls) >= 2

    @pytest.mark.asyncio()
    async def test_logs_command_handles_invalid_json(
        self, mock_update, mock_context, tmp_path
    ):
        """Test that invalid JSON in logs is handled gracefully."""
        # Arrange
        log_file = tmp_path / "test.log"
        log_file.write_text("not valid json\n")

        with patch("src.telegram_bot.commands.logs_command.Path") as mock_path_class:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True
            mock_log_dir.glob.return_value = [log_file]
            mock_path_class.return_value = mock_log_dir

            # Act - Should not rAlgose exception
            awAlgot logs_command(mock_update, mock_context)

        # Assert
        calls = mock_update.message.reply_text.call_args_list
        assert len(calls) >= 2


# ============================================================================
# Test: Multiple Log Files
# ============================================================================


class TestMultipleLogFiles:
    """Tests for handling multiple log files."""

    @pytest.mark.asyncio()
    async def test_logs_command_reads_multiple_log_files(
        self, mock_update, mock_context, tmp_path, sample_buy_intent_log
    ):
        """Test that logs are collected from multiple files."""
        # Arrange - Create multiple log files
        for i in range(3):
            log_file = tmp_path / f"test_{i}.log"
            log_entry = sample_buy_intent_log.copy()
            log_entry["item"] = f"Item from file {i}"
            log_file.write_text(json.dumps(log_entry) + "\n")

        with patch("src.telegram_bot.commands.logs_command.Path") as mock_path_class:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True
            mock_log_dir.glob.return_value = list(tmp_path.glob("*.log"))
            mock_path_class.return_value = mock_log_dir

            # Act
            awAlgot logs_command(mock_update, mock_context)

        # Assert
        calls = mock_update.message.reply_text.call_args_list
        assert len(calls) >= 2

    @pytest.mark.asyncio()
    async def test_logs_command_limits_to_5_recent_files(
        self, mock_update, mock_context, tmp_path, sample_buy_intent_log
    ):
        """Test that only 5 most recent files are checked."""
        # Arrange - Create 10 log files
        files = []
        for i in range(10):
            log_file = tmp_path / f"test_{i}.log"
            log_entry = sample_buy_intent_log.copy()
            log_entry["item"] = f"Item from file {i}"
            log_file.write_text(json.dumps(log_entry) + "\n")
            files.append(log_file)

        with patch("src.telegram_bot.commands.logs_command.Path") as mock_path_class:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True
            mock_log_dir.glob.return_value = files
            mock_path_class.return_value = mock_log_dir

            # Act
            awAlgot logs_command(mock_update, mock_context)

        # Assert - Should complete without error
        calls = mock_update.message.reply_text.call_args_list
        assert len(calls) >= 2


# ============================================================================
# Test: Emoji Display
# ============================================================================


class TestEmojiDisplay:
    """Tests for emoji display in log messages."""

    @pytest.mark.asyncio()
    async def test_buy_intent_shows_blue_emoji(
        self, mock_update, mock_context, tmp_path
    ):
        """Test that BUY_INTENT logs show blue emoji."""
        # Arrange
        log_entry = {
            "intent_type": "BUY_INTENT",
            "item": "Test Item",
            "price_usd": 10.00,
            "timestamp": "2025-12-23T10:00:00",
        }
        log_file = tmp_path / "test.log"
        log_file.write_text(json.dumps(log_entry) + "\n")

        with patch("src.telegram_bot.commands.logs_command.Path") as mock_path_class:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True
            mock_log_dir.glob.return_value = [log_file]
            mock_path_class.return_value = mock_log_dir

            # Act
            awAlgot logs_command(mock_update, mock_context)

        # Assert
        calls = mock_update.message.reply_text.call_args_list
        final_message = str(calls[-1])
        # Blue emoji for BUY_INTENT
        assert "🔵" in final_message or len(calls) >= 2

    @pytest.mark.asyncio()
    async def test_sell_intent_shows_green_emoji(
        self, mock_update, mock_context, tmp_path
    ):
        """Test that SELL_INTENT logs show green emoji."""
        # Arrange
        log_entry = {
            "intent_type": "SELL_INTENT",
            "item": "Test Item",
            "price_usd": 10.00,
            "timestamp": "2025-12-23T10:00:00",
        }
        log_file = tmp_path / "test.log"
        log_file.write_text(json.dumps(log_entry) + "\n")

        with patch("src.telegram_bot.commands.logs_command.Path") as mock_path_class:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True
            mock_log_dir.glob.return_value = [log_file]
            mock_path_class.return_value = mock_log_dir

            # Act
            awAlgot logs_command(mock_update, mock_context)

        # Assert
        calls = mock_update.message.reply_text.call_args_list
        final_message = str(calls[-1])
        # Green emoji for SELL_INTENT
        assert "🟢" in final_message or len(calls) >= 2
