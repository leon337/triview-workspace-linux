"""Reusable process and X11 window runtime for non-browser panels."""

from __future__ import annotations

import logging
import os
import re
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

LOGGER = logging.getLogger(__name__)


class PanelRuntimeError(RuntimeError):
    """Base error raised by panel process and window operations."""


class PanelBackendUnavailable(PanelRuntimeError):
    """Raised when the current environment cannot launch the requested panel."""


class PanelLaunchError(PanelRuntimeError):
    """Raised when a process cannot be started or managed safely."""


@dataclass(frozen=True, slots=True)
class PanelRuntimeAvailability:
    """Availability report for a command in the current graphical session."""

    available: bool
    can_embed: bool
    reason: str
    executable: str | None = None
    xdotool_command: str | None = None


@dataclass(frozen=True, slots=True)
class PanelRuntimeLaunchRequest:
    """Validated request sent to a concrete panel runtime backend."""

    panel_id: str
    command: tuple[str, ...]
    window_hints: tuple[str, ...]
    allow_external_fallback: bool = True


@dataclass(slots=True)
class PanelRuntimeSession:
    """Runtime handle for one process and its optional embedded X11 window."""

    panel_id: str
    command: tuple[str, ...]
    process: subprocess.Popen[bytes] | None
    window_id: str | None
    embedded: bool
    external: bool


class PanelRuntimeBackend(Protocol):
    """Contract implemented by concrete process/window backends."""

    def availability(self, command: Sequence[str]) -> PanelRuntimeAvailability:
        """Return whether a command can be launched and optionally embedded."""

    def launch(
        self,
        request: PanelRuntimeLaunchRequest,
        parent_window_id: int,
    ) -> PanelRuntimeSession:
        """Start a process and embed it when the backend supports doing so."""

    def resize(self, session: PanelRuntimeSession, width: int, height: int) -> None:
        """Resize an embedded session to the current host area."""

    def close(self, session: PanelRuntimeSession) -> None:
        """Close one session without affecting other panels."""


def safe_panel_token(panel_id: str) -> str:
    """Return a filesystem/window-safe token derived from a panel identifier."""

    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", panel_id).strip(".-")
    return token or "panel"


def split_command(value: str) -> tuple[str, ...]:
    """Split one command line without invoking a shell."""

    raw = value.strip()
    if not raw:
        raise ValueError("O comando da aplicação não pode ficar vazio.")
    if "\x00" in raw:
        raise ValueError("O comando da aplicação contém um caractere inválido.")
    try:
        parts = tuple(shlex.split(raw, posix=True))
    except ValueError as exc:
        raise ValueError(f"O comando da aplicação é inválido: {exc}.") from exc
    if not parts:
        raise ValueError("O comando da aplicação não pode ficar vazio.")
    return parts


def normalize_command(value: str) -> str:
    """Return a normalized display-safe command line."""

    return shlex.join(split_command(value))


def resolve_command(value: str | Sequence[str]) -> tuple[str, ...]:
    """Resolve the executable while preserving arguments and avoiding a shell."""

    parts = split_command(value) if isinstance(value, str) else tuple(value)
    if not parts:
        raise ValueError("O comando da aplicação não pode ficar vazio.")

    executable = parts[0]
    if "/" in executable:
        path = Path(executable).expanduser()
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError(f"O executável não existe ou não pode ser executado: {path}.")
        resolved = str(path.resolve())
    else:
        found = shutil.which(executable)
        if found is None:
            raise ValueError(f"O programa '{executable}' não foi encontrado no sistema.")
        resolved = found

    return (resolved, *parts[1:])


