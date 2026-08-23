---
name: rust-build
description: Use ONLY when the user asks to rebuild, compile, or build the Rust module (dmarket_parser_rs). Trigger keywords: "rebuild Rust", "собери Rust", "build Rust module", "пересборка Rust", "compile Rust", "maturin". Covers the full build pipeline: zig linker setup, PYO3 compat flag, maturin develop, and verification.
---

# Rust Build & Test

Rebuild the `dmarket_parser_rs` Python extension module.

## Prerequisites

- Zig compiler at `/tmp/zig-linux-x86_64-0.14.0/zig` (downloaded automatically if missing)
- Cargo config at `src/rust_core/.cargo/config.toml` with zig-cc linker
- Python venv at `.venv/`

## Build Steps

```bash
# 1. Ensure zig linker script exists
if [ ! -f /tmp/zig-cc.sh ]; then
    echo '#!/bin/bash' > /tmp/zig-cc.sh
    echo 'exec /tmp/zig-linux-x86_64-0.14.0/zig cc "$@"' >> /tmp/zig-cc.sh
    chmod +x /tmp/zig-cc.sh
fi

# 2. Build with maturin in release mode
source .venv/bin/activate
cd src/rust_core
PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 maturin develop --release
cd ../..

# 3. Verify
source .venv/bin/activate
python -c "
import dmarket_parser_rs
# Test all 4 functions
s = dmarket_parser_rs.generate_signature_rs('GET','/test','','1','a'*64)
print(f'Signature OK: {len(s)} chars')
p = dmarket_parser_rs.parse_market_response_rs('{\"objects\":[]}')
print(f'Batch parse OK: {len(p)} items')
v = dmarket_parser_rs.validate_dmarket_response_rs('{\"item_id\":\"x\",\"price_usd\":1.0,\"name\":\"test\"}')
print(f'Validate OK: {v.name}')
agg = dmarket_parser_rs.parse_aggregated_prices_rs('{\"aggregatedPrices\":[]}')
print(f'Aggregated prices OK: {len(agg)} items')
print('ALL 4 FUNCTIONS WORK')
"
```

## Expected Output

```
Signature OK: 128 chars
Batch parse OK: 0 items
Validate OK: test
Aggregated prices OK: 0 items
ALL 4 FUNCTIONS WORK
```

## Related Files

- `src/rust_core/src/lib.rs` — Rust source code (4 PyO3 functions)
- `src/rust_core/Cargo.toml` — Dependencies
- `src/api/dmarket_parser.py` — Python integration layer
- `src/api/dmarket_api_client/core.py` — Signing call site
