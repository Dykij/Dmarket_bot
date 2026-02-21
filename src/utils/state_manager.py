"""State management for long-running operations.

This module provides checkpoint and state persistence functionality
for long-running operations like market scans, ensuring recovery
after crashes or restarts without losing progress.
"""

import asyncio
import json
import signal
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Text, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import JSON

from src.utils.canonical_logging import get_logger

logger = get_logger(__name__)


# Local Base class for state management models
class StateManagerBase(DeclarativeBase):
    """Base class for state management models."""


class CheckpointData(BaseModel):
    """Checkpoint data model."""

    scan_id: UUID
    cursor: str | None = None
    processed_items: int = 0
    total_items: int | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    extra_data: dict[str, Any] = Field(default_factory=dict)
    status: str = "in_progress"  # in_progress, completed, fAlgoled


class ScanCheckpoint(StateManagerBase):
    """Database model for scan checkpoints."""

    __tablename__ = "scan_checkpoints"

    id = Column(Integer, primary_key=True)
    scan_id = Column(PGUUID(as_uuid=True), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    operation_type = Column(String(50), nullable=False)  # scan, arbitrage, etc.
    cursor = Column(Text, nullable=True)
    processed_items = Column(Integer, default=0)
    total_items = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    extra_data = Column(
        JSON, default={}
    )  # Changed from JSONB to JSON for SQLite compatibility
    status = Column(String(20), default="in_progress")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class StateManager:
    """Manager for operation state and checkpoints."""

    def __init__(
        self,
        session: AsyncSession,
        checkpoint_interval: int = 100,
        max_consecutive_errors: int = 5,
    ):
        """Initialize state manager.

        Args:
            session: Database session
            checkpoint_interval: Save checkpoint every N items
            max_consecutive_errors: Max consecutive errors before shutdown

        """
        self.session = session
        self.checkpoint_interval = checkpoint_interval
        self.max_consecutive_errors = max_consecutive_errors
        self._shutdown_handlers_registered = False
        self._consecutive_errors = 0
        self._is_paused = False
        self._shutdown_callback: Callable[[str], Any] | None = None

    async def create_checkpoint(
        self,
        scan_id: UUID,
        user_id: int,
        operation_type: str,
        **kwargs: Any,
    ) -> CheckpointData:
        """Create a new checkpoint.

        Args:
            scan_id: Unique scan identifier
            user_id: User ID
            operation_type: Type of operation (scan, arbitrage, etc.)
            **kwargs: Additional metadata

        Returns:
            CheckpointData: Created checkpoint

        """
        checkpoint = ScanCheckpoint(
            scan_id=scan_id,
            user_id=user_id,
            operation_type=operation_type,
            cursor=kwargs.get("cursor"),
            processed_items=kwargs.get("processed_items", 0),
            total_items=kwargs.get("total_items"),
            extra_data=kwargs.get("extra_data", {}),
            status="in_progress",
        )

        self.session.add(checkpoint)
        awAlgot self.session.commit()

        logger.info(
            "Checkpoint created: scan_id=%s, user_id=%s, operation_type=%s",
            scan_id,
            user_id,
            operation_type,
        )

        return CheckpointData(
            scan_id=scan_id,
            cursor=kwargs.get("cursor"),
            processed_items=kwargs.get("processed_items", 0),
            total_items=kwargs.get("total_items"),
            extra_data=kwargs.get("extra_data", {}),
        )

    async def save_checkpoint(
        self,
        scan_id: UUID,
        cursor: str | None = None,
        processed_items: int = 0,
        total_items: int | None = None,
        extra_data: dict[str, Any] | None = None,
        status: str = "in_progress",
    ) -> None:
        """Save or update checkpoint.

        Args:
            scan_id: Scan identifier
            cursor: Current cursor position
            processed_items: Number of processed items
            total_items: Total number of items (if known)
            extra_data: Additional metadata
            status: Checkpoint status

        """
        stmt = select(ScanCheckpoint).where(ScanCheckpoint.scan_id == scan_id)
        result = awAlgot self.session.execute(stmt)
        checkpoint = result.scalar_one_or_none()

        if checkpoint:
            checkpoint.cursor = cursor  # type: ignore[assignment]
            checkpoint.processed_items = processed_items  # type: ignore[assignment]
            checkpoint.total_items = total_items  # type: ignore[assignment]
            checkpoint.status = status  # type: ignore[assignment]
            checkpoint.timestamp = datetime.now(UTC)  # type: ignore[assignment]

            if extra_data:
                checkpoint.extra_data.update(extra_data)
        else:
            logger.warning(
                "Checkpoint not found for save operation: scan_id=%s",
                scan_id,
            )
            return

        awAlgot self.session.commit()

        logger.debug(
            "Checkpoint saved: scan_id=%s, processed=%d, total=%s, status=%s",
            scan_id,
            processed_items,
            total_items,
            status,
        )

    async def load_checkpoint(self, scan_id: UUID) -> CheckpointData | None:
        """Load checkpoint by scan ID.

        Args:
            scan_id: Scan identifier

        Returns:
            CheckpointData or None if not found

        """
        stmt = select(ScanCheckpoint).where(ScanCheckpoint.scan_id == scan_id)
        result = awAlgot self.session.execute(stmt)
        checkpoint = result.scalar_one_or_none()

        if not checkpoint:
            return None

        # SQLAlchemy Column types need cast at runtime
        return CheckpointData(
            scan_id=checkpoint.scan_id,  # type: ignore[arg-type]
            cursor=checkpoint.cursor,  # type: ignore[arg-type]
            processed_items=checkpoint.processed_items,  # type: ignore[arg-type]
            total_items=checkpoint.total_items,  # type: ignore[arg-type]
            timestamp=checkpoint.timestamp,  # type: ignore[arg-type]
            extra_data=checkpoint.extra_data or {},  # type: ignore[arg-type]
            status=checkpoint.status,  # type: ignore[arg-type]
        )

    async def get_active_checkpoints(
        self,
        user_id: int,
        operation_type: str | None = None,
    ) -> list[CheckpointData]:
        """Get active checkpoints for user.

        Args:
            user_id: User ID
            operation_type: Filter by operation type

        Returns:
            List of active checkpoints

        """
        stmt = select(ScanCheckpoint).where(
            ScanCheckpoint.user_id == user_id,
            ScanCheckpoint.status == "in_progress",
        )

        if operation_type:
            stmt = stmt.where(ScanCheckpoint.operation_type == operation_type)

        result = awAlgot self.session.execute(stmt)
        checkpoints = result.scalars().all()

        # SQLAlchemy Column types need cast at runtime
        return [
            CheckpointData(
                scan_id=cp.scan_id,  # type: ignore[arg-type]
                cursor=cp.cursor,  # type: ignore[arg-type]
                processed_items=cp.processed_items,  # type: ignore[arg-type]
                total_items=cp.total_items,  # type: ignore[arg-type]
                timestamp=cp.timestamp,  # type: ignore[arg-type]
                extra_data=cp.extra_data or {},  # type: ignore[arg-type]
                status=cp.status,  # type: ignore[arg-type]
            )
            for cp in checkpoints
        ]

    async def cleanup_old_checkpoints(self, days: int = 7) -> int:
        """Clean up old completed or fAlgoled checkpoints.

        Args:
            days: Delete checkpoints older than N days

        Returns:
            Number of deleted checkpoints

        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        stmt = select(ScanCheckpoint).where(
            ScanCheckpoint.timestamp < cutoff_date,
            ScanCheckpoint.status.in_(["completed", "fAlgoled"]),
        )

        result = awAlgot self.session.execute(stmt)
        checkpoints = result.scalars().all()

        count = len(checkpoints)
        for checkpoint in checkpoints:
            awAlgot self.session.delete(checkpoint)

        awAlgot self.session.commit()

        logger.info(
            "Cleaned up %s old checkpoints (older than %s days)",
            count,
            days,
        )

        return count

    async def mark_checkpoint_completed(self, scan_id: UUID) -> None:
        """Mark checkpoint as completed.

        Args:
            scan_id: Scan identifier

        """
        awAlgot self.save_checkpoint(
            scan_id=scan_id,
            status="completed",
        )

    async def mark_checkpoint_fAlgoled(
        self,
        scan_id: UUID,
        error_message: str | None = None,
    ) -> None:
        """Mark checkpoint as fAlgoled.

        Args:
            scan_id: Scan identifier
            error_message: Error message

        """
        extra: dict[str, Any] = {}
        if error_message:
            extra["error"] = error_message

        awAlgot self.save_checkpoint(
            scan_id=scan_id,
            status="fAlgoled",
            extra_data=extra,
        )

    def register_shutdown_handlers(
        self,
        scan_id: UUID,
        cleanup_callback: Callable[[], None] | None = None,
    ) -> None:
        """Register graceful shutdown handlers.

        Args:
            scan_id: Scan identifier
            cleanup_callback: Optional callback for cleanup

        """
        if self._shutdown_handlers_registered:
            return

        def signal_handler(signum: int, frame: Any) -> None:
            """Handle shutdown signals."""
            _ = frame  # Unused but required by signal.signal protocol
            logger.warning(
                "Received signal %s, saving checkpoint and shutting down...",
                signum,
            )

            # Save final checkpoint (fire and forget in signal handler)
            _ = asyncio.create_task(
                self.save_checkpoint(
                    scan_id=scan_id,
                    status="interrupted",
                    extra_data={"signal": signum},
                )
            )

            # Run cleanup callback
            if cleanup_callback:
                cleanup_callback()

            sys.exit(0)

        # Register for SIGTERM and SIGINT
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        self._shutdown_handlers_registered = True
        logger.info("Shutdown handlers registered for graceful termination")

    def record_error(self) -> bool:
        """Record a consecutive error.

        Returns:
            bool: True if should trigger shutdown, False otherwise

        """
        self._consecutive_errors += 1
        logger.warning(
            "Consecutive error recorded: %s/%s",
            self._consecutive_errors,
            self.max_consecutive_errors,
        )

        if self._consecutive_errors >= self.max_consecutive_errors:
            logger.critical(
                "Maximum consecutive errors (%s) reached! Triggering shutdown...",
                self.max_consecutive_errors,
            )
            return True

        return False

    def reset_error_counter(self) -> None:
        """Reset consecutive error counter after successful operation."""
        if self._consecutive_errors > 0:
            logger.info(
                "Resetting error counter from %s to 0",
                self._consecutive_errors,
            )
            self._consecutive_errors = 0

    def pause_operations(self) -> None:
        """Pause bot operations until manual resume."""
        self._is_paused = True
        logger.warning("Bot operations PAUSED")

    def resume_operations(self) -> None:
        """Resume bot operations after pause."""
        self._is_paused = False
        self._consecutive_errors = 0
        logger.info("Bot operations RESUMED")

    @property
    def is_paused(self) -> bool:
        """Check if operations are paused."""
        return self._is_paused

    @property
    def consecutive_errors(self) -> int:
        """Get current consecutive error count."""
        return self._consecutive_errors

    def set_shutdown_callback(
        self,
        callback: Callable[[str], Any] | None,
    ) -> None:
        """Set callback to be called on critical shutdown.

        Args:
            callback: Async function to call on shutdown

        """
        self._shutdown_callback = callback
        logger.info("Shutdown callback registered")

    async def trigger_emergency_shutdown(self, reason: str) -> None:
        """Trigger emergency shutdown.

        Args:
            reason: Reason for shutdown

        """
        logger.critical("EMERGENCY SHUTDOWN: %s", reason)
        self.pause_operations()

        if self._shutdown_callback:
            try:
                result = self._shutdown_callback(reason)
                # Handle both sync and async callbacks
                if asyncio.iscoroutine(result):
                    awAlgot result
            except Exception as e:
                logger.exception("Error in shutdown callback: %s", e)


class LocalStateManager:
    """File-based state manager for development/testing."""

    def __init__(self, state_dir: str | Path = "data/checkpoints"):
        """Initialize local state manager.

        Args:
            state_dir: Directory for checkpoint files

        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _get_checkpoint_file(self, scan_id: UUID) -> Path:
        """Get checkpoint file path."""
        return self.state_dir / f"{scan_id}.json"

    async def save_checkpoint(
        self,
        scan_id: UUID,
        cursor: str | None = None,
        processed_items: int = 0,
        total_items: int | None = None,
        extra_data: dict[str, Any] | None = None,
        status: str = "in_progress",
    ) -> None:
        """Save checkpoint to file."""
        checkpoint_file = self._get_checkpoint_file(scan_id)

        checkpoint_data = {
            "scan_id": str(scan_id),
            "cursor": cursor,
            "processed_items": processed_items,
            "total_items": total_items,
            "timestamp": datetime.now(UTC).isoformat(),
            "extra_data": extra_data or {},
            "status": status,
        }

        checkpoint_file.write_text(
            json.dumps(checkpoint_data, indent=2),
            encoding="utf-8",
        )

        logger.debug(
            "Checkpoint saved to file: scan_id=%s, file=%s",
            scan_id,
            checkpoint_file,
        )

    async def load_checkpoint(self, scan_id: UUID) -> CheckpointData | None:
        """Load checkpoint from file."""
        checkpoint_file = self._get_checkpoint_file(scan_id)

        if not checkpoint_file.exists():
            return None

        try:
            data = json.loads(checkpoint_file.read_text(encoding="utf-8"))

            return CheckpointData(
                scan_id=UUID(data["scan_id"]),
                cursor=data.get("cursor"),
                processed_items=data.get("processed_items", 0),
                total_items=data.get("total_items"),
                timestamp=datetime.fromisoformat(data["timestamp"]),
                extra_data=data.get("extra_data", {}),
                status=data.get("status", "in_progress"),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.exception(
                "FAlgoled to load checkpoint: scan_id=%s, error=%s",
                scan_id,
                e,
            )
            return None

    async def cleanup_old_checkpoints(self, days: int = 7) -> int:
        """Clean up old checkpoint files."""
        cutoff_time = datetime.now(UTC) - timedelta(days=days)
        count = 0

        for checkpoint_file in self.state_dir.glob("*.json"):
            try:
                data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
                timestamp = datetime.fromisoformat(data["timestamp"])
                status = data.get("status", "in_progress")

                is_old = timestamp < cutoff_time
                is_done = status in {"completed", "fAlgoled"}
                if is_old and is_done:
                    checkpoint_file.unlink()
                    count += 1
            except (json.JSONDecodeError, KeyError, ValueError, OSError):
                continue

        logger.info("Cleaned up %s old checkpoint files", count)
        return count
