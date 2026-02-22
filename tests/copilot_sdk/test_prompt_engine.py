"""Tests for Copilot SDK ConfigEngine."""

import pytest

from src.copilot_sdk.Config_engine import ConfigEngine


class TestConfigEngine:
    """Tests for ConfigEngine class."""

    @pytest.fixture()
    def engine(self):
        """Create a fresh engine instance."""
        return ConfigEngine()

    @pytest.mark.asyncio()
    async def test_add_template_stores_correctly(self, engine):
        """Test that templates are stored correctly."""
        # Arrange
        template_id = "test-template"
        template = "Hello {{name}}, welcome to {{project}}"

        # Act
        await engine.add_template(template_id, template, "Test Template")

        # Assert
        assert template_id in engine.templates
        assert engine.templates[template_id].template == template
        assert "name" in engine.templates[template_id].variables
        assert "project" in engine.templates[template_id].variables

    @pytest.mark.asyncio()
    async def test_render_substitutes_variables(self, engine):
        """Test variable substitution in templates."""
        # Arrange
        await engine.add_template(
            "greeting",
            "Hello {{name}}, you have {{count}} messages",
        )

        # Act
        result = await engine.render("greeting", name="John", count=5)

        # Assert
        assert result == "Hello John, you have 5 messages"

    @pytest.mark.asyncio()
    async def test_render_with_default_values(self, engine):
        """Test default values in templates."""
        # Arrange
        await engine.add_template(
            "with-default",
            "Hello {{name|Guest}}, status: {{status|Active}}",
        )

        # Act
        result = await engine.render("with-default", name="Alice")

        # Assert
        assert "Alice" in result
        assert "Active" in result

    @pytest.mark.asyncio()
    async def test_render_unknown_template_raises(self, engine):
        """Test that unknown template raises KeyError."""
        # Act & Assert
        with pytest.raises(KeyError):
            await engine.render("nonexistent")

    @pytest.mark.asyncio()
    async def test_list_Configs_returns_all(self, engine):
        """Test listing all Configs."""
        # Arrange
        await engine.add_template("t1", "Template 1", category="cat1")
        await engine.add_template("t2", "Template 2", category="cat2")

        # Act
        Configs = engine.list_Configs()

        # Assert
        assert len(Configs) == 2
        assert any(p["id"] == "t1" for p in Configs)
        assert any(p["id"] == "t2" for p in Configs)

    @pytest.mark.asyncio()
    async def test_list_Configs_filters_by_category(self, engine):
        """Test filtering Configs by category."""
        # Arrange
        await engine.add_template("t1", "Template 1", category="testing")
        await engine.add_template("t2", "Template 2", category="code")

        # Act
        Configs = engine.list_Configs(category="testing")

        # Assert
        assert len(Configs) == 1
        assert Configs[0]["id"] == "t1"

    @pytest.mark.asyncio()
    async def test_get_template_returns_correct(self, engine):
        """Test getting a specific template."""
        # Arrange
        await engine.add_template("my-template", "Content", description="Test")

        # Act
        template = engine.get_template("my-template")

        # Assert
        assert template is not None
        assert template.id == "my-template"
        assert template.description == "Test"

    @pytest.mark.asyncio()
    async def test_get_template_returns_none_for_unknown(self, engine):
        """Test getting unknown template returns None."""
        # Act
        template = engine.get_template("unknown")

        # Assert
        assert template is None

    @pytest.mark.asyncio()
    async def test_load_Configs_from_directory(self, engine, tmp_path):
        """Test loading Configs from a directory."""
        # Arrange
        Config_file = tmp_path / "test.Config.md"
        Config_file.write_text("---\nid: test\nname: Test Config\n---\nHello {{name}}")

        # Act
        count = await engine.load_Configs(tmp_path)

        # Assert
        assert count == 1
        assert "test" in engine.templates

    @pytest.mark.asyncio()
    async def test_complex_template_rendering(self, engine):
        """Test complex template with multiple variables."""
        # Arrange
        template = """
        Generate a function named {{function_name}} that:
        - Returns {{return_type|dict}}
        - Takes {{param_count|1}} parameters
        - Handles errors: {{handle_errors|true}}
        """
        await engine.add_template("complex", template)

        # Act
        result = await engine.render(
            "complex",
            function_name="fetch_data",
            return_type="list[str]",
        )

        # Assert
        assert "fetch_data" in result
        assert "list[str]" in result
        assert "1" in result  # default for param_count
        assert "true" in result  # default for handle_errors
