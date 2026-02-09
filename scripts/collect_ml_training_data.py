"""
Script to collect real market prices for ML training.

This script connects to DMarket API and collects real price data
for training the ML price predictor model.

Usage:
    python scripts/collect_ml_training_data.py --games csgo rust --items 500

Features:
    - Collects real prices from DMarket API
    - Saves data in format suitable for ML training
    - Supports multiple games
    - Automatic deduplication
    - Progress tracking

Created: January 2026
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.dmarket.dmarket_api import DMarketAPI
from src.ml.price_normalizer import PriceNormalizer

# Output directory for training data
OUTPUT_DIR = Path("data/ml_training/real_data")


async def collect_prices_for_game(
    collector: RealPriceCollector,
    game: GameType,
    max_items: int = 500,
) -> list[dict]:
    """Collect prices for a specific game.
    
    Args:
        collector: RealPriceCollector instance
        game: Game type to collect prices for
        max_items: Maximum number of items to collect
        
    Returns:
        List of collected price records
    """
    print(f"\n{'='*60}")
    print(f"Collecting prices for {game.value.upper()}")
    print(f"{'='*60}")
    
    collected_data = []
    
    try:
        # Collect from DMarket
        result = await collector.collect_from_dmarket(
            item_names=[],  # Empty list = collect all available
            game=game,
        )
        
        print(f"DMarket: {result.items_collected} items collected")
        
        for price in result.prices:
            record = {
                "item_name": price.item_name,
                "game": game.value,
                "source": price.normalized_price.source.value,
                "price_usd": float(price.normalized_price.price_usd),
                "price_cents": price.normalized_price.price_cents,
                "collected_at": datetime.now(UTC).isoformat(),
                "additional_data": price.additional_data,
            }
            collected_data.append(record)
            
            if len(collected_data) >= max_items:
                break
                
    except Exception as e:
        print(f"Error collecting from DMarket: {e}")
    
    print(f"Total collected for {game.value}: {len(collected_data)} items")
    return collected_data


async def collect_all_games(
    api: DMarketAPI,
    games: list[str],
    max_items_per_game: int = 500,
) -> dict:
    """Collect prices from all specified games.
    
    Args:
        api: DMarket API client
        games: List of game names
        max_items_per_game: Maximum items per game
        
    Returns:
        Dictionary with all collected data
    """
    collector = RealPriceCollector(
        dmarket_api=api,
        normalizer=PriceNormalizer(),
    )
    
    all_data = {
        "metadata": {
            "collected_at": datetime.now(UTC).isoformat(),
            "games": games,
            "max_items_per_game": max_items_per_game,
            "total_items": 0,
        },
        "prices": [],
    }
    
    for game_name in games:
        try:
            game = GameType(game_name.lower())
        except ValueError:
            print(f"Unknown game: {game_name}, skipping...")
            continue
            
        prices = await collect_prices_for_game(
            collector=collector,
            game=game,
            max_items=max_items_per_game,
        )
        all_data["prices"].extend(prices)
    
    all_data["metadata"]["total_items"] = len(all_data["prices"])
    return all_data


async def collect_from_live_api(
    games: list[str],
    max_items_per_game: int = 500,
) -> dict:
    """Collect real prices from live DMarket API.
    
    Args:
        games: List of game names to collect
        max_items_per_game: Maximum items per game
        
    Returns:
        Dictionary with collected data
    """
    print("\n" + "="*60)
    print("COLLECTING REAL PRICES FROM DMARKET API")
    print("="*60)
    
    # Get API keys from environment
    public_key = os.getenv("DMARKET_PUBLIC_KEY", "")
    secret_key = os.getenv("DMARKET_SECRET_KEY", "")
    
    if not public_key or not secret_key:
        print("ERROR: DMARKET_PUBLIC_KEY and DMARKET_SECRET_KEY must be set!")
        print("Set them in .env file or environment variables.")
        return {"metadata": {"error": "Missing API keys"}, "prices": []}
    
    # Initialize DMarket API
    api = DMarketAPI(public_key=public_key, secret_key=secret_key)
    
    try:
        # Check connection
        balance = await api.get_balance()
        print(f"Connected to DMarket API. Balance: ${balance:.2f}")
    except Exception as e:
        print(f"Warning: Could not get balance: {e}")
        print("Continuing with price collection...")
    
    # Collect prices
    all_data = {
        "metadata": {
            "collected_at": datetime.now(UTC).isoformat(),
            "games": games,
            "max_items_per_game": max_items_per_game,
            "total_items": 0,
            "source": "dmarket_live",
        },
        "prices": [],
    }
    
    for game_name in games:
        print(f"\n{'='*60}")
        print(f"Collecting prices for {game_name.upper()}")
        print(f"{'='*60}")
        
        try:
            # Get items from DMarket with price filter for realistic data
            response = await api.get_market_items(
                game=game_name,
                limit=min(max_items_per_game, 100),  # API limit per request
                price_from=1.0,  # Minimum $1 to avoid trash items
                price_to=100.0,  # Maximum $100 for common tradable items
            )
            
            # Extract items from response (objects or items key)
            items = response.get("objects", []) or response.get("items", [])
            print(f"Received {len(items)} items from API")
            
            for item in items:
                # Extract price data
                price_data = item.get("price", {})
                suggested_price = item.get("suggestedPrice", {})
                extra = item.get("extra", {})
                
                price_usd = float(price_data.get("USD", 0)) / 100
                suggested_usd = float(suggested_price.get("USD", 0)) / 100 if suggested_price else None
                
                record = {
                    "item_name": item.get("title", "Unknown"),
                    "game": game_name,
                    "source": "dmarket",
                    "price_usd": price_usd,
                    "suggested_price_usd": suggested_usd,
                    "discount_percent": ((suggested_usd - price_usd) / suggested_usd * 100) if suggested_usd and suggested_usd > 0 else None,
                    "collected_at": datetime.now(UTC).isoformat(),
                    "item_id": item.get("itemId", ""),
                    "trade_lock_hours": extra.get("tradeLockDuration", 0) / 3600 if extra.get("tradeLockDuration") else 0,
                    "category": extra.get("category", ""),
                    "exterior": extra.get("exterior", ""),
                    "float_value": extra.get("floatValue"),
                }
                all_data["prices"].append(record)
                
        except Exception as e:
            print(f"Error collecting {game_name}: {e}")
            import traceback
            traceback.print_exc()
    
    all_data["metadata"]["total_items"] = len(all_data["prices"])
    
    return all_data


def save_training_data(data: dict, filename: str | None = None) -> Path:
    """Save collected data to file.
    
    Args:
        data: Collected price data
        filename: Optional filename (auto-generated if not provided)
        
    Returns:
        Path to saved file
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"prices_{timestamp}.json"
    
    output_path = OUTPUT_DIR / filename
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print(f"Data saved to: {output_path}")
    print(f"Total items: {data['metadata']['total_items']}")
    print(f"{'='*60}")
    
    return output_path


