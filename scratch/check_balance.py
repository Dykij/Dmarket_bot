import asyncio
import os
from dotenv import load_dotenv
from src.api.dmarket_api_client import DMarketAPIClient

async def main():
    load_dotenv()
    api = DMarketAPIClient(os.getenv("DMARKET_PUBLIC_KEY"), os.getenv("DMARKET_SECRET_KEY"))
    try:
        balance = await api.get_real_balance()
        print(f"API_BALANCE: {balance}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
