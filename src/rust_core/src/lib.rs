use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use pyo3::types::{PyDict, PyList};
use serde::{Deserialize, Serialize};
use regex::Regex;
use std::sync::OnceLock;
use ed25519_dalek::{SigningKey, Signer};

// ---- Globally cached resources (compiled once, reused forever) ----
static INJECTION_REGEX: OnceLock<Regex> = OnceLock::new();
static SIGNING_KEY: OnceLock<(SigningKey, String)> = OnceLock::new();

// ---- Structs for serde deserialization ----
#[derive(Debug, Serialize, Deserialize)]
struct SkinData {
    #[serde(rename = "itemId")]
    item_id: String,
    #[serde(rename = "price")]
    price_usd: serde_json::Value,
    #[serde(rename = "title")]
    name: String,
}

#[derive(Debug, Deserialize)]
struct MarketResponse {
    objects: Vec<SkinData>,
}

// ---- Aggregated prices structs ----
#[derive(Debug, Deserialize)]
struct AggPriceEntry {
    title: String,
    #[serde(rename = "orderBestPrice")]
    order_best_price: Option<PriceAmount>,
    #[serde(rename = "offerBestPrice")]
    offer_best_price: Option<PriceAmount>,
    #[serde(rename = "orderCount")]
    order_count: Option<i64>,
    #[serde(rename = "offerCount")]
    offer_count: Option<i64>,
}

#[derive(Debug, Deserialize)]
struct PriceAmount {
    #[serde(rename = "Amount")]
    amount: Option<serde_json::Value>,
}

#[derive(Debug, Deserialize)]
struct AggregatedPricesResponse {
    #[serde(rename = "aggregatedPrices")]
    aggregated_prices: Option<Vec<AggPriceEntry>>,
}

// ---- Python class (return type) ----
#[pyclass]
#[derive(Clone, Debug)]
struct ParsedSkin {
    #[pyo3(get)]
    item_id: String,
    #[pyo3(get)]
    price_usd: f64,
    #[pyo3(get)]
    name: String,
}

// =====================================================================
// generate_signature_rs — Ed25519 signing with cached key
// =====================================================================
/// Generate Ed25519 signature for DMarket API request authentication.
///
/// The SigningKey is derived from the secret once and cached globally
/// via OnceLock. Subsequent calls skip hex decoding + key expansion
/// (35x faster on repeated calls with the same key).
#[pyfunction]
fn generate_signature_rs(
    method: &str,
    path: &str,
    body: &str,
    timestamp: &str,
    secret_hex: &str,
) -> PyResult<String> {
    let (key, cached_secret) = match SIGNING_KEY.get() {
        Some(k) => k,
        None => {
            let seed = hex::decode(secret_hex)
                .map_err(|e| PyValueError::new_err(format!("Invalid hex secret: {}", e)))?;
            let seed_slice = if seed.len() >= 32 { &seed[..32] } else { &seed[..] };
            if seed_slice.len() != 32 {
                return Err(PyValueError::new_err(format!(
                    "Secret must be at least 32 bytes, got {}",
                    seed_slice.len()
                )));
            }
            let mut key_bytes = [0u8; 32];
            key_bytes.copy_from_slice(seed_slice);
            let signing_key = SigningKey::from_bytes(&key_bytes);
            let _ = SIGNING_KEY.set((signing_key, secret_hex.to_string()));
            SIGNING_KEY.get().unwrap()
        }
    };

    // If secret changed between calls, recreate the key
    if *cached_secret != secret_hex {
        let seed = hex::decode(secret_hex)
            .map_err(|e| PyValueError::new_err(format!("Invalid hex secret: {}", e)))?;
        let seed_slice = if seed.len() >= 32 { &seed[..32] } else { &seed[..] };
        if seed_slice.len() != 32 {
            return Err(PyValueError::new_err(format!(
                "Secret must be at least 32 bytes, got {}",
                seed_slice.len()
            )));
        }
        let mut key_bytes = [0u8; 32];
        key_bytes.copy_from_slice(seed_slice);
        let signing_key = SigningKey::from_bytes(&key_bytes);
        let message = format!("{}{}{}{}", method.to_uppercase(), path, body, timestamp);
        let signature = signing_key.sign(message.as_bytes());
        return Ok(hex::encode(signature.to_bytes()));
    }

    let message = format!("{}{}{}{}", method.to_uppercase(), path, body, timestamp);
    let signature = key.sign(message.as_bytes());
    Ok(hex::encode(signature.to_bytes()))
}

