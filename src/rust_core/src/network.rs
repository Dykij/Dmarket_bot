use reqwest::{Client, StatusCode, Method};
use std::time::Duration;
use crate::rate_limiter::DMarketLimiter;
use std::sync::Arc;
use futures::future::join_all;
use std::collections::HashMap;
use ed25519_dalek::{Signer, SigningKey, Signature};
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::time::sleep;

use std::sync::atomic::{AtomicU64, Ordering};

/// Hybrid HFT Gateway for DMarket API v2.
/// Uses HTTP/2 Multiplexing for Market Data (Source of Truth).
/// Includes header optimization and robust error handling.
pub struct RustNetworkClient {
    http_client: Client,
    limiter: Arc<DMarketLimiter>, 
    api_url: String,
    public_key: String,
    secret_key: String,
    daily_spend_cents: AtomicU64,
}

impl RustNetworkClient {
    /// Initialize with Strict ToS Limits (e.g., 5 RPS).
    pub fn new(requests_per_second: u32, public_key: String, secret_key: String) -> Result<Self, String> {
        let http_client = Client::builder()
            .timeout(Duration::from_secs(10))
            .pool_idle_timeout(Duration::from_secs(90))
            // Core: Mimic browser behavior to avoid low-level blocks
            .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            // Core: Explicit GZIP/Brotli support
            .gzip(true)
            .brotli(true)
            .deflate(true)
            .build()
            .map_err(|e| format!("Failed to build HTTP client: {}", e))?;

        Ok(RustNetworkClient {
            http_client,
            limiter: Arc::new(DMarketLimiter::new(requests_per_second)), // Python should pass 2 here
            api_url: "https://api.dmarket.com".to_string(),
            public_key: public_key.trim().to_lowercase(),
            secret_key: secret_key.trim().to_lowercase(),
            daily_spend_cents: AtomicU64::new(0),
        })
    }

    /// Sign request using Ed25519 (DMarket specific: method + url_path + body + timestamp)
    fn sign_request(&self, method: &str, path: &str, body: &str, timestamp: u64) -> Result<String, String> {
        let message = format!("{}{}{}{}", method, path, body, timestamp);
        
        // Error Handling: Handle invalid hex string
        // PATCH: Trim secret key to remove invisible CRLF/whitespace
        let secret_bytes = hex::decode(self.secret_key.trim())
            .map_err(|e| format!("Invalid Secret Key Hex: {}", e))?;
            
        let seed = if secret_bytes.len() == 64 {
            &secret_bytes[0..32]
        } else if secret_bytes.len() == 32 {
            &secret_bytes[0..32]
        } else {
             return Err(format!("Secret Key length error: expected 32 or 64 bytes, got {}", secret_bytes.len()));
        };
        
        let signing_key = SigningKey::from_bytes(seed.try_into().map_err(|_| "Invalid Key Length")?);
        let signature: Signature = signing_key.sign(message.as_bytes());
        
        Ok(hex::encode(signature.to_bytes()))
    }

    /// Unified Request Handler with Retry Logic (Token Bucket + Backoff)
    async fn send_signed_request(&self, method: Method, path: &str, body: &str) -> Result<String, String> {
        let mut retries = 0;
        let max_retries = 3;

        loop {
            // Rate Limiter
            self.limiter.acquire().await;

            let timestamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
            let signature = self.sign_request(method.as_str(), path, body, timestamp)?;
            
            let url = format!("{}{}", self.api_url, path);
            let signature_val = format!("dmar ed25519 {}", signature);

            let mut req_builder = match method {
                Method::GET => self.http_client.get(&url),
                Method::POST => self.http_client.post(&url).body(body.to_string()),
                Method::PATCH => self.http_client.patch(&url).body(body.to_string()),
                Method::DELETE => self.http_client.delete(&url).body(body.to_string()),
                _ => return Err(format!("Unsupported method: {}", method)),
            };

            req_builder = req_builder
                .header("X-Api-Key", self.public_key.trim().to_lowercase())
                .header("X-Request-Sign", signature_val)
                .header("X-Sign-Date", timestamp.to_string())
                .header("Content-Type", "application/json")
                .header("Accept", "application/json");

            match req_builder.send().await {
                Ok(resp) => {
                    match resp.status() {
                        StatusCode::OK | StatusCode::NO_CONTENT | StatusCode::CREATED => {
                            return resp.text().await.map_err(|e| format!("Body Read Error: {}", e));
                        },
                        StatusCode::TOO_MANY_REQUESTS => {
                            if retries >= max_retries {
                                return Err("429: Max Retries Exceeded".to_string());
                            }
                            eprintln!("WARNING: 429 Rate Limit. Backing off for 2s...");
                            sleep(Duration::from_secs(2)).await;
                            retries += 1;
                            continue;
                        },
                        status => {
                            let err_body = resp.text().await.unwrap_or_default();
                            return Err(format!("API Error {}: {}", status, err_body));
                        }
                    }
                },
                Err(e) => return Err(format!("Network Error: {}", e)),
            }
        }
    }
    
    /// Get User Balance (Authenticated)
    pub async fn fetch_user_balance(&self) -> Result<String, String> {
        self.send_signed_request(Method::GET, "/account/v1/balance", "").await
    }

