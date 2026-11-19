"""Regression tests: the SecurityAuditor logging filter must scrub secrets that
arrive through %-style log arguments (record.args), not only through the
message template.

Before the fix, `logger.error("headers=%s", {...})` printed the public key and
the signature in full: the filter only sanitized `record.msg` (the template).

All key material below is FAKE.
"""

from __future__ import annotations

import io
import logging

import pytest

from src.risk.security_auditor import SecurityAuditor

FAKE_PUB = "ab" * 32   # 64 hex  (X-Api-Key-like)
FAKE_SIG = "cd" * 64   # 128 hex (signature-like)


def _logger():
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(SecurityAuditor.as_logging_filter())
    lg = logging.getLogger(f"t.args.{id(buf)}")
    lg.handlers = [handler]
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    return lg, buf


def _record(msg, args):
    return logging.LogRecord("x", logging.ERROR, __file__, 1, msg, args, None)


class TestArgsScrubbing:
    def test_dict_argument_with_headers(self):
        lg, buf = _logger()
        lg.error("headers=%s", {"X-Api-Key": FAKE_PUB,
                                "X-Request-Sign": f"dmar ed25519 {FAKE_SIG}"})
        out = buf.getvalue()
        assert FAKE_PUB not in out
        assert FAKE_SIG not in out
        assert "headers=" in out

    def test_plain_string_argument_signature(self):
        lg, buf = _logger()
        lg.error("sign %s for %s", FAKE_SIG, "item")
        out = buf.getvalue()
        assert FAKE_SIG not in out
        assert "for item" in out

    def test_key_value_in_string_argument(self):
        lg, buf = _logger()
        lg.error("config: %s", f"api_key={'z' * 40}")
        assert "z" * 40 not in buf.getvalue()

    def test_mapping_style_args(self):
        lg, buf = _logger()
        lg.error("hdr=%(h)s id=%(i)s", {"h": f"X-Api-Key: {FAKE_PUB}", "i": 7})
        out = buf.getvalue()
        assert FAKE_PUB not in out
        assert "id=7" in out

    def test_secret_in_template_still_scrubbed(self):
        lg, buf = _logger()
        lg.error(f"X-Api-Key: {FAKE_PUB} user=%s", "bob")
        out = buf.getvalue()
        assert FAKE_PUB not in out
        assert "user=bob" in out

    def test_non_string_message_object(self):
        class Boom:
            def __str__(self):
                return f"X-Api-Key: {FAKE_PUB}"

        lg, buf = _logger()
        lg.error(Boom())
        assert FAKE_PUB not in buf.getvalue()

    def test_secret_in_args_and_traceback_together(self):
        lg, buf = _logger()
        try:
            raise RuntimeError(f"X-Api-Key: {FAKE_PUB}")
        except RuntimeError:
            lg.error("failed sig=%s", FAKE_SIG, exc_info=True)
        out = buf.getvalue()
        assert FAKE_PUB not in out
        assert FAKE_SIG not in out
        assert "failed" in out

    def test_bad_format_is_redacted_not_raised(self):
        """A malformed %-template must not crash the filter or leak the args."""
        record = _record("value=%d", (FAKE_SIG,))
        assert SecurityAuditor.as_logging_filter().filter(record) is True
        assert "REDACTED" in record.msg
        assert record.args == ()


class TestCleanRecordsUntouched:
    def test_clean_args_stay_lazy(self):
        """No secret -> the record keeps its template and args (cheap, unchanged)."""
        record = _record("price=%s item=%s", (12.5, "AK-47"))
        SecurityAuditor.as_logging_filter().filter(record)
        assert record.msg == "price=%s item=%s"
        assert record.args == (12.5, "AK-47")
        assert record.getMessage() == "price=12.5 item=AK-47"

    def test_clean_message_without_args_unchanged(self):
        record = _record("scan finished", ())
        SecurityAuditor.as_logging_filter().filter(record)
        assert record.msg == "scan finished"

    def test_percent_in_message_without_args_not_formatted(self):
        record = _record("margin 5% of 100%", ())
        SecurityAuditor.as_logging_filter().filter(record)
        assert record.getMessage() == "margin 5% of 100%"


class TestConfigureLoggingIntegration:
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

    def test_args_secret_scrubbed_through_configure_logging(self, clean_root):
        from src.utils.logging_setup import configure_logging

        buf = io.StringIO()
        configure_logging(component="test", stream=buf)
        logging.getLogger("t.args.integration").error(
            "request headers=%s", {"X-Api-Key": FAKE_PUB, "sig": FAKE_SIG}
        )
        out = buf.getvalue()
        assert "request headers=" in out
        assert FAKE_PUB not in out
        assert FAKE_SIG not in out
