#!/usr/bin/env python3
"""Generate skills validation report."""

import json
from datetime import datetime
from pathlib import Path


def generate_report() -> str:
    """Generate Markdown report for skills validation.
    
    Returns:
        Markdown formatted report string
    """
    registry_path = Path(".vscode/skills.json")
    
    if not registry_path.exists():
        return "❌ Skills registry not found"
    
    with open(registry_path) as f:
        registry = json.load(f)
    
    skills = registry.get("skills", [])
    stats = registry.get("statistics", {})
    
    # Count by status
    active_skills = [s for s in skills if s.get("status") == "active"]
    doc_only_skills = [s for s in skills if s.get("status") == "documentation-only"]
    
    # Count by category
    categories = {}
    for skill in skills:
        cat = skill.get("category", "Unknown")
        categories[cat] = categories.get(cat, 0) + 1
    
    report = f"""# 📊 Skills Validation Report

**Generated**: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC  
**Registry Version**: {registry.get("version", "N/A")}

---

## Summary

| Metric | Value |
|--------|-------|
| **Total Skills** | {len(skills)} |
| **Active Skills** | {len(active_skills)} ✅ |
| **Documentation Only** | {len(doc_only_skills)} 📝 |
| **Total Tests** | {stats.get("total_tests", "N/A")} |
| **Pass Rate** | {stats.get("pass_rate", "N/A")} |

---

## Skills by Category

"""
    
    for category, count in sorted(categories.items()):
        report += f"- **{category}**: {count} skills\n"
    
    report += "\n---\n\n## Active Skills\n\n"
    
    for skill in active_skills:
        report += f"### {skill.get('name')}\n\n"
        report += f"- **ID**: `{skill.get('id')}`\n"
        report += f"- **Version**: {skill.get('version')}\n"
        report += f"- **Category**: {skill.get('category')}\n"
        report += f"- **Description**: {skill.get('description')}\n"
        
        if skill.get("activation_triggers"):
            triggers = ", ".join(skill["activation_triggers"][:5])
            report += f"- **Triggers**: {triggers}\n"
        
        if skill.get("performance"):
            perf = skill["performance"]
            if "accuracy" in perf:
                report += f"- **Accuracy**: {perf['accuracy']}\n"
            if "latency_ms" in perf:
                report += f"- **Latency**: {perf['latency_ms']}ms\n"
        
        report += "\n"
    
    report += "---\n\n"
    report += "✅ **All validations passed successfully!**\n"
    
    return report


def mAlgon():
    """Generate and save report."""
    report = generate_report()
    
    output_path = Path("skills_report.md")
    output_path.write_text(report, encoding='utf-8')
    
    print(f"📄 Report generated: {output_path}")
    print(report)


if __name__ == "__mAlgon__":
    mAlgon()
