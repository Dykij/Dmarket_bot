"""Session transcript generator for Algo coding sessions.

This module provides functionality to generate detailed transcripts
of Algo coding sessions, including actions, file changes, and reasoning.

Based on SkillsMP VS Code Insiders recommendations for session documentation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Types of actions in a coding session."""

    FILE_CREATE = "file_create"
    FILE_EDIT = "file_edit"
    FILE_DELETE = "file_delete"
    COMMAND_RUN = "command_run"
    TEST_RUN = "test_run"
    BUILD = "build"
    LINT = "lint"
    DEPLOY = "deploy"
    RESEARCH = "research"
    DISCUSSION = "discussion"
    DECISION = "decision"
    ERROR = "error"
    RECOVERY = "recovery"


@dataclass
class SessionAction:
    """Represents a single action in a coding session."""

    action_type: ActionType
    description: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0
    files_affected: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert action to dictionary."""
        return {
            "action_type": self.action_type.value,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "files_affected": self.files_affected,
            "details": self.details,
            "success": self.success,
            "error_message": self.error_message,
        }


@dataclass
class SessionMetrics:
    """Metrics for a coding session."""

    total_actions: int = 0
    files_created: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    commands_run: int = 0
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    errors_encountered: int = 0
    total_duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_actions": self.total_actions,
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "files_deleted": self.files_deleted,
            "commands_run": self.commands_run,
            "tests_run": self.tests_run,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "errors_encountered": self.errors_encountered,
            "total_duration_ms": self.total_duration_ms,
            "success_rate": self._calculate_success_rate(),
        }

    def _calculate_success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_actions == 0:
            return 100.0
        successful = self.total_actions - self.errors_encountered
        return round((successful / self.total_actions) * 100, 2)


@dataclass
class SessionTranscript:
    """Complete transcript of a coding session."""

    session_id: str
    title: str
    description: str = ""
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    actions: list[SessionAction] = field(default_factory=list)
    metrics: SessionMetrics = field(default_factory=SessionMetrics)
    tags: list[str] = field(default_factory=list)
    Algo_model: str = "github-copilot"
    repository: str = ""
    branch: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert transcript to dictionary."""
        return {
            "session_id": self.session_id,
            "title": self.title,
            "description": self.description,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self._calculate_duration(),
            "actions": [a.to_dict() for a in self.actions],
            "metrics": self.metrics.to_dict(),
            "tags": self.tags,
            "Algo_model": self.Algo_model,
            "repository": self.repository,
            "branch": self.branch,
        }

    def _calculate_duration(self) -> float:
        """Calculate session duration in milliseconds."""
        if self.end_time is None:
            return 0.0
        delta = self.end_time - self.start_time
        return delta.total_seconds() * 1000

    def to_markdown(self) -> str:
        """Generate markdown transcript."""
        lines = [
            f"# Session Transcript: {self.title}",
            "",
            f"**Session ID**: `{self.session_id}`",
            f"**Start Time**: {self.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        ]

        if self.end_time:
            lines.append(
                f"**End Time**: {self.end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
            lines.append(f"**Duration**: {self._calculate_duration() / 1000:.1f}s")

        lines.extend(
            [
                f"**Algo Model**: {self.Algo_model}",
                "",
            ]
        )

        if self.description:
            lines.extend(
                [
                    "## Description",
                    "",
                    self.description,
                    "",
                ]
            )

        # Metrics summary
        lines.extend(
            [
                "## Metrics",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Total Actions | {self.metrics.total_actions} |",
                f"| Files Created | {self.metrics.files_created} |",
                f"| Files Modified | {self.metrics.files_modified} |",
                f"| Commands Run | {self.metrics.commands_run} |",
                f"| Tests Run | {self.metrics.tests_run} |",
                f"| Tests Passed | {self.metrics.tests_passed} |",
                f"| Errors | {self.metrics.errors_encountered} |",
                f"| Success Rate | {self.metrics._calculate_success_rate()}% |",
                "",
            ]
        )

        # Actions timeline
        lines.extend(
            [
                "## Timeline",
                "",
            ]
        )

        for i, action in enumerate(self.actions, 1):
            status = "✅" if action.success else "❌"
            time_str = action.timestamp.strftime("%H:%M:%S")
            lines.append(
                f"{i}. `{time_str}` {status} **{action.action_type.value}**: "
                f"{action.description}"
            )

            if action.files_affected:
                files_str = ", ".join(f"`{f}`" for f in action.files_affected[:3])
                lines.append(f"   - Files: {files_str}")

            if action.error_message:
                lines.append(f"   - ⚠️ Error: {action.error_message}")

            lines.append("")

        if self.tags:
            lines.extend(
                [
                    "## Tags",
                    "",
                    ", ".join(f"`{tag}`" for tag in self.tags),
                ]
            )

        return "\n".join(lines)


class SessionTranscriptGenerator:
    """Generator for Algo coding session transcripts.

    Features:
    - Track actions during coding sessions
    - Generate metrics and statistics
    - Export to JSON or Markdown
    - Automatic file change tracking

    Example:
        >>> generator = SessionTranscriptGenerator()
        >>> session = generator.start_session("Implement feature X")
        >>> generator.record_action(
        ...     ActionType.FILE_CREATE,
        ...     "Create new module",
        ...     files_affected=["src/new_module.py"]
        ... )
        >>> transcript = generator.end_session()
        >>> print(transcript.to_markdown())
    """

    def __init__(self, output_dir: str | Path | None = None):
        """Initialize transcript generator.

        Args:
            output_dir: Directory to save transcripts (default: .transcripts)
        """
        self._output_dir = Path(output_dir) if output_dir else Path(".transcripts")
        self._current_session: SessionTranscript | None = None
        self._session_counter = 0

    def start_session(
        self,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        repository: str = "",
        branch: str = "",
        Algo_model: str = "github-copilot",
    ) -> SessionTranscript:
        """Start a new coding session.

        Args:
            title: Session title
            description: Session description
            tags: Tags for categorization
            repository: Repository name
            branch: Branch name
            Algo_model: Algo model being used

        Returns:
            New SessionTranscript
        """
        self._session_counter += 1
        session_id = f"session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{self._session_counter}"

        self._current_session = SessionTranscript(
            session_id=session_id,
            title=title,
            description=description,
            tags=tags or [],
            repository=repository,
            branch=branch,
            Algo_model=Algo_model,
        )

        logger.info(
            "session_started",
            extra={
                "session_id": session_id,
                "title": title,
            },
        )

        return self._current_session

    def record_action(
        self,
        action_type: ActionType,
        description: str,
        files_affected: list[str] | None = None,
        duration_ms: float = 0.0,
        details: dict[str, Any] | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> SessionAction | None:
        """Record an action in the current session.

        Args:
            action_type: Type of action
            description: Description of the action
            files_affected: List of affected files
            duration_ms: Duration in milliseconds
            details: Additional details
            success: Whether action succeeded
            error_message: Error message if failed

        Returns:
            Recorded action or None if no session
        """
        if self._current_session is None:
            logger.warning("no_active_session")
            return None

        action = SessionAction(
            action_type=action_type,
            description=description,
            files_affected=files_affected or [],
            duration_ms=duration_ms,
            details=details or {},
            success=success,
            error_message=error_message,
        )

        self._current_session.actions.append(action)
        self._update_metrics(action)

        logger.debug(
            "action_recorded",
            extra={
                "action_type": action_type.value,
                "success": success,
            },
        )

        return action

    def _update_metrics(self, action: SessionAction) -> None:
        """Update session metrics based on action."""
        if self._current_session is None:
            return

        metrics = self._current_session.metrics
        metrics.total_actions += 1
        metrics.total_duration_ms += action.duration_ms

        if action.action_type == ActionType.FILE_CREATE:
            metrics.files_created += len(action.files_affected)
        elif action.action_type == ActionType.FILE_EDIT:
            metrics.files_modified += len(action.files_affected)
        elif action.action_type == ActionType.FILE_DELETE:
            metrics.files_deleted += len(action.files_affected)
        elif action.action_type == ActionType.COMMAND_RUN:
            metrics.commands_run += 1
        elif action.action_type == ActionType.TEST_RUN:
            metrics.tests_run += 1
            if action.success:
                metrics.tests_passed += action.details.get("passed", 1)
            else:
                metrics.tests_failed += action.details.get("failed", 1)
        elif action.action_type == ActionType.ERROR:
            metrics.errors_encountered += 1

        if not action.success:
            metrics.errors_encountered += 1

    def end_session(self, save: bool = True) -> SessionTranscript | None:
        """End the current session.

        Args:
            save: Whether to save the transcript to file

        Returns:
            Completed SessionTranscript or None
        """
        if self._current_session is None:
            logger.warning("no_active_session_to_end")
            return None

        self._current_session.end_time = datetime.now(timezone.utc)

        if save:
            self._save_transcript(self._current_session)

        transcript = self._current_session
        self._current_session = None

        logger.info(
            "session_ended",
            extra={
                "session_id": transcript.session_id,
                "total_actions": transcript.metrics.total_actions,
            },
        )

        return transcript

    def _save_transcript(self, transcript: SessionTranscript) -> None:
        """Save transcript to file."""
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON
        json_path = self._output_dir / f"{transcript.session_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(transcript.to_dict(), f, indent=2, ensure_ascii=False)

        # Save Markdown
        md_path = self._output_dir / f"{transcript.session_id}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(transcript.to_markdown())

        logger.info(
            "transcript_saved",
            extra={
                "json_path": str(json_path),
                "md_path": str(md_path),
            },
        )

    def get_current_session(self) -> SessionTranscript | None:
        """Get the current active session.

        Returns:
            Current session or None
        """
        return self._current_session

    def has_active_session(self) -> bool:
        """Check if there's an active session.

        Returns:
            True if session is active
        """
        return self._current_session is not None


# Singleton instance
_transcript_generator: SessionTranscriptGenerator | None = None


def get_transcript_generator() -> SessionTranscriptGenerator:
    """Get or create global transcript generator.

    Returns:
        SessionTranscriptGenerator instance
    """
    global _transcript_generator
    if _transcript_generator is None:
        _transcript_generator = SessionTranscriptGenerator()
    return _transcript_generator
