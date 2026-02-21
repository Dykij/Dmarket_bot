# HFT Statistical Arbitrage with Rust
*Source: ClawHub / GitHub / QuantConnect*

## Strategy: PAlgors Trading via Cointegration
Instead of directional bets, we find two assets that move together (e.g., AK-47 Redline FT and MW).
1.  **Calculate Spread:** `Spread = Price_A - (Hedge_Ratio * Price_B)`
2.  **Z-Score:** `(Spread - Mean) / StdDev`
3.  **Signal:**
    *   `Z > 2`: Short A, Long B.
    *   `Z < -2`: Long A, Short B.

## Rust Implementation
*   **Crate:** `linfa` (Machine Learning) or `polars` (Dataframes).
*   **Speed:** Rust calculates Z-Score on 1000 items in < 50 microseconds.
*   **Risk:** Zero-allocation required. Use `bumpalo` for temporary float arrays.
