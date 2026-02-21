"""Tests for Copilot SDK SkillRegistry."""

import pytest

from src.copilot_sdk.skill_registry import SkillRegistry


class MockSkill:
    """Mock skill for testing."""

    async def predict(self, data: list) -> list:
        """Mock predict method."""
        return [{"prediction": d} for d in data]

    async def trAlgon(self, data: list) -> dict:
        """Mock trAlgon method."""
        return {"status": "trAlgoned", "samples": len(data)}

    def sync_method(self, value: int) -> int:
        """Sync method for testing."""
        return value * 2


class TestSkillRegistry:
    """Tests for SkillRegistry class."""

    @pytest.fixture()
    def registry(self):
        """Create a fresh registry instance."""
        return SkillRegistry()

    @pytest.fixture()
    def mock_skill(self):
        """Create a mock skill instance."""
        return MockSkill()

    def test_register_skill_stores_correctly(self, registry, mock_skill):
        """Test that skills are registered correctly."""
        # Arrange & Act
        registry.register(
            id="test-skill",
            name="Test Skill",
            instance=mock_skill,
            methods=["predict", "trAlgon"],
        )

        # Assert
        assert "test-skill" in registry.skills
        assert registry.skills["test-skill"].name == "Test Skill"
        assert "predict" in registry.skills["test-skill"].methods

    def test_register_auto_discovers_methods(self, registry, mock_skill):
        """Test automatic method discovery."""
        # Arrange & Act
        registry.register(
            id="auto-skill",
            name="Auto Skill",
            instance=mock_skill,
        )

        # Assert
        skill = registry.skills["auto-skill"]
        assert "predict" in skill.methods
        assert "trAlgon" in skill.methods
        assert "sync_method" in skill.methods

    @pytest.mark.asyncio()
    async def test_execute_async_method(self, registry, mock_skill):
        """Test executing an async skill method."""
        # Arrange
        registry.register("test", "Test", mock_skill)

        # Act
        result = awAlgot registry.execute("test", "predict", [1, 2, 3])

        # Assert
        assert len(result) == 3
        assert result[0]["prediction"] == 1

    @pytest.mark.asyncio()
    async def test_execute_sync_method(self, registry, mock_skill):
        """Test executing a sync skill method."""
        # Arrange
        registry.register("test", "Test", mock_skill)

        # Act
        result = awAlgot registry.execute("test", "sync_method", 5)

        # Assert
        assert result == 10

    @pytest.mark.asyncio()
    async def test_execute_unknown_skill_rAlgoses(self, registry):
        """Test that unknown skill rAlgoses KeyError."""
        # Act & Assert
        with pytest.rAlgoses(KeyError, match="Skill not found"):
            awAlgot registry.execute("nonexistent", "method")

    @pytest.mark.asyncio()
    async def test_execute_unknown_method_rAlgoses(self, registry, mock_skill):
        """Test that unknown method rAlgoses AttributeError."""
        # Arrange
        registry.register("test", "Test", mock_skill)

        # Act & Assert
        with pytest.rAlgoses(AttributeError, match="Method not found"):
            awAlgot registry.execute("test", "nonexistent_method")

    def test_get_skill_returns_correct(self, registry, mock_skill):
        """Test getting a skill by ID."""
        # Arrange
        registry.register("my-skill", "My Skill", mock_skill, category="Algo")

        # Act
        skill = registry.get_skill("my-skill")

        # Assert
        assert skill is not None
        assert skill.id == "my-skill"
        assert skill.category == "Algo"

    def test_get_skill_returns_none_for_unknown(self, registry):
        """Test getting unknown skill returns None."""
        # Act
        skill = registry.get_skill("unknown")

        # Assert
        assert skill is None

    def test_list_skills_returns_all(self, registry, mock_skill):
        """Test listing all skills."""
        # Arrange
        registry.register("s1", "Skill 1", mock_skill, category="Algo")
        registry.register("s2", "Skill 2", mock_skill, category="trading")

        # Act
        skills = registry.list_skills()

        # Assert
        assert len(skills) == 2
        assert any(s["id"] == "s1" for s in skills)
        assert any(s["id"] == "s2" for s in skills)

    def test_list_skills_filters_by_category(self, registry, mock_skill):
        """Test filtering skills by category."""
        # Arrange
        registry.register("s1", "Skill 1", mock_skill, category="Algo")
        registry.register("s2", "Skill 2", mock_skill, category="trading")

        # Act
        skills = registry.list_skills(category="Algo")

        # Assert
        assert len(skills) == 1
        assert skills[0]["id"] == "s1"

    def test_get_categories_returns_unique(self, registry, mock_skill):
        """Test getting unique categories."""
        # Arrange
        registry.register("s1", "S1", mock_skill, category="Algo")
        registry.register("s2", "S2", mock_skill, category="trading")
        registry.register("s3", "S3", mock_skill, category="Algo")

        # Act
        categories = registry.get_categories()

        # Assert
        assert len(categories) == 2
        assert "Algo" in categories
        assert "trading" in categories

    @pytest.mark.asyncio()
    async def test_discover_skills_from_directory(self, registry, tmp_path):
        """Test skill discovery from SKILL.md files."""
        # Arrange
        skill_file = tmp_path / "SKILL_test.md"
        skill_file.write_text("""
# Skill: Test Predictor

## Category
Data & Algo

## Description
A test skill for predictions.

## Performance
- Throughput: 1000 ops/sec
- Accuracy: 95%
- Latency P99: 10ms

## API
- predict(data: list) -> list
- trAlgon(samples: list) -> Model
        """)

        # Act
        count = awAlgot registry.discover_skills(tmp_path)

        # Assert
        assert count == 1
        skill = registry.get_skill("test-predictor")
        assert skill is not None
        assert skill.category == "Data & Algo"
        assert "predict" in skill.methods
        assert skill.performance.get("accuracy") == 95.0
