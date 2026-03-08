import asyncio
import sys
import os

# Add parent directory to path to allow imports if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market_data_fetcher import LiveMarketDataFetcher

async def main():
    print("=== DMarket Live Prices Test ===")
    
    fetcher = LiveMarketDataFetcher()
    game_id = "a8db" # CS2 / CS:GO
    item_title = "AK-47 | Slate (Field-Tested)"
    
    print(f"Fetching live Order Book for '{item_title}'...")
    try:
        best_bid, best_ask = await fetcher.get_order_book(game_id, item_title)
        
        print("\n--- Live Market Data ---")
        if best_bid is not None:
            print(f"💰 Best Bid (Buy Target): ${best_bid:.2f}")
        else:
            print("💰 Best Bid (Buy Target): None found or API restricted")
            
        if best_ask is not None:
            print(f"🛒 Best Ask (Sell Offer): ${best_ask:.2f}")
        else:
            print("🛒 Best Ask (Sell Offer): None found")
            
        if best_bid is not None and best_ask is not None:
            spread = best_ask - best_bid
            print(f"📊 Gross Spread: ${spread:.2f}")
    except Exception as e:
        print(f"Failed to fetch market data: {e}")
    finally:
        await fetcher.close()

if __name__ == "__main__":
    asyncio.run(main())
