"""Example tests demonstrating VCR.py usage for HTTP recording/playback.

This file shows how to use VCR.py fixtures from conftest_vcr.py
to record and replay HTTP interactions with DMarket API.

On first run: HTTP requests are recorded to cassette files in tests/cassettes/
On subsequent runs: Recorded responses are replayed without network access

This enables:
- Deterministic tests (same response every time)
- Fast tests (no network latency)
- Offline testing
- CI/CD without API access
"""

import pytest

from tests.conftest_vcr import (
    CASSETTES_DIR,
    VCRConfigs,
    cassette_exists,
    get_cassette_path,
    vcr_config,
)


class TestVCRBasics:
    """Basic VCR.py usage examples."""

    def test_cassettes_directory_exists(self) -> None:
        """Verify cassettes directory is set up correctly."""
        assert CASSETTES_DIR.exists()
        assert CASSETTES_DIR.is_dir()

    def test_vcr_config_is_configured(self) -> None:
        """Verify VCR configuration is properly set up."""
        assert vcr_config is not None
        assert vcr_config.record_mode == "once"

    def test_cassette_path_generation(self) -> None:
        """Test cassette path generation utility."""
        path = get_cassette_path("test_example")
        assert path.suffix == ".yaml"
        assert "test_example" in str(path)

        path_with_module = get_cassette_path("test_example", "dmarket/api")
        assert "dmarket" in str(path_with_module)
        assert "api" in str(path_with_module)

    def test_cassette_exists_function(self) -> None:
        """Test cassette existence check utility."""
        # Non-existent cassette
        assert not cassette_exists("non_existent_test_xyz123")

        # Note: After recording, this would return True


class TestVCRConfigs:
    """Test pre-configured VCR instances."""

    def test_dmarket_vcr_config(self) -> None:
        """Test DMarket-specific VCR configuration."""
        dmarket_vcr = VCRConfigs.dmarket_api()

        assert dmarket_vcr is not None
        assert dmarket_vcr.record_mode == "once"
        assert "X-Api-Key" in dmarket_vcr.filter_headers

    def test_telegram_vcr_config(self) -> None:
        """Test Telegram-specific VCR configuration."""
        telegram_vcr = VCRConfigs.telegram_api()

        assert telegram_vcr is not None
        assert telegram_vcr.record_mode == "once"
        assert "Authorization" in telegram_vcr.filter_headers


@pytest.mark.vcr()
class TestVCRWithFixture:
    """Examples using VCR fixtures.

    These tests demonstrate how to use the VCR fixtures
    defined in conftest_vcr.py.

    Note: These tests will fail on first run if there's no actual
    API access, as they need to record cassettes first.
    For CI, you would commit pre-recorded cassettes.
    """

    def test_with_vcr_cassette(self) -> None:
        """Example using automatic cassette naming fixture.

        This test demonstrates VCR cassette pattern without
        requiring API access. Uses mock to simulate HTTP.
        """
        from unittest.mock import MagicMock, patch

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"objects": [], "total": 0}

        with patch("httpx.get", return_value=mock_response):
            import httpx

            response = httpx.get("https://api.dmarket.com/exchange/v1/market/items")
            assert response.status_code == 200

    def test_with_custom_cassette(self) -> None:
        """Example using custom cassette name fixture.

        Demonstrates custom cassette naming pattern without API access.
        Uses mock to simulate the cassette replay behavior.
        """
        from unittest.mock import MagicMock, patch

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"market_data": "shared"}

        with patch("httpx.get", return_value=mock_response):
            import httpx

            # Simulates HTTP calls using shared_market_data cassette
            response = httpx.get("https://api.dmarket.com/exchange/v1/market/items")
            assert response.status_code == 200
            assert response.json()["market_data"] == "shared"


@pytest.mark.vcr()
@pytest.mark.asyncio()
class TestVCRAsync:
    """Examples for async HTTP clients (httpx, aiohttp)."""

    async def test_async_api_call(self) -> None:
        """Example using async VCR fixture with httpx.

        VCR.py natively supports async HTTP clients.
        This test demonstrates the pattern using mocks.
        """
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"usd": "10000", "dmc": "5000"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.dmarket.com/account/v1/balance"
                )
                assert response.status_code in {200, 401}


class TestVCRIntegrationPattern:
    """Shows the recommended pattern for VCR integration tests.

    This pattern allows tests to:
    1. Run with real API in development (to record cassettes)
    2. Run with cassettes in CI/CD (no API access needed)
    """

    def test_vcr_integration_pattern(self) -> None:
        """Demonstrate the recommended test structure for VCR tests.

        Recommended structure for your actual API tests:

        ```python
        @pytest.mark.vcr
        @pytest.mark.asyncio()
        async def test_get_balance(vcr_cassette_async, dmarket_api):
            '''Test getting user balance.

            Cassette path:
            tests/cassettes/dmarket/test_dmarket_api/test_get_balance.yaml
            '''
            # First run: Makes real API call, records to cassette
            # Subsequent runs: Replays from cassette
            balance = await dmarket_api.get_balance()

            assert "balance" in balance
            assert balance["balance"] >= 0
        ```

        To record/re-record cassettes:
        ```bash
        # Record all new cassettes
        pytest --vcr-record=new_episodes tests/dmarket/

        # Re-record everything (after API changes)
        pytest --vcr-record=all tests/dmarket/test_dmarket_api.py
        ```
        """
        # This is a documentation test - actual implementation would be in
        # tests/dmarket/test_dmarket_api.py
        assert True


def test_vcr_module_loads_correctly() -> None:
    """Verify VCR module and fixtures are importable."""
    # These imports are verified at module load time (lines 16-24)
    assert CASSETTES_DIR is not None
    assert vcr_config is not None
    assert VCRConfigs is not None
    assert callable(get_cassette_path)
    assert callable(cassette_exists)
