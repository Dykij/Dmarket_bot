#!/usr/bin/env python3
"""
Skills Composition & Dependency Graph Manager

Manages skill dependencies, version resolution, and composition.
Part of Phase 3 Week 3-4 implementation.
"""

import re
import sys
from pathlib import Path

import yaml


class SkillDependency:
    """Represents a skill dependency with version constraints."""

    def __init__(self, name: str, version_constraint: str):
        self.name = name
        self.version_constraint = version_constraint
        self.min_version, self.max_version = self._parse_constraint(version_constraint)

    def _parse_constraint(self, constraint: str) -> tuple[str | None, str | None]:
        """Parse semver constraint (e.g., '>=1.0.0', '^1.2.0', '~1.2.0')."""
        if constraint.startswith(">="):
            return constraint[2:], None
        if constraint.startswith("^"):
            # ^1.2.3 means >=1.2.3 <2.0.0
            version = constraint[1:]
            parts = version.split(".")
            if len(parts) >= 1:
                next_major = str(int(parts[0]) + 1) + ".0.0"
                return version, next_major
        elif constraint.startswith("~"):
            # ~1.2.3 means >=1.2.3 <1.3.0
            version = constraint[1:]
            parts = version.split(".")
            if len(parts) >= 2:
                next_minor = f"{parts[0]}.{int(parts[1]) + 1}.0"
                return version, next_minor
        elif constraint.startswith("=="):
            version = constraint[2:]
            return version, version
        else:
            # Exact version
            return constraint, constraint
        return None, None

    def is_satisfied(self, version: str) -> bool:
        """Check if a version satisfies this dependency constraint."""
        # For exact version (min == max), check equality
        if self.min_version == self.max_version and self.min_version is not None:
            return self._compare_versions(version, self.min_version) == 0

        if self.min_version and self._compare_versions(version, self.min_version) < 0:
            return False
        if self.max_version and self._compare_versions(version, self.max_version) >= 0:
            return False
        return True

    @staticmethod
    def _compare_versions(v1: str, v2: str) -> int:
        """Compare two semver versions. Returns -1, 0, or 1."""
        parts1 = [int(x) for x in v1.split(".")]
        parts2 = [int(x) for x in v2.split(".")]

        # Pad to same length
        while len(parts1) < len(parts2):
            parts1.append(0)
        while len(parts2) < len(parts1):
            parts2.append(0)

        for p1, p2 in zip(parts1, parts2):
            if p1 < p2:
                return -1
            if p1 > p2:
                return 1
        return 0


