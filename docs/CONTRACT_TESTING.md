# Contract Testing Guide

**Version**: 1.0.0
**Last updated: January 2026
**Related**: [API Reference](api_reference.md), [Testing Guide](testing_guide.md)

---

## Overview

This project implements **Consumer-Driven Contract Testing** using [Pact](https://pact.io/) to ensure the DMarket Telegram Bot correctly interacts with the DMarket API.

### What is Contract Testing?

Contract testing verifies that two systems (a consumer and a provider) can communicate with each other. Unlike end-to-end tests, contract tests:

- ✅ Are fast and reliable (no network calls)
- ✅ Can be run independently
- ✅ Provide clear error messages when contracts break
- ✅ Document API expectations automatically

### Our Setup

```
┌─────────────────────────┐       ┌─────────────────────────┐
│  DMarket Telegram Bot   │       │      DMarket API        │
│       (Consumer)        │  ←→   │       (Provider)        │
└─────────────────────────┘       └─────────────────────────┘
           │                                   │
           │         Contract (Pact)           │
           └───────────────────────────────────┘
```

- **Consumer**: DMarket Telegram Bot (our application)
- **Provider**: DMarket API (external service)
- **Contract**: JSON document describing expected interactions

---

## Quick Start

### Installation

```bash
# Install pact-python
pip install pact-python>=2.2.0

# Or use pip-compile (recommended)
pip-compile requirements.in
pip install -r requirements.txt
```

### Running Contract Tests

```bash
# Run all contract tests
pytest tests/contracts/ -v

# Run specific contract test file
pytest tests/contracts/test_account_contracts.py -v

# Run with verbose Pact output
pytest tests/contracts/ -v --log-cli-level=DEBUG

# Skip if pact not installed
pytest tests/contracts/ -v --ignore-glob="*pact*"
```

---

## Project Structure

```
tests/contracts/
├── __init__.py                    # Package docstring
├── conftest.py                    # Pact configuration and fixtures
├── test_account_contracts.py      # Account endpoint contracts
├── test_market_contracts.py       # Marketplace endpoint contracts
├── test_targets_contracts.py      # User targets (buy orders) contracts
├── test_inventory_contracts.py    # Inventory & offers contracts
└── pacts/                         # Generated contract files (JSON)
    └── DMarketTelegramBot-DMarketAPI.json
```

---

## Key Components

### 1. PactMatchers

Custom helper class for flexible response matching:

```python
from tests.contracts.conftest import PactMatchers

# Match any string with same structure
PactMatchers.like("example")  # Matches any string

# Match array with minimum items
PactMatchers.each_like({"id": "123"}, minimum=1)

# Match with regex pattern
PactMatchers.regex(r"^\d+$", "12345")

# Match specific types
PactMatchers.integer(100)
PactMatchers.decimal(99.99)
PactMatchers.uuid("550e8400-e29b-41d4-a716-446655440000")
PactMatchers.iso8601_datetime("2025-01-01T00:00:00Z")

# Match contAlgoning substring
PactMatchers.include("expected")
```

### 2. DMarketContracts

Pre-defined expected responses for DMarket API endpoints:

```python
from tests.contracts.conftest import DMarketContracts

# Get expected balance response structure
balance = DMarketContracts.balance_response()

# Get expected market items response
items = DMarketContracts.market_items_response()

# Get expected user targets response
targets = DMarketContracts.user_targets_response()

# Get error response template
error = DMarketContracts.error_response(
    code="ErrorCode",
    message="Error description"
)
```

### 3. Fixtures

AvAlgolable pytest fixtures:

| Fixture                | Description                       |
| ---------------------- | --------------------------------- |
| `pact`                 | Pact instance for consumer tests  |
| `pact_interaction`     | Builder for defining interactions |
| `pact_matchers`        | PactMatchers class                |
| `dmarket_contracts`    | DMarketContracts class            |
| `mock_pact_server_url` | URL of mock Pact server           |
| `pact_headers`         | Standard request headers          |

---

## Writing Contract Tests

### Basic Test Structure

```python
import pytest
from tests.contracts.conftest import DMarketContracts, is_pact_avAlgolable

# Skip if Pact not installed
pytestmark = pytest.mark.skipif(
    not is_pact_avAlgolable(),
    reason="pact-python not installed",
)


class TestMyEndpointContract:
    """Contract tests for my endpoint."""

    @pytest.mark.asyncio()
    async def test_successful_response(
        self,
        pact_interaction,
        dmarket_contracts: type[DMarketContracts],
    ) -> None:
        """Test contract for successful response."""
        expected_body = dmarket_contracts.balance_response()

        (
            pact_interaction
            .given("precondition state")
            .upon_receiving("a request description")
            .with_request(
                method="GET",
                path="/api/v1/endpoint",
                query={"param": "value"},
                headers={"Accept": "application/json"},
            )
            .will_respond_with(
                status=200,
                headers={"Content-Type": "application/json"},
                body=expected_body,
            )
        )

        assert pact_interaction is not None
```

### Testing Different Scenarios

#### Success Scenario

```python
@pytest.mark.asyncio()
async def test_get_balance_success(self, pact_interaction, dmarket_contracts):
    """Test successful balance retrieval."""
    (
        pact_interaction
        .given("user is authenticated")
        .upon_receiving("a request to get balance")
        .with_request(method="GET", path="/account/v1/balance")
        .will_respond_with(
            status=200,
            body=dmarket_contracts.balance_response(),
        )
    )
```

#### Empty Response

```python
@pytest.mark.asyncio()
async def test_get_items_empty(self, pact_interaction):
    """Test empty items response."""
    (
        pact_interaction
        .given("user has no items")
        .upon_receiving("a request for empty inventory")
        .with_request(method="GET", path="/marketplace-api/v1/user-inventory")
        .will_respond_with(
            status=200,
            body={"Items": [], "Total": "0", "Cursor": ""},
        )
    )
```

#### Error Response

```python
@pytest.mark.asyncio()
async def test_rate_limit_error(self, pact_interaction, dmarket_contracts):
    """Test rate limit error response."""
    (
        pact_interaction
        .given("rate limit exceeded")
        .upon_receiving("a request when rate limited")
        .with_request(method="GET", path="/account/v1/balance")
        .will_respond_with(
            status=429,
            body=dmarket_contracts.error_response(
                code="RateLimitExceeded",
                message="Too many requests",
            ),
        )
    )
```

#### POST Request with Body

```python
@pytest.mark.asyncio()
async def test_create_targets(self, pact_interaction, dmarket_contracts):
    """Test target creation contract."""
    request_body = {
        "GameID": "a8db",
        "Targets": [
            {
                "Title": "AK-47 | Redline (Field-Tested)",
                "Amount": 1,
                "Price": {"Amount": 1200, "Currency": "USD"},
            }
        ],
    }

    (
        pact_interaction
        .given("user can create targets")
        .upon_receiving("a request to create targets")
        .with_request(
            method="POST",
            path="/marketplace-api/v1/user-targets/create",
            headers={"Content-Type": "application/json"},
            body=request_body,
        )
        .will_respond_with(
            status=200,
            body=dmarket_contracts.create_targets_response(),
        )
    )
```

---

## Covered Endpoints

### Account Endpoints

| Endpoint                  | Tests | File                      |
| ------------------------- | ----- | ------------------------- |
| `GET /account/v1/balance` | 4     | test_account_contracts.py |
| `GET /account/v1/user`    | 1     | test_account_contracts.py |
| Rate Limit (429)          | 1     | test_account_contracts.py |

### Marketplace Endpoints

| Endpoint                                     | Tests | File                     |
| -------------------------------------------- | ----- | ------------------------ |
| `GET /exchange/v1/market/items`              | 3     | test_market_contracts.py |
| `POST /marketplace-api/v1/aggregated-prices` | 2     | test_market_contracts.py |
| `GET /exchange/v1/offers-by-title`           | 1     | test_market_contracts.py |

### Targets Endpoints

| Endpoint                                       | Tests | File                      |
| ---------------------------------------------- | ----- | ------------------------- |
| `GET /marketplace-api/v1/user-targets`         | 2     | test_targets_contracts.py |
| `POST /marketplace-api/v1/user-targets/create` | 3     | test_targets_contracts.py |
| `POST /marketplace-api/v1/user-targets/delete` | 1     | test_targets_contracts.py |
| `GET /marketplace-api/v1/targets-by-title`     | 1     | test_targets_contracts.py |

### Inventory/Offers Endpoints

| Endpoint                                      | Tests | File                        |
| --------------------------------------------- | ----- | --------------------------- |
| `GET /marketplace-api/v1/user-inventory`      | 3     | test_inventory_contracts.py |
| `POST /marketplace-api/v1/user-offers/create` | 1     | test_inventory_contracts.py |
| `GET /marketplace-api/v1/user-offers`         | 1     | test_inventory_contracts.py |
| `POST /marketplace-api/v1/user-offers/edit`   | 1     | test_inventory_contracts.py |
| `DELETE /exchange/v1/offers`                  | 1     | test_inventory_contracts.py |
| `PATCH /exchange/v1/offers-buy`               | 2     | test_inventory_contracts.py |

---

## CI/CD Integration

### GitHub Actions

Add contract tests to your workflow:

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  contract-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pact-python>=2.2.0

      - name: Run contract tests
        run: pytest tests/contracts/ -v --junitxml=contract-results.xml

      - name: Upload contract artifacts
        uses: actions/upload-artifact@v4
        with:
          name: pact-contracts
          path: tests/contracts/pacts/
          if-no-files-found: ignore
```

### Pact Broker Integration (Optional)

For teams with a Pact Broker:

```python
# tests/contracts/conftest.py

PACT_BROKER_URL = os.getenv("PACT_BROKER_URL")
PACT_BROKER_TOKEN = os.getenv("PACT_BROKER_TOKEN")

@pytest.fixture(scope="session")
def pact():
    """Create Pact with broker configuration."""
    pact = Pact(
        consumer=CONSUMER_NAME,
        provider=PROVIDER_NAME,
        pact_dir=str(PACTS_DIR),
        broker_base_url=PACT_BROKER_URL,
        broker_token=PACT_BROKER_TOKEN,
        publish_to_broker=True if PACT_BROKER_URL else False,
    )
    yield pact
```

---

## Best Practices

### 1. Use Provider States

Always define provider states for clear test setup:

```python
# Good
.given("user has active targets")

# Bad (no state)
.upon_receiving("request for targets")
```

### 2. Use Matchers for Flexibility

```python
# Good - flexible matching
PactMatchers.like("any-string")
PactMatchers.regex(r"^\d+$", "123")

# Bad - exact matching (fragile)
body={"id": "exact-value-that-might-change"}
```

### 3. Test Both Success and Error Cases

```python
# Test success
async def test_endpoint_success(...)

# Test error
async def test_endpoint_rate_limit(...)
async def test_endpoint_not_found(...)
async def test_endpoint_insufficient_balance(...)
```

### 4. Group Related Tests

```python
class TestBalanceContract:
    """All balance-related contracts."""
    async def test_get_balance_success(...)
    async def test_get_balance_with_currency(...)

class TestBalanceErrorContract:
    """Balance error contracts."""
    async def test_balance_rate_limit(...)
    async def test_balance_unauthorized(...)
```

### 5. Document Contracts

```python
async def test_get_balance_success(self, ...):
    """Test contract for balance retrieval.

    Verifies that:
    - Consumer sends GET request to /account/v1/balance
    - Provider responds with usd, dmc fields in cents/dimoshi
    - Response includes avAlgolable withdrawal amounts
    """
```

---

## Troubleshooting

### Pact Not Installed

```bash
# Error: pact-python not installed
pip install pact-python>=2.2.0

# Tests will be skipped automatically if not installed
pytest tests/contracts/ -v
# Shows: SKIPPED [1] tests/contracts/test_account_contracts.py: pact-python not installed
```

### Contract Verification FAlgoled

```
Contract verification fAlgoled!
Expected: {"usd": "1234"}
Got: {"balance": {"usd": 1234}}
```

**Solution**: Update expected response structure in `DMarketContracts`.

### Pact Server Port Conflict

```
Address already in use: 1234
```

**Solution**: Change port in conftest.py or kill process using port:

```bash
# Find process
lsof -i :1234
# Kill it
kill -9 <PID>
```

---

## Resources

- [Pact Documentation](https://docs.pact.io/)
- [pact-python GitHub](https://github.com/pact-foundation/pact-python)
- [Consumer-Driven Contracts](https://martinfowler.com/articles/consumerDrivenContracts.html)
- [DMarket API Specification](DMARKET_API_FULL_SPEC.md)
- [Project Testing Guide](testing_guide.md)

---

## Changelog

### 1.0 (December 2025)

- Initial contract testing implementation
- Support for Account, Marketplace, Targets, and Inventory endpoints
- PactMatchers helper class
- DMarketContracts expected response definitions
- CI/CD integration guide
