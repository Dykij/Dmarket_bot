"""Tests for Copilot SDK InstructionMatcher."""

import pytest

from src.copilot_sdk.instruction_matcher import InstructionMatcher


class TestInstructionMatcher:
    """Tests for InstructionMatcher class."""

    @pytest.fixture()
    def matcher(self):
        """Create a fresh matcher instance."""
        return InstructionMatcher()

    @pytest.mark.asyncio()
    async def test_add_instruction_stores_correctly(self, matcher):
        """Test that instructions are stored correctly."""
        # Arrange
        name = "test-instruction"
        patterns = ["src/**/*.py"]
        content = "# Test instruction"

        # Act
        await matcher.add_instruction(name, patterns, content)

        # Assert
        assert name in matcher.instructions
        assert matcher.instructions[name].name == name
        assert matcher.instructions[name].patterns == patterns
        assert matcher.instructions[name].content == content

    @pytest.mark.asyncio()
    async def test_get_instructions_matches_patterns(self, matcher):
        """Test pattern matching for files."""
        # Arrange
        await matcher.add_instruction(
            "python-style",
            ["src/**/*.py"],
            "Python style guide",
        )
        await matcher.add_instruction(
            "testing",
            ["tests/**/*.py"],
            "Testing guide",
        )

        # Act
        src_instructions = await matcher.get_instructions("src/api/client.py")
        test_instructions = await matcher.get_instructions("tests/test_api.py")

        # Assert
        assert "python-style" in src_instructions
        assert "testing" not in src_instructions
        assert "testing" in test_instructions
        assert "python-style" not in test_instructions

    @pytest.mark.asyncio()
    async def test_get_merged_instructions_combines_content(self, matcher):
        """Test merging multiple instruction contents."""
        # Arrange
        await matcher.add_instruction(
            "instruction1",
            ["src/**/*.py"],
            "Content 1",
        )
        await matcher.add_instruction(
            "instruction2",
            ["src/**/*.py"],
            "Content 2",
        )

        # Act
        merged = await matcher.get_merged_instructions("src/module.py")

        # Assert
        assert "Content 1" in merged
        assert "Content 2" in merged
        assert "instruction1" in merged
        assert "instruction2" in merged

    @pytest.mark.asyncio()
    async def test_list_instructions_returns_summaries(self, matcher):
        """Test listing all instructions."""
        # Arrange
        await matcher.add_instruction("test1", ["*.py"], "Content 1", priority=1)
        await matcher.add_instruction("test2", ["*.md"], "Content 2", priority=2)

        # Act
        instructions = matcher.list_instructions()

        # Assert
        assert len(instructions) == 2
        assert any(i["name"] == "test1" for i in instructions)
        assert any(i["name"] == "test2" for i in instructions)

    @pytest.mark.asyncio()
    async def test_load_instructions_from_directory(self, matcher, tmp_path):
        """Test loading instructions from a directory."""
        # Arrange
        instruction_file = tmp_path / "test.instructions.md"
        instruction_file.write_text(
            "# Test Instruction\n\nApply to: `src/**/*.py`\n\n## Rules\n- Rule 1"
        )

        # Act
        count = await matcher.load_instructions(tmp_path)

        # Assert
        assert count == 1
        # Name includes the full stem (test.instructions)
        assert len(matcher.instructions) == 1

    @pytest.mark.asyncio()
    async def test_load_instructions_from_nonexistent_dir(self, matcher):
        """Test loading from non-existent directory returns 0."""
        # Act
        count = await matcher.load_instructions("/nonexistent/path")

        # Assert
        assert count == 0

    @pytest.mark.asyncio()
    async def test_priority_sorting(self, matcher):
        """Test that instructions are sorted by priority."""
        # Arrange
        await matcher.add_instruction("low", ["src/**/*.py"], "Low", priority=1)
        await matcher.add_instruction("high", ["src/**/*.py"], "High", priority=10)
        await matcher.add_instruction("medium", ["src/**/*.py"], "Medium", priority=5)

        # Act
        instructions = await matcher.get_instructions("src/test.py")

        # Assert
        assert instructions[0] == "high"
        assert instructions[1] == "medium"
        assert instructions[2] == "low"
