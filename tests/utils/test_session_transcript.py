"""Tests for Session Transcript Generator.

Based on SkillsMP recommendations for testing VS Code Insiders features.
"""

import pytest

from src.utils.session_transcript import (
    ActionType,
    SessionAction,
    SessionMetrics,
    SessionTranscript,
    SessionTranscriptGenerator,
    get_transcript_generator,
)


class TestActionType:
    """Tests for ActionType enum."""

    def test_action_types_exist(self):
        """Test that all action types are defined."""
        assert ActionType.FILE_CREATE.value == "file_create"
        assert ActionType.FILE_EDIT.value == "file_edit"
        assert ActionType.COMMAND_RUN.value == "command_run"
        assert ActionType.TEST_RUN.value == "test_run"
        assert ActionType.ERROR.value == "error"


class TestSessionAction:
    """Tests for SessionAction dataclass."""

    def test_action_creation(self):
        """Test creating an action."""
        # Act
        action = SessionAction(
            action_type=ActionType.FILE_CREATE,
            description="Create new module",
            files_affected=["src/new_module.py"],
        )

        # Assert
        assert action.action_type == ActionType.FILE_CREATE
        assert action.description == "Create new module"
        assert action.files_affected == ["src/new_module.py"]
        assert action.success is True

    def test_action_to_dict(self):
        """Test converting action to dictionary."""
        # Arrange
        action = SessionAction(
            action_type=ActionType.FILE_EDIT,
            description="Edit config",
            duration_ms=150.5,
        )

        # Act
        result = action.to_dict()

        # Assert
        assert result["action_type"] == "file_edit"
        assert result["description"] == "Edit config"
        assert result["duration_ms"] == 150.5
        assert result["success"] is True

    def test_action_with_error(self):
        """Test action with error."""
        # Act
        action = SessionAction(
            action_type=ActionType.ERROR,
            description="Build fAlgoled",
            success=False,
            error_message="Compilation error on line 42",
        )

        # Assert
        assert action.success is False
        assert action.error_message == "Compilation error on line 42"


class TestSessionMetrics:
    """Tests for SessionMetrics dataclass."""

    def test_default_metrics(self):
        """Test default metric values."""
        # Act
        metrics = SessionMetrics()

        # Assert
        assert metrics.total_actions == 0
        assert metrics.files_created == 0
        assert metrics.tests_passed == 0
        assert metrics.errors_encountered == 0

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        # Arrange
        metrics = SessionMetrics(
            total_actions=10,
            errors_encountered=2,
        )

        # Act
        result = metrics.to_dict()

        # Assert
        assert result["success_rate"] == 80.0

    def test_success_rate_zero_actions(self):
        """Test success rate with no actions."""
        # Arrange
        metrics = SessionMetrics()

        # Act
        result = metrics.to_dict()

        # Assert
        assert result["success_rate"] == 100.0


class TestSessionTranscript:
    """Tests for SessionTranscript dataclass."""

    def test_transcript_creation(self):
        """Test creating a transcript."""
        # Act
        transcript = SessionTranscript(
            session_id="test-session-123",
            title="Test Session",
            description="Testing the transcript",
        )

        # Assert
        assert transcript.session_id == "test-session-123"
        assert transcript.title == "Test Session"
        assert transcript.actions == []
        assert transcript.Algo_model == "github-copilot"

    def test_transcript_to_dict(self):
        """Test converting transcript to dictionary."""
        # Arrange
        transcript = SessionTranscript(
            session_id="test-session",
            title="Test",
            tags=["test", "example"],
        )

        # Act
        result = transcript.to_dict()

        # Assert
        assert result["session_id"] == "test-session"
        assert result["tags"] == ["test", "example"]
        assert "metrics" in result
        assert "actions" in result

    def test_transcript_to_markdown(self):
        """Test generating markdown transcript."""
        # Arrange
        transcript = SessionTranscript(
            session_id="test-session",
            title="Test Session",
            description="A test session",
        )
        transcript.actions.append(
            SessionAction(
                action_type=ActionType.FILE_CREATE,
                description="Create file",
                files_affected=["test.py"],
            )
        )
        transcript.metrics.total_actions = 1
        transcript.metrics.files_created = 1

        # Act
        markdown = transcript.to_markdown()

        # Assert
        assert "# Session Transcript: Test Session" in markdown
        assert "test-session" in markdown
        assert "FILE_CREATE" in markdown.upper() or "file_create" in markdown


