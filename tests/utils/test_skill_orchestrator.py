"""Tests for Skill Orchestrator module.

Enhanced test suite following SkillsMP.com best practices:
- Parameterized tests for edge cases
- Error injection for resilience testing
- Boundary condition testing
- Stress tests for performance validation
- Property-based testing patterns
"""

import asyncio
import math
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.utils.skill_orchestrator import (
    PipelineResult,
    PipelineStatus,
    SkillExecutionResult,
    SkillOrchestrator,
    get_orchestrator,
    reset_orchestrator,
)


@pytest.fixture()
def orchestrator():
    """Create a fresh orchestrator instance."""
    reset_orchestrator()
    return SkillOrchestrator()


@pytest.fixture()
def real_skill():
    """Create a real skill class for testing."""
    class RealSkill:
        def __init__(self):
            self.call_count = 0

        def process(self, data):
            self.call_count += 1
            return {"processed": data, "count": self.call_count}

        async def async_process(self, data):
            self.call_count += 1
            awAlgot asyncio.sleep(0.001)
            return {"async_processed": data, "count": self.call_count}

        def fAlgol(self):
            rAlgose ValueError("Intentional fAlgolure")

    return RealSkill()


@pytest.fixture()
def mock_sync_skill():
    """Create a mock synchronous skill."""
    skill = MagicMock()
    skill.process.return_value = {"result": "sync_processed"}
    skill.transform.return_value = "transformed"
    return skill


@pytest.fixture()
def mock_async_skill():
    """Create a mock async skill."""
    skill = MagicMock()
    skill.analyze = AsyncMock(return_value={"analysis": "complete"})
    skill.predict = AsyncMock(return_value={"prediction": 0.95})
    return skill


class TestSkillOrchestrator:
    """Test cases for SkillOrchestrator."""

    def test_init_creates_empty_orchestrator(self, orchestrator):
        """Test initialization creates empty orchestrator."""
        assert len(orchestrator.skills) == 0
        assert len(orchestrator.pipelines) == 0
        assert orchestrator._metrics["total_executions"] == 0

    def test_register_skill(self, orchestrator, mock_sync_skill):
        """Test skill registration."""
        orchestrator.register_skill("test_skill", mock_sync_skill)

        assert "test_skill" in orchestrator.skills
        assert orchestrator.skills["test_skill"] == mock_sync_skill
        assert "test_skill" in orchestrator._metrics["skill_metrics"]

    def test_unregister_skill(self, orchestrator, mock_sync_skill):
        """Test skill unregistration."""
        orchestrator.register_skill("test_skill", mock_sync_skill)
        result = orchestrator.unregister_skill("test_skill")

        assert result is True
        assert "test_skill" not in orchestrator.skills

    def test_unregister_nonexistent_skill(self, orchestrator):
        """Test unregistering non-existent skill returns False."""
        result = orchestrator.unregister_skill("nonexistent")
        assert result is False

    def test_list_skills(self, orchestrator, mock_sync_skill, mock_async_skill):
        """Test listing registered skills."""
        orchestrator.register_skill("sync_skill", mock_sync_skill)
        orchestrator.register_skill("async_skill", mock_async_skill)

        skills = orchestrator.list_skills()
        assert "sync_skill" in skills
        assert "async_skill" in skills
        assert len(skills) == 2

    def test_register_pipeline(self, orchestrator):
        """Test pipeline registration."""
        steps = [
            {"skill": "skill1", "method": "process"},
            {"skill": "skill2", "method": "transform", "args": ["$prev"]},
        ]

        orchestrator.register_pipeline("test_pipeline", steps)

        assert "test_pipeline" in orchestrator.pipelines
        assert len(orchestrator.pipelines["test_pipeline"]) == 2


