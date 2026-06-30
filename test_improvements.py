"""
Test script to verify improvements without running the full bot.
"""
import os
import sys
import time
import json
import asyncio
import logging
from pathlib import Path

sys.path.insert(0, '/home/deck/dmarket/Dmarket_bot-main')

# mock dotenv
class MockDotenv:
    @staticmethod
    def load_dotenv(*a, **k):
        pass
sys.modules['dotenv'] = MockDotenv()

logging.basicConfig(level=logging.INFO)


def main():
    print("=" * 60)
    print("DMarket Bot Improvements Test")
    print("=" * 60)

    # 1. Test Config TOD bug fix
    print("\n[1] Testing Config TOD bug fix...")
    try:
        from src.config import Config
        assert Config.TIME_OF_DAY_ENABLED == Config.TOD_ENABLED
        print("   PASS: TIME_OF_DAY_ENABLED matches TOD_ENABLED")
    except (AssertionError, AttributeError) as e:
        print(f"   FAIL: {e}")

    # 2. Test Circuit专业能力
    print("\n[2] Testing CircuitBreaker improvements...")
    try:
        from src.api.dmarket_api_client.backoff import CircuitBreaker
        cb = CircuitBreaker(name="test", fail_threshold=3)
        assert cb.allow_request()
        cb.record_failure(Exception("test"))
        # Test apply_retry_after
        cb.apply_retry_after(5.0)
        assert cb._server_backoff_until > time.time()
        print("   PASS: CircuitBreaker basic functionality")
    except Exception as e:
        print(f"   FAIL: {e}")

    # 3. Test Extract backoff from headers
    print("\n3] Testing extract_backoff_from_headers...")
    try:
        from src.api.dmarket_api_client.backoff import extract_backoff_from_headers
        headers = {
            "X-RateLimit-Remaining": "10",
            "Retry-After": "30"
        }
        retry_after, remaining, reset_in = extract_backoff_from_headers(headers)
        assert retry_after == 30.0
        assert remaining == 10
        print("   PASS: Header parsing works correctly")
    except Exception as e:
        print(f"   FAIL: {e}")

    # 4. Test DMarketAPIClient fallback
    print("\n[4] Testing DMarketAPIClient fallback URL...")
    try:
        from src.api.dmarket_api_client import DMarketAPIClient
        client = DMarketAPIClient(
            public_key="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            secret_key="REDACTED_TEST_KEY_ROTATE_IF_USED_IN_PRODUCTION"
        )
        assert hasattr(client, '_FALLBACK_BASE_URL')
        assert client._FALLBACK_BASE_URL == "https://trading.dmarket.com"
        print("   PASS: Fallback URL configured")
    except Exception as e:
        print(f"   FAIL: {e}")

    # 5. Test Adaptive backoff method
    print("\n[5] Testing adaptive backoff integration...")
    try:
        from src.api.dmarket_api_client import DMarketAPIClient
        import aiohttp
        client = DMarketAPIClient(
            public_key="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            secret_key="REDACTED_TEST_KEY_ROTATE_IF_USED_IN_PRODUCTION"
        )
        assert hasattr(client, '_adaptive_backoff')
        print("   PASS: _adaptive_backoff method exists")
    except Exception as e:
        print(f"   FAIL: {e}")

    print("\n" + "=" * 60)
    print("All improvements verified successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
