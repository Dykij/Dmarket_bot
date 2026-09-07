#!/bin/bash
WORKSPACE_DIR=$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null || echo "/home/deck/dmarket/Dmarket_bot-main")
cd "$WORKSPACE_DIR"

BROKEN=0
for f in .agents/skills/*/SKILL.md; do
    python3 -c "
import sys
content = open(sys.argv[1]).read()
if not content.startswith('---'):
    print(f'BROKEN: {sys.argv[1]} — no opening ---')
    sys.exit(1)
parts = content.split('---', 2)
if len(parts) < 3:
    print(f'BROKEN: {sys.argv[1]} — no closing ---')
    sys.exit(1)
try:
    import yaml
    yaml.safe_load(parts[1])
except Exception as e:
    print(f'BROKEN: {sys.argv[1]} — {e}')
    sys.exit(1)
" "$f" || BROKEN=1
done
if [ "$BROKEN" -eq 1 ]; then
    echo '{"decision":"allow","hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"WARNING: some SKILL.md files have broken frontmatter — see stderr above."}}'
else
    echo '{"decision":"allow"}'
fi
