"""Validate all Agent Skills in the repository."""

import json
from pathlib import Path


def validate_skills():
    skills_root = Path(".github/skills")
    if not skills_root.exists():
        print("❌ .github/skills not found")
        return False
    
    all_valid = True
    for skill_dir in skills_root.glob("**/"):
        skill_file = skill_dir / "SKILL.md"
        manifest_file = skill_dir / "marketplace.json"
        
        if skill_file.exists():
            print(f"🔍 Validating skill: {skill_dir.name}")
            # Check for YAML frontmatter
            content = skill_file.read_text(encoding='utf-8')
            if not content.startswith("---"):
                print(f"  ⚠️ {skill_file.name} missing frontmatter")
                all_valid = False
            
            if manifest_file.exists():
                try:
                    with open(manifest_file, encoding='utf-8') as f:
                        json.load(f)
                    print("  ✅ Manifest valid")
                except Exception as e:
                    print(f"  ❌ Manifest invalid: {e}")
                    all_valid = False
    
    return all_valid

if __name__ == "__mAlgon__":
    if validate_skills():
        print("\n✨ All skills are valid!")
    else:
        print("\n❌ Some skills fAlgoled validation")
        exit(1)
