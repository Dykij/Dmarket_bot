#!/usr/bin/env python
"""Запуск модульных тестов для конкретных модулей проекта.

Скрипт позволяет запускать тесты для выбранных модулей или для всего проекта
с использованием модульной структуры тестов.

Примеры использования:
    python scripts/run_module_tests.py --all  # запуск всех тестов
    python scripts/run_module_tests.py --dmarket  # запуск тестов только для dmarket
    python scripts/run_module_tests.py --telegram-bot  # запуск тестов для telegram_bot
    python scripts/run_module_tests.py --utils  # запуск тестов для utils
    python scripts/run_module_tests.py --dmarket --utils  # запуск тестов для dmarket и utils
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def get_project_root() -> Path:
    """Возвращает корневую директорию проекта.

    Returns:
        Путь к корневой директории проекта
    """
    current_file = Path(__file__).resolve()
    return current_file.parent.parent


def run_tests(
    module_paths: list[str],
    verbose: bool = False,
    report: bool = False,
) -> bool:
    """Запускает тесты для указанных модулей.

    Args:
        module_paths: Список путей к директориям с тестами
        verbose: Выводить подробную информацию
        report: Генерировать отчет о покрытии

    Returns:
        True, если все тесты успешно пSwarmдены, иначе False
    """
    project_root = get_project_root()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)

    cmd = ["pytest"]

    if verbose:
        cmd.append("-v")

    if report:
        cmd.extend(["--cov=src", "--cov-report=term", "--cov-report=html"])

    cmd.extend(module_paths)

    print(f"Выполнение команды: {' '.join(cmd)}")

    result = subprocess.run(cmd, env=env, cwd=str(project_root), check=False)
    return result.returncode == 0


def main() -> int:
    """Основная функция скрипта.

    Returns:
        Код возврата: 0 при успехе, 1 при ошибке
    """
    parser = argparse.ArgumentParser(description="Запуск модульных тестов")
    parser.add_argument("--all", action="store_true", help="Запустить все тесты")
    parser.add_argument(
        "--dmarket",
        action="store_true",
        help="Запустить тесты для dmarket",
    )
    parser.add_argument(
        "--telegram-bot",
        action="store_true",
        help="Запустить тесты для telegram_bot",
    )
    parser.add_argument(
        "--utils",
        action="store_true",
        help="Запустить тесты для utils",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    parser.add_argument(
        "--report",
        action="store_true",
        help="Генерировать отчет о покрытии",
    )

    args = parser.parse_args()

    # Если не указаны конкретные модули и не указан флаг --all, выводим справку
    if not (args.all or args.dmarket or args.telegram_bot or args.utils):
        parser.print_help()
        return 1

    # Формируем список модулей для тестирования
    module_paths = []

    if args.all:
        module_paths.append("src/*/tests")
    else:
        if args.dmarket:
            module_paths.append("src/dmarket/tests")
        if args.telegram_bot:
            module_paths.append("src/telegram_bot/tests")
        if args.utils:
            module_paths.append("src/utils/tests")

    success = run_tests(module_paths, args.verbose, args.report)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
