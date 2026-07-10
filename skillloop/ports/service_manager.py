from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ServiceState:
    kind: str
    label: str
    installed: bool
    active: bool
    path: str | None = None


class ServiceManager(ABC):
    """Platform-agnostic contract for installing, activating, inspecting,
    and removing a local background controller service.

    Activation is EXPLICIT: :meth:`install` only materializes the platform
    definition file and records metadata. The caller must invoke
    :meth:`activate` separately to actually start/enabled the service. This
    keeps application logic free of implicit OS-side side effects.
    """

    kind: str

    @abstractmethod
    def install(self, spec: Any, *, launch_agents_dir: str | Path | None = None) -> Path:
        """Write the platform service definition and record metadata.

        Must NOT auto-activate the service. Returns the path of the written
        definition file.
        """

    @abstractmethod
    def activate(self, spec: Any, *, launch_agents_dir: str | Path | None = None) -> None:
        """Explicitly load/enable and start the installed service."""

    @abstractmethod
    def status(self, spec: Any, *, launch_agents_dir: str | Path | None = None) -> ServiceState:
        """Report whether the service is installed and active."""

    @abstractmethod
    def uninstall(self, spec: Any, *, launch_agents_dir: str | Path | None = None) -> list[Path]:
        """Remove the definition file and recorded metadata. Returns removed paths."""

    @abstractmethod
    def install_message(self, spec: Any, path: str | Path) -> list[str]:
        """Return user-facing lines describing the just-written service definition
        file and how to activate/deactivate it.

        All OS-specific wording (launchctl/systemctl commands, plist/unit
        terminology) lives here so the CLI layer stays platform-agnostic and
        merely renders the returned lines.
        """

    @abstractmethod
    def status_message(self, metadata: dict[str, Any]) -> list[str]:
        """Return user-facing lines describing recorded installation metadata.

        OS-specific wording (plist/unit file existence terminology) lives here
        so the CLI layer renders it without knowing the platform.
        """
