"""Tests for SkillsMP.com Integration Client.

Based on SkillsMP recommendations for testing marketplace integration.
"""

import pytest

from src.mcp_server.skillsmp_client import (
    Skill,
    SkillsMPIntegration,
    get_skillsmp_client,
)


class TestSkill:
    """Tests for Skill dataclass."""

    def test_skill_creation(self):
        """Test creating a skill."""
        # Act
        skill = Skill(
            name="test-skill",
            description="Test skill description",
            category="Testing",
            version="1.0.0",
            author="Test Author",
            stars=5,
        )

        # Assert
        assert skill.name == "test-skill"
        assert skill.description == "Test skill description"
        assert skill.category == "Testing"
        assert skill.version == "1.0.0"
        assert skill.stars == 5
        assert skill.installed is False

    def test_skill_to_dict(self):
        """Test converting skill to dictionary."""
        # Arrange
        skill = Skill(
            name="test-skill",
            description="Test description",
            category="Testing",
            tags=["test", "example"],
        )

        # Act
        result = skill.to_dict()

        # Assert
        assert result["name"] == "test-skill"
        assert result["description"] == "Test description"
        assert result["tags"] == ["test", "example"]
        assert result["installed"] is False
        assert result["installed_at"] is None

    def test_skill_default_values(self):
        """Test skill default values."""
        # Act
        skill = Skill(
            name="minimal-skill",
            description="Minimal",
            category="Test",
        )

        # Assert
        assert skill.version == "1.0.0"
        assert skill.author == ""
        assert skill.stars == 0
        assert skill.dependencies == []
        assert skill.tags == []


class TestSkillsMPIntegration:
    """Tests for SkillsMPIntegration class."""

    @pytest.fixture
    def client(self):
        """Create SkillsMP client."""
        return SkillsMPIntegration()

    @pytest.mark.asyncio
    async def test_discover_skills(self, client):
        """Test discovering skills."""
        # Act
        skills = await client.discover_skills()

        # Assert
        assert len(skills) > 0
        assert all(isinstance(s, Skill) for s in skills)

    @pytest.mark.asyncio
    async def test_discover_skills_by_category(self, client):
        """Test discovering skills filtered by category."""
        # Act
        skills = await client.discover_skills(category="Data & AI")

        # Assert
        assert len(skills) > 0
        assert all(s.category == "Data & AI" for s in skills)

    @pytest.mark.asyncio
    async def test_discover_skills_with_min_stars(self, client):
        """Test discovering skills with minimum stars filter."""
        # Act
        skills = await client.discover_skills(min_stars=4)

        # Assert
        assert all(s.stars >= 4 for s in skills)

    @pytest.mark.asyncio
    async def test_discover_skills_with_limit(self, client):
        """Test discovering skills with limit."""
        # Act
        skills = await client.discover_skills(limit=3)

        # Assert
        assert len(skills) <= 3

    @pytest.mark.asyncio
    async def test_search_skills(self, client):
        """Test searching skills by keyword."""
        # Act
        results = await client.search_skills("docker")

        # Assert
        assert len(results) > 0
        assert any("docker" in s.name.lower() for s in results)

    @pytest.mark.asyncio
    async def test_search_skills_case_insensitive(self, client):
        """Test that search is case insensitive."""
        # Act
        results_lower = await client.search_skills("redis")
        results_upper = await client.search_skills("REDIS")

        # Assert
        assert len(results_lower) == len(results_upper)

    @pytest.mark.asyncio
    async def test_search_skills_by_tag(self, client):
        """Test searching skills by tag."""
        # Act
        results = await client.search_skills("caching")

        # Assert
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_install_skill(self, client):
        """Test installing a skill."""
        # Act
        success = await client.install_skill("docker-optimization")

        # Assert
        assert success is True
        installed = await client.list_installed_skills()
        assert any(s.name == "docker-optimization" for s in installed)

    @pytest.mark.asyncio
    async def test_install_nonexistent_skill(self, client):
        """Test installing a skill that doesn't exist."""
        # Act
        success = await client.install_skill("nonexistent-skill")

        # Assert
        assert success is False

    @pytest.mark.asyncio
    async def test_uninstall_skill(self, client):
        """Test uninstalling a skill."""
        # Arrange
        await client.install_skill("docker-optimization")

        # Act
        success = await client.uninstall_skill("docker-optimization")

        # Assert
        assert success is True
        installed = await client.list_installed_skills()
        assert not any(s.name == "docker-optimization" for s in installed)

    @pytest.mark.asyncio
    async def test_uninstall_not_installed_skill(self, client):
        """Test uninstalling a skill that's not installed."""
        # Act
        success = await client.uninstall_skill("not-installed-skill")

        # Assert
        assert success is False

    @pytest.mark.asyncio
    async def test_update_skill(self, client):
        """Test updating an installed skill."""
        # Arrange
        await client.install_skill("docker-optimization")

        # Act
        success = await client.update_skill("docker-optimization", "2.0.0")

        # Assert
        assert success is True

    @pytest.mark.asyncio
    async def test_update_not_installed_skill(self, client):
        """Test updating a skill that's not installed."""
        # Act
        success = await client.update_skill("not-installed-skill")

        # Assert
        assert success is False

    @pytest.mark.asyncio
    async def test_list_installed_skills(self, client):
        """Test listing installed skills."""
        # Arrange
        await client.install_skill("redis-caching")
        await client.install_skill("docker-optimization")

        # Act
        installed = await client.list_installed_skills()

        # Assert
        assert len(installed) == 2
        names = [s.name for s in installed]
        assert "redis-caching" in names
        assert "docker-optimization" in names

    @pytest.mark.asyncio
    async def test_get_skill_info(self, client):
        """Test getting skill information."""
        # Act
        skill = await client.get_skill_info("docker-optimization")

        # Assert
        assert skill is not None
        assert skill.name == "docker-optimization"
        assert skill.category == "Containers"
        assert skill.stars >= 0

    @pytest.mark.asyncio
    async def test_get_skill_info_not_found(self, client):
        """Test getting info for nonexistent skill."""
        # Act
        skill = await client.get_skill_info("nonexistent-skill")

        # Assert
        assert skill is None

    @pytest.mark.asyncio
    async def test_get_latest_version(self, client):
        """Test getting latest version of a skill."""
        # Act
        version = await client.get_latest_version("docker-optimization")

        # Assert
        assert version is not None
        assert isinstance(version, str)

    @pytest.mark.asyncio
    async def test_get_latest_version_not_found(self, client):
        """Test getting version for nonexistent skill."""
        # Act
        version = await client.get_latest_version("nonexistent-skill")

        # Assert
        assert version is None

    def test_categories(self, client):
        """Test that categories are defined."""
        # Assert
        assert len(client.CATEGORIES) > 0
        assert "Data & AI" in client.CATEGORIES
        assert "DevOps" in client.CATEGORIES
        assert "CI/CD" in client.CATEGORIES


class TestGetSkillsMPClient:
    """Tests for get_skillsmp_client function."""

    def test_singleton_creation(self):
        """Test singleton is created."""
        from src.mcp_server import skillsmp_client as module

        # Reset singleton
        module._skillsmp_client = None

        # Act
        client1 = get_skillsmp_client()
        client2 = get_skillsmp_client()

        # Assert
        assert client1 is client2
