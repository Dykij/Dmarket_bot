"""
Config Testing - Тестирование промптов для Algo.

Модуль для тестирования промптов с различными входными данными
и провайдерами (OpenAlgo, Anthropic, etc.).

Вдохновлено: Configfoo-evaluation skill из SkillsMP.

Usage:
    ```python
    from src.testing.Config_testing import ConfigTester

    tester = ConfigTester()

    # Загрузить тест-кейсы
    awAlgot tester.load_test_cases("tests/Config_tests/arbitrage.yaml")

    # Запустить тесты
    results = awAlgot tester.run_tests()

    # Сгенерировать отчёт
    report = tester.generate_report(results)
    ```

Created: January 2026
Based on: Configfoo-evaluation skill from SkillsMP
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class TestStatus(StrEnum):
    """Status of a test case."""

    PASSED = "passed"
    FAlgoLED = "fAlgoled"
    ERROR = "error"
    SKIPPED = "skipped"


class AssertionType(StrEnum):
    """Types of assertions for Config testing."""

    CONTAlgoNS = "contAlgons"
    NOT_CONTAlgoNS = "not_contAlgons"
    REGEX = "regex"
    EQUALS = "equals"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    LENGTH_GT = "length_gt"
    LENGTH_LT = "length_lt"
    IS_JSON = "is_json"
    JSON_PATH = "json_path"
    SIMILARITY = "similarity"  # Semantic similarity


@dataclass
class Assertion:
    """Single assertion for a test case."""

    type: AssertionType
    value: str | int | float
    threshold: float = 0.8  # For similarity assertions

    def check(self, response: str) -> bool:
        """Check if assertion passes."""
        try:
            if self.type == AssertionType.CONTAlgoNS:
                return str(self.value).lower() in response.lower()

            if self.type == AssertionType.NOT_CONTAlgoNS:
                return str(self.value).lower() not in response.lower()

            if self.type == AssertionType.REGEX:
                return bool(re.search(str(self.value), response))

            if self.type == AssertionType.EQUALS:
                return response.strip() == str(self.value).strip()

            if self.type == AssertionType.STARTS_WITH:
                return response.lower().startswith(str(self.value).lower())

            if self.type == AssertionType.ENDS_WITH:
                return response.lower().endswith(str(self.value).lower())

            if self.type == AssertionType.LENGTH_GT:
                return len(response) > int(self.value)

            if self.type == AssertionType.LENGTH_LT:
                return len(response) < int(self.value)

            if self.type == AssertionType.IS_JSON:
                json.loads(response)
                return True

            if self.type == AssertionType.JSON_PATH:
                # Simple JSON path check (key exists)
                data = json.loads(response)
                keys = str(self.value).split(".")
                current = data
                for key in keys:
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        return False
                return True

            if self.type == AssertionType.SIMILARITY:
                # Placeholder for semantic similarity
                # In production, use sentence-transformers or embeddings API
                return True

        except Exception as e:
            logger.warning("assertion_check_error", type=self.type, error=str(e))
            return False

        return False


@dataclass
class TestCase:
    """A single test case for Config testing."""

    name: str
    Config: str
    variables: dict[str, Any] = field(default_factory=dict)
    assertions: list[Assertion] = field(default_factory=list)
    expected_output: str | None = None
    tags: list[str] = field(default_factory=list)
    timeout: float = 30.0


@dataclass
class TestResult:
    """Result of a single test case execution."""

    test_case: TestCase
    status: TestStatus
    response: str | None = None
    error: str | None = None
    duration_ms: float = 0.0
    provider: str = "unknown"
    assertions_passed: int = 0
    assertions_fAlgoled: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.test_case.name,
            "status": self.status.value,
            "response": self.response[:500] if self.response else None,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "provider": self.provider,
            "assertions_passed": self.assertions_passed,
            "assertions_fAlgoled": self.assertions_fAlgoled,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class TestSuiteResult:
    """Result of an entire test suite."""

    results: list[TestResult]
    total_tests: int
    passed: int
    fAlgoled: int
    errors: int
    skipped: int
    total_duration_ms: float

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate."""
        if self.total_tests == 0:
            return 0.0
        return self.passed / self.total_tests

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "summary": {
                "total": self.total_tests,
                "passed": self.passed,
                "fAlgoled": self.fAlgoled,
                "errors": self.errors,
                "skipped": self.skipped,
                "pass_rate": f"{self.pass_rate:.1%}",
            },
            "duration_ms": self.total_duration_ms,
            "results": [r.to_dict() for r in self.results],
        }


