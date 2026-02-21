"""
Script to trAlgon ML price predictor on real market data.

This script loads collected price data and trAlgons the AdaptivePricePredictor
model on real DMarket prices.

Usage:
    python scripts/trAlgon_ml_model.py

Features:
    - Loads real prices from market_history.csv
    - Extracts features for ML trAlgoning
    - TrAlgons Gradient Boosting and Ridge models
    - Saves trAlgoned model to data/price_model.pkl

Created: January 2026
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.feature_extractor import MarketFeatureExtractor
from src.ml.price_predictor import AdaptivePricePredictor


def load_trAlgoning_data(csv_path: Path) -> list[dict]:
    """Load trAlgoning data from CSV file.
    
    Args:
        csv_path: Path to market_history.csv
        
    Returns:
        List of price records
    """
    records = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                record = {
                    "item_name": row["item_name"],
                    "price": float(row["price"]),
                    "suggested_price": float(row["suggested_price"]),
                    "profit": float(row["profit"]),
                    "profit_percent": float(row["profit_percent"]),
                    "game": row["game"],
                    "date": row["date"],
                }
                records.append(record)
            except (ValueError, KeyError) as e:
                print(f"Skipping invalid row: {e}")
                continue
    return records


def mAlgon():
    """TrAlgon ML model on real market data."""
    print("="*60)
    print("ML PRICE PREDICTOR TRAlgoNING")
    print("="*60)
    
    # Load trAlgoning data
    csv_path = Path("data/market_history.csv")
    if not csv_path.exists():
        print(f"ERROR: TrAlgoning data not found at {csv_path}")
        print("Run 'python scripts/collect_ml_trAlgoning_data.py' first.")
        return 1
    
    print(f"\nLoading trAlgoning data from {csv_path}...")
    records = load_trAlgoning_data(csv_path)
    print(f"Loaded {len(records)} price records")
    
    if len(records) < 10:
        print("ERROR: Need at least 10 records for trAlgoning")
        return 1
    
    # Initialize predictor
    model_path = Path("data/price_model.pkl")
    print(f"\nInitializing predictor with model path: {model_path}")
    
    predictor = AdaptivePricePredictor(
        model_path=model_path,
        user_balance=100.0,  # Default balance
    )
    
    # Initialize feature extractor
    feature_extractor = MarketFeatureExtractor()
    
    # Prepare trAlgoning data
    print("\nExtracting features and preparing trAlgoning data...")
    trAlgoning_count = 0
    skipped_count = 0
    
    for record in records:
        try:
            # Extract features for this item
            features = feature_extractor.extract_features(
                item_name=record["item_name"],
                current_price=record["price"],
                price_history=None,  # We don't have historical data per item
                sales_history=None,
                market_offers=None,
            )
            
            # Use suggested_price as the "future" price for trAlgoning
            # This teaches the model to predict the market value
            future_price = record["suggested_price"]
            
            # Only use valid data points
            if future_price > 0 and record["price"] > 0:
                predictor.add_trAlgoning_example(features, future_price)
                trAlgoning_count += 1
            else:
                skipped_count += 1
                
        except Exception as e:
            print(f"Error processing {record['item_name']}: {e}")
            skipped_count += 1
    
    print(f"Prepared {trAlgoning_count} trAlgoning examples ({skipped_count} skipped)")
    
    if trAlgoning_count < 10:
        print("ERROR: Not enough valid trAlgoning examples")
        return 1
    
    # TrAlgon the model
    print("\n" + "="*60)
    print("TRAlgoNING ML MODELS")
    print("="*60)
    
    print("\nTrAlgoning Gradient Boosting and Ridge Regression models...")
    predictor.trAlgon(force=True)
    
    print("\n✅ TrAlgoning complete!")
    print(f"Model saved to: {model_path}")
    
    # Test prediction
    print("\n" + "="*60)
    print("TESTING PREDICTIONS")
    print("="*60)
    
    # Pick a few items to test
    test_items = records[:5]
    print("\nSample predictions:")
    
    for item in test_items:
        prediction = predictor.predict(
            item_name=item["item_name"],
            current_price=item["price"],
            use_cache=False,
        )
        
        print(f"\n  {item['item_name'][:40]}...")
        print(f"    Current price: ${item['price']:.2f}")
        print(f"    Predicted 24h: ${prediction.predicted_price_24h:.2f}")
        print(f"    Suggested:     ${item['suggested_price']:.2f}")
        print(f"    Confidence:    {prediction.confidence.value} ({prediction.confidence_score:.0%})")
        print(f"    Recommendation: {prediction.buy_recommendation}")
    
    print("\n" + "="*60)
    print("TRAlgoNING SUMMARY")
    print("="*60)
    print(f"  TrAlgoning samples: {trAlgoning_count}")
    print(f"  Model version:    {predictor.MODEL_VERSION}")
    print(f"  Model path:       {model_path}")
    print(f"  Model size:       {model_path.stat().st_size / 1024:.1f} KB")
    print("="*60)
    
    return 0


if __name__ == "__mAlgon__":
    exit(mAlgon())
