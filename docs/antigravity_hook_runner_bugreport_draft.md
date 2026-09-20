# Bug Report Draft: Workspace-Level Hook Runner Silent Failure

**Date:** 2026-09-19
**Antigravity Version:** 2.13.0 (binary build date: 2026-08-20, from `app.asar` mtime)
**OS:** Linux (SteamOS / Arch-based, x64)
**enableTerminalSandbox:** false (Full Machine mode)

## Problem Description

Workspace-level `.agents/hooks.json` hooks configured for `PreToolUse`, `PostToolUse`, and `Stop` events do not execute silently — no errors, no output, no log entries. The hook runner appears to be completely inactive from the perspective of the tool-use lifecycle events when `enableTerminalSandbox` is set to `false`.

## Configuration

`.agents/hooks.json` contains 9 hook groups including:
- `PreToolUse` on `run_command` → `bash .agents/scripts/pre_danger_gate.sh`
- `PostToolUse` on `run_command` → `bash .agents/scripts/raw_output_logger.sh`
- `Stop` → `bash .agents/scripts/stop_gate.sh`
- `PreInvocation` → `bash .agents/scripts/session_init.sh`

Scripts exist, are executable, have correct shebangs (`#!/bin/bash`), pass `shellcheck`. Hook JSON is valid (validated with `python3 -m json.tool`). Paths are relative to workspace root and have been tested to execute correctly when called manually from the workspace root.

No global `~/.gemini/config/hooks.json` exists (no conflict/override from global level).

## Steps to Reproduce

1. Open Antigravity with a workspace set to a directory containing `.agents/hooks.json`.
2. Set `enableTerminalSandbox` to `false` (Full Machine mode, not Turbo).
3. Run any tool that should trigger `PreToolUse` or `PostToolUse` (e.g., `run_command`, `write_to_file`).
4. Observe: hook script is NOT called. The log file that hook scripts write to (`raw_output_logger.sh` appends to `.agents/logs/RAW_OUTPUT.log`) does not receive new entries despite dozens of tool calls.

## What Has Been Eliminated as Cause

- Script syntax errors (shellcheck passes on all 9 scripts)
- Invalid JSON in `hooks.json` (validated with `python3 -m json.tool`)
- Wrong hook event names (tried `PreInvocation`, `PreToolUse`, `PostToolUse`, `Stop`)
- Missing `matcher` field (tested both with and without matcher)
- Script permission issues (all scripts are `chmod +x`)
- Missing shebang (all scripts have `#!/bin/bash`)
- New subagent within the same process (tested — same silence)
- Global hooks.json conflict (does not exist)

## Observed Pattern

Hooks appeared to function in an earlier session on the same day (log entries exist up to 13:06 local time). After a session break, hooks stopped firing entirely (19:39+ — 0 new entries despite 20+ `run_command` calls). The application was NOT restarted between the working and non-working sessions.

## Suspected Cause (Requires Confirmation)

1. **Version mismatch**: Workspace-level hooks.json may have been stabilized/fixed in a version newer than 2.13.0. The changelog for 2.15.0 (released 2026-09-18) mentions changes to agent configuration, which may include hook routing fixes.

2. **Sandbox interaction**: When `enableTerminalSandbox: false`, the hook runner may not activate for tool-use lifecycle events. This would explain why hooks worked intermittently (possibly when terminal sandbox was briefly enabled) and consistently fail now.

## Requested Action

Please confirm:
1. Whether workspace-level hooks.json `PreToolUse`/`PostToolUse` events require `enableTerminalSandbox: true` to fire.
2. Whether version 2.13.0 had a known bug where hook routing was non-functional for workspace hooks with terminal sandbox disabled.
3. The expected interaction between global vs workspace hooks.json (does absence of global hooks.json prevent workspace hooks from loading?).
