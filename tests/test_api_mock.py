import pytest
from unittest.mock import patch, MagicMock
from src.dmarket_api_client import DMarketAPIClient

@pytest.fixture
def mock_client():
    # Mocking nacl init internally since we don't need real keys for this mock
    with patch('src.dmarket_api_client.SigningKey'):
        return DMarketAPIClient(public_key="mock_pub", secret_key="mock_sec_mock_sec_mock_sec_mock_sec_mock_sec_mock_sec_mock_sec_")

def test_get_real_balance_success(mock_client):
    with patch.object(mock_client, 'make_request') as mock_make_request:
        # DMarket returns balance in cents as string
        mock_make_request.return_value = {"usd": "1550"} 
        
        balance = mock_client.get_real_balance()
        assert balance == 15.50
        mock_make_request.assert_called_once_with("GET", "/account/v1/balance")

def test_get_real_balance_api_failure(mock_client):
    with patch.object(mock_client, 'make_request') as mock_make_request:
        # Simulate an unexpected API format
        mock_make_request.return_value = {"error": "Unauthorized"}
        
        balance = mock_client.get_real_balance()
        assert balance == 0.0
