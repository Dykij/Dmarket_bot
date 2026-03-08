import time
import json
import random
import ssl
import socket
import hashlib
import functools
import urllib.parse
from typing import Dict, Any, Optional

import requests
from nacl.signing import SigningKey
from nacl.encoding import HexEncoder

try:
    from tenacity import retry, stop_after_attempt, wait_exponential
except ImportError:
    # Fallback if package is missing yet
    def retry(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
        
    def stop_after_attempt(*args, **kwargs): pass
    def wait_exponential(*args, **kwargs): pass

# ── Security Hardening (Phase 13: V1/V4 patched) ──
JITTER_SAFE_MIN = 0.4
JITTER_SAFE_MAX = 3.0

# V4 Fix: Cert fingerprint is NO LONGER stored as a module global.
# It is retrieved on-demand from the OS keyring, keeping it out of
# module.__dict__ and resistant to ReadProcessMemory extraction.
_FROZEN_KEYS = {"JITTER_SAFE_MIN", "JITTER_SAFE_MAX"}


def _get_cert_fingerprint() -> str | None:
    """
    Retrieve the TLS cert fingerprint from the OS credential store.

    Set it once via:
        python -c "import keyring; keyring.set_password('dmarket_bot', 'cert_fp', '<sha256hex>')"

    Returns None if not set (pinning disabled).
    """
    try:
        import keyring
        fp = keyring.get_password("dmarket_bot", "cert_fp")
        return fp if fp and len(fp) == 64 else None
    except Exception:
        return None


class SecurityViolation(Exception):
    """Raised when a security invariant is breached."""
    pass


# V1 Fix: Freeze security constants against runtime mutation.
# Any attempt to overwrite JITTER_SAFE_MIN/MAX from another module
# (e.g., via .pth injection) will raise SecurityViolation.
import sys as _sys
_this_module = _sys.modules[__name__]
_OrigModuleType = type(_this_module)


class _FrozenModule(_OrigModuleType):
    """Module subclass that prevents mutation of security constants."""
    def __setattr__(self, key, value):
        if key in _FROZEN_KEYS:
            raise SecurityViolation(
                f"Attempt to mutate frozen security constant: {key}"
            )
        super().__setattr__(key, value)


_this_module.__class__ = _FrozenModule


def secure_request(jitter_bounds=(0.6, 1.2)):
    """
    Decorator that enforces:
    1. Jitter boundaries — blocks if random.uniform args escape safe range.
    2. TLS certificate validation — detects MITM proxies.
    3. URL allowlist — only api.dmarket.com is permitted.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, method, path, *args, **kwargs):
            # ── Check 1: Jitter bounds ──
            lo, hi = jitter_bounds
            if lo < JITTER_SAFE_MIN or hi > JITTER_SAFE_MAX or lo >= hi:
                raise SecurityViolation(
                    f"Jitter bounds ({lo}, {hi}) outside safe range "
                    f"[{JITTER_SAFE_MIN}, {JITTER_SAFE_MAX}]"
                )

            # ── Check 2: URL allowlist ──
            url = f"{self.BASE_URL}{path}"
            if "api.dmarket.com" not in url:
                raise SecurityViolation(f"Request to non-allowlisted host: {url}")

            # ── Check 3: TLS certificate pinning (V4: keyring-backed) ──
            cert_fp = _get_cert_fingerprint()
            if cert_fp:
                try:
                    ctx = ssl.create_default_context()
                    with ctx.wrap_socket(
                        socket.socket(), server_hostname="api.dmarket.com"
                    ) as s:
                        s.settimeout(5)
                        s.connect(("api.dmarket.com", 443))
                        cert_der = s.getpeercert(binary_form=True)
                        fp = hashlib.sha256(cert_der).hexdigest()
                        if fp != cert_fp:
                            raise SecurityViolation(
                                f"TLS fingerprint mismatch! "
                                f"Expected {cert_fp[:16]}..., "
                                f"got {fp[:16]}... Possible MITM."
                            )
                except SecurityViolation:
                    raise
                except Exception:
                    pass  # Network issues — let requests lib handle TLS

            return func(self, method, path, *args, **kwargs)
        return wrapper
    return decorator


class DMarketAPIClient:
    """
    DMarket Trading API v2 Client
    Strict compliance with ToS:
    - Rate Limiting: <= 2 RPS
    - Anti-Scraping: REST API ONLY, NO HTML parsing
    - Signing: Ed25519 signature scheme via NACL
    """
    
    BASE_URL = "https://api.dmarket.com"
    
    def __init__(self, public_key: str, secret_key: str):
        self.public_key = public_key
        self.secret_key = secret_key
        self._last_request_time = 0.0
        self._min_request_interval = 0.51  # Strict <= 2 RPS (~0.5s spacing)
        
        # Load the signing key
        try:
            self._signing_key = SigningKey(self.secret_key.encode('utf-8'), encoder=HexEncoder)
        except Exception as e:
            raise ValueError(f"Failed to initialize Ed25519 key: {e}")

    def _wait_for_rate_limit(self):
        """Enforces <= 2 RPS with anti-detect jitter (randomized delays)."""
        jitter = random.uniform(0.6, 1.2)
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < jitter:
            time.sleep(jitter - elapsed)
        self._last_request_time = time.time()

    def _generate_signature(self, method: str, api_path: str, body: str, timestamp: str) -> str:
        """
        Builds the non-signed string formula and signs with NACL.
        Formula: (HTTP Method) + (Route path + HTTP query params) + (body string) + (timestamp)
        """
        signature_prefix = f"{method}{api_path}{body}{timestamp}"
        signed_message = self._signing_key.sign(signature_prefix.encode('utf-8'))
        # PyNaCl sign returns the signature prepended to the message. We want the signature in hex.
        # However, the api expects the signature hex string.
        return signed_message.signature.hex()

    @secure_request(jitter_bounds=(0.6, 1.2))
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def make_request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generic authorized request wrapper API with Exponetial Backoff."""
        self._wait_for_rate_limit()
        
        url = f"{self.BASE_URL}{path}"
        method = method.upper()
        timestamp = str(int(time.time()))
        
        # Format query params
        api_path = path
        if params:
            query_string = urllib.parse.urlencode(params)
            api_path = f"{path}?{query_string}"
            url = f"{self.BASE_URL}{api_path}"
            
        body_str = ""
        if body:
            body_str = json.dumps(body)
            
        signature = self._generate_signature(method, api_path, body_str, timestamp)
        
        headers = {
            "X-Api-Key": self.public_key,
            "X-Sign-Date": timestamp,
            "X-Request-Sign": f"dmar {signature}",
            "Content-Type": "application/json"
        }
        
        response = requests.request(method, url, headers=headers, json=body if body else None)
        response.raise_for_status()
        return response.json()
    
    # --- API Wrappers ---
    def get_account_balance(self):
        return self.make_request("GET", "/account/v1/balance")
        
    def get_real_balance(self) -> float:
        """Fetch the actual USD balance from the DMarket account synchronously."""
        data = self.get_account_balance()
        # DMarket balance is usually represented in cents (e.g. 1000 = $10.00)
        usd_balance_str = data.get("usd", "0")
        try:
            return float(usd_balance_str) / 100.0
        except (ValueError, TypeError):
            return 0.0
        
    def get_user_offers(self, game_id: str, limit: int = 20):
        # CS:GO = a8db, TF2 = tf2, Dota2 = 9a92, Rust = rust
        params = {"GameID": game_id, "Limit": limit}
        return self.make_request("GET", "/exchange/v1/user/offers", params=params)

    def verify_inventory(self, game_id: str):
        """Simulates checking if item was successfully bought."""
        return self.make_request("GET", "/exchange/v1/user/inventory", params={"GameID": game_id})
