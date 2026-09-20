#!/bin/bash
TRANSCRIPT=$(jq -r '.transcriptPath' -)
if [ ! -f "$TRANSCRIPT" ]; then
    echo "{}"
    exit 0
fi

# Filter out context summaries at the JSON level using jq
RESULT=$(tail -n 100 "$TRANSCRIPT" | jq -r 'select(.source != "MODEL") | select(.content | contains("this summary is just for your reference") | not) | .content' 2>/dev/null | grep -oE '\[[a-zA-Z0-9_-]+\] FINAL_VERDICT: (PASS|FAIL)' | awk '{
  agent = $1
  verdict = $3
  verdicts[agent] = verdict
} END {
  fail_count = 0
  for (a in verdicts) {
    if (verdicts[a] == "FAIL") fail_count++
  }
  if (fail_count > 0) print "FAIL"
  else print "PASS"
}')

if [ "$RESULT" = "FAIL" ]; then
    cat <<JSON
{
  "injectSteps": [
    {
      "ephemeralMessage": "WARNING: Subagent check failed. Unresolved fail found."
    }
  ]
}
JSON
else
    echo "{}"
fi
