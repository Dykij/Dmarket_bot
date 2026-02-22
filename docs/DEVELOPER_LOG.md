# Developer Log - Lessons Learned

## Case #1: The 401 Header Fallacy
**Date:** 2026-02-21
**Incident:** Persistent 401 Unauthorized errors despite valid cryptography and synchronized time.
**Root Cause:**
1.  **Dirty Inputs:** The Secret Key in `.env` might contain invisible whitespace/newlines.
    *   *Fix:* Always use `.trim()` on sensitive credential strings before decoding.
2.  **Header Pedantry:** DMarket API v2 is strictly typed regarding headers.
    *   `X-Sign` vs `X-Request-Sign`: Documentation matters.
    *   `X-Timestamp` vs `X-Sign-Date`: Documentation matters.
    *   `Content-Type`: Required even for GET requests by some Gateways/WAFs.
3.  **Blame Shift:** The team incorrectly blamed the user (Email confirmation, IP) instead of rigorously auditing the HTTP packet structure against the raw Swagger spec.

**Resolution:**
- Enforce `trim()` on all keys.
- Adhere strictly to `X-Request-Sign` and `X-Sign-Date`.
- Include `Content-Type: application/json` and `Accept: application/json` explicitly.
- **Philosophy:** Code is guilty until proven innocent against the spec.

## Case #2: Official Spec Alignment
**Date:** 2026-02-21
**Spec Version:** v1.1.0 (Parsed from Swagger)
**Key Requirement:** `X-Api-Key` MUST be a **hex string in lowercase**.
**Action:** Implemented `.to_lowercase()` in Rust network layer to ensure compliance regardless of input format.
**Status:** Code is now 100% compliant with Swagger v1.1.0 regarding Headers, Path, and Auth.
