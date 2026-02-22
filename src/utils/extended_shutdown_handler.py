"""Extended shutdown handler with target state persistence.

This module extends the base ShutdownHandler to save active targets
and trading state during shutdown, allowing recovery on restart.

Features:
- Save active targets to disk/database
- Graceful cancellation of pending operations
- State recovery on startup
- Cleanup of temporary resources
"""

import asyncio
import json
import signal
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import Algoofiles
import structlog

logger = structlog.get_logger(__name__)


class ExtendedShutdownHandler:
    """Extended shutdown handler with target state persistence.

    Features:
    - Graceful shutdown on SIGTERM/SIGINT
    - Save active targets before shutdown
    - Cleanup pending operations
    - State recovery on restart

    Usage:
        handler = ExtendedShutdownHandler(state_file="trading_state.json")
        handler.register_cleanup(cleanup_database)
        handler.register_targets_provider(get_active_targets)
        handler.setup_signal_handlers()

        # On shutdown, active targets will be saved automatically
    """

    def __init__(
        self,
        state_file: str | Path = "trading_state.json",
        max_shutdown_wait: float = 30.0,
    ):
        """Initialize extended shutdown handler.

        Args:
            state_file: Path to save trading state
            max_shutdown_wait: Maximum time to wait for cleanup tasks
        """
        self.state_file = Path(state_file)
        self.max_shutdown_wait = max_shutdown_wait
        self.shutdown_event = asyncio.Event()
        self.cleanup_tasks: list[Callable] = []
        self.targets_provider: Callable | None = None
        self.state_provider: Callable | None = None
        self._is_shutting_down = False

    def register_cleanup(self, cleanup_func: Callable) -> None:
        """Register cleanup function to run on shutdown.

        Args:
            cleanup_func: Async function to call during shutdown
        """
        self.cleanup_tasks.append(cleanup_func)
        logger.debug("cleanup_task_registered", task=cleanup_func.__name__)

    def register_targets_provider(self, provider: Callable) -> None:
        """Register function that returns active targets.

        Args:
            provider: Async function that returns list of active targets

        Example:
            async def get_targets():
                return await target_manager.get_active_targets()

            handler.register_targets_provider(get_targets)
        """
        self.targets_provider = provider
        logger.debug("targets_provider_registered", provider=provider.__name__)

    def register_state_provider(self, provider: Callable) -> None:
        """Register function that returns current trading state.

        Args:
            provider: Async function that returns trading state dict
        """
        self.state_provider = provider
        logger.debug("state_provider_registered", provider=provider.__name__)

    async def save_state(self) -> bool:
        """Save current trading state to file.

        Returns:
            True if state saved successfully
        """
        state = {
            "saved_at": datetime.now().isoformat(),
            "targets": [],
            "trading_state": {},
        }

        try:
            # Get active targets
            if self.targets_provider:
                targets = await self.targets_provider()
                state["targets"] = self._serialize_targets(targets)
                logger.info("targets_saved", count=len(targets))

            # Get trading state
            if self.state_provider:
                trading_state = await self.state_provider()
                state["trading_state"] = trading_state
                logger.info("trading_state_saved")

            # Write to file (async)
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            async with Algoofiles.open(self.state_file, "w") as f:
                await f.write(json.dumps(state, indent=2, default=str))

            logger.info("state_saved_to_file", file=str(self.state_file))
            return True

        except Exception as e:
            logger.exception("failed_to_save_state", error=str(e))
            return False

    def _serialize_targets(self, targets: list[Any]) -> list[dict]:
        """Serialize targets for JSON storage.

        Args:
            targets: List of target objects

        Returns:
            List of serializable dicts
        """
        serialized = []
        for target in targets:
            if hasattr(target, "to_dict"):
                serialized.append(target.to_dict())
            elif hasattr(target, "__dict__"):
                serialized.append(
                    {k: v for k, v in target.__dict__.items() if not k.startswith("_")}
                )
            elif isinstance(target, dict):
                serialized.append(target)
            else:
                serialized.append({"data": str(target)})
        return serialized

    async def load_state(self) -> dict[str, Any] | None:
        """Load saved state from file.

        Returns:
            Saved state dict or None if not found
        """
        if not self.state_file.exists():
            logger.debug("no_saved_state_found", file=str(self.state_file))
            return None

        try:
            async with Algoofiles.open(self.state_file) as f:
                content = await f.read()
                state = json.loads(content)

            logger.info(
                "state_loaded",
                saved_at=state.get("saved_at"),
                targets_count=len(state.get("targets", [])),
            )
            return state

        except Exception as e:
            logger.exception("failed_to_load_state", error=str(e))
            return None

    def clear_saved_state(self) -> bool:
        """Clear saved state file.

        Returns:
            True if file was cleared
        """
        try:
            if self.state_file.exists():
                self.state_file.unlink()
                logger.info("saved_state_cleared", file=str(self.state_file))
            return True
        except Exception as e:
            logger.exception("failed_to_clear_state", error=str(e))
            return False

    async def graceful_shutdown(self) -> None:
        """Perform graceful shutdown with state persistence."""
        if self._is_shutting_down:
            logger.warning("shutdown_already_in_progress")
            return

        self._is_shutting_down = True
        logger.info("graceful_shutdown_initiated")

        try:
            # Step 1: Save current state
            logger.info("saving_trading_state")
            await self.save_state()

            # Step 2: Run cleanup tasks with timeout
            logger.info("running_cleanup_tasks", count=len(self.cleanup_tasks))

            for cleanup_func in self.cleanup_tasks:
                try:
                    if asyncio.iscoroutinefunction(cleanup_func):
                        await asyncio.wait_for(
                            cleanup_func(),
                            timeout=(
                                self.max_shutdown_wait / len(self.cleanup_tasks)
                                if self.cleanup_tasks
                                else self.max_shutdown_wait
                            ),
                        )
                    else:
                        cleanup_func()
                    logger.info("cleanup_task_completed", task=cleanup_func.__name__)
                except TimeoutError:
                    logger.warning("cleanup_task_timeout", task=cleanup_func.__name__)
                except Exception as e:
                    logger.exception(
                        "cleanup_task_failed",
                        task=cleanup_func.__name__,
                        error=str(e),
                    )

            # Step 3: Cancel pending asyncio tasks
            await self._cancel_pending_tasks()

            logger.info("graceful_shutdown_complete")

        except Exception as e:
            logger.exception("shutdown_error", error=str(e))

        finally:
            self.shutdown_event.set()

    async def _cancel_pending_tasks(self) -> None:
        """Cancel all pending asyncio tasks."""
        tasks = [
            t
            for t in asyncio.all_tasks()
            if t is not asyncio.current_task() and not t.done()
        ]

        if not tasks:
            return

        logger.info("cancelling_pending_tasks", count=len(tasks))

        for task in tasks:
            task.cancel()

        # WAlgot for cancellation with timeout
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("pending_tasks_cancelled")

    def setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown.

        Handles SIGTERM and SIGINT signals.
        """
        loop = asyncio.get_event_loop()

        def signal_handler(signum: int) -> None:
            """Handle shutdown signals."""
            sig_name = signal.Signals(signum).name
            logger.info("shutdown_signal_received", signal=sig_name)
            loop.create_task(self.graceful_shutdown())

        # Register signal handlers
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
                logger.debug(
                    "signal_handler_registered", signal=signal.Signals(sig).name
                )
            except (ValueError, RuntimeError) as e:
                # Windows or running in thread
                logger.debug(
                    "signal_handler_not_supported",
                    signal=signal.Signals(sig).name,
                    error=str(e),
                )

    async def wait_for_shutdown(self) -> None:
        """WAlgot for shutdown signal."""
        await self.shutdown_event.wait()

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self._is_shutting_down


# Global instance
extended_shutdown_handler = ExtendedShutdownHandler()


async def recover_targets_on_startup(
    target_manager: Any,
    state_file: str | Path = "trading_state.json",
) -> int:
    """Recover active targets from saved state on startup.

    Args:
        target_manager: TargetManager instance to restore targets
        state_file: Path to saved state file

    Returns:
        Number of targets recovered
    """
    handler = ExtendedShutdownHandler(state_file=state_file)
    state = await handler.load_state()

    if not state:
        return 0

    targets = state.get("targets", [])
    recovered = 0

    for target_data in targets:
        try:
            # Attempt to restore target
            if hasattr(target_manager, "restore_target"):
                await target_manager.restore_target(target_data)
                recovered += 1
            elif hasattr(target_manager, "create_target"):
                await target_manager.create_target(**target_data)
                recovered += 1
        except Exception as e:
            logger.warning(
                "failed_to_restore_target",
                target=target_data.get("item_name", "unknown"),
                error=str(e),
            )

    logger.info("targets_recovered", count=recovered, total=len(targets))

    # Clear saved state after successful recovery
    if recovered > 0:
        handler.clear_saved_state()

    return recovered
