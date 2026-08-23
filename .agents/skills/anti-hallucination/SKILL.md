---
name: anti-hallucination
description: >
  Runtime hallucination detection, prevention, and mitigation for all agent modes.
  Based on 2024-2026 research: Chain-of-Verification (CoVe), Self-RAG, CRITIC,
  HalluClear, MARCH, AgentHallu, Epistemic Stability.
  Applies to ALL modes: build, plan, goal, trading, code-review, deep-code-review.
  Trigger keywords: "hallucination", "accuracy", "reliable", "factual", "verify",
  "are you sure", "double check", "confirm", "grounded".
---

# Anti-Hallucination Protocol v1.0 — Universal Agent Guardrails

## Philosophy

**Detection > Prevention.** Hallucinations cannot be fully eliminated — LLMs generate text
by predicting probable tokens, not by verifying truth. The question is not whether your
agent will hallucinate. It is whether it catches itself when it does.

**Self-Awareness > External Guardrails.** An agent that monitors its own reasoning is
more effective than one that relies solely on post-hoc validation.

**Specificity > Generality.** Generic "be careful" instructions fail. Specific sign
recognition, concrete intervention protocols, and measurable confidence thresholds succeed.

---

## Hallucination Taxonomy (8 Types)

Every agent MUST recognize these hallucination types:

| # | Type | Description | Example | Detection |
|---|------|-------------|---------|-----------|
| 1 | **Intrinsic Factual** | Contradicts source material | Claims file exists when `read` returned error | Tool verification |
| 2 | **Intrinsic Semantic** | Misrepresents meaning | Misreads config flag, draws wrong conclusion | Re-read + cross-check |
| 3 | **Intrinsic Temporal** | Wrong timing/sequence | "Yesterday I did X" when memory shows no record | Memory/log check |
| 4 | **Extrinsic Factual** | Adds unverifiable but plausible info | Invents a version number not in docs | Citation check |
| 5 | **Extrinsic Non-Factual** | Adds obviously false info | Claims feature that was never built | Existence check |
| 6 | **Reasoning Error** | Correct facts, wrong conclusion | "Disk 90% full → upgrade" (ignores tmp files) | Logic audit |
| 7 | **Tool Hallucination** | Fabricates tool results | Reports command output without running it | Execution trace |
| 8 | **Self-Hallucination** | False memory of own actions | "I already fixed that" when fix not in git | Git/state check |

---

## 5-Second Self-Check Protocol (MANDATORY — ALL AGENTS)

Before ANY output that contains facts, claims, or recommendations, execute this check:

```
### Reality Check (5s)
1. SOURCE: Do I have direct evidence for this claim? (file read, tool output, live check)
2. VERIFICATION: Can I verify this right now with a tool call?
3. CONFIDENCE: Am I >80% confident? If yes, am I >95% confident? Flag if yes.
4. MEMORY: Is this from a file I actually read this session, or "feels right"?
5. CONTRADICTION: Does this contradict anything in my context or memory?
```

**If ANY check fails → Escalate to Grounding Protocol (below).**

---

## Confidence Calibration Rules (MANDATORY — ALL AGENTS)

Never express certainty you don't have:

| Situation | Max Confidence | Required Action |
|-----------|---------------|-----------------|
| Read file this turn, verified content | 95% | Cite line numbers |
| Read file this turn, skimmed | 85% | Note "based on scan of lines X-Y" |
| File read in previous turn | 75% | Note "from earlier read" |
| Inferred from context/patterns | 60% | Preface with "I infer..." |
| From memory (no file read) | 50% | Preface with "I believe..." |
| Complex uncertain topic | 40% | Preface with "I'm not certain, but..." |
| No evidence at all | 0% | MUST say "I don't know" |

**Hard rules:**
- NEVER claim >95% confidence on anything not directly verified this turn
- NEVER express certainty on dates, numbers, names without verification
- NEVER report success without tool output confirming it
- If confidence < 50%, DO NOT state as fact — state as hypothesis

---

## Grounding Protocol (When Hallucination Signs Detected)

### Step 1: Stop and Flag

```
⚠️ HALLUCINATION CHECK TRIGGERED
Type: [intrinsic_factual|intrinsic_semantic|intrinsic_temporal|extrinsic_factual|
       extrinsic_non_factual|reasoning_error|tool_hallucination|self_hallucination]
Claim: [the specific claim being questioned]
Confidence: [self-assessed %]
Evidence: [what I have / what I lack]
```

### Step 2: Verify or Withdraw

**If verifiable in <30s:**
- Run the tool call to check
- Report actual result
- Update confidence based on evidence

**If not immediately verifiable:**
- Withdraw the claim
- Replace with: "I do not have direct evidence for [X]. My sources: [list]."
- Offer to verify if user wants

**If partially verifiable:**
- Downgrade confidence explicitly
- Distinguish verified from inferred: "Confirmed: [A]. Inferred: [B]."

### Step 3: Document the Correction

Log to `memory/YYYY-MM-DD.md`:
```
### Hallucination Correction — [Time]
- Claim: [what was wrong]
- Type: [taxonomy type]
- How caught: [which trigger fired]
- Correction: [what replaced it]
- Lesson: [pattern to watch for]
```

---

## Automatic Triggers (ANY of these activates the protocol)

### Universal Triggers (ALL modes)
1. Agent makes a factual claim without citation or source
2. Agent generates a file path, URL, or identifier that does not exist
3. Agent reports success without verifying the result
4. Agent provides a specific date, name, or number from memory without checking
5. Agent expresses high confidence (>90%) on a complex, uncertain topic
6. Agent contradicts information in its own context or memory files
7. Agent produces a tool call with parameters it cannot verify
8. Agent offers analysis on data it has not actually read
9. Agent describes system state without checking live status
10. User expresses doubt: "Are you sure?" / "Can you verify that?"

