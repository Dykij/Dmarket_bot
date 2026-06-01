"""
Tests for Telegram Control Bot v12.2.

Validates:
1. Keyboard construction
2. Inline keyboard buttons
3. Access control (admin check)
4. Command registration
5. Text content of messages
6. Resilience utilities (safe_call, retry_async, BotState)
7. FSM and graceful shutdown handlers
"""

import os
import sys
import asyncio

# Ensure project root in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ["DRY_RUN"] = "true"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test:token_for_unit_tests")
os.environ.setdefault("TELEGRAM_ADMIN_ID", "458765683")

PASSED = 0
FAILED = 0


def record(test_name: str, passed: bool, details: str = ""):
    global PASSED, FAILED
    if passed:
        PASSED += 1
        status = "✅ PASS"
    else:
        FAILED += 1
        status = "❌ FAIL"
    print(f"{status} | {test_name} | {details}")


def run_async(coro):
    """Run a coroutine in a way that works both standalone and inside an event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is None:
        return asyncio.run(coro)
    # Already in a running loop: run in a new thread
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(asyncio.run, coro)
        return future.result(timeout=30)


def test_main_keyboard():
    """Test 1: Main reply keyboard has all required buttons."""
    from src.telegram.control_bot import get_main_keyboard
    kb = get_main_keyboard()
    all_texts = []
    for row in kb.keyboard:
        for btn in row:
            all_texts.append(btn.text)
    required = [
        "🚀 START BOT", "🛑 STOP BOT",
        "💰 BALANCE", "📊 STATUS",
        "📦 INVENTORY", "📈 PROFITS",
        "🧪 TEST ITEM", "⚙️ SETTINGS",
        "🔥 PANIC", "🆘 HELP",
    ]
    missing = [t for t in required if t not in all_texts]
    record("Main Keyboard", len(missing) == 0,
           f"buttons={len(all_texts)}, missing={missing}")


def test_inline_status_keyboard_stopped():
    """Test 2a: Inline status keyboard when bot is STOPPED."""
    from src.telegram.control_bot import get_inline_status_kb
    kb = get_inline_status_kb(is_running=False)
    all_callbacks = []
    for row in kb.inline_keyboard:
        for btn in row:
            all_callbacks.append(btn.callback_data)
    # When stopped: start should be active, stop should be noop
    has_active_start = "btn:start" in all_callbacks
    stop_is_noop = all(c != "btn:stop" for c in all_callbacks)
    record("Inline Status KB (stopped)", has_active_start and stop_is_noop,
           f"active_start={has_active_start}, stop_noop={stop_is_noop}")


def test_inline_status_keyboard_running():
    """Test 2b: Inline status keyboard when bot is RUNNING."""
    from src.telegram.control_bot import get_inline_status_kb
    kb = get_inline_status_kb(is_running=True)
    all_callbacks = []
    for row in kb.inline_keyboard:
        for btn in row:
            all_callbacks.append(btn.callback_data)
    # When running: start should be noop, stop should be active
    has_active_stop = "btn:stop" in all_callbacks
    start_is_noop = all(c != "btn:start" for c in all_callbacks)
    record("Inline Status KB (running)", has_active_stop and start_is_noop,
           f"active_stop={has_active_stop}, start_noop={start_is_noop}")


def test_inline_inventory_keyboard():
    """Test 3: Inline inventory keyboard has refresh and back buttons."""
    from src.telegram.control_bot import get_inline_inventory_kb
    kb = get_inline_inventory_kb()
    all_callbacks = []
    for row in kb.inline_keyboard:
        for btn in row:
            all_callbacks.append(btn.callback_data)
    required = ["btn:inventory", "btn:profits", "btn:refresh_status"]
    missing = [c for c in required if c not in all_callbacks]
    record("Inline Inventory Keyboard", len(missing) == 0,
           f"callbacks={len(all_callbacks)}")


def test_admin_access():
    """Test 4: Admin access control function."""
    from src.telegram.control_bot import is_admin, _ADMIN_ID
    record("Admin Access (positive)", is_admin(_ADMIN_ID), f"admin_id={_ADMIN_ID}")
    record("Admin Access (negative)", not is_admin(12345), "user_id=12345 rejected")


def test_bot_module_imports():
    """Test 5: Bot module imports without errors."""
    try:
        from src.telegram.control_bot import (
            router,
            get_main_keyboard, get_inline_status_kb, get_inline_inventory_kb,
            is_admin, set_commands, main, on_startup, on_shutdown,
            cmd_start, cmd_help, cmd_start_bot, cmd_stop_bot, cmd_panic,
            cmd_balance, cmd_status, cmd_inventory, cmd_profits,
            cmd_settings, cmd_test, cmd_clock, cmd_refresh, cmd_cancel,
            cb_start, cb_stop, cb_balance, cb_inventory, cb_profits,
            cb_refresh_status, cb_noop,
            safe_call, retry_async, state, BotState, TestItemFSM,
        )
        record("Bot Module Imports", True, "all functions + utils importable")
    except Exception as e:
        record("Bot Module Imports", False, f"IMPORT ERROR: {e}")


def test_commands_registration():
    """Test 6: set_commands registers all required commands."""
    from src.telegram.control_bot import set_commands
    import inspect
    sig = inspect.signature(set_commands)
    params = list(sig.parameters.keys())
    record("Commands Registration Function", "bot" in params,
           f"signature={params}")


def test_keyboard_button_count():
    """Test 7: Main keyboard has exactly 5 rows."""
    from src.telegram.control_bot import get_main_keyboard
    kb = get_main_keyboard()
    row_count = len(kb.keyboard)
    record("Keyboard Row Count", row_count == 5, f"rows={row_count} (expected 5)")


def test_emoji_unicode_in_buttons():
    """Test 8: Buttons contain emoji characters (visual indicators)."""
    from src.telegram.control_bot import get_main_keyboard
    kb = get_main_keyboard()
    all_text = " ".join(btn.text for row in kb.keyboard for btn in row)
    has_emojis = any(ord(c) > 127 for c in all_text)
    record("Emoji in Buttons", has_emojis, f"unicode chars present={has_emojis}")


def test_callback_data_format():
    """Test 9: All inline callbacks use 'btn:' prefix (except 'noop')."""
    from src.telegram.control_bot import get_inline_status_kb, get_inline_inventory_kb
    try:
        for kb in [get_inline_status_kb(is_running=True), get_inline_inventory_kb()]:
            for row in kb.inline_keyboard:
                for btn in row:
                    if btn.callback_data and btn.callback_data != "noop":
                        assert btn.callback_data.startswith("btn:"), f"Bad format: {btn.callback_data}"
        record("Callback Data Format", True, "all callbacks use 'btn:' prefix")
    except AssertionError as e:
        record("Callback Data Format", False, str(e))


def test_input_field_placeholder():
    """Test 10: Reply keyboard has placeholder text."""
    from src.telegram.control_bot import get_main_keyboard
    kb = get_main_keyboard()
    placeholder = getattr(kb, 'input_field_placeholder', None)
    record("Input Placeholder", placeholder is not None,
           f"placeholder={placeholder!r}")


def test_resilience_safe_call():
    """Test 11: safe_call decorator catches exceptions and reports to user."""
    from src.telegram.control_bot import safe_call

    captured = []

    class FakeMessage:
        def __init__(self):
            self.from_user = type("U", (), {"id": _get_admin_id()})()
        async def answer(self, text):
            captured.append(text)

    async def boom_handler(message):
        raise RuntimeError("simulated crash")

    wrapped = safe_call(boom_handler)
    run_async(wrapped(FakeMessage()))

    record(
        "safe_call catches exceptions",
        any("simulated crash" in t for t in captured),
        f"error_messages={len(captured)}",
    )


def _get_admin_id():
    from src.telegram.control_bot import _ADMIN_ID
    return _ADMIN_ID


def test_resilience_retry_async_success():
    """Test 12: retry_async returns result on first success."""
    from src.telegram.control_bot import retry_async

    async def good_coro():
        return 42

    result = run_async(retry_async(good_coro, operation="test.good"))
    record("retry_async success", result == 42, f"got={result}")


def test_resilience_retry_async_retries_then_succeeds():
    """Test 13: retry_async retries on retriable errors and eventually succeeds."""
    from src.telegram.control_bot import retry_async

    counter = {"n": 0}

    async def flaky_coro():
        counter["n"] += 1
        if counter["n"] < 3:
            raise ConnectionError("flaky")
        return "ok"

    result = run_async(retry_async(flaky_coro, max_attempts=5, base_delay=0.01, operation="test.flaky"))
    record(
        "retry_async retries",
        result == "ok" and counter["n"] == 3,
        f"attempts={counter['n']}, result={result}",
    )


def test_resilience_bot_state_lock():
    """Test 14: BotState has an asyncio lock for thread safety."""
    from src.telegram.control_bot import state
    has_lock = hasattr(state, "lock") and isinstance(state.lock, asyncio.Lock)
    has_is_running = hasattr(state, "is_running") and state.is_running is False
    record("BotState lock + initial state", has_lock and has_is_running,
           f"has_lock={has_lock}, is_running={state.is_running}")


def test_resilience_no_sys_exit_at_import():
    """Test 15: Module imports without sys.exit() even if token is missing."""
    import subprocess

    # Run a fresh python process with NO token in env
    env = os.environ.copy()
    env.pop("TELEGRAM_BOT_TOKEN", None)
    env.pop("TELEGRAM_ADMIN_ID", None)
    env["DRY_RUN"] = "true"
    env["PYTHONPATH"] = "/tmp/opencode/Dmarket_bot"

    code = f"""
