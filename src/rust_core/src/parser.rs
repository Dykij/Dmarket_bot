use serde::Deserialize;
use serde_json::Value; // simd-json is API-compatible but requires unsafe/nightly for full potential sometimes. sticking to serde with zero-copy intent.

/// High-Performance Parser.
/// In a real HFT scenario, we would use `simd-json`'s `from_slice` to parse bytes directly
/// into structs allocated in the Bumpalo arena.
pub fn parse_order_book(json_data: &[u8]) -> Result<Value, serde_json::Error> {
    // Zero-copy deserialization where possible
    serde_json::from_slice(json_data)
}

#[derive(Deserialize, Debug)]
pub struct DMarketItemRaw<'a> {
    pub title: &'a str,
    pub price: DMarketPriceRaw,
}

#[derive(Deserialize, Debug)]
pub struct DMarketPriceRaw {
    #[serde(rename = "USD")]
    pub usd: f64,
}
