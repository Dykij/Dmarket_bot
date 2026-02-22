# OpenClaw 2026.2.14 Changelog

## Core Engine Updates
- **Telegram Polls**: Added support for native Telegram polls via `openclaw message poll`.
    - Usage: `openclaw message poll --question "Do you like lobsters?" --options "Yes,No,Maybe" --channel telegram`
- **dmPolicy**: Added `dmPolicy` and `allowFrom` aliases for finer-grained DM access control.
    - Config: `agents.defaults.channels.telegram.dmPolicy: "pairing"` (default) or `"open"`.
- **Media Paths**: Added support for `MEDIA:` prefix in outbound messages to reference local files.
    - Example: `MEDIA:./images/chart.png` (relative to CWD).
    - Note: Absolute paths (`MEDIA:/...`) and home paths (`MEDIA:~/...`) are blocked for security.

## Bug Fixes
- Fixed `SchemaError` when using `families` key in `openclaw.json`.
- Removed legacy Anthropic references from default templates.
- Improved error handling for `sessions_spawn` when model is not specified.
