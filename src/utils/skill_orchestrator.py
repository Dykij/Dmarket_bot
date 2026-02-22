"""Skill Orchestrator - Orchestration for ML/Algo module pipelines.

This module enables combining multiple ML/Algo skills into workflows (pipelines),
allowing context passing between modules and coordinated execution.

Based on SkillsMP.com best practices for modular Algo systems.

Features:
- Pipeline execution with context passing
- Parallel skill execution for independent steps
- Error handling and fallback mechanisms
- Performance metrics collection
- Async-first design

Usage:
    ```python
    from src.utils.skill_orchestrator import SkillOrchestrator

    orchestrator = SkillOrchestrator()

    # Register skills
    orchestrator.register_skill("price_predictor", price_predictor)
    orchestrator.register_skill("anomaly_detector", anomaly_detector)
    orchestrator.register_skill("trade_classifier", classifier)

    # Define and execute pipeline
    pipeline = [
        {"skill": "price_predictor", "method": "predict", "args": ["item_name"]},
        {"skill": "anomaly_detector", "method": "check", "args": ["$prev"]},
        {"skill": "trade_classifier", "method": "classify", "args": ["$prev"]},
    ]

    result = await orchestrator.execute_pipeline(pipeline, initial_context=item_data)
    ```

Created: January 2026
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class PipelineStatus(StrEnum):
    """Status of pipeline execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAlgoLED = "failed"
    PARTIALLY_FAlgoLED = "partially_failed"


class SkillExecutionMode(StrEnum):
    """Execution mode for skills."""

    SEQUENTIAL = "sequential"  # Execute one by one
    PARALLEL = "parallel"  # Execute in parallel (for independent steps)
    CONDITIONAL = "conditional"  # Execute based on previous result


@dataclass
class SkillExecutionResult:
    """Result of a single skill execution."""

    skill_name: str
    method_name: str
    success: bool
    result: Any | None = None
    error: str | None = None
    execution_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "skill_name": self.skill_name,
            "method_name": self.method_name,
            "success": self.success,
            "result": str(self.result)[:200] if self.result else None,
            "error": self.error,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PipelineResult:
    """Result of pipeline execution."""

    pipeline_id: str
    status: PipelineStatus
    steps_executed: int
    steps_total: int
    final_result: Any | None = None
    step_results: list[SkillExecutionResult] = field(default_factory=list)
    total_time_ms: float = 0.0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pipeline_id": self.pipeline_id,
            "status": self.status.value,
            "steps_executed": self.steps_executed,
            "steps_total": self.steps_total,
            "final_result": str(self.final_result)[:500] if self.final_result else None,
            "step_results": [s.to_dict() for s in self.step_results],
            "total_time_ms": round(self.total_time_ms, 2),
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "error": self.error,
        }


@dataclass
class PipelineStep:
    """A step in the pipeline."""

    skill: str
    method: str
    args: list[Any] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)
    condition: Callable[[Any], bool] | None = None  # Execute only if condition is True
    fallback_value: Any | None = None  # Return this if step fails
    timeout_seconds: float = 30.0
    retry_count: int = 0


