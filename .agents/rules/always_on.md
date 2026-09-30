---
trigger: always_on
---
# Always On Constraints
- Do not use `rm` without an explicit file list.
- Do not modify `src/config.py`.
- Do not use `sed` for Python files (use `libcst`).
- `Proceed-` tokens are strictly required for any git commit or push.
- When asking an auditor, ask neutrally ("Review this"), without leading them to a PASS.
