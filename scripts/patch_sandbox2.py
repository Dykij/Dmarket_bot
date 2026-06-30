from pathlib import Path

p = Path("tests/sandbox_full_cycle.py")
content = p.read_text()

# Replace assignment at line 286
content = content.replace(
    '        dm_buy_price = ask',
    '        dm_buy_price = D(str(ask))'
)
# Replace dict value at line 555
content = content.replace(
    '            "dm_buy_price": ask,',
    '            "dm_buy_price": D(str(ask)),'
)

# Replace any other hard-coded float constants that could conflict with Decimal operations
# like `0.025`, `0.005`, `0.01` etc. if they are involved in math with Decimal Config values.
# We'll be conservative and only patch exact lines if needed based on next error.

p.write_text(content)
print("Patched dm_buy_price in tests/sandbox_full_cycle.py")
