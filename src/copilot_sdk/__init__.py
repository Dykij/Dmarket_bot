"""GitHub Copilot SDK - Integration library for enhanced Copilot experience.

This module provides tools for integrating GitHub Copilot into Python projects:
- InstructionMatcher: Auto-apply instructions based on file patterns
- PromptEngine: Template-based prompt management
- SkillRegistry: Skill discovery and management
- CopilotAgent: High-level interface for AI operations
- AutonomousAgent: Autonomous task execution
- FileEditor: AI-powered file editing
- ProjectIndexer: Project-wide semantic search

Created: January 2026
Version: 1.1.0
"""

from src.copilot_sdk.autonomous_agent import AutonomousAgent
from src.copilot_sdk.copilot_agent import CopilotAgent
from src.copilot_sdk.file_editor import FileEditor
from src.copilot_sdk.instruction_matcher import InstructionMatcher
from src.copilot_sdk.project_indexer import ProjectIndexer
from src.copilot_sdk.prompt_engine import PromptEngine
from src.copilot_sdk.skill_registry import SkillRegistry

__all__ = [
    "InstructionMatcher",
    "PromptEngine",
    "SkillRegistry",
    "CopilotAgent",
    "AutonomousAgent",
    "FileEditor",
    "ProjectIndexer",
]

__version__ = "1.1.0"