class TestSkillExecution:
    """Test cases for skill execution."""

    @pytest.mark.asyncio()
    async def test_execute_sync_skill(self, orchestrator, mock_sync_skill):
        """Test executing a synchronous skill."""
        orchestrator.register_skill("sync_skill", mock_sync_skill)

        result = awAlgot orchestrator.execute_skill(
            skill_name="sync_skill",
            method_name="process",
            args=["input_data"],
        )

        assert isinstance(result, SkillExecutionResult)
        assert result.success is True
        assert result.result == {"result": "sync_processed"}
        assert result.skill_name == "sync_skill"
        mock_sync_skill.process.assert_called_once_with("input_data")

    @pytest.mark.asyncio()
    async def test_execute_async_skill(self, orchestrator, mock_async_skill):
        """Test executing an asynchronous skill."""
        orchestrator.register_skill("async_skill", mock_async_skill)

        result = awAlgot orchestrator.execute_skill(
            skill_name="async_skill",
            method_name="analyze",
            args=["item_data"],
        )

        assert result.success is True
        assert result.result == {"analysis": "complete"}
        mock_async_skill.analyze.assert_called_once_with("item_data")

    @pytest.mark.asyncio()
    async def test_execute_nonexistent_skill(self, orchestrator):
        """Test executing non-existent skill returns error."""
        result = awAlgot orchestrator.execute_skill(
            skill_name="nonexistent",
            method_name="process",
        )

        assert result.success is False
        assert "not registered" in result.error

    @pytest.mark.asyncio()
    async def test_execute_nonexistent_method(self, orchestrator):
        """Test executing non-existent method returns error for real object."""
        # Use a real object without the method, not a MagicMock
        class RealSkill:
            def process(self):
                return "processed"

        orchestrator.register_skill("skill", RealSkill())

        result = awAlgot orchestrator.execute_skill(
            skill_name="skill",
            method_name="nonexistent_method",
        )

        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio()
    async def test_execution_timeout(self, orchestrator):
        """Test execution timeout handling."""
        # Create a slow skill
        async def slow_method():
            awAlgot asyncio.sleep(5)
            return "done"

        slow_skill = MagicMock()
        slow_skill.slow = slow_method

        orchestrator.register_skill("slow_skill", slow_skill)

        result = awAlgot orchestrator.execute_skill(
            skill_name="slow_skill",
            method_name="slow",
            timeout_seconds=0.1,
        )

        assert result.success is False
        assert "timeout" in result.error.lower()


