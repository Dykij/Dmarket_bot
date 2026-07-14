from pathlib import Path

p = Path("tests/sandbox_full_cycle.py")
content = p.read_text()

# Wrap sell_price assignment with D(str(...)) to ensure Decimal
# There are two places where sell_price is assigned from best_sell_price and other.
# Add wrap around best_sell_price before sell_price assignment
# old:         sell_price = best_sell_price
# new:         sell_price = D(str(best_sell_price))
content = content.replace(
    '        sell_price = best_sell_price',
    '        sell_price = D(str(best_sell_price))'
)

# Also wrap csEntrerie  285 and 905
content = content.replace(
    '        cs_price = oracle_prices.get(title, 0)',
    '        cs_price = D(str(oracle_prices.get(title, 0)))'
)

# For line 905 if it exists
content = content.replace(
    '                        cs_price = getattr(snap, "min_price", 0) if snap else 0',
    '                        cs_price = D(str(getattr(snap, "min_price", 0))) if snap else D("0")'
)

p.write_text(content)
print("Patched sell_price in tests/sandbox_full_cycle.py")
