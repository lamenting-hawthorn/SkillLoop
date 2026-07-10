from __future__ import annotations

import os
import re

from skillloop.errors import InputError

REDACTION = "[REDACTED_SECRET]"
ARTIFACT_REF_REDACTION = "[REDACTED_ARTIFACT_REF]"
PII_REDACTION = "[REDACTED_PII]"

_ENV_MAX_FIELD_CHARS = int(os.environ.get("SKILLLOOP_MAX_FIELD_CHARS", "65536"))
ENV_REDACT_PII = os.environ.get("SKILLLOOP_REDACT_PII", "0").lower() in {"1", "true", "yes", "on"}
ENV_MAX_TRACE_CHARS = int(os.environ.get("SKILLLOOP_MAX_TRACE_CHARS", "5_000_000".replace("_", "")))
ENV_MAX_MESSAGE_CHARS = int(
    os.environ.get("SKILLLOOP_MAX_MESSAGE_CHARS", "200_000".replace("_", ""))
)

MAX_FIELD_CHARS = _ENV_MAX_FIELD_CHARS
MAX_TRACE_CHARS = ENV_MAX_TRACE_CHARS
MAX_MESSAGE_CHARS = ENV_MAX_MESSAGE_CHARS
MAX_ERROR_CHARS = 4_000

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

_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?\d[\d\s().\-]{7,}\d)(?!\d)")
_IPV4_PATTERN = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")


def validate_field_size(value: str, *, label: str, limit: int | None = None) -> str:
    """Reject oversized string inputs with an :class:`InputError`."""
    cap = MAX_FIELD_CHARS if limit is None else limit
    if len(value) > cap:
        raise InputError(
            f"{label} exceeds maximum allowed size of {cap} characters",
            context={"label": label, "size": len(value), "limit": cap},
        )
    return value


def validate_trace_size(text: str, *, limit: int | None = None) -> str:
    cap = MAX_TRACE_CHARS if limit is None else limit
    if len(text) > cap:
        raise InputError(
            f"trace content exceeds maximum allowed size of {cap} characters",
            context={"size": len(text), "limit": cap},
        )
    return text


def validate_message_size(text: str, *, limit: int | None = None) -> str:
    cap = MAX_MESSAGE_CHARS if limit is None else limit
    if len(text) > cap:
        raise InputError(
            f"message exceeds maximum allowed size of {cap} characters",
            context={"size": len(text), "limit": cap},
        )
    return text


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(REDACTION, redacted)
    return redacted


def redact_pii(text: str) -> str:
    redacted = _EMAIL_PATTERN.sub(PII_REDACTION, text)
    redacted = _PHONE_PATTERN.sub(PII_REDACTION, redacted)
    redacted = _IPV4_PATTERN.sub(PII_REDACTION, redacted)
    return redacted  # noqa: RET504


def redact_artifact_ref(ref: str) -> str:
    text = redact_secrets(str(ref))
    normalized = text.replace("\\", "/")
    if text == REDACTION or text != str(ref):
        return ARTIFACT_REF_REDACTION
    if _ABSOLUTE_PATH_PATTERN.match(text) and any(
        marker in normalized.lower() for marker in _SENSITIVE_PATH_MARKERS
    ):
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


def redact_for_report(text: str, *, pii: bool | None = None, limit: int = MAX_ERROR_CHARS) -> str:
    """Sanitize an error/diagnostic string so secrets and PII cannot leak.

    Secrets are always redacted. PII redaction is gated behind the ``pii`` flag
    (defaults to the ``SKILLLOOP_REDACT_PII`` env setting). Output is truncated
    to ``limit`` characters to bound what lands in logs/diagnostics.
    """
    if not isinstance(text, str):
        text = str(text)
    redacted = redact_secrets(text)
    if pii if pii is not None else ENV_REDACT_PII:
        redacted = redact_pii(redacted)
    if len(redacted) > limit:
        redacted = redacted[:limit] + "…[TRUNCATED]"
    return redacted


__all__ = [
    "ARTIFACT_REF_REDACTION",
    "MAX_FIELD_CHARS",
    "MAX_MESSAGE_CHARS",
    "MAX_TRACE_CHARS",
    "PII_REDACTION",
    "REDACTION",
    "redact_artifact_ref",
    "redact_artifact_refs",
    "redact_data",
    "redact_for_report",
    "redact_pii",
    "redact_secrets",
    "validate_field_size",
    "validate_message_size",
    "validate_trace_size",
]
