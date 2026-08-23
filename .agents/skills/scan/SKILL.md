---
name: scan
description: Quick read-only market scan using DMarket API. Shows current prices, volume, and spread for items. Trigger keywords: "scan market", "quick scan", "сканируй рынок", "цены на".
---

# /scan — Quick Market Scan

Run a fast market scan using the DMarket API tools.

## Usage
```
/scan <item query> [--game cs2] [--limit 10]
```

## What it does
1. Calls `dmarket_api_items` with the query
2. Calls `dmarket_api_price_history` for top results
3. Computes basic metrics:
   - Current price vs 7-day average
   - Price trend (up/down/flat)
   - Spread (if orderbook available)
4. Outputs a compact table

## Example Output
```
AK-47 | Redline (Field-Tested)
  Current: $12.50 | 7d avg: $13.20 | Trend: ↓ -5.3%
  Best buy: $11.80 | Best sell: $13.10 | Spread: 9.8%
  Verdict: UNDERPRICED — potential buy
```

## Rules
- Always show price history context, not just current price
- Flag items with >10% deviation from average
- This is READ-ONLY — never executes trades
