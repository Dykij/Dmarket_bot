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
        # DMarket request header carrying the public key (X-Api-Key: <64 hex>);
        # the generic pattern above misses it because of the hyphens.
        re.compile(r"(?i)X-Api-Key['\"]?\s*[:=]\s*['\"]?[a-fA-F0-9]{32,}['\"]?"),
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
        - Tracebacks (`exc_info` / cached `exc_text`) are scrubbed too:
          if the rendered traceback contains a secret, the scrubbed text is
          appended to the message and `exc_info` is dropped, so every
          formatter (stdlib, structlog, JSON) sees only the redacted text.
        """
        class _SecretScrubFilter(logging.Filter):
            @staticmethod
            def _scrub_traceback(record: logging.LogRecord) -> None:
                try:
                    if record.exc_text:
                        cached = cls.sanitize(record.exc_text)
                        if cached != record.exc_text:
                            record.exc_text = cached
                    if record.exc_info and record.exc_info[0] is not None:
                        tb_text = logging.Formatter().formatException(record.exc_info)
                        scrubbed_tb = cls.sanitize(tb_text)
                        if scrubbed_tb != tb_text:
                            record.msg = f"{record.getMessage()}\n{scrubbed_tb}"
                            record.args = ()
                            record.exc_info = None
                            record.exc_text = None
                except Exception:
                    # Fail-closed: never emit a traceback we could not scrub.
                    record.msg = f"{record.msg} [REDACTED - traceback scrub error]"
                    record.args = ()
                    record.exc_info = None
                    record.exc_text = None

            def filter(self, record: logging.LogRecord) -> bool:
                try:
                    # Scrub the RENDERED message (template + %-args), not just the
                    # template: secrets usually arrive through the args, e.g.
                    # logger.error("headers=%s", headers). A record without a
                    # secret is left untouched (template and args stay lazy).
                    try:
                        rendered = record.getMessage()
                    except Exception:
                        # P1-3: Fail-closed — malformed template/args: never emit the raw args
                        record.msg = "[REDACTED - scrub filter error]"
                        record.args = ()
                    else:
                        scrubbed = cls.sanitize(rendered)
                        if scrubbed != rendered:
                            record.msg = scrubbed
                            record.args = ()
                except Exception:
                    # P1-3: Fail-closed — redact rather than risk leaking secrets
                    record.msg = "[REDACTED - scrub filter error]"
                    record.args = ()
                self._scrub_traceback(record)
                return True

        return _SecretScrubFilter()

# ======= Example Usage =======
if __name__ == "__main__":
    test_log = "Error in connection. Using api_key = 'sk-1234567890abcdef1234567890abcdef12' for retry."
    if SecurityAuditor.scan_for_leaks(test_log):
        print("Leak detected! Sanitizing...")
        safe_log = SecurityAuditor.sanitize(test_log)
        print(f"Safe Log: {safe_log}")
