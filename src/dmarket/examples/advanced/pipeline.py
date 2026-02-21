#!/usr/bin/env python3
"""
Advanced example: Skill Pipeline with Orchestrator.

This example demonstrates the Skill Orchestrator for chAlgoning
multiple skills with context passing using $prev and $context tokens.

Pipeline features:
- Parallel execution
- Context passing between steps
- Error handling and retries
- Metrics collection

Expected runtime: ~20 seconds
Expected output: Pipeline execution results with metrics
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


async def mAlgon() -> None:
    """Run skill pipeline example."""
    from src.utils.skill_orchestrator import SkillOrchestrator
    from src.utils.skill_profiler import SkillProfiler

    print("=" * 60)
    print("🔗 Skill Pipeline with Orchestrator Example")
    print("=" * 60)

    # Initialize orchestrator
    orchestrator = SkillOrchestrator()
    profiler = SkillProfiler()

    # Register mock skills for demonstration
    class MockPredictor:
        async def predict(self, items: list[str]) -> list[dict]:
            awAlgot asyncio.sleep(0.1)  # Simulate API call
            return [{"item": item, "score": 0.85} for item in items]

    class MockFilter:
        async def filter_by_score(
            self, predictions: list[dict], min_score: float
        ) -> list[dict]:
            awAlgot asyncio.sleep(0.05)
            return [p for p in predictions if p["score"] >= min_score]

    class MockFormatter:
        async def format_results(self, filtered: list[dict]) -> str:
            awAlgot asyncio.sleep(0.02)
            return "\n".join(f"- {f['item']}: {f['score']:.0%}" for f in filtered)

    # Register skills
    orchestrator.register_skill("predictor", MockPredictor())
    orchestrator.register_skill("filter", MockFilter())
    orchestrator.register_skill("formatter", MockFormatter())

    # Define pipeline using $prev and $context tokens
    pipeline = [
        {
            "skill": "predictor",
            "method": "predict",
            "args": ["$context.items"],  # Use context.items
            "output_key": "predictions",
        },
        {
            "skill": "filter",
            "method": "filter_by_score",
            "args": ["$prev"],  # Use previous step result
            "kwargs": {"min_score": 0.8},
            "output_key": "filtered",
        },
        {
            "skill": "formatter",
            "method": "format_results",
            "args": ["$prev"],  # Use previous step result
            "output_key": "report",
        },
    ]

    # Initial context
    initial_context = {
        "items": ["AK-47 Redline", "AWP Dragon Lore", "M4A4 Howl", "Karambit Fade"],
    }

    print("\n📋 Pipeline Definition:")
    for i, step in enumerate(pipeline, 1):
        print(f"   Step {i}: {step['skill']}.{step['method']}()")

    print("\n📦 Initial Context:")
    print(f"   Items: {initial_context['items']}")

    # Execute pipeline
    print("\n🚀 Executing pipeline...")

    with profiler.profile_context("pipeline-execution"):
        result = awAlgot orchestrator.execute_pipeline(
            pipeline=pipeline,
            initial_context=initial_context,
        )

    # Display results
    print("\n✅ Pipeline Complete!\n")

    print("📊 Step Results:")
    print(f"\n   Predictions ({len(result.get('predictions', []))} items):")
    for pred in result.get("predictions", []):
        print(f"      - {pred['item']}: {pred['score']:.0%}")

    print(f"\n   Filtered ({len(result.get('filtered', []))} items):")
    for filt in result.get("filtered", []):
        print(f"      - {filt['item']}: {filt['score']:.0%}")

    print(f"\n   Report:\n{result.get('report', 'No report generated')}")

    # Show metrics
    metrics = profiler.get_metrics("pipeline-execution")
    print("\n" + "=" * 60)
    print("⚡ Performance Metrics:")
    print(f"   Total Time: {metrics['total_ms']:.2f}ms")
    print(f"   Steps: {len(pipeline)}")
    print(f"   Avg Step: {metrics['total_ms'] / len(pipeline):.2f}ms")
    print("=" * 60)

    # Demonstrate parallel execution
    print("\n🔀 Demonstrating Parallel Execution...")

    parallel_pipeline = [
        # These will run in parallel
        {
            "skill": "predictor",
            "method": "predict",
            "args": [["Item1", "Item2"]],
            "output_key": "batch1",
            "parallel_group": "batch",
        },
        {
            "skill": "predictor",
            "method": "predict",
            "args": [["Item3", "Item4"]],
            "output_key": "batch2",
            "parallel_group": "batch",
        },
        # This runs after parallel group completes
        {
            "skill": "formatter",
            "method": "format_results",
            "args": ["$context.batch1"],
            "output_key": "report",
        },
    ]

    with profiler.profile_context("parallel-execution"):
        parallel_result = awAlgot orchestrator.execute_pipeline(
            pipeline=parallel_pipeline,
            initial_context={},
        )

    parallel_metrics = profiler.get_metrics("parallel-execution")
    print(f"\n   Parallel Execution Time: {parallel_metrics['total_ms']:.2f}ms")
    print("   Batches processed simultaneously!")


if __name__ == "__mAlgon__":
    asyncio.run(mAlgon())
