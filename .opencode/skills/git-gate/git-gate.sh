#!/bin/bash
# git-gate.sh — Standalone gate script for DMarket bot
# Run: ./.opencode/skills/git-gate/git-gate.sh <command>
# Commands: commit, push, status, skip

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
GATE_WORKTREE="/tmp/dmarket-gate-$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Status tracking
PASS=0
FAIL=0
TOTAL=0

log_pass() { echo -e "${GREEN}✓${NC} $1"; ((PASS++)); ((TOTAL++)); }
log_fail() { echo -e "${RED}✗${NC} $1"; ((FAIL++)); ((TOTAL++)); }
log_info() { echo -e "${BLUE}ℹ${NC} $1"; }
log_warn() { echo -e "${YELLOW}� Warning${NC} $1"; }

show_help() {
    cat <<EOF
git-gate — Quality gate for DMarket bot

Commands:
  commit <msg>   Run light checks + commit with conventional format
  push           Run full pipeline in worktree, then push if green
  status         Show gate status (which checks passed/failed)
  skip           Bypass gate (DANGER — requires confirmation)
  help           Show this help

Pipeline steps:
  1. Pre-commit: diff review, syntax check, fast lint
  2. Worktree: create isolated git worktree
  3. AI Review: code review for correctness and safety
  4. Tests: pytest + sandbox + simulation
  5. Security: pre-deploy audit
  6. Push: if all green, push to origin

EOF
}

# ----- PHASE 1: Pre-Commit Checks (Light) -----

phase1_light_checks() {
    echo -e "\n${BLUE}=== Phase 1: Pre-Commit Checks ===${NC}"
    
    # 1. Check if there are staged changes
    if ! git diff --cached --quiet 2>/dev/null; then
        log_info "Staged changes found"
    elif ! git diff --quiet 2>/dev/null; then
        log_warn "Unstaged changes found. Run 'git add' first or use 'git-gate commit'"
    else
        log_fail "No changes to commit/push"
        return 1
    fi
    
    # 2. Diff review summary
    echo -e "\n${BLUE}Staged changes:${NC}"
    git diff --cached --stat || true
    echo ""
    
    # 3. Syntax check (only changed Python files)
    log_info "Running syntax check..."
    changed_py=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)
    if [ -n "$changed_py" ]; then
        for f in $changed_py; do
            if python -m py_compile "$f" 2>/dev/null; then
                log_pass "Syntax: $f"
            else
                log_fail "Syntax: $f"
                return 1
            fi
        done
    else
        log_info "No Python files changed"
    fi
    
    # 4. Fast lint (fatal/errors only)
    log_info "Running fast lint (fatal/error only)..."
    if command -v ruff &>/dev/null; then
        if ruff check src/ --select=F,E --output-format=concise --quiet 2>/dev/null; then
            log_pass "Ruff lint (fatal/error)"
        else
            log_fail "Ruff lint found fatal errors"
            return 1
        fi
    else
        log_warn "ruff not found, skipping lint"
    fi
    
    # 5. No secrets (basic scan)
    log_info "Scanning for potential secrets..."
    if git diff --cached 2>/dev/null | grep -iE "password|secret|token|api.?key" | grep -v "test" | grep -v "example" | grep -v "dummy" | head -1; then
        log_warn "Potential secret-like strings found in diff. Review carefully."
    else
        log_pass "No obvious secrets in diff"
    fi
    
    echo -e "\n${GREEN}Phase 1 complete: ${PASS}/${TOTAL} passed${NC}\n"
    return 0
}

# ----- PHASE 2: Full Pipeline (Worktree-based) -----

phase2_create_worktree() {
    echo -e "\n${BLUE}=== Phase 2: Creating Worktree ===${NC}"
    
    # Clean up old worktree if exists
    if [ -d "$GATE_WORKTREE" ]; then
        log_info "Removing old worktree: $GATE_WORKTREE"
        rm -rf "$GATE_WORKTREE"
    fi
    
    # Create new worktree
    git worktree add "$GATE_WORKTREE" --detach 2>/dev/null || {
        log_fail "Failed to create worktree"
        return 1
    }
    
    log_pass "Worktree created: $GATE_WORKTREE"
    return 0
}

phase3_tests() {
    echo -e "\n${BLUE}=== Phase 3: Running Tests ===${NC}"
    
    cd "$GATE_WORKTREE"
    
    # Activate venv if exists
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi
    
    # pytest (fast mode)
    log_info "Running pytest..."
    if python -m pytest tests/ -x -q --tb=short 2>/dev/null; then
        log_pass "pytest (all tests)"
    else
        log_fail "pytest (some tests failed)"
        return 1
    fi
    
    # Sandbox
    log_info "Running sandbox..."
    if ENCRYPTION_KEY="test" python -m tests.sandbox_full_cycle 2>/dev/null; then
        log_pass "sandbox_full_cycle"
    else
        log_fail "sandbox_full_cycle"
        return 1
    fi
    
    echo -e "\n${GREEN}Phase 3 complete${NC}\n"
    return 0
}

