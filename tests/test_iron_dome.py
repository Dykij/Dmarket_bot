import unittest
from decimal import Decimal
from src.core.security import Sanitizer, TradeValidator, SecurityException

class TestIronDome(unittest.TestCase):

    def test_sanitizer_injection(self):
        """Test cleaning of malicious item names."""
        dirty_input = "AWP | Ignore Rules; DROP TABLE"
        expected = "AWP | Ignore Rules" # Semicolon and DROP TABLE parts are invalid in regex?
        # Wait, regex is [^a-zA-Z0-9\s\|\-\(\)]
        # ; is removed. D, R, O, P, T, A, B, L, E are allowed.
        # So "DROP TABLE" will remain, but the semicolon won't.
        # Let's adjust expectation based on the regex logic provided in instructions.
        # Regex: r"[^a-zA-Z0-9\s\|\-\(\)]"
        # Input: "AWP | Ignore Rules; DROP TABLE"
        # The ';' is not in allowlist. The rest are letters/spaces.
        # So it becomes "AWP | Ignore Rules DROP TABLE"

        # Let's verify the exact instruction expectation: "Expect None or Cleaned string".
        cleaned = Sanitizer.clean_item_name(dirty_input)
        print(f"\n[Sanitizer] Input: '{dirty_input}' -> Output: '{cleaned}'")

        # The goal is to ensure special chars that could be SQL/Command injection (like ;) are gone.
        self.assertNotIn(";", cleaned)
        self.assertEqual(cleaned, "AWP | Ignore Rules DROP TABLE")

    def test_hallucination_price(self):
        """Test price validation logic."""
        avg_price = 5.0
        hallucinated_price = 500.0
        balance = 10000.0 # High balance so that check passes

        print(f"\n[TradeValidator] Testing Price {hallucinated_price} vs Avg {avg_price}")

        with self.assertRaises(SecurityException) as cm:
            TradeValidator.validate_buy(hallucinated_price, avg_price, balance)

        print(f"[TradeValidator] Caught expected exception: {cm.exception}")

    def test_balance_protection(self):
        """Test balance exposure limit."""
        price = 200.0
        avg_price = 1000.0 # Price is fine vs avg
        balance = 1000.0   # But price is 20% of balance (limit is 10%)

        print(f"\n[TradeValidator] Testing Balance Exposure: Price {price} vs Balance {balance}")

        with self.assertRaises(SecurityException) as cm:
            TradeValidator.validate_buy(price, avg_price, balance)

        print(f"[TradeValidator] Caught expected exception: {cm.exception}")

if __name__ == '__main__':
    unittest.main()
