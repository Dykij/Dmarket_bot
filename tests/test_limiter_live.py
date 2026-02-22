import asyncio
import time
from src.utils.brain_limiter import BrAlgonRateLimiter

async def test():
    l = BrAlgonRateLimiter(max_requests=2, window_seconds=2)
    print(f"Start: {time.time()}")
    await l.acquire()
    print("Req 1 (Instant)")
    await l.acquire()
    print("Req 2 (Instant)")
    start_wait = time.time()
    await l.acquire()
    print(f"Req 3 (Delayed by {time.time() - start_wait:.2f}s)")

if __name__ == "__main__":
    asyncio.run(test())
