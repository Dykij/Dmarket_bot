from nacl.signing import SigningKey
from nacl.encoding import HexEncoder
import os
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('KeyCheck')

load_dotenv()

pub_hex = os.getenv("DMARKET_PUBLIC_KEY").strip().strip('"')
sec_hex = os.getenv("DMARKET_SECRET_KEY").strip().strip('"')

# Decode Secret Key
sec_bytes = bytes.fromhex(sec_hex)
seed = sec_bytes[:32]

# Derive Public Key from Seed
signing_key = SigningKey(seed)
verify_key = signing_key.verify_key
verify_key_hex = verify_key.encode(encoder=HexEncoder).decode('utf-8')

logger.info(f"Provided Public Key: {pub_hex}")
logger.info(f"Derived Public Key:  {verify_key_hex}")

if pub_hex == verify_key_hex:
    logger.info("MATCH! The keys are a valid pair.")
else:
    logger.error("MISMATCH! The public key in .env does not belong to the secret key.")
