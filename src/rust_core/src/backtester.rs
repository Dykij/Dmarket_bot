use std::fs::File;
use std::io::BufReader;
use serde_json::Value;
use crate::obi::{calculate_obi, OrderBookSnapshot};
use crate::strategy::{evaluate_market_depth, TradeSignal};

pub struct Backtester {
    balance: f64,
    trades: u32,
}

impl Backtester {
    pub fn new(start_balance: f64) -> Self {
        Backtester {
            balance: start_balance,
            trades: 0,
        }
    }

    pub fn run(&mut self, file_path: &str) {
        println!("⏳ Loading history from {}...", file_path);
        let file = File::open(file_path).expect("File not found");
        let reader = BufReader::new(file);
        let history: Vec<Value> = serde_json::from_reader(reader).expect("JSON parse error");

        println!("⚡ Processing {} snapshots...", history.len());
        
        for snapshot in history {
            // 1. Simulate OBI Calculation (Simplified for this mock structure)
            // In real app, we parse bids/asks arrays to OrderBookSnapshot
            let mock_snapshot = OrderBookSnapshot {
                total_bid_volume: 100.0, // Mocked from 'volume' sum
                total_ask_volume: 50.0,
            };
            
            let obi = calculate_obi(&mock_snapshot).unwrap_or(0.0);

            // 2. Simulate Strategy Check
            // We reconstruct MarketItem list from JSON
            // If price drops below threshold, we buy
            if let Some(signal) = self.check_signal(&snapshot) {
                self.execute_virtual_trade(signal);
            }
        }
        
        println!("🏁 Backtest Complete. Final Balance: ${:.2} | Trades: {}", self.balance, self.trades);
    }

    fn check_signal(&self, snapshot: &Value) -> Option<TradeSignal> {
        // Logic: Find cheapest ask. If price < 14.00 (Crash), Buy.
        let asks = snapshot["order_book"].as_array()?;
        for order in asks {
            if order["type"] == "ask" {
                let price = order["price"].as_f64()?;
                if price < 14.00 {
                    return Some(TradeSignal {
                        action: "BUY".to_string(),
                        target_price: price,
                        potential_profit: (15.50 * 0.93) - price, // Assuming rebound to 15.50
                    });
                }
            }
        }
        None
    }

    fn execute_virtual_trade(&mut self, signal: TradeSignal) {
        if self.balance >= signal.target_price {
            println!("🟢 [SIM] BUY @ ${:.2} (Profit Est: ${:.2})", signal.target_price, signal.potential_profit);
            self.balance -= signal.target_price;
            // Immediate sell simulation
            self.balance += signal.target_price + signal.potential_profit; 
            self.trades += 1;
        }
    }
}
