# DMarket API v2 Migration Guide (2026)

## Overview
DMarket has transitioned to **Signature v2** using Ed25519 for all critical endpoints (Trading, Withdrawals, Balance). The old Hex/SHA256 method (v1) is deprecated and may return `401 Unauthorized` or `400 Bad Request`.

## Signature v2 Specification

### 1. Algorithm
- **Type:** Ed25519 (Edwards-curve Digital Signature Algorithm).
- **Library:** `nacl.signing.SigningKey` (Python `pynacl` or similar).

### 2. Payload Construction
The string to sign is constructed by concatenating:
`{Method}{Path}{Body}{Timestamp}`

- **Method:** HTTP verb (e.g., `GET`, `POST`).
- **Path:** Full path including query parameters (e.g., `/exchange/v1/offers-by-title?Title=AK-47&Limit=10`).
- **Body:** JSON string of the request body (empty string `""` if no body).
- **Timestamp:** Current Unix timestamp (seconds).

### 3. Header Requirements
- `X-Api-Key`: Your Public Key (Hex encoded).
- `X-Sign-Date`: The timestamp used in the signature.
- `X-Request-Sign`: The generated signature.
    - **Format:** `dmar ed25519 {signature_hex}`
    - **Note:** The signature itself must be hex-encoded, then prefixed with `dmar ed25519 `.

### 4. Python Example (Updated for 2026)
```python
import time
import requests
from nacl.signing import SigningKey
from nacl.encoding import HexEncoder

def generate_signature(secret_key_hex, method, path, body="", timestamp=None):
    if timestamp is None:
        timestamp = str(int(time.time()))
    
    # Payload
    string_to_sign = f"{method}{path}{body}{timestamp}"
    
    # Signing
    signing_key = SigningKey(secret_key_hex, encoder=HexEncoder)
    signed = signing_key.sign(string_to_sign.encode('utf-8'))
    signature_hex = signed.signature.hex()
    
    return f"dmar ed25519 {signature_hex}", timestamp

# Usage
api_key = "YOUR_PUBLIC_KEY"
secret_key = "YOUR_SECRET_KEY"
headers = {
    "X-Api-Key": api_key,
    "Content-Type": "application/json"
}
signature, timestamp = generate_signature(secret_key, "GET", "/account/v1/balance")
headers["X-Sign-Date"] = timestamp
headers["X-Request-Sign"] = signature

response = requests.get("https://api.dmarket.com/account/v1/balance", headers=headers)
print(response.json())
```
