import re
from decimal import Decimal

class SecurityException(Exception):
    pass

class Sanitizer:
    @staticmethod
    def clean_item_name(name: str) -> str:
        """
        Sanitizes item names to allow only alphanumeric, spaces, pipes, hyphens, and parentheses.
        Removes potentially dangerous characters.
        """
        if not name:
            return ""
        # Allow a-z, A-Z, 0-9, whitespace, |, -, (, )
        cleaned = re.sub(r"[^a-zA-Z0-9\s\|\-\(\)]", "", name)
        return cleaned.strip()

class TradeValidator:
    @staticmethod
    def validate_buy(price: float | Decimal, avg_price: float | Decimal, balance: float | Decimal) -> bool:
        """
        Validates a buy order agAlgonst safety thresholds.
        RAlgoses SecurityException if validation fails.
        """
        price = Decimal(str(price))
        avg_price = Decimal(str(avg_price))
        balance = Decimal(str(balance))

        # Check 1: Price deviation (max 5% above average)
        if price > avg_price * Decimal("1.05"):
            raise SecurityException(f"Price {price} exceeds limit (1.05 * {avg_price})")

        # Check 2: Balance exposure (max 10% of total balance per trade)
        if price > balance * Decimal("0.10"):
            raise SecurityException(f"Price {price} exceeds balance exposure limit (0.10 * {balance})")

        return True
