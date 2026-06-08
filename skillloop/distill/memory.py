from __future__ import annotations

import re

from skillloop.schema import AgentTrace, Proposal

SECRET_PATTERNS = ("api key", "token", "password", "secret", "sk-")
PREFERENCE_PATTERNS = (
    r"remember that (?P<fact>.+)",
    r"i prefer (?P<fact>.+)",
    r"always (?P<fact>.+)",
    r"never (?P<fact>.+)",
)


def _safe(text: str) -> bool:
    lowered = text.lower()
    return not any(pattern in lowered for pattern in SECRET_PATTERNS)


def _first_sentence(text: str) -> str:
    # Keep memory atomic. If the user combines a durable preference with a
    # workflow/procedure, store only the preference sentence as memory; the
    # workflow distiller handles the procedural part separately.
    return re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0].strip().rstrip(".")


def propose_memory_updates(trace: AgentTrace) -> list[Proposal]:
    proposals: list[Proposal] = []
    for message in trace.messages:
        if message.role != "user":
            continue
        content = message.content.strip()
        lowered = content.lower()
        if not _safe(content):
            continue
        for pattern in PREFERENCE_PATTERNS:
            match = re.search(pattern, lowered, flags=re.IGNORECASE)
            if match:
                fact = _first_sentence(match.group("fact"))
                proposals.append(
                    Proposal(
                        trace_id=trace.id,
                        kind="memory",
                        title="Durable user/environment memory candidate",
                        content=fact,
                        reason="User phrased this as a durable preference, rule, or remembered fact.",
                    )
                )
                break
    return proposals
