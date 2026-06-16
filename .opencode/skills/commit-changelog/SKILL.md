---
name: commit-changelog
description: Use when the user asks to commit, push, or update the changelog. Trigger keywords: "commit", "push", "закомить", "changelog", "release", "version bump". Creates semantic commits with Conventional Commits format and updates CHANGELOG.md automatically.
---

# Commit & Changelog

Create properly formatted commits and update the project changelog.

## Commit Format (Conventional Commits)

```
<type>(<scope>): <short description>

<optional body — longer explanation of what and why>

<optional footer — breaking changes, issue references>
```

### Types

| Type | Use for |
|------|---------|
| `feat` | New feature or significant capability |
| `fix` | Bug fix |
| `perf` | Performance improvement |
| `refactor` | Code restructuring without feature change |
| `test` | Adding or updating tests |
| `docs` | Documentation only |
| `chore` | Maintenance, build, CI |
| `style` | Formatting, linting |

### Scopes (project-specific)

| Scope | Files affected |
|-------|----------------|
| `api` | `src/api/` |
| `core` | `src/core/target_sniping/` |
| `db` | `src/db/` |
| `risk` | `src/risk/` |
| `telegram` | `src/telegram/` |
| `rust` | `src/rust_core/` |
| `config` | `src/config.py` |
| `test` | `tests/` |
| `docs` | `*.md` documentation |

## Changelog Update

When committing a feature or fix, update `CHANGELOG.md`:

1. Add new version entry at top (e.g., `## [13.4.0] - 2026-06-16`)
2. Group changes by type: `### Added`, `### Fixed`, `### Changed`, `### Performance`
3. Reference research sources and API docs when relevant

## Pre-Commit Checklist

```bash
# 1. Check git status
git status --short

# 2. Review diff
git diff --stat

# 3. Run ruff (only fatal/error)
ruff check src/ --select=F,E

# 4. Compile Python
python -c "
import py_compile
# Add changed .py files here
for f in []:
    py_compile.compile(f, doraise=True)
print('Compile OK')
"

# 5. Commit
git add <files>
git commit -m "<message>"

# 6. Push
git push
```

## Version Convention

```
v<major>.<minor>.<patch>

Major (X.0.0): Breaking changes, API migrations, strategy redesigns
Minor (0.X.0): New features, significant improvements
Patch (0.0.X): Bug fixes, small tweaks
```

Current: **v13.4**

## Related Files

- `CHANGELOG.md` — Full version history
- `MEMORY.md` — Strategic context
- `README.md` — Project overview
