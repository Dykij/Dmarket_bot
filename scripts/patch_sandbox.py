from pathlib import Path

p = Path("tests/sandbox_full_cycle.py")
content = p.read_text()

# Add import if not present
if 'from src.utils.decimal_helpers import D, quantize' not in content:
    content = content.replace(
        'from src.config import Config',
        'from src.config import Config\nfrom src.utils.decimal_helpers import D, quantize'
    )

# Replace the two specific lines that cause TypeError due to float * Decimal
content = content.replace(
    'cross_sell = cs_price * (1 - destination_fee) * (1 - Config.WITHDRAWAL_FEE_RATE)',
    'cross_sell = D(str(cs_price)) * (D("1") - D(str(destination_fee))) * (D("1") - Config.WITHDRAWAL_FEE_RATE)'
)

content = content.replace(
    'cross_sell = cs_price * (1 - 0.025) * (1 - Config.WITHDRAWAL_FEE_RATE)',
    'cross_sell = D(str(cs_price)) * (D("1") - D("0.025")) * (D("1") - Config.WITHDRAWAL_FEE_RATE)'
)

p.write_text(content)
print("Patched tests/sandbox_full_cycle.py")
