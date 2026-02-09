"""Copilot Agent - High-level interface for AI-assisted development.

This module provides a unified interface for interacting with GitHub Copilot
capabilities, combining instructions, prompts, and skills.

Usage:
    ```python
    from src.copilot_sdk import CopilotAgent

    agent = CopilotAgent()
    await agent.initialize()

    # Get context for a file
    context = await agent.get_context("src/dmarket/api.py")

    # Generate code using a prompt
    code = await agent.generate(
        "test-generator",
        function_name="fetch_items",
        module_path="src/dmarket/api.py",
    )

    # Execute a skill
    result = await agent.execute_skill(
        "ai-arbitrage-predictor",
        "predict",
        items,
    )
    ```

Created: January 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from src.copilot_sdk.instruction_matcher import InstructionMatcher
from src.copilot_sdk.prompt_engine import PromptEngine
from src.copilot_sdk.skill_registry import SkillRegistry

logger = structlog.get_logger(__name__)


@dataclass
class AgentConfig:
    """Configuration for CopilotAgent."""

    instructions_dir: str = ".github/instructions"
    prompts_dir: str = ".github/prompts"
    skills_dir: str = "src/"
    auto_discover: bool = True
    cache_enabled: bool = True


@dataclass
class CopilotContext:
    """Context for a specific file or operation."""

    file_path: str
    instructions: list[str]
    instruction_content: str
    skills: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


class CopilotAgent:
    """High-level interface for Copilot SDK.

    Combines InstructionMatcher, PromptEngine, and SkillRegistry
    into a unified API for AI-assisted development.

    Example:
        ```python
        agent = CopilotAgent()
        await agent.initialize()

        # Get full context for a file
        context = await agent.get_context("src/api/client.py")
        print(f"Instructions: {context.instructions}")
        print(f"Skills: {context.skills}")

        # Generate code
        code = await agent.generate(
            "python-async",
            function_name="fetch_data",
            return_type="dict",
        )

        # Execute skill
        result = await agent.execute_skill(
            "price-predictor",
            "predict",
            item_data,
        )
        ```
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        """Initialize the Copilot Agent.

        Args:
            config: Agent configuration
        """
        self.config = config or AgentConfig()
        self.instructions = InstructionMatcher()
        self.prompts = PromptEngine()
        self.skills = SkillRegistry()
        self._initialized = False

    async def initialize(self, project_root: str | Path | None = None) -> None:
        """Initialize all components.

        Args:
            project_root: Root directory of the project
        """
        root = Path(project_root) if project_root else Path.cwd()

        # Load instructions
        instructions_path = root / self.config.instructions_dir
        await self.instructions.load_instructions(instructions_path)

        # Load prompts
        prompts_path = root / self.config.prompts_dir
        await self.prompts.load_prompts(prompts_path)

        # Discover skills
        if self.config.auto_discover:
            skills_path = root / self.config.skills_dir
            await self.skills.discover_skills(skills_path)

        self._initialized = True
        logger.info(
            "copilot_agent_initialized",
            instructions=len(self.instructions.instructions),
            prompts=len(self.prompts.templates),
            skills=len(self.skills.skills),
        )

    async def get_context(self, file_path: str) -> CopilotContext:
        """Get full context for a file.

        Args:
            file_path: Path to the file

        Returns:
            CopilotContext with all relevant information
        """
        self._ensure_initialized()

        # Get matching instructions
        instruction_names = await self.instructions.get_instructions(file_path)
        instruction_content = await self.instructions.get_merged_instructions(file_path)

        # Get relevant skills based on file path
        relevant_skills = self._get_relevant_skills(file_path)

        return CopilotContext(
            file_path=file_path,
            instructions=instruction_names,
            instruction_content=instruction_content,
            skills=relevant_skills,
            metadata={
                "prompts_available": list(self.prompts.templates.keys()),
            },
        )

    def _get_relevant_skills(self, file_path: str) -> list[str]:
        """Get skills relevant to a file path."""
        relevant = []
        path_lower = file_path.lower()

        for skill in self.skills.skills.values():
            category = skill.category.lower()

            # Match by category and file path
            if (
                ("trading" in path_lower and "trading" in category)
                or ("ml" in path_lower and ("ai" in category or "ml" in category))
                or ("api" in path_lower and "integration" in category)
                or ("test" in path_lower and "testing" in category)
            ):
                relevant.append(skill.id)

        return relevant

    async def generate(self, prompt_id: str, **variables: Any) -> str:
        """Generate content using a prompt template.

        Args:
            prompt_id: ID of the prompt template
            **variables: Variables to substitute

        Returns:
            Generated content
        """
        self._ensure_initialized()
        return await self.prompts.render(prompt_id, **variables)

    async def execute_skill(
        self,
        skill_id: str,
        method: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute a skill method.

        Args:
            skill_id: ID of the skill
            method: Method to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of skill execution
        """
        self._ensure_initialized()
        return await self.skills.execute(skill_id, method, *args, **kwargs)

    def register_skill(
        self,
        skill_id: str,
        instance: Any,
        name: str | None = None,
        methods: list[str] | None = None,
    ) -> None:
        """Register a skill with the agent.

        Args:
            skill_id: Unique skill ID
            instance: Skill instance
            name: Human-readable name
            methods: List of methods
        """
        self.skills.register(
            id=skill_id,
            name=name or skill_id,
            instance=instance,
            methods=methods,
        )

    def add_prompt(
        self,
        prompt_id: str,
        template: str,
        name: str | None = None,
        description: str = "",
    ) -> None:
        """Add a prompt template.

        Args:
            prompt_id: Unique prompt ID
            template: Template content
            name: Human-readable name
            description: Description
        """
        # Use asyncio to call the async method synchronously in this context
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.prompts.add_template(prompt_id, template, name, description))
        except RuntimeError:
            asyncio.run(self.prompts.add_template(prompt_id, template, name, description))

    def _ensure_initialized(self) -> None:
        """Ensure the agent is initialized."""
        if not self._initialized:
            raise RuntimeError(
                "CopilotAgent not initialized. Call `await agent.initialize()` first."
            )

    def get_status(self) -> dict[str, Any]:
        """Get agent status.

        Returns:
            Status dictionary
        """
        return {
            "initialized": self._initialized,
            "instructions_count": len(self.instructions.instructions),
            "prompts_count": len(self.prompts.templates),
            "skills_count": len(self.skills.skills),
            "config": {
                "instructions_dir": self.config.instructions_dir,
                "prompts_dir": self.config.prompts_dir,
                "skills_dir": self.config.skills_dir,
            },
        }


# Convenience function for quick setup
async def create_agent(project_root: str | Path | None = None) -> CopilotAgent:
    """Create and initialize a CopilotAgent.

    Args:
        project_root: Root directory of the project

    Returns:
        Initialized CopilotAgent
    """
    agent = CopilotAgent()
    await agent.initialize(project_root)
    return agent