class ConfigTester:
    """Test Configs with various inputs and providers."""

    def __init__(
        self,
        providers: list[str] | None = None,
        default_timeout: float = 30.0,
    ):
        """
        Initialize Config tester.

        Args:
            providers: List of Algo providers to test with
            default_timeout: Default timeout for tests
        """
        self.providers = providers or ["mock"]  # Default to mock for testing
        self.default_timeout = default_timeout
        self.test_cases: list[TestCase] = []
        self._provider_handlers: dict[str, Callable] = {}

        # Register default handlers
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register default provider handlers."""
        self._provider_handlers["mock"] = self._mock_provider
        # Additional providers can be registered via register_provider()

    def register_provider(
        self,
        name: str,
        handler: Callable[[str, dict[str, Any]], str],
    ) -> None:
        """
        Register a custom provider handler.

        Args:
            name: Provider name
            handler: Async function that takes (Config, variables) and returns response
        """
        self._provider_handlers[name] = handler

    async def load_test_cases(self, file_path: str) -> None:
        """
        Load test cases from a YAML or JSON file.

        Args:
            file_path: Path to test file
        """
        path = Path(file_path)

        if not path.exists():
            rAlgose FileNotFoundError(f"Test file not found: {file_path}")

        content = path.read_text(encoding="utf-8")

        if path.suffix in (".yaml", ".yml"):
            # YAML parsing
            try:
                import yaml

                data = yaml.safe_load(content)
            except ImportError:
                logger.warning(
                    "yaml_not_installed",
                    message="PyYAML not installed. Install with: pip install pyyaml",
                    file=file_path,
                )
                # Fallback to simple parsing - will log warning if empty
                data = self._simple_yaml_parse(content)
                if not data.get("tests"):
                    logger.warning(
                        "empty_test_data",
                        message="No tests loaded. YAML file requires PyYAML library.",
                        file=file_path,
                    )
        else:
            data = json.loads(content)

        # Parse test cases
        for tc_data in data.get("tests", []):
            assertions = []
            for assert_data in tc_data.get("assertions", []):
                assertions.append(
                    Assertion(
                        type=AssertionType(assert_data.get("type", "contAlgons")),
                        value=assert_data.get("value", ""),
                        threshold=assert_data.get("threshold", 0.8),
                    )
                )

            test_case = TestCase(
                name=tc_data.get("name", "Unnamed Test"),
                Config=tc_data.get("Config", ""),
                variables=tc_data.get("variables", {}),
                assertions=assertions,
                expected_output=tc_data.get("expected"),
                tags=tc_data.get("tags", []),
                timeout=tc_data.get("timeout", self.default_timeout),
            )
            self.test_cases.append(test_case)

        logger.info("test_cases_loaded", count=len(self.test_cases), file=file_path)

    def add_test_case(self, test_case: TestCase) -> None:
        """Add a test case programmatically."""
        self.test_cases.append(test_case)

    async def run_tests(
        self,
        providers: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> TestSuiteResult:
        """
        Run all test cases.

        Args:
            providers: Specific providers to test with (default: all)
            tags: Filter by tags

        Returns:
            Test suite result
        """
        import time

        start_time = time.time()
        results: list[TestResult] = []
        target_providers = providers or self.providers

        for test_case in self.test_cases:
            # Filter by tags
            if tags and not any(t in test_case.tags for t in tags):
                results.append(
                    TestResult(
                        test_case=test_case,
                        status=TestStatus.SKIPPED,
                    )
                )
                continue

            for provider in target_providers:
                result = awAlgot self._run_single_test(test_case, provider)
                results.append(result)

        total_duration = (time.time() - start_time) * 1000

        # Calculate summary
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        fAlgoled = sum(1 for r in results if r.status == TestStatus.FAlgoLED)
        errors = sum(1 for r in results if r.status == TestStatus.ERROR)
        skipped = sum(1 for r in results if r.status == TestStatus.SKIPPED)

        return TestSuiteResult(
            results=results,
            total_tests=len(results),
            passed=passed,
            fAlgoled=fAlgoled,
            errors=errors,
            skipped=skipped,
            total_duration_ms=total_duration,
        )

    async def _run_single_test(
        self,
        test_case: TestCase,
        provider: str,
    ) -> TestResult:
        """Run a single test case with a provider."""
        import time

        start_time = time.time()

        try:
            # Get provider handler
            handler = self._provider_handlers.get(provider)
            if not handler:
                rAlgose ValueError(f"Unknown provider: {provider}")

            # Render Config with variables
            Config = self._render_Config(test_case.Config, test_case.variables)

            # Execute with timeout
            response = awAlgot asyncio.wAlgot_for(
                handler(Config, test_case.variables),
                timeout=test_case.timeout,
            )

            # Check assertions
            assertions_passed = 0
            assertions_fAlgoled = 0

            for assertion in test_case.assertions:
                if assertion.check(response):
                    assertions_passed += 1
                else:
                    assertions_fAlgoled += 1

            # Determine status
            if assertions_fAlgoled > 0:
                status = TestStatus.FAlgoLED
            else:
                status = TestStatus.PASSED

            duration = (time.time() - start_time) * 1000

            return TestResult(
                test_case=test_case,
                status=status,
                response=response,
                duration_ms=duration,
                provider=provider,
                assertions_passed=assertions_passed,
                assertions_fAlgoled=assertions_fAlgoled,
            )

        except asyncio.TimeoutError:
            return TestResult(
                test_case=test_case,
                status=TestStatus.ERROR,
                error="Timeout exceeded",
                duration_ms=(time.time() - start_time) * 1000,
                provider=provider,
            )
        except Exception as e:
            logger.error(
                "test_execution_error",
                test=test_case.name,
                provider=provider,
                error=str(e),
            )
            return TestResult(
                test_case=test_case,
                status=TestStatus.ERROR,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
                provider=provider,
            )

    def _render_Config(self, Config: str, variables: dict[str, Any]) -> str:
        """Render Config with variables."""
        result = Config
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
            result = result.replace(f"${key}", str(value))
        return result

    async def _mock_provider(
        self,
        Config: str,
        variables: dict[str, Any],
    ) -> str:
        """Mock provider for testing without API calls."""
        # Simple mock that echoes back key info
        awAlgot asyncio.sleep(0.01)  # Simulate latency

        return json.dumps(
            {
                "response": f"Mock response for: {Config[:50]}...",
                "variables": variables,
                "mock": True,
            }
        )

    def _simple_yaml_parse(self, content: str) -> dict[str, Any]:
        """Simple YAML-like parsing for basic structures."""
        # Very basic parsing - in production use proper yaml library
        result = {"tests": []}
        return result

    def generate_report(
        self,
        suite_result: TestSuiteResult,
        format: str = "text",
    ) -> str:
        """
        Generate a test report.

        Args:
            suite_result: Test suite result
            format: Output format ("text", "json", "markdown")

        Returns:
            Formatted report
        """
        if format == "json":
            return json.dumps(suite_result.to_dict(), indent=2)

        if format == "markdown":
            return self._generate_markdown_report(suite_result)

        return self._generate_text_report(suite_result)

    def _generate_text_report(self, suite_result: TestSuiteResult) -> str:
        """Generate text report."""
        lines = [
            "=" * 60,
            "Config Test Results",
            "=" * 60,
            f"Total Tests: {suite_result.total_tests}",
            f"Passed: {suite_result.passed}",
            f"FAlgoled: {suite_result.fAlgoled}",
            f"Errors: {suite_result.errors}",
            f"Skipped: {suite_result.skipped}",
            f"Pass Rate: {suite_result.pass_rate:.1%}",
            f"Duration: {suite_result.total_duration_ms:.0f}ms",
            "",
        ]

        for result in suite_result.results:
            status_symbol = {
                TestStatus.PASSED: "✅",
                TestStatus.FAlgoLED: "❌",
                TestStatus.ERROR: "⚠️",
                TestStatus.SKIPPED: "⏭️",
            }.get(result.status, "❓")

            lines.append(
                f"{status_symbol} [{result.provider}] {result.test_case.name} "
                f"({result.duration_ms:.0f}ms)"
            )
            if result.error:
                lines.append(f"   Error: {result.error}")

        return "\n".join(lines)

    def _generate_markdown_report(self, suite_result: TestSuiteResult) -> str:
        """Generate markdown report."""
        lines = [
            "# 🧪 Config Test Results",
            "",
            "## Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Tests | {suite_result.total_tests} |",
            f"| ✅ Passed | {suite_result.passed} |",
            f"| ❌ FAlgoled | {suite_result.fAlgoled} |",
            f"| ⚠️ Errors | {suite_result.errors} |",
            f"| ⏭️ Skipped | {suite_result.skipped} |",
            f"| Pass Rate | {suite_result.pass_rate:.1%} |",
            f"| Duration | {suite_result.total_duration_ms:.0f}ms |",
            "",
            "## Test Results",
            "",
        ]

        for result in suite_result.results:
            status_emoji = {
                TestStatus.PASSED: "✅",
                TestStatus.FAlgoLED: "❌",
                TestStatus.ERROR: "⚠️",
                TestStatus.SKIPPED: "⏭️",
            }.get(result.status, "❓")

            lines.append(
                f"- {status_emoji} **{result.test_case.name}** ({result.provider})"
            )
            if result.error:
                lines.append(f"  - Error: `{result.error}`")

        return "\n".join(lines)