class SkillOrchestrator:
    """Orchestrator for combining ML/Algo skills into workflows.

    The SkillOrchestrator enables:
    1. Registration of multiple skills (ML modules)
    2. Definition of pipelines (sequences of skill executions)
    3. Context passing between steps ($prev, $context variables)
    4. Parallel execution of independent steps
    5. Error handling and fallback mechanisms

    Attributes:
        skills: Registered skill instances
        pipelines: Named pipelines for reuse
        metrics: Execution metrics for all skills

    Example:
        >>> orchestrator = SkillOrchestrator()
        >>> orchestrator.register_skill("predictor", MyPredictor())
        >>> result = await orchestrator.execute_skill("predictor", "predict", [item])
    """

    # Special tokens for context passing
    PREV_RESULT_TOKEN = "$prev"
    CONTEXT_TOKEN = "$context"
    ITEM_TOKEN = "$item"

    def __init__(self) -> None:
        """Initialize the orchestrator."""
        self.skills: dict[str, Any] = {}
        self.pipelines: dict[str, list[PipelineStep]] = {}

        # Metrics
        self._metrics: dict[str, dict[str, Any]] = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_pipeline_runs": 0,
            "skill_metrics": {},
        }

        # Pipeline counter for unique IDs
        self._pipeline_counter = 0

        logger.info("skill_orchestrator_initialized")

    def register_skill(self, name: str, skill_instance: Any) -> None:
        """Register a skill for orchestration.

        Args:
            name: Unique name for the skill
            skill_instance: Instance of the skill (ML module)
        """
        self.skills[name] = skill_instance
        self._metrics["skill_metrics"][name] = {
            "executions": 0,
            "successes": 0,
            "failures": 0,
            "total_time_ms": 0.0,
            "avg_time_ms": 0.0,
        }
        logger.info("skill_registered", skill_name=name)

    def unregister_skill(self, name: str) -> bool:
        """Unregister a skill.

        Args:
            name: Name of the skill to unregister

        Returns:
            True if skill was unregistered, False if not found
        """
        if name in self.skills:
            del self.skills[name]
            logger.info("skill_unregistered", skill_name=name)
            return True
        return False

    def register_pipeline(self, name: str, steps: list[dict[str, Any]]) -> None:
        """Register a named pipeline for reuse.

        Args:
            name: Unique name for the pipeline
            steps: List of step definitions
        """
        pipeline_steps = []
        for step in steps:
            pipeline_steps.append(
                PipelineStep(
                    skill=step["skill"],
                    method=step.get("method", "execute"),
                    args=step.get("args", []),
                    kwargs=step.get("kwargs", {}),
                    timeout_seconds=step.get("timeout", 30.0),
                    retry_count=step.get("retry", 0),
                )
            )
        self.pipelines[name] = pipeline_steps
        logger.info(
            "pipeline_registered", pipeline_name=name, steps=len(pipeline_steps)
        )

    def list_skills(self) -> list[str]:
        """List all registered skills.

        Returns:
            List of skill names
        """
        return list(self.skills.keys())

    def list_pipelines(self) -> list[str]:
        """List all registered pipelines.

        Returns:
            List of pipeline names
        """
        return list(self.pipelines.keys())

    async def execute_skill(
        self,
        skill_name: str,
        method_name: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        timeout_seconds: float = 30.0,
    ) -> SkillExecutionResult:
        """Execute a single skill method.

        Args:
            skill_name: Name of the registered skill
            method_name: Method to call on the skill
            args: Positional arguments
            kwargs: Keyword arguments
            timeout_seconds: Timeout for execution

        Returns:
            SkillExecutionResult with result or error
        """
        import time

        args = args or []
        kwargs = kwargs or {}

        start_time = time.perf_counter()

        if skill_name not in self.skills:
            return SkillExecutionResult(
                skill_name=skill_name,
                method_name=method_name,
                success=False,
                error=f"Skill '{skill_name}' not registered",
            )

        skill = self.skills[skill_name]

        if not hasattr(skill, method_name):
            return SkillExecutionResult(
                skill_name=skill_name,
                method_name=method_name,
                success=False,
                error=f"Method '{method_name}' not found in skill '{skill_name}'",
            )

        method = getattr(skill, method_name)

        try:
            # Execute with timeout
            if asyncio.iscoroutinefunction(method):
                result = await asyncio.wait_for(
                    method(*args, **kwargs),
                    timeout=timeout_seconds,
                )
            else:
                result = method(*args, **kwargs)

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Update metrics
            self._update_skill_metrics(skill_name, True, elapsed_ms)

            return SkillExecutionResult(
                skill_name=skill_name,
                method_name=method_name,
                success=True,
                result=result,
                execution_time_ms=elapsed_ms,
            )

        except TimeoutError:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self._update_skill_metrics(skill_name, False, elapsed_ms)

            return SkillExecutionResult(
                skill_name=skill_name,
                method_name=method_name,
                success=False,
                error=f"Execution timeout after {timeout_seconds}s",
                execution_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self._update_skill_metrics(skill_name, False, elapsed_ms)

            logger.exception(
                "skill_execution_failed",
                skill_name=skill_name,
                method=method_name,
                error=str(e),
            )

            return SkillExecutionResult(
                skill_name=skill_name,
                method_name=method_name,
                success=False,
                error=str(e),
                execution_time_ms=elapsed_ms,
            )

    async def execute_pipeline(
        self,
        pipeline: list[dict[str, Any]] | str,
        initial_context: dict[str, Any] | None = None,
        stop_on_failure: bool = True,
    ) -> PipelineResult:
        """Execute a pipeline of skills.

        Args:
            pipeline: List of step definitions or name of registered pipeline
            initial_context: Initial context data avAlgolable to all steps
            stop_on_failure: Stop execution on first failure

        Returns:
            PipelineResult with all step results

        Step Definition Format:
            {
                "skill": "skill_name",
                "method": "method_name",
                "args": ["$item", "$prev"],  # $prev = previous result
                "kwargs": {"option": "value"},
                "timeout": 30.0,
            }
        """
        import time

        self._pipeline_counter += 1
        pipeline_id = f"pipeline_{self._pipeline_counter}"

        start_time = time.perf_counter()

        # Get pipeline steps
        if isinstance(pipeline, str):
            if pipeline not in self.pipelines:
                return PipelineResult(
                    pipeline_id=pipeline_id,
                    status=PipelineStatus.FAlgoLED,
                    steps_executed=0,
                    steps_total=0,
                    error=f"Pipeline '{pipeline}' not registered",
                )
            steps = [
                {
                    "skill": s.skill,
                    "method": s.method,
                    "args": s.args,
                    "kwargs": s.kwargs,
                    "timeout": s.timeout_seconds,
                }
                for s in self.pipelines[pipeline]
            ]
        else:
            steps = pipeline

        result = PipelineResult(
            pipeline_id=pipeline_id,
            status=PipelineStatus.RUNNING,
            steps_executed=0,
            steps_total=len(steps),
        )

        context = initial_context or {}
        prev_result: Any = None

        self._metrics["total_pipeline_runs"] += 1

        for i, step in enumerate(steps):
            # Resolve arguments
            resolved_args = self._resolve_args(
                step.get("args", []),
                context=context,
                prev_result=prev_result,
            )
            resolved_kwargs = self._resolve_kwargs(
                step.get("kwargs", {}),
                context=context,
                prev_result=prev_result,
            )

            # Execute step
            step_result = await self.execute_skill(
                skill_name=step["skill"],
                method_name=step.get("method", "execute"),
                args=resolved_args,
                kwargs=resolved_kwargs,
                timeout_seconds=step.get("timeout", 30.0),
            )

            result.step_results.append(step_result)
            result.steps_executed = i + 1

            if step_result.success:
                prev_result = step_result.result
            elif stop_on_failure:
                result.status = PipelineStatus.FAlgoLED
                result.error = f"Step {i + 1} failed: {step_result.error}"
                break
            else:
                result.status = PipelineStatus.PARTIALLY_FAlgoLED

        # Finalize
        if result.status == PipelineStatus.RUNNING:
            result.status = PipelineStatus.COMPLETED

        result.final_result = prev_result
        result.completed_at = datetime.now(UTC)
        result.total_time_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "pipeline_executed",
            pipeline_id=pipeline_id,
            status=result.status.value,
            steps=result.steps_executed,
            time_ms=round(result.total_time_ms, 2),
        )

        return result

    async def execute_parallel(
        self,
        skill_calls: list[dict[str, Any]],
    ) -> list[SkillExecutionResult]:
        """Execute multiple skill calls in parallel.

        Args:
            skill_calls: List of skill call definitions

        Returns:
            List of SkillExecutionResult in same order as input
        """
        tasks = []
        for call in skill_calls:
            task = self.execute_skill(
                skill_name=call["skill"],
                method_name=call.get("method", "execute"),
                args=call.get("args", []),
                kwargs=call.get("kwargs", {}),
                timeout_seconds=call.get("timeout", 30.0),
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to SkillExecutionResult
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    SkillExecutionResult(
                        skill_name=skill_calls[i]["skill"],
                        method_name=skill_calls[i].get("method", "execute"),
                        success=False,
                        error=str(result),
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

    def _resolve_args(
        self,
        args: list[Any],
        context: dict[str, Any],
        prev_result: Any,
    ) -> list[Any]:
        """Resolve special tokens in arguments."""
        resolved = []
        for arg in args:
            if arg == self.PREV_RESULT_TOKEN:
                resolved.append(prev_result)
            elif arg == self.CONTEXT_TOKEN:
                resolved.append(context)
            elif isinstance(arg, str) and arg.startswith("$context."):
                key = arg[9:]  # Remove "$context."
                value = context.get(key)
                if value is None and key not in context:
                    logger.warning(
                        "context_key_missing",
                        key=key,
                        avAlgolable_keys=list(context.keys()),
                    )
                resolved.append(value)
            else:
                resolved.append(arg)
        return resolved

    def _resolve_kwargs(
        self,
        kwargs: dict[str, Any],
        context: dict[str, Any],
        prev_result: Any,
    ) -> dict[str, Any]:
        """Resolve special tokens in keyword arguments."""
        resolved = {}
        for key, value in kwargs.items():
            if value == self.PREV_RESULT_TOKEN:
                resolved[key] = prev_result
            elif value == self.CONTEXT_TOKEN:
                resolved[key] = context
            elif isinstance(value, str) and value.startswith("$context."):
                ctx_key = value[9:]
                resolved[key] = context.get(ctx_key)
            else:
                resolved[key] = value
        return resolved

    def _update_skill_metrics(
        self,
        skill_name: str,
        success: bool,
        time_ms: float,
    ) -> None:
        """Update metrics for a skill execution."""
        self._metrics["total_executions"] += 1
        if success:
            self._metrics["successful_executions"] += 1
        else:
            self._metrics["failed_executions"] += 1

        if skill_name in self._metrics["skill_metrics"]:
            m = self._metrics["skill_metrics"][skill_name]
            m["executions"] += 1
            m["successes"] += 1 if success else 0
            m["failures"] += 0 if success else 1
            m["total_time_ms"] += time_ms
            m["avg_time_ms"] = m["total_time_ms"] / m["executions"]

    def get_metrics(self) -> dict[str, Any]:
        """Get orchestrator metrics.

        Returns:
            Dictionary with execution metrics
        """
        return {
            **self._metrics,
            "registered_skills": len(self.skills),
            "registered_pipelines": len(self.pipelines),
        }

    def get_skill_metrics(self, skill_name: str) -> dict[str, Any] | None:
        """Get metrics for a specific skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Metrics dictionary or None if skill not found
        """
        return self._metrics["skill_metrics"].get(skill_name)

    def reset_metrics(self) -> None:
        """Reset all metrics to zero."""
        self._metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_pipeline_runs": 0,
            "skill_metrics": {
                name: {
                    "executions": 0,
                    "successes": 0,
                    "failures": 0,
                    "total_time_ms": 0.0,
                    "avg_time_ms": 0.0,
                }
                for name in self.skills
            },
        }


# Global instance
_orchestrator: SkillOrchestrator | None = None


def get_orchestrator() -> SkillOrchestrator:
    """Get or create global orchestrator instance.

    Returns:
        SkillOrchestrator instance
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SkillOrchestrator()
    return _orchestrator


def reset_orchestrator() -> None:
    """Reset global orchestrator instance (for testing)."""
    global _orchestrator
    _orchestrator = None