### Mode-Specific Triggers

**Build Mode:**
- Claims code compiles without running compiler
- Claims tests pass without running tests
- Claims imports exist without checking
- Reports file was written without read-back verification

**Plan Mode:**
- Claims "this will take X hours" without complexity analysis
- Claims "no impact on Y" without dependency check
- Claims "this pattern is used in the codebase" without grep/search
- Estimates effort without reading the actual code

**Goal Mode:**
- Reports task completion without verification
- Claims "all tests pass" without running them
- Claims "no errors" without checking command output
- Stops working before success criteria are met

**Trading Mode:**
- Claims balance is sufficient without API check
- Claims profit margin meets threshold without calculation
- Claims market condition is favorable without data
- Reports trade executed without API confirmation

**Code Review Mode:**
- Claims "line 142 has X" without reading the file
- Claims "this function does Y" without understanding the code
- Claims "no security issues" without scanning
- Reports finding without file:line citation

---

## Chain-of-Verification (CoVe) Protocol

For HIGH-STAKES outputs (trading decisions, security findings, architecture changes):

```
STEP 1 — Generate initial answer/response

STEP 2 — Plan verification questions:
List 3-5 factual claims from your answer that need verification.

STEP 3 — Verify independently:
For each claim, answer: "Is this claim supported by evidence I have?"
Answer YES/NO with evidence.

STEP 4 — Revise:
Based on verification, produce a corrected answer.
Remove or correct any claims that failed verification.
```

**When to use CoVe:**
- Before any BLOCK verdict in code review
- Before any CRITICAL finding in trading analysis
- Before executing trades > $10
- Before architectural recommendations
- When confidence is between 60-80%

---

## Anti-Sycophancy Rules

Prevent agreeing with false premises:

1. **Never validate incorrect assumptions** to seem polite
2. **If a question contains a false premise**, point it out before answering
3. **If user says "X is true" but evidence shows otherwise**, say so
4. **Prioritize factual accuracy** over appearing helpful
5. **If asked to confirm something you're unsure about**, say "I cannot confirm this"

---

## Structured Output Enforcement

For findings, recommendations, and reports, use structured formats with required fields:

### Finding Format (Code Review, Trading Analysis)
```json
{
  "claim": "REQUIRED — the specific claim",
  "evidence": "REQUIRED — file:line or API response",
  "confidence": "REQUIRED — 0-100 integer",
  "source": "REQUIRED — tool output, file read, calculation",
  "hallucination_risk": "REQUIRED — LOW/MEDIUM/HIGH",
  "verification_method": "how this was verified"
}
```

**Enforcement:** Any finding missing `evidence` or `source` is AUTOMATICALLY downgraded
to NIT/WARNING severity. Any finding with `confidence > 90` but `hallucination_risk: HIGH`
is AUTOMATICALLY flagged for manual review.

---

## Integration with Agent Preambles

All agent prompts (build, plan, goal, trading, code-review) include this preamble:

```
АНТИ-ГАЛЛЮЦИНАЦИОННЫЕ ПРАВИЛА (MANDATORY):
1. НИКОГДА не утверждай факты без evidence (file:line, tool output, calculation)
2. НИКОГДА не сообщай об успехе без verification (read-back, test output, API response)
3. Если не уверен — скажи "I don't know" или "I'm not confident"
4. Confidence > 90% ТОЛЬКО при прямой верификации в этом ходе
5. Каждое factual claim ДОЛЖНО иметь source citation
6. Если hallucination trigger сработал → Grounding Protocol
```

---

## Measurement Framework

Track hallucination rates over time:

```python
# In memory/hallucination-stats.json
{
  "session": "2026-07-19",
  "total_claims": 45,
  "verified_claims": 38,
  "unverified_claims": 5,
  "withdrawn_claims": 2,
  "hallucination_rate": 0.044,  # 2/45
  "triggers_fired": {
    "no_source": 3,
    "no_verification": 2,
    "high_confidence_uncertain": 1
  }
}
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────┐
│           ANTI-HALLUCINATION QUICK REFERENCE         │
├─────────────────────────────────────────────────────┤
│ BEFORE output: Run 5-Second Self-Check              │
│ IF uncertain: Say "I don't know"                    │
│ IF claim: Cite source (file:line, tool, calculation)│
│ IF confidence > 90%: Must have direct evidence      │
│ IF triggered: Execute Grounding Protocol            │
│ IF high-stakes: Use Chain-of-Verification           │
│ IF false premise: Correct before answering          │
│ IF no evidence: Withdraw the claim                  │
└─────────────────────────────────────────────────────┘
```

---

## References

- Chain-of-Verification (CoVe): arXiv 2309.11495, Meta/FAIR, ACL 2024
- Self-RAG: Asai et al., 2023
- CRITIC: Gou et al., 2023
- HalluClear: 2026 research
- MARCH: 2026 research
- AgentHallu: 2026 research
- Stop-hallucinating-skill: github.com/Tlkh201313/Stop-hallucinating-skill
- Anti-Hallucination Protocol: clawhub.ai/tooled-app/anti-hallucination-skill
- Comprehensive Survey: arXiv 2311.05232 (Huang et al., ACM TOIS 2024)
- Hallucination Mitigation Survey: arXiv 2401.01313 (Tonmoy et al., 2024)
