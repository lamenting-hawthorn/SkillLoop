from skillloop.sanitize import redact_secrets


def test_redacts_common_api_keys_and_bearer_tokens():
    text = "api_key='sk-abcdefghijklmnopqrstuvwxyz123456' Authorization: Bearer abcdefghijklmnopqrstuvwxyz"

    redacted = redact_secrets(text)

    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in redacted
    assert "Bearer abcdef...xyz" not in redacted
    assert "[REDACTED_SECRET]" in redacted


def test_preserves_normal_text():
    assert redact_secrets("I prefer concise answers") == "I prefer concise answers"
