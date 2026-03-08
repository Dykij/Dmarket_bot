import os
from nacl.signing import SigningKey
from datetime import datetime, timezone
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

class DMarketAuth:
    def __init__(self):
        self.public_key = os.getenv("DMARKET_PUBLIC_KEY", "").strip().strip('\'"')
        self.secret_key = os.getenv("DMARKET_SECRET_KEY", "").strip().strip('\'"')
            
        if not self.public_key or not self.secret_key:
            print("[WARNING] DMARKET API Keys not found in .env!")

    def generate_headers(self, method: str, path: str, body: str = "") -> dict:
        if not self.public_key or not self.secret_key:
            return {}

        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        string_to_sign = method + path + body + timestamp
        
        try:
            # If the key is 128 chars (concatenated pair), take only the first 64 chars (32-byte seed)
            clean_secret = self.secret_key[:64] if len(self.secret_key) == 128 else self.secret_key
            secret_bytes = bytes.fromhex(clean_secret)
            sign_key = SigningKey(secret_bytes)
            signature = sign_key.sign(string_to_sign.encode('utf-8')).signature.hex()
        except ValueError:
            print("[Error] Secret Key is not a valid hexadecimal string. Cannot sign request.")
            return {}
        except Exception as e:
            print(f"[Error] Cryptographic signing failed: {e}")
            return {}

        return {
            "X-Api-Key": self.public_key,
            "X-Request-Sign": f"dmar ed25519 {signature}",
            "X-Sign-Date": timestamp,
            "Content-Type": "application/json"
        }
