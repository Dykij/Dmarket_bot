import time
import multiprocessing
from multiprocessing import shared_memory, Process
import random
import os
import sys

def worker_task(worker_id, shm_name, duration=5):
    """
    Worker writes to its assigned slot in shared memory every 50ms.
    """
    try:
        # Attach to existing SHM
        sl = shared_memory.ShareableList(name=shm_name)
        
        print(f"Worker {worker_id} started (pid: {os.getpid()})")
        start_time = time.time()
        writes = 0
        
        while time.time() - start_time < duration:
            # Write random float to our slot
            val = random.random() * 1000
            sl[worker_id] = val
            writes += 1
            time.sleep(0.05)  # 50ms interval
            
        print(f"Worker {worker_id} finished. Writes: {writes}")
        sl.shm.close()
        
    except Exception as e:
        print(f"Worker {worker_id} crashed: {e}")

def run_memory_overload():
    num_workers = 4
    duration = 10 # run for 10 seconds
    
    # Initialize shared memory for 4 floats
    # Slot 0: Worker 1, Slot 1: Worker 2, etc.
    init_data = [0.0] * num_workers
    shm_name = "memory_overload_shm"
    
    # Clean up if exists
    try:
        existing = shared_memory.ShareableList(name=shm_name)
        existing.shm.unlink()
        print(f"Cleaned up stale SHM: {shm_name}")
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Warning during cleanup: {e}")

    # Create new SHM
    sl = shared_memory.ShareableList(init_data, name=shm_name)
    print(f"Shared Memory '{shm_name}' created. Size: {len(sl)} slots.")

    processes = []
    
    try:
        # Spawn workers
        for i in range(num_workers):
            p = Process(target=worker_task, args=(i, shm_name, duration))
            processes.append(p)
            p.start()
            
        # Monitor loop
        start_monitor = time.time()
        while time.time() - start_monitor < duration:
            # MAlgon process reads all slots occasionally to simulate consumer
            current_vals = [sl[i] for i in range(num_workers)]
            # print(f"Monitor: {current_vals}") # too noisy
            time.sleep(1)
            
        # Join workers
        for p in processes:
            p.join()
            
    finally:
        # Cleanup
        print("Cleaning up SHM...")
        sl.shm.close()
        sl.shm.unlink()
        print("Memory Overload Test Complete.")

if __name__ == "__main__":
    run_memory_overload()