class SkillCompositionManager:
    """Manages skill dependencies and composition."""

    def __init__(self, skills_dir: Path = Path(".github/skills")):
        self.skills_dir = skills_dir
        self.skills: dict[str, dict] = {}
        self._load_skills()

    def _load_skills(self):
        """Load all skills from .github/skills/ directory."""
        if not self.skills_dir.exists():
            return

        for skill_path in self.skills_dir.rglob("SKILL.md"):
            try:
                content = Path(skill_path).read_text(encoding="utf-8")

                # Extract YAML frontmatter
                match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
                if match:
                    metadata = yaml.safe_load(match.group(1))
                    skill_name = metadata.get("name")
                    if skill_name:
                        self.skills[skill_name] = {
                            "metadata": metadata,
                            "path": skill_path,
                        }
            except Exception as e:
                print(f"⚠️ Error loading skill {skill_path}: {e}")

    def get_dependencies(self, skill_name: str) -> list[SkillDependency]:
        """Get dependencies for a skill."""
        if skill_name not in self.skills:
            return []

        metadata = self.skills[skill_name]["metadata"]
        depends_on = metadata.get("depends_on") or []

        dependencies = []
        for dep in depends_on:
            if isinstance(dep, str):
                # Format: "skill-name>=1.0.0"
                match = re.match(r"^([a-z0-9-]+)(.*)$", dep)
                if match:
                    name, constraint = match.groups()
                    dependencies.append(SkillDependency(name, constraint or ">=0.0.0"))
        return dependencies

    def check_circular_dependencies(self) -> list[list[str]]:
        """Check for circular dependencies. Returns list of cycles found."""
        cycles = []

        def dfs(skill: str, path: set[str], visited: set[str]):
            if skill in path:
                # Found a cycle
                cycle_start = list(path).index(skill)
                cycle = list(path)[cycle_start:] + [skill]
                cycles.append(cycle)
                return

            if skill in visited:
                return

            visited.add(skill)
            path.add(skill)

            for dep in self.get_dependencies(skill):
                if dep.name in self.skills:
                    dfs(dep.name, path.copy(), visited)

            path.discard(skill)

        for skill_name in self.skills:
            dfs(skill_name, set(), set())

        return cycles

    def resolve_dependencies(self, skill_name: str) -> tuple[bool, list[str], list[str]]:
        """
        Resolve all dependencies for a skill.

        Returns:
            (success, resolved_skills, missing_skills)
        """
        if skill_name not in self.skills:
            return False, [], [skill_name]

        resolved = []
        missing = []
        visited = set()

        def resolve(name: str):
            if name in visited:
                return
            visited.add(name)

            if name not in self.skills:
                missing.append(name)
                return

            # Resolve dependencies first (post-order)
            for dep in self.get_dependencies(name):
                resolve(dep.name)

            resolved.append(name)

        resolve(skill_name)

        return len(missing) == 0, resolved, missing

    def validate_dependency_versions(self, skill_name: str) -> list[str]:
        """Validate that all dependency version constraints are satisfied."""
        errors = []

        if skill_name not in self.skills:
            errors.append(f"Skill '{skill_name}' not found")
            return errors

        for dep in self.get_dependencies(skill_name):
            if dep.name not in self.skills:
                errors.append(f"Dependency '{dep.name}' required by '{skill_name}' not found")
                continue

            actual_version = self.skills[dep.name]["metadata"].get("version", "0.0.0")
            if not dep.is_satisfied(actual_version):
                errors.append(
                    f"Dependency '{dep.name}' version {actual_version} does not satisfy "
                    f"constraint '{dep.version_constraint}' required by '{skill_name}'"
                )

        return errors

    def generate_dependency_graph(self) -> str:
        """Generate a text-based dependency graph visualization."""
        lines = ["# Skills Dependency Graph", ""]

        for skill_name in sorted(self.skills.keys()):
            version = self.skills[skill_name]["metadata"].get("version", "0.0.0")
            lines.append(f"## {skill_name} (v{version})")

            deps = self.get_dependencies(skill_name)
            if deps:
                lines.append("**Dependencies:**")
                for dep in deps:
                    lines.append(f"  - {dep.name} {dep.version_constraint}")
            else:
                lines.append("**No dependencies**")

            lines.append("")

        return "\n".join(lines)


def main():
    """MAlgon CLI for skills composition management."""
    import argparse

    parser = argparse.ArgumentParser(description="Manage skill dependencies")
    parser.add_argument(
        "command",
        choices=["check", "resolve", "graph", "validate"],
        help="Command to execute",
    )
    parser.add_argument("--skill", help="Skill name (for resolve/validate)")

    args = parser.parse_args()

    manager = SkillCompositionManager()

    if args.command == "check":
        print("🔍 Checking for circular dependencies...")
        cycles = manager.check_circular_dependencies()
        if cycles:
            print(f"\n❌ Found {len(cycles)} circular dependency cycle(s):\n")
            for i, cycle in enumerate(cycles, 1):
                print(f"  Cycle {i}: {' → '.join(cycle)}")
            sys.exit(1)
        else:
            print("✅ No circular dependencies found")

    elif args.command == "resolve":
        if not args.skill:
            print("❌ --skill required for resolve command")
            sys.exit(1)

        print(f"🔍 Resolving dependencies for '{args.skill}'...")
        success, resolved, missing = manager.resolve_dependencies(args.skill)

        if success:
            print(f"\n✅ Successfully resolved {len(resolved)} skill(s):")
            for skill in resolved:
                version = manager.skills[skill]["metadata"].get("version", "0.0.0")
                print(f"  - {skill} (v{version})")
        else:
            print("\n❌ Failed to resolve. Missing skills:")
            for skill in missing:
                print(f"  - {skill}")
            sys.exit(1)

    elif args.command == "validate":
        if not args.skill:
            print("❌ --skill required for validate command")
            sys.exit(1)

        print(f"🔍 Validating dependencies for '{args.skill}'...")
        errors = manager.validate_dependency_versions(args.skill)

        if errors:
            print(f"\n❌ Found {len(errors)} error(s):")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
        else:
            print("✅ All dependency versions are valid")

    elif args.command == "graph":
        print(manager.generate_dependency_graph())


if __name__ == "__main__":
    main()
