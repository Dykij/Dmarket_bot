---
name: rust-performance
description: Rust performance optimization for the DMarket parser. Use when profiling, benchmarking, or optimizing the Rust extension module — criterion, flamegraph, allocation analysis, zero-cost abstractions.
---

# Rust Performance — DMarket Parser Optimization

## When to Use
- Profiling the Rust parser hot paths
- Optimizing maturin/PyO3 bridge latency
- Reducing memory allocations in parsing loops
- Benchmarking order book processing
- Investigating latency spikes

## Profiling Tools

### cargo-timings
```bash
cargo build --timings
# Opens target/cargo-timings.html with per-crate build times
```

### cargo-flamegraph
```bash
cargo install flamegraph
cargo flamegraph --bench my_benchmark
# Produces flamegraph.svg showing CPU time per function
```

### perf (Linux)
```bash
perf record -g --call-graph dwarf ./target/release/dmarket_parser_rs
perf report
```

## Optimization Checklist for PyO3 Bridge
- [ ] Minimize crossing Python↔Rust boundary (batch data transfer)
- [ ] Use `PyBytes` instead of `PyString` for raw data
- [ ] Avoid Python object creation in tight loops
- [ ] Use `#[pyclass]` with `#[pymethods]` for zero-copy access
- [ ] Profile GIL acquisition overhead

## Zero-Allocation Patterns
```rust
// BAD: allocates on every call
fn parse_price(s: &str) -> f64 {
    s.parse().unwrap()
}

// GOOD: reuse buffer
struct Parser {
    buf: String::with_capacity(1024),
}

impl Parser {
    fn parse_price(&mut self, s: &str) -> f64 {
        self.buf.clear();
        self.buf.push_str(s);
        self.buf.parse().unwrap()
    }
}
```

## Benchmarking with Criterion
```rust
use criterion::{criterion_group, criterion_main, Criterion};

fn bench_orderbook_parse(c: &mut Criterion) {
    let data = include_str!("../fixtures/orderbook.json");
    c.bench_function("parse_orderbook", |b| {
        b.iter(|| parse_orderbook(data))
    });
}

criterion_group!(benches, bench_orderbook_parse);
criterion_main!(benches);
```

## Build Optimization
- Use `mold` linker (2-3x faster linking)
- Enable `codegen-units = 1` for release builds
- Use `sccache` for shared compilation cache
- Split workspace if crate is large

## Key Files
- `rust_core/src/parser.rs` — main parsing logic
- `rust_core/src/lib.rs` — PyO3 bindings
- `rust_core/benches/` — criterion benchmarks
