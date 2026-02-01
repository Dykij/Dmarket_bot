"""SkillsMP.com Integration Client.

This module provides a client for interacting with SkillsMP.com marketplace
to discover, install, and manage AI skills for the MCP server.

Based on SkillsMP MCP Integration Skill recommendations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore


logger = logging.getLogger(__name__)


# SkillsMP.com API endpoints
SKILLSMP_BASE_URL = "https://skillsmp.com"
SKILLSMP_API_URL = f"{SKILLSMP_BASE_URL}/api"
SKILLSMP_CATEGORIES_URL = f"{SKILLSMP_BASE_URL}/categories"


@dataclass
class Skill:
    """Represents a skill from SkillsMP.com marketplace."""

    name: str
    description: str
    category: str
    version: str = "1.0.0"
    author: str = ""
    stars: int = 0
    url: str = ""
    dependencies: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    installed: bool = False
    installed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert skill to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "author": self.author,
            "stars": self.stars,
            "url": self.url,
            "dependencies": self.dependencies,
            "tags": self.tags,
            "installed": self.installed,
            "installed_at": (
                self.installed_at.isoformat() if self.installed_at else None
            ),
        }


class SkillsMPIntegration:
    """Client for SkillsMP.com marketplace integration.

    Features:
    - Discover skills from marketplace
    - Search by category, tags, or keywords
    - Install/uninstall skills
    - Manage skill dependencies
    - Track installed skills

    Example:
        >>> client = SkillsMPIntegration()
        >>> skills = await client.discover_skills(category="Data & AI")
        >>> await client.install_skill("ai-arbitrage-predictor")
    """

    # Popular categories on SkillsMP.com
    CATEGORIES = [
        "Data & AI",
        "DevOps",
        "Testing & Security",
        "Development",
        "Containers",
        "CI/CD",
        "Cloud",
        "Database",
    ]

    def __init__(
        self,
        base_url: str = SKILLSMP_BASE_URL,
        skills_dir: str | Path | None = None,
        timeout: float = 30.0,
    ):
        """Initialize SkillsMP integration client.

        Args:
            base_url: SkillsMP.com base URL
            skills_dir: Directory to store installed skills
            timeout: HTTP request timeout in seconds
        """
        self._base_url = base_url
        self._skills_dir = Path(skills_dir) if skills_dir else Path(".skills")
        self._timeout = timeout
        self._installed_skills: dict[str, Skill] = {}
        self._cache: dict[str, Any] = {}
        self._cache_ttl = 3600  # 1 hour

    async def discover_skills(
        self,
        category: str | None = None,
        min_stars: int = 0,
        limit: int = 50,
    ) -> list[Skill]:
        """Discover available skills from SkillsMP.com.

        Args:
            category: Filter by category
            min_stars: Minimum star rating
            limit: Maximum number of skills to return

        Returns:
            List of discovered skills
        """
        cache_key = f"discover:{category}:{min_stars}:{limit}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if cached["expires"] > datetime.now(timezone.utc):
                return cached["data"]

        # For now, return mock data based on known skills
        # In production, this would call the SkillsMP API
        skills = self._get_known_skills()

        # Filter by category
        if category:
            skills = [s for s in skills if s.category == category]

        # Filter by stars
        skills = [s for s in skills if s.stars >= min_stars]

        # Apply limit
        skills = skills[:limit]

        # Cache results
        self._cache[cache_key] = {
            "data": skills,
            "expires": datetime.now(timezone.utc),
        }

        logger.info(
            "discovered_skills",
            extra={
                "count": len(skills),
                "category": category,
                "min_stars": min_stars,
            },
        )

        return skills

    async def search_skills(
        self,
        query: str,
        category: str | None = None,
        min_stars: int = 0,
    ) -> list[Skill]:
        """Search skills by keyword.

        Args:
            query: Search query
            category: Optional category filter
            min_stars: Minimum star rating

        Returns:
            List of matching skills
        """
        all_skills = await self.discover_skills(category, min_stars)
        query_lower = query.lower()

        # Search in name, description, and tags
        results = [
            skill
            for skill in all_skills
            if query_lower in skill.name.lower()
            or query_lower in skill.description.lower()
            or any(query_lower in tag.lower() for tag in skill.tags)
        ]

        logger.info(
            "searched_skills",
            extra={"query": query, "results": len(results)},
        )

        return results

    async def install_skill(
        self,
        skill_name: str,
        version: str = "latest",
    ) -> bool:
        """Install a skill from the marketplace.

        Args:
            skill_name: Name of the skill to install
            version: Version to install (default: latest)

        Returns:
            True if installation successful
        """
        # Find skill in known skills
        skills = self._get_known_skills()
        skill = next((s for s in skills if s.name == skill_name), None)

        if not skill:
            logger.warning("skill_not_found", extra={"skill_name": skill_name})
            return False

        # Create skills directory
        self._skills_dir.mkdir(parents=True, exist_ok=True)

        # Mark as installed
        skill.installed = True
        skill.installed_at = datetime.now(timezone.utc)
        self._installed_skills[skill_name] = skill

        logger.info(
            "skill_installed",
            extra={
                "skill_name": skill_name,
                "version": version,
            },
        )

        return True

    async def uninstall_skill(self, skill_name: str) -> bool:
        """Uninstall a skill.

        Args:
            skill_name: Name of the skill to uninstall

        Returns:
            True if uninstallation successful
        """
        if skill_name not in self._installed_skills:
            logger.warning("skill_not_installed", extra={"skill_name": skill_name})
            return False

        del self._installed_skills[skill_name]

        logger.info("skill_uninstalled", extra={"skill_name": skill_name})

        return True

    async def update_skill(
        self,
        skill_name: str,
        version: str = "latest",
    ) -> bool:
        """Update an installed skill.

        Args:
            skill_name: Name of the skill to update
            version: Version to update to

        Returns:
            True if update successful
        """
        if skill_name not in self._installed_skills:
            return False

        # Re-install with new version
        await self.uninstall_skill(skill_name)
        return await self.install_skill(skill_name, version)

    async def list_installed_skills(self) -> list[Skill]:
        """List all installed skills.

        Returns:
            List of installed skills
        """
        return list(self._installed_skills.values())

    async def get_skill_info(self, skill_name: str) -> Skill | None:
        """Get detailed information about a skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Skill details or None if not found
        """
        skills = self._get_known_skills()
        return next((s for s in skills if s.name == skill_name), None)

    async def get_latest_version(self, skill_name: str) -> str | None:
        """Get the latest version of a skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Latest version string or None
        """
        skill = await self.get_skill_info(skill_name)
        return skill.version if skill else None

    def _get_known_skills(self) -> list[Skill]:
        """Get list of known skills from SkillsMP.com.

        This is a static list based on the research report.
        In production, this would be fetched from the API.
        """
        return [
            Skill(
                name="docker-optimization",
                description="Docker image optimization with BuildKit, multi-stage builds, and security best practices",
                category="Containers",
                version="1.2.0",
                author="SkillsMP",
                stars=5,
                url=f"{SKILLSMP_BASE_URL}/skills/docker-optimization",
                dependencies=["docker>=20.10"],
                tags=["docker", "containers", "optimization", "buildkit"],
            ),
            Skill(
                name="github-actions-templates",
                description="Production-ready GitHub Actions workflow templates",
                category="CI/CD",
                version="2.0.0",
                author="SkillsMP",
                stars=4,
                url=f"{SKILLSMP_BASE_URL}/skills/github-actions-templates",
                dependencies=[],
                tags=["github", "actions", "ci/cd", "workflows"],
            ),
            Skill(
                name="redis-caching",
                description="Redis caching patterns with TTL, invalidation, and distributed locking",
                category="Database",
                version="1.5.0",
                author="SkillsMP",
                stars=5,
                url=f"{SKILLSMP_BASE_URL}/skills/redis-caching",
                dependencies=["redis>=4.0"],
                tags=["redis", "caching", "distributed", "locking"],
            ),
            Skill(
                name="mcp-integration",
                description="MCP server integration for Claude and other AI tools",
                category="Data & AI",
                version="1.0.0",
                author="SkillsMP",
                stars=4,
                url=f"{SKILLSMP_BASE_URL}/skills/mcp-integration",
                dependencies=["httpx>=0.28", "pydantic>=2.5"],
                tags=["mcp", "ai", "claude", "integration"],
            ),
            Skill(
                name="ai-arbitrage-predictor",
                description="ML-based arbitrage prediction with ensemble models",
                category="Data & AI",
                version="1.1.0",
                author="SkillsMP",
                stars=5,
                url=f"{SKILLSMP_BASE_URL}/skills/ai-arbitrage-predictor",
                dependencies=["scikit-learn>=1.0", "numpy>=1.24"],
                tags=["ml", "arbitrage", "prediction", "trading"],
            ),
            Skill(
                name="telegram-nlp-handler",
                description="NLP-powered Telegram message handler",
                category="Data & AI",
                version="1.0.0",
                author="SkillsMP",
                stars=3,
                url=f"{SKILLSMP_BASE_URL}/skills/telegram-nlp-handler",
                dependencies=["python-telegram-bot>=22.0"],
                tags=["telegram", "nlp", "bot", "handler"],
            ),
            Skill(
                name="portfolio-risk-assessor",
                description="Portfolio risk assessment with VaR calculations",
                category="Data & AI",
                version="1.0.0",
                author="SkillsMP",
                stars=4,
                url=f"{SKILLSMP_BASE_URL}/skills/portfolio-risk-assessor",
                dependencies=["pandas>=2.0", "scipy>=1.10"],
                tags=["portfolio", "risk", "finance", "var"],
            ),
            Skill(
                name="structlog-json",
                description="Structured JSON logging with context binding",
                category="DevOps",
                version="1.3.0",
                author="SkillsMP",
                stars=5,
                url=f"{SKILLSMP_BASE_URL}/skills/structlog-json",
                dependencies=["structlog>=24.1"],
                tags=["logging", "structlog", "json", "observability"],
            ),
            Skill(
                name="sqlalchemy-profiler",
                description="SQL query profiling and slow query detection",
                category="Database",
                version="1.0.0",
                author="SkillsMP",
                stars=4,
                url=f"{SKILLSMP_BASE_URL}/skills/sqlalchemy-profiler",
                dependencies=["sqlalchemy>=2.0"],
                tags=["sql", "profiling", "database", "performance"],
            ),
            Skill(
                name="container-security",
                description="Container security scanning with Trivy and SBOM generation",
                category="Testing & Security",
                version="1.2.0",
                author="SkillsMP",
                stars=5,
                url=f"{SKILLSMP_BASE_URL}/skills/container-security",
                dependencies=[],
                tags=["security", "containers", "trivy", "sbom"],
            ),
        ]


# Singleton instance
_skillsmp_client: SkillsMPIntegration | None = None


def get_skillsmp_client() -> SkillsMPIntegration:
    """Get or create global SkillsMP client.

    Returns:
        SkillsMPIntegration instance
    """
    global _skillsmp_client
    if _skillsmp_client is None:
        _skillsmp_client = SkillsMPIntegration()
    return _skillsmp_client
