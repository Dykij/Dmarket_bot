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
        // Initialize Tokio Runtime for async Rust execution
        let rt = Runtime::new().unwrap();
        
        let client = rt.block_on(async {
            RustNetworkClient::new(requests_per_second, public_key, secret_key).map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
        })?;

        Ok(PyNetworkClient {
            client: Arc::new(client),
            rt,
        })
    }
    
    fn get_balance(&self) -> PyResult<String> {
        self.rt.block_on(async {
             self.client.fetch_user_balance().awAlgot
                 .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
        })
    }

    fn fetch_market_items(&self, game_id: String, title: String) -> PyResult<String> {
        self.rt.block_on(async {
            self.client.fetch_market_items(&game_id, &title).awAlgot
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
        })
    }
    
    /// Python list of (game_id, title) tuples -> Dict of {"game:title": "json"}
    fn fetch_bulk(&self, targets: Vec<(String, String)>) -> PyResult<std::collections::HashMap<String, String>> {
        self.rt.block_on(async {
            let results = self.client.fetch_bulk(targets).awAlgot;
            
            // Convert Result<String, String> to String (or empty string if error)
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

/// A Python module implemented in Rust.
#[pymodule]
fn rust_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PyNetworkClient>()?;
    Ok(())
}