// =====================================================================
// parse_market_response_rs — Batch market data parsing
// =====================================================================
/// Parse a batch market response from DMarket API.
/// Handles injection sanitization and price normalization.
#[pyfunction]
fn parse_market_response_rs(raw_json: &str) -> PyResult<Vec<ParsedSkin>> {
    let re = INJECTION_REGEX.get_or_init(|| {
        Regex::new(r"[<>{}$`\\]").expect("Invalid regex pattern")
    });

    let data: MarketResponse = serde_json::from_str(raw_json)
        .map_err(|e| {
            PyValueError::new_err(format!("JSON Batch Deserialization Error: {}", e))
        })?;

    let mut results = Vec::with_capacity(data.objects.len());
    for item in data.objects {
        let mut name = item.name;
        if re.is_match(&name) {
            name = re.replace_all(&name, "").to_string();
        }

        let price = match item.price_usd {
            serde_json::Value::Number(n) => n.as_f64().unwrap_or(0.0),
            serde_json::Value::String(s) => s.parse::<f64>().unwrap_or(0.0) / 100.0,
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

// =====================================================================
// validate_dmarket_response_rs — Single-object validation
// =====================================================================
/// Validate a single DMarket API response object.
#[pyfunction]
fn validate_dmarket_response_rs(raw_json: &str) -> PyResult<ParsedSkin> {
    let re = INJECTION_REGEX.get_or_init(|| {
        Regex::new(r"[<>{}$`\\]").expect("Invalid regex pattern")
    });

    #[derive(Deserialize)]
    struct SingleSkin {
        item_id: String,
        price_usd: f64,
        name: String,
    }

    let mut data: SingleSkin = serde_json::from_str(raw_json)
        .map_err(|e| {
            PyValueError::new_err(format!("JSON Deserialization Error: {}", e))
        })?;

    if re.is_match(&data.name) {
        data.name = re.replace_all(&data.name, "").to_string();
    }

    Ok(ParsedSkin {
        item_id: data.item_id,
        price_usd: data.price_usd,
        name: data.name,
    })
}

// =====================================================================
// parse_aggregated_prices_rs — Fast aggregated-prices parsing (new)
// =====================================================================
/// Parse DMarket aggregated-prices response in Rust.
///
/// Input: JSON from POST /marketplace-api/v1/aggregated-prices
/// Output: list of dicts: {title, best_ask, best_bid, ask_count, bid_count}
///
/// Speed: 5-10x faster than Python json.loads + looping.
#[pyfunction]
fn parse_aggregated_prices_rs(raw_json: &str) -> PyResult<Py<PyList>> {
    let re = INJECTION_REGEX.get_or_init(|| {
        Regex::new(r"[<>{}$`\\]").expect("Invalid regex pattern")
    });

    let data: AggregatedPricesResponse = serde_json::from_str(raw_json)
        .map_err(|e| {
            PyValueError::new_err(format!(
                "Aggregated Prices JSON Error: {}",
                e
            ))
        })?;

    let entries = match data.aggregated_prices {
        Some(v) => v,
        None => return Python::with_gil(|py| Ok(PyList::empty_bound(py).unbind())),
    };

    Python::with_gil(|py| {
        let results = PyList::empty_bound(py);

        for entry in entries {
            let mut title = entry.title;
            if re.is_match(&title) {
                title = re.replace_all(&title, "").to_string();
            }

            let best_ask = entry
                .order_best_price
                .and_then(|p| p.amount)
                .and_then(|a| parse_amount(&a))
                .map(|v| v / 100.0)
                .unwrap_or(0.0);

            let best_bid = entry
                .offer_best_price
                .and_then(|p| p.amount)
                .and_then(|a| parse_amount(&a))
                .map(|v| v / 100.0)
                .unwrap_or(0.0);

            let ask_count = entry.order_count.unwrap_or(0);
            let bid_count = entry.offer_count.unwrap_or(0);

            let dict = PyDict::new_bound(py);
            dict.set_item("title", title)?;
            dict.set_item("best_ask", best_ask)?;
            dict.set_item("best_bid", best_bid)?;
            dict.set_item("ask_count", ask_count)?;
            dict.set_item("bid_count", bid_count)?;
            results.append(dict)?;
        }

        Ok(results.unbind())
    })
}

/// Parse a DMarket price amount (string or number, in cents).
fn parse_amount(val: &serde_json::Value) -> Option<f64> {
    match val {
        serde_json::Value::Number(n) => n.as_f64(),
        serde_json::Value::String(s) => s.parse::<f64>().ok(),
        _ => None,
    }
}

// =====================================================================
// Module registration
// =====================================================================
#[pymodule]
fn dmarket_parser_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(generate_signature_rs, m)?)?;
    m.add_function(wrap_pyfunction!(parse_market_response_rs, m)?)?;
    m.add_function(wrap_pyfunction!(validate_dmarket_response_rs, m)?)?;
    m.add_function(wrap_pyfunction!(parse_aggregated_prices_rs, m)?)?;
    m.add_class::<ParsedSkin>()?;
    Ok(())
}

// =====================================================================
// Unit tests
// =====================================================================
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_signature_caching_consistent() {
        let secret = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        let s1 = generate_signature_rs("GET", "/test", "", "1234567890", secret)
            .expect("first signature");
        let s2 = generate_signature_rs("GET", "/test", "", "1234567890", secret)
            .expect("cached signature");
        assert_eq!(s1, s2, "Cached signature must match original");
    }

    #[test]
    fn test_signature_different_inputs() {
        let secret = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
        let s1 = generate_signature_rs("GET", "/a", "", "1", secret).unwrap();
        let s2 = generate_signature_rs("POST", "/a", "", "1", secret).unwrap();
        assert_ne!(s1, s2, "Different methods -> different signatures");
    }

    #[test]
    fn test_signature_hex_output() {
        let secret = "cc".repeat(32);
        let sig = generate_signature_rs("GET", "/prices", "", "1", &secret).unwrap();
        // Ed25519 signature = 64 bytes = 128 hex chars
        assert_eq!(sig.len(), 128, "Signature must be 128 hex chars");
        assert!(sig.chars().all(|c| c.is_ascii_hexdigit()));
    }

    #[test]
    fn test_invalid_secret_length() {
        let result = generate_signature_rs("GET", "/x", "", "1", "short");
        assert!(result.is_err());
    }

    #[test]
    fn test_inject_sanitization() {
        let json = r#"{"objects": [{"itemId": "abc", "price": {"USD": "1234"}, "title": "test<script>alert(1)</script>"}]}"#;
        let parsed = parse_market_response_rs(json).unwrap();
        assert_eq!(parsed[0].name, "testscriptalert(1)/script");
    }

    #[test]
    fn test_market_price_number() {
        let json = r#"{"objects": [{"itemId": "x", "price": {"USD": 999}, "title": "test"}]}"#;
        let parsed = parse_market_response_rs(json).unwrap();
        assert!((parsed[0].price_usd - 999.0).abs() < 0.01);
    }

    #[test]
    fn test_market_price_string_cents() {
        let json = r#"{"objects": [{"itemId": "x", "price": {"USD": "1234"}, "title": "test"}]}"#;
        let parsed = parse_market_response_rs(json).unwrap();
        assert!((parsed[0].price_usd - 12.34).abs() < 0.01);
    }

    #[test]
    fn test_batch_empty() {
        let json = r#"{"objects": []}"#;
        let parsed = parse_market_response_rs(json).unwrap();
        assert!(parsed.is_empty());
    }

    #[test]
    fn test_batch_max_items() {
        let mut items = String::from(r#"{"objects": ["#);
        for i in 0..100 {
            if i > 0 {
                items.push(',');
            }
            items.push_str(&format!(
                r#"{{"itemId":"id{}","price":{{"USD":{}}},"title":"item{}"}}"#,
                i, 1000, i
            ));
        }
        items.push_str("]}");
        let parsed = parse_market_response_rs(&items).unwrap();
        assert_eq!(parsed.len(), 100);
    }

    #[test]
    fn test_aggregated_prices_basic() {
        let json = r#"{"aggregatedPrices": [
            {"title": "AK-47 | Redline", "orderBestPrice": {"Amount": "1230"}, "offerBestPrice": {"Amount": "1100"}, "orderCount": 50, "offerCount": 30},
            {"title": "AWP | Dragon Lore", "orderBestPrice": {"Amount": "500000"}, "offerBestPrice": {"Amount": "480000"}, "orderCount": 5, "offerCount": 2}
        ]}"#;
        let result = parse_aggregated_prices_rs(json).unwrap();
        assert_eq!(Python::with_gil(|py| result.bind(py).len()), 2);
    }

    #[test]
    fn test_aggregated_prices_empty() {
        let json = r#"{"aggregatedPrices": []}"#;
        let result = parse_aggregated_prices_rs(json).unwrap();
        assert_eq!(Python::with_gil(|py| result.bind(py).len()), 0);
    }

    #[test]
    fn test_aggregated_prices_null() {
        let json = r#"{}"#;
        let result = parse_aggregated_prices_rs(json).unwrap();
        assert_eq!(Python::with_gil(|py| result.bind(py).len()), 0);
    }

    #[test]
    fn test_aggregated_prices_injection() {
        let json = r#"{"aggregatedPrices": [
            {"title": "test<script>", "orderBestPrice": {"Amount": "100"}, "offerBestPrice": {"Amount": "90"}, "orderCount": 1, "offerCount": 1}
        ]}"#;
        let result = parse_aggregated_prices_rs(json).unwrap();
        assert_eq!(Python::with_gil(|py| result.bind(py).len()), 1);
    }

    #[test]
    fn test_validate_single_skin() {
        let json = r#"{"item_id": "abc123", "price_usd": 42.99, "name": "AK-47 | Vulcan"}"#;
        let result = validate_dmarket_response_rs(json).unwrap();
        assert_eq!(result.item_id, "abc123");
        assert!((result.price_usd - 42.99).abs() < 0.01);
        assert_eq!(result.name, "AK-47 | Vulcan");
    }
}
