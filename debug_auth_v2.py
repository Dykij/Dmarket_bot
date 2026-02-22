import os
import time
import requests
import json
import logging
from nacl.signing import SigningKey
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('AuthDebugV2')

def test_request(name, method, path, body, public_key, secret_key, headers_extra={}):
    try:
        timestamp = str(int(time.time()))
        message = f"{method}{path}{body}{timestamp}"
        
        # Decode secret
        secret_bytes = bytes.fromhex(secret_key)
        seed = secret_bytes[:32] if len(secret_bytes) == 64 else secret_bytes
        
        signing_key = SigningKey(seed)
        signature = signing_key.sign(message.encode('utf-8')).signature.hex()
        
        headers = {
            "X-Api-Key": public_key,
            "X-Sign": signature,
            "X-Timestamp": timestamp
        }
        headers.update(headers_extra)
        
        url = "https://api.dmarket.com" + path
        logger.info(f"--- TEST: {name} ---")
        logger.info(f"URL: {url}")
        logger.info(f"Sign String: {message}")
        logger.info(f"Headers: {json.dumps(headers, indent=2)}")
        
        if method == "GET":
            resp = requests.get(url, headers=headers)
        else:
            resp = requests.post(url, headers=headers, data=body)
            
        logger.info(f"Response: {resp.status_code} {resp.text[:200]}")
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Error in {name}: {e}")
        return False

def main():
    load_dotenv()
    pub = os.getenv("DMARKET_PUBLIC_KEY") or os.getenv("DMARKET_API_KEY")
    sec = os.getenv("DMARKET_SECRET_KEY")
    
    if not pub or not sec:
        logger.error("Missing keys")
        return

    pub = pub.strip().strip('"')
    sec = sec.strip().strip('"')

    # Test 1: Standard Balance
    test_request("Balance_Standard", "GET", "/account/v1/balance", "", pub, sec)
    
    # Test 2: Balance with Trailing Slash
    test_request("Balance_Slash", "GET", "/account/v1/balance/", "", pub, sec)
    
    # Test 3: Market Items (Signed)
    # Note: query params are NOT part of sign string usually?
    # Let's try WITHOUT query params in sign string, but WITH in URL?
    # Or let's try a POST request if possible? No, GET is safer.
    
    # Test 4: User (Self)
    test_request("User_Self", "GET", "/account/v1/user", "", pub, sec)

if __name__ == "__main__":
    main()
