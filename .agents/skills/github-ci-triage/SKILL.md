---
name: github-ci-triage
description: 'Use when you need to investigate why a GitHub Actions CI pipeline failed, why a Dependabot PR is failing, or how to view logs for a specific run. Trigger keywords: "упал CI", "почему не собирается", "статус PR", "логи GitHub Actions", "github action failure", "ci triage".'
---

# GitHub CI Triage Skill

This skill guides the agent on how to investigate and triage GitHub CI failures properly.

## Instructions

1. **Verify the environment**: If you are reproducing a CI failure locally in a `git worktree`, remember that the worktree lacks the `.env` file. Tests that depend on `.env` (like `MIN_SPREAD_PCT`) will fail locally but might pass in CI, or vice-versa. Always check environment variables.
2. **Read the logs directly**: Use `gh run view <id> --log-failed` or `--log` to see the actual error.
3. **Do not trust shell exit codes blindly**: If a command was piped or used `|| true`, `rc=$?` will lie. Always read the RAW output.
4. **Tool discrepancies**: The local `ruff` or `pytest` command might output different numbers than CI if configurations (`pyproject.toml`, `ruff.toml`) differ or if you run them on a different directory (e.g. `tests/unit/` vs `tests/`). Check what command CI actually runs!
5. **Cancellations and Actors**: If a run says "canceled by @username", this means the token owned by that user executed `gh run cancel`. It could have been the human, OR it could have been an AI agent using the human's CLI! Always cross-reference with agent session logs before concluding.
6. **Expired Logs**: If `gh run view` returns no logs because they expired, you MUST state `NOT_VERIFIED` in your report. Do not guess the failure reason.
7. **Permissions**: Always check `gh auth status` scopes before attempting write operations.

Triage-Protocol: gh-ci-v1
