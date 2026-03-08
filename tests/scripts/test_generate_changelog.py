#!/usr/bin/env python3
"""
Тесты для генератора CHANGELOG.
"""

from unittest.mock import MagicMock, patch

import pytest

from scripts.generate_changelog import ChangelogGenerator


class TestChangelogGenerator:
    """Тесты для ChangelogGenerator."""

    def test_parse_conventional_commit(self):
        """Тест парсинга Conventional Commits."""
        generator = ChangelogGenerator()

        commit_line = "abc1234|2025-12-14 10:00:00 +0000|feat(api): add new endpoint"
        result = generator.parse_commit(commit_line)

        assert result is not None
        assert result["hash"] == "abc1234"
        assert result["type"] == "feat"
        assert result["scope"] == "api"
        assert result["message"] == "add new endpoint"

    def test_parse_commit_without_scope(self):
        """Тест парсинга коммита без scope."""
        generator = ChangelogGenerator()

        commit_line = "abc1234|2025-12-14 10:00:00 +0000|fix: resolve bug"
        result = generator.parse_commit(commit_line)

        assert result is not None
        assert result["type"] == "fix"
        assert result["scope"] is None
        assert result["message"] == "resolve bug"

    def test_parse_non_conventional_commit(self):
        """Тест парсинга обычного коммита."""
        generator = ChangelogGenerator()

        commit_line = "abc1234|2025-12-14 10:00:00 +0000|Update README"
        result = generator.parse_commit(commit_line)

        assert result is not None
        assert result["type"] == "chore"
        assert result["message"] == "Update README"

    def test_format_change_with_scope(self):
        """Тест форматирования изменения со scope."""
        generator = ChangelogGenerator()

        commit = {
            "hash": "abc1234",
            "scope": "api",
            "message": "add new endpoint",
        }

        result = generator.format_change(commit)
        assert "**api**:" in result
        assert "add new endpoint" in result
        assert "abc1234" in result

    def test_format_change_without_scope(self):
        """Тест форматирования изменения без scope."""
        generator = ChangelogGenerator()

        commit = {
            "hash": "abc1234",
            "scope": None,
            "message": "fix critical bug",
        }

        result = generator.format_change(commit)
        assert "**" not in result.split(":")[0]
        assert "fix critical bug" in result

    @patch("subprocess.run")
    def test_get_commits(self, mock_run):
        """Тест получения коммитов из git."""
        mock_run.return_value = MagicMock(
            stdout="abc1234|2025-12-14 10:00:00|feat: test\ndef5678|2025-12-13 09:00:00|fix: bug",
            returncode=0,
        )

        generator = ChangelogGenerator()
        commits = generator.get_commits()

        assert len(commits) == 2
        assert "feat: test" in commits[0]
        assert "fix: bug" in commits[1]

    @patch("subprocess.run")
    def test_get_commits_with_since(self, mock_run):
        """Тест получения коммитов с указанием ref."""
        mock_run.return_value = MagicMock(
            stdout="abc1234|2025-12-14 10:00:00|feat: test",
            returncode=0,
        )

        generator = ChangelogGenerator(since="v1.0.0")
        generator.get_commits()

        # Проверяем что команда содержит диапазон
        call_args = mock_run.call_args[0][0]
        assert "v1.0.0..HEAD" in call_args

    def test_categorize_commits(self):
        """Тест категоризации коммитов."""
        generator = ChangelogGenerator()

        with patch.object(generator, "get_commits") as mock_get:
            mock_get.return_value = [
                "abc1234|2025-12-14 10:00:00|feat: new feature",
                "def5678|2025-12-14 09:00:00|fix: bug fix",
                "ghi9012|2025-12-14 08:00:00|docs: update docs",
            ]

            generator.categorize_commits()

            assert "Added" in generator.changes
            assert "Fixed" in generator.changes
            assert "Documentation" in generator.changes
            assert len(generator.changes["Added"]) == 1
            assert len(generator.changes["Fixed"]) == 1

    def test_generate_changelog_structure(self):
        """Тест структуры сгенерированного CHANGELOG."""
        generator = ChangelogGenerator()

        with patch.object(generator, "get_commits") as mock_get:
            mock_get.return_value = [
                "abc1234|2025-12-14 10:00:00|feat(api): add endpoint"
            ]

            changelog = generator.generate()

            assert "# Changelog" in changelog
            assert "## [Unreleased]" in changelog
            assert "### Added" in changelog
            assert "add endpoint" in changelog

    def test_generate_empty_changelog(self):
        """Тест генерации пустого CHANGELOG."""
        generator = ChangelogGenerator()

        with patch.object(generator, "get_commits") as mock_get:
            mock_get.return_value = []

            changelog = generator.generate()

            assert "No changes found" in changelog

    @pytest.mark.parametrize(
        ("commit_type", "expected_category"),
        (
            ("feat", "Added"),
            ("fix", "Fixed"),
            ("docs", "Documentation"),
            ("refactor", "Changed"),
            ("perf", "Performance"),
            ("test", "Tests"),
            ("chore", "Chores"),
        ),
    )
    def test_commit_type_mapping(self, commit_type, expected_category):
        """Тест маппинга типов коммитов на категории."""
        assert ChangelogGenerator.COMMIT_TYPES[commit_type] == expected_category
