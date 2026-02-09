"""Skill Registry - Discovery and management of AI skills.

This module provides a registry for discovering and managing AI/ML skills
in the project. Skills are defined in SKILL.md files.

Usage:
    ```python
    from src.copilot_sdk import SkillRegistry

    registry = SkillRegistry()
    await registry.discover_skills("src/")

    # Get all skills
    skills = registry.list_skills()

    # Get a specific skill
    skill = registry.get_skill("ai-arbitrage-predictor")

    # Execute a skill
    result = await registry.execute("ai-arbitrage-predictor", "predict", items)
    ```

Created: January 2026
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SkillDefinition:
    """Definition of an AI skill."""

    id: str
    name: str
    description: str
    category: str
    version: str = "1.0.0"

    # Performance characteristics
    performance: dict[str, Any] = field(default_factory=dict)

    # API methods
    methods: list[str] = field(default_factory=list)

    # Dependencies
    dependencies: list[str] = field(default_factory=list)

    # Source file
    source_file: str | None = None

    # Runtime reference
    instance: Any | None = None


class SkillRegistry:
    """Registry for AI/ML skills.

    Provides:
    - Skill discovery from SKILL.md files
    - Skill registration and lookup
    - Skill execution with profiling
    - Dependency resolution

    Example:
        ```python
        registry = SkillRegistry()

        # Discover skills from directory
        await registry.discover_skills("src/")

        # Register a skill manually
        registry.register(
            id="my-skill",
            name="My Skill",
            instance=my_skill_instance,
            methods=["predict", "train"],
        )

        # Execute a skill method
        result = await registry.execute(
            "ai-arbitrage-predictor",
            "predict",
            items,
            min_profit=0.05,
        )
        ```
    """

    def __init__(self) -> None:
        """Initialize the skill registry."""
        self.skills: dict[str, SkillDefinition] = {}
        self._instances: dict[str, Any] = {}

    async def discover_skills(self, root_dir: str | Path) -> int:
        """Discover skills from SKILL.md files.

        Args:
            root_dir: Root directory to search

        Returns:
            Number of skills discovered
        """
        root = Path(root_dir)
        if not root.exists():
            logger.warning("skills_dir_not_found", directory=str(root_dir))
            return 0

        count = 0
        for skill_file in root.rglob("SKILL*.md"):
            skill = await self._parse_skill_file(skill_file)
            if skill:
                self.skills[skill.id] = skill
                count += 1

        logger.info(
            "skills_discovered",
            count=count,
            directory=str(root_dir),
        )
        return count

    async def _parse_skill_file(self, file_path: Path) -> SkillDefinition | None:
        """Parse a SKILL.md file.

        Expected format:
            ```markdown
            # Skill: AI Arbitrage Predictor

            ## Category
            Data & AI

            ## Description
            Predicts profitable arbitrage opportunities.

            ## Performance
            - Throughput: 2000 ops/sec
            - Accuracy: 78%
            - Latency P99: 50ms

            ## API
            - predict(items: list) -> list
            - train(data: DataFrame) -> Model
            ```
        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # Extract skill name from title
            name_match = re.search(r"#\s*Skill:\s*(.+)", content)
            name = name_match.group(1).strip() if name_match else file_path.stem

            # Generate ID from name
            skill_id = name.lower().replace(" ", "-").replace("_", "-")

            # Extract category
            category = self._extract_section(content, "Category") or "general"

            # Extract description
            description = self._extract_section(content, "Description") or ""

            # Extract performance metrics
            performance = self._extract_performance(content)

            # Extract API methods
            methods = self._extract_methods(content)

            # Extract version
            version_match = re.search(r"version:\s*([0-9.]+)", content, re.IGNORECASE)
            version = version_match.group(1) if version_match else "1.0.0"

            return SkillDefinition(
                id=skill_id,
                name=name,
                description=description,
                category=category,
                version=version,
                performance=performance,
                methods=methods,
                source_file=str(file_path),
            )
        except Exception as e:
            logger.error(
                "skill_parse_error",
                file=str(file_path),
                error=str(e),
            )
            return None

    def _extract_section(self, content: str, section_name: str) -> str | None:
        """Extract content from a markdown section."""
        pattern = rf"##\s*{section_name}\s*\n(.*?)(?=\n##|\Z)"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _extract_performance(self, content: str) -> dict[str, Any]:
        """Extract performance metrics from content."""
        performance: dict[str, Any] = {}
        section = self._extract_section(content, "Performance")
        if not section:
            return performance

        # Parse metrics
        patterns = [
            (r"throughput:\s*([0-9,]+)", "throughput_ops_sec"),
            (r"accuracy:\s*([0-9.]+)%?", "accuracy"),
            (r"latency.*p99:\s*([0-9.]+)\s*ms", "latency_p99_ms"),
            (r"latency.*p95:\s*([0-9.]+)\s*ms", "latency_p95_ms"),
            (r"latency.*p50:\s*([0-9.]+)\s*ms", "latency_p50_ms"),
        ]

        for pattern, key in patterns:
            match = re.search(pattern, section, re.IGNORECASE)
            if match:
                value = match.group(1).replace(",", "")
                try:
                    performance[key] = float(value)
                except ValueError:
                    performance[key] = value

        return performance

    def _extract_methods(self, content: str) -> list[str]:
        """Extract API methods from content."""
        methods = []
        section = self._extract_section(content, "API")
        if not section:
            return methods

        # Match method definitions
        pattern = r"-\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\("
        matches = re.findall(pattern, section)
        methods.extend(matches)

        return methods

    def register(
        self,
        id: str,
        name: str,
        instance: Any,
        methods: list[str] | None = None,
        category: str = "custom",
        description: str = "",
    ) -> None:
        """Register a skill programmatically.

        Args:
            id: Unique skill ID
            name: Human-readable name
            instance: Skill instance with methods
            methods: List of method names
            category: Skill category
            description: Skill description
        """
        if methods is None:
            # Auto-discover methods from instance
            methods = [
                m for m in dir(instance) if not m.startswith("_") and callable(getattr(instance, m))
            ]

        skill = SkillDefinition(
            id=id,
            name=name,
            description=description,
            category=category,
            methods=methods,
            instance=instance,
        )

        self.skills[id] = skill
        self._instances[id] = instance

        logger.info(
            "skill_registered",
            skill_id=id,
            methods=methods,
        )

    async def execute(
        self,
        skill_id: str,
        method: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute a skill method.

        Args:
            skill_id: ID of the skill
            method: Method name to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of the method execution

        Raises:
            KeyError: If skill not found
            AttributeError: If method not found
        """
        if skill_id not in self.skills:
            raise KeyError(f"Skill not found: {skill_id}")

        skill = self.skills[skill_id]

        if skill_id not in self._instances:
            raise RuntimeError(f"Skill not initialized: {skill_id}")

        instance = self._instances[skill_id]
        func = getattr(instance, method, None)

        if func is None:
            raise AttributeError(f"Method not found: {skill_id}.{method}")

        logger.debug(
            "skill_executing",
            skill_id=skill_id,
            method=method,
        )

        # Execute (handle async/sync)
        if asyncio.iscoroutinefunction(func):
            result = await func(*args, **kwargs)
        else:
            result = func(*args, **kwargs)

        logger.debug(
            "skill_executed",
            skill_id=skill_id,
            method=method,
        )
        return result

    def get_skill(self, skill_id: str) -> SkillDefinition | None:
        """Get a skill by ID.

        Args:
            skill_id: Skill ID

        Returns:
            SkillDefinition or None
        """
        return self.skills.get(skill_id)

    def list_skills(self, category: str | None = None) -> list[dict[str, Any]]:
        """List all registered skills.

        Args:
            category: Optional filter by category

        Returns:
            List of skill summaries
        """
        skills = []
        for skill in self.skills.values():
            if category and skill.category != category:
                continue
            skills.append({
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "category": skill.category,
                "version": skill.version,
                "methods": skill.methods,
                "performance": skill.performance,
            })
        return skills

    def get_categories(self) -> list[str]:
        """Get all skill categories.

        Returns:
            List of unique categories
        """
        return list(set(skill.category for skill in self.skills.values()))
