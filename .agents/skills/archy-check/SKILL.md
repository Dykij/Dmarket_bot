---
name: archy-check
description: Architecture health check using Archy sensor. Use when reviewing code changes, before commits, or when investigating architectural issues. Detects cycles, complexity hotspots, layer violations, and tracks architecture score over time.
---

# Archy Architecture Check

## When to Use
- Before committing significant code changes
- When reviewing PRs that touch multiple modules
- When investigating architectural drift or complexity
- During heartbeats to track architecture health trends
- When adding new modules or refactoring existing ones

## Available Commands

### Quick Score
```bash
archy score .
```
One-shot architectural health number (0-1.0). Track over time.

### Find Cycles
```bash
archy cycles .
```
Detects circular imports that create hidden coupling.

### Hotspots
```bash
archy hotspots .
```
Files ranked by cyclomatic complexity × git churn. These are the files most likely to break.

### Full Graph
```bash
archy graph .
```
Visualize module dependencies.

### Layer Check
```bash
archy check .
```
Verify layer rules defined in archy.yaml are respected.

### What to Refactor Next
```bash
archy what-to-refactor-next .
```
Fused priority list combining complexity and change frequency.

## Scoring Guide

| Score | Rating | Action |
|-------|--------|--------|
| 0.80+ | Excellent | Maintain current practices |
| 0.60-0.79 | Good | Minor improvements possible |
| 0.40-0.59 | Fair | Plan refactoring for hotspots |
| <0.40 | Poor | Immediate architectural attention needed |

## DMarket Bot Current Metrics

- **Architecture Score**: 0.561 (Fair)
- **Cycles**: 6 found (2 mutual, 4 self-imports)
- **Top Hotspot**: `core.target_sniping.core` (score: 3160)
- **Modularity**: 0.688 (24 communities)
- **Acyclicity**: 0.955

## Integration with Other Skills

- **code-reviewer**: Run `archy hotspots` before reviewing to focus on high-risk files
- **git-gate**: Run `archy check` in Phase 2 (FULL) validation
- **pre-deploy-audit**: Run `archy score --record` to track deployment impact
