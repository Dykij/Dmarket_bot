"""Tests for skills_test_runner.py.

Tests skill test discovery and execution.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.skills_test_runner import SkillTestRunner


class TestSkillTestRunner:
    """Tests for SkillTestRunner class."""

    @pytest.fixture()
    def temp_skills_dir(self, tmp_path: Path) -> Path:
        """Create temporary skills directory."""
        skills_dir = tmp_path / ".github" / "skills"
        skills_dir.mkdir(parents=True)
        return skills_dir

    def _create_skill_with_tests(
        self,
        skills_dir: Path,
        name: str,
        test_content: str | None = None,
    ) -> Path:
        """Create a test skill with tests directory."""
        skill_dir = skills_dir / name
        tests_dir = skill_dir / "tests"
        tests_dir.mkdir(parents=True)

        # Create SKILL.md
        skill_content = f"---\nname: {name}\nversion: 1.0.0\n---\n\n# {name}\n"
        (skill_dir / "SKILL.md").write_text(skill_content, encoding="utf-8")

        # Create test file
        test_code = (
            test_content
            or """
def test_example():
    assert True
"""
        )
        (tests_dir / "test_example.py").write_text(test_code, encoding="utf-8")

        return skill_dir

    def test_discover_skills_empty(self, temp_skills_dir: Path):
        """Test discovering skills in empty directory."""
        runner = SkillTestRunner(temp_skills_dir)
        skills = runner.discover_skills()

        assert len(skills) == 0

    def test_discover_skills_no_tests(self, temp_skills_dir: Path):
        """Test discovering skills without tests directory."""
        # Create skill without tests
        skill_dir = temp_skills_dir / "skill-no-tests"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: test\n---\n# Test")

        runner = SkillTestRunner(temp_skills_dir)
        skills = runner.discover_skills()

        assert len(skills) == 0

    def test_discover_skills_with_tests(self, temp_skills_dir: Path):
        """Test discovering skills with tests."""
        self._create_skill_with_tests(temp_skills_dir, "skill-a")
        self._create_skill_with_tests(temp_skills_dir, "skill-b")

        runner = SkillTestRunner(temp_skills_dir)
        skills = runner.discover_skills()

        assert len(skills) == 2

    @patch("scripts.skills_test_runner.subprocess.run")
    def test_run_tests_success(self, mock_run: MagicMock, temp_skills_dir: Path):
        """Test running tests successfully."""
        skill_dir = self._create_skill_with_tests(temp_skills_dir, "skill-a")

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="1 PASSED\n",
            stderr="",
        )

        runner = SkillTestRunner(temp_skills_dir)
        result = runner.run_tests(skill_dir)

        assert result["skill"] == "skill-a"
        assert result["exit_code"] == 0
        assert result["passed"] >= 1

    @patch("scripts.skills_test_runner.subprocess.run")
    def test_run_tests_failure(self, mock_run: MagicMock, temp_skills_dir: Path):
        """Test running tests with failures."""
        skill_dir = self._create_skill_with_tests(temp_skills_dir, "skill-b")

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="2 PASSED 1 FAlgoLED\n",
            stderr="",
        )

        runner = SkillTestRunner(temp_skills_dir)
        result = runner.run_tests(skill_dir)

        assert result["skill"] == "skill-b"
        assert result["exit_code"] == 1
        assert result["failed"] >= 1

    @patch("scripts.skills_test_runner.subprocess.run")
    def test_run_tests_timeout(self, mock_run: MagicMock, temp_skills_dir: Path):
        """Test running tests with timeout."""
        from subprocess import TimeoutExpired

        skill_dir = self._create_skill_with_tests(temp_skills_dir, "skill-c")

        mock_run.side_effect = TimeoutExpired(cmd="pytest", timeout=60)

        runner = SkillTestRunner(temp_skills_dir)
        result = runner.run_tests(skill_dir)

        assert result["skill"] == "skill-c"
        assert result["exit_code"] == -1
        assert "timeout" in result["errors"].lower()

    @patch("scripts.skills_test_runner.subprocess.run")
    def test_run_all_tests(self, mock_run: MagicMock, temp_skills_dir: Path):
        """Test running all tests."""
        self._create_skill_with_tests(temp_skills_dir, "skill-a")
        self._create_skill_with_tests(temp_skills_dir, "skill-b")

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="1 PASSED\n",
            stderr="",
        )

        runner = SkillTestRunner(temp_skills_dir)
        passed, failed, _skipped = runner.run_all_tests()

        assert passed >= 2
        assert failed == 0

    def test_generate_report(self, temp_skills_dir: Path):
        """Test generating JSON report."""
        runner = SkillTestRunner(temp_skills_dir)
        runner.results = {
            "skill-a": {
                "skill": "skill-a",
                "passed": 5,
                "failed": 0,
                "skipped": 1,
                "exit_code": 0,
            }
        }

        report_path = temp_skills_dir / "test-report.json"
        runner.generate_report(report_path)

        assert report_path.exists()
        import json

        with open(report_path, encoding="utf-8") as f:
            data = json.load(f)

        assert "skill-a" in data
        assert data["skill-a"]["passed"] == 5


class TestSkillTestRunnerCLI:
    """Tests for CLI functionality."""

    def test_main_import(self):
        """Test that main function is importable."""
        from scripts.skills_test_runner import main

        assert callable(main)
