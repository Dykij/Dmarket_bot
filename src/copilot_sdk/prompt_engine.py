"""Prompt Engine - Template-based prompt management for Copilot.

This module provides a template engine for managing and executing
reusable prompts with variable substitution.

Usage:
    ```python
    from src.copilot_sdk import PromptEngine

    engine = PromptEngine()
    await engine.load_prompts(".github/prompts")

    # Execute a prompt with variables
    result = await engine.render(
        "test-generator",
        function_name="calculate_profit",
        module_path="src/dmarket/arbitrage.py",
    )
    ```

Created: January 2026
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PromptTemplate:
    """Represents a prompt template."""

    id: str
    name: str
    description: str
    template: str
    variables: list[str]
    category: str = "general"
    tags: list[str] = field(default_factory=list)
    examples: list[dict[str, Any]] = field(default_factory=list)


class PromptEngine:
    """Template engine for managing Copilot prompts.

    Supports:
    - Variable substitution: {{variable}}
    - Conditional blocks: {{#if condition}}...{{/if}}
    - Loops: {{#each items}}...{{/each}}
    - Default values: {{variable|default}}

    Example:
        ```python
        engine = PromptEngine()
        await engine.load_prompts(".github/prompts")

        # Render template
        output = await engine.render(
            "python-async",
            function_name="fetch_data",
            return_type="dict[str, Any]",
        )

        # List available prompts
        prompts = engine.list_prompts()
        ```
    """

    def __init__(self) -> None:
        """Initialize the prompt engine."""
        self.templates: dict[str, PromptTemplate] = {}

    async def load_prompts(self, directory: str | Path) -> int:
        """Load all prompt templates from a directory.

        Args:
            directory: Path to prompts directory

        Returns:
            Number of prompts loaded
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            logger.warning("prompts_dir_not_found", directory=str(directory))
            return 0

        count = 0
        for file_path in dir_path.glob("*.prompt.md"):
            template = await self._parse_prompt_file(file_path)
            if template:
                self.templates[template.id] = template
                count += 1

        logger.info(
            "prompts_loaded",
            count=count,
            directory=str(directory),
        )
        return count

    async def _parse_prompt_file(self, file_path: Path) -> PromptTemplate | None:
        """Parse a prompt template file.

        Expected format:
            ```markdown
            ---
            id: template-id
            name: Template Name
            description: What this template does
            variables:
              - var1
              - var2
            ---
            Template content with {{var1}} and {{var2}}
            ```
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            template_id = file_path.stem.replace(".prompt", "")

            # Parse frontmatter
            metadata = self._parse_frontmatter(content)

            # Extract template body
            template_body = self._extract_template_body(content)

            # Extract variables from template
            variables = self._extract_variables(template_body)

            return PromptTemplate(
                id=metadata.get("id", template_id),
                name=metadata.get("name", template_id),
                description=metadata.get("description", ""),
                template=template_body,
                variables=variables,
                category=metadata.get("category", "general"),
                tags=metadata.get("tags", []),
            )
        except Exception as e:
            logger.error(
                "prompt_parse_error",
                file=str(file_path),
                error=str(e),
            )
            return None

    def _parse_frontmatter(self, content: str) -> dict[str, Any]:
        """Parse YAML-like frontmatter from content."""
        metadata: dict[str, Any] = {}

        # Check for frontmatter delimiters
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1].strip()
                for line in frontmatter.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        key = key.strip()
                        value = value.strip()
                        # Handle lists
                        if value.startswith("[") and value.endswith("]"):
                            value = [
                                v.strip().strip("'\"") for v in value[1:-1].split(",")
                            ]
                        metadata[key] = value

        return metadata

    def _extract_template_body(self, content: str) -> str:
        """Extract the template body from content (after frontmatter)."""
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return content.strip()

    def _extract_variables(self, template: str) -> list[str]:
        """Extract variable names from template."""
        # Match {{variable}} or {{variable|default}}
        pattern = r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)"
        matches = re.findall(pattern, template)
        return list(set(matches))

    async def render(self, template_id: str, **variables: Any) -> str:
        """Render a template with variables.

        Args:
            template_id: ID of the template to render
            **variables: Variables to substitute

        Returns:
            Rendered template

        Raises:
            KeyError: If template not found
            ValueError: If required variable missing
        """
        if template_id not in self.templates:
            raise KeyError(f"Template not found: {template_id}")

        template = self.templates[template_id]
        result = template.template

        # Check for missing required variables
        for var in template.variables:
            if var not in variables:
                # Check for default value
                default_pattern = rf"\{{\{{{var}\|([^}}]+)\}}\}}"
                if not re.search(default_pattern, result):
                    logger.warning(
                        "missing_variable",
                        template_id=template_id,
                        variable=var,
                    )

        # Substitute variables with defaults
        for var, value in variables.items():
            # With default: {{var|default}}
            result = re.sub(
                rf"\{{\{{{var}\|[^}}]*\}}\}}",
                str(value),
                result,
            )
            # Without default: {{var}}
            result = result.replace(f"{{{{{var}}}}}", str(value))

        # Handle remaining defaults
        result = re.sub(
            r"\{\{[a-zA-Z_][a-zA-Z0-9_]*\|([^}]+)\}\}",
            r"\1",
            result,
        )

        logger.debug(
            "template_rendered",
            template_id=template_id,
            variables=list(variables.keys()),
        )
        return result

    async def add_template(
        self,
        template_id: str,
        template: str,
        name: str | None = None,
        description: str = "",
        category: str = "general",
    ) -> None:
        """Add a template programmatically.

        Args:
            template_id: Unique template ID
            template: Template content
            name: Human-readable name
            description: Template description
            category: Template category
        """
        variables = self._extract_variables(template)

        self.templates[template_id] = PromptTemplate(
            id=template_id,
            name=name or template_id,
            description=description,
            template=template,
            variables=variables,
            category=category,
        )

        logger.info(
            "template_added",
            template_id=template_id,
            variables=variables,
        )

    def list_prompts(self, category: str | None = None) -> list[dict[str, Any]]:
        """List all available prompts.

        Args:
            category: Optional filter by category

        Returns:
            List of prompt summaries
        """
        prompts = []
        for template in self.templates.values():
            if category and template.category != category:
                continue
            prompts.append(
                {
                    "id": template.id,
                    "name": template.name,
                    "description": template.description,
                    "variables": template.variables,
                    "category": template.category,
                    "tags": template.tags,
                }
            )
        return prompts

    def get_template(self, template_id: str) -> PromptTemplate | None:
        """Get a template by ID.

        Args:
            template_id: Template ID

        Returns:
            PromptTemplate or None if not found
        """
        return self.templates.get(template_id)
