"""
Project Indexer - Индексатор проекта для контекстного поиска.

Создаёт поисковый индекс всего проекта для улучшения context awareness.
Поддерживает семантический поиск через embeddings.

Вдохновлено Claude Code для глубокого понимания всего проекта.

Usage:
    ```python
    from src.copilot_sdk.project_indexer import ProjectIndexer

    indexer = ProjectIndexer()
    index = await indexer.index(".")

    # Поиск по проекту
    results = await indexer.query("How does authentication work?")
    for result in results:
        print(f"{result.file}: {result.snippet}")
    ```

Created: January 2026
"""

from __future__ import annotations

import ast
import hashlib
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Symbol:
    """Символ кода (функция, класс, переменная)."""

    name: str
    type: str  # "function", "class", "variable", "import"
    file: str
    line: int
    docstring: str | None = None
    signature: str | None = None


@dataclass
class FileInfo:
    """Информация о файле в индексе."""

    path: str
    symbols: list[Symbol] = field(default_factory=list)
    content_hash: str = ""
    last_modified: datetime | None = None
    lines_count: int = 0
    language: str = "unknown"


@dataclass
class SearchResult:
    """Результат поиска."""

    file: str
    line: int | None = None
    snippet: str = ""
    score: float = 0.0
    symbol: Symbol | None = None
    match_type: str = "text"  # "text", "symbol", "semantic"


