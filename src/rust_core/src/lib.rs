use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use serde::{Deserialize, Serialize};
use regex::Regex;
use std::sync::OnceLock;
use ed25519_dalek::{SigningKey, Signer};

static INJECTION_REGEX: OnceLock<Regex> = OnceLock::new();

#[derive(Debug, Serialize, Deserialize)]
struct SkinData {
    #[serde(rename = "itemId")]
    item_id: String,
    #[serde(rename = "price")]
    price_usd: serde_json::Value, // Can be string or number in some API versions
    #[serde(rename = "title")]
    name: String,
}

#[derive(Debug, Deserialize)]
struct MarketResponse {
    objects: Vec<SkinData>,
}

#[pyclass]
#[derive(Clone)]
struct ParsedSkin {
    #[pyo3(get)]
    item_id: String,
    #[pyo3(get)]
    price_usd: f64,
    #[pyo3(get)]
    name: String,
}

#[pyfunction]
fn generate_signature_rs(method: &str, path: &str, body: &str, timestamp: &str, secret_hex: &str) -> PyResult<String> {
    let seed = hex::decode(secret_hex)
        .map_err(|e| PyValueError::new_err(format!("Invalid hex secret: {}", e)))?;
    
    // Support both 128-char and 64-char hex keys
    let seed_slice = if seed.len() == 64 { &seed[..32] } else { &seed[..] };
    
    let signing_key = SigningKey::from_slice(seed_slice)
        .map_err(|e| PyValueError::new_err(format!("Invalid seed length: {}", e)))?;
    
    let message = format!("{}{}{}{}", method.to_uppercase(), path, body, timestamp);
    let signature = signing_key.sign(message.as_bytes());
    
    Ok(hex::encode(signature.to_bytes()))
}

#[pyfunction]
fn parse_market_response_rs(raw_json: &str) -> PyResult<Vec<ParsedSkin>> {
    let re = INJECTION_REGEX.get_or_init(|| {
        Regex::new(r"[\<\>\{\}\$\`\\]").expect("Invalid regex pattern")
    });

    let data: MarketResponse = serde_json::from_str(raw_json)
        .map_err(|e| PyValueError::new_err(format!("JSON Batch Deserialization Error: {}", e)))?;

    let mut results = Vec::new();
    for item in data.objects {
        let mut name = item.name;
        if re.is_match(&name) {
            name = re.replace_all(&name, "").to_string();
        }

        let price = match item.price_usd {
            serde_json::Value::Number(n) => n.as_f64().unwrap_or(0.0),
            serde_json::Value::String(s) => s.parse::<f64>().unwrap_or(0.0) / 100.0, // Some DMarket APIs return cents as string
            _ => 0.0,
        };

        results.push(ParsedSkin {
            item_id: item.item_id,
            price_usd: price,
            name,
        });
    }

    Ok(results)
}

#[pyfunction]
fn validate_dmarket_response_rs(raw_json: &str) -> PyResult<ParsedSkin> {
    let re = INJECTION_REGEX.get_or_init(|| {
        Regex::new(r"[\<\>\{\}\$\`\\]").expect("Invalid regex pattern")
    });

    // Handle single item format (legacy or specific endpoints)
    #[derive(Deserialize)]
    struct SingleSkin {
        item_id: String,
        price_usd: f64,
        name: String,
    }

    let mut data: SingleSkin = serde_json::from_str(raw_json)
        .map_err(|e| PyValueError::new_err(format!("JSON Deserialization Error: {}", e)))?;

    if re.is_match(&data.name) {
        data.name = re.replace_all(&data.name, "").to_string();
    }

    Ok(ParsedSkin {
        item_id: data.item_id,
        price_usd: data.price_usd,
        name: data.name,
    })
}

#[pymodule]
fn dmarket_parser_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(generate_signature_rs, m)?)?;
    m.add_function(wrap_pyfunction!(parse_market_response_rs, m)?)?;
    m.add_function(wrap_pyfunction!(validate_dmarket_response_rs, m)?)?;
    m.add_class::<ParsedSkin>()?;
    Ok(())
}
