"""Smoke tests for CI/CD pipeline validation.

These tests verify that basic functionality works correctly
and help identify environment setup issues in CI/CD.
"""

import sys
from pathlib import Path


class TestEnvironmentSetup:
    """Тесты проверки окружения CI/CD."""

    def test_python_version_is_3_11_or_higher(self):
        """Тест проверяет что используется Python 3.11+."""
        # Arrange
        required_version = (3, 11)

        # Act
        actual_version = sys.version_info

        # Assert
        assert (
            actual_version >= required_version
        ), f"Python 3.11+ required, got {actual_version}"

    def test_essential_project_directories_exist(self):
        """Тест проверяет наличие всех необходимых директорий проекта."""
        # Arrange
        project_root = Path(__file__).parent.parent
        essential_dirs = [
            project_root / "src",
            project_root / "src" / "dmarket",
            project_root / "src" / "telegram_bot",
            project_root / "src" / "utils",
            project_root / "tests",
        ]

        # Act & Assert
        for directory in essential_dirs:
            assert directory.exists(), f"Missing essential directory: {directory}"


class TestModuleImports:
    """Тесты проверки доступности импортов модулей."""

    def test_core_modules_import_successfully(self):
        """Тест проверяет успешный импорт всех основных модулей."""
        # Arrange & Act & Assert
        try:
            import src  # noqa: F401
            import src.dmarket  # noqa: F401
            import src.telegram_bot  # noqa: F401
            import src.utils  # noqa: F401
        except ImportError as e:
            raise AssertionError(f"Import failed: {e}") from e


class TestProjectConfiguration:
    """Тесты проверки конфигурационных файлов проекта."""

    def test_env_example_file_exists_in_project_root(self):
        """Тест проверяет наличие файла .env.example."""
        # Arrange
        project_root = Path(__file__).parent.parent
        env_example = project_root / ".env.example"

        # Act
        file_exists = env_example.exists()

        # Assert
        assert file_exists, ".env.example file is missing"

    def test_requirements_file_exists_in_project_root(self):
        """Тест проверяет наличие файла requirements.txt."""
        # Arrange
        project_root = Path(__file__).parent.parent
        requirements = project_root / "requirements.txt"

        # Act
        file_exists = requirements.exists()

        # Assert
        assert file_exists, "requirements.txt file is missing"


class TestPytestSanity:
    """Базовые проверки работоспособности pytest."""

    def test_basic_arithmetic_operations_work_correctly(self):
        """Тест проверяет корректность базовых арифметических операций."""
        # Arrange & Act & Assert
        assert 1 + 1 == 2
        assert 2 * 3 == 6
        assert 10 / 2 == 5

    def test_string_operations_work_correctly(self):
        """Тест проверяет корректность базовых операций со строками."""
        # Arrange
        test_string = "DMarket Bot"

        # Act & Assert
        assert "Bot" in test_string
        assert test_string.lower() == "dmarket bot"
        assert len(test_string) > 0
