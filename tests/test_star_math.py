import pytest

def mock_star_spread_filter(best_bid: float, best_ask: float, commission_fee: float = 0.05) -> bool:
    """Mock reproducing the math logic in autonomous_scanner.py"""
    if best_bid <= 0 or best_ask <= 0:
        return False
        
    raw_profit = (best_bid * (1 - commission_fee)) - best_ask
    return raw_profit > 0.01

def test_star_math_positive_spread():
    # Buy at $10.00, Sell at $12.00.
    # Commission on $12.00 sale is $0.60. We receive $11.40.
    # Profit: 11.40 - 10.00 = $1.40 (> 0.01)
    
    # In scanner logic: best_bid is target sale price, best_ask is target purchase price.
    result = mock_star_spread_filter(best_bid=12.00, best_ask=10.00)
    assert result is True

def test_star_math_negative_spread():
    # Target Sale (Bid) is $10.00. Purchase (Ask) is $9.60.
    # We receive 10.00 * 0.95 = 9.50.
    # Profit: 9.50 - 9.60 = -$0.10. Should reject!
    result = mock_star_spread_filter(best_bid=10.00, best_ask=9.60)
    assert result is False

def test_star_math_zero_prices():
    result = mock_star_spread_filter(best_bid=0.00, best_ask=5.00)
    assert result is False