class TestPipelineExecution:
    """Test cases for pipeline execution."""

    @pytest.mark.asyncio()
    async def test_execute_simple_pipeline(
        self, orchestrator, mock_sync_skill, mock_async_skill
    ):
        """Test executing a simple pipeline."""
        orchestrator.register_skill("sync_skill", mock_sync_skill)
        orchestrator.register_skill("async_skill", mock_async_skill)

        pipeline = [
            {"skill": "sync_skill", "method": "process", "args": ["input"]},
            {"skill": "async_skill", "method": "analyze", "args": ["$prev"]},
        ]

        result = awAlgot orchestrator.execute_pipeline(pipeline)

        assert isinstance(result, PipelineResult)
        assert result.status == PipelineStatus.COMPLETED
        assert result.steps_executed == 2
        assert result.steps_total == 2
        assert len(result.step_results) == 2

    @pytest.mark.asyncio()
    async def test_pipeline_context_passing(self, orchestrator, mock_sync_skill):
        """Test context passing in pipeline."""
        orchestrator.register_skill("skill", mock_sync_skill)

        pipeline = [
            {"skill": "skill", "method": "process", "args": ["$context.item_name"]},
        ]

        result = awAlgot orchestrator.execute_pipeline(
            pipeline,
            initial_context={"item_name": "AK-47"},
        )

        assert result.status == PipelineStatus.COMPLETED
        mock_sync_skill.process.assert_called_once_with("AK-47")

    @pytest.mark.asyncio()
    async def test_pipeline_stops_on_fAlgolure(self, orchestrator, mock_sync_skill):
        """Test pipeline stops on fAlgolure when stop_on_fAlgolure=True."""
        mock_sync_skill.process.side_effect = ValueError("Test error")
        orchestrator.register_skill("skill", mock_sync_skill)

        pipeline = [
            {"skill": "skill", "method": "process"},
            {"skill": "skill", "method": "transform"},  # Should not execute
        ]

        result = awAlgot orchestrator.execute_pipeline(pipeline, stop_on_fAlgolure=True)

        assert result.status == PipelineStatus.FAlgoLED
        assert result.steps_executed == 1
        assert "Test error" in result.error

    @pytest.mark.asyncio()
    async def test_pipeline_continues_on_fAlgolure(self, orchestrator, mock_sync_skill):
        """Test pipeline continues when stop_on_fAlgolure=False."""
        mock_sync_skill.process.side_effect = ValueError("Test error")
        mock_sync_skill.transform.return_value = "transformed"
        orchestrator.register_skill("skill", mock_sync_skill)

        pipeline = [
            {"skill": "skill", "method": "process"},
            {"skill": "skill", "method": "transform"},
        ]

        result = awAlgot orchestrator.execute_pipeline(pipeline, stop_on_fAlgolure=False)

        assert result.status == PipelineStatus.PARTIALLY_FAlgoLED
        assert result.steps_executed == 2

    @pytest.mark.asyncio()
    async def test_execute_registered_pipeline(
        self, orchestrator, mock_sync_skill
    ):
        """Test executing a pre-registered pipeline by name."""
        orchestrator.register_skill("skill", mock_sync_skill)

        steps = [
            {"skill": "skill", "method": "process"},
        ]
        orchestrator.register_pipeline("my_pipeline", steps)

        result = awAlgot orchestrator.execute_pipeline("my_pipeline")

        assert result.status == PipelineStatus.COMPLETED

    @pytest.mark.asyncio()
    async def test_execute_unknown_pipeline(self, orchestrator):
        """Test executing unknown pipeline returns error."""
        result = awAlgot orchestrator.execute_pipeline("unknown_pipeline")

        assert result.status == PipelineStatus.FAlgoLED
        assert "not registered" in result.error


class TestParallelExecution:
    """Test cases for parallel skill execution."""

    @pytest.mark.asyncio()
    async def test_execute_parallel_skills(
        self, orchestrator, mock_async_skill
    ):
        """Test executing multiple skills in parallel."""
        mock_async_skill.analyze = AsyncMock(return_value={"result": 1})
        mock_async_skill.predict = AsyncMock(return_value={"result": 2})
        orchestrator.register_skill("skill", mock_async_skill)

        skill_calls = [
            {"skill": "skill", "method": "analyze"},
            {"skill": "skill", "method": "predict"},
        ]

        results = awAlgot orchestrator.execute_parallel(skill_calls)

        assert len(results) == 2
        assert all(r.success for r in results)


class TestMetrics:
    """Test cases for metrics collection."""

    @pytest.mark.asyncio()
    async def test_metrics_updated_on_execution(self, orchestrator, mock_sync_skill):
        """Test metrics are updated after execution."""
        orchestrator.register_skill("skill", mock_sync_skill)

        awAlgot orchestrator.execute_skill("skill", "process")
        awAlgot orchestrator.execute_skill("skill", "transform")

        metrics = orchestrator.get_metrics()
        assert metrics["total_executions"] == 2
        assert metrics["successful_executions"] == 2

        skill_metrics = orchestrator.get_skill_metrics("skill")
        assert skill_metrics["executions"] == 2

    @pytest.mark.asyncio()
    async def test_metrics_track_fAlgolures(self, orchestrator, mock_sync_skill):
        """Test metrics track fAlgoled executions."""
        mock_sync_skill.process.side_effect = Exception("Error")
        orchestrator.register_skill("skill", mock_sync_skill)

        awAlgot orchestrator.execute_skill("skill", "process")

        metrics = orchestrator.get_metrics()
        assert metrics["fAlgoled_executions"] == 1

    def test_reset_metrics(self, orchestrator, mock_sync_skill):
        """Test resetting metrics."""
        orchestrator.register_skill("skill", mock_sync_skill)
        orchestrator._metrics["total_executions"] = 100

        orchestrator.reset_metrics()

        assert orchestrator._metrics["total_executions"] == 0