class ProjectIndex:
    """Индекс проекта для поиска."""

    def __init__(self):
        """Инициализация индекса."""
        self.files: dict[str, FileInfo] = {}
        self.symbols: dict[str, list[Symbol]] = {}  # name -> list of symbols
        self.docs: dict[str, str] = {}  # path -> content
        self._embeddings: dict[str, list[float]] = {}  # path -> embedding vector
        self.created_at: datetime = datetime.now()

    def add_file(self, path: str, file_info: FileInfo) -> None:
        """Добавить файл в индекс."""
        self.files[path] = file_info
        for symbol in file_info.symbols:
            if symbol.name not in self.symbols:
                self.symbols[symbol.name] = []
            self.symbols[symbol.name].append(symbol)

    def add_doc(self, path: str, content: str) -> None:
        """Добавить документацию в индекс."""
        self.docs[path] = content

    async def build_embeddings(self) -> None:
        """
        Построить embeddings для семантического поиска.

        TODO: Интеграция с OpenAI/Sentence-Transformers для реальных embeddings.
        """
        # Placeholder - в реальной реализации используем embeddings API
        for path, content in self.docs.items():
            # Простой хеш как placeholder для embedding
            self._embeddings[path] = self._simple_embedding(content)

        for path, file_info in self.files.items():
            content = "\n".join(s.name for s in file_info.symbols)
            self._embeddings[path] = self._simple_embedding(content)

    def _simple_embedding(self, text: str) -> list[float]:
        """Простой placeholder для embedding."""
        # В реальной реализации - вызов API embeddings
        words = text.lower().split()
        # Простой bag-of-words вектор
        vector = [0.0] * 100
        for word in words:
            idx = hash(word) % 100
            vector[idx] += 1
        # Нормализация
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        return vector

    async def search(
        self,
        query: str,
        top_k: int = 10,
        search_type: str = "all",
    ) -> list[SearchResult]:
        """
        Поиск по индексу.

        Args:
            query: Поисковый запрос
            top_k: Количество результатов
            search_type: Тип поиска ("text", "symbol", "semantic", "all")

        Returns:
            Список результатов
        """
        results: list[SearchResult] = []

        # Поиск по символам
        if search_type in ("symbol", "all"):
            for name, symbols in self.symbols.items():
                if query.lower() in name.lower():
                    for symbol in symbols:
                        results.append(
                            SearchResult(
                                file=symbol.file,
                                line=symbol.line,
                                snippet=f"{symbol.type}: {symbol.name}",
                                score=1.0 if name.lower() == query.lower() else 0.8,
                                symbol=symbol,
                                match_type="symbol",
                            )
                        )

        # Текстовый поиск в документации
        if search_type in ("text", "all"):
            query_lower = query.lower()
            for path, content in self.docs.items():
                if query_lower in content.lower():
                    # Найти контекст
                    idx = content.lower().find(query_lower)
                    start = max(0, idx - 50)
                    end = min(len(content), idx + len(query) + 50)
                    snippet = content[start:end]

                    results.append(
                        SearchResult(
                            file=path,
                            snippet=f"...{snippet}...",
                            score=0.7,
                            match_type="text",
                        )
                    )

        # Семантический поиск
        if search_type in ("semantic", "all") and self._embeddings:
            query_embedding = self._simple_embedding(query)

            for path, embedding in self._embeddings.items():
                # Косинусное сходство
                score = sum(a * b for a, b in zip(query_embedding, embedding))
                if score > 0.1:
                    results.append(
                        SearchResult(
                            file=path,
                            snippet="[Semantic match]",
                            score=score * 0.5,  # Снижаем вес для простого алгоритма
                            match_type="semantic",
                        )
                    )

        # Сортировка по релевантности
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику индекса."""
        return {
            "files_count": len(self.files),
            "docs_count": len(self.docs),
            "symbols_count": sum(len(s) for s in self.symbols.values()),
            "embeddings_count": len(self._embeddings),
            "created_at": self.created_at.isoformat(),
        }


class ProjectIndexer:
    """Индексатор проекта."""

    def __init__(
        self,
        exclude_patterns: list[str] | None = None,
        include_tests: bool = True,
    ):
        """
        Инициализация индексатора.

        Args:
            exclude_patterns: Паттерны для исключения
            include_tests: Включать тестовые файлы
        """
        self.exclude_patterns = exclude_patterns or [
            "__pycache__",
            ".git",
            ".venv",
            "venv",
            "node_modules",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            "*.pyc",
            "*.egg-info",
        ]
        self.include_tests = include_tests
        self.index: ProjectIndex | None = None

    async def index(self, root: str = ".") -> ProjectIndex:
        """
        Создать индекс проекта.

        Args:
            root: Корневая директория

        Returns:
            Индекс проекта
        """
        logger.info("project_indexing_started", root=root)

        index = ProjectIndex()
        root_path = Path(root)

        # Индексировать Python файлы
        async for file in self._discover_files(root_path, "*.py"):
            try:
                file_info = await self._index_python_file(file)
                index.add_file(str(file), file_info)
            except Exception as e:
                logger.warning("file_indexing_failed", file=str(file), error=str(e))

        # Индексировать документацию
        async for doc in self._discover_files(root_path, "*.md"):
            try:
                content = doc.read_text(encoding="utf-8")
                index.add_doc(str(doc), content)
            except Exception as e:
                logger.warning("doc_indexing_failed", file=str(doc), error=str(e))

        # Построить embeddings
        await index.build_embeddings()

        self.index = index

        logger.info(
            "project_indexing_completed",
            files=len(index.files),
            docs=len(index.docs),
            symbols=sum(len(s) for s in index.symbols.values()),
        )

        return index

    async def _discover_files(
        self,
        root: Path,
        pattern: str,
    ) -> AsyncIterator[Path]:
        """Найти файлы по паттерну."""
        for file in root.rglob(pattern):
            # Проверить исключения
            if any(excl in str(file) for excl in self.exclude_patterns):
                continue

            # Проверить тесты
            if not self.include_tests and "test" in str(file).lower():
                continue

            yield file

    async def _index_python_file(self, file: Path) -> FileInfo:
        """Индексировать Python файл."""
        content = file.read_text(encoding="utf-8")
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        symbols = await self._extract_symbols(content, str(file))

        return FileInfo(
            path=str(file),
            symbols=symbols,
            content_hash=content_hash,
            last_modified=datetime.fromtimestamp(file.stat().st_mtime),
            lines_count=len(content.splitlines()),
            language="python",
        )

    async def _extract_symbols(self, content: str, file_path: str) -> list[Symbol]:
        """Извлечь символы из Python кода."""
        symbols: list[Symbol] = []

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return symbols

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                symbols.append(
                    Symbol(
                        name=node.name,
                        type="function",
                        file=file_path,
                        line=node.lineno,
                        docstring=ast.get_docstring(node),
                        signature=self._get_function_signature(node),
                    )
                )
            elif isinstance(node, ast.AsyncFunctionDef):
                symbols.append(
                    Symbol(
                        name=node.name,
                        type="async_function",
                        file=file_path,
                        line=node.lineno,
                        docstring=ast.get_docstring(node),
                        signature=self._get_function_signature(node),
                    )
                )
            elif isinstance(node, ast.ClassDef):
                symbols.append(
                    Symbol(
                        name=node.name,
                        type="class",
                        file=file_path,
                        line=node.lineno,
                        docstring=ast.get_docstring(node),
                    )
                )

        return symbols

    def _get_function_signature(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> str:
        """Получить сигнатуру функции."""
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                try:
                    arg_str += f": {ast.unparse(arg.annotation)}"
                except Exception:
                    pass
            args.append(arg_str)

        returns = ""
        if node.returns:
            try:
                returns = f" -> {ast.unparse(node.returns)}"
            except Exception:
                pass

        return f"({', '.join(args)}){returns}"

    async def query(self, question: str, top_k: int = 10) -> list[SearchResult]:
        """
        Поиск по проекту.

        Args:
            question: Вопрос или поисковый запрос
            top_k: Количество результатов

        Returns:
            Список результатов
        """
        if self.index is None:
            raise RuntimeError(
                "Project not indexed. Call `await indexer.index()` first."
            )

        return await self.index.search(question, top_k)

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику индексатора."""
        if self.index is None:
            return {"status": "not_indexed"}
        return self.index.get_stats()
