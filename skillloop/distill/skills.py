from __future__ import annotations

from skillloop.schema import AgentTrace, Proposal

WORKFLOW_SIGNALS = ("when ", "workflow", "first ", "then ", "steps", "procedure")


def propose_skill_updates(trace: AgentTrace) -> list[Proposal]:
    proposals: list[Proposal] = []
    for message in trace.messages:
        if message.role != "user":
            continue
        text = message.content.strip()
        lowered = text.lower()
        if not all(signal in lowered for signal in ("when ", "then")) and not any(signal in lowered for signal in ("workflow", "procedure")):
            continue
        title = "Reusable workflow candidate"
        content = f"""---
name: proposed-workflow-{trace.id[:8]}
description: Reusable workflow distilled from an agent trace.
---

# {title}

## Trigger

Use when the task resembles this user instruction:

> {text}

## Steps

1. Restate the task and identify the target system.
2. Follow the user-provided workflow exactly.
3. Capture pitfalls discovered during execution.
4. Verify the result with a real command, test, or read-back check.

## Pitfalls

- Do not save credentials, tokens, or short-lived task state.
- Do not mutate global agent memory/skills without human approval.

## Verification

Confirm the workflow produced the requested result and record the concrete output.
"""
        proposals.append(
            Proposal(
                trace_id=trace.id,
                kind="skill",
                title=title,
                content=content,
                reason="User described a conditional procedure that can become procedural memory.",
                source_trace_schema_version=trace.schema_version,
            )
        )
    return proposals
