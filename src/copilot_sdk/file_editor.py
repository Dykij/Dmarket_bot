"""
File Editor - Редактор файлов с AI-поддержкой.

Позволяет редактировать файлы на основе инструкций,
с автоматическим резервным копированием и отменой.

Вдохновлено Claude Code: "Claude Code can directly edit files, run commands, and create commits"

Usage:
    ```python
    from src.copilot_sdk.file_editor import FileEditor

    editor = FileEditor()

    # Редактировать файл по инструкции
    result = await editor.edit(
        "src/api/client.py",
        "Add type hints to all functions"
    )

    # Откатить изменения
    await editor.revert(result.backup)

    # Создать коммит
    await editor.commit("Add type hints to API client")
    ```

Created: January 2026
"""

from __future__ import annotations

import difflib
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class EditResult:
    """Результат редактирования файла."""

    file_path: str
    original: str
    edited: str
    backup: str | None = None
    diff: str | None = None
    success: bool = True
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def changed(self) -> bool:
        """Был ли файл изменён."""
        return self.original != self.edited


@dataclass
class CommitResult:
    """Результат создания коммита."""

    success: bool
    commit_hash: str | None = None
    message: str | None = None
    files_changed: int = 0
    error: str | None = None


class FileEditor:
    """Редактор файлов с AI-поддержкой."""

    def __init__(
        self,
        backup_dir: str | Path = ".backups",
        dry_run: bool = False,
    ):
        """
        Инициализация редактора.

        Args:
            backup_dir: Директория для резервных копий
            dry_run: Режим симуляции без реальных изменений
        """
        self.backup_dir = Path(backup_dir)
        self.dry_run = dry_run
        self._history: list[EditResult] = []

    async def edit(
        self,
        file_path: str,
        instruction: str,
        create_backup: bool = True,
    ) -> EditResult:
        """
        Редактировать файл на основе инструкции.

        Args:
            file_path: Путь к файлу
            instruction: Инструкция для редактирования
            create_backup: Создавать резервную копию

        Returns:
            Результат редактирования
        """
        logger.info(
            "file_edit_started",
            file_path=file_path,
            instruction=instruction[:50],
            dry_run=self.dry_run,
        )

        try:
            # Прочитать оригинальное содержимое
            original = await self._read_file(file_path)

            # Создать резервную копию
            backup_path = None
            if create_backup and not self.dry_run:
                backup_path = await self._backup(file_path)

            # Сгенерировать редактирование
            edited = await self._generate_edit(original, instruction, file_path)

            # Применить изменения
            if not self.dry_run and original != edited:
                await self._write_file(file_path, edited)

            # Создать diff
            diff = await self._create_diff(original, edited)

            result = EditResult(
                file_path=file_path,
                original=original,
                edited=edited,
                backup=backup_path,
                diff=diff,
                success=True,
            )

            self._history.append(result)

            logger.info(
                "file_edit_completed",
                file_path=file_path,
                changed=result.changed,
                backup=backup_path,
            )

            return result

        except Exception as e:
            logger.error(
                "file_edit_failed",
                file_path=file_path,
                error=str(e),
                exc_info=True,
            )
            return EditResult(
                file_path=file_path,
                original="",
                edited="",
                success=False,
                error=str(e),
            )

    async def batch_edit(
        self,
        edits: list[tuple[str, str]],
    ) -> list[EditResult]:
        """
        Редактировать несколько файлов.

        Args:
            edits: Список кортежей (путь, инструкция)

        Returns:
            Список результатов
        """
        results = []
        for file_path, instruction in edits:
            result = await self.edit(file_path, instruction)
            results.append(result)
        return results

    async def revert(self, backup_path: str) -> bool:
        """
        Откатить изменения из резервной копии.

        Args:
            backup_path: Путь к резервной копии

        Returns:
            Успешность отката
        """
        if self.dry_run:
            logger.info("revert_dry_run", backup_path=backup_path)
            return True

        try:
            backup = Path(backup_path)
            if not backup.exists():
                raise FileNotFoundError(f"Backup not found: {backup_path}")

            # Извлечь оригинальный путь из имени
            original_path = self._get_original_from_backup(backup_path)
            shutil.copy2(backup, original_path)

            logger.info("file_reverted", backup=backup_path, original=original_path)
            return True

        except Exception as e:
            logger.error("revert_failed", backup_path=backup_path, error=str(e))
            return False

    async def commit(self, message: str, files: list[str] | None = None) -> CommitResult:
        """
        Создать git коммит с изменениями.

        Args:
            message: Сообщение коммита
            files: Список файлов (None = все изменённые)

        Returns:
            Результат коммита
        """
        if self.dry_run:
            logger.info("commit_dry_run", message=message)
            return CommitResult(
                success=True,
                message=f"[DRY RUN] {message}",
            )

        try:
            # Добавить файлы
            if files:
                for file in files:
                    await self._run_git(["add", file])
            else:
                await self._run_git(["add", "-A"])

            # Создать коммит
            result = await self._run_git(["commit", "-m", message])

            # Получить хеш коммита
            hash_result = await self._run_git(["rev-parse", "HEAD"])
            commit_hash = hash_result.strip()[:8]

            # Получить количество изменённых файлов
            diff_result = await self._run_git(["diff", "--stat", "HEAD~1"])
            files_changed = len([l for l in diff_result.split("\n") if "|" in l])

            logger.info(
                "commit_created",
                hash=commit_hash,
                message=message,
                files_changed=files_changed,
            )

            return CommitResult(
                success=True,
                commit_hash=commit_hash,
                message=message,
                files_changed=files_changed,
            )

        except Exception as e:
            logger.error("commit_failed", error=str(e))
            return CommitResult(success=False, error=str(e))

    async def _read_file(self, file_path: str) -> str:
        """Прочитать содержимое файла."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        return path.read_text(encoding="utf-8")

    async def _write_file(self, file_path: str, content: str) -> None:
        """Записать содержимое в файл."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    async def _backup(self, file_path: str) -> str:
        """Создать резервную копию файла."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        source = Path(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{source.stem}_{timestamp}{source.suffix}"
        backup_path = self.backup_dir / backup_name

        shutil.copy2(source, backup_path)
        return str(backup_path)

    def _get_original_from_backup(self, backup_path: str) -> str:
        """Получить оригинальный путь из пути резервной копии."""
        # Логика восстановления пути из истории
        for result in reversed(self._history):
            if result.backup == backup_path:
                return result.file_path
        raise ValueError(f"Original path not found for backup: {backup_path}")

    async def _generate_edit(
        self,
        content: str,
        instruction: str,
        file_path: str,
    ) -> str:
        """
        Сгенерировать редактирование на основе инструкции.

        В будущем здесь будет интеграция с LLM.
        """
        # Простые паттерны редактирования
        instruction_lower = instruction.lower()

        if "add type hints" in instruction_lower:
            return self._add_type_hints(content)
        elif "add docstrings" in instruction_lower:
            return self._add_docstrings(content)
        elif "format" in instruction_lower:
            return await self._format_code(content, file_path)
        elif "remove comments" in instruction_lower:
            return self._remove_comments(content)
        else:
            # Без изменений (требуется LLM для сложных инструкций)
            logger.warning(
                "edit_instruction_not_understood",
                instruction=instruction,
                file=file_path,
            )
            return content

    def _add_type_hints(self, content: str) -> str:
        """Добавить базовые type hints (простая реализация)."""
        # TODO: Интеграция с LLM для полной реализации
        # Пока возвращаем без изменений
        return content

    def _add_docstrings(self, content: str) -> str:
        """Добавить docstrings (простая реализация)."""
        # TODO: Интеграция с LLM
        return content

    async def _format_code(self, content: str, file_path: str) -> str:
        """Форматировать код через ruff/black."""
        if file_path.endswith(".py"):
            try:
                result = subprocess.run(
                    ["ruff", "format", "--stdin-filename", file_path, "-"],
                    input=content,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    return result.stdout
            except Exception as e:
                logger.warning("format_failed", error=str(e))
        return content

    def _remove_comments(self, content: str) -> str:
        """Удалить комментарии из кода."""
        lines = []
        for line in content.split("\n"):
            stripped = line.strip()
            if not stripped.startswith("#"):
                lines.append(line)
        return "\n".join(lines)

    async def _create_diff(self, original: str, edited: str) -> str:
        """Создать diff между версиями."""
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            edited.splitlines(keepends=True),
            fromfile="original",
            tofile="edited",
        )
        return "".join(diff)

    async def _run_git(self, args: list[str]) -> str:
        """Выполнить git команду."""
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Git error: {result.stderr}")
        return result.stdout

    def get_history(self) -> list[EditResult]:
        """Получить историю редактирований."""
        return self._history.copy()

    def clear_history(self) -> None:
        """Очистить историю редактирований."""
        self._history.clear()
