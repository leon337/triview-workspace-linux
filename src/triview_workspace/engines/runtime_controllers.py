"""GUI-neutral runtime controllers for executable panel adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from triview_workspace.domain import PanelSpec
from triview_workspace.engines.application import ApplicationEngine
from triview_workspace.engines.browser import BrowserEngine
from triview_workspace.engines.panel_runtime import PanelRuntimeAvailability
from triview_workspace.engines.terminal import TerminalEngine


@dataclass(frozen=True, slots=True)
class RuntimeOpenResult:
    """Normalized result returned after opening any executable panel."""

    embedded: bool
    external: bool = False


class RuntimeController(Protocol):
    """Uniform contract consumed by the desktop shell."""

    adapter_name: str

    def availability(self, panel: PanelSpec) -> PanelRuntimeAvailability:
        """Report whether the panel can be opened."""

    def open(
        self,
        panel: PanelSpec,
        parent_window_id: int,
        width: int,
        height: int,
    ) -> RuntimeOpenResult:
        """Open a panel and normalize its runtime state."""

    def has_session(self, panel_id: str) -> bool:
        """Return whether this controller owns a session for the panel."""

    def resize(self, panel_id: str, width: int, height: int) -> None:
        """Resize the panel session when embedded."""

    def close(self, panel_id: str) -> None:
        """Close one session."""

    def close_all(self) -> None:
        """Close every session owned by the controller."""


class BrowserRuntimeController:
    adapter_name = "browser"

    def __init__(self, engine: BrowserEngine) -> None:
        self.engine = engine

    def availability(self, panel: PanelSpec) -> PanelRuntimeAvailability:
        del panel
        report = self.engine.availability()
        return PanelRuntimeAvailability(
            report.available,
            report.available,
            report.reason,
            executable=report.browser_command,
            xdotool_command=report.xdotool_command,
        )

    def open(
        self,
        panel: PanelSpec,
        parent_window_id: int,
        width: int,
        height: int,
    ) -> RuntimeOpenResult:
        self.engine.open(panel.id, panel.target, parent_window_id, width, height)
        return RuntimeOpenResult(embedded=True)

    def has_session(self, panel_id: str) -> bool:
        return self.engine.has_session(panel_id)

    def resize(self, panel_id: str, width: int, height: int) -> None:
        self.engine.resize(panel_id, width, height)

    def close(self, panel_id: str) -> None:
        self.engine.close(panel_id)

    def close_all(self) -> None:
        self.engine.close_all()


class ApplicationRuntimeController:
    adapter_name = "application"

    def __init__(self, engine: ApplicationEngine) -> None:
        self.engine = engine

    def availability(self, panel: PanelSpec) -> PanelRuntimeAvailability:
        return self.engine.availability(panel.target)

    def open(
        self,
        panel: PanelSpec,
        parent_window_id: int,
        width: int,
        height: int,
    ) -> RuntimeOpenResult:
        session = self.engine.open(
            panel.id,
            panel.target,
            parent_window_id,
            width,
            height,
        )
        return RuntimeOpenResult(session.embedded, session.external)

    def has_session(self, panel_id: str) -> bool:
        return self.engine.has_session(panel_id)

    def resize(self, panel_id: str, width: int, height: int) -> None:
        self.engine.resize(panel_id, width, height)

    def close(self, panel_id: str) -> None:
        self.engine.close(panel_id)

    def close_all(self) -> None:
        self.engine.close_all()


class TerminalRuntimeController:
    adapter_name = "terminal"

    def __init__(self, engine: TerminalEngine) -> None:
        self.engine = engine

    def availability(self, panel: PanelSpec) -> PanelRuntimeAvailability:
        report = self.engine.availability(panel.target)
        return PanelRuntimeAvailability(
            report.available,
            report.can_embed,
            report.reason,
            executable=report.emulator,
        )

    def open(
        self,
        panel: PanelSpec,
        parent_window_id: int,
        width: int,
        height: int,
    ) -> RuntimeOpenResult:
        session = self.engine.open(
            panel.id,
            panel.title,
            panel.target,
            parent_window_id,
            width,
            height,
        )
        return RuntimeOpenResult(session.embedded, session.external)

    def has_session(self, panel_id: str) -> bool:
        return self.engine.has_session(panel_id)

    def resize(self, panel_id: str, width: int, height: int) -> None:
        self.engine.resize(panel_id, width, height)

    def close(self, panel_id: str) -> None:
        self.engine.close(panel_id)

    def close_all(self) -> None:
        self.engine.close_all()


class RuntimeControllerRegistry:
    """Resolve executable adapters to runtime controllers."""

    def __init__(self, controllers: tuple[RuntimeController, ...]) -> None:
        self._controllers = {item.adapter_name: item for item in controllers}

    def get(self, adapter_name: str) -> RuntimeController | None:
        return self._controllers.get(adapter_name)

    def close_all(self) -> None:
        for controller in self._controllers.values():
            controller.close_all()

    def controllers(self) -> tuple[RuntimeController, ...]:
        return tuple(self._controllers.values())
