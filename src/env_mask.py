"""
env_mask.py — Sanitizes secrets from any string before logging.

Usage:
    from src.env_mask import mask_secrets
    print(mask_secrets(f"key={some_value}"))
"""

import os
import re

# Collect all known secret patterns at import time
_SECRETS: set = set()
for _var in ("DMARKET_SECRET_KEY", "DMARKET_PUBLIC_KEY"):
    _val = os.environ.get(_var, "")
    if len(_val) >= 8:
        _SECRETS.add(_val)


def mask_secrets(text: str) -> str:
    """Replace any occurrence of known secrets with [REDACTED]."""
    for secret in _SECRETS:
        if secret in text:
            masked = f"{secret[:4]}...{secret[-4:]}"
            text = text.replace(secret, f"[REDACTED:{masked}]")
    # Also catch hex-like 64+ char strings that look like keys
    text = re.sub(
        r'(?<=["\' =])[0-9a-fA-F]{64,}(?=["\' ,\n])',
        "[REDACTED:hex_key]",
        text,
    )
    return text
