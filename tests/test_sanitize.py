import pytest

from skillloop.errors import InputError
from skillloop.sanitize import (
    MAX_FIELD_CHARS,
    PII_REDACTION,
    REDACTION,
    redact_for_report,
    redact_pii,
    redact_secrets,
    validate_field_size,
    validate_message_size,
    validate_trace_size,
)


def test_redacts_common_api_keys_and_bearer_tokens():
    text = "api_key='sk-abcdefghijklmnopqrstuvwxyz123456' Authorization: Bearer abcdefghijklmnopqrstuvwxyz"

    redacted = redact_secrets(text)

    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in redacted
    assert "Bearer abcdef...xyz" not in redacted
    assert "[REDACTED_SECRET]" in redacted


def test_preserves_normal_text():
    assert redact_secrets("I prefer concise answers") == "I prefer concise answers"


def test_redact_pii_gated_and_off_by_default():
    text = "reach me at jane.doe@example.com or 415-555-1234 or 10.0.0.1"

    assert redact_secrets(text) == text
    assert redact_pii(text) == f"reach me at {PII_REDACTION} or {PII_REDACTION} or {PII_REDACTION}"


def test_redact_for_report_always_strips_secrets_and_truncates():
    text = "secret sk-abcdefghijklmnopqrstuvwxyz123456 " + "x" * 10_000

    report = redact_for_report(text, pii=False)

    assert REDACTION in report
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in report
    assert report.endswith("[TRUNCATED]")


def test_redact_for_report_pii_flag_redacts_emails():
    text = "email jane.doe@example.com password sk-abcdefghijklmnopqrstuvwxyz123456"

    report = redact_for_report(text, pii=True)

    assert "[REDACTED_SECRET]" in report
    assert PII_REDACTION in report
    assert "jane.doe@example.com" not in report


def test_validate_field_size_rejects_oversized_input():
    with pytest.raises(InputError):
        validate_field_size("a" * (MAX_FIELD_CHARS + 1), label="field")


def test_validate_trace_and_message_size_reject_oversized():
    with pytest.raises(InputError):
        validate_trace_size("t" * (validate_trace_size.__globals__["MAX_TRACE_CHARS"] + 1))
    with pytest.raises(InputError):
        validate_message_size("m" * (validate_message_size.__globals__["MAX_MESSAGE_CHARS"] + 1))
