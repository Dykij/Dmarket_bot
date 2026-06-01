import time
from nacl.signing import SigningKey
import binascii

def benchmark_nacl():
    # 32-byte secret key hex (64 chars)
    seed_hex = "0" * 64
    seed = bytes.fromhex(seed_hex)
    signing_key = SigningKey(seed)
    
    message = b"GET/api/v2/get-item{}1605619994"
    
    # Warmup
    for _ in range(100):
        signing_key.sign(message)
        
    start = time.perf_counter()
    iters = 1000
    for _ in range(iters):
        signing_key.sign(message)
    end = time.perf_counter()
    
    avg_ms = ((end - start) / iters) * 1000
    print(f"Average PyNaCl Signature Latency: {avg_ms:.4f} ms")

if __name__ == "__main__":
    benchmark_nacl()
