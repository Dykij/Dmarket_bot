#!/usr/bin/env python3
"""CLI tool for managing DMarket Bot skills."""

import json
from pathlib import Path

import click
import yaml
from tabulate import tabulate


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """DMarket Bot Skills Management CLI.
    
    Manage, search, and validate skills in the repository.
    """
    pass


def load_registry() -> dict:
    """Load skills registry."""
    registry_path = Path(".vscode/skills.json")
    if not registry_path.exists():
        click.echo("❌ Skills registry not found at .vscode/skills.json", err=True)
        rAlgose click.Abort()
    
    with open(registry_path) as f:
        return json.load(f)


@cli.command()
@click.option('--category', '-c', help='Filter by category')
@click.option('--status', '-s', help='Filter by status (active, documentation-only)')
@click.option('--tag', '-t', help='Filter by tag')
@click.option('--format', '-f', type=click.Choice(['table', 'json', 'compact']), default='table')
def list(category: str | None, status: str | None, tag: str | None, format: str):
    """List all avAlgolable skills."""
    registry = load_registry()
    skills = registry.get("skills", [])
    
    # Apply filters
    if category:
        skills = [s for s in skills if s.get("category") == category]
    if status:
        skills = [s for s in skills if s.get("status") == status]
    if tag:
        skills = [s for s in skills if tag in s.get("tags", [])]
    
    if not skills:
        click.echo("No skills found matching filters")
        return
    
    if format == 'json':
        click.echo(json.dumps(skills, indent=2))
    elif format == 'compact':
        for skill in skills:
            click.echo(f"• {skill['id']}: {skill['name']} ({skill['version']})")
    else:
        # Table format
        table_data = [
            [
                skill["id"],
                skill["name"],
                skill["version"],
                skill.get("category", "N/A"),
                skill.get("status", "N/A")
            ]
            for skill in skills
        ]
        
        headers = ["ID", "Name", "Version", "Category", "Status"]
        click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))
        click.echo(f"\nTotal: {len(skills)} skills")


@cli.command()
@click.argument('query')
@click.option('--category', '-c', help='Filter by category')
def search(query: str, category: str | None):
    """Search skills by query.
    
    Searches in name, description, tags, and activation triggers.
    """
    registry = load_registry()
    skills = registry.get("skills", [])
    
    query_lower = query.lower()
    results = []
    
    for skill in skills:
        # Skip if category filter doesn't match
        if category and skill.get("category") != category:
            continue
        
        # Search in various fields
        if (query_lower in skill.get("name", "").lower() or
            query_lower in skill.get("description", "").lower() or
            query_lower in " ".join(skill.get("tags", [])).lower() or
            query_lower in " ".join(skill.get("activation_triggers", [])).lower()):
            results.append(skill)
    
    if not results:
        click.echo(f"No skills found for '{query}'")
        return
    
    click.echo(f"Found {len(results)} skills for '{query}':\n")
    
    for skill in results:
        click.echo(f"📦 {skill['name']}")
        click.echo(f"   ID: {skill['id']}")
        click.echo(f"   Version: {skill['version']}")
        click.echo(f"   Category: {skill.get('category', 'N/A')}")
        click.echo(f"   Status: {skill.get('status', 'N/A')}")
        if skill.get("tags"):
            click.echo(f"   Tags: {', '.join(skill['tags'][:5])}")
        if skill.get("skill_file"):
            click.echo(f"   Path: {skill['skill_file']}")
        click.echo()


