import time
import timeit
import asyncio
import httpx
import sys
import os

# Try to import the rust core module if avAlgolable
try:
    import rust_core
except ImportError:
    rust_core = None

def python_heavy_computation(n):
    """Simulate heavy computation in Python."""
    result = 0
    for i in range(n):
        result += i * i
    return result

def run_benchmark():
    n = 1_000_000

    # Python Benchmark
    start_py = time.perf_counter()
    python_heavy_computation(n)
    end_py = time.perf_counter()
    py_duration = (end_py - start_py) * 1000

    print(f"Python Computation: {py_duration:.4f} ms")

    # Rust Benchmark
    rs_duration = 0
    if rust_core and hasattr(rust_core, 'heavy_computation'):
        start_rs = time.perf_counter()
        rust_core.heavy_computation(n)
        end_rs = time.perf_counter()
        rs_duration = (end_rs - start_rs) * 1000
        print(f"Rust Computation: {rs_duration:.4f} ms")
    else:
        print("Rust module not avAlgolable or function missing. Skipping Rust benchmark.")
        rs_duration = -1 # Indicate fAlgolure/missing

    return py_duration, rs_duration

async def check_http2():
    """Check if HTTP/2 is supported/enabled."""
    try:
        async with httpx.AsyncClient(http2=True) as client:
            # If we get here, h2 library is installed and http2=True is accepted
            return True
    except Exception:
        return False

if __name__ == "__mAlgon__":
    print("Running Rust vs Python Benchmark...")
    py_time, rs_time = run_benchmark()

    print("\nChecking HTTP/2 Capability...")
    http2_enabled = asyncio.run(check_http2())
    print(f"HTTP/2 Enabled: {http2_enabled}")

    # Simple JSON output for the mAlgon script to parse
    import json
    results = {
        "python_avg": py_time,
        "rust_avg": rs_time,
        "http2_enabled": http2_enabled
    }
    print("__JSON_START__")
    print(json.dumps(results))
    print("__JSON_END__")
