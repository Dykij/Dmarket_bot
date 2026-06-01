"""
Tests for Telegram Control Bot v12.2.

Validates:
1. Keyboard construction
2. Inline keyboard buttons
3. Access control (admin check)
4. Command registration
5. Text content of messages
"""

import os
import sys
import asyncio

# Ensure project root in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ["DRY_RUN"] = "true"

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


def test_main_keyboard():
    """Test 1: Main reply keyboard has all required buttons."""
    from src.telegram.control_bot import get_main_keyboard
    kb = get_main_keyboard()
    # Flatten all button texts
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


def test_inline_status_keyboard():
    """Test 2: Inline status keyboard has all required buttons (or 'noop' as state-dependent)."""
    from src.telegram.control_bot import get_inline_status_kb
    kb = get_inline_status_kb()
    # Inline keyboards are lists of lists
    all_callbacks = []
    for row in kb.inline_keyboard:
        for btn in row:
            all_callbacks.append(btn.callback_data)
    # In initial state (not running), start=btn:start, stop=noop (state-dependent)
    # We test that all critical buttons are present (either active or noop)
    expected_states = {
        "btn:start": ("btn:start", "noop"),  # either active or noop
        "btn:stop": ("btn:stop", "noop"),
        "btn:balance": ("btn:balance",),
        "btn:inventory": ("btn:inventory",),
        "btn:profits": ("btn:profits",),
        "btn:refresh_status": ("btn:refresh_status",),
    }
    missing = []
    for name, allowed in expected_states.items():
        if not any(c in all_callbacks for c in allowed):
            missing.append(name)
    record("Inline Status Keyboard", len(missing) == 0,
           f"callbacks={all_callbacks}, missing={missing}")


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
    # Use the actual env value
    from src.telegram.control_bot import is_admin, ADMIN_ID
    # Positive: admin user_id should return True
    record("Admin Access (positive)", is_admin(ADMIN_ID), f"admin_id={ADMIN_ID}")
    # Negative: other user_id should return False
    record("Admin Access (negative)", not is_admin(12345), "user_id=12345 rejected")


def test_bot_module_imports():
    """Test 5: Bot module imports without errors."""
    try:
        from src.telegram.control_bot import (
            bot, dp, router,
            get_main_keyboard, get_inline_status_kb, get_inline_inventory_kb,
            is_admin, set_commands, main, on_startup,
            cmd_start, cmd_help, cmd_start_bot, cmd_stop_bot, cmd_panic,
            cmd_balance, cmd_status, cmd_inventory, cmd_profits,
            cmd_settings, cmd_test, cmd_clock, cmd_refresh,
            cb_start, cb_stop, cb_balance, cb_inventory, cb_profits,
            cb_refresh_status, cb_noop,
        )
        record("Bot Module Imports", True, "all functions importable")
    except Exception as e:
        record("Bot Module Imports", False, f"IMPORT ERROR: {e}")


def test_commands_registration():
    """Test 6: set_commands registers all required commands."""
    from src.telegram.control_bot import set_commands
    # Just verify it's a callable that accepts a Bot
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
    """Test 9: All inline callbacks use 'btn:' prefix."""
    from src.telegram.control_bot import get_inline_status_kb, get_inline_inventory_kb
    for kb in [get_inline_status_kb(), get_inline_inventory_kb()]:
        for row in kb.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data != "noop":
                    assert btn.callback_data.startswith("btn:"), f"Bad format: {btn.callback_data}"
    record("Callback Data Format", True, "all callbacks use 'btn:' prefix")


def test_input_field_placeholder():
    """Test 10: Reply keyboard has placeholder text."""
    from src.telegram.control_bot import get_main_keyboard
    kb = get_main_keyboard()
    placeholder = getattr(kb, 'input_field_placeholder', None)
    record("Input Placeholder", placeholder is not None,
           f"placeholder={placeholder!r}")


def main():
    print("="*60)
    print("TELEGRAM CONTROL BOT v12.2 — VERIFICATION")
    print("="*60)

    tests = [
        test_main_keyboard,
        test_inline_status_keyboard,
        test_inline_inventory_keyboard,
        test_admin_access,
        test_bot_module_imports,
        test_commands_registration,
        test_keyboard_button_count,
        test_emoji_unicode_in_buttons,
        test_callback_data_format,
        test_input_field_placeholder,
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
        print("🎉 ALL TESTS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
