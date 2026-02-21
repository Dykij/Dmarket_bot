use reqwest::{Client, StatusCode};
use std::time::Duration;
use crate::rate_limiter::DMarketLimiter;
use std::sync::Arc;
use futures::future::join_all;
use std::collections::HashMap;
use ed25519_dalek::{Signer, SigningKey, Signature};
use std::time::{SystemTime, UNIX_EPOCH};

/// Hybrid HFT Gateway for DMarket API v2.
/// Uses HTTP/2 Multiplexing for Market Data (Source of Truth).
/// Includes header optimization and robust error handling.
pub struct RustNetworkClient {
    http_client: Client,
    limiter: Arc<DMarketLimiter>, 
    api_url: String,
    public_key: String,
    secret_key: String,
}

impl RustNetworkClient {
    /// Initialize with Strict ToS Limits (e.g., 5 RPS).
    pub fn new(requests_per_second: u32, public_key: String, secret_key: String) -> Result<Self, String> {
        let http_client = Client::builder()
            .timeout(Duration::from_secs(5))
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
            limiter: Arc::new(DMarketLimiter::new(requests_per_second)),
            api_url: "https://api.dmarket.com".to_string(),
            public_key,
            secret_key,
        })
    }

    /// Sign request using Ed25519 (DMarket specific: method + url_path + body + timestamp)
    fn sign_request(&self, method: &str, path: &str, body: &str, timestamp: u64) -> Result<String, String> {
        let message = format!("{}{}{}{}", method, path, body, timestamp);
        
        // Error Handling: Handle invalid hex string
        let secret_bytes = hex::decode(&self.secret_key)
            .map_err(|e| format!("Invalid Secret Key Hex: {}", e))?;
            
        if secret_bytes.len() != 64 {
             return Err("Secret Key must be 64 bytes (hex decoded)".to_string());
        }
        
        let seed = &secret_bytes[0..32];
        let signing_key = SigningKey::from_bytes(seed.try_into().map_err(|_| "Invalid Key Length")?);
        let signature: Signature = signing_key.sign(message.as_bytes());
        
        Ok(hex::encode(signature.to_bytes()))
    }
    
    /// Get User Balance (Authenticated)
    pub async fn fetch_user_balance(&self) -> Result<String, String> {
        self.limiter.acquire().await;
        
        let path = "/account/v1/balance";
        let method = "GET";
        let body = "";
        let timestamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
        
        let signature = self.sign_request(method, path, body, timestamp)?;
        
        let url = format!("{}{}", self.api_url, path);
        
        let response = self.http_client.get(&url)
            .header("X-Api-Key", &self.public_key)
            .header("X-Sign", signature)
            .header("X-Timestamp", timestamp.to_string())
            .header("Content-Type", "application/json")
            .send()
            .await
            .map_err(|e| format!("Network Error: {}", e))?;

        match response.status() {
            StatusCode::OK => {
                let text = response.text().await.map_err(|e| format!("Body Read Error: {}", e))?;
                Ok(text)
            },
            status => {
                // QA: Log the error body for debugging (e.g., "Invalid Signature")
                let err_body = response.text().await.unwrap_or_default();
                Err(format!("API Error {}: {}", status, err_body))
            }
        }
    }

    /// Fetch Market Items (REST v2)
    /// This is the "Hot Path".
    pub async fn fetch_market_items(&self, game_id: &str, title: &str) -> Result<String, String> {
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
