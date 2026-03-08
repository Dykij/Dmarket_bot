import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from src.Algo.price_predictor import PricePredictor
    from src.dmarket.market_data_logger import MarketDataLoggerConfig
    
    # 1. Check Model Status
    print("--- DIAGNOSTICS START ---")
    predictor = PricePredictor()
    model_info = predictor.get_model_info()
    print(f"MODEL_TRAlgoNED: {model_info['is_trained']}")
    print(f"KNOWN_ITEMS: {model_info.get('known_items_count', 0)}")

    # 2. Check Data Status
    config = MarketDataLoggerConfig()
    data_path = Path(config.output_path)
    rows = 0
    
    if data_path.exists():
        try:
            with open(data_path, encoding='utf-8') as f:
                rows = sum(1 for _ in f) - 1
        except Exception:
            rows = 0
            
    print(f"DATA_ROWS: {rows}")
    print(f"DATA_PATH: {data_path}")

    # 3. Action Logic (Self-Correction)
    if not model_info['is_trained']:
        if rows >= 100:
            print("ACTION: TRAlgoNING_MODEL...")
            try:
                result = predictor.train_model()
                print(f"TRAlgoNING_RESULT: {result}")
            except Exception as e:
                print(f"TRAlgoNING_ERROR: {e}")
        else:
            print("ACTION: NEED_DATA_COLLECTION")
            print(f"MISSING_ROWS: {100 - rows}")
    else:
        print("ACTION: MODEL_OK")

    print("--- DIAGNOSTICS END ---")

except Exception as e:
    print(f"CRITICAL_ERROR: {e}")