    /// Buy Offer (PATCH /exchange/v1/offers-buy)
    pub async fn buy_offer(&self, offer_id: &str, price_cents: u64, _asset_id: &str) -> Result<String, String> {
        // SAFETY CHECKS (Hard Limits)
        const MAX_ITEM_PRICE_CENTS: u64 = 500; // $5.00
        const MAX_DAILY_SPEND_CENTS: u64 = 1500; // $15.00

        if price_cents > MAX_ITEM_PRICE_CENTS {
            return Err(format!("SAFETY: Item Price {} cents > Limit {} cents", price_cents, MAX_ITEM_PRICE_CENTS));
        }

        let current_spend = self.daily_spend_cents.load(Ordering::Relaxed);
        if current_spend + price_cents > MAX_DAILY_SPEND_CENTS {
            return Err(format!("SAFETY: Daily Spend Limit Exceeded. Current: {}, Attempt: {}, Limit: {}", current_spend, price_cents, MAX_DAILY_SPEND_CENTS));
        }

        // Body: {"offers": [{"offerId": "...", "price": {"amount": "...", "currency": "USD"}, "type": "dmarket"}]}
        let body = format!(
            r#"{{"offers":[{{"offerId":"{}","price":{{"amount":"{}","currency":"USD"}},"type":"dmarket"}}]}}"#,
            offer_id, price_cents
        );
        
        let result = self.send_signed_request(Method::PATCH, "/exchange/v1/offers-buy", &body).await;
        
        if result.is_ok() {
            // Optimistically update spend (or wait for confirmation parsing? Rust return string is raw body)
            // For safety, we update on HTTP 200 OK (which send_signed_request guarantees for Ok result)
            self.daily_spend_cents.fetch_add(price_cents, Ordering::SeqCst);
        }
        
        result
    }

    /// Create Sell Offer (POST /marketplace-api/v2/offers:batchCreate)
    pub async fn create_sell_offer(&self, asset_id: &str, price_cents: u64) -> Result<String, String> {
        // Body: {"requests": [{"assetId": "...", "priceCents": ...}]}
        let body = format!(
            r#"{{"requests":[{{"assetId":"{}","priceCents":{}}}]}}"#,
            asset_id, price_cents
        );
        self.send_signed_request(Method::POST, "/marketplace-api/v2/offers:batchCreate", &body).await
    }

    /// Fetch Market Items (REST v2)
    /// This is the "Hot Path".
    pub async fn fetch_market_items(&self, game_id: &str, title: &str) -> Result<String, String> {
        // We use the simpler method here to avoid overhead of signing if not needed, 
        // BUT for consistency and rate limits we should probably use the same pipeline if possible.
        // However, market items endpoint is public usually? But we sign it to get higher limits.
        // Let's stick to explicit implementation for bulk.
        
        self.limiter.acquire().await;

        let url = format!("{}/exchange/v1/market/items?gameId={}&title={}&limit=10&sort=price&order=asc&currency=USD", self.api_url, game_id, title);

        let response = self.http_client.get(&url)
            .send()
            .await
            .map_err(|e| format!("Network Error: {}", e))?;

        match response.status() {
            StatusCode::OK => {
                let body = response.text().await.map_err(|e| format!("Body Error: {}", e))?;
                Ok(body) 
            },
            StatusCode::TOO_MANY_REQUESTS => {
                Err("429: Rate Limit Exceeded. Backing off.".to_string())
            },
            status => {
                Err(format!("API Error: {}", status))
            }
        }
    }

    /// Multi-threaded fetch for multiple targets.
    /// Uses join_all to execute concurrently, but respects the SHARED global rate limiter.
    /// Returns a map of "GameID:Title" -> Result<JSON, Error>
    pub async fn fetch_bulk(&self, targets: Vec<(String, String)>) -> HashMap<String, Result<String, String>> {
        let mut tasks = Vec::new();
        // Clone Arcs to move into threads (cheap)
        let client_ref = &self.http_client;
        let limiter_ref = &self.limiter;
        let api_url_ref = &self.api_url;
        
        for (game_id, title) in targets {
            let client = client_ref.clone();
            let limiter = limiter_ref.clone();
            let url_base = api_url_ref.clone();
            
            // Spawn a future for each request
            tasks.push(tokio::spawn(async move {
                // Rate Limit Check (Global across all threads)
                limiter.acquire().await;
                
                let url = format!("{}/exchange/v1/market/items?gameId={}&title={}&limit=10&sort=price&order=asc&currency=USD", url_base, game_id, title);
                
                match client.get(&url).send().await {
                    Ok(resp) => {
                        match resp.status() {
                            StatusCode::OK => {
                                match resp.text().await {
                                    Ok(text) => (game_id, title, Ok(text)),
                                    Err(e) => (game_id, title, Err(e.to_string())),
                                }
                            },
                            StatusCode::TOO_MANY_REQUESTS => (game_id, title, Err("429".to_string())),
                            s => (game_id, title, Err(format!("Status: {}", s))),
                        }
                    },
                    Err(e) => (game_id, title, Err(e.to_string())),
                }
            }));
        }

        let results = join_all(tasks).await;
        
        let mut map = HashMap::new();
        for res in results {
            match res {
                Ok((g, t, r)) => {
                    let key = format!("{}:{}", g, t);
                    map.insert(key, r);
                },
                Err(_) => {}, // Task panicked? rare.
            }
        }
        map
    }
}
