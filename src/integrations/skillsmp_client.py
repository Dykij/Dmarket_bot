"""SkillsMP API Client - AI-powered code improvements and recommendations.

This module provides integration with SkillsMP.com API for:
- Finding AI skills for testing improvements
- Getting code quality recommendations
- Discovering automation opportunities

Usage:
    ```python
    from src.integrations.skillsmp_client import SkillsMPClient, get_skillsmp_client

    # Using environment variable
    client = get_skillsmp_client()

    # Search for testing improvements
    skills = await client.search_skills(
        category="testing",
        tags=["python", "pytest", "asyncio"],
    )

    # Get recommendations for a repository
    recommendations = await client.get_recommendations(
        repo_url="https://github.com/user/repo",
        focus=["testing", "performance", "security"],
    )
    ```

Created: January 2026
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Skill:
    """Represents a skill from SkillsMP marketplace."""

    id: str
    name: str
    description: str
    category: str
    author: str
    version: str = "1.0.0"
    rating: float = 0.0
    downloads: int = 0
    tags: list[str] = field(default_factory=list)
    pricing: dict[str, Any] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)
    integration: dict[str, Any] = field(default_factory=dict)


@dataclass
class Recommendation:
    """A code improvement recommendation."""

    id: str
    title: str
    description: str
    category: str
    priority: str  # high, medium, low
    impact: str  # high, medium, low
    effort: str  # high, medium, low
    suggested_skills: list[str] = field(default_factory=list)
    code_examples: list[dict[str, str]] = field(default_factory=list)
    references: list[str] = field(default_factory=list)


class SkillsMPClient:
    """Client for SkillsMP.com API.

    Provides methods for:
    - Searching skills by category, tags, or keywords
    - Getting recommendations for repositories
    - Downloading and integrating skills

    Example:
        ```python
        client = SkillsMPClient(api_key="sk_live_...")

        # Search for testing skills
        skills = await client.search_skills(
            category="testing",
            query="property based testing",
        )

        # Get improvement recommendations
        recs = await client.get_recommendations(
            repo_url="https://github.com/user/repo",
        )
        ```
    """

    BASE_URL = "https://skillsmp.com/api/v1"

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize the SkillsMP client.

        Args:
            api_key: SkillsMP API key (sk_live_...)
            base_url: Optional custom base URL
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "DMarket-Telegram-Bot/1.0",
                },
            )
        return self._client

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make an API request.

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request arguments

        Returns:
            API response data

        Raises:
            httpx.HTTPError: If request fails
        """
        client = await self._get_client()

        logger.debug(
            "skillsmp_request",
            method=method,
            endpoint=endpoint,
        )

        try:
            response = await client.request(method, endpoint, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "skillsmp_api_error",
                status_code=e.response.status_code,
                endpoint=endpoint,
                error=str(e),
            )
            raise
        except httpx.RequestError as e:
            logger.error(
                "skillsmp_request_error",
                endpoint=endpoint,
                error=str(e),
            )
            raise

    async def search_skills(
        self,
        query: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        min_rating: float = 0.0,
        limit: int = 20,
    ) -> list[Skill]:
        """Search for skills in the marketplace.

        Args:
            query: Search query string
            category: Filter by category (testing, automation, ai, etc.)
            tags: Filter by tags
            min_rating: Minimum rating filter
            limit: Maximum results to return

        Returns:
            List of matching skills
        """
        params: dict[str, Any] = {"limit": limit}
        if query:
            params["q"] = query
        if category:
            params["category"] = category
        if tags:
            params["tags"] = ",".join(tags)
        if min_rating > 0:
            params["min_rating"] = min_rating

        data = await self._request("GET", "/skills/search", params=params)

        skills = []
        for item in data.get("skills", []):
            skills.append(
                Skill(
                    id=item.get("id", ""),
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    category=item.get("category", ""),
                    author=item.get("author", ""),
                    version=item.get("version", "1.0.0"),
                    rating=item.get("rating", 0.0),
                    downloads=item.get("downloads", 0),
                    tags=item.get("tags", []),
                    pricing=item.get("pricing", {}),
                    capabilities=item.get("capabilities", []),
                    integration=item.get("integration", {}),
                )
            )

        logger.info(
            "skillsmp_search_completed",
            query=query,
            category=category,
            results=len(skills),
        )
        return skills

    async def get_skill(self, skill_id: str) -> Skill | None:
        """Get details for a specific skill.

        Args:
            skill_id: Skill ID

        Returns:
            Skill details or None if not found
        """
        try:
            data = await self._request("GET", f"/skills/{skill_id}")
            item = data.get("skill", {})
            return Skill(
                id=item.get("id", skill_id),
                name=item.get("name", ""),
                description=item.get("description", ""),
                category=item.get("category", ""),
                author=item.get("author", ""),
                version=item.get("version", "1.0.0"),
                rating=item.get("rating", 0.0),
                downloads=item.get("downloads", 0),
                tags=item.get("tags", []),
                pricing=item.get("pricing", {}),
                capabilities=item.get("capabilities", []),
                integration=item.get("integration", {}),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def get_recommendations(
        self,
        repo_url: str | None = None,
        languages: list[str] | None = None,
        focus: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[Recommendation]:
        """Get improvement recommendations for a repository.

        Args:
            repo_url: GitHub repository URL
            languages: Programming languages used
            focus: Areas to focus on (testing, security, performance)
            context: Additional context about the project

        Returns:
            List of recommendations
        """
        payload: dict[str, Any] = {}
        if repo_url:
            payload["repo_url"] = repo_url
        if languages:
            payload["languages"] = languages
        if focus:
            payload["focus"] = focus
        if context:
            payload["context"] = context

        data = await self._request("POST", "/recommendations", json=payload)

        recommendations = []
        for item in data.get("recommendations", []):
            recommendations.append(
                Recommendation(
                    id=item.get("id", ""),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    category=item.get("category", ""),
                    priority=item.get("priority", "medium"),
                    impact=item.get("impact", "medium"),
                    effort=item.get("effort", "medium"),
                    suggested_skills=item.get("suggested_skills", []),
                    code_examples=item.get("code_examples", []),
                    references=item.get("references", []),
                )
            )

        logger.info(
            "skillsmp_recommendations_received",
            repo_url=repo_url,
            count=len(recommendations),
        )
        return recommendations

    async def get_testing_improvements(
        self,
        languages: list[str] | None = None,
        frameworks: list[str] | None = None,
        current_coverage: float = 0.0,
    ) -> list[Recommendation]:
        """Get testing-specific improvement recommendations.

        Args:
            languages: Programming languages
            frameworks: Testing frameworks used (pytest, unittest, etc.)
            current_coverage: Current test coverage percentage

        Returns:
            List of testing recommendations
        """
        payload: dict[str, Any] = {
            "type": "testing",
            "current_coverage": current_coverage,
        }
        if languages:
            payload["languages"] = languages
        if frameworks:
            payload["frameworks"] = frameworks

        data = await self._request("POST", "/recommendations/testing", json=payload)

        recommendations = []
        for item in data.get("recommendations", []):
            recommendations.append(
                Recommendation(
                    id=item.get("id", ""),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    category="testing",
                    priority=item.get("priority", "medium"),
                    impact=item.get("impact", "medium"),
                    effort=item.get("effort", "medium"),
                    suggested_skills=item.get("suggested_skills", []),
                    code_examples=item.get("code_examples", []),
                    references=item.get("references", []),
                )
            )

        return recommendations

    async def analyze_repository(
        self,
        repo_url: str,
        include_tests: bool = True,
        include_security: bool = True,
        include_performance: bool = True,
    ) -> dict[str, Any]:
        """Perform comprehensive repository analysis.

        Args:
            repo_url: GitHub repository URL
            include_tests: Include testing analysis
            include_security: Include security analysis
            include_performance: Include performance analysis

        Returns:
            Analysis results
        """
        payload = {
            "repo_url": repo_url,
            "include_tests": include_tests,
            "include_security": include_security,
            "include_performance": include_performance,
        }

        data = await self._request("POST", "/analyze", json=payload)

        logger.info(
            "skillsmp_analysis_completed",
            repo_url=repo_url,
            score=data.get("overall_score"),
        )
        return data

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


def get_skillsmp_client() -> SkillsMPClient | None:
    """Get a SkillsMP client using environment variables.

    Returns:
        SkillsMPClient if API key is configured, None otherwise
    """
    api_key = os.getenv("SKILLSMP_API_KEY")
    if not api_key:
        logger.warning("skillsmp_api_key_not_set")
        return None

    base_url = os.getenv("SKILLSMP_API_URL")
    return SkillsMPClient(api_key=api_key, base_url=base_url)


# Pre-defined categories for searching
SKILL_CATEGORIES = {
    "testing": "Testing & QA automation",
    "security": "Security scanning & auditing",
    "performance": "Performance optimization",
    "automation": "CI/CD & workflow automation",
    "ai": "AI/ML integration",
    "documentation": "Documentation generation",
    "code-quality": "Code quality & linting",
    "monitoring": "Monitoring & observability",
}

# Pre-defined tags for DMarket bot improvements
RECOMMENDED_TAGS = [
    "python",
    "pytest",
    "asyncio",
    "telegram-bot",
    "trading",
    "api-integration",
    "property-based-testing",
    "mutation-testing",
    "contract-testing",
    "load-testing",
]
