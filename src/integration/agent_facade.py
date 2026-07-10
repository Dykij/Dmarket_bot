"""
Agent facade — единый интерфейс для агента, интегрирующий все новые модули.
Предоставляет: safe bash, CoT logging, snapshot/rollback, workflow orchestration.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.cot_audit.core import CoTLogEntry, CoTReport, FormatStyle
from src.reflexion.core import ReflexionConfig, SnapshotManager, SnapshotManifest
from src.sandbox.core import BashSandbox, SandboxCommand, SandboxConfig, SandboxResult
from src.workflow.chains import WorkflowBuilder

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    jitter: bool = True


@dataclass
class RetryResult:
    success: bool
    attempts: int
    total_delay_ms: float
    last_error: str | None = None


@dataclass
class AgentAction:
    name: str
    description: str
    handler: callable


class AgentFacade:
    """
    Единый фасад для всех архитектурных компонентов OpenCode.
    """

    def __init__(self, repo_root: str = ".", work_dir: str = ".", retry_config: RetryConfig | None = None):
        self.sandbox = BashSandbox(SandboxConfig(work_dir=work_dir))
        self.cot_report: CoTReport = CoTReport(session_id="auto")
        self.snapshot_manager = SnapshotManager(ReflexionConfig(repo_root=repo_root))
        self.workflow_builder: WorkflowBuilder | None = None
        self.retry_config = retry_config or RetryConfig()

    # ── Safe Bash Interface ──

    async def safe_bash(self, command: str, cwd: str | None = None, env: dict[str, str] | None = None) -> SandboxResult:
        """
        Безопасное выполнение bash-команд через Sandbox.
        """
        self._log_cot("Bash Execution", f"Executing: {command}")
        result = await self.sandbox.execute(SandboxCommand(command=command, cwd=cwd, env=env or {}))
        if result.status.value == "success":
            self._log_cot("Bash Success", f"Output:\n{result.stdout}")
        else:
            self._log_cot("Bash Failure", f"Error:\n{result.stderr}", reasoning="Sandbox returned non-success status")
        return result

    # ── CoT Logging ──

    def _log_cot(self, title: str, content: str, reasoning: str | None = None) -> None:
        step = len(self.cot_report.entries) + 1
        entry = CoTLogEntry(step_number=step, title=title, content=content, reasoning=reasoning)
        self.cot_report.entries.append(entry)

    def get_cot_markdown(self) -> str:
        """Возвращает цепочку рассуждений в Markdown для пользователя."""
        return self.cot_report.to_markdown()

    def get_cot_user_friendly(self, style: FormatStyle = FormatStyle.BULLET) -> str:
        return self.cot_report.to_user_friendly(style)

    # ── Snapshot / Rollback ──

    def create_snapshot(self, label: str = "auto") -> SnapshotManifest:
        """Создаёт точку восстановления."""
        manifest = self.snapshot_manager.create(label)
        self._log_cot("Snapshot Created", f"ID: {manifest.id}")
        return manifest

    def rollback(self, snapshot_id: str) -> bool:
        """Восстанавливает состояние из snapshot."""
        self._log_cot("Rollback", f"Restoring to {snapshot_id}")
        return self.snapshot_manager.rollback(snapshot_id)

    # ── Workflow Orchestration ──

    def start_workflow(self) -> WorkflowBuilder:
        """Начинает новую цепочку workflow."""
        self.workflow_builder = WorkflowBuilder()
        self._log_cot("Workflow Started", "New workflow chain initialized")
        return self.workflow_builder

    async def run_workflow(self) -> list[Any]:
        """Запускает workflow и возвращает результаты."""
        if not self.workflow_builder:
            raise RuntimeError("No workflow builder initialized. Call start_workflow() first.")
        self._log_cot("Workflow Running", f"Tasks: {len(self.workflow_builder._tasks)}")
        return await self.workflow_builder.run()

    # ── Combined Operations ──

    def _compute_backoff(self, attempt: int) -> float:
        """Compute exponential backoff delay with optional jitter."""
        delay = min(
            self.retry_config.base_delay * (2 ** attempt),
            self.retry_config.max_delay,
        )
        if self.retry_config.jitter:
            delay *= (0.5 + random.random() * 0.5)
        return delay

    async def execute_with_snapshot(
        self,
        command: str,
        label: str = "exec",
        max_retries: int | None = None,
        on_retry: Callable[[int, float, Exception], None] | None = None,
    ) -> SandboxResult:
        """
        Выполняет команду с автоматической точкой восстановления и retry.
        При ошибке: rollback → backoff → retry (до max_retries попыток).
        """
        retries = max_retries if max_retries is not None else self.retry_config.max_retries
        manifest = self.create_snapshot(label)
        last_error: Exception | None = None
        total_delay_ms = 0.0

        for attempt in range(retries + 1):
            try:
                result = await self.safe_bash(command)
                if result.status.value != "success":
                    raise RuntimeError(f"Command failed: {result.stderr}")
                if attempt > 0:
                    self._log_cot(
                        "Retry Success",
                        f"Succeeded on attempt {attempt + 1}/{retries + 1}",
                        reasoning=f"Total delay: {total_delay_ms:.0f}ms",
                    )
                return result
            except Exception as e:
                last_error = e
                self._log_cot(
                    "Attempt Failed",
                    f"Attempt {attempt + 1}/{retries + 1}: {e}",
                    reasoning="Will retry after rollback" if attempt < retries else "Max retries reached",
                )

                # Rollback to snapshot before retry
                self.rollback(manifest.id)

                # If not last attempt, wait with exponential backoff
                if attempt < retries:
                    delay = self._compute_backoff(attempt)
                    total_delay_ms += delay * 1000
                    self._log_cot(
                        "Backoff Wait",
                        f"Waiting {delay:.2f}s before retry {attempt + 2}/{retries + 1}",
                    )
                    if on_retry:
                        on_retry(attempt + 1, delay, e)
                    await asyncio.sleep(delay)

        # All retries exhausted
        self._log_cot(
            "All Retries Exhausted",
            f"Failed after {retries + 1} attempts",
            reasoning=f"Last error: {last_error}",
        )
        raise last_error
