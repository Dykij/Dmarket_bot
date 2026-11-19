"""Regression tests: SecurityAuditor logging filter must scrub secrets in
tracebacks (exc_info) and in the X-Api-Key header value.

All key material below is FAKE.
"""

from __future__ import annotations

import io
import logging

import pytest

from src.risk.security_auditor import SecurityAuditor

FAKE_PUB = "ab" * 32   # 64 hex  (looks like an X-Api-Key value)
FAKE_SIG = "cd" * 64   # 128 hex (looks like an ed25519 signature)


def _logger_with_filter(fmt: str = "%(message)s"):
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter(fmt))
    handler.addFilter(SecurityAuditor.as_logging_filter())
    lg = logging.getLogger(f"t.{id(buf)}")
    lg.handlers = [handler]
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    return lg, buf


class TestXApiKeyPattern:
    @pytest.mark.parametrize("text", [
        f"X-Api-Key: {FAKE_PUB}",
        f"x-api-key={FAKE_PUB}",
        str({"X-Api-Key": FAKE_PUB, "X-Sign-Date": "1763580000"}),
    ])
    def test_sanitize_redacts_public_key_header(self, text):
        out = SecurityAuditor.sanitize(text)
        assert FAKE_PUB not in out
        assert "REDACTED" in out

    def test_unrelated_hex_in_other_context_untouched(self):
        text = "itemId: 0123456789abcdef0123456789abcdef"
        assert SecurityAuditor.sanitize(text) == text


class TestTracebackScrubbing:
    def test_secret_in_exception_message_is_scrubbed(self):
        lg, buf = _logger_with_filter()
        try:
            raise RuntimeError(
                f"request failed headers={{'X-Api-Key': '{FAKE_PUB}', "
                f"'X-Request-Sign': 'dmar ed25519 {FAKE_SIG}'}}"
            )
        except RuntimeError:
            lg.error("call failed", exc_info=True)
        out = buf.getvalue()
        assert FAKE_PUB not in out
        assert FAKE_SIG not in out
        assert "call failed" in out
        assert "RuntimeError" in out          # traceback is still there, just redacted
        assert "REDACTED" in out

    def test_clean_traceback_is_left_untouched(self):
        lg, buf = _logger_with_filter()
        try:
            raise ValueError("plain failure, nothing secret")
        except ValueError:
            lg.error("oops", exc_info=True)
        out = buf.getvalue()
        assert "Traceback (most recent call last)" in out
        assert "ValueError: plain failure, nothing secret" in out
        assert "REDACTED" not in out

    def test_cached_exc_text_is_scrubbed(self):
        """A formatter that ran earlier may have cached record.exc_text."""
        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "msg", (), None)
        record.exc_text = f"Traceback...\nRuntimeError: X-Api-Key: {FAKE_PUB}"
        SecurityAuditor.as_logging_filter().filter(record)
        assert FAKE_PUB not in record.exc_text

    def test_same_filter_instance_on_two_handlers(self):
        """__main__ attaches ONE filter instance to console + rotating file."""
        shared = SecurityAuditor.as_logging_filter()
        bufs = []
        lg = logging.getLogger(f"t.two.{id(shared)}")
        lg.handlers = []
        for _ in range(2):
            buf = io.StringIO()
            h = logging.StreamHandler(buf)
            h.setFormatter(logging.Formatter("%(message)s"))
            h.addFilter(shared)
            lg.addHandler(h)
            bufs.append(buf)
        lg.setLevel(logging.DEBUG)
        lg.propagate = False
        try:
            raise RuntimeError(f"X-Api-Key: {FAKE_PUB}")
        except RuntimeError:
            lg.error("boom", exc_info=True)
        for buf in bufs:
            assert FAKE_PUB not in buf.getvalue()
            assert "boom" in buf.getvalue()


class TestConfigureLoggingIntegration:
    """control_bot entry point: configure_logging() (structlog formatter)."""

    @pytest.fixture
    def clean_root(self):
        root = logging.getLogger()
        saved_handlers, saved_level = list(root.handlers), root.level
        root.handlers = []
        yield root
        root.handlers = saved_handlers
        root.setLevel(saved_level)
        try:
            import structlog
            structlog.reset_defaults()
        except Exception:
            pass

    def test_traceback_secret_scrubbed_through_configure_logging(self, clean_root):
        from src.utils.logging_setup import configure_logging

        buf = io.StringIO()
        configure_logging(component="test", stream=buf)
        lg = logging.getLogger("t.integration")
        try:
            raise RuntimeError(f"headers: X-Api-Key: {FAKE_PUB} sign {FAKE_SIG}")
        except RuntimeError:
            lg.error("integration failure", exc_info=True)
        out = buf.getvalue()
        assert "integration failure" in out
        assert FAKE_PUB not in out
        assert FAKE_SIG not in out
