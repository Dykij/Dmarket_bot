---
name: telegram-module-dev
description: Use when the user asks to add, modify, or fix Telegram bot commands, keyboards, callbacks, or handlers. Trigger keywords: "telegram", "add command", "new button", "telegram handler", "keyboard", "callback", "добавить команду", "кнопка", "клавиатура", "telegram bot". Applies project patterns for aiogram 3.x: routers, safe_call decorator, format helpers, and inline keyboards.
---

# Telegram Module Development

Patterns and conventions for the Telegram control bot (`src/telegram/control_bot/`).

## Project Structure

```
src/telegram/control_bot/
├── __init__.py          # Re-exports (update when adding new symbols)
├── bot.py               # Bot wiring, ThrottlingMiddleware, main()
├── state.py             # BotState, _load_config, is_admin
├── lifecycle.py         # set_commands, on_startup, on_shutdown
├── keyboards.py         # BTN_*/CB_* constants + keyboard builders
├── formatters.py        # Pure formatting functions (Markdown-safe)
├── callbacks.py         # Inline callback handlers (btn:start, etc.)
├── filters.py           # reject_non_admin, on_router_error
├── resilience.py        # safe_call, retry_async, dmarket_client
├── commands/
│   ├── __init__.py      # Combined router + exports
│   ├── lifecycle.py     # /start, /help, /settings
│   ├── control.py       # /start_bot, /stop_bot, /panic
│   ├── views.py         # /balance, /status, /inventory, /profits, /portfolio, /daily, /analyze, /sell, /prices
│   ├── test.py          # /test (FSM)
│   └── utils.py         # /clock, /refresh
└── notifier.py           # Standalone aiohttp-based push notifier
```

## Adding a New Command

### 1. Add button constant (keyboards.py)
```python
BTN_MY_CMD = "🔧 MY CMD"
```

### 2. Add to main keyboard (keyboards.py)
```python
# In get_main_keyboard(), add to appropriate row
[KeyboardButton(text=BTN_MY_CMD), KeyboardButton(text=BTN_EXISTING)],
```

### 3. Add command handler (commands/views.py)
```python
@router.message(Command("my_cmd"))
@router.message(F.text == BTN_MY_CMD)
@safe_call
async def cmd_my_cmd(message):
    logger.info("cmd_my_cmd by user %s", message.from_user.id)
    # Handler logic here
    await message.answer("Result text", reply_markup=get_inline_my_kb())
    logger.debug("cmd_my_cmd ok")
```

### 4. Update exports (commands/__init__.py)
```python
from .views import cmd_my_cmd
# Add to __all__
```

### 5. Register slash command (lifecycle.py)
```python
types.BotCommand(command="my_cmd", description="🔧 My command description"),
```

### 6. Update root __init__.py
```python
from .keyboards import BTN_MY_CMD, ...
from .commands import cmd_my_cmd, ...
from .callbacks import cb_my_cmd, ...
# Add to __all__
```

## Adding a New Inline Callback

### 1. Add callback constant (keyboards.py)
```python
CB_MY_CALLBACK = "btn:my_callback"
```

### 2. Add inline keyboard function
```python
def get_inline_my_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Action", callback_data=CB_MY_CALLBACK)],
        [InlineKeyboardButton(text="⬅️ Status", callback_data=CB_REFRESH_STATUS)],
    ])
```

### 3. Add callback handler (callbacks.py)
```python
@router.callback_query(F.data == CB_MY_CALLBACK)
@safe_call
async def cb_my_callback(callback: types.CallbackQuery):
    if callback.message is None or not isinstance(callback.message, types.Message):
        return
    logger.info("cb_my_callback triggered")
    # Handler logic
    await callback.message.edit_text("Result", reply_markup=get_inline_my_kb())
    await callback.answer()
```

## Patterns

- **ALL handlers use `@safe_call`** — catches errors, logs traceback, shows generic error to user
- **ALL handlers log at INFO** — `logger.info("handler_name by user %s", message.from_user.id)`
- **Formatters are PURE functions** — no side effects, take data → return markdown string
- **Markdown escaping** — use `escape_md()` from formatters.py for any user-supplied text in messages
- **Inline keyboards always include Refresh + Back to Status buttons**

## Related Files

- `src/telegram/control_bot/keyboards.py` — Button constants + builders
- `src/telegram/control_bot/callbacks.py` — Inline handlers
- `src/telegram/control_bot/commands/views.py` — Command handlers
- `src/telegram/control_bot/formatters.py` — Formatting functions
