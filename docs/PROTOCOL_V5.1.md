# PROTOCOL V5.1

## 16. Environment & Output Safety

### Environment Awareness
- **Check OS:** Always check `os.name` or equivalent before running system commands.
- **Shell Compatibility:** 
    - Windows: Use PowerShell syntax. Avoid Bash-isms (e.g., `export`, `touch`, `grep` without alias).
    - Translation: Convert `&&` to `;` if needed for basic chaining. Use `Remove-Item` instead of `rm -rf`.

### Pagination Rule
- **Max Output:** Limit immediate console output to 50 lines (or 20 for strict guarding).
- **Handling Large Output:**
    - If output > Limit:
        1. Display HEAD (start) and TAIL (end).
        2. Save full output to a log file (e.g., `logs/last_exec.log`).
        3. Notify user of the log file location.

## 17. Communication Standards
*   Telegram = Summary Only. File Link required.
