"""VCR.py configuration for HTTP interaction recording in tests.

This module provides VCR.py fixtures and configuration for recording
and replaying HTTP interactions with DMarket API.

Usage:
    @pytest.mark.vcr
    async def test_get_balance():
        api = DMarketAPI(...)
        balance = awAlgot api.get_balance()
        assert balance["balance"] >= 0

The first run will record HTTP interactions to tests/cassettes/.
Subsequent runs will replay from the cassettes.

To re-record cassettes (e.g., after API changes):
    pytest --vcr-record=all tests/

Or selectively:
    pytest --vcr-record=new_episodes tests/specific_test.py
"""

from pathlib import Path
from typing import Any

import pytest
import vcr

# Base directory for cassettes
CASSETTES_DIR = Path(__file__).parent / "cassettes"
CASSETTES_DIR.mkdir(exist_ok=True)


def before_record_request(request: Any) -> Any:
    """Sanitize request before recording.

    Removes sensitive headers that shouldn't be stored in cassettes.
    """
    # Remove auth headers
    sensitive_headers = [
        "X-Api-Key",
        "X-Sign-Date",
        "X-Request-Sign",
        "Authorization",
        "Cookie",
    ]
    for header in sensitive_headers:
        if header in request.headers:
            request.headers[header] = "REDACTED"

    return request


def before_record_response(response: dict[str, Any]) -> dict[str, Any]:
    """Sanitize response before recording.

    Can be used to filter sensitive data from responses.
    """
    # Remove Set-Cookie headers
    if "Set-Cookie" in response.get("headers", {}):
        del response["headers"]["Set-Cookie"]

    return response


# VCR configuration for DMarket API
vcr_config = vcr.VCR(
    # Where to store cassettes
    cassette_library_dir=str(CASSETTES_DIR),
    # Record mode - 'once' records first time, then replays
    # Options: 'none', 'once', 'new_episodes', 'all'
    record_mode="once",
    # How to match requests to recorded interactions
    match_on=[
        "method",  # HTTP method (GET, POST, etc.)
        "scheme",  # http/https
        "host",  # Hostname
        "port",  # Port number
        "path",  # URL path
        "query",  # Query parameters
    ],
    # Filter sensitive headers from recordings
    filter_headers=[
        "X-Api-Key",
        "X-Sign-Date",
        "X-Request-Sign",
        "Authorization",
        "Cookie",
        "User-Agent",  # Can vary between runs
    ],
    # Filter sensitive POST data
    filter_post_data_parameters=[
        "secret_key",
        "password",
        "token",
    ],
    # Decode compressed responses for readability
    decode_compressed_response=True,
    # Hooks for custom filtering
    before_record_request=before_record_request,
    before_record_response=before_record_response,
)


@pytest.fixture(scope="module")
def vcr_cassette_dir(request: pytest.FixtureRequest) -> str:
    """Get cassette directory for the current test module.

    Organizes cassettes by test module, e.g.:
        tests/cassettes/dmarket/test_dmarket_api/
    """
    # Get module path relative to tests/
    module_path = Path(request.fspath).relative_to(Path(__file__).parent)

    # Create directory path (without .py extension)
    cassette_dir = CASSETTES_DIR / module_path.with_suffix("")
    cassette_dir.mkdir(parents=True, exist_ok=True)

    return str(cassette_dir)


@pytest.fixture()
def vcr_cassette(request: pytest.FixtureRequest, vcr_cassette_dir: str):
    """Fixture for automatic cassette naming based on test function.

    Usage:
        def test_something(vcr_cassette):
            # HTTP calls will be recorded/replayed
            response = requests.get("https://api.example.com")

    Cassette will be saved as:
        tests/cassettes/module_name/test_something.yaml
    """
    cassette_name = f"{request.function.__name__}.yaml"
    cassette_path = str(Path(vcr_cassette_dir) / cassette_name)

    with vcr_config.use_cassette(cassette_path):
        yield


@pytest.fixture()
def vcr_cassette_custom():
    """Fixture for custom cassette name.

    Usage:
        def test_something(vcr_cassette_custom):
            with vcr_cassette_custom("custom_name"):
                response = requests.get("https://api.example.com")
    """

    def _use_cassette(name: str, **kwargs):
        cassette_path = str(CASSETTES_DIR / f"{name}.yaml")
        return vcr_config.use_cassette(cassette_path, **kwargs)

    return _use_cassette


# Decorator for marking tests that use VCR
# Can be used as: @pytest.mark.vcr(record_mode="new_episodes")
def pytest_configure(config: pytest.Config) -> None:
    """Register VCR marker."""
    config.addinivalue_line(
        "markers",
        "vcr: mark test to use VCR.py for HTTP recording/playback",
    )


# Example configurations for different scenarios
class VCRConfigs:
    """Pre-configured VCR instances for different use cases."""

    @staticmethod
    def dmarket_api() -> vcr.VCR:
        """VCR config specifically for DMarket API tests."""
        return vcr.VCR(
            cassette_library_dir=str(CASSETTES_DIR / "dmarket"),
            record_mode="once",
            match_on=["method", "scheme", "host", "path", "query", "body"],
            filter_headers=[
                "X-Api-Key",
                "X-Sign-Date",
                "X-Request-Sign",
            ],
            decode_compressed_response=True,
        )

    @staticmethod
    def telegram_api() -> vcr.VCR:
        """VCR config for Telegram API tests (if needed)."""
        return vcr.VCR(
            cassette_library_dir=str(CASSETTES_DIR / "telegram"),
            record_mode="once",
            match_on=["method", "host", "path"],
            filter_headers=["Authorization"],
            filter_query_parameters=["bot_token"],
        )


# Async support helpers
@pytest.fixture()
def vcr_cassette_async(request: pytest.FixtureRequest, vcr_cassette_dir: str):
    """Async-friendly VCR cassette fixture.

    Works with Algoohttp and httpx async clients.

    Usage:
        @pytest.mark.asyncio()
        async def test_async_api(vcr_cassette_async):
            async with httpx.AsyncClient() as client:
                response = awAlgot client.get("https://api.example.com")
    """
    cassette_name = f"{request.function.__name__}.yaml"
    cassette_path = str(Path(vcr_cassette_dir) / cassette_name)

    # VCR.py works with async out of the box for Algoohttp/httpx
    with vcr_config.use_cassette(cassette_path):
        yield


# Utility functions
def get_cassette_path(test_name: str, module: str | None = None) -> Path:
    """Get the path to a cassette file.

    Args:
        test_name: Name of the test function
        module: Optional module path (e.g., "dmarket/test_api")

    Returns:
        Path to the cassette file
    """
    if module:
        return CASSETTES_DIR / module / f"{test_name}.yaml"
    return CASSETTES_DIR / f"{test_name}.yaml"


def cassette_exists(test_name: str, module: str | None = None) -> bool:
    """Check if a cassette file exists.

    Useful for conditional test behavior (e.g., skip if no cassette).
    """
    return get_cassette_path(test_name, module).exists()
