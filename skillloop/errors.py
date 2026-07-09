from __future__ import annotations

from typing import Any


class SkillLoopError(Exception):
    """Base class for all SkillLoop-specific errors.

    Carries an optional ``context`` mapping so error reports can attach
    machine-readable details without leaking those details into user-facing
    messages by default.
    """

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, Any] = dict(context or {})

    def __str__(self) -> str:
        return self.message


class ConfigError(SkillLoopError):
    """Invalid static configuration (files, environment, settings)."""


class InputError(SkillLoopError):
    """Rejected user/agent-supplied input (oversized, malformed, unsafe)."""


class PersistenceError(SkillLoopError):
    """Failure to read, write, or persist state durably."""


class ConnectorError(SkillLoopError):
    """Failure talking to an external system or adapter."""


class PolicyError(SkillLoopError):
    """Invalid or unsupported policy definition."""


__all__ = [
    "SkillLoopError",
    "ConfigError",
    "InputError",
    "PersistenceError",
    "ConnectorError",
    "PolicyError",
]
