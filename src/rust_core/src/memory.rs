use bumpalo::Bump;
use serde::{Deserialize, Deserializer};

/// Zero-Allocation Memory Arena for Order Book Processing.
/// Instead of allocating new memory for each order, we use a pre-allocated arena.
/// This eliminates malloc/free overhead in the hot loop.
pub struct OrderBookArena {
    pub bump: Bump,
}

impl OrderBookArena {
    pub fn new() -> Self {
        OrderBookArena {
            bump: Bump::with_capacity(1024 * 1024), // Pre-allocate 1MB
        }
    }

    pub fn reset(&mut self) {
        self.bump.reset();
    }
}

/// Zero-Copy Order Structure (Lifetime bound to Arena)
#[derive(Debug)]
pub struct Order<'a> {
    pub id: &'a str,
    pub price: f64,
    pub amount: u32,
}

impl<'a> Order<'a> {
    pub fn new_in(arena: &'a Bump, id: &str, price: f64, amount: u32) -> &'a mut Self {
        arena.alloc(Order {
            id: arena.alloc_str(id),
            price,
            amount,
        })
    }
}
