"""Instruction Pattern Matcher - Auto-apply instructions based on file patterns.

This module matches file paths to instruction files using glob patterns,
enabling automatic context application for GitHub Copilot.

Usage:
    ```python
    from src.copilot_sdk import InstructionMatcher

    matcher = InstructionMatcher()
    await matcher.load_instructions(".github/instructions")

    # Get instructions for a file
    instructions = await matcher.get_instructions("src/dmarket/api.py")
    # Returns: ["python-style.instructions.md", "api-integration.instructions.md"]
    ```

Created: January 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Instruction:
    """Represents a single instruction file."""

    name: str
    patterns: list[str]
    content: str
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class InstructionMatcher:
    """Match files to instructions based on glob patterns.

    Attributes:
        instructions: Dict of loaded instructions by name
        pattern_map: Mapping of patterns to instruction names

    Example:
        ```python
        matcher = InstructionMatcher()
        await matcher.load_instructions(".github/instructions")

        # Match single file
        result = await matcher.get_instructions("src/api/client.py")

        # Match with merged content
        content = await matcher.get_merged_instructions("tests/test_api.py")
        ```
    """

    def __init__(self) -> None:
        """Initialize the instruction matcher."""
        self.instructions: dict[str, Instruction] = {}
        self.pattern_map: dict[str, list[str]] = {}

    async def load_instructions(self, directory: str | Path) -> int:
        """Load all instruction files from a directory.

        Args:
            directory: Path to instructions directory

        Returns:
            Number of instructions loaded

        Raises:
            FileNotFoundError: If directory doesn't exist
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            logger.warning("instructions_dir_not_found", directory=str(directory))
            return 0

        count = 0
        for file_path in dir_path.glob("*.instructions.md"):
            instruction = await self._parse_instruction_file(file_path)
            if instruction:
                self.instructions[instruction.name] = instruction
                for pattern in instruction.patterns:
                    if pattern not in self.pattern_map:
                        self.pattern_map[pattern] = []
                    self.pattern_map[pattern].append(instruction.name)
                count += 1

        logger.info(
            "instructions_loaded",
            count=count,
            directory=str(directory),
        )
        return count

    async def _parse_instruction_file(self, file_path: Path) -> Instruction | None:
        """Parse an instruction file.

        Expected format:
            ```markdown
            # Title
            Apply to: `pattern1`, `pattern2`
            ## Rules
            ...
            ```
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            name = file_path.stem

            # Extract patterns from "Apply to:" line or frontmatter
            patterns = self._extract_patterns(content, name)

            # Extract priority from content (optional)
            priority = self._extract_priority(content)

            return Instruction(
                name=name,
                patterns=patterns,
                content=content,
                priority=priority,
            )
        except Exception as e:
            logger.error(
                "instruction_parse_error",
                file=str(file_path),
                error=str(e),
            )
            return None

    def _extract_patterns(self, content: str, name: str) -> list[str]:
        """Extract file patterns from instruction content."""
        patterns = []

        # Look for "Apply to:" line
        for line in content.split("\n"):
            line_lower = line.lower()
            if "apply to:" in line_lower or "applies to:" in line_lower:
                # Extract patterns from backticks
                import re

                found = re.findall(r"`([^`]+)`", line)
                patterns.extend(found)
                break

        # Default patterns based on name
        if not patterns:
            default_patterns = {
                "python-style": ["src/**/*.py"],
                "testing": ["tests/**/*.py"],
                "workflows": [
                    ".github/workflows/**/*.yml",
                    ".github/workflows/**/*.yaml",
                ],
                "documentation": ["docs/**/*.md", "*.md"],
                "database": ["src/models/**/*.py", "alembic/**/*.py"],
                "api-integration": ["src/dmarket/**/*.py", "src/waxpeer/**/*.py"],
                "telegram-bot": ["src/telegram_bot/**/*.py"],
            }
            patterns = default_patterns.get(name, ["**/*"])

        return patterns

    def _extract_priority(self, content: str) -> int:
        """Extract priority from instruction content."""
        for line in content.split("\n"):
            if "priority:" in line.lower():
                import re

                match = re.search(r"priority:\s*(\d+)", line, re.IGNORECASE)
                if match:
                    return int(match.group(1))
        return 0

    def _match_pattern(self, path: str, pattern: str) -> bool:
        """Match path against pattern supporting ** glob.

        Args:
            path: File path to match
            pattern: Glob pattern (supports **)

        Returns:
            True if path matches pattern
        """
        from pathlib import PurePosixPath

        try:
            # Direct match
            if PurePosixPath(path).match(pattern):
                return True

            # For patterns like "tests/**/*.py", also match "tests/*.py"
            # by trying alternative patterns
            if "**/" in pattern:
                # Try pattern without **/ (for direct children)
                simple_pattern = pattern.replace("**/", "")
                if PurePosixPath(path).match(simple_pattern):
                    return True

            return False
        except Exception:
            return False

    async def get_instructions(self, file_path: str) -> list[str]:
        """Get all matching instructions for a file path.

        Args:
            file_path: Path to the file

        Returns:
            List of instruction names that match
        """
        matching = []
        normalized_path = file_path.replace("\\", "/")

        for pattern, instruction_names in self.pattern_map.items():
            if self._match_pattern(normalized_path, pattern):
                for name in instruction_names:
                    if name not in matching:
                        matching.append(name)

        # Sort by priority
        matching.sort(
            key=lambda n: (
                self.instructions[n].priority if n in self.instructions else 0
            ),
            reverse=True,
        )

        logger.debug(
            "instructions_matched",
            file_path=file_path,
            matching=matching,
        )
        return matching

    async def get_merged_instructions(self, file_path: str) -> str:
        """Get merged content of all matching instructions.

        Args:
            file_path: Path to the file

        Returns:
            Combined instruction content
        """
        instruction_names = await self.get_instructions(file_path)
        contents = []

        for name in instruction_names:
            if name in self.instructions:
                contents.append(f"# From: {name}.instructions.md\n\n")
                contents.append(self.instructions[name].content)
                contents.append("\n\n---\n\n")

        return "".join(contents)

    async def add_instruction(
        self,
        name: str,
        patterns: list[str],
        content: str,
        priority: int = 0,
    ) -> None:
        """Add an instruction programmatically.

        Args:
            name: Unique instruction name
            patterns: List of glob patterns
            content: Instruction content
            priority: Priority for ordering (higher = first)
        """
        instruction = Instruction(
            name=name,
            patterns=patterns,
            content=content,
            priority=priority,
        )
        self.instructions[name] = instruction

        for pattern in patterns:
            if pattern not in self.pattern_map:
                self.pattern_map[pattern] = []
            if name not in self.pattern_map[pattern]:
                self.pattern_map[pattern].append(name)

        logger.info(
            "instruction_added",
            name=name,
            patterns=patterns,
        )

    def list_instructions(self) -> list[dict[str, Any]]:
        """List all loaded instructions.

        Returns:
            List of instruction summaries
        """
        return [
            {
                "name": inst.name,
                "patterns": inst.patterns,
                "priority": inst.priority,
            }
            for inst in self.instructions.values()
        ]
