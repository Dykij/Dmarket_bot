# DMarket API v2 Authorization Specification
# Source: Official Swagger Documentation (Parsed via web_fetch)

## Headers
Correct HTTP headers for ALL signed requests:
- `X-Api-Key`: Public Key (hex string)
- `X-Sign-Date`: Timestamp (Unix seconds). Example: 1605619994.
- `X-Request-Sign`: Signature (hex string)

## Signature Construction
Formula: `Method + Path + Body + Timestamp`

### Rules:
1. **Method**: HTTP Method (GET, POST, etc.). Case sensitive? Swagger example uses "POST".
2. **Path**: Route path + HTTP query parameters.
   - Example from Swagger: `/get-item?Amount="0.25"&Limit="100"`
   - **CRITICAL:** Note the query params are INCLUDED in the signature string if present.
   - **CRITICAL:** Note the path starts with `/`.
3. **Body**: Request body string.
   - For GET requests without body: Empty string `""`.
   - For POST requests: The exact JSON string sent.
4. **Timestamp**: Same value as `X-Sign-Date`.

### Example (from Swagger):
`POST/get-item?Amount="0.25"&Limit="100"&Offset="150"&Order="desc"&1605619994`

## Specific Endpoint: /account/v1/balance
- **Method**: GET
- **Path**: `/account/v1/balance` (No query params documented for this endpoint)
- **Body**: Empty
- **Timestamp**: current unix seconds
- **String to Sign**: `GET/account/v1/balance1605619994`

## Key Management
- Secret Key used for signing must be the private key part of the Ed25519 pair.
- If Secret Key provided is 128 hex chars (64 bytes), it is likely `Seed (32 bytes) + Public Key (32 bytes)`. Use the first 32 bytes as the seed.

## Notes on 401
- `X-Sign-Date` must not be older than 2 minutes.
- `X-Api-Key` must be lowercase hex string.
