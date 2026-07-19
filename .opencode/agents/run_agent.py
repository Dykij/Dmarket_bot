#!/usr/bin/env python3
"""
Universal Code Review Agent Runner for MiMo V2.5 Pro API.
Runs a single agent and saves findings to JSON.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from openai import OpenAI


# Available agents
AGENTS = [
    "correctness",
    "security",
    "performance",
    "architecture",
    "domain",
    "test_coverage",
    "async_safety",
    "db_safety",
    "api_safety",
    "config_safety",
    "error_recovery",
    "duplication",
]


def load_prompt(agent_name: str) -> str:
    """Load agent prompt from file."""
    prompt_path = Path(__file__).parent / "prompts" / f"{agent_name}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")
    return prompt_path.read_text()


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
        max_tokens=4000,
    )

    return response.choices[0].message.content


def parse_findings(content: str) -> list:
    """Parse findings from LLM response.
    
    Expects JSON array of findings, each with:
    - severity: IMPORTANT / NIT / PRE_EXISTING
    - file: file path
    - line: line number
    - title: short description
    - description: detailed description
    - trigger: when does this fire?
    - impact: what breaks / financial impact
    - fix: suggested fix
    - in_diff: YES / NO
    - confidence: 0-100
    """
    # Try to extract JSON from response
    try:
        # Find JSON array in response
        start = content.find("[")
        end = content.rfind("]") + 1
        if start != -1 and end != -1:
            json_str = content[start:end]
            findings = json.loads(json_str)
            return findings
    except json.JSONDecodeError:
        pass

    # Fallback: try to parse entire content as JSON
    try:
        findings = json.loads(content)
        if isinstance(findings, list):
            return findings
    except json.JSONDecodeError:
        pass

    # Last resort: return empty list with error note
    return [
        {
            "severity": "ERROR",
            "file": "N/A",
            "line": 0,
            "title": "Failed to parse LLM response",
            "description": content[:500],
            "trigger": "N/A",
            "impact": "N/A",
            "fix": "N/A",
            "in_diff": "N/A",
            "confidence": 0,
        }
    ]


def run_agent(agent_name: str, files: str, diff: str, output: str) -> None:
    """Run a single Code Review agent."""
    print(f"[{agent_name}] Starting...")

    # Load prompt
    system_prompt = load_prompt(agent_name)
    print(f"[{agent_name}] Loaded prompt ({len(system_prompt)} chars)")

    # Prepare user message
    user_message = f"""Files to review: {files}

DIFF CONTEXT:
{diff}

Analyze the diff above and return findings in JSON format.
Each finding should be an object with these fields:
- severity: "IMPORTANT" / "NIT" / "PRE_EXISTING"
- file: file path
- line: line number
- title: short description (one line)
- description: detailed explanation
- trigger: when does this bug fire?
- impact: what breaks / financial impact
- fix: suggested fix (code snippet if possible)
- in_diff: "YES" if line is in diff hunk, "NO" if it's context
- confidence: 0-100

Return a JSON array of findings. If no issues found, return [].
"""

    # Call MiMo API
    print(f"[{agent_name}] Calling MiMo API...")
    try:
        response = call_mimo_api(system_prompt, user_message)
        print(f"[{agent_name}] Got response ({len(response)} chars)")
    except Exception as e:
        print(f"[{agent_name}] ERROR: {e}")
        response = f"Error calling API: {e}"

    # Parse findings
    findings = parse_findings(response)
    print(f"[{agent_name}] Found {len(findings)} findings")

    # Save to file
    result = {
        "agent": agent_name,
        "findings": findings,
        "raw_response": response[:2000],  # Keep first 2000 chars for debugging
    }

    with open(output, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[{agent_name}] Saved to {output}")


def main():
    parser = argparse.ArgumentParser(description="Run a Code Review agent")
    parser.add_argument(
        "--agent",
        required=True,
        choices=AGENTS,
        help="Agent name to run",
    )
    parser.add_argument(
        "--files",
        required=True,
        help="Comma-separated list of changed files",
    )
    parser.add_argument(
        "--diff",
        required=False,
        default=None,
        help="Git diff content (inline)",
    )
    parser.add_argument(
        "--diff-file",
        required=False,
        default=None,
        help="Path to file containing git diff",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON file path",
    )
    args = parser.parse_args()

    # Load diff from file if provided, otherwise use inline diff
    if args.diff_file:
        with open(args.diff_file) as f:
            diff = f.read()
    elif args.diff:
        diff = args.diff
    else:
        raise ValueError("Either --diff or --diff-file must be provided")

    run_agent(args.agent, args.files, diff, args.output)


if __name__ == "__main__":
    main()
