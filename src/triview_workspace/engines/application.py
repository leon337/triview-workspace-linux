"""Application panel adapter and engine built on the reusable Panel Runtime."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import RLock
from typing import Protocol

from triview_workspace.domain import PanelKind, PanelSpec
from triview_workspace.engines.panel_runtime import (
    PanelRuntimeAvailability,
    PanelRuntimeLaunchRequest,
    PanelRuntimeSession,
    X11PanelRuntimeBackend,
    normalize_command,
    resolve_command,
    safe_panel_token,
    split_command,
)

X11ApplicationBackend = X11PanelRuntimeBackend
LOGGER = logging.getLogger(__name__)


class ApplicationEngineError(RuntimeError):
    """Base error raised by application panel operations."""


class ApplicationBackend(Protocol):
    """Contract required by the Application Engine."""

    def availability(self, command: tuple[str, ...]) -> PanelRuntimeAvailability:
        """Return availability for the supplied command."""

    def launch(
        self,
        request: PanelRuntimeLaunchRequest,
        parent_window_id: int,
    ) -> PanelRuntimeSession:
        """Launch and optionally embed an application."""

    def resize(self, session: PanelRuntimeSession, width: int, height: int) -> None:
        """Resize an embedded application session."""

    def close(self, session: PanelRuntimeSession) -> None:
        """Close an application session."""


class ApplicationPanelAdapter:
    """Workspace adapter that prepares application launch metadata."""

    name = "application"

    def supports(self, kind: PanelKind) -> bool:
        return kind is PanelKind.APPLICATION

    def build_launch_request(self, panel: PanelSpec) -> dict[str, object]:
        command = split_command(panel.target)
        return {
            "mode": "application",
            "panel_id": panel.id,
            "command": command,
            "target": normalize_command(panel.target),
        }


class ApplicationEngine:
    """Manage Linux application sessions independently from Tkinter and layouts."""

    def __init__(self, backend: ApplicationBackend) -> None:
        self._backend = backend
        self._sessions: dict[str, PanelRuntimeSession] = {}
        self._lock = RLock()

    def availability(self, target: str) -> PanelRuntimeAvailability:
        try:
            command = split_command(target)
        except ValueError as exc:
            return PanelRuntimeAvailability(False, False, str(exc))
        return self._backend.availability(command)

    def has_session(self, panel_id: str) -> bool:
        with self._lock:
            return panel_id in self._sessions

    def session(self, panel_id: str) -> PanelRuntimeSession | None:
        with self._lock:
            return self._sessions.get(panel_id)

    def open(
        self,
        panel_id: str,
        target: str,
        parent_window_id: int,
        width: int,
        height: int,
    ) -> PanelRuntimeSession:
        command = resolve_command(target)
        executable_name = Path(command[0]).name
        token = safe_panel_token(panel_id)
        request = PanelRuntimeLaunchRequest(
            panel_id=panel_id,
            command=command,
            window_hints=(
                executable_name,
                executable_name.removesuffix(".bin"),
                token,
                panel_id,
            ),
            allow_external_fallback=True,
        )

        with self._lock:
            previous = self._sessions.pop(panel_id, None)
        if previous is not None:
            self._backend.close(previous)

        session = self._backend.launch(request, parent_window_id)
        try:
            if session.embedded:
                self._backend.resize(session, width, height)
        except Exception:
            try:
                self._backend.close(session)
            finally:
                raise

        with self._lock:
            self._sessions[panel_id] = session
        return session

    def resize(self, panel_id: str, width: int, height: int) -> None:
        with self._lock:
            session = self._sessions.get(panel_id)
        if session is not None:
            self._backend.resize(session, width, height)

    def close(self, panel_id: str) -> None:
        with self._lock:
            session = self._sessions.pop(panel_id, None)
        if session is not None:
            self._backend.close(session)

    def close_all(self) -> None:
        with self._lock:
            sessions = tuple(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            try:
                self._backend.close(session)
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unable to close application panel %s", session.panel_id)
