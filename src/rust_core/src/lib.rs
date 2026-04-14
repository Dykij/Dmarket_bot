use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use serde::{Deserialize, Serialize};
use regex::Regex;
use std::sync::OnceLock;

static INJECTION_REGEX: OnceLock<Regex> = OnceLock::new();

#[derive(Debug, Serialize, Deserialize)]
struct SkinData {
    item_id: String,
    price_usd: f64,
    name: String,
}

#[pyclass]
struct ParsedSkin {
    #[pyo3(get)]
    item_id: String,
    #[pyo3(get)]
    price_usd: f64,
    #[pyo3(get)]
    name: String,
}

#[pyfunction]
fn validate_dmarket_response_rs(raw_json: &str) -> PyResult<ParsedSkin> {
    let re = INJECTION_REGEX.get_or_init(|| {
        Regex::new(r"[\<\>\{\}\$\`\\]").expect("Invalid regex pattern")
    });

    let mut data: SkinData = serde_json::from_str(raw_json)
        .map_err(|e| PyValueError::new_err(format!("JSON Deserialization Error: {}", e)))?;

    // Pre-validation sanitizer for Prompt Injection (matching Python logic)
    if re.is_match(&data.name) {
        data.name = re.replace_all(&data.name, "").to_string();
    }

    if data.price_usd < 0.01 {
        return Err(PyValueError::new_err("Price must be at least 0.01 USD"));
    }

    Ok(ParsedSkin {
        item_id: data.item_id,
        price_usd: data.price_usd,
        name: data.name,
    })
}

#[pymodule]
fn dmarket_parser_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(validate_dmarket_response_rs, m)?)?;
    m.add_class::<ParsedSkin>()?;
    Ok(())
}
