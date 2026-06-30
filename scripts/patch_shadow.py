from pathlib import Path

p = Path("src/core/shadow_engine.py")
content = p.read_text()

if 'from decimal import Decimal' not in content:
    content = content.replace(
        'import json',
        'import json\nfrom decimal import Decimal\nfrom src.utils.decimal_helpers import D, quantize'
    )

# __init__ Decimal initialization
content = content.replace(
    '        self._balance = initial_balance\n        self._initial_balance = initial_balance\n        self._peak_balance = initial_balance',
    '        self._balance = D(str(initial_balance))\n        self._initial_balance = D(str(initial_balance))\n        self._peak_balance = D(str(initial_balance))'
)

# Wrap float arithmetic with `_balance` to use Decimal
content = content.replace(
    '                    self._balance += current_price - fee',
    '                    self._balance += D(str(current_price)) - D(str(fee))'
)

# cycle_result spent/earned might also need wrapping if they mix with Decimal. 
# For now we only patch _balance operations because that's what crashes.

p.write_text(content)
print("Patched shadow_engine.py")
