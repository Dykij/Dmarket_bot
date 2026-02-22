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
logger = logging.getLogger('AuthDebug')

def main():
    load_dotenv()
    
    public_key = os.getenv("DMARKET_PUBLIC_KEY") or os.getenv("DMARKET_API_KEY")
    secret_key = os.getenv("DMARKET_SECRET_KEY")
    
    if not public_key or not secret_key:
        logger.error("Keys missing from .env")
        return

    # Clean keys
    public_key = public_key.strip().strip('"')
    secret_key = secret_key.strip().strip('"')

    logger.info(f"Using Public Key: {public_key[:6]}...{public_key[-4:]}")
    logger.info(f"Using Secret Key: {secret_key[:6]}...{secret_key[-4:]} (Len: {len(secret_key)})")

    # Construct request
    method = "GET"
    path = "/account/v1/balance"
    body = ""
    timestamp = str(int(time.time()))
    
    # Sign
    message = f"{method}{path}{body}{timestamp}"
    logger.info(f"Signing Message: {message}")
    
    try:
        # Decode secret key (assuming hex seed 32 bytes or keypair 64 bytes)
        secret_bytes = bytes.fromhex(secret_key)
        
        if len(secret_bytes) == 64:
             # Ed25519 seed is first 32 bytes usually
             seed = secret_bytes[:32]
        elif len(secret_bytes) == 32:
             seed = secret_bytes
        else:
             logger.error(f"Invalid Secret Key Length: {len(secret_bytes)} bytes")
             return

        signing_key = SigningKey(seed)
        signature_bytes = signing_key.sign(message.encode('utf-8')).signature
        signature = signature_bytes.hex()
        
        logger.info(f"Signature: {signature}")
        
        # Send Request
        headers = {
            "X-Api-Key": public_key,
            "X-Sign": signature,
            "X-Timestamp": timestamp,
            "Content-Type": "application/json"
        }
        
        url = "https://api.dmarket.com" + path
        logger.info(f"Sending request to {url}")
        
        resp = requests.get(url, headers=headers)
        
        if resp.status_code == 200:
            logger.info(f"SUCCESS! Response: {resp.text}")
        else:
            logger.error(f"FAILED: {resp.status_code} - {resp.text}")
            logger.error(f"Sent Headers: {json.dumps(headers, indent=2)}")

    except Exception as e:
        logger.error(f"Exception: {e}")

if __name__ == "__main__":
    main()