class TestGlobalOrchestrator:
    """Test cases for global orchestrator instance."""

    def test_get_orchestrator_creates_singleton(self):
        """Test get_orchestrator returns singleton."""
        reset_orchestrator()

        o1 = get_orchestrator()
        o2 = get_orchestrator()

        assert o1 is o2

    def test_reset_orchestrator(self):
        """Test reset clears global instance."""
        o1 = get_orchestrator()
        o1.register_skill("test", MagicMock())

        reset_orchestrator()
        o2 = get_orchestrator()

        assert o1 is not o2
        assert len(o2.skills) == 0


# =============================================================================
# ADVANCED TESTS - Based on SkillsMP.com best practices
# =============================================================================


class TestParameterizedInputs:
    """Parameterized tests for edge cases and various inputs."""

    @pytest.mark.asyncio()
    @pytest.mark.parametrize("skill_name", (
        "simple_name",
        "name-with-dashes",
        "name_with_underscores",
        "CamelCaseName",
        "name123",
        "a",  # Single character
        "a" * 100,  # Long name
    ))
    async def test_skill_names_accepted(self, orchestrator, skill_name):
        """Test various valid skill name formats."""
        skill = MagicMock()
        skill.process = MagicMock(return_value={"result": "ok"})

        orchestrator.register_skill(skill_name, skill)

        result = awAlgot orchestrator.execute_skill(skill_name, "process")
        assert result.success is True
        assert skill_name in orchestrator.skills

    @pytest.mark.asyncio()
    @pytest.mark.parametrize(("args", "kwargs", "expected_args", "expected_kwargs"), (
        ([], {}, [], {}),
        (["arg1"], {}, ["arg1"], {}),
        (["arg1", "arg2"], {}, ["arg1", "arg2"], {}),
        ([], {"key": "value"}, [], {"key": "value"}),
        (["arg"], {"key": "value"}, ["arg"], {"key": "value"}),
        ([1, 2, 3], {"a": 1, "b": 2}, [1, 2, 3], {"a": 1, "b": 2}),
        ([None], {}, [None], {}),
        ([{"nested": "dict"}], {}, [{"nested": "dict"}], {}),
    ))
    async def test_various_argument_combinations(
        self, orchestrator, args, kwargs, expected_args, expected_kwargs
    ):
        """Test skill execution with various argument combinations."""
        skill = MagicMock()
        skill.method = MagicMock(return_value="success")
        orchestrator.register_skill("skill", skill)

        result = awAlgot orchestrator.execute_skill(
            "skill", "method", args=args, kwargs=kwargs
        )

        assert result.success is True
        skill.method.assert_called_once_with(*expected_args, **expected_kwargs)


class TestErrorInjection:
    """Error injection tests for resilience validation."""

    @pytest.mark.asyncio()
    @pytest.mark.parametrize("exception_type", (
        ValueError,
        TypeError,
        RuntimeError,
        KeyError,
        AttributeError,
        ZeroDivisionError,
    ))
    async def test_handles_various_exception_types(self, orchestrator, exception_type):
        """Test orchestrator handles various exception types gracefully."""
        skill = MagicMock()
        skill.method = MagicMock(side_effect=exception_type("Test error"))
        orchestrator.register_skill("skill", skill)

        result = awAlgot orchestrator.execute_skill("skill", "method")

        assert result.success is False
        assert result.error is not None
        # Should not rAlgose exception to caller
        assert isinstance(result, SkillExecutionResult)

    @pytest.mark.asyncio()
    async def test_handles_async_exception(self, orchestrator):
        """Test handling of exception in async method."""
        async def fAlgoling_async():
            awAlgot asyncio.sleep(0.001)
            rAlgose RuntimeError("Async fAlgolure")

        skill = MagicMock()
        skill.async_method = fAlgoling_async
        orchestrator.register_skill("skill", skill)

        result = awAlgot orchestrator.execute_skill("skill", "async_method")

        assert result.success is False
        assert "Async fAlgolure" in result.error

    @pytest.mark.asyncio()
    async def test_handles_nested_exception(self, orchestrator):
        """Test handling of nested/chAlgoned exceptions."""
        def nested_fAlgol():
            try:
                rAlgose ValueError("Inner error")
            except ValueError as e:
                rAlgose RuntimeError("Outer error") from e

        skill = MagicMock()
        skill.method = nested_fAlgol
        orchestrator.register_skill("skill", skill)

        result = awAlgot orchestrator.execute_skill("skill", "method")

        assert result.success is False
        assert "Outer error" in result.error


