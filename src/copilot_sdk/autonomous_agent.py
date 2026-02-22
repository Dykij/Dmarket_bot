"""
Autonomous Agent - Автономный агент для выполнения сложных задач.

Агент, который может создавать и выполнять планы для достижения целей,
с возможностью адаптации при неудачах.

Вдохновлено Claude Code: "Assign issues directly and let it autonomously write code"

Usage:
    ```python
    from src.copilot_sdk.autonomous_agent import AutonomousAgent

    agent = AutonomousAgent()
    await agent.initialize()

    # Выполнить задачу автономно
    results = await agent.execute_plan("Find and fix all type errors in src/dmarket/")

    # Проверить прогресс
    status = agent.get_status()
    ```

Created: January 2026
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import structlog

from src.copilot_sdk.file_editor import FileEditor
from src.copilot_sdk.project_indexer import ProjectIndexer

logger = structlog.get_logger(__name__)


class StepStatus(StrEnum):
    """Статус шага плана."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAlgoLED = "failed"
    SKIPPED = "skipped"


@dataclass
class Step:
    """Шаг плана выполнения."""

    id: str
    description: str
    skill: str | None = None
    action: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def duration(self) -> float | None:
        """Продолжительность выполнения в секундах."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


@dataclass
class Plan:
    """План выполнения задачи."""

    goal: str
    steps: list[Step]
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "created"
    adjustments: int = 0

    @property
    def progress(self) -> float:
        """Прогресс выполнения (0.0 - 1.0)."""
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        return completed / len(self.steps)

    @property
    def is_complete(self) -> bool:
        """План полностью выполнен."""
        return all(
            s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in self.steps
        )


@dataclass
class StepResult:
    """Результат выполнения шага."""

    success: bool
    output: Any = None
    error: str | None = None


class AutonomousAgent:
    """Агент для автономного выполнения сложных задач."""

    def __init__(self, max_adjustments: int = 3, dry_run: bool = False):
        """
        Инициализация автономного агента.

        Args:
            max_adjustments: Максимальное количество корректировок плана
            dry_run: Режим симуляции без реальных действий
        """
        self.max_adjustments = max_adjustments
        self.dry_run = dry_run
        self._initialized = False
        self._current_plan: Plan | None = None

        # Компоненты
        self._skill_registry = None
        self._file_editor = None
        self._project_indexer = None

    async def initialize(self, project_root: str | Path | None = None) -> None:
        """
        Инициализация агента.

        Args:
            project_root: Корневая директория проекта
        """
        from src.copilot_sdk.skill_registry import SkillRegistry

        self._skill_registry = SkillRegistry()
        root = Path(project_root) if project_root else Path.cwd()
        await self._skill_registry.discover_skills(root / "src")

        self._initialized = True
        # Core skills registration
        await self._register_core_skills()

        logger.info(
            "autonomous_agent_initialized",
            skills_count=len(self._skill_registry.skills),
            dry_run=self.dry_run,
        )

    async def _register_core_skills(self) -> None:
        """Register core skills manually."""
        if not self._skill_registry:
            return

        # File Editor
        self._skill_registry.register(
            id="file-editor",
            name="File Editor",
            instance=FileEditor(dry_run=self.dry_run),
            description="Edit files, apply patches, and manage git commits.",
            category="development",
        )

        # Project Indexer
        self._skill_registry.register(
            id="project-indexer",
            name="Project Indexer",
            instance=ProjectIndexer(),
            description="Index and search project codebase.",
            category="development",
        )

    async def execute_plan(self, goal: str) -> list[StepResult]:
        """
        Создать и выполнить план для достижения цели.

        Args:
            goal: Целевая задача

        Returns:
            Список результатов выполнения шагов
        """
        self._ensure_initialized()

        logger.info("autonomous_agent_executing", goal=goal)

        # 1. Создать план
        plan = await self._create_plan(goal)
        self._current_plan = plan

        # 2. Выполнить шаги
        results: list[StepResult] = []

        for step in plan.steps:
            result = await self._execute_step(step)
            results.append(result)

            # 3. Проверить и скорректировать при неудаче
            if not result.success:
                if plan.adjustments < self.max_adjustments:
                    adjusted_plan = await self._adjust_plan(plan, step, result)
                    if adjusted_plan:
                        plan = adjusted_plan
                        self._current_plan = plan
                else:
                    logger.warning(
                        "max_adjustments_reached",
                        goal=goal,
                        adjustments=plan.adjustments,
                    )

        plan.status = "completed" if plan.is_complete else "partial"

        logger.info(
            "autonomous_agent_completed",
            goal=goal,
            success=plan.is_complete,
            progress=plan.progress,
        )

        return results

    async def _create_plan(self, goal: str) -> Plan:
        """
        Создать план выполнения.

        Args:
            goal: Целевая задача

        Returns:
            План с шагами
        """
        steps = []

        # Анализ цели и создание шагов
        goal_lower = goal.lower()

        # Паттерны задач и соответствующие шаги
        if "find" in goal_lower and "fix" in goal_lower:
            steps = await self._create_find_fix_plan(goal)
        elif "arbitrage" in goal_lower or "scan" in goal_lower:
            steps = await self._create_arbitrage_plan(goal)
        elif "test" in goal_lower:
            steps = await self._create_testing_plan(goal)
        elif "refactor" in goal_lower:
            steps = await self._create_refactoring_plan(goal)
        else:
            steps = await self._create_generic_plan(goal)

        return Plan(goal=goal, steps=steps)

    async def _create_find_fix_plan(self, goal: str) -> list[Step]:
        """Создать план для поиска и исправления."""
        return [
            Step(
                id="analyze",
                description="Анализ кода для поиска проблем",
                skill="project-indexer",
                action="search",
            ),
            Step(
                id="identify",
                description="Идентификация конкретных проблем",
                skill="code-analyzer",
                action="find_issues",
            ),
            Step(
                id="fix",
                description="Исправление найденных проблем",
                skill="file-editor",
                action="apply_fixes",
            ),
            Step(
                id="verify",
                description="Проверка исправлений",
                skill="test-runner",
                action="run_tests",
            ),
        ]

    async def _create_arbitrage_plan(self, goal: str) -> list[Step]:
        """Создать план для арбитража."""
        return [
            Step(
                id="scan",
                description="Сканирование рынка",
                skill="Algo-arbitrage-predictor",
                action="predict",
            ),
            Step(
                id="filter",
                description="Фильтрация возможностей",
                skill="Algo-arbitrage-predictor",
                action="filter_opportunities",
            ),
            Step(
                id="analyze",
                description="Анализ ликвидности",
                skill="liquidity-analyzer",
                action="analyze",
            ),
            Step(
                id="notify",
                description="Отправка уведомлений",
                skill="notifier",
                action="send_alerts",
            ),
        ]

    async def _create_testing_plan(self, goal: str) -> list[Step]:
        """Создать план для тестирования."""
        return [
            Step(
                id="discover",
                description="Поиск тестов",
                skill="test-runner",
                action="discover",
            ),
            Step(
                id="run",
                description="Запуск тестов",
                skill="test-runner",
                action="run",
            ),
            Step(
                id="report",
                description="Формирование отчёта",
                skill="test-runner",
                action="report",
            ),
        ]

    async def _create_refactoring_plan(self, goal: str) -> list[Step]:
        """Создать план для рефакторинга."""
        return [
            Step(
                id="analyze",
                description="Анализ кода",
                skill="code-analyzer",
                action="analyze",
            ),
            Step(
                id="identify",
                description="Идентификация областей для рефакторинга",
                skill="code-analyzer",
                action="identify_smells",
            ),
            Step(
                id="refactor",
                description="Применение рефакторинга",
                skill="file-editor",
                action="refactor",
            ),
            Step(
                id="verify",
                description="Проверка через тесты",
                skill="test-runner",
                action="run",
            ),
        ]

    async def _create_generic_plan(self, goal: str) -> list[Step]:
        """Создать общий план."""
        return [
            Step(
                id="understand",
                description="Понимание задачи",
                skill="project-indexer",
                action="search",
            ),
            Step(
                id="plan",
                description="Детальное планирование",
                skill=None,
                action="create_subtasks",
            ),
            Step(
                id="execute",
                description="Выполнение",
                skill=None,
                action="execute",
            ),
            Step(
                id="verify",
                description="Проверка результата",
                skill=None,
                action="verify",
            ),
        ]

    async def _execute_step(self, step: Step) -> StepResult:
        """
        Выполнить шаг плана.

        Args:
            step: Шаг для выполнения

        Returns:
            Результат выполнения
        """
        step.status = StepStatus.IN_PROGRESS
        step.started_at = datetime.now()

        logger.info(
            "step_executing",
            step_id=step.id,
            description=step.description,
            dry_run=self.dry_run,
        )

        try:
            if self.dry_run:
                # Симуляция
                await asyncio.sleep(0.1)
                result = StepResult(
                    success=True,
                    output=f"[DRY RUN] Step '{step.id}' would execute: {step.description}",
                )
            # Реальное выполнение
            elif step.skill and self._skill_registry:
                output = await self._skill_registry.execute(
                    step.skill,
                    step.action or "execute",
                    **step.args,
                )
                result = StepResult(success=True, output=output)
            else:
                result = StepResult(
                    success=True,
                    output=f"Step '{step.id}' executed (no skill assigned)",
                )

            step.status = StepStatus.COMPLETED
            step.result = result.output

        except Exception as e:
            logger.error(
                "step_failed",
                step_id=step.id,
                error=str(e),
                exc_info=True,
            )
            result = StepResult(success=False, error=str(e))
            step.status = StepStatus.FAlgoLED
            step.error = str(e)

        step.completed_at = datetime.now()
        return result

    async def _adjust_plan(
        self,
        plan: Plan,
        failed_step: Step,
        result: StepResult,
    ) -> Plan | None:
        """
        Скорректировать план после неудачи.

        Args:
            plan: Текущий план
            failed_step: Неудавшийся шаг
            result: Результат неудачи

        Returns:
            Скорректированный план или None
        """
        plan.adjustments += 1

        logger.info(
            "plan_adjusting",
            goal=plan.goal,
            failed_step=failed_step.id,
            adjustment=plan.adjustments,
        )

        # Стратегии корректировки
        # 1. Пропустить шаг и продолжить
        if "optional" in failed_step.description.lower():
            failed_step.status = StepStatus.SKIPPED
            return plan

        # 2. Добавить подготовительный шаг
        if "permission" in str(result.error).lower():
            prep_step = Step(
                id=f"prep_{failed_step.id}",
                description="Подготовка окружения",
                skill=None,
                action="prepare",
            )
            idx = plan.steps.index(failed_step)
            plan.steps.insert(idx, prep_step)
            failed_step.status = StepStatus.PENDING
            return plan

        # 3. Разбить на подшаги
        # TODO: Более сложная логика разбиения

        return plan

    def get_status(self) -> dict[str, Any]:
        """Получить статус агента."""
        status = {
            "initialized": self._initialized,
            "dry_run": self.dry_run,
            "max_adjustments": self.max_adjustments,
        }

        if self._current_plan:
            status["current_plan"] = {
                "goal": self._current_plan.goal,
                "progress": self._current_plan.progress,
                "steps_total": len(self._current_plan.steps),
                "steps_completed": sum(
                    1
                    for s in self._current_plan.steps
                    if s.status == StepStatus.COMPLETED
                ),
                "adjustments": self._current_plan.adjustments,
            }

        if self._skill_registry:
            status["skills_count"] = len(self._skill_registry.skills)

        return status

    def get_current_plan(self) -> Plan | None:
        """Получить текущий план."""
        return self._current_plan

    def _ensure_initialized(self) -> None:
        """Проверка инициализации."""
        if not self._initialized:
            raise RuntimeError(
                "AutonomousAgent not initialized. Call `await agent.initialize()` first."
            )


# Convenience function
async def create_autonomous_agent(
    project_root: str | Path | None = None,
    dry_run: bool = True,
) -> AutonomousAgent:
    """
    Создать и инициализировать автономного агента.

    Args:
        project_root: Корневая директория проекта
        dry_run: Режим симуляции

    Returns:
        Инициализированный агент
    """
    agent = AutonomousAgent(dry_run=dry_run)
    await agent.initialize(project_root)
    return agent
