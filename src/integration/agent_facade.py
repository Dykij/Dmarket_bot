"""
Agent facade — единый интерфейс для агента, интегрирующий все новые модули.
Предоставляет: safe bash, CoT logging, snapshot/rollback, workflow orchestration.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.sandbox.core import BashSandbox, SandboxCommand, SandboxConfig, SandboxResult
from src.cot_audit.core import CoTLogEntry, CoTReport, FormatStyle
from src.reflexion.core import ReflexionConfig, SnapshotManager, SnapshotManifest
from src.workflow.chains import AgentRole, WorkflowBuilder

logger = logging.getLogger(__name__)


@dataclass
class AgentAction:
    name: str
    description: str
    handler: callable


class AgentFacade:
    """
    Единый фасад для всех архитектурных компонентов OpenCode.
    """

    def __init__(self, repo_root: str = ".", work_dir: str = "."):
        self.sandbox = BashSandbox(SandboxConfig(work_dir=work_dir))
        self.cot_report: CoTReport = CoTReport(session_id="auto")
        self.snapshot_manager = SnapshotManager(ReflexionConfig(repo_root=repo_root))
        self.workflow_builder: Optional[WorkflowBuilder] = None

    # ── Safe Bash Interface ──

    async def safe_bash(self, command: str, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> SandboxResult:
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

    def _log_cot(self, title: str, content: str, reasoning: Optional[str] = None) -> None:
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

    async def run_workflow(self) -> List[Any]:
        """Запускает workflow и возвращает результаты."""
        if not self.workflow_builder:
            raise RuntimeError("No workflow builder initialized. Call start_workflow() first.")
        self._log_cot("Workflow Running", f"Tasks: {len(self.workflow_builder._tasks)}")
        return await self.workflow_builder.run()

    # ── Combined Operations ──

    async def execute_with_snapshot(self, command: str, label: str = "exec") -> SandboxResult:
        """
        Выполняет команду с автоматической точкой восстановления.
        Если команда не удалась — автоматический rollback.
        """
        manifest = self.create_snapshot(label)
        try:
            result = await self.safe_bash(command)
            if result.status.value != "success":
                raise RuntimeError(f"Command failed: {result.stderr}")
            return result
        except Exception as e:
            self._log_cot("Auto-Rollback", f"Exception: {e}")
            self.rollback(manifest.id)
            raise