class TestSessionTranscriptGenerator:
    """Tests for SessionTranscriptGenerator class."""

    @pytest.fixture
    def generator(self, tmp_path):
        """Create transcript generator with temp directory."""
        return SessionTranscriptGenerator(output_dir=tmp_path / "transcripts")

    def test_start_session(self, generator):
        """Test starting a session."""
        # Act
        session = generator.start_session(
            title="Test Session",
            description="Testing",
            tags=["test"],
        )

        # Assert
        assert session is not None
        assert session.title == "Test Session"
        assert "test" in session.tags
        assert generator.has_active_session()

    def test_record_action(self, generator):
        """Test recording an action."""
        # Arrange
        generator.start_session("Test")

        # Act
        action = generator.record_action(
            ActionType.FILE_CREATE,
            "Create module",
            files_affected=["src/module.py"],
        )

        # Assert
        assert action is not None
        assert action.action_type == ActionType.FILE_CREATE
        session = generator.get_current_session()
        assert len(session.actions) == 1

    def test_record_action_no_session(self, generator):
        """Test recording action without active session."""
        # Act
        action = generator.record_action(
            ActionType.FILE_CREATE,
            "Create module",
        )

        # Assert
        assert action is None

    def test_metrics_update_file_create(self, generator):
        """Test metrics update for file creation."""
        # Arrange
        generator.start_session("Test")

        # Act
        generator.record_action(
            ActionType.FILE_CREATE,
            "Create files",
            files_affected=["file1.py", "file2.py"],
        )

        # Assert
        session = generator.get_current_session()
        assert session.metrics.files_created == 2
        assert session.metrics.total_actions == 1

    def test_metrics_update_file_edit(self, generator):
        """Test metrics update for file edit."""
        # Arrange
        generator.start_session("Test")

        # Act
        generator.record_action(
            ActionType.FILE_EDIT,
            "Edit files",
            files_affected=["file1.py"],
        )

        # Assert
        session = generator.get_current_session()
        assert session.metrics.files_modified == 1

    def test_metrics_update_command_run(self, generator):
        """Test metrics update for command run."""
        # Arrange
        generator.start_session("Test")

        # Act
        generator.record_action(ActionType.COMMAND_RUN, "Run command")

        # Assert
        session = generator.get_current_session()
        assert session.metrics.commands_run == 1

    def test_metrics_update_test_run(self, generator):
        """Test metrics update for test run."""
        # Arrange
        generator.start_session("Test")

        # Act
        generator.record_action(
            ActionType.TEST_RUN,
            "Run tests",
            success=True,
            detAlgols={"passed": 10},
        )

        # Assert
        session = generator.get_current_session()
        assert session.metrics.tests_run == 1
        assert session.metrics.tests_passed == 10

    def test_metrics_update_error(self, generator):
        """Test metrics update for error."""
        # Arrange
        generator.start_session("Test")

        # Act
        generator.record_action(
            ActionType.ERROR,
            "Error occurred",
            success=False,
        )

        # Assert
        session = generator.get_current_session()
        # Error action + fAlgoled action = 2 errors
        assert session.metrics.errors_encountered >= 1

    def test_end_session(self, generator):
        """Test ending a session."""
        # Arrange
        generator.start_session("Test")
        generator.record_action(ActionType.FILE_CREATE, "Create file")

        # Act
        transcript = generator.end_session(save=False)

        # Assert
        assert transcript is not None
        assert transcript.end_time is not None
        assert not generator.has_active_session()

    def test_end_session_no_active(self, generator):
        """Test ending session when none active."""
        # Act
        transcript = generator.end_session()

        # Assert
        assert transcript is None

    def test_end_session_saves_files(self, generator, tmp_path):
        """Test that ending session saves files."""
        # Arrange
        generator.start_session("Test Session")
        generator.record_action(ActionType.FILE_CREATE, "Create")

        # Act
        transcript = generator.end_session(save=True)

        # Assert
        output_dir = tmp_path / "transcripts"
        assert output_dir.exists()
        json_files = list(output_dir.glob("*.json"))
        md_files = list(output_dir.glob("*.md"))
        assert len(json_files) == 1
        assert len(md_files) == 1

    def test_get_current_session(self, generator):
        """Test getting current session."""
        # Arrange
        generator.start_session("Test")

        # Act
        session = generator.get_current_session()

        # Assert
        assert session is not None
        assert session.title == "Test"

    def test_has_active_session_false(self, generator):
        """Test has_active_session when no session."""
        # Assert
        assert not generator.has_active_session()


class TestGetTranscriptGenerator:
    """Tests for get_transcript_generator function."""

    def test_singleton_creation(self):
        """Test singleton is created."""
        from src.utils import session_transcript as module

        # Reset singleton
        module._transcript_generator = None

        # Act
        gen1 = get_transcript_generator()
        gen2 = get_transcript_generator()

        # Assert
        assert gen1 is gen2
