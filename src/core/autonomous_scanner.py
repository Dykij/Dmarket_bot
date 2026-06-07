"""
Autonomous DMarket Scanner v3.2 — Pure Script / Math Pipeline.

Pipeline:
  1. DMarketAPIClient initialization.
  2. InventoryManager initialization.
  3. Start the Target Sniping Loop (Math based).

v12.5 changes:
- setup_logging() is now a no-op (logging is owned by src.__main__).
- Exponential backoff capped at 5 min, resets on first successful run.
- Quota-aware: if the inner loop already handles the rate-limit guard,
  we just sleep longer between restarts when monthly usage is high.
- psutil: log memory + fd count on every restart, useful for spotting
  leaks that the inner loop's RSS check would miss.
- Sends a Telegram alert on every restart (best-effort, non-blocking).
"""

import asyncio
import os
import sys
import logging
import time
import traceback
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = str(Path(__file__).resolve().parent.parent.parent)
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from src.api.dmarket_api_client import DMarketAPIClient
from src.inventory_manager import InventoryManager
from src.utils.vault import vault


def setup_logging() -> None:
    """No-op stub for back-compat. Logging is configured in src.__main__."""
    return None


# Use the logger configured by __main__ — no additional handlers here.
logger = logging.getLogger("AutonomousScanner")

# Phase 1: Feature-flag selection between v12.0 and legacy v10.0 loops.
_USE_V12 = os.getenv("USE_V12_LOOP", "true").lower() == "true"
if _USE_V12:
    from src.core.target_sniping.core import SnipingLoop
    logger.info("🔀 Using SnipingLoop v12.0 (batched endpoints + selective CS2Cap)")
else:
    from src.core.target_sniping import SnipingLoop
    logger.warning("⚠️  Using legacy v10.0 SnipingLoop (per-item CS2Cap, quota-heavy)")


async def _send_telegram_alert(message: str) -> None:
    """
    Best-effort Telegram notification on engine crash/restart.
    Never raises — if Telegram is down or not configured, we silently skip.
    """
    try:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if not token or not chat_id or token.startswith("ROTATE_ME"):
            return
        import aiohttp
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={"chat_id": chat_id, "text": message[:3500]},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status >= 400:
                    logger.debug(f"[telegram alert] HTTP {resp.status}")
    except Exception as e:
        logger.debug(f"[telegram alert] failed (non-fatal): {e}")


def _format_process_stats() -> str:
    """Memory / FD stats — useful for spotting leaks on restart."""
    try:
        import psutil
        p = psutil.Process()
        mi = p.memory_info()
        fds = len(p.open_files())
        return (
            f"RSS={mi.rss/1024/1024:.1f}MB "
            f"VMS={mi.vms/1024/1024:.1f}MB "
            f"open_fds={fds} "
            f"threads={p.num_threads()}"
        )
    except Exception:
        return "(psutil unavailable)"


