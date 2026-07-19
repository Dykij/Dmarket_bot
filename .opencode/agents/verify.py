#!/usr/bin/env python3
"""
Verification agent for Code Review findings.
Independently verifies or rejects findings from other agents.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from openai import OpenAI


def load_verification_prompt() -> str:
    """Load verification prompt."""
    return """You are a verification agent. Your job is to independently verify or reject
a code review finding.

For each finding:
1. Read the file at the specified line and surrounding context
2. Understand the code flow
3. Determine if this is a REAL issue or FALSE POSITIVE
4. If real: construct the exact input/condition that triggers the bug
5. If false positive: explain precisely why it's not a real issue

Return JSON with:
- verdict: "CONFIRMED" / "FALSE_POSITIVE" / "NEEDS_MANUAL"
- confidence: 0-100
- explanation: 1-3 sentences explaining your verdict
- reproduction_steps: (if CONFIRMED) exact steps to reproduce
- reason: (if FALSE_POSITIVE) why it's not a real issue
"""


def call_mimo_api(system_prompt: str, user_message: str) -> str:
    """Call MiMo API and return response content."""
    api_key = os.getenv("MIMO_API_KEY")
    base_url = os.getenv("MIMO_BASE_URL", "https://token-plan-sgp.xiaomimimo.com/v1")

    if not api_key:
        raise ValueError("MIMO_API_KEY environment variable not set")

    client = OpenAI(base_url=base_url, api_key=api_key)

    response = client.chat.completions.create(
        model="mimo-v2.5-pro",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        max_tokens=2000,
    )

    return response.choices[0].message.content


def verify_finding(finding: dict, diff: str) -> dict:
    """Verify a single finding."""
    system_prompt = load_verification_prompt()

    user_message = f"""Finding to verify:
- Source agent: {finding.get('agent', 'unknown')}
- Severity: {finding.get('severity', 'unknown')}
- Title: {finding.get('title', 'unknown')}
- Description: {finding.get('description', 'N/A')}
- File:line: {finding.get('file', '?')}:{finding.get('line', '?')}
- Trigger: {finding.get('trigger', 'N/A')}
- Impact: {finding.get('impact', 'N/A')}
- Suggested fix: {finding.get('fix', 'N/A')}

DIFF CONTEXT:
{diff[:3000]}

Verify this finding. Is it a REAL issue or FALSE POSITIVE?
Return JSON with: verdict, confidence, explanation, reproduction_steps (if confirmed), reason (if false positive).
"""

    try:
        response = call_mimo_api(system_prompt, user_message)

        # Parse response
        start = response.find("{")
        end = response.rfind("}") + 1
        if start != -1 and end != -1:
            result = json.loads(response[start:end])
            return result
    except Exception as e:
        return {
            "verdict": "NEEDS_MANUAL",
            "confidence": 0,
            "explanation": f"Verification failed: {e}",
        }

    return {
        "verdict": "NEEDS_MANUAL",
        "confidence": 0,
        "explanation": "Could not parse verification response",
    }


def verify_findings(input_file: str, output_file: str, diff: str) -> None:
    """Verify all findings from deduped file."""
    print(f"Loading findings from {input_file}...")

    with open(input_file) as f:
        data = json.load(f)

    findings = data.get("findings", [])
    print(f"Found {len(findings)} findings to verify")

    # Only verify IMPORTANT and NIT findings
    to_verify = [f for f in findings if f.get("severity") in ("IMPORTANT", "NIT")]
    print(f"Verifying {len(to_verify)} findings (skipping PRE_EXISTING)")

    verified = []
    for i, finding in enumerate(to_verify, 1):
        print(f"  [{i}/{len(to_verify)}] Verifying: {finding.get('title', '?')[:50]}...")

        result = verify_finding(finding, diff)

        finding["verification"] = {
            "verdict": result.get("verdict", "NEEDS_MANUAL"),
            "confidence": result.get("confidence", 0),
            "explanation": result.get("explanation", "N/A"),
            "reproduction_steps": result.get("reproduction_steps", ""),
            "reason": result.get("reason", ""),
        }

        # Update finding confidence based on verification
        if result.get("verdict") == "CONFIRMED":
            finding["verified"] = True
            finding["confidence"] = min(100, finding.get("confidence", 0) + 10)
        elif result.get("verdict") == "FALSE_POSITIVE":
            finding["verified"] = False
            finding["confidence"] = max(0, finding.get("confidence", 0) - 20)
        else:
            finding["verified"] = None

        verified.append(finding)

    # Merge back with pre-existing findings
    pre_existing = [f for f in findings if f.get("severity") == "PRE_EXISTING"]
    all_findings = verified + pre_existing

    # Save
    result = {
        "total_findings": len(all_findings),
        "verified_count": sum(1 for f in verified if f.get("verified") is True),
        "false_positive_count": sum(1 for f in verified if f.get("verified") is False),
        "needs_manual_count": sum(1 for f in verified if f.get("verified") is None),
        "findings": all_findings,
    }

    with open(output_file, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Verification complete. Saved to {output_file}")
    print(f"  Confirmed: {result['verified_count']}")
    print(f"  False positives: {result['false_positive_count']}")
    print(f"  Needs manual: {result['needs_manual_count']}")


def main():
    parser = argparse.ArgumentParser(description="Verify Code Review findings")
    parser.add_argument("--input", required=True, help="Input deduped JSON file")
    parser.add_argument("--output", required=True, help="Output verified JSON file")
    parser.add_argument("--diff", required=True, help="Git diff content")
    args = parser.parse_args()

    verify_findings(args.input, args.output, args.diff)


if __name__ == "__main__":
    main()
