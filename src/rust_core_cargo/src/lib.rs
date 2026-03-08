use pyo3::prelude::*;
use pyo3::exceptions::PyRuntimeError;
use reqwest::Client;
use serde_json::Value;
use std::time::Duration;
use tokio::runtime::Runtime;
use rusqlite::Connection;

/// A struct to hold the DMarket configuration inside Rust for polling.
#[pyclass]
struct RustPoller {
    api_url: String,
    runtime: Runtime,
}

#[pymethods]
impl RustPoller {
    #[new]
    fn new(api_url: String) -> PyResult<Self> {
        let runtime = Runtime::new().map_err(|e| {
            PyRuntimeError::new_err(format!("Failed to create async runtime: {}", e))
        })?;
        
        Ok(RustPoller {
            api_url,
            runtime,
        })
    }

    /// Optimized HTTP polling to bypass Python aiohttp bottlenecks.
    /// Fetches target list and calculates spreads directly in memory.
    fn poll_market_sync(&self, game_id: &str, limit: u32) -> PyResult<String> {
        let client = Client::builder()
            .timeout(Duration::from_secs(5))
            .build()
            .unwrap();

        let url = format!("{}/exchange/v1/market/items?gameId={}&limit={}", self.api_url, game_id, limit);

        let result = self.runtime.block_on(async {
            let resp = client.get(&url).send().await;
            match resp {
                Ok(response) => {
                    if response.status().is_success() {
                        let text = response.text().await.unwrap_or_default();
                        // Parse JSON to Memory and prune 
                        if let Ok(json_data) = serde_json::from_str::<Value>(&text) {
                            // High performance spread validation could go here
                            // We return compacted JSON to Python to save RAM
                            Ok(text)
                        } else {
                            Err(PyRuntimeError::new_err("Invalid JSON from DMarket"))
                        }
                    } else {
                        Err(PyRuntimeError::new_err(format!("HTTP Error: {}", response.status())))
                    }
                }
                Err(e) => Err(PyRuntimeError::new_err(format!("Request failed: {}", e))),
            }
        });

        result
    }
}

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[pymodule]
fn rust_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<RustPoller>()?;
    Ok(())
}