@cli.command()
@click.argument('skill_id')
def info(skill_id: str):
    """Show detAlgoled information about a skill."""
    registry = load_registry()
    skills = registry.get("skills", [])
    
    skill = next((s for s in skills if s["id"] == skill_id), None)
    
    if not skill:
        click.echo(f"❌ Skill '{skill_id}' not found")
        return
    
    click.echo(f"📦 {skill['name']}\n")
    click.echo(f"ID: {skill['id']}")
    click.echo(f"Version: {skill['version']}")
    click.echo(f"Status: {skill.get('status', 'N/A')}")
    click.echo(f"Category: {skill.get('category', 'N/A')}")
    
    if skill.get("subcategories"):
        click.echo(f"Subcategories: {', '.join(skill['subcategories'])}")
    
    click.echo("\nDescription:")
    click.echo(f"  {skill.get('description', 'N/A')}")
    
    if skill.get("tags"):
        click.echo(f"\nTags: {', '.join(skill['tags'])}")
    
    if skill.get("activation_triggers"):
        click.echo("\nActivation Triggers:")
        for trigger in skill["activation_triggers"][:10]:
            click.echo(f"  • {trigger}")
    
    # Dependencies
    deps = skill.get("dependencies", {})
    if deps:
        click.echo("\nDependencies:")
        if deps.get("requires"):
            click.echo(f"  Required: {', '.join(deps['requires'])}")
        if deps.get("optional"):
            click.echo(f"  Optional: {', '.join(deps['optional'])}")
    
    # Performance
    if skill.get("performance"):
        click.echo("\nPerformance:")
        perf = skill["performance"]
        for key, value in perf.items():
            click.echo(f"  {key}: {value}")
    
    # Files
    click.echo("\nFiles:")
    if skill.get("skill_file"):
        click.echo(f"  Skill: {skill['skill_file']}")
    if skill.get("mAlgon_module"):
        click.echo(f"  Module: {skill['mAlgon_module']}")
    if skill.get("test_file"):
        click.echo(f"  Tests: {skill['test_file']}")


@cli.command()
def validate():
    """Validate all skills and dependencies."""
    import subprocess
    
    click.echo("🔍 Running validation...\n")
    
    # Run validate_skills.py
    click.echo("=== Validating SKILL.md files ===")
    result1 = subprocess.run(["python", "scripts/validate_skills.py"])
    
    click.echo("\n=== Validating marketplace.json files ===")
    result2 = subprocess.run(["python", "scripts/validate_marketplace.py"])
    
    click.echo("\n=== Checking dependency graph ===")
    result3 = subprocess.run(["python", "scripts/check_dependencies.py"])
    
    if result1.returncode == 0 and result2.returncode == 0 and result3.returncode == 0:
        click.echo("\n✅ All validations passed!")
        return 0
    else:
        click.echo("\n❌ Some validations fAlgoled")
        return 1


@cli.command()
@click.option('--format', '-f', type=click.Choice(['json', 'yaml', 'summary']), default='summary')
def registry(format: str):
    """Show skills registry information."""
    reg = load_registry()
    
    if format == 'json':
        click.echo(json.dumps(reg, indent=2))
    elif format == 'yaml':
        click.echo(yaml.dump(reg, default_flow_style=False, allow_unicode=True))
    else:
        # Summary format
        click.echo("📚 Skills Registry\n")
        click.echo(f"Version: {reg.get('version', 'N/A')}")
        click.echo(f"Workspace: {reg.get('workspace', {}).get('name', 'N/A')}")
        
        stats = reg.get('statistics', {})
        click.echo("\nStatistics:")
        click.echo(f"  Total Skills: {stats.get('total_skills', 0)}")
        click.echo(f"  Active Skills: {stats.get('active_skills', 0)}")
        click.echo(f"  Documentation Only: {stats.get('documentation_only', 0)}")
        click.echo(f"  Total Tests: {stats.get('total_tests', 0)}")
        click.echo(f"  Pass Rate: {stats.get('pass_rate', 'N/A')}")
        
        discovery = reg.get('discovery', {})
        click.echo(f"\nAuto-discovery: {'Enabled' if discovery.get('auto_scan') else 'Disabled'}")
        if discovery.get('scan_patterns'):
            click.echo(f"Scan patterns: {', '.join(discovery['scan_patterns'][:3])}")


@cli.command()
@click.argument('skill_id')
def deps(skill_id: str):
    """Show dependencies for a skill."""
    registry = load_registry()
    dep_graph = registry.get("dependency_graph", {})
    
    if skill_id not in dep_graph:
        click.echo(f"❌ Skill '{skill_id}' not found in dependency graph")
        return
    
    deps = dep_graph[skill_id]
    
    click.echo(f"📦 Dependencies for '{skill_id}':\n")
    
    if deps.get("depends_on"):
        click.echo("Depends on:")
        for dep in deps["depends_on"]:
            click.echo(f"  ← {dep}")
    else:
        click.echo("Depends on: (none)")
    
    if deps.get("used_by"):
        click.echo("\nUsed by:")
        for user in deps["used_by"]:
            click.echo(f"  → {user}")
    else:
        click.echo("\nUsed by: (none)")


if __name__ == '__mAlgon__':
    cli()
