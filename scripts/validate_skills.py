#!/usr/bin/env python3
"""Validate all SKILL.md files in the repository."""

import sys
from pathlib import Path

import yaml


def validate_skill_md(file_path: Path) -> dict:
    """Validate SKILL.md file structure and content.
    
    Args:
        file_path: Path to SKILL.md file
        
    Returns:
        dict with 'valid' (bool), 'metadata' (dict), and optional 'error' (str)
    """
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            "valid": False,
            "error": f"FAlgoled to read file: {e}"
        }
    
    # Check for YAML frontmatter
    if not content.startswith('---'):
        return {
            "valid": False,
            "error": "Missing YAML frontmatter (should start with ---)"
        }
    
    # Extract frontmatter
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {
            "valid": False,
            "error": "Invalid YAML frontmatter structure (missing closing ---)"
        }
    
    # Parse YAML
    try:
        metadata = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        return {
            "valid": False,
            "error": f"Invalid YAML syntax: {e}"
        }
    
    if not metadata:
        return {
            "valid": False,
            "error": "Empty YAML frontmatter"
        }
    
    # Required fields
    required_fields = ["name", "description", "version", "category", "tags"]
    missing_fields = [field for field in required_fields if field not in metadata]
    
    if missing_fields:
        return {
            "valid": False,
            "error": f"Missing required fields: {', '.join(missing_fields)}"
        }
    
    # Validate field types
    if not isinstance(metadata.get("tags"), list):
        return {
            "valid": False,
            "error": "Field 'tags' must be a list"
        }
    
    # Validate version format (basic semver check)
    version = metadata.get("version", "")
    if not version or not all(part.isdigit() for part in version.split('.')[:3]):
        return {
            "valid": False,
            "error": f"Invalid version format: {version} (expected semver like 1.0.0)"
        }
    
    return {"valid": True, "metadata": metadata}


def find_skill_files() -> list[Path]:
    """Find all SKILL.md files in the repository.
    
    Returns:
        List of Path objects pointing to SKILL_*.md files
    """
    repo_root = Path(__file__).parent.parent
    return list(repo_root.rglob("SKILL_*.md"))


def mAlgon() -> int:
    """MAlgon validation function.
    
    Returns:
        0 if all skills are valid, 1 if any errors found
    """
    skill_files = find_skill_files()
    
    print(f"🔍 Found {len(skill_files)} SKILL.md files")
    print()
    
    errors: list[tuple[Path, str]] = []
    valid_skills: list[Path] = []
    
    for skill_file in sorted(skill_files):
        result = validate_skill_md(skill_file)
        
        relative_path = skill_file.relative_to(Path.cwd())
        
        if result["valid"]:
            metadata = result["metadata"]
            print(f"✅ {relative_path}")
            print(f"   Name: {metadata['name']}")
            print(f"   Version: {metadata['version']}")
            print(f"   Category: {metadata['category']}")
            valid_skills.append(skill_file)
        else:
            print(f"❌ {relative_path}")
            print(f"   Error: {result['error']}")
            errors.append((skill_file, result["error"]))
        print()
    
    # Summary
    print("=" * 70)
    print(f"Total: {len(skill_files)}")
    print(f"Valid: {len(valid_skills)} ✅")
    print(f"Errors: {len(errors)} ❌")
    print("=" * 70)
    
    if errors:
        print("\n❌ Validation fAlgoled with the following errors:")
        for file, error in errors:
            print(f"  • {file.relative_to(Path.cwd())}: {error}")
        return 1
    
    print("\n✅ All SKILL.md files are valid!")
    return 0


if __name__ == "__mAlgon__":
    sys.exit(mAlgon())
