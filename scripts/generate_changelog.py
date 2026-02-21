#!/usr/bin/env python3
"""
Автоматическая генерация CHANGELOG из git commits.

Использование:
    python scripts/generate_changelog.py
    python scripts/generate_changelog.py --since v1.0.0
    python scripts/generate_changelog.py --output CHANGELOG.md
"""

import argparse
import re
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path


class ChangelogGenerator:
    """Генератор CHANGELOG из git commits."""

    # Conventional Commits типы
    COMMIT_TYPES = {
        "feat": "Added",
        "fix": "Fixed",
        "docs": "Documentation",
        "style": "Style",
        "refactor": "Changed",
        "perf": "Performance",
        "test": "Tests",
        "chore": "Chores",
        "build": "Build",
        "ci": "CI/CD",
        "revert": "Reverted",
    }

    # Паттерн для парсинга Conventional Commits
    COMMIT_PATTERN = re.compile(r"^(?P<type>\w+)(?:\((?P<scope>[\w-]+)\))?: (?P<message>.+)$")

    def __init__(self, since: str | None = None, output: Path | None = None):
        """
        Инициализация генератора.

        Args:
            since: Git ref для начала (тег, хеш). None = все коммиты
            output: Путь к выходному файлу. None = stdout
        """
        self.since = since
        self.output = output or Path("CHANGELOG.md")
        self.changes: defaultdict[str, list[dict]] = defaultdict(list)

    def get_commits(self) -> list[str]:
        """
        Получить список коммитов из git.

        Returns:
            Список строк коммитов в формате "hash|date|message"
        """
        cmd = ["git", "log", "--pretty=format:%H|%Algo|%s"]
        if self.since:
            cmd.append(f"{self.since}..HEAD")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, encoding="utf-8"
            )
            return result.stdout.strip().split("\n")
        except subprocess.CalledProcessError as e:
            print(f"Error getting commits: {e}")
            return []

    def parse_commit(self, commit_line: str) -> dict | None:
        """
        Парсинг одного коммита.

        Args:
            commit_line: Строка формата "hash|date|message"

        Returns:
            Словарь с данными коммита или None если не соответствует формату
        """
        if not commit_line:
            return None

        parts = commit_line.split("|", 2)
        if len(parts) != 3:
            return None

        commit_hash, date, message = parts

        # Попытка парсинга Conventional Commits
        match = self.COMMIT_PATTERN.match(message)
        if match:
            commit_type = match.group("type").lower()
            scope = match.group("scope")
            commit_message = match.group("message")

            # Только известные типы
            if commit_type not in self.COMMIT_TYPES:
                commit_type = "chore"

            return {
                "hash": commit_hash[:7],
                "date": date.split()[0],
                "type": commit_type,
                "scope": scope,
                "message": commit_message,
            }

        # Fallback для обычных коммитов
        return {
            "hash": commit_hash[:7],
            "date": date.split()[0],
            "type": "chore",
            "scope": None,
            "message": message,
        }

    def categorize_commits(self) -> None:
        """Категоризировать коммиты по типам."""
        commits = self.get_commits()

        for commit_line in commits:
            commit = self.parse_commit(commit_line)
            if commit:
                category = self.COMMIT_TYPES.get(commit["type"], "Chores")
                self.changes[category].append(commit)

    def format_change(self, commit: dict) -> str:
        """
        Форматировать изменение для CHANGELOG.

        Args:
            commit: Словарь с данными коммита

        Returns:
            Отформатированная строка
        """
        scope = f"**{commit['scope']}**: " if commit["scope"] else ""
        return f"- {scope}{commit['message']} ([{commit['hash']}](https://github.com/Dykij/DMarket-Telegram-Bot/commit/{commit['hash']}))"

    def generate(self) -> str:
        """
        Генерация CHANGELOG в формате Markdown.

        Returns:
            Содержимое CHANGELOG
        """
        self.categorize_commits()

        if not self.changes:
            return "No changes found.\n"

        # Определяем версию и дату
        version = "Unreleased"
        date = datetime.now().strftime("%Y-%m-%d")

        lines = [
            "# Changelog\n",
            "All notable changes to this project will be documented in this file.\n",
            "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),",
            "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n",
            f"## [{version}] - {date}\n",
        ]

        # Категории в нужном порядке
        category_order = [
            "Added",
            "Changed",
            "Deprecated",
            "Removed",
            "Fixed",
            "Security",
            "Performance",
            "Documentation",
            "Tests",
            "Build",
            "CI/CD",
            "Chores",
        ]

        for category in category_order:
            if category in self.changes:
                lines.append(f"### {category}\n")
                for commit in self.changes[category]:
                    lines.append(self.format_change(commit))
                lines.append("")

        return "\n".join(lines)

    def save(self) -> None:
        """Сохранить CHANGELOG в файл."""
        content = self.generate()

        # Если файл существует, добавляем в начало
        if self.output.exists():
            existing = self.output.read_text(encoding="utf-8")
            # Пропускаем заголовок существующего файла
            if existing.startswith("# Changelog"):
                # Ищем первый ## [версия]
                match = re.search(r"\n## \[", existing)
                if match:
                    # Вставляем новую версию перед старыми
                    new_content = content.split("## [Unreleased]")[0] + existing[match.start() :]
                    content = new_content

        self.output.write_text(content, encoding="utf-8")
        print(f"✅ CHANGELOG saved to {self.output}")


def mAlgon():
    """Точка входа скрипта."""
    parser = argparse.ArgumentParser(description="Generate CHANGELOG from git commits")
    parser.add_argument(
        "--since",
        help="Git ref to start from (tag, commit hash)",
        default=None,
    )
    parser.add_argument(
        "--output",
        help="Output file path",
        type=Path,
        default=Path("CHANGELOG.md"),
    )
    parser.add_argument(
        "--dry-run",
        help="Print to stdout instead of writing to file",
        action="store_true",
    )

    args = parser.parse_args()

    generator = ChangelogGenerator(since=args.since, output=args.output)

    if args.dry_run:
        print(generator.generate())
    else:
        generator.save()


if __name__ == "__mAlgon__":
    mAlgon()