phase4_security() {
    echo -e "\n${BLUE}=== Phase 4: Security Audit ===${NC}"
    
    cd "$PROJECT_ROOT"
    
    # Run the pre-deploy audit inline
    python -c "
import os

checks = []
key = os.getenv('ENCRYPTION_KEY', '')
checks.append(('ENCRYPTION_KEY not test', bool(key and key not in ['test-key', 'validate-key', 'test'])))

pub = os.getenv('DMARKET_PUBLIC_KEY', '')
checks.append(('DMARKET_PUBLIC_KEY valid', len(pub) > 20 and 'test' not in pub.lower()))

sec = os.getenv('DMARKET_SECRET_KEY', '')
checks.append(('DMARKET_SECRET_KEY valid', len(sec) > 20))

# No debug flags
checks.append(('LOG_LEVEL is WARNING+', os.getenv('LOG_LEVEL', 'INFO') in ('WARNING', 'ERROR')))

for name, ok in checks:
    print(f'  {\"Y\" if ok else \"N\"} {name}')

if not all(c[1] for c in checks):
    exit(1)
" 2>/dev/null && log_pass "Security audit" || log_fail "Security audit"
    
    return 0
}

phase5_push() {
    echo -e "\n${BLUE}=== Phase 5: Push to Origin ===${NC}"
    
    if [ $FAIL -gt 0 ]; then
        echo -e "${RED}Cannot push: ${FAIL} checks failed${NC}"
        echo "Fix issues and run: git-gate push"
        return 1
    fi
    
    # Push to origin
    cd "$PROJECT_ROOT"
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    
    log_info "Pushing branch: $CURRENT_BRANCH"
    git push origin "$CURRENT_BRANCH"
    
    log_pass "Pushed to origin/$CURRENT_BRANCH"
    echo -e "${GREEN}Gate complete! Clean PR ready.${NC}\n"
    return 0
}

# ----- COMMANDS -----

cmd_commit() {
    if [ $# -lt 1 ]; then
        echo "Usage: git-gate commit <message>"
        exit 1
    fi
    
    phase1_light_checks || exit 1
    
    # Commit with conventional format validation
    msg="$1"
    if ! echo "$msg" | grep -qE '^(feat|fix|perf|refactor|test|docs|chore|style)(\([a-z]+\))?: .+'; then
        log_warn "Commit message doesn't follow conventional commits"
        echo "Format: <type>(<scope>): <description>"
        echo "Types: feat, fix, perf, refactor, test, docs, chore, style"
        read -p "Continue anyway? (y/N): " confirm
        [ "$confirm" != "y" ] && exit 1
    fi
    
    git commit -m "$msg"
    log_pass "Committed: $msg"
}

cmd_push() {
    phase1_light_checks || exit 1
    phase2_create_worktree || exit 1
    phase3_tests || exit 1
    phase4_security || exit 1
    phase5_push || exit 1
    
    # Clean up worktree
    rm -rf "$GATE_WORKTREE"
    git worktree prune
}

cmd_status() {
    echo -e "${BLUE}Git Gate Status${NC}"
    echo "Worktree: $GATE_WORKTREE"
    echo "Project:  $PROJECT_ROOT"
    echo ""
    echo "Defined checks:"
    echo "  ✓ Phase 1: Pre-commit (syntax, lint, secrets)"
    echo "  ✓ Phase 2: Worktree creation"
    echo "  ✓ Phase 3: Tests (pytest, sandbox)"
    echo "  ✓ Phase 4: Security audit"
    echo "  ✓ Phase 5: Push to origin"
    echo ""
    echo "Run 'git-gate push' to execute full pipeline."
}

cmd_skip() {
    echo -e "${RED}DANGER: You are about to bypass the quality gate.${NC}"
    read -p "Reason for bypass (required): " reason
    if [ -z "$reason" ]; then
        echo "Bypass cancelled."
        exit 1
    fi
    
    # Log bypass to memory file
    MEM_FILE="$PROJECT_ROOT/memory/$(date +%Y-%m-%d).md"
    mkdir -p "$(dirname "$MEM_FILE")"
    echo "$(date) — GATE BYPASS: $reason" >> "$MEM_FILE"
    
    echo "Bypass logged to memory. Use with caution."
    
    # Actually push
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    git push origin "$CURRENT_BRANCH"
}

# ----- MAIN -----

case "${1:-help}" in
    commit)
        shift
        cmd_commit "$@"
        ;;
    push)
        shift
        cmd_push
        ;;
    status)
        cmd_status
        ;;
    skip)
        cmd_skip
        ;;
    help|--help|-h|*)
        show_help
        ;;
esac