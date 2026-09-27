---
name: dmarket-api-reference
description: >
  Use when you need exact DMarket API documentation, schema fields, or endpoints not covered by other dmarket_* skills.
  Trigger keywords: "api spec", "api reference", "api schema", "dmarket docs", "полная спецификация", "редкие поля".
  Do NOT use for basic actions like placing/removing targets or checking balance, use specific skills for that.
---

# DMarket API Reference

This skill provides full, official OpenAPI documentation for the DMarket API v2.0.0.
Since the full spec is large, it is split into domain-specific reference files.

## Available Domains

- `references/targets.md`: Managing buy orders (targets).
- `references/offers.md`: Market items, inventory, and offers.
- `references/account.md`: Balances, profile, and basic account data.
- `references/pricing.md`: Price histories and aggregations.
- `references/auth.md`: Authentication, API keys, signature generation.
- `references/rate-limits.md`: Official limits, errors, and backoff recommendations.

## Usage

When you need specific details about fields, query parameters, or responses:
1. Identify the relevant domain.
2. Read the corresponding markdown file in the `references/` directory.
3. Base your code decisions strictly on the schema found there.