def merge_with_existing(new_data: dict, existing_path: Path | None = None) -> dict:
    """Merge new data with existing training data.
    
    Args:
        new_data: Newly collected data
        existing_path: Path to existing data file
        
    Returns:
        Merged data
    """
    if existing_path is None or not existing_path.exists():
        return new_data
    
    with open(existing_path, encoding="utf-8") as f:
        existing_data = json.load(f)
    
    # Create set of existing items for deduplication
    existing_keys = set()
    for price in existing_data.get("prices", []):
        key = f"{price['item_name']}:{price['game']}:{price['collected_at'][:10]}"
        existing_keys.add(key)
    
    # Add only new items
    new_items_added = 0
    for price in new_data.get("prices", []):
        key = f"{price['item_name']}:{price['game']}:{price['collected_at'][:10]}"
        if key not in existing_keys:
            existing_data["prices"].append(price)
            new_items_added += 1
    
    # Update metadata
    existing_data["metadata"]["total_items"] = len(existing_data["prices"])
    existing_data["metadata"]["last_updated"] = datetime.now(UTC).isoformat()
    
    print(f"Merged {new_items_added} new items with existing data")
    
    return existing_data


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Collect real market prices for ML training"
    )
    parser.add_argument(
        "--games",
        nargs="+",
        default=["csgo", "rust", "dota2", "tf2"],
        help="Games to collect prices for",
    )
    parser.add_argument(
        "--items",
        type=int,
        default=500,
        help="Maximum items per game",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output filename (auto-generated if not provided)",
    )
    parser.add_argument(
        "--merge",
        type=str,
        default=None,
        help="Path to existing file to merge with",
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("ML TRAINING DATA COLLECTOR")
    print("="*60)
    print(f"Games: {args.games}")
    print(f"Max items per game: {args.items}")
    
    # Collect data
    data = asyncio.run(collect_from_live_api(
        games=args.games,
        max_items_per_game=args.items,
    ))
    
    # Merge with existing if specified
    if args.merge:
        merge_path = Path(args.merge)
        data = merge_with_existing(data, merge_path)
    
    # Save data
    save_training_data(data, args.output)
    
    print("\nDone!")


if __name__ == "__main__":
    main()
