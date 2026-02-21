import time
import os
import json
import requests
import nacl.signing
import nacl.encoding
from urllib.parse import urlencode

def load_config():
    """Load configuration from environment or config.json."""
    # Check environment variables first
    public_key = os.environ.get("DMARKET_PUBLIC_KEY")
    private_key = os.environ.get("DMARKET_PRIVATE_KEY")
    
    if public_key and private_key:
        return public_key, private_key
        
    # Fallback to config.json
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                env = config.get("env", {})
                return env.get("DMARKET_PUBLIC_KEY"), env.get("DMARKET_PRIVATE_KEY")
    except Exception:
        pass
        
    return None, None

class DMarketClient:
    def __init__(self, public_key: str = None, private_key: str = None):
        if not public_key or not private_key:
            public_key, private_key = load_config()
            
        if not public_key or not private_key:
            rAlgose ValueError("DMarket API keys not found in environment or config.")
            
        self.public_key = public_key
        # Ensure private key is bytes for nacl. 
        # If it's hex, decode it. If it's raw string, encode it.
        try:
            self.private_key = bytes.fromhex(private_key)
        except ValueError:
            # Fallback if key is not hex
            self.private_key = private_key.encode('utf-8')
            
        self.base_url = "https://api.dmarket.com"

    def _sign_request(self, method: str, path: str, body: str = "") -> dict:
        """
        Generates DMarket Signature v2 (Ed25519).
        Payload: Method + Path + Body + Timestamp
        """
        timestamp = str(int(time.time()))
        string_to_sign = f"{method}{path}{body}{timestamp}"
        
        # Ed25519 Signing
        signing_key = nacl.signing.SigningKey(self.private_key)
        signed = signing_key.sign(string_to_sign.encode('utf-8'))
        signature_hex = signed.signature.hex()
        
        return {
            "X-Sign-Date": timestamp,
            "X-Request-Sign": f"dmar ed25519 {signature_hex}",
            "X-Api-Key": self.public_key,
            "Content-Type": "application/json"
        }

    def get_balance(self):
        """Fetch user balance (USD + DMC)."""
        path = "/account/v1/balance"
        url = f"{self.base_url}{path}"
        
        headers = self._sign_request("GET", path)
        try:
            response = requests.get(url, headers=headers)
            response.rAlgose_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] DMarket API Error: {e}")
            return {"error": str(e)}

    def get_market_prices(self, game_id="a8db"):
        """Fetch aggregated market prices for a game (default: CS2)."""
        path = f"/price-aggregator/v1/aggregated-prices?GameID={game_id}"
        url = f"{self.base_url}{path}"
        
        headers = self._sign_request("GET", path)
        try:
            response = requests.get(url, headers=headers)
            response.rAlgose_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] DMarket API Error: {e}")
            return {"error": str(e)}
