from __future__ import annotations

from skillloop.infrastructure.services.launchd import LaunchdServiceManager
from skillloop.infrastructure.services.systemd import SystemdServiceManager
from skillloop.ports.service_manager import ServiceManager

_MANAGERS: dict[str, type[ServiceManager]] = {
    LaunchdServiceManager.kind: LaunchdServiceManager,
    SystemdServiceManager.kind: SystemdServiceManager,
}


def available_kinds() -> list[str]:
    return list(_MANAGERS)


def get_service_manager(kind: str) -> ServiceManager:
    if kind not in _MANAGERS:
        raise ValueError(f"Unsupported service kind: {kind}. Available: {sorted(_MANAGERS)}")
    return _MANAGERS[kind]()


__all__ = [
    "LaunchdServiceManager",
    "SystemdServiceManager",
    "ServiceManager",
    "available_kinds",
    "get_service_manager",
]
