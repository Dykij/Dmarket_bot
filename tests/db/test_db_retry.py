"""
Unit tests for src.db.db_retry (v12.7).

Coverage:
- Basic retry on transient "database is locked" error
- Exponential backoff timing
- Max attempts cap (eventually re-raises)
- Non-transient errors propagate immediately (no retry)
- Decorator works on sync and async functions
- Methods on classes (preserves self)
- Default args (3 attempts, 50ms base, 500ms max)
- Custom args honored
- Total time bounded by max_attempts and max_delay
- Lock-acquired-then-released pattern (real SQLite contention)
- Operation name in logs
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.db.db_retry import _is_transient, with_db_retry  # noqa: E402


# =====================================================================
# TestIsTransient
# =====================================================================

class TestIsTransient:
    def test_operational_error_locked(self) -> None:
        assert _is_transient(sqlite3.OperationalError("database is locked")) is True

    def test_operational_error_busy(self) -> None:
        assert _is_transient(sqlite3.OperationalError("database is busy")) is True

    def test_operational_error_other(self) -> None:
        """Non-lock/busy OperationalError is NOT transient."""
        assert _is_transient(sqlite3.OperationalError("syntax error")) is False
        assert _is_transient(sqlite3.OperationalError("UNIQUE constraint failed")) is False

    def test_non_operational_error(self) -> None:
        assert _is_transient(ValueError("not a sqlite error")) is False
        assert _is_transient(RuntimeError("...")) is False

    def test_case_insensitive(self) -> None:
        """The 'locked'/'busy' check is case-insensitive."""
        assert _is_transient(sqlite3.OperationalError("DATABASE IS LOCKED")) is True
        assert _is_transient(sqlite3.OperationalError("Database Is Busy")) is True

    def test_substring_match(self) -> None:
        """Substring anywhere in the message matches."""
        assert _is_transient(sqlite3.OperationalError("attempt to write a readonly database (locked)")) is True


# =====================================================================
# TestWithDbRetrySync
# =====================================================================

class TestWithDbRetrySync:
    def test_no_retry_on_success(self) -> None:
        calls = []

        @with_db_retry()
        def good():
            calls.append(1)
            return "ok"

        result = good()
        assert result == "ok"
        assert len(calls) == 1

    def test_retry_on_locked_then_success(self) -> None:
        """First call fails with 'locked', second succeeds."""
        call_count = 0

        @with_db_retry(max_attempts=3, base_delay=0.001)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise sqlite3.OperationalError("database is locked")
            return "ok"

        result = flaky()
        assert result == "ok"
        assert call_count == 2  # 1 fail + 1 success

    def test_retry_on_busy_then_success(self) -> None:
        call_count = 0

        @with_db_retry(max_attempts=3, base_delay=0.001)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise sqlite3.OperationalError("database is busy")
            return "ok"

        result = flaky()
        assert result == "ok"
        assert call_count == 3

    def test_max_attempts_exhausted_reraises(self) -> None:
        """All attempts fail with transient error → re-raise last exception."""
        call_count = 0

        @with_db_retry(max_attempts=3, base_delay=0.001)
        def always_locked():
            nonlocal call_count
            call_count += 1
            raise sqlite3.OperationalError("database is locked")

        with pytest.raises(sqlite3.OperationalError, match="locked"):
            always_locked()
        assert call_count == 3  # tried 3 times, gave up

    def test_non_transient_propagates_immediately(self) -> None:
        """Syntax error / constraint violation is NOT retried."""
        call_count = 0

        @with_db_retry(max_attempts=3, base_delay=0.001)
        def bad():
            nonlocal call_count
            call_count += 1
            raise sqlite3.OperationalError("syntax error")

        with pytest.raises(sqlite3.OperationalError, match="syntax error"):
            bad()
        assert call_count == 1  # gave up immediately

    def test_non_sqlite_exception_propagates_immediately(self) -> None:
        call_count = 0

        @with_db_retry(max_attempts=3, base_delay=0.001)
        def bad():
            nonlocal call_count
            call_count += 1
            raise ValueError("not a sqlite error")

        with pytest.raises(ValueError, match="not a sqlite error"):
            bad()
        assert call_count == 1

    def test_exponential_backoff_timing(self) -> None:
        """3 attempts: delays should be 0.05s, 0.10s (before the 3rd)."""
        call_count = 0
        timings = []

        @with_db_retry(max_attempts=3, base_delay=0.05, max_delay=1.0)
        def always_locked():
            nonlocal call_count
            call_count += 1
            timings.append(time.time())
            raise sqlite3.OperationalError("locked")

        with pytest.raises(sqlite3.OperationalError):
            always_locked()
        assert call_count == 3
        # Delay between attempt 1 and 2 should be ~0.05s
        d1 = timings[1] - timings[0]
        assert 0.04 <= d1 <= 0.15  # 50ms ± jitter
        # Delay between attempt 2 and 3 should be ~0.10s
        d2 = timings[2] - timings[1]
        assert 0.09 <= d2 <= 0.20

    def test_max_delay_cap_respected(self) -> None:
        """Delay should not exceed max_delay even after many attempts."""
        @with_db_retry(max_attempts=10, base_delay=1.0, max_delay=0.05)
        def always_locked():
            raise sqlite3.OperationalError("locked")

        start = time.time()
        with pytest.raises(sqlite3.OperationalError):
            always_locked()
        # 9 retries × 0.05s cap = 0.45s. Plus per-try overhead. Allow
        # generous upper bound for CI jitter.
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Took {elapsed}s, expected <5s"

    def test_preserves_function_metadata(self) -> None:
        @with_db_retry()
        def my_function():
            """My docstring."""
            return 42

        assert my_function.__name__ == "my_function"
        assert "My docstring." in my_function.__doc__

    def test_preserves_self_for_methods(self) -> None:
        """A decorated method should still receive self."""
        class Counter:
            def __init__(self):
                self.n = 0
            @with_db_retry(max_attempts=2, base_delay=0.001)
            def increment(self):
                self.n += 1
                return self.n

        c = Counter()
        assert c.increment() == 1
        assert c.increment() == 2


# =====================================================================
# TestWithDbRetryAsync
# =====================================================================

class TestWithDbRetryAsync:
    @pytest.mark.asyncio
    async def test_no_retry_on_success(self) -> None:
        calls = []

        @with_db_retry()
        async def good():
            calls.append(1)
            return "ok"

        result = await good()
        assert result == "ok"
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_retry_on_locked_then_success(self) -> None:
        call_count = 0

        @with_db_retry(max_attempts=3, base_delay=0.001)
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise sqlite3.OperationalError("database is locked")
            return "ok"

        result = await flaky()
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_max_attempts_reraises(self) -> None:
        call_count = 0

        @with_db_retry(max_attempts=2, base_delay=0.001)
        async def always_locked():
            nonlocal call_count
            call_count += 1
            raise sqlite3.OperationalError("locked")

        with pytest.raises(sqlite3.OperationalError):
            await always_locked()
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_non_transient_propagates(self) -> None:
        @with_db_retry(max_attempts=3, base_delay=0.001)
        async def bad():
            raise ValueError("not sqlite")

        with pytest.raises(ValueError):
            await bad()


# =====================================================================
# TestWithDbRetryDefaults
# =====================================================================

class TestWithDbRetryDefaults:
    def test_default_max_attempts_is_3(self) -> None:
        """Verify by counting retries: 3 attempts total."""
        call_count = 0

        @with_db_retry(base_delay=0.001)
        def always_locked():
            nonlocal call_count
            call_count += 1
            raise sqlite3.OperationalError("locked")

        with pytest.raises(sqlite3.OperationalError):
            always_locked()
        assert call_count == 3  # default = 3

    def test_default_base_delay(self) -> None:
        """Default base_delay is 50ms (verified by timing)."""
        @with_db_retry(max_attempts=2)
        def always_locked():
            raise sqlite3.OperationalError("locked")

        start = time.time()
        with pytest.raises(sqlite3.OperationalError):
            always_locked()
        elapsed = time.time() - start
        # 1 retry × 50ms = ~50ms minimum, with overhead ~100ms
        assert 0.04 <= elapsed <= 1.0, f"Took {elapsed}s, expected ~0.1s"


# =====================================================================
# TestWithDbRetryRealSqliteContention
# =====================================================================

class TestWithDbRetryRealSqliteContention:
    """
    Real-world test: use the decorator on a real SQLite operation
    that's currently locked by another thread. Verify the retry
    succeeds once the lock is released.
    """

    def test_concurrent_writer_retries(self) -> None:
        """Thread A holds a write lock briefly; thread B's write is
        retried by the decorator until it succeeds."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            conn = sqlite3.connect(db_path, timeout=0.1, check_same_thread=False)
            # Set up schema
            conn.execute("CREATE TABLE kv (k TEXT PRIMARY KEY, v INTEGER)")
            conn.commit()

            # Hold a write transaction in a background thread
            lock_released = threading.Event()
            other_thread_started = threading.Event()

            def hold_lock():
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("INSERT INTO kv VALUES ('hold', 1)")
                other_thread_started.set()
                # Hold for 0.3s then commit
                time.sleep(0.3)
                conn.execute("COMMIT")
                lock_released.set()

            other = threading.Thread(target=hold_lock)
            other.start()
            other_thread_started.wait()
            time.sleep(0.05)  # ensure the other thread is in BEGIN IMMEDIATE

            # Now the decorator-protected write
            @with_db_retry(max_attempts=10, base_delay=0.05, max_delay=0.2)
            def write_via_decorator():
                conn.execute("INSERT INTO kv VALUES (?, ?)", ("from_decorator", 42))
                conn.commit()

            # This should retry until the other thread releases
            write_via_decorator()
            other.join()

            # Verify the value was written
            row = conn.execute(
                "SELECT v FROM kv WHERE k = 'from_decorator'"
            ).fetchone()
            assert row is not None
            assert row[0] == 42
        finally:
            os.unlink(db_path)


# =====================================================================
# TestWithDbRetryOperationName
# =====================================================================

class TestWithDbRetryOperationName:
    def test_custom_operation_name_in_log(self, caplog) -> None:
        """The decorator's log message should include the operation name."""
        import logging
        caplog.set_level(logging.WARNING, logger="DBRetry")

        @with_db_retry(max_attempts=2, base_delay=0.001, operation_name="my_special_op")
        def always_locked():
            raise sqlite3.OperationalError("locked")

        with pytest.raises(sqlite3.OperationalError):
            always_locked()

        # The log should mention our custom op name
        assert any("my_special_op" in r.message for r in caplog.records)

    def test_default_uses_qualname(self, caplog) -> None:
        """Without operation_name=, the function's qualname is used."""
        import logging
        caplog.set_level(logging.WARNING, logger="DBRetry")

        @with_db_retry(max_attempts=2, base_delay=0.001)
        def my_named_function():
            raise sqlite3.OperationalError("locked")

        with pytest.raises(sqlite3.OperationalError):
            my_named_function()

        assert any("my_named_function" in r.message for r in caplog.records)
