import unittest
import asyncio
from src.core.rate_limiter import AdaptiveRateLimiter

class TestAdaptiveRateLimiter(unittest.TestCase):
    def setUp(self):
        self.limiter = AdaptiveRateLimiter()

    def test_high_availability_delay(self):
        """Test delay when remaining quota is high (>50%)."""
        headers = {
            'X-RateLimit-Remaining': '60',
            'X-RateLimit-Limit': '100',
            'X-RateLimit-Reset': '1234567890'
        }
        self.limiter.update_from_headers(headers)
        self.assertEqual(self.limiter.current_delay, 0.1, "Delay should be 0.1s when remaining > 50%")

    def test_low_availability_delay(self):
        """Test delay when remaining quota is low (<10%)."""
        headers = {
            'X-RateLimit-Remaining': '5',
            'X-RateLimit-Limit': '100',
            'X-RateLimit-Reset': '1234567890'
        }
        self.limiter.update_from_headers(headers)
        self.assertEqual(self.limiter.current_delay, 1.0, "Delay should be 1.0s when remaining < 10%")

    def test_medium_availability_delay(self):
        """Test delay when remaining quota is medium (10-50%)."""
        headers = {
            'X-RateLimit-Remaining': '30',
            'X-RateLimit-Limit': '100',
            'X-RateLimit-Reset': '1234567890'
        }
        self.limiter.update_from_headers(headers)
        # Based on implementation decision for middle ground
        self.assertEqual(self.limiter.current_delay, 0.5, "Delay should be 0.5s when remaining is between 10% and 50%")

    def test_async_acquire(self):
        """Test that acquire actually waits (mocked)."""
        async def run_test():
            start_time = asyncio.get_event_loop().time()
            self.limiter.current_delay = 0.1
            await self.limiter.acquire()
            end_time = asyncio.get_event_loop().time()
            return end_time - start_time

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        elapsed = loop.run_until_complete(run_test())
        loop.close()

        # Allow small margin of error for scheduler
        self.assertGreaterEqual(elapsed, 0.09)

if __name__ == '__main__':
    unittest.main()
