"""
Telegram Control Bot v14.4 — entry point.

Real implementation lives in the `control_bot/` package. This thin facade
preserves the command `python -m src.telegram.control_bot` and re-exports
all public symbols for backward compatibility with existing tests/scripts.

Run:
    python -m src.telegram.control_bot
or:
    ./scripts/start_telegram_bot.sh
"""

import asyncio
import sys

from src.telegram.control_bot import *  # noqa: F401, F403

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user (KeyboardInterrupt)")
    except Exception as e:
        print(f"Bot crashed: {e}")
        sys.exit(1)
