use pyo3::prelude::*;
use crate::network::RustNetworkClient;
use std::sync::Arc;
use tokio::runtime::Runtime;

mod network;
mod rate_limiter;
mod parser;
mod memory;
mod obi;

#[pyclass]
struct PyNetworkClient {
    client: Arc<RustNetworkClient>,
    rt: Runtime,
}

#[pymethods]
impl PyNetworkClient {
    #[new]
    fn new(requests_per_second: u32, public_key: String, secret_key: String) -> PyResult<Self> {
        let rt = Runtime::new().unwrap();
        let client = rt.block_on(async {
            RustNetworkClient::new(requests_per_second, public_key, secret_key).map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
        })?;
        Ok(PyNetworkClient { client: Arc::new(client), rt })
    }
    
    fn get_balance(&self) -> PyResult<String> {
        self.rt.block_on(async {
             self.client.fetch_user_balance().await
                 .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
        })
    }

    fn fetch_market_items(&self, game_id: String, title: String) -> PyResult<String> {
        self.rt.block_on(async {
            self.client.fetch_market_items(&game_id, &title).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
        })
    }

    fn buy_offer(&self, offer_id: String, price_cents: u64, asset_id: String) -> PyResult<String> {
        self.rt.block_on(async {
            self.client.buy_offer(&offer_id, price_cents, &asset_id).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
        })
    }

    fn create_sell_offer(&self, asset_id: String, price_cents: u64) -> PyResult<String> {
        self.rt.block_on(async {
            self.client.create_sell_offer(&asset_id, price_cents).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
        })
    }
    
    fn fetch_bulk(&self, targets: Vec<(String, String)>) -> PyResult<std::collections::HashMap<String, String>> {
        self.rt.block_on(async {
            let results = self.client.fetch_bulk(targets).await;
            let mut py_map = std::collections::HashMap::new();
            for (k, v) in results {
                match v {
                    Ok(json) => { py_map.insert(k, json); },
                    Err(e) => { py_map.insert(k, format!("ERROR: {}", e)); }
                }
            }
            Ok(py_map)
        })
    }
}

/// Calculate Order Book Imbalance (OBI)
/// Formula: (Buy_Vol - Sell_Vol) / (Buy_Vol + Sell_Vol)
#[pyfunction]
fn calculate_obi(buy_vol: i64, sell_vol: i64) -> f64 {
    let total = buy_vol + sell_vol;
    if total == 0 {
        return 0.0;
    }
    (buy_vol - sell_vol) as f64 / total as f64
}

#[pymodule]
fn rust_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PyNetworkClient>()?;
    m.add_function(wrap_pyfunction!(calculate_obi, m)?)?;
    Ok(())
}
