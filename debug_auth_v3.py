import os
import time
import requests
import json
import logging
import binascii
from nacl.signing import SigningKey
from nacl.encoding import HexEncoder
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('AuthDebugV3')

def main():
    load_dotenv()
    
    # Try different key names
    public_key = os.getenv("DMARKET_PUBLIC_KEY") or os.getenv("DMARKET_API_KEY")
    secret_key = os.getenv("DMARKET_SECRET_KEY")
    
    if not public_key or not secret_key:
        logger.error("Keys missing from .env")
        return

    # Clean keys (remove quotes, whitespace)
    public_key = public_key.strip().strip('"')
    secret_key = secret_key.strip().strip('"')

    logger.info(f"Public Key: {public_key}")
    logger.info(f"Secret Key (Len: {len(secret_key)}): {secret_key[:10]}...")

    # Validate Hex
    try:
        secret_bytes = bytes.fromhex(secret_key)
        logger.info(f"Secret Key Hex Decoded Length: {len(secret_bytes)} bytes")
    except Exception as e:
        logger.error(f"Secret Key is NOT valid hex: {e}")
        return

    # Ed25519 Seed Logic
    # DMarket Secret Key is usually 128 hex chars = 64 bytes.
    # The first 32 bytes are the SEED. The last 32 bytes are the PUBLIC KEY.
    if len(secret_bytes) == 64:
        seed = secret_bytes[:32]
        logger.info("Using first 32 bytes as seed.")
    elif len(secret_bytes) == 32:
        seed = secret_bytes
        logger.info("Using 32 bytes as seed directly.")
    else:
        logger.error(f"Invalid binary length: {len(secret_bytes)}")
        return

    signing_key = SigningKey(seed)
    
    # Construct Message
    method = "GET"
    path = "/account/v1/balance"
    body = ""
    timestamp = str(int(time.time()))
    
    message_str = f"{method}{path}{body}{timestamp}"
    message_bytes = message_str.encode('utf-8')
    
    logger.info(f"--- SIGNATURE SIMULATION ---")
    logger.info(f"Method: {method}")
    logger.info(f"Path: {path}")
    logger.info(f"Body: '{body}'")
    logger.info(f"Timestamp: {timestamp}")
    logger.info(f"Raw String: '{message_str}'")
    
    # Sign
    signature_bytes = signing_key.sign(message_bytes).signature
    signature_hex = signature_bytes.hex()
    
    logger.info(f"Generated Signature: {signature_hex}")
    
    # Verify Public Key Match?
    # verify_key = signing_key.verify_key
    # verify_key_hex = verify_key.encode(encoder=HexEncoder).decode('utf-8')
    # logger.info(f"Derived Public Key from Secret: {verify_key_hex}")
    # logger.info(f"Provided Public Key in .env:   {public_key}")
    
    # if verify_key_hex != public_key:
    #      logger.warning("WARNING: Derived Public Key does NOT match .env Public Key! You might be using the wrong pair.")

    # Send Request
    headers = {
        "X-Api-Key": public_key,
        "X-Sign": signature_hex,
        "X-Timestamp": timestamp,
        "Content-Type": "application/json"
    }
    
    url = "https://api.dmarket.com" + path
    logger.info(f"Sending request to {url}")
    
    try:
        resp = requests.get(url, headers=headers)
        logger.info(f"Response Status: {resp.status_code}")
        logger.info(f"Response Body: {resp.text}")
    except Exception as e:
        logger.error(f"Request failed: {e}")

if __name__ == "__main__":
    main()
