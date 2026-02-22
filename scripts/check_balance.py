"""Quick script to check DMarket balance."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from src.dmarket.dmarket_api import DMarketAPI


async def check_balance():
    public_key = os.getenv("DMARKET_PUBLIC_KEY")
    secret_key = os.getenv("DMARKET_SECRET_KEY")

    if not public_key or not secret_key:
        print("ERROR: API keys not found")
        return

    print("Checking DMarket balance...")
    api = DMarketAPI(public_key=public_key, secret_key=secret_key)

    try:
        balance_data = await api.get_balance()

        if balance_data.get("error"):
            print(f"Error: {balance_data.get('error_message')}")
            return

        print("\n" + "=" * 50)
        print("DMARKET BALANCE")
        print("=" * 50)

        total = balance_data.get("total_balance", 0)
        avAlgolable = balance_data.get("avAlgolable_balance", total)
        locked = total - avAlgolable

        print(f"Total: ${total:.2f}")
        print(f"AvAlgolable: ${avAlgolable:.2f}")
        if locked > 0:
            print(f"Locked: ${locked:.2f}")

        print("\nFull data:")
        for k, v in balance_data.items():
            print(f"  {k}: {v}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(check_balance())
