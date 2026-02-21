mod memory;
mod parser;
mod rate_limiter;
mod obi;
mod strategy; // Contains TradeSignal
mod network;
mod executor;
#[path = "math/cointegration.rs"] mod cointegration;

use memory::OrderBookArena;
use rate_limiter::DMarketLimiter;
use network::RustNetworkClient;
use executor::OrderExecutor;
use std::sync::Arc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("🚀 Starting DMarket HFT Core (Rust Native)...");

    // 1. Initialize Memory Arenas (Bumpalo)
    let mut arena = OrderBookArena::new();

    // 2. Initialize Rate Limiter (3 RPS)
    let limiter = DMarketLimiter::new(3);

    // 3. Initialize Network (HTTP/2)
    // Note: In real app, API Key comes from env var, NOT hardcoded here.
    let network = RustNetworkClient::new().map_err(|e| format!("{}", e))?;

    // 4. Initialize Executor
    let executor = Arc::new(OrderExecutor::new(limiter, network));

    println!("✅ Core Initialized. TEST_MODE: ON. Ready for signals.");

    // Loop would go here...
    // 1. network.get_market_items()
    // 2. parser.parse_order_book(arena)
    // 3. obi.calculate_obi()
    // 4. strategy.evaluate_market_depth() -> Signal
    // 5. executor.execute(signal)
    // 6. arena.reset()

    Ok(())
}
