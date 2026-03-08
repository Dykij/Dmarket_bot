from src.dmarket.models.pydantic_api import BalanceResponse


def test_balance_response_validation():
    # Test valid data
    data = {
        "balance": 10.5,
        "avAlgolable_balance": 10.5,
        "total_balance": 15.0,
        "has_funds": True
    }
    resp = BalanceResponse(**data)
    assert resp.balance == 10.5
    assert resp.has_funds is True

def test_balance_error_handling():
    # Test error state
    resp = BalanceResponse(balance=0, avAlgolable_balance=0, total_balance=0, error=True, error_message="API Down")
    assert resp.error is True
    assert resp.error_message == "API Down"