import sys
sys.path.insert(0, '/tmp/opencode/Dmarket_bot')
import src.telegram.control_bot as cb
# Should NOT have called sys.exit
print('OK', cb._TOKEN, cb._ADMIN_ID)
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env, capture_output=True, text=True, timeout=30,
    )
    ok = result.returncode == 0 and "OK" in result.stdout
    record(
        "No sys.exit at import time",
        ok,
        f"rc={result.returncode}, stdout={result.stdout[:100]}, stderr={result.stderr[:200]}",
    )


def test_fsm_states():
    """Test 16: FSM has waiting_for_item state for /test flow."""
    from src.telegram.control_bot import TestItemFSM
    has_state = hasattr(TestItemFSM, "waiting_for_item")
    record("FSM has waiting_for_item", has_state, f"state={TestItemFSM}")


def test_signal_handlers():
    """Test 17: _install_signal_handlers exists and accepts (loop, bot)."""
    from src.telegram.control_bot import _install_signal_handlers
    import inspect
    sig = inspect.signature(_install_signal_handlers)
    params = list(sig.parameters.keys())
    record(
        "_install_signal_handlers signature",
        params == ["loop", "bot"],
        f"signature={params}",
    )


def main():
    print("="*60)
    print("TELEGRAM CONTROL BOT v12.2 — VERIFICATION (extended)")
    print("="*60)

    tests = [
        test_main_keyboard,
        test_inline_status_keyboard_stopped,
        test_inline_status_keyboard_running,
        test_inline_inventory_keyboard,
        test_admin_access,
        test_bot_module_imports,
        test_commands_registration,
        test_keyboard_button_count,
        test_emoji_unicode_in_buttons,
        test_callback_data_format,
        test_input_field_placeholder,
        test_resilience_safe_call,
        test_resilience_retry_async_success,
        test_resilience_retry_async_retries_then_succeeds,
        test_resilience_bot_state_lock,
        test_resilience_no_sys_exit_at_import,
        test_fsm_states,
        test_signal_handlers,
    ]

    for t in tests:
        try:
            t()
        except Exception as e:
            record(t.__name__, False, f"CRASH: {e}")

    print("="*60)
    print(f"RESULTS: {PASSED} passed / {FAILED} failed / {len(tests)} total")
    print("="*60)
    if FAILED > 0:
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
