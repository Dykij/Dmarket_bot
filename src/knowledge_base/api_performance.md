# API Performance Best Practices

## JSON Parsing
*   **simdjson:** Use for critical hot paths. It is significantly faster than standard `json`.
*   **orjson:** Good alternative for Python speedups.

## Buffer Management
*   **Reuse Buffers:** Avoid allocating new buffers for every message. Reusing memory reduces GC overhead and latency.

## Recommendations
1.  Prioritize Rust-based parsers in the hot loop.
2.  Minimize object creation in WebSocket handlers.
