# Trading Strategies Concept: The Golden Triangle (v1.0)

## Overview
This module implements multi-platform trading logic for 4 core games, using **DMarket** as the entry point, **Steam** as the valuation reference, and **Waxpeer** as the primary exit point.

## The "Golden Triangle" Logic
1. **Buy (DMarket)**: Identify underpriced items using historical data and current listings.
2. **Reference (Steam)**: Compare with Steam Community Market prices to ensure liquidity and real market value. Items with a significant discount relative to Steam are prioritized.
3. **Sell (Waxpeer)**: Transfer items to Waxpeer for P2P sale to avoid high DMarket sell fees or to capture higher regional/platform-specific prices.

## Game Specifics

| Game | Trade Lock | Volatility | Strategy Approach |
| :--- | :--- | :--- | :--- |
| **CS2** | 7 Days | High | Risk premium calculation (15%+ profit target). Needs float/sticker analysis. |
| **Dota 2** | 0-7 Days | Medium | High volume, focus on "Betting" items and Arcanas. |
| **Rust** | 0-7 Days | Medium | Focus on new releases and limited store items. |
| **TF2** | 0 Days | Low | Stable "Currency" trading (Keys, Earbuds). Minimal risk. |

## Execution Flow
- `StrategyFactory` selects the class based on `game_id`.
- `BaseStrategy` provides shared math for ROI and Fee calculations.
- `TradingEngine` orchestrates the transfer between platforms and tracks status in the DB.
