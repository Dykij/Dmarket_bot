from pathlib import Path

p = Path("src/core/target_sniping/validations.py")
content = p.read_text()

content = content.replace(
    "from src.config import Config\nfrom src.db.price_history import price_db",
    'from src.config import Config\nfrom src.db.price_history import price_db\nfrom src.utils.decimal_helpers import D, quantize'
)

content = content.replace(
    "def check_obi(\n    ask_cnt: int, bid_cnt: int, best_ask: float, best_bid: float\n) -> dict:",
    'def check_obi(\n    ask_cnt: int, bid_cnt: int, best_ask: Decimal, best_bid: Decimal\n) -> dict:'
)

content = content.replace(
    '    safe_bid = best_bid or 0.01\n    safe_ask = best_ask or 0.01',
    '    safe_bid = best_bid or D("0.01")\n    safe_ask = best_ask or D("0.01")'
)

content = content.replace(
    '    obi_ratio = bid_volume / ask_volume if ask_volume > 0 else 1.0',
    '    obi_ratio = bid_volume / ask_volume if ask_volume > 0 else D("1")'
)

# replace check_slippage signature if it exists
if 'def check_slippage(' in content:
    content = content.replace(
        'def check_slippage(\n    target_price: float,\n    best_ask_price: float,\n    max_slippage_pct: float = 0.05,\n) -> dict:',
        'def check_slippage(\n    target_price: Decimal,\n    best_ask_price: Decimal,\n    max_slippage_pct: Decimal = D("0.05"),\n) -> dict:'
    )

# replace evaluate_cross_market_arb signature
if 'def evaluate_cross_market_arb(' in content:
    content = content.replace(
        'def evaluate_cross_market_arb(\n    title: str,\n    buy_price: float,\n    sell_price: float,\n    source_fee: float = 0.0,\n    dest_fee: float = 0.0,\n    min_margin_pct: float = 0.0,\n) -> dict:',
        'def evaluate_cross_market_arb(\n    title: str,\n    buy_price: Decimal,\n    sell_price: Decimal,\n    source_fee: Decimal = D("0.0"),\n    dest_fee: Decimal = D("0.0"),\n    min_margin_pct: Decimal = D("0.0"),\n) -> dict:'
    )
    content = content.replace(
        '    if buy_price <= 0:',
        '    if buy_price <= D("0"):'
    )

p.write_text(content)
print("Patched src/core/target_sniping/validations.py")