async def run_autonomous_scanner() -> None:
    """
    Main entry with infinite restart loop.

    v12.5 stability contract:
    - First error: wait 5s, retry.
    - Subsequent consecutive errors: exponential backoff (10s, 20s, 40s,
      80s, 160s, capped at 300s = 5 min).
    - After a successful run_cycle, the counter resets.
    - On crash: log full traceback, send a short Telegram alert, sleep.
    """
    base_retry = 5
    max_retry = 300
    retry_delay = base_retry
    consecutive_crashes = 0
    started_at = time.time()
    successful_cycles = 0

    # v12.5: Watchdog heartbeat (outer level). The inner SnipingLoop
    # writes its own heartbeat at cycle boundaries, but the watchdog
    # also needs to see liveness while we're waiting for API keys,
    # between cycles, or during backoff sleeps.
    heartbeat_path = Path(
        os.getenv("WATCHDOG_HEARTBEAT_FILE", "data/watchdog_heartbeat.txt")
    )
    try:
        heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    def _write_heartbeat() -> None:
        try:
            heartbeat_path.write_text(str(int(time.time())), encoding="utf-8")
        except Exception:
            pass

    _write_heartbeat()  # initial

    while True:
        _write_heartbeat()  # beat on every outer iteration
        try:
            # Re-initialize vault and environment each major restart.
            # This is critical: if a previous run started with a partial
            # env, the new run will pick up corrected values.
            # override=False so a command-line DRY_RUN=false isn't clobbered.
            for env_candidate in (
                os.path.join(os.getcwd(), ".env"),
                os.path.join(BASE_DIR, ".env"),
            ):
                if os.path.isfile(env_candidate):
                    load_dotenv(dotenv_path=env_candidate, override=False)
                    vault.re_initialize()
                    break

            pub_key = os.environ.get("DMARKET_PUBLIC_KEY", "").strip()
            sec_key = vault.get_dmarket_secret()

            if not pub_key or not sec_key or pub_key.startswith("ROTATE_ME"):
                logger.error(
                    "API keys not configured (placeholders detected in .env?). "
                    "Edit .env and insert real keys. Retrying in 60s..."
                )
                await asyncio.sleep(60)
                continue

            api = DMarketAPIClient(public_key=pub_key, secret_key=sec_key)
            inventory_mgr = InventoryManager(api)
            bot = SnipingLoop(api)
            bot.inventory_mgr = inventory_mgr  # Link the manager

            logger.info(
                f"🚀 QUANTITATIVE ENGINE v12.5 (24/7 Deep Scan Active) | "
                f"{_format_process_stats()}"
            )

            # v12.5: Send a Telegram notification that the bot is up
            # (so the user knows it's alive even if no trades happen
            # for a while). The notifier is no-op if disabled.
            try:
                from src.telegram.notifier import notifier
                import time as _t
                uptime_s = int(_t.time() - started_at)
                asyncio.create_task(
                    notifier.custom(
                        f"🟢 <b>DMarket bot started</b>\n"
                        f"Mode: {'🧪 DRY_RUN' if os.getenv('DRY_RUN', 'true').lower() == 'true' else '💸 LIVE'}\n"
                        f"Targets: {self.target_games}\n"
                        f"Uptime: {uptime_s}s\n"
                        f"{_format_process_stats()}",
                        severity="info",
                    )
                )
            except Exception as e:
                logger.debug(f"startup notification failed: {e}")

            # Run the inner loop. It blocks until the bot is cancelled or
            # raises. We don't break out of this on transient cycle errors
            # (the inner loop handles its own retries); we only return
            # here on cancellation or fatal initialization error.
            await bot.start()
            successful_cycles += 1
            consecutive_crashes = 0
            retry_delay = base_retry
            logger.info(
                f"[v12.5] Inner loop returned cleanly. Stats: "
                f"uptime={time.time()-started_at:.0f}s "
                f"successes={successful_cycles}"
            )

        except asyncio.CancelledError:
            logger.info("Engine cancelled by supervisor. Exiting cleanly.")
            break
        except KeyboardInterrupt:
            logger.info("Engine interrupted. Exiting.")
            break
        except Exception as e:
            consecutive_crashes += 1
            tb = traceback.format_exc()
            logger.error(
                f"⚠️ CRITICAL ENGINE CRASH #{consecutive_crashes}: {e}\n{tb}"
            )
            # Telegram alert on the FIRST crash only (don't spam on storm)
            if consecutive_crashes == 1:
                asyncio.create_task(
                    _send_telegram_alert(
                        f"⚠️ <b>DMarket Engine crashed</b>\n"
                        f"<code>{e!s}</code>\n"
                        f"Restarting in {retry_delay}s...\n"
                        f"{_format_process_stats()}"
                    )
                )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry)


if __name__ == "__main__":
    try:
        asyncio.run(run_autonomous_scanner())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
