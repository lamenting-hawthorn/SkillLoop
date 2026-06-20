from __future__ import annotations

import re

REDACTION = "[REDACTED_SECRET]"
ARTIFACT_REF_REDACTION = "[REDACTED_ARTIFACT_REF]"

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-\.]{8,}"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9_\-\.]{8,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s]{8,}['\"]?"),
]
_ABSOLUTE_PATH_PATTERN = re.compile(r"^(?:/|[A-Za-z]:[\\/])")
_SENSITIVE_PATH_MARKERS = (
    "/.ssh/",
    "/.aws/",
    "/.config/",
    "/.env",
    "/secrets/",
    "/secret/",
    "/credentials/",
    "/tokens/",
)


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(REDACTION, redacted)
    return redacted


def redact_artifact_ref(ref: str) -> str:
    text = redact_secrets(str(ref))
    normalized = text.replace("\\", "/")
    if text == REDACTION or text != str(ref):
        return ARTIFACT_REF_REDACTION
    if _ABSOLUTE_PATH_PATTERN.match(text) and any(marker in normalized.lower() for marker in _SENSITIVE_PATH_MARKERS):
        return ARTIFACT_REF_REDACTION
    return text


def redact_artifact_refs(refs: list[str]) -> list[str]:
    return [redact_artifact_ref(ref) for ref in refs]


def redact_data(value):
    """Recursively redact secrets from JSON-like data without changing shape."""
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return {str(k): redact_data(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    if isinstance(value, tuple):
        return [redact_data(item) for item in value]
    return value
