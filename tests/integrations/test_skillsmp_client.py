"""Tests for SkillsMP API Client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.integrations.skillsmp_client import (
    RECOMMENDED_TAGS,
    SKILL_CATEGORIES,
    Recommendation,
    Skill,
    SkillsMPClient,
    get_skillsmp_client,
)


class TestSkillsMPClient:
    """Tests for SkillsMPClient class."""

    @pytest.fixture()
    def client(self):
        """Create a test client."""
        return SkillsMPClient(api_key="test_key_123")

    @pytest.fixture()
    def mock_response(self):
        """Create a mock HTTP response."""
        response = MagicMock()
        response.status_code = 200
        response.raise_for_status = MagicMock()
        return response

    def test_client_initialization(self):
        """Test client initializes with correct values."""
        # Arrange & Act
        client = SkillsMPClient(
            api_key="test_key",
            base_url="https://custom.api.com",
            timeout=60.0,
        )

        # Assert
        assert client.api_key == "test_key"
        assert client.base_url == "https://custom.api.com"
        assert client.timeout == 60.0

    def test_client_default_base_url(self):
        """Test client uses default base URL."""
        # Arrange & Act
        client = SkillsMPClient(api_key="test")

        # Assert
        assert client.base_url == "https://api.skillsmp.com/v1"

    @pytest.mark.asyncio()
    async def test_search_skills_returns_skills(self, client):
        """Test skill search returns skill objects."""
        # Arrange
        mock_data = {
            "skills": [
                {
                    "id": "skill-1",
                    "name": "Test Skill",
                    "description": "A test skill",
                    "category": "testing",
                    "author": "test_author",
                    "rating": 4.5,
                    "downloads": 1000,
                    "tags": ["python", "pytest"],
                },
            ]
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data

            # Act
            skills = await client.search_skills(
                query="test",
                category="testing",
                tags=["python"],
            )

            # Assert
            assert len(skills) == 1
            assert skills[0].id == "skill-1"
            assert skills[0].name == "Test Skill"
            assert skills[0].rating == 4.5
            mock_request.assert_called_once()

    @pytest.mark.asyncio()
    async def test_search_skills_empty_results(self, client):
        """Test skill search with no results."""
        # Arrange
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"skills": []}

            # Act
            skills = await client.search_skills(query="nonexistent")

            # Assert
            assert len(skills) == 0

    @pytest.mark.asyncio()
    async def test_get_skill_returns_skill(self, client):
        """Test getting a specific skill."""
        # Arrange
        mock_data = {
            "skill": {
                "id": "skill-123",
                "name": "Specific Skill",
                "description": "Details",
                "category": "security",
                "author": "author",
            }
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data

            # Act
            skill = await client.get_skill("skill-123")

            # Assert
            assert skill is not None
            assert skill.id == "skill-123"
            assert skill.name == "Specific Skill"

    @pytest.mark.asyncio()
    async def test_get_skill_not_found(self, client):
        """Test getting a non-existent skill."""
        # Arrange
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            error = httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=MagicMock(status_code=404),
            )
            mock_request.side_effect = error

            # Act
            skill = await client.get_skill("nonexistent")

            # Assert
            assert skill is None

    @pytest.mark.asyncio()
    async def test_get_recommendations(self, client):
        """Test getting repository recommendations."""
        # Arrange
        mock_data = {
            "recommendations": [
                {
                    "id": "rec-1",
                    "title": "Add mutation testing",
                    "description": "Improve test quality",
                    "category": "testing",
                    "priority": "high",
                    "impact": "high",
                    "effort": "medium",
                },
            ]
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data

            # Act
            recs = await client.get_recommendations(
                repo_url="https://github.com/test/repo",
                focus=["testing"],
            )

            # Assert
            assert len(recs) == 1
            assert recs[0].title == "Add mutation testing"
            assert recs[0].priority == "high"

    @pytest.mark.asyncio()
    async def test_get_testing_improvements(self, client):
        """Test getting testing-specific improvements."""
        # Arrange
        mock_data = {
            "recommendations": [
                {
                    "id": "test-1",
                    "title": "Add property-based tests",
                    "description": "Use Hypothesis",
                    "priority": "medium",
                    "impact": "high",
                    "effort": "low",
                },
            ]
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data

            # Act
            recs = await client.get_testing_improvements(
                languages=["python"],
                frameworks=["pytest"],
                current_coverage=85.0,
            )

            # Assert
            assert len(recs) == 1
            assert recs[0].category == "testing"

    @pytest.mark.asyncio()
    async def test_analyze_repository(self, client):
        """Test repository analysis."""
        # Arrange
        mock_data = {
            "overall_score": 85,
            "testing": {"score": 90, "coverage": 85},
            "security": {"score": 80, "issues": 2},
            "performance": {"score": 85},
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data

            # Act
            result = await client.analyze_repository(
                repo_url="https://github.com/test/repo",
            )

            # Assert
            assert result["overall_score"] == 85
            assert result["testing"]["coverage"] == 85

    @pytest.mark.asyncio()
    async def test_close_client(self, client):
        """Test closing the client."""
        # Arrange
        mock_http_client = AsyncMock()
        client._client = mock_http_client

        # Act
        await client.close()

        # Assert
        mock_http_client.aclose.assert_called_once()


class TestGetSkillsMPClient:
    """Tests for get_skillsmp_client function."""

    def test_returns_none_without_api_key(self):
        """Test returns None when API key not set."""
        # Arrange
        with patch.dict("os.environ", {}, clear=True):
            # Act
            client = get_skillsmp_client()

            # Assert
            assert client is None

    def test_returns_client_with_api_key(self):
        """Test returns client when API key is set."""
        # Arrange
        with patch.dict("os.environ", {"SKILLSMP_API_KEY": "test_key"}):
            # Act
            client = get_skillsmp_client()

            # Assert
            assert client is not None
            assert isinstance(client, SkillsMPClient)
            assert client.api_key == "test_key"

    def test_uses_custom_base_url(self):
        """Test uses custom base URL from environment."""
        # Arrange
        with patch.dict(
            "os.environ",
            {
                "SKILLSMP_API_KEY": "test_key",
                "SKILLSMP_API_URL": "https://custom.api.com",
            },
        ):
            # Act
            client = get_skillsmp_client()

            # Assert
            assert client.base_url == "https://custom.api.com"


class TestDataClasses:
    """Tests for Skill and Recommendation dataclasses."""

    def test_skill_creation(self):
        """Test Skill dataclass creation."""
        # Arrange & Act
        skill = Skill(
            id="test-id",
            name="Test Skill",
            description="A test",
            category="testing",
            author="test_author",
            rating=4.5,
            downloads=100,
            tags=["python"],
        )

        # Assert
        assert skill.id == "test-id"
        assert skill.rating == 4.5
        assert skill.tags == ["python"]

    def test_recommendation_creation(self):
        """Test Recommendation dataclass creation."""
        # Arrange & Act
        rec = Recommendation(
            id="rec-1",
            title="Test Rec",
            description="Description",
            category="testing",
            priority="high",
            impact="high",
            effort="low",
            suggested_skills=["skill-1"],
        )

        # Assert
        assert rec.id == "rec-1"
        assert rec.priority == "high"
        assert rec.suggested_skills == ["skill-1"]


class TestConstants:
    """Tests for module constants."""

    def test_skill_categories_defined(self):
        """Test skill categories are defined."""
        assert "testing" in SKILL_CATEGORIES
        assert "security" in SKILL_CATEGORIES
        assert "performance" in SKILL_CATEGORIES

    def test_recommended_tags_defined(self):
        """Test recommended tags are defined."""
        assert "python" in RECOMMENDED_TAGS
        assert "pytest" in RECOMMENDED_TAGS
        assert "asyncio" in RECOMMENDED_TAGS
