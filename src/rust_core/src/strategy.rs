use serde::{Deserialize, Serialize};

const FEE_DMARKET: f64 = 0.07; // 7% Standard Fee (TODO: Dynamic adjustment)

#[derive(Serialize, Deserialize, Debug)]
pub struct MarketItem {
    pub title: String,
    pub price: f64, // Normalized USD
    pub amount: u32,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct TradeSignal {
    pub action: String, // "BUY", "SELL", "HOLD"
    pub target_price: f64,
    pub potential_profit: f64,
}

/// The Predator's Eye: Evaluates Market Depth for gaps
pub fn evaluate_market_depth(order_book: Vec<MarketItem>, min_profit_usd: f64) -> Option<TradeSignal> {
    if order_book.is_empty() {
        return None;
    }

    // Sort by price ascending (Cheapest first)
    let mut sorted_book = order_book;
    sorted_book.sort_by(|a, b| a.price.partial_cmp(&b.price).unwrap());

    // Strategy 1: The "Wall" Breaker
    // Look for a gap between the lowest price and the next major price cluster
    let best_price = sorted_book[0].price;
    
    // Simulate "Instant Sell" price (approximated as lowest listing for now, 
    // ideally we need Bid data which is harder to get via public API)
    let sell_price = best_price * 1.05; // Target +5% listing strategy

    // Net Profit Calculation (Lucas QA Verified)
    // Profit = (Sell Price * (1 - Fee)) - Buy Price
    let net_return = (sell_price * (1.0 - FEE_DMARKET)) - best_price;

    if net_return > min_profit_usd {
        return Some(TradeSignal {
            action: "BUY".to_string(),
            target_price: best_price,
            potential_profit: net_return,
        });
    }

    None
}
