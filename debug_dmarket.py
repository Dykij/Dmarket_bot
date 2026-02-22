import os
import time
import requests
import json
import logging
from nacl.signing import SigningKey
from nacl.encoding import HexEncoder
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('IsolatedProbe')

def main():
    # 1. Load keys directly
    load_dotenv(r'D:\Dmarket_bot\.env')
    
    # Raw read to detect quotes
    try:
        with open(r'D:\Dmarket_bot\.env', 'r') as f:
            raw_content = f.read()
            if '="' in raw_content or "='" in raw_content:
                logger.warning("ALERT: Quotes detected in .env file content!")
    except:
        pass

    public_key = os.getenv("DMARKET_PUBLIC_KEY") or os.getenv("DMARKET_API_KEY")
    secret_key = os.getenv("DMARKET_SECRET_KEY")
    
    if not public_key or not secret_key:
        logger.error("Keys missing from .env")
        return

    # 2. Sanitation (The "Zero Trust" approach)
    public_key = public_key.strip().strip('"').strip("'")
    secret_key = secret_key.strip().strip('"').strip("'")

    logger.info(f"Public Key (Sanitized): {public_key}")
    logger.info(f"Secret Key (Sanitized, Len={len(secret_key)}): {secret_key[:10]}...")

    # 3. Crypto Setup
    try:
        secret_bytes = bytes.fromhex(secret_key)
        # Handle 128 hex (64 bytes) vs 64 hex (32 bytes)
        if len(secret_bytes) == 64:
            seed = secret_bytes[:32]
        else:
            seed = secret_bytes
        signing_key = SigningKey(seed)
    except Exception as e:
        logger.error(f"Crypto Init Failed: {e}")
        return

    # 4. Request Construction (Strictly per Swagger)
    method = "GET"
    path = "/account/v1/balance"
    body = ""
    timestamp = str(int(time.time()))
    
    message_str = f"{method}{path}{body}{timestamp}"
    
    # Sign
    signature_bytes = signing_key.sign(message_str.encode('utf-8')).signature
    signature_hex = signature_bytes.hex()
    
    logger.info(f"String to Sign: '{message_str}'")
    logger.info(f"Signature: {signature_hex}")
    
    # 5. Execute
    headers = {
        "X-Api-Key": public_key,
        "X-Request-Sign": signature_hex,
        "X-Sign-Date": timestamp,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    url = "https://api.dmarket.com" + path
    
    try:
        logger.info(f"Sending Probe to {url}...")
        resp = requests.get(url, headers=headers)
        
        logger.info(f"Status Code: {resp.status_code}")
        logger.info(f"Response Headers: {resp.headers}")
        logger.info(f"Response Body: {resp.text}")
        
        if resp.status_code == 200:
            data = resp.json()
            usd_cents = data.get("usd", 0)
            print(f"\n>>> SUCCESS! BALANCE: ${int(usd_cents)/100.0} <<<\n")
        else:
            print(f"\n>>> FAILURE: {resp.status_code} <<<\n")
            
    except Exception as e:
        logger.error(f"Probe Failed: {e}")

if __name__ == "__main__":
    main()
