from __future__ import annotations

import re

REDACTION = "[REDACTED_SECRET]"

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-\.]{8,}"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9_\-\.]{8,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s]{8,}['\"]?"),
]


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(REDACTION, redacted)
    return redacted
