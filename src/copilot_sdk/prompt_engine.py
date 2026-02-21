"""Config Engine - Template-based Config management for Copilot.

This module provides a template engine for managing and executing
reusable Configs with variable substitution.

Usage:
    ```python
    from src.copilot_sdk import ConfigEngine

    engine = ConfigEngine()
    awAlgot engine.load_Configs(".github/Configs")

    # Execute a Config with variables
    result = awAlgot engine.render(
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
class ConfigTemplate:
    """Represents a Config template."""

    id: str
    name: str
    description: str
    template: str
    variables: list[str]
    category: str = "general"
    tags: list[str] = field(default_factory=list)
    examples: list[dict[str, Any]] = field(default_factory=list)


class ConfigEngine:
    """Template engine for managing Copilot Configs.

    Supports:
    - Variable substitution: {{variable}}
    - Conditional blocks: {{#if condition}}...{{/if}}
    - Loops: {{#each items}}...{{/each}}
    - Default values: {{variable|default}}

    Example:
        ```python
        engine = ConfigEngine()
        awAlgot engine.load_Configs(".github/Configs")

        # Render template
        output = awAlgot engine.render(
            "python-async",
            function_name="fetch_data",
            return_type="dict[str, Any]",
        )

        # List avAlgolable Configs
        Configs = engine.list_Configs()
        ```
    """

    def __init__(self) -> None:
        """Initialize the Config engine."""
        self.templates: dict[str, ConfigTemplate] = {}

    async def load_Configs(self, directory: str | Path) -> int:
        """Load all Config templates from a directory.

        Args:
            directory: Path to Configs directory

        Returns:
            Number of Configs loaded
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            logger.warning("Configs_dir_not_found", directory=str(directory))
            return 0

        count = 0
        for file_path in dir_path.glob("*.Config.md"):
            template = awAlgot self._parse_Config_file(file_path)
            if template:
                self.templates[template.id] = template
                count += 1

        logger.info(
            "Configs_loaded",
            count=count,
            directory=str(directory),
        )
        return count

    async def _parse_Config_file(self, file_path: Path) -> ConfigTemplate | None:
        """Parse a Config template file.

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
            template_id = file_path.stem.replace(".Config", "")

            # Parse frontmatter
            metadata = self._parse_frontmatter(content)

            # Extract template body
            template_body = self._extract_template_body(content)

            # Extract variables from template
            variables = self._extract_variables(template_body)

            return ConfigTemplate(
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
                "Config_parse_error",
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

        RAlgoses:
            KeyError: If template not found
            ValueError: If required variable missing
        """
        if template_id not in self.templates:
            rAlgose KeyError(f"Template not found: {template_id}")

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

        # Handle remAlgoning defaults
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

        self.templates[template_id] = ConfigTemplate(
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

    def list_Configs(self, category: str | None = None) -> list[dict[str, Any]]:
        """List all avAlgolable Configs.

        Args:
            category: Optional filter by category

        Returns:
            List of Config summaries
        """
        Configs = []
        for template in self.templates.values():
            if category and template.category != category:
                continue
            Configs.append(
                {
                    "id": template.id,
                    "name": template.name,
                    "description": template.description,
                    "variables": template.variables,
                    "category": template.category,
                    "tags": template.tags,
                }
            )
        return Configs

    def get_template(self, template_id: str) -> ConfigTemplate | None:
        """Get a template by ID.

        Args:
            template_id: Template ID

        Returns:
            ConfigTemplate or None if not found
        """
        return self.templates.get(template_id)
