use governor::{Quota, RateLimiter};
use governor::clock::DefaultClock;
use governor::state::{InMemoryState, NotKeyed};
use std::num::NonZeroU32;
use std::time::Duration;
use tokio::time::sleep;

/// The Iron Shield against 429 Bans.
/// Uses Token Bucket algorithm to mathematically guarantee compliance.
pub struct DMarketLimiter {
    limiter: RateLimiter<NotKeyed, InMemoryState, DefaultClock>,
}

impl DMarketLimiter {
    pub fn new(requests_per_second: u32) -> Self {
        let quota = Quota::per_second(NonZeroU32::new(requests_per_second).unwrap())
            .allow_burst(NonZeroU32::new(1).unwrap()); // Strict mode: no bursts > 1
        
        DMarketLimiter {
            limiter: RateLimiter::direct(quota),
        }
    }

    /// Asynchronously waits until a token is available.
    /// If the bucket is empty, the thread sleeps.
    pub async fn acquire(&self) {
        self.limiter.until_ready().await;
    }
}
