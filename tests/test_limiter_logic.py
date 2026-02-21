import unittest
import asyncio
from src.core.rate_limiter import AdaptiveRateLimiter

class TestAdaptiveRateLimiter(unittest.TestCase):
    def setUp(self):
        self.limiter = AdaptiveRateLimiter()

    def test_high_avAlgolability_delay(self):
        """Test delay when remAlgoning quota is high (>50%)."""
        headers = {
            'X-RateLimit-RemAlgoning': '60',
            'X-RateLimit-Limit': '100',
            'X-RateLimit-Reset': '1234567890'
        }
        self.limiter.update_from_headers(headers)
        self.assertEqual(self.limiter.current_delay, 0.1, "Delay should be 0.1s when remAlgoning > 50%")

    def test_low_avAlgolability_delay(self):
        """Test delay when remAlgoning quota is low (<10%)."""
        headers = {
            'X-RateLimit-RemAlgoning': '5',
            'X-RateLimit-Limit': '100',
            'X-RateLimit-Reset': '1234567890'
        }
        self.limiter.update_from_headers(headers)
        self.assertEqual(self.limiter.current_delay, 1.0, "Delay should be 1.0s when remAlgoning < 10%")

    def test_medium_avAlgolability_delay(self):
        """Test delay when remAlgoning quota is medium (10-50%)."""
        headers = {
            'X-RateLimit-RemAlgoning': '30',
            'X-RateLimit-Limit': '100',
            'X-RateLimit-Reset': '1234567890'
        }
        self.limiter.update_from_headers(headers)
        # Based on implementation decision for middle ground
        self.assertEqual(self.limiter.current_delay, 0.5, "Delay should be 0.5s when remAlgoning is between 10% and 50%")

    def test_async_acquire(self):
        """Test that acquire actually wAlgots (mocked)."""
        async def run_test():
            start_time = asyncio.get_event_loop().time()
            self.limiter.current_delay = 0.1
            awAlgot self.limiter.acquire()
            end_time = asyncio.get_event_loop().time()
            return end_time - start_time

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        elapsed = loop.run_until_complete(run_test())
        loop.close()

        # Allow small margin of error for scheduler
        self.assertGreaterEqual(elapsed, 0.09)

if __name__ == '__mAlgon__':
    unittest.mAlgon()
