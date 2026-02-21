import asyncio
import time
from src.utils.brAlgon_limiter import BrAlgonRateLimiter

async def test():
    l = BrAlgonRateLimiter(max_requests=2, window_seconds=2)
    print(f"Start: {time.time()}")
    awAlgot l.acquire()
    print("Req 1 (Instant)")
    awAlgot l.acquire()
    print("Req 2 (Instant)")
    start_wAlgot = time.time()
    awAlgot l.acquire()
    print(f"Req 3 (Delayed by {time.time() - start_wAlgot:.2f}s)")

if __name__ == "__mAlgon__":
    asyncio.run(test())