class X11PanelRuntimeBackend:
    """Launch Linux applications and embed compatible windows through xdotool."""

    def __init__(self, launch_timeout: float = 8.0) -> None:
        self._launch_timeout = launch_timeout

    @staticmethod
    def _xdotool_command() -> str | None:
        return shutil.which("xdotool")

    def availability(self, command: Sequence[str]) -> PanelRuntimeAvailability:
        try:
            resolved = resolve_command(command)
        except ValueError as exc:
            return PanelRuntimeAvailability(False, False, str(exc))

        if not os.environ.get("DISPLAY"):
            return PanelRuntimeAvailability(
                False,
                False,
                "A execução de aplicações exige uma sessão gráfica com DISPLAY disponível.",
                executable=resolved[0],
            )

        xdotool = self._xdotool_command()
        if xdotool is None:
            return PanelRuntimeAvailability(
                True,
                False,
                "O programa pode abrir externamente, mas xdotool não está disponível para incorporação.",
                executable=resolved[0],
            )

        return PanelRuntimeAvailability(
            True,
            True,
            "Backend X11 pronto para executar e incorporar aplicações compatíveis.",
            executable=resolved[0],
            xdotool_command=xdotool,
        )

    def launch(
        self,
        request: PanelRuntimeLaunchRequest,
        parent_window_id: int,
    ) -> PanelRuntimeSession:
        availability = self.availability(request.command)
        if not availability.available:
            raise PanelBackendUnavailable(availability.reason)

        command = resolve_command(request.command)
        try:
            process = subprocess.Popen(  # noqa: S603
                list(command),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise PanelLaunchError(f"Não foi possível iniciar a aplicação: {exc}.") from exc

        if not availability.can_embed or availability.xdotool_command is None:
            return PanelRuntimeSession(
                panel_id=request.panel_id,
                command=command,
                process=process,
                window_id=None,
                embedded=False,
                external=True,
            )

        try:
            window_id = self._wait_for_window(
                availability.xdotool_command,
                process,
                request.window_hints,
            )
            if window_id is None:
                if request.allow_external_fallback:
                    return PanelRuntimeSession(
                        panel_id=request.panel_id,
                        command=command,
                        process=process if process.poll() is None else None,
                        window_id=None,
                        embedded=False,
                        external=True,
                    )
                raise PanelLaunchError(
                    "A aplicação abriu, mas sua janela X11 não pôde ser incorporada."
                )

            self._run_xdotool(
                availability.xdotool_command,
                "windowreparent",
                window_id,
                str(parent_window_id),
            )
            self._run_xdotool(
                availability.xdotool_command,
                "windowmap",
                window_id,
            )
        except Exception:
            if request.allow_external_fallback and process.poll() is None:
                LOGGER.warning(
                    "Application panel %s could not be embedded; keeping external fallback.",
                    request.panel_id,
                )
                return PanelRuntimeSession(
                    panel_id=request.panel_id,
                    command=command,
                    process=process,
                    window_id=None,
                    embedded=False,
                    external=True,
                )
            self._terminate_process(process)
            raise

        return PanelRuntimeSession(
            panel_id=request.panel_id,
            command=command,
            process=process,
            window_id=window_id,
            embedded=True,
            external=False,
        )

    def resize(self, session: PanelRuntimeSession, width: int, height: int) -> None:
        if not session.embedded or not session.window_id:
            return
        xdotool = self._xdotool_command()
        if xdotool is None:
            raise PanelBackendUnavailable(
                "O xdotool deixou de estar disponível durante a sessão da aplicação."
            )
        safe_width = max(1, int(width))
        safe_height = max(1, int(height))
        self._run_xdotool(xdotool, "windowmove", session.window_id, "0", "0")
        self._run_xdotool(
            xdotool,
            "windowsize",
            session.window_id,
            str(safe_width),
            str(safe_height),
        )

    def close(self, session: PanelRuntimeSession) -> None:
        xdotool = self._xdotool_command()
        if session.window_id and xdotool:
            try:
                self._run_xdotool(xdotool, "windowclose", session.window_id)
            except PanelLaunchError:
                LOGGER.warning("Unable to request X11 close for panel %s", session.panel_id)
        if session.process is not None:
            self._terminate_process(session.process)

    def _wait_for_window(
        self,
        xdotool: str,
        process: subprocess.Popen[bytes],
        hints: Sequence[str],
    ) -> str | None:
        deadline = time.monotonic() + self._launch_timeout
        normalized_hints = tuple(
            hint.strip() for hint in hints if hint and hint.strip()
        )

        while time.monotonic() < deadline:
            by_pid = subprocess.run(  # noqa: S603
                [xdotool, "search", "--onlyvisible", "--pid", str(process.pid)],
                capture_output=True,
                text=True,
                check=False,
                timeout=2,
            )
            window_ids = [
                line.strip() for line in by_pid.stdout.splitlines() if line.strip()
            ]
            if window_ids:
                return window_ids[-1]

            for hint in normalized_hints:
                for selector in ("--class", "--classname", "--name"):
                    result = subprocess.run(  # noqa: S603
                        [xdotool, "search", "--onlyvisible", selector, hint],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=2,
                    )
                    window_ids = [
                        line.strip()
                        for line in result.stdout.splitlines()
                        if line.strip()
                    ]
                    if window_ids:
                        return window_ids[-1]

            if process.poll() is not None:
                return None
            time.sleep(0.2)

        return None

    @staticmethod
    def _terminate_process(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()

    @staticmethod
    def _run_xdotool(xdotool: str, *arguments: str) -> None:
        result = subprocess.run(  # noqa: S603
            [xdotool, *arguments],
            capture_output=True,
            text=True,
            check=False,
            timeout=4,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "erro desconhecido"
            raise PanelLaunchError(f"Falha no xdotool: {detail}.")
