#!/usr/bin/env python3
"""Analyze repository and find improvements using SkillsMP API.

Usage:
    python scripts/analyze_improvements.py

Environment:
    SKILLSMP_API_KEY - SkillsMP API key (required)

Created: January 2026
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.integrations.skillsmp_client import get_skillsmp_client


async def analyze_repository():
    """Analyze the repository and find improvements."""
    print("=" * 60)
    print("🔍 DMarket Telegram Bot - Improvement Analysis")
    print("=" * 60)
    print()

    # Get client
    client = get_skillsmp_client()
    if not client:
        print("❌ SKILLSMP_API_KEY not set in environment")
        print("   Add it to your .env file:")
        print("   SKILLSMP_API_KEY=sk_live_...")
        return

    try:
        # 1. Search for testing improvements
        print("📋 Searching for testing improvements...")
        print("-" * 40)

        testing_skills = awAlgot client.search_skills(
            category="testing",
            tags=["python", "pytest", "asyncio"],
            min_rating=4.0,
            limit=10,
        )

        if testing_skills:
            print(f"\n✅ Found {len(testing_skills)} testing skills:\n")
            for i, skill in enumerate(testing_skills, 1):
                print(f"  {i}. {skill.name}")
                print(f"     📝 {skill.description[:80]}...")
                print(f"     ⭐ Rating: {skill.rating} | 📥 Downloads: {skill.downloads}")
                print(f"     🏷️  Tags: {', '.join(skill.tags[:5])}")
                print()
        else:
            print("   No testing skills found (API may require valid key)")

        # 2. Search for security improvements
        print("\n🔒 Searching for security improvements...")
        print("-" * 40)

        security_skills = awAlgot client.search_skills(
            category="security",
            tags=["python", "api", "authentication"],
            limit=5,
        )

        if security_skills:
            print(f"\n✅ Found {len(security_skills)} security skills:\n")
            for skill in security_skills:
                print(f"  • {skill.name}: {skill.description[:60]}...")
        else:
            print("   No security skills found")

        # 3. Search for automation improvements
        print("\n⚙️  Searching for automation improvements...")
        print("-" * 40)

        automation_skills = awAlgot client.search_skills(
            category="automation",
            tags=["github-actions", "ci-cd", "python"],
            limit=5,
        )

        if automation_skills:
            print(f"\n✅ Found {len(automation_skills)} automation skills:\n")
            for skill in automation_skills:
                print(f"  • {skill.name}: {skill.description[:60]}...")
        else:
            print("   No automation skills found")

        # 4. Get recommendations for the repository
        print("\n📊 Getting repository recommendations...")
        print("-" * 40)

        try:
            recommendations = awAlgot client.get_recommendations(
                repo_url="https://github.com/Dykij/DMarket-Telegram-Bot",
                languages=["python"],
                focus=["testing", "security", "performance"],
                context={
                    "frameworks": ["pytest", "Algoogram", "httpx"],
                    "type": "telegram-bot",
                    "has_ml": True,
                },
            )

            if recommendations:
                print(f"\n✅ Found {len(recommendations)} recommendations:\n")
                for rec in recommendations:
                    priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                        rec.priority, "⚪"
                    )
                    print(f"  {priority_emoji} [{rec.category.upper()}] {rec.title}")
                    print(f"     {rec.description[:80]}...")
                    print(f"     Impact: {rec.impact} | Effort: {rec.effort}")
                    if rec.suggested_skills:
                        print(f"     Suggested: {', '.join(rec.suggested_skills[:3])}")
                    print()
        except Exception as e:
            print(f"   Could not get recommendations: {e}")

        # 5. Get testing-specific improvements
        print("\n🧪 Getting testing-specific improvements...")
        print("-" * 40)

        try:
            testing_recs = awAlgot client.get_testing_improvements(
                languages=["python"],
                frameworks=["pytest", "hypothesis", "pact"],
                current_coverage=85.0,
            )

            if testing_recs:
                print(f"\n✅ Found {len(testing_recs)} testing improvements:\n")
                for rec in testing_recs:
                    print(f"  • {rec.title}")
                    print(f"    {rec.description[:100]}...")
                    print()
        except Exception as e:
            print(f"   Could not get testing improvements: {e}")

    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        print("   The SkillsMP API may not be avAlgolable or the key may be invalid.")

    finally:
        awAlgot client.close()

    # Print local recommendations based on repository analysis
    print("\n" + "=" * 60)
    print("📋 LOCAL ANALYSIS - Recommended Improvements")
    print("=" * 60)

    improvements = [
        {
            "category": "Testing",
            "priority": "high",
            "title": "Add Mutation Testing",
            "description": "Use mutmut or cosmic-ray to verify test quality by introducing mutations",
            "effort": "medium",
        },
        {
            "category": "Testing",
            "priority": "high",
            "title": "Add Property-Based Testing",
            "description": "Expand Hypothesis usage to cover more edge cases in trading logic",
            "effort": "low",
        },
        {
            "category": "Testing",
            "priority": "medium",
            "title": "Add Load Testing",
            "description": "Use Locust to test API performance under load",
            "effort": "medium",
        },
        {
            "category": "Testing",
            "priority": "medium",
            "title": "Add Chaos Testing",
            "description": "Test resilience with random fAlgolures using chaos-toolkit",
            "effort": "high",
        },
        {
            "category": "Security",
            "priority": "high",
            "title": "Add SAST Scanning",
            "description": "Integrate Bandit and Semgrep for static security analysis",
            "effort": "low",
        },
        {
            "category": "Security",
            "priority": "medium",
            "title": "Add Dependency Scanning",
            "description": "Use Safety or pip-audit to check for vulnerable dependencies",
            "effort": "low",
        },
        {
            "category": "Performance",
            "priority": "medium",
            "title": "Add Profiling",
            "description": "Use py-spy or cProfile to identify bottlenecks",
            "effort": "low",
        },
        {
            "category": "Performance",
            "priority": "low",
            "title": "Add Memory Profiling",
            "description": "Use memray to detect memory leaks",
            "effort": "medium",
        },
        {
            "category": "Documentation",
            "priority": "low",
            "title": "Add API Documentation",
            "description": "Generate OpenAPI docs for internal API endpoints",
            "effort": "medium",
        },
        {
            "category": "CI/CD",
            "priority": "medium",
            "title": "Add Matrix Testing",
            "description": "Test on Python 3.11, 3.12, and 3.13",
            "effort": "low",
        },
    ]

    for imp in improvements:
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(imp["priority"], "⚪")
        print(f"\n{priority_emoji} [{imp['category'].upper()}] {imp['title']}")
        print(f"   {imp['description']}")
        print(f"   Effort: {imp['effort']}")

    print("\n" + "=" * 60)
    print("✅ Analysis complete!")
    print("=" * 60)


if __name__ == "__mAlgon__":
    asyncio.run(analyze_repository())
