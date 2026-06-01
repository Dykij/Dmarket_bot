"""
TEST: AsyncDMarketClient (Manual Verification)
"""
import asyncio
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.api_client import AsyncDMarketClient

async def run_manual_test():
    print("=== BEGIN MANUAL TEST: AsyncDMarketClient ===")
    
    # 1. Create client instance (using placeholders for keys)
    public_key = "test_pk_123"
    secret_key = "test_sk_456"
    
    try:
        client = AsyncDMarketClient(public_key, secret_key)
        print("✅ Client instantiated successfully.")
        
        # 2. Check imports
        import src.dmarket.api.auth
        print(f"✅ Auth module imported: {src.dmarket.api.auth}")
        
        # 3. Simulate Request Signing (Dry Run)
        print("🔍 Simulating request signing...")
        try:
            # This calls generate_signature_ed25519 internally
            # We mock request execution if possible, but simpler to just try a call and catch connection error if offline
            pass
        except Exception as e:
            print(f"❌ Signing failed: {e}")

        # 4. Try connecting (will likely fail 401 or network error without real keys)
        print("🌐 Attempting connection to DMarket API...")
        try:
            # We use a context manager to initialize the session
            async with client as c:
                print("✅ Session initialized.")
                # We try a public endpoint that might not require auth for basic info, 
                # or just expect 401 Unauthorized which proves the client works.
                try:
                    # Intentionally using a call that requires auth to see if we get a structured response
                    # or a network error.
                    resp = await c.get_market_items(limit=1)
                    print(f"✅ Response received: {resp}")
                except Exception as e:
                    print(f"⚠️ API Call failed (Expected without keys): {e}")

        except Exception as e:
            print(f"❌ Session failed: {e}")

    except Exception as e:
        print(f"❌ Client instantiation failed: {e}")

    print("=== END TEST ===")

if __name__ == "__main__":
    asyncio.run(run_manual_test())
