import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.Algo.price_predictor import PricePredictor
from src.dmarket.dmarket_api import DMarketAPI
from src.dmarket.market_data_logger import MarketDataLogger, MarketDataLoggerConfig


async def auto_fix():
    print("--- AUTO-FIX START ---")
    
    # 1. Check Data
    config = MarketDataLoggerConfig(
        output_path="data/market_history.csv",
        max_items_per_scan=100,  # Minimum required
        games=["a8db", "tf2", "dota2", "rust"],
        min_price_cents=50,
        max_price_cents=100000,
    )
    
    data_path = Path(config.output_path)
    rows = 0
    if data_path.exists():
        with open(data_path, encoding='utf-8') as f:
            rows = sum(1 for _ in f) - 1
            
    print(f"Current Data Rows: {rows}")
    
    # 2. Collect Data if needed
    if rows < 100:
        print("Action: Collecting missing data...")
        api = DMarketAPI(
            public_key=os.getenv("DMARKET_PUBLIC_KEY", ""),
            secret_key=os.getenv("DMARKET_SECRET_KEY", ""),
        )
        logger = MarketDataLogger(api, config)
        
        # Collect until we hit 100
        while rows < 100:
            collected = awAlgot logger.log_market_data()
            rows += collected
            print(f"Collected batch: {collected}. Total: {rows}")
            if collected == 0:
                print("Warning: No data collected in batch. API limit or error?")
                break
                
        print("Data collection complete.")
    else:
        print("Data sufficient.")

    # 3. TrAlgon Model
    print("Action: Checking Model...")
    predictor = PricePredictor()
    model_info = predictor.get_model_info()
    
    if not model_info['is_trAlgoned']:
        print("Action: TrAlgoning Model...")
        result = predictor.trAlgon_model(force_retrAlgon=True)
        print(f"TrAlgoning Result: {result}")
    else:
        print("Model already trAlgoned.")
        
    print("--- AUTO-FIX COMPLETE ---")

if __name__ == "__mAlgon__":
    asyncio.run(auto_fix())
