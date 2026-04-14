import asyncio
import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()
from src.api.dmarket_api_client import DMarketAPIClient
from src.api.csfloat_oracle import CSFloatOracle

async def test_dmarket_isolated():
    print('[1] Testing DMarket Connection...')
    pub = os.getenv('DMARKET_PUBLIC_KEY')
    sec = os.getenv('DMARKET_SECRET_KEY')
    dm_api = DMarketAPIClient(pub, sec)
    try:
        res = await dm_api.get_market_items_v2('a8db', limit=1)
        objects = res.get("objects", [])
        print(f'   -> Success: {len(objects)} objects found.')
    except Exception as e:
        print(f'   -> DMarket Error Occurred:')
        print(f'      Type: {type(e).__name__}')
        print(f'      Message: {str(e)}')
    finally:
        await dm_api.close()

async def test_csfloat_isolated():
    print('\n[2] Testing CSFloat Connection...')
    cs_api = CSFloatOracle(os.getenv('CSFLOAT_API_KEY'))
    try:
        price = await cs_api.get_item_price('AK-47 | Redline (Field-Tested)')
        print(f'   -> Success: CSFloat Price is ${price}')
    except Exception as e:
        print(f'   -> CSFloat Error Occurred:')
        print(f'      Type: {type(e).__name__}')
        print(f'      Message: {str(e)}')
    finally:
        await cs_api.close()

async def main():
    await test_dmarket_isolated()
    await test_csfloat_isolated()

asyncio.run(main())
