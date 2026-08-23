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

## Automated Changelog Generation (git-release pattern)

Based on `git-release` skill (⭐4 on SkillsMP):

### Detect bump type from commits since last tag

```bash
# What type of version bump?
git log $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD~10")..HEAD --oneline | \
  grep -c "^feat\|^fix\|BREAKING"
```

### Generate changelog entry

```bash
source .venv/bin/activate
python -c "
import subprocess, re
# Get commits since last tag
tag = subprocess.run(['git', 'describe', '--tags', '--abbrev=0'], 
                      capture_output=True, text=True).stdout.strip()
log = subprocess.run(['git', 'log', f'{tag}..HEAD', '--oneline', '--no-merges'],
                      capture_output=True, text=True).stdout

# Categorize
feats = [l for l in log.split('\n') if l.startswith('feat')]
fixes = [l for l in log.split('\n') if l.startswith('fix')]
perfs = [l for l in log.split('\n') if l.startswith('perf')]
docs = [l for l in log.split('\n') if l.startswith('docs')]

has_breaking = any('BREAKING' in l for l in log.split('\n'))

if has_breaking: bump = 'major'
elif feats: bump = 'minor'
elif fixes or perfs: bump = 'patch'
else: bump = 'none'

print(f'Recommended bump: {bump}')
print(f'Feat: {len(feats)}, Fix: {len(fixes)}, Perf: {len(perfs)}, Docs: {len(docs)}')
"
```

## Related Files

- `CHANGELOG.md` — Full version history
- `MEMORY.md` — Strategic context
- `README.md` — Project overview
- Source skill: https://github.com/mgiovani/cc-arsenal/tree/main/skills/git-release
- SkillsMP: https://skillsmp.com
