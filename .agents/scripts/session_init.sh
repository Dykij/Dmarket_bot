#!/bin/bash
PAYLOAD=$(cat)
INVOCATION_NUM=$(echo "$PAYLOAD" | jq -r '.invocationNum // empty')

if [ "$INVOCATION_NUM" != "0" ]; then
    echo "{}"
    exit 0
fi

ARTIFACTS_DIR=$(echo "$PAYLOAD" | jq -r '.artifactDirectoryPath // empty')
WORKSPACE_DIR=$(echo "$PAYLOAD" | jq -r '.workspacePaths[0] // empty')

BRIEF=""

if [ -n "$ARTIFACTS_DIR" ] && [ -f "$ARTIFACTS_DIR/task.md" ]; then
    TASK_CONTENT=$(cat "$ARTIFACTS_DIR/task.md")
    if [ -n "$TASK_CONTENT" ]; then
        BRIEF="${BRIEF}=== CURRENT TASK.MD ===\n${TASK_CONTENT}\n\n"
    fi
fi

BRIEF="${BRIEF}=== STANDING RULES ===\nОбязательно следовать: AGENTS.md, .agents/rules/tooling.md, .agents/rules/otsebyatina-registry.md. Строгая RAW-дисциплина.\n\n"

if [ -n "$WORKSPACE_DIR" ] && [ -d "$WORKSPACE_DIR/.git" ]; then
    pushd "$WORKSPACE_DIR" > /dev/null 2>&1
    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
    
    # Detached HEAD check
    LOG_BASE="${CURRENT_BRANCH}"
    if [ -z "$CURRENT_BRANCH" ]; then
        CURRENT_BRANCH="(detached HEAD)"
        LOG_BASE="HEAD"
    fi
    
    BRIEF="${BRIEF}=== GIT STATE ===\nCurrent Branch: ${CURRENT_BRANCH}\n"
    
    UNCOMMITTED=$(git status --porcelain 2>/dev/null)
    if [ -n "$UNCOMMITTED" ]; then
        BRIEF="${BRIEF}Uncommitted changes:\n${UNCOMMITTED}\n"
    else
        BRIEF="${BRIEF}Uncommitted changes: None\n"
    fi
    
    UNMERGED_INFO=""
    for branch in $(git for-each-ref --format='%(refname:short)' refs/heads/ 2>/dev/null); do
        if [ "$branch" != "$CURRENT_BRANCH" ]; then
            LOG=$(git log ${LOG_BASE}..${branch} -n 5 --oneline 2>/dev/null)
            if [ -n "$LOG" ]; then
                UNMERGED_INFO="${UNMERGED_INFO}- '${branch}' has unique commits:\n${LOG}\n"
                
                # Check if there are more than 5 commits
                TOTAL_COMMITS=$(git rev-list --count ${LOG_BASE}..${branch} 2>/dev/null)
                if [ "$TOTAL_COMMITS" -gt 5 ]; then
                    UNMERGED_INFO="${UNMERGED_INFO}  ... and $((TOTAL_COMMITS - 5)) more.\n"
                fi
            fi
        fi
    done
    if [ -n "$UNMERGED_INFO" ]; then
        BRIEF="${BRIEF}Unmerged local branches:\n${UNMERGED_INFO}"
    fi
    popd > /dev/null 2>&1
fi

# Convert literal \n to actual newlines before passing to jq
printf -v FORMATTED_BRIEF "%b" "Session Start Brief:\n\n$BRIEF"

jq -n --arg msg "$FORMATTED_BRIEF" '{"injectSteps": [{"ephemeralMessage": $msg}]}'