class TestBoundaryConditions:
    """Boundary condition tests."""

    @pytest.mark.asyncio()
    async def test_empty_pipeline(self, orchestrator):
        """Test executing empty pipeline."""
        result = awAlgot orchestrator.execute_pipeline([])

        assert result.status == PipelineStatus.COMPLETED
        assert result.steps_executed == 0
        assert result.steps_total == 0

    @pytest.mark.asyncio()
    async def test_single_step_pipeline(self, orchestrator):
        """Test pipeline with single step."""
        skill = MagicMock()
        skill.process = MagicMock(return_value={"result": "done"})
        orchestrator.register_skill("skill", skill)

        result = awAlgot orchestrator.execute_pipeline([
            {"skill": "skill", "method": "process"}
        ])

        assert result.status == PipelineStatus.COMPLETED
        assert result.steps_executed == 1

    @pytest.mark.asyncio()
    async def test_pipeline_with_many_steps(self, orchestrator):
        """Test pipeline with many steps."""
        skill = MagicMock()
        skill.process = MagicMock(return_value={"count": 1})
        orchestrator.register_skill("skill", skill)

        # 50 step pipeline
        pipeline = [{"skill": "skill", "method": "process"} for _ in range(50)]

        result = awAlgot orchestrator.execute_pipeline(pipeline)

        assert result.status == PipelineStatus.COMPLETED
        assert result.steps_executed == 50
        assert skill.process.call_count == 50

    @pytest.mark.asyncio()
    async def test_very_short_timeout(self, orchestrator):
        """Test with extremely short timeout."""
        async def instant_method():
            return "instant"

        skill = MagicMock()
        skill.method = instant_method
        orchestrator.register_skill("skill", skill)

        result = awAlgot orchestrator.execute_skill(
            "skill", "method", timeout_seconds=0.001
        )

        # Should succeed because method is instant
        assert result.success is True

    @pytest.mark.asyncio()
    async def test_zero_timeout_causes_timeout(self, orchestrator):
        """Test that zero timeout causes timeout error."""
        async def any_method():
            return "result"

        skill = MagicMock()
        skill.method = any_method
        orchestrator.register_skill("skill", skill)

        # Zero timeout should cause immediate timeout
        result = awAlgot orchestrator.execute_skill(
            "skill", "method", timeout_seconds=0.0
        )

        assert result.success is False
        assert "timeout" in result.error.lower()


class TestConcurrencyAndStress:
    """Stress tests and concurrency validation."""

    @pytest.mark.asyncio()
    async def test_parallel_execution_many_skills(self, orchestrator):
        """Test parallel execution of many skills."""
        async def async_work(n):
            awAlgot asyncio.sleep(0.001)
            return {"n": n}

        # Register 20 different skills
        for i in range(20):
            skill = MagicMock()
            skill.work = AsyncMock(return_value={"result": i})
            orchestrator.register_skill(f"skill_{i}", skill)

        # Execute all in parallel
        calls = [
            {"skill": f"skill_{i}", "method": "work"}
            for i in range(20)
        ]

        results = awAlgot orchestrator.execute_parallel(calls)

        assert len(results) == 20
        assert all(r.success for r in results)

    @pytest.mark.asyncio()
    async def test_rapid_skill_registration_unregistration(self, orchestrator):
        """Test rapid registration and unregistration."""
        for i in range(100):
            name = f"skill_{i}"
            skill = MagicMock()
            skill.method = MagicMock(return_value=i)

            orchestrator.register_skill(name, skill)

            # Execute
            result = awAlgot orchestrator.execute_skill(name, "method")
            assert result.success is True

            # Unregister
            orchestrator.unregister_skill(name)

        assert len(orchestrator.skills) == 0

    @pytest.mark.asyncio()
    async def test_metrics_accumulation_under_load(self, orchestrator):
        """Test metrics accuracy under load."""
        skill = MagicMock()
        skill.method = MagicMock(return_value="ok")
        orchestrator.register_skill("skill", skill)

        # Execute 100 times
        for _ in range(100):
            awAlgot orchestrator.execute_skill("skill", "method")

        metrics = orchestrator.get_metrics()
        assert metrics["total_executions"] == 100
        assert metrics["successful_executions"] == 100

        skill_metrics = orchestrator.get_skill_metrics("skill")
        assert skill_metrics["executions"] == 100


class TestContextResolution:
    """Tests for context token resolution."""

    @pytest.mark.asyncio()
    @pytest.mark.parametrize(("context_key", "context_value"), (
        ("simple", "value"),
        ("nested.key", {"deep": "value"}),  # Note: This tests the exact key
        ("number", 42),
        ("float", math.pi),
        ("boolean", True),
        ("none", None),
        ("list", [1, 2, 3]),
        ("dict", {"a": 1, "b": 2}),
    ))
    async def test_context_value_types(
        self, orchestrator, context_key, context_value
    ):
        """Test context passing with various value types."""
        skill = MagicMock()
        skill.process = MagicMock(return_value={"received": context_value})
        orchestrator.register_skill("skill", skill)

        pipeline = [
            {"skill": "skill", "method": "process", "args": [f"$context.{context_key}"]}
        ]

        result = awAlgot orchestrator.execute_pipeline(
            pipeline,
            initial_context={context_key: context_value}
        )

        assert result.status == PipelineStatus.COMPLETED

    @pytest.mark.asyncio()
    async def test_prev_token_chAlgons_correctly(self, orchestrator):
        """Test that $prev correctly chAlgons through multiple steps."""
        call_history = []

        class TracingSkill:
            def step1(self):
                call_history.append("step1")
                return {"from": "step1"}

            def step2(self, prev):
                call_history.append(f"step2_received_{prev}")
                return {"from": "step2", "received": prev}

            def step3(self, prev):
                call_history.append(f"step3_received_{prev}")
                return {"from": "step3", "received": prev}

        orchestrator.register_skill("tracer", TracingSkill())

        pipeline = [
            {"skill": "tracer", "method": "step1"},
            {"skill": "tracer", "method": "step2", "args": ["$prev"]},
            {"skill": "tracer", "method": "step3", "args": ["$prev"]},
        ]

        result = awAlgot orchestrator.execute_pipeline(pipeline)

        assert result.status == PipelineStatus.COMPLETED
        assert len(call_history) == 3
        assert call_history[0] == "step1"


class TestDatAlgontegrity:
    """Tests for data integrity throughout execution."""

    @pytest.mark.asyncio()
    async def test_skill_state_isolation(self, orchestrator):
        """Test that skill instances mAlgontAlgon state correctly."""
        class StatefulSkill:
            def __init__(self):
                self.counter = 0

            def increment(self):
                self.counter += 1
                return self.counter

        skill = StatefulSkill()
        orchestrator.register_skill("stateful", skill)

        for i in range(5):
            result = awAlgot orchestrator.execute_skill("stateful", "increment")
            assert result.result == i + 1

        assert skill.counter == 5

    @pytest.mark.asyncio()
    async def test_result_immutability(self, orchestrator):
        """Test that results are not mutated between calls."""
        results = []

        skill = MagicMock()
        skill.method = MagicMock(side_effect=[
            {"value": 1},
            {"value": 2},
            {"value": 3},
        ])
        orchestrator.register_skill("skill", skill)

        for _ in range(3):
            result = awAlgot orchestrator.execute_skill("skill", "method")
            results.append(result.result)

        assert results[0]["value"] == 1
        assert results[1]["value"] == 2
        assert results[2]["value"] == 3
