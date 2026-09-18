#!/bin/bash
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.toolCall.args.CommandLine' 2>/dev/null)
JQ_EXIT_CODE=$?

if [ $JQ_EXIT_CODE -ne 0 ] || [[ -z "$CMD" || "$CMD" == "null" ]]; then
    echo '{"decision": "allow"}'
    exit 0
fi

if [[ "$CMD" =~ ^rm[[:space:]]+(-f[[:space:]]+)?([^[:space:]]+) ]]; then
    FILE_PATH="${BASH_REMATCH[2]}"
    BASENAME=$(basename "$FILE_PATH")
    TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcriptPath // empty')
    
    FOUND=0
    if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
        if grep -q "\"name\":\"view_file\".*\"AbsolutePath\":.*$BASENAME" "$TRANSCRIPT" || \
           grep -q "\"name\":\"run_command\".*\"CommandLine\":.*cat.*$BASENAME" "$TRANSCRIPT" || \
           grep -q "\"name\":\"run_command\".*\"CommandLine\":.*sed.*$BASENAME" "$TRANSCRIPT" || \
           grep -q "\"name\":\"run_command\".*\"CommandLine\":.*head.*$BASENAME" "$TRANSCRIPT" || \
           grep -q "\"name\":\"run_command\".*\"CommandLine\":.*tail.*$BASENAME" "$TRANSCRIPT"; then
           FOUND=1
        fi
    fi
    
    if [ "$FOUND" -eq 1 ]; then
        echo '{"decision":"allow"}'
        exit 0
    fi
    
    # Check scratch patterns
    if [[ "$BASENAME" == tmp_* ]] || [[ "$BASENAME" == *_results.txt ]] || [[ "$BASENAME" == *_results*.txt ]] || \
       [[ "$BASENAME" == test_debug* ]] || [[ "$BASENAME" == cst_*.py ]] || [[ "$BASENAME" == explore_*.sh ]] || \
       [[ "$BASENAME" == gap_closure* ]] || [[ "$BASENAME" == *_full.log ]] || [[ "$BASENAME" == baseline_*.log ]] || \
       [[ "$BASENAME" == diff_full.txt ]]; then
        echo "{\"decision\":\"ask\",\"reason\":\"Файл $FILE_PATH удаляется без явного показа его содержимого в этой сессии. Подтвердите.\"}"
        exit 0
    fi
fi

echo '{"decision":"allow"}'
exit 0
