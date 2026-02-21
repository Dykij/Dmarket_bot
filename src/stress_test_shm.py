
import time
import multiprocessing
from multiprocessing import shared_memory
import struct

def stress_test_shm():
    # 4 floats (CS2, Rust, TF2, Dota) = 4 * 8 bytes (double) = 32 bytes
    # actually ShareableList handles types, but for raw speed usually struct is better?
    # The Config asks for ShareableList explicitly: "Use multiprocessing.shared_memory.ShareableList"
    
    data = [0.0, 0.0, 0.0, 0.0]
    shm_name = "stress_test_shm"
    
    try:
        sl = shared_memory.ShareableList(data, name=shm_name)
    except FileExistsError:
        # Cleanup if exists from previous run
        existing = shared_memory.ShareableList(name=shm_name)
        existing.shm.unlink()
        sl = shared_memory.ShareableList(data, name=shm_name)

    iterations = 100000
    start_write = time.perf_counter()
    for i in range(iterations):
        sl[0] = float(i)
        sl[1] = float(i)
        sl[2] = float(i)
        sl[3] = float(i)
    end_write = time.perf_counter()
    
    start_read = time.perf_counter()
    for i in range(iterations):
        _ = sl[0]
        _ = sl[1]
        _ = sl[2]
        _ = sl[3]
    end_read = time.perf_counter()
    
    avg_write = ((end_write - start_write) / iterations) * 1000 # ms
    avg_read = ((end_read - start_read) / iterations) * 1000 # ms
    
    print(f"Write Latency: {avg_write:.5f} ms")
    print(f"Read Latency: {avg_read:.5f} ms")
    
    sl.shm.close()
    sl.shm.unlink()

if __name__ == "__mAlgon__":
    stress_test_shm()
