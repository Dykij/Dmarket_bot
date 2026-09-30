# GitHub CLI Cheatsheet for CI Triage

- `gh run list --workflow <name> --limit 10` - List recent runs.
- `gh run view <id> --log-failed` - View failed jobs logs.
- **IMPORTANT**: Do NOT trust `rc=$?` if piped or combined with `|| true`. Check raw logs directly.
- **IMPORTANT**: `triggering_actor` shows the token owner, NOT necessarily the human who clicked. Check agent session logs if a run was cancelled suspiciously.
- **IMPORTANT**: If logs are expired, report as `NOT_VERIFIED`.
