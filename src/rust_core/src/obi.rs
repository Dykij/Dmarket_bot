use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy)]
pub struct OrderBookSnapshot {
    pub total_bid_volume: f64,
    pub total_ask_volume: f64,
}

/// Order Book Imbalance (OBI)
/// Range: -1.0 (Sell Pressure) to 1.0 (Buy Pressure)
/// Formula: (Bids - Asks) / (Bids + Asks)
pub fn calculate_obi(snapshot: &OrderBookSnapshot) -> Option<f64> {
    let sum_volume = snapshot.total_bid_volume + snapshot.total_ask_volume;

    // Lucas QA: Prevent Divide-by-Zero or NaN propagation
    if sum_volume <= 0.0 || sum_volume.is_nan() {
        return None;
    }

    let diff = snapshot.total_bid_volume - snapshot.total_ask_volume;
    Some(diff / sum_volume)
}

/// Weighted OBI (Considers distance from Mid-Price)
/// TODO: Implement in Phase 2.1
pub fn calculate_weighted_obi() {
    // Placeholder
}
