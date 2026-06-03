"""
Smoke test for src/telegram/control_bot/commands refactor (474 LOC → 5 files).

Verifies:
    1. Public API backward compat (all symbols importable)
    2. Router composition (5 sub-routers mounted)
    3. Handler count matches original (24 message handlers)
    4. TestItemFSM FSM works
    5. Each sub-module imports cleanly in isolation
"""

from __future__ import annotations

import sys

# ---------------------------------------------------------------------------
# Test 1: Public API backward compat
# ---------------------------------------------------------------------------
def test_public_api():
    from src.telegram.control_bot import (
        BTN_PANIC,
        BTN_START,
        BTN_STOP,
        BTN_TEST,
        TestItemFSM,
        cmd_balance,
        cmd_cancel,
        cmd_clock,
        cmd_help,
        cmd_inventory,
        cmd_panic,
        cmd_profits,
        cmd_refresh,
        cmd_settings,
        cmd_start,
        cmd_start_bot,
        cmd_status,
        cmd_stop_bot,
        cmd_test,
        cmd_test_receive,
    )

    expected = [
        "BTN_PANIC", "BTN_START", "BTN_STOP", "BTN_TEST",
        "TestItemFSM",
        "cmd_balance", "cmd_cancel", "cmd_clock", "cmd_help",
        "cmd_inventory", "cmd_panic", "cmd_profits", "cmd_refresh",
        "cmd_settings", "cmd_start", "cmd_start_bot", "cmd_status",
        "cmd_stop_bot", "cmd_test", "cmd_test_receive",
    ]
    assert len(expected) == 20, f"expected 20 symbols, got {len(expected)}"
    print(f"  [OK] {len(expected)} public symbols importable from control_bot")


# ---------------------------------------------------------------------------
# Test 2: Router composition
# ---------------------------------------------------------------------------
def test_router_composition():
    from src.telegram.control_bot.commands import router

    assert router.name == "telegram-control-commands"
    sub_names = [r.name for r in router.sub_routers]
    expected = [
        "telegram-control-lifecycle",
        "telegram-control-control",
        "telegram-control-views",
        "telegram-control-test",
        "telegram-control-utils",
    ]
    assert sub_names == expected, f"expected {expected}, got {sub_names}"
    print(f"  [OK] router has {len(sub_names)} sub-routers: {sub_names}")


# ---------------------------------------------------------------------------
# Test 3: Handler count matches original (18 functions, 24 handlers
#         because 6 commands have dual Command + F.text filter)
# ---------------------------------------------------------------------------
def test_handler_count():
    from src.telegram.control_bot.commands import router

    total_msg, total_cb = 0, 0
    per_sub = {}
    for sub in router.sub_routers:
        n_msg = len(sub.message.handlers)
        n_cb = len(sub.callback_query.handlers)
        per_sub[sub.name] = (n_msg, n_cb)
        total_msg += n_msg
        total_cb += n_cb

    # Original commands.py: 18 function defs; 6 of them registered twice
    # (Command + F.text button filter) → 18 + 6 = 24 message handlers
    assert total_msg == 24, f"expected 24 message handlers, got {total_msg}"
    assert total_cb == 0, f"expected 0 callback handlers here, got {total_cb}"

    # Per-sub-router sanity (each module's footprint)
    assert per_sub["telegram-control-lifecycle"] == (4, 0)
    assert per_sub["telegram-control-control"] == (6, 0)
    assert per_sub["telegram-control-views"] == (8, 0)
    assert per_sub["telegram-control-test"] == (4, 0)
    assert per_sub["telegram-control-utils"] == (2, 0)
    print(f"  [OK] 24 message handlers across 5 sub-routers (matches original)")


# ---------------------------------------------------------------------------
# Test 4: TestItemFSM FSM
# ---------------------------------------------------------------------------
def test_fsm():
    from src.telegram.control_bot import TestItemFSM
    from src.telegram.control_bot.commands.test import TestItemFSM as T2

    assert TestItemFSM is T2, "TestItemFSM should be the SAME class from both paths"
    state = TestItemFSM.waiting_for_item
    assert state.state == "TestItemFSM:waiting_for_item", state.state
    print(f"  [OK] TestItemFSM.waiting_for_item = {state.state}")


# ---------------------------------------------------------------------------
# Test 5: Each sub-module imports independently
# ---------------------------------------------------------------------------
def test_submodule_isolation():
    # Force re-import in isolation
    for mod_name in [
        "src.telegram.control_bot.commands.lifecycle",
        "src.telegram.control_bot.commands.control",
        "src.telegram.control_bot.commands.views",
        "src.telegram.control_bot.commands.test",
        "src.telegram.control_bot.commands.utils",
        "src.telegram.control_bot.commands",
    ]:
        if mod_name in sys.modules:
            del sys.modules[mod_name]

    # Each module must import on its own
    from src.telegram.control_bot.commands import lifecycle  # noqa: F401
    from src.telegram.control_bot.commands import control  # noqa: F401
    from src.telegram.control_bot.commands import views  # noqa: F401
    from src.telegram.control_bot.commands import test  # noqa: F401
    from src.telegram.control_bot.commands import utils  # noqa: F401
    print("  [OK] all 5 sub-modules import independently")


# ---------------------------------------------------------------------------
# Test 6: Each router in the package has its own .router attribute
# ---------------------------------------------------------------------------
def test_per_module_routers():
    from src.telegram.control_bot.commands import control, lifecycle, test, utils, views

    for mod in [lifecycle, control, views, test, utils]:
        assert hasattr(mod, "router"), f"{mod.__name__} missing router"
        r = mod.router
        assert r.name.startswith("telegram-control-"), r.name
    print("  [OK] every sub-module exports a Router with proper name prefix")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print("\n=== src/telegram/control_bot/commands refactor smoke test ===\n")
    tests = [
        ("Public API backward compat", test_public_api),
        ("Router composition", test_router_composition),
        ("Handler count", test_handler_count),
        ("TestItemFSM FSM", test_fsm),
        ("Submodule isolation", test_submodule_isolation),
        ("Per-module routers", test_per_module_routers),
    ]
    passed = 0
    for label, fn in tests:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {label}: {e}")
        except Exception as e:
            print(f"  [ERROR] {label}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())
