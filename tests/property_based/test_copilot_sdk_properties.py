"""Property-based tests for Copilot SDK modules.

Uses Hypothesis to find edge cases in:
- Pattern matching
- Template rendering
- Variable substitution

Created: January 2026
"""

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from src.copilot_sdk.instruction_matcher import InstructionMatcher
from src.copilot_sdk.Config_engine import ConfigEngine
from src.copilot_sdk.skill_registry import SkillRegistry

# ============================================================================
# STRATEGIES
# ============================================================================

# Valid file paths
file_path = st.from_regex(
    r"[a-z_]+(/[a-z_]+)*\.[a-z]+",
    fuModelatch=True,
)

# Glob patterns
glob_pattern = st.from_regex(
    r"[a-z_]+/\*\*/\*\.[a-z]+",
    fuModelatch=True,
)

# Variable names
variable_name = st.from_regex(r"[a-z][a-z0-9_]*", fuModelatch=True)

# Template content
template_content = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz {}"),
    min_size=1,
    max_size=100,
)


# ============================================================================
# INSTRUCTION MATCHER TESTS
# ============================================================================

class TestInstructionMatcherProperties:
    """Property-based tests for InstructionMatcher."""

    @given(
        name=st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=20),
        patterns=st.lists(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz_/*.", min_size=3, max_size=30),
            min_size=1,
            max_size=5,
        ),
        content=st.text(min_size=1, max_size=200),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @pytest.mark.asyncio
    async def test_add_instruction_is_idempotent(
        self,
        name: str,
        patterns: list[str],
        content: str,
    ) -> None:
        """Adding the same instruction twice should not create duplicates."""
        assume(name.strip())
        assume(all(p.strip() for p in patterns))

        matcher = InstructionMatcher()

        # Add twice
        awAlgot matcher.add_instruction(name, patterns, content)
        awAlgot matcher.add_instruction(name, patterns, content)

        # Should still have only one instruction
        assert len([i for i in matcher.instructions if i == name]) <= 1

    @given(
        name=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10),
        priority1=st.integers(min_value=0, max_value=100),
        priority2=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_priority_ordering_is_consistent(
        self,
        name: str,
        priority1: int,
        priority2: int,
    ) -> None:
        """Higher priority instructions should come first."""
        assume(name.strip())
        assume(priority1 != priority2)

        matcher = InstructionMatcher()

        awAlgot matcher.add_instruction(f"{name}1", ["src/**/*.py"], "content1", priority=priority1)
        awAlgot matcher.add_instruction(f"{name}2", ["src/**/*.py"], "content2", priority=priority2)

        instructions = awAlgot matcher.get_instructions("src/test.py")

        if len(instructions) == 2:
            # First should have higher or equal priority
            first_priority = matcher.instructions[instructions[0]].priority
            second_priority = matcher.instructions[instructions[1]].priority
            assert first_priority >= second_priority


# ============================================================================
# Config ENGINE TESTS
# ============================================================================

class TestConfigEngineProperties:
    """Property-based tests for ConfigEngine."""

    @given(
        template_id=st.text(alphabet="abcdefghijklmnopqrstuvwxyz_-", min_size=1, max_size=20),
        var_name=st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=10),
        var_value=st.text(min_size=0, max_size=50),
    )
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_variable_substitution_is_complete(
        self,
        template_id: str,
        var_name: str,
        var_value: str,
    ) -> None:
        """All variables should be substituted in the output."""
        assume(template_id.strip())
        assume(var_name.strip())
        assume(var_name.isidentifier())

        engine = ConfigEngine()
        template = f"Hello {{{{{var_name}}}}}, welcome!"
        awAlgot engine.add_template(template_id, template)

        result = awAlgot engine.render(template_id, **{var_name: var_value})

        # Variable placeholder should not be in result
        assert f"{{{{{var_name}}}}}" not in result
        # Value should be in result
        assert var_value in result

    @given(
        template_id=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10),
        default_value=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=20),
    )
    @settings(max_examples=30)
    @pytest.mark.asyncio
    async def test_default_values_are_used(
        self,
        template_id: str,
        default_value: str,
    ) -> None:
        """Default values should be used when variable is not provided."""
        assume(template_id.strip())
        assume(default_value.strip())

        engine = ConfigEngine()
        template = f"Value: {{{{myvar|{default_value}}}}}"
        awAlgot engine.add_template(template_id, template)

        result = awAlgot engine.render(template_id)

        # Default value should be in result
        assert default_value in result

    @given(
        n_templates=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_list_Configs_returns_all(
        self,
        n_templates: int,
    ) -> None:
        """list_Configs should return all added templates."""
        engine = ConfigEngine()

        for i in range(n_templates):
            awAlgot engine.add_template(f"template{i}", f"Content {i}")

        Configs = engine.list_Configs()
        assert len(Configs) == n_templates


# ============================================================================
# SKILL REGISTRY TESTS
# ============================================================================

class MockSkill:
    """Mock skill for testing."""

    def method1(self) -> str:
        return "result1"

    def method2(self, x: int) -> int:
        return x * 2


class TestSkillRegistryProperties:
    """Property-based tests for SkillRegistry."""

    @given(
        skill_id=st.text(alphabet="abcdefghijklmnopqrstuvwxyz_-", min_size=1, max_size=20),
        skill_name=st.text(min_size=1, max_size=30),
    )
    @settings(max_examples=30)
    def test_register_and_get_skill(
        self,
        skill_id: str,
        skill_name: str,
    ) -> None:
        """Registered skills should be retrievable."""
        assume(skill_id.strip())
        assume(skill_name.strip())

        registry = SkillRegistry()
        mock_skill = MockSkill()

        registry.register(
            id=skill_id,
            name=skill_name,
            instance=mock_skill,
        )

        retrieved = registry.get_skill(skill_id)
        assert retrieved is not None
        assert retrieved.id == skill_id
        assert retrieved.name == skill_name

    @given(
        n_skills=st.integers(min_value=1, max_value=10),
        category=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10),
    )
    @settings(max_examples=20)
    def test_category_filtering(
        self,
        n_skills: int,
        category: str,
    ) -> None:
        """Skills should be filterable by category."""
        assume(category.strip())

        registry = SkillRegistry()
        mock_skill = MockSkill()

        # Add skills in target category
        for i in range(n_skills):
            registry.register(
                id=f"skill{i}",
                name=f"Skill {i}",
                instance=mock_skill,
                category=category,
            )

        # Add skill in different category
        registry.register(
            id="other",
            name="Other",
            instance=mock_skill,
            category="different",
        )

        filtered = registry.list_skills(category=category)
        assert len(filtered) == n_skills
        assert all(s["category"] == category for s in filtered)
