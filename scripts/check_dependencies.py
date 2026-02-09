#!/usr/bin/env python3
"""Check dependency graph consistency in skills.json."""

import json
import sys
from pathlib import Path


def load_skills_registry() -> dict:
    """Load skills registry from .vscode/skills.json.
    
    Returns:
        dict with skills registry data
    """
    registry_path = Path(".vscode/skills.json")
    
    if not registry_path.exists():
        print("❌ Skills registry not found at .vscode/skills.json")
        sys.exit(1)
    
    with open(registry_path, encoding='utf-8') as f:
        return json.load(f)


def check_dependency_graph(registry: dict) -> list[str]:
    """Check dependency graph for consistency.
    
    Args:
        registry: Skills registry data
        
    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    
    skills = {skill["id"]: skill for skill in registry.get("skills", [])}
    dependency_graph = registry.get("dependency_graph", {})
    
    # Check all skills in dependency graph exist
    for skill_id, deps in dependency_graph.items():
        if skill_id not in skills:
            errors.append(f"Dependency graph references unknown skill: {skill_id}")
            continue
        
        # Check depends_on
        for dep in deps.get("depends_on", []):
            # Skip external dependencies (contain dots or slashes)
            if "." in dep or "/" in dep:
                continue
            
            if dep not in skills:
                errors.append(
                    f"Skill '{skill_id}' depends on unknown skill: {dep}"
                )
        
        # Check used_by
        for user in deps.get("used_by", []):
            # Skip module references (contain dots or slashes)
            if "." in user or "/" in user:
                continue
            
            if user not in skills and user not in dependency_graph:
                errors.append(
                    f"Skill '{skill_id}' is used by unknown entity: {user}"
                )
    
    # Check for circular dependencies
    def has_circular_dependency(skill_id: str, visited: set[str], stack: list[str]) -> bool:
        """Check if skill has circular dependency using DFS."""
        if skill_id in stack:
            cycle = " -> ".join(stack[stack.index(skill_id):] + [skill_id])
            errors.append(f"Circular dependency detected: {cycle}")
            return True
        
        if skill_id in visited:
            return False
        
        visited.add(skill_id)
        stack.append(skill_id)
        
        deps = dependency_graph.get(skill_id, {}).get("depends_on", [])
        for dep in deps:
            if "." not in dep and "/" not in dep:  # Only check skill dependencies
                if has_circular_dependency(dep, visited, stack):
                    return True
        
        stack.pop()
        return False
    
    visited = set()
    for skill_id in skills:
        if skill_id not in visited:
            has_circular_dependency(skill_id, visited, [])
    
    return errors


def main() -> int:
    """Main dependency checking function.
    
    Returns:
        0 if dependency graph is valid, 1 if errors found
    """
    print("🔍 Checking dependency graph...")
    print()
    
    registry = load_skills_registry()
    errors = check_dependency_graph(registry)
    
    if errors:
        print("❌ Dependency graph validation failed:\n")
        for error in errors:
            print(f"  • {error}")
        print()
        return 1
    
    print("✅ Dependency graph is valid!")
    print()
    
    # Print statistics
    dependency_graph = registry.get("dependency_graph", {})
    total_deps = sum(
        len(deps.get("depends_on", []))
        for deps in dependency_graph.values()
    )
    
    print("📊 Statistics:")
    print(f"  • Skills in graph: {len(dependency_graph)}")
    print(f"  • Total dependencies: {total_deps}")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
