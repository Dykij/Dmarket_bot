"""
__main__.py — entry point for `python -m src.telegram.control_bot`.

Allows the package to be executed directly. The actual `main()` is in
`bot.py`. The `if __name__ == "__main__"` block in the parent
`control_bot.py` (facade) handles keyboard interrupt + crash reporting.
"""

import asyncio
import sys

from src.utils.logging_setup import configure_logging

configure_logging(component="control_bot")

from .bot import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user (KeyboardInterrupt)")
    except Exception as e:
        print(f"Bot crashed: {e}")
        sys.exit(1)
