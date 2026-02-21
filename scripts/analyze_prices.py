"""Quick script to analyze and convert collected price data."""
import csv
import glob
import json
from pathlib import Path

# Find the latest collected data file
data_files = sorted(glob.glob("data/ml_trAlgoning/real_data/prices_*.json"))
if not data_files:
    print("No price data files found!")
    exit(1)

data_file = Path(data_files[-1])  # Use latest file
print(f"Using data file: {data_file}")

with open(data_file, encoding="utf-8") as f:
    data = json.load(f)

# Filter valid prices (reasonable range: $1 - $100)
all_prices = data["prices"]
valid_prices = [p for p in all_prices if 1.0 <= p["price_usd"] <= 100]

print(f"\nTotal items collected: {len(all_prices)}")
print(f"Valid prices ($1-$100): {len(valid_prices)}")
print(f"Invalid (out of range): {len(all_prices) - len(valid_prices)}")
print()

# Sample valid items
print("Sample valid items:")
for item in valid_prices[:10]:
    suggested = item.get("suggested_price_usd") or 0
    discount = ((suggested - item["price_usd"]) / suggested * 100) if suggested > 0 else 0
    print(f"  {item['item_name'][:45]}: ${item['price_usd']:.2f} (discount: {discount:.1f}%)")

# Convert to CSV format for ML trAlgoning
output_csv = Path("data/market_history.csv")

with open(output_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["date", "item_name", "price", "suggested_price", "profit", "profit_percent", "game"])
    
    for item in valid_prices:
        suggested = item.get("suggested_price_usd") or item["price_usd"]
        profit = suggested - item["price_usd"] if suggested > 0 else 0
        profit_percent = (profit / item["price_usd"] * 100) if item["price_usd"] > 0 else 0
        
        writer.writerow([
            item["collected_at"],
            item["item_name"],
            round(item["price_usd"], 2),
            round(suggested, 2),
            round(profit, 2),
            round(profit_percent, 2),
            item["game"],
        ])

print(f"\nReplaced market_history.csv with {len(valid_prices)} real prices from DMarket API")
print(f"Data saved to: {output_csv}")
