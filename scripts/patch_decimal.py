import re
from pathlib import Path

def patch_file(filepath: str, replacements: list):
    p = Path(filepath)
    content = p.read_text()
    for old, new in replacements:
        if old not in content:
            print(f"WARN: Pattern not found in {filepath}: {old[:50]}...")
            continue
        content = content.replace(old, new)
    p.write_text(content)
    print(f"Patched {filepath}")

# Validate we're in the right directory
import os
os.chdir('/home/deck/dmarket/Dmarket_bot-main')

# 1. price_validator.py
patch_file("src/risk/price_validator.py", [
    ('from typing import Union\n\nMIN_PRICE_USD = 0.10\nMAX_PRICE_USD = 50_000.00', 
     'from typing import Union\nfrom decimal import Decimal\n\nfrom src.utils.decimal_helpers import D, quantize\n\nMIN_PRICE_USD = Decimal("0.10")\nMAX_PRICE_USD = Decimal("50000")'),
    
    ('def validate_price(\n    price: Union[float, int, str],\n    label: str = "price",\n) -> float:',
     'def validate_price(\n    price: Union[Decimal, float, int, str],\n    label: str = "price",\n) -> Decimal:'),
    
    ("    try:\n        value = float(price)\n    except (ValueError, TypeError) as e:",
     "    try:\n        value = Decimal(str(price))\n    except (ValueError, TypeError) as e:"),
     
    ('def validate_arbitrage_profit(\n    buy_price: float,\n    expected_sell_price: float,\n    fee_markup: float = 0.05,\n    min_profit_margin: float = 0.05,\n    lock_days: int = 7,\n    penalty_per_day: float = 0.005  # 0.5% per day penalty\n) -> float:',
     'def validate_arbitrage_profit(\n    buy_price: Decimal,\n    expected_sell_price: Decimal,\n    fee_markup: Decimal = Decimal("0.05"),\n    min_profit_margin: Decimal = Decimal("0.05"),\n    lock_days: int = 7,\n    penalty_per_day: Decimal = Decimal("0.005")  # 0.5% per day penalty\n) -> Decimal:'),
     
    ('    net_received = expected_sell_price * (1.0 - fee_markup)\n    actual_profit = net_received - buy_price\n\n    if actual_profit <= 0:',
     '    net_received = expected_sell_price乘以 * (Decimal("1") - fee_markup)\n    actual_profit = net_received - buy_price\n\n    if actual_profit <= Decimal("0"):'),
     
    ('    profit_margin_pct = actual_profit / buy_price\n    \n    # --- TVM Penalty (v7.6) ---\n    # Adjust margin by time penalty: Margin_Adj = Margin - (Penalty * Days)\n    # This reflects that $100 profit today is better than $100 profit in 7 days.\n    tvm_adjusted_margin = profit_margin_pct - (penalty_per_day * lock_days)',
     '    profit_margin_pct = actual_profit / buy_price\n    \n    # --- TVM Penalty (v7.6) ---\n    # Adjust margin by time penalty: Margin_Adj = Margin - (Penalty * Days)\n    # This reflects that $100 profit today is better than $100 profit in 7 days.\n    tvm_adjusted_margin = profit_margin_pct - (penalty_per_day * Decimal(lock_days))'),
     
    ('def validate_slippage(target_price: float, current_market_price: float, max_slippage_pct: float = 0.02) -> None:',
     'def validate_slippage(target_price: Decimal, current_market_price: Decimal, max_slippage_pct: Decimal = Decimal("0.02")) -> None:'),
    
    ('    if current_market_price <= 0:\n        raise PriceValidationError("Market price is invalid (<=0).")\n    if target_price <= 0:',
     '    if current_market_price <= Decimal("0"):\n        raise PriceValidationError("Market price is invalid (<=0).")\n    if target_price <= Decimal("0"):'),
    
    ('def validate_volatility(recent_prices: list[float], max_std_dev_pct: float = 0.15) -> None:',
     'def validate_volatility(recent_prices: list[Decimal], max_std_dev_pct: Decimal = Decimal("0.15")) -> None:'),
])

# 2. base.py - calculate_position_size relevant parts
patch_file("src/strategies/base.py", [
    ('from src.config import Config\n\nlogger = logging.getLogger("Strategy")', 
     'from src.config import Config\nfrom decimal import Decimal\n\nlogger = logging.getLogger("Strategy")'),
    
    ('    def calculate_position_size(\n        self,\n        current_balance: float,\n        item_price: float,\n        volatility_score: float = 1.0,\n        sharpe_estimate: float = 1.0,\n    ) -> int:',
     '    def calculate_position_size(\n        self,\n        current_balance: Decimal,\n        item_price: Decimal,\n        volatility_score: Decimal = Decimal("1.0"),\n        sharpe_estimate: Decimal = Decimal("1.0"),\n    ) -> int:'),
     
    ('        if not Config.USE_DYNAMIC_SIZING or current_balance <= 0:\n            return 1\n\n        max_risk_amount = current_balance * (Config.MAX_POSITION_RISK_PCT / 100.0)\n\n        # Adjust risk based on volatility (higher vol = lower risk)\n        adjusted_risk = max_risk_amount / max(volatility_score, 1.0)', 
     '        if not Config.USE_DYNAMIC_SIZING or current_balance <= Decimal("0"):\n            return 1\n\n        max_risk_amount = current_balance * (Config.MAX_POSITION_RISK_PCT / Decimal("100"))\n\n        # Adjust risk based on volatility (higher vol = lower risk)\n        adjusted_risk = max_risk_amount / max(volatility_score, Decimal("1.0"))'),
     
    ('        if sharpe_estimate < 1.0:\n            adjusted_risk *= max(0.3, sharpe_estimate)\n        elif sharpe_estimate > 2.0:\n            adjusted_risk *= min(1.5, sharpe_estimate / 1.5)',
     '        if sharpe_estimate < Decimal("1.0"):\n            adjusted_risk *= max(Decimal("0.3"), sharpe_estimate)\n        elif sharpe_estimate > Decimal("2.0"):\n            adjusted_risk *= min(Decimal("1.5"), sharpe_estimate / Decimal("1.5"))'),
])

# 3. profit_tracker.py
patch_file("src/db/profit_tracker.py", [
    ('from src.db.db_retry import with_db_retry', 
     'from decimal import Decimal\nfrom alt=""src.utils.decimal_helpers import D, quantize\nfrom src.db.db_retry import with_db_retry'),
    
    ('    def record_trade(self, item_name: str, buy_price: float, sell_price: float, fee_rate: float):',
     '    def record_trade(self, item_name: str, buy_price: Decimal, sell_price: Decimal, fee_rate: Decimal):'),
    
    ("        with self.conn:\n            self.conn.execute('''\n                INSERT INTO trades (item_name, buy_price, sell_price, fee_amount, net_profit)\n                VALUES (?, ?, ?, ?, ?)\n            ''', (item_name, buy_price, sell_price, fee_amount, net_profit))",
     "        with self.conn:\n            self.conn.execute('''\n                INSERT INTO trades (item_name, buy_price, sell_price, fee_amount, net_profit)\n                VALUES (?, ?, ?, ?, ?)\n            ''', (item_name, float(buy_price), float(sell_price), float(fee_amount), float(net_profit)))"),
])

print("All patches applied successfully!")
