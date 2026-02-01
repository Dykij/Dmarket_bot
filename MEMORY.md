# MEMORY.md - Аркадий's Long-Term Memory

## Project Context: DMarket-Telegram-Bot
- **Human:** Бодичка.
- **Location:** `D:\DMarket-Telegram-Bot-main`.
- **Tech Stack:** Python 3.11+, DMarket API v1.1.0 (Ed25519), SQLAlchemy, PostgreSQL, python-telegram-bot.
- **Architecture:** Modular "Skills" system.

## Strategic Decisions
- **Persistence:** Move away from `.pickle` files to full SQL-based state management.
- **Skills:** Migrate to `.github/skills/` standard as per 2026 SkillsMP.com updates.
- **Initialization:** Ensure `Application.initialize` is phase-based and robust against single-service failures.

## Lessons Learned
- Always use `ls` or `Get-ChildItem` in this environment (Windows PowerShell).
- Never use `/b` or `/s` flags with `dir`.
- The project has a huge number of tests (7600+ mentioned in README), use `pytest` sparingly to avoid long execution times.
