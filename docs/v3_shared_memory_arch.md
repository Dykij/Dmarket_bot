# v3.0 Architecture Upgrade: Shared Memory & Zero-Copy

## 1. Overview
This document outlines the upgrade path to v3.0, focusing on eliminating Redis network overhead for local inter-process communication (IPC) and improving system stability via a hardware-level watchdog.

## 2. Shared Memory Implementation
We will replace the Redis-based status flags with `multiprocessing.shared_memory` to achieve sub-microsecond latency.

### Data Structure (`ShareableList` or `Struct`)
We will use a fixed-size C-struct via `multiprocessing.shared_memory.SharedMemory` for maximum performance, or `ShareableList` for simplicity.

**Proposed Struct Layout (bytes):**
```python
import struct

# Format: 'd' (double, timestamp), 'i' (int, status_code), 'i' (int, pid)
# Size: 8 + 4 + 4 = 16 bytes per worker
```

| Offset | Field | Type | Description |
| :--- | :--- | :--- | :--- |
| 0 | `last_heartbeat` | `double` | Timestamp of last worker activity |
| 8 | `status_code` | `int` | 0=OK, 1=WARN, 2=ERROR |
| 12 | `pid` | `int` | System Process ID |

### Heartbeat Mechanism
*   **Workers:** Write `time.time()` to their dedicated slot in Shared Memory every loop (or every N loops).
*   **Master:** Reads the entire memory block directly. No syscalls, no serialization.

## 3. Zero-Copy Serialization
Replace `json` and `pickle` with `orjson` for all data passing that still requires serialization (e.g., complex objects sent over pipes/queues).

*   **Benchmark Goal:** < 10µs serialization time for standard trade payloads.
*   **Integration:** Patch `redis-py` or wrapper classes to use `orjson.dumps` and `orjson.loads`.

## 4. Watchdog & Recovery
The Master process will run a high-frequency monitoring loop (separate thread or asyncio task).

*   **Check:** Iterate over Shared Memory struct every 100ms.
*   **Condition:** If `current_time - worker.last_heartbeat > 10.0`:
    1.  **Kill:** `os.kill(worker.pid, signal.SIGKILL)`
    2.  **Restart:** Respawn the worker process.
    3.  **Alert:** Send critical notification to Telegram.

## 5. Event Loop Optimization
*   **Redis Polling:** Move blocking Redis `blpop` or similar calls to `asyncio.create_task` to prevent blocking the main heartbeat loop.
*   **Signal Handling:** Use `loop.add_signal_handler` for graceful shutdowns.

## 6. Migration Steps
1.  **Prototype:** Create a standalone `shared_mem_test.py` to validate `SharedMemory` linking between spawn/fork processes.
2.  **Wrapper:** Create `SharedState` class to abstract memory management.
3.  **Integration:** Refactor `Worker` base class to use `SharedState`.
4.  **Watchdog:** Implement the monitor in `Master`.
