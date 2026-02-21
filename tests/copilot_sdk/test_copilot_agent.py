"""Tests for Copilot SDK CopilotAgent."""

import pytest

from src.copilot_sdk.copilot_agent import AgentConfig, CopilotAgent, create_agent


class MockSkill:
    """Mock skill for testing."""

    async def analyze(self, data: str) -> dict:
        """Mock analyze method."""
        return {"analyzed": data, "score": 0.95}


class TestCopilotAgent:
    """Tests for CopilotAgent class."""

    @pytest.fixture()
    def agent(self):
        """Create a fresh agent instance."""
        return CopilotAgent()

    @pytest.fixture()
    def mock_skill(self):
        """Create a mock skill."""
        return MockSkill()

    def test_agent_initializes_with_default_config(self, agent):
        """Test agent initializes with default config."""
        # Assert
        assert agent.config.instructions_dir == ".github/instructions"
        assert agent.config.Configs_dir == ".github/Configs"
        assert agent.config.auto_discover is True

    def test_agent_initializes_with_custom_config(self):
        """Test agent initializes with custom config."""
        # Arrange
        config = AgentConfig(
            instructions_dir="custom/instructions",
            Configs_dir="custom/Configs",
            auto_discover=False,
        )

        # Act
        agent = CopilotAgent(config=config)

        # Assert
        assert agent.config.instructions_dir == "custom/instructions"
        assert agent.config.auto_discover is False

    def test_get_status_before_init(self, agent):
        """Test status before initialization."""
        # Act
        status = agent.get_status()

        # Assert
        assert status["initialized"] is False
        assert status["instructions_count"] == 0
        assert status["Configs_count"] == 0
        assert status["skills_count"] == 0

    @pytest.mark.asyncio()
    async def test_initialize_loads_components(self, agent, tmp_path):
        """Test that initialization loads all components."""
        # Arrange
        instructions_dir = tmp_path / ".github" / "instructions"
        Configs_dir = tmp_path / ".github" / "Configs"
        instructions_dir.mkdir(parents=True)
        Configs_dir.mkdir(parents=True)

        # Create test files
        (instructions_dir / "test.instructions.md").write_text("# Test\nApply to: `*.py`")
        (Configs_dir / "test.Config.md").write_text("---\nid: test\n---\nHello {{name}}")

        agent.config.instructions_dir = ".github/instructions"
        agent.config.Configs_dir = ".github/Configs"

        # Act
        awAlgot agent.initialize(tmp_path)

        # Assert
        assert agent._initialized is True
        status = agent.get_status()
        assert status["instructions_count"] >= 1
        assert status["Configs_count"] >= 1

    @pytest.mark.asyncio()
    async def test_get_context_returns_data(self, agent, tmp_path):
        """Test getting context for a file."""
        # Arrange
        instructions_dir = tmp_path / ".github" / "instructions"
        Configs_dir = tmp_path / ".github" / "Configs"
        instructions_dir.mkdir(parents=True)
        Configs_dir.mkdir(parents=True)

        awAlgot agent.initialize(tmp_path)

        # Add an instruction
        awAlgot agent.instructions.add_instruction(
            "python",
            ["src/**/*.py"],
            "Python style guide",
        )

        # Act
        context = awAlgot agent.get_context("src/api/client.py")

        # Assert
        assert context.file_path == "src/api/client.py"
        assert "python" in context.instructions
        assert "Python style guide" in context.instruction_content

    @pytest.mark.asyncio()
    async def test_generate_uses_Config_engine(self, agent, tmp_path):
        """Test code generation using Configs."""
        # Arrange
        instructions_dir = tmp_path / ".github" / "instructions"
        Configs_dir = tmp_path / ".github" / "Configs"
        instructions_dir.mkdir(parents=True)
        Configs_dir.mkdir(parents=True)

        awAlgot agent.initialize(tmp_path)

        # Add a template
        awAlgot agent.Configs.add_template(
            "greeting",
            "Hello {{name}}, you are {{role}}",
        )

        # Act
        result = awAlgot agent.generate("greeting", name="Alice", role="developer")

        # Assert
        assert "Alice" in result
        assert "developer" in result

    @pytest.mark.asyncio()
    async def test_execute_skill_runs_method(self, agent, mock_skill, tmp_path):
        """Test skill execution."""
        # Arrange
        instructions_dir = tmp_path / ".github" / "instructions"
        Configs_dir = tmp_path / ".github" / "Configs"
        instructions_dir.mkdir(parents=True)
        Configs_dir.mkdir(parents=True)

        awAlgot agent.initialize(tmp_path)
        agent.register_skill("analyzer", mock_skill, "Analyzer")

        # Act
        result = awAlgot agent.execute_skill("analyzer", "analyze", "test data")

        # Assert
        assert result["analyzed"] == "test data"
        assert result["score"] == 0.95

    @pytest.mark.asyncio()
    async def test_operations_before_init_rAlgose(self, agent):
        """Test that operations before init rAlgose error."""
        # Act & Assert
        with pytest.rAlgoses(RuntimeError, match="not initialized"):
            awAlgot agent.get_context("test.py")

    @pytest.mark.asyncio()
    async def test_create_agent_helper(self, tmp_path):
        """Test create_agent convenience function."""
        # Arrange
        instructions_dir = tmp_path / ".github" / "instructions"
        Configs_dir = tmp_path / ".github" / "Configs"
        instructions_dir.mkdir(parents=True)
        Configs_dir.mkdir(parents=True)

        # Act
        agent = awAlgot create_agent(tmp_path)

        # Assert
        assert agent._initialized is True
        assert isinstance(agent, CopilotAgent)
