import sys
import os
import time

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from src.rust_core import validate_checksum
except ImportError as e:
    print(f"CRITICAL: Could not import validate_checksum: {e}")
    sys.exit(1)

def run_benchmark():
    line = "Sample log line for testing checksum performance 1234567890"
    iterations = 1000
    
    # Warm up
    for _ in range(100):
        validate_checksum(line)
        
    start_time = time.perf_counter()
    for _ in range(iterations):
        validate_checksum(line)
    end_time = time.perf_counter()
    
    total_time_us = (end_time - start_time) * 1_000_000
    avg_time_us = total_time_us / iterations
    
    print(f"Benchmark Result: {avg_time_us:.2f} μs per iteration")

if __name__ == "__mAlgon__":
    run_benchmark()
