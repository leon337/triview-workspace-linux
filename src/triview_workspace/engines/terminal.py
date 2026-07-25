"""Terminal panel adapter and engine built on the shared Panel Runtime."""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

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

LOGGER = logging.getLogger(__name__)
_TERMINAL_CANDIDATES = (
    "xterm",
    "xfce4-terminal",
    "gnome-terminal",
    "kitty",
    "alacritty",
    "konsole",
)


class TerminalEngineError(RuntimeError):
    """Base error raised by terminal panel operations."""


@dataclass(frozen=True, slots=True)
class TerminalAvailability:
    """Terminal emulator and shell availability report."""

    available: bool
    can_embed: bool
    reason: str
    emulator: str | None = None
    shell: str | None = None


class TerminalPanelAdapter:
    """Workspace adapter that prepares terminal launch metadata."""

    name = "terminal"

    def supports(self, kind: PanelKind) -> bool:
        return kind is PanelKind.TERMINAL

    def build_launch_request(self, panel: PanelSpec) -> dict[str, object]:
        shell_command = split_command(panel.target)
        return {
            "mode": "terminal",
            "panel_id": panel.id,
            "shell_command": shell_command,
            "target": normalize_command(panel.target),
        }


class X11TerminalBackend:
    """Translate terminal requests into commands handled by Panel Runtime."""

    def __init__(self, runtime: X11PanelRuntimeBackend | None = None) -> None:
        self._runtime = runtime or X11PanelRuntimeBackend()

    @staticmethod
    def _terminal_emulator() -> str | None:
        configured = os.environ.get("TRIVIEW_TERMINAL")
        if configured:
            resolved = shutil.which(configured)
            if resolved is not None:
                return resolved
        return next(
            (
                resolved
                for candidate in _TERMINAL_CANDIDATES
                if (resolved := shutil.which(candidate))
            ),
            None,
        )

    def availability(self, shell_command: tuple[str, ...]) -> TerminalAvailability:
        try:
            shell = resolve_command(shell_command)
        except ValueError as exc:
            return TerminalAvailability(False, False, str(exc))

        emulator = self._terminal_emulator()
        if emulator is None:
            return TerminalAvailability(
                False,
                False,
                "Nenhum emulador de terminal compatível foi encontrado.",
                shell=shell[0],
            )

        command = self._build_command(emulator, "TriView Terminal", shell)
        runtime_availability = self._runtime.availability(command)
        return TerminalAvailability(
            runtime_availability.available,
            runtime_availability.can_embed,
            runtime_availability.reason,
            emulator=emulator,
            shell=shell[0],
        )

    def launch(
        self,
        panel_id: str,
        title: str,
        shell_command: tuple[str, ...],
        parent_window_id: int,
    ) -> PanelRuntimeSession:
        shell = resolve_command(shell_command)
        emulator = self._terminal_emulator()
        if emulator is None:
            raise TerminalEngineError(
                "Nenhum emulador de terminal compatível foi encontrado."
            )
        command = self._build_command(emulator, title, shell)
        token = safe_panel_token(panel_id)
        request = PanelRuntimeLaunchRequest(
            panel_id=panel_id,
            command=command,
            window_hints=(
                title,
                Path(emulator).name,
                token,
                panel_id,
            ),
            allow_external_fallback=True,
        )
        return self._runtime.launch(request, parent_window_id)

    def resize(self, session: PanelRuntimeSession, width: int, height: int) -> None:
        self._runtime.resize(session, width, height)

    def close(self, session: PanelRuntimeSession) -> None:
        self._runtime.close(session)

    @staticmethod
    def _build_command(
        emulator: str,
        title: str,
        shell_command: tuple[str, ...],
    ) -> tuple[str, ...]:
        name = Path(emulator).name
        if name == "xterm":
            return (emulator, "-T", title, "-e", *shell_command)
        if name == "xfce4-terminal":
            return (
                emulator,
                "--disable-server",
                f"--title={title}",
                "--execute",
                *shell_command,
            )
        if name == "gnome-terminal":
            return (emulator, f"--title={title}", "--", *shell_command)
        if name == "kitty":
            return (emulator, "--single-instance=no", "--title", title, *shell_command)
        if name == "alacritty":
            return (emulator, "--title", title, "-e", *shell_command)
        if name == "konsole":
            return (emulator, "--new-tab", "-p", f"tabtitle={title}", "-e", *shell_command)
        return (emulator, "-e", *shell_command)


class TerminalEngine:
    """Manage terminal sessions independently from Tkinter and workspace layout."""

    def __init__(self, backend: X11TerminalBackend | None = None) -> None:
        self._backend = backend or X11TerminalBackend()
        self._sessions: dict[str, PanelRuntimeSession] = {}
        self._lock = RLock()

    def availability(self, target: str) -> TerminalAvailability:
        try:
            shell_command = split_command(target)
        except ValueError as exc:
            return TerminalAvailability(False, False, str(exc))
        return self._backend.availability(shell_command)

    def has_session(self, panel_id: str) -> bool:
        with self._lock:
            return panel_id in self._sessions

    def open(
        self,
        panel_id: str,
        title: str,
        target: str,
        parent_window_id: int,
        width: int,
        height: int,
    ) -> PanelRuntimeSession:
        shell_command = split_command(target)
        with self._lock:
            previous = self._sessions.pop(panel_id, None)
        if previous is not None:
            self._backend.close(previous)

        session = self._backend.launch(
            panel_id,
            title,
            shell_command,
            parent_window_id,
        )
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
                LOGGER.exception("Unable to close terminal panel %s", session.panel_id)
