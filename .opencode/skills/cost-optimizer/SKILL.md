---
name: cost-optimizer
description: Monitor and optimize token usage and API costs for DMarket bot development on Steam Deck. Trigger keywords: "cost", "tokens", "budget", "spending", "расходы", "токены", "бюджет", "optimize cost".
license: MIT
compatibility: opencode
metadata:
  platform: steam-deck
  priority: medium
---

## What I do

Help optimize token usage, API costs, and resource consumption during DMarket bot development, especially constrained environments like Steam Deck OLED (16GB shared RAM).

## When to use me

Use this skill when:
- Token usage seems high or budget is a concern
- Context window is getting full (compaction needed)
- Running on constrained hardware (Steam Deck, laptop)
- Need to reduce API calls or batch operations
- Reviewing which MCP servers/plugins are consuming resources

## Optimization Strategies

### 1. Token Budget Management

```bash
# Check current session token usage
# OpenCode shows token count in the status bar

# Recommended daily budgets for Steam Deck:
# - Light dev (code review, small fixes): ~50K tokens
# - Medium dev (feature work): ~150K tokens
# - Heavy dev (refactoring, debugging): ~300K tokens
```

### 2. Context Window Optimization

- **Auto-compaction** is enabled (`tail_turns: 15`) — old messages are compressed
- Use `plan` agent for analysis (no code changes, less context)
- Use `explore` subagent for search (isolated context)
- Avoid reading large files unnecessarily — use `grep` first

### 3. MCP Resource Awareness

Current MCP: `sequential-thinking` (lightweight, ~5MB RAM)

If adding more MCP servers, monitor:
- RAM usage: `free -h` before/after
- Context tokens: each MCP tool adds ~200-500 tokens to system prompt
- Network latency: WiFi on Steam Deck adds 50-200ms per MCP call

### 4. Plugin Efficiency

Active plugins and their impact:
- `opencode-vibeguard` — negligible overhead, protects secrets
- `opencode-dynamic-context-pruning` — saves tokens by removing stale tool outputs
- `opencode-shell-strategy` — prevents shell hangs, no token cost

### 5. Batch Operations

Instead of multiple small edits:
```
# Bad: 3 separate edit calls
edit file A, edit file B, edit file C

# Good: Read all, plan, then batch edits
read A, read B, read C → plan → edit A, edit B, edit C
```

### 6. Subagent Delegation

Use subagents for isolated tasks to keep main context clean:
- `@explore` — codebase search (returns summary, not full files)
- `@general` — multi-step tasks that don't need main context
- `@plan` — analysis without code changes

### 7. Model Selection

For Steam Deck, use smaller models when possible:
- `kimi-k2.6` — good balance of speed and quality
- Avoid `opus` or `sonnet` class models — slower on Zen 2 CPU
- Use `small_model` for quick tasks (explore, title generation)

## Monitoring Commands

```bash
# Check RAM usage
free -h

# Check disk usage
df -h ~

# Check OpenCode process memory
ps aux | grep opencode

# Check MCP server processes
ps aux | grep -E "sequential|thinking"
```

## Cost-Saving Tips

1. **Read before edit** — always read the file first to avoid wasted edits
2. **Use grep/glob** — find files before reading them
3. **Batch parallel reads** — read multiple files in one message
4. **Plan before code** — use plan agent to analyze, then implement
5. **Commit early** — avoid losing work and having to redo
6. **Use trash over rm** — recoverable mistakes are cheaper than re-creation
