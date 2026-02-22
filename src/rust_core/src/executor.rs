use crate::rate_limiter::DMarketLimiter;
use crate::strategy::TradeSignal;
use crate::network::RustNetworkClient;

// SAFETY: Set to FALSE only when ready for Real Money Trade
const TEST_MODE: bool = true;

pub struct OrderExecutor {
    limiter: DMarketLimiter,
    network: RustNetworkClient,
}

impl OrderExecutor {
    pub fn new(limiter: DMarketLimiter, network: RustNetworkClient) -> Self {
        OrderExecutor { limiter, network }
    }

    /// Executes trade based on signal.
    /// Returns: Order ID (String) or "DRY_RUN"
    pub async fn execute(&self, signal: TradeSignal) -> Result<String, String> {
        // 1. Check Rate Limit (Governor)
        self.limiter.acquire().await;

        match signal.action.as_str() {
            "BUY" => {
                if TEST_MODE {
                    let log_msg = format!(
                        "🔵 [DRY RUN] WOULD BUY: Item at ${} | Profit: ${:.2}",
                        signal.target_price, signal.potential_profit
                    );
                    println!("{}", log_msg); // In prod, send to structured log
                    return Ok("DRY_RUN_ID".to_string());
                } else {
                    // REAL TRADE LOGIC (Blocked by TEST_MODE)
                    // let response = self.network.post_buy_order(...)
                    return Err("Real trading not yet enabled".to_string());
                }
            },
            "SELL" => {
                // Sell logic...
                Ok("SELL_ORDER_ID".to_string())
            },
            _ => Ok("NO_ACTION".to_string()),
        }
    }
}
