import logging
import re


class SecurityAuditor:
    """
    Brigade: Dmarket
    Role: Security Auditor
    Model Constraint: llama3.1:8b (8GB VRAM shared)
    
    Scans outputs and logs for hardcoded API keys, environment variables,
    and sensitive tokens before they are saved or broadcasted to Telegram.

    v12.9: Expanded pattern coverage for all known key formats used by
    DMarket, CSFloat, Waxpeer, Telegram, GitHub, and common
    cloud providers.
    """

    # Common patterns for sensitive keys (Gitleaks 8.x compatible patterns)
    PATTERNS = [
        # Generic key-value patterns
        re.compile(r"(?i)(?:api_key|apikey|secret|token|password|t_token|auth|private_key|access_key)"
                   r"[=:\s]+['\"]?([a-zA-Z0-9\-_/+]{16,})['\"]?"),
        # OpenAI / generic secret keys
        re.compile(r"(?i)sk-[a-zA-Z0-9]{20,}"),
        re.compile(r"(?i)pk-[a-zA-Z0-9]{20,}"),
        # JWT / Bearer tokens
        re.compile(r"(?i)Bearer\s+[a-zA-Z0-9\-\._~+\/=]{20,}"),
        # Hex-encoded Ed25519 secrets (64 hex chars = 32 bytes, or 128 hex = 64 bytes)
        re.compile(r"(?i)(?:DMARKET_SECRET_KEY|secret_key)[=:\s]+['\"]?([a-fA-F0-9]{64,128})['\"]?"),
        re.compile(r"(?i)[a-fA-F0-9]{128}"),
        # DMarket public keys
        re.compile(r"(?i)DMARKET_PUBLIC_KEY[=:\s]+['\"]?[a-fA-F0-9]{64,}['\"]?"),
        # .env references
        re.compile(r"(?i)[a-zA-Z0-9_-]+\.env"),
        # Private keys (PEM)
        re.compile(r"(?i)-----BEGIN\s+(?:RSA|OPENSSH|PGP|DSA|EC|PRIVATE)\s+KEY-----"),
        # SSH private keys (OPENSSH format)
        re.compile(r"(?i)-----BEGIN\s+OPENSSH\s+PRIVATE\s+KEY-----"),
        # GitHub tokens
        re.compile(r"(?i)(?:ghp_|gho_|ghu_|ghs_|ghr_|github_pat_)[a-zA-Z0-9_]{36,}"),
        # Slack tokens
        re.compile(r"(?i)xox[baprs]-[0-9]+-[0-9]+-[a-zA-Z0-9]+"),
        # Slack webhooks
        re.compile(r"(?i)hooks\.slack\.com/services/T[a-zA-Z0-9_]{8,}/B[a-zA-Z0-9_]{8,}/[a-zA-Z0-9_]{24,}"),
        # Telegram bot tokens
        re.compile(r"(?i)[0-9]{8,10}:[a-zA-Z0-9_-]{35,}"),
        # CSFloat / Waxpeer API keys
        re.compile(r"(?i)(?:CSFLOAT_API_KEY|WAXPEER_API_KEY)"
                   r"[=:\s]+['\"]?[a-zA-Z0-9]{16,}['\"]?"),
        # AWS keys
        re.compile(r"(?i)AKIA[0-9A-Z]{16}"),
        # Google service account keys
        re.compile(r"(?i)\"type\":\s*\"service_account\""),
        # Sentry DSN (contains project secret)
        re.compile(r"(?i)https://[a-f0-9]{32}@[a-zA-Z0-9]+\.ingest\.sentry\.io"),
        # Generic base64-encoded credentials
        re.compile(r"(?i)(?:Basic\s+)[a-zA-Z0-9+/=]{20,}"),
        # Fernet keys
        re.compile(r"(?i)[a-zA-Z0-9_-]{40,}(?:\.[a-zA-Z0-9_-]{40,})+"),
        # HashiCorp Vault tokens
        re.compile(r"(?i)hvs\.[a-zA-Z0-9_-]{36,}"),
    ]

    # Patterns indicating potential prompt injection or system prompt leakage attempts
    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"(?i)(ignore\s+all\s+previous\s+instructions|disregard\s+all)"),
        re.compile(r"(?i)(you\s+are\s+now|act\s+as\s+if)\s+(you\s+are\s+not|you\s+can\s+do\s+anything)"),
        re.compile(r"(?i)(print|show|output)\s+(your\s+)?(system\s+prompt|instructions)"),
    ]

    @classmethod
    def scan_for_leaks(cls, text: str) -> bool:
        """
        Scans the text for potential security leaks and basic prompt injections.
        Returns True if a leak or injection attempt is detected, False otherwise.
        """
        return any(pattern.search(text) for pattern in cls.PATTERNS + cls.PROMPT_INJECTION_PATTERNS)

    @classmethod
    def sanitize(cls, text: str) -> str:
        """
        Redacts detected sensitive information or blocks prompt injections.
        """
        sanitized_text = text

        for pattern in cls.PROMPT_INJECTION_PATTERNS:
            if pattern.search(text):
                return "[BLOCKED_BY_SECURITY_AUDITOR: PROMPT_INJECTION_DETECTED]"

        for pattern in cls.PATTERNS:
            # Replace the captured group or the whole match with REDACTED
            sanitized_text = pattern.sub("[REDACTED_BY_SECURITY_AUDITOR]", sanitized_text)
        return sanitized_text

    @classmethod
    def as_logging_filter(cls) -> "logging.Filter":
        """
        v12.5: Return a logging.Filter that scrubs secrets from every
        log record before it's emitted. Plug into a handler via
        `handler.addFilter(SecurityAuditor.as_logging_filter())`.

        Redaction policy:
        - If the record's message contains a known secret pattern,
          it is REPLACED with a redacted version (not blocked, so
          the line still gets emitted with timestamp + level).
        - If it contains a prompt-injection pattern, the entire
          message is replaced with [BLOCKED].
        - The original record is never destroyed — the filter only
          mutates `record.msg` / `record.args` in place.
        """
        class _SecretScrubFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                try:
                    if record.msg and isinstance(record.msg, str):
                        scrubbed = cls.sanitize(record.msg)
                        if scrubbed != record.msg:
                            record.msg = scrubbed
                            record.args = ()
                    elif record.args:
                        # msg is a template; format and check
                        try:
                            rendered = record.msg % record.args
                            scrubbed = cls.sanitize(rendered)
                            if scrubbed != rendered:
                                record.msg = scrubbed
                                record.args = ()
                        except Exception:
                            pass
                except Exception:
                    # Never let the filter break logging
                    pass
                return True

        return _SecretScrubFilter()

# ======= Example Usage =======
if __name__ == "__main__":
    test_log = "Error in connection. Using api_key = 'sk-1234567890abcdef1234567890abcdef12' for retry."
    if SecurityAuditor.scan_for_leaks(test_log):
        print("Leak detected! Sanitizing...")
        safe_log = SecurityAuditor.sanitize(test_log)
        print(f"Safe Log: {safe_log}")
