#!/bin/bash
TRANSCRIPT=$(jq -r '.transcriptPath' -)

if [ ! -f "$TRANSCRIPT" ]; then
    echo "{}"
    exit 0
fi

RESULT=$(grep -oE '\[[a-zA-Z0-9_-]+\] FINAL_VERDICT: (PASS|FAIL)' "$TRANSCRIPT" | awk '{
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
      "ephemeralMessage": "WARNING: You have an unresolved [Agent] FINAL_VERDICT: FAIL from at least one subagent! You MUST fix the issue and get a PASS before you can finish your task or output the final report. DO NOT ignore this."
    }
  ]
}
JSON
else
    echo "{}"
fi
