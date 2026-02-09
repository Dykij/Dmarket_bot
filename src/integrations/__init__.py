"""Integrations module for external services."""

from src.integrations.skillsmp_client import (
    RECOMMENDED_TAGS,
    SKILL_CATEGORIES,
    Recommendation,
    Skill,
    SkillsMPClient,
    get_skillsmp_client,
)

__all__ = [
    "RECOMMENDED_TAGS",
    "SKILL_CATEGORIES",
    "Recommendation",
    "Skill",
    "SkillsMPClient",
    "get_skillsmp_client",
]
