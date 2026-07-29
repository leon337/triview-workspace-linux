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
from functools import wraps
from pathlib import Path
from threading import RLock
from typing import Callable, ParamSpec, Protocol, Sequence, TypeVar

LOGGER = logging.getLogger(__name__)
_X11_LAUNCH_LOCK = RLock()
_P = ParamSpec("_P")
_R = TypeVar("_R")
_PARENT_WINDOW_PATTERN = re.compile(
    r"Parent window id:\s*(0x[0-9A-Fa-f]+|[0-9]+)",
    re.IGNORECASE,
)
_MAP_STATE_PATTERN = re.compile(r"Map State:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def _serialized_x11_launch(function: Callable[_P, _R]) -> Callable[_P, _R]:
    """Serialize X11 discovery so simultaneous panels cannot capture each other."""

    @wraps(function)
    def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        with _X11_LAUNCH_LOCK:
            return function(*args, **kwargs)

    return wrapped


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
    xwininfo_command: str | None = None


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


def parse_parent_window_id(output: str) -> int | None:
    """Extract the X11 parent window identifier reported by xwininfo."""

    match = _PARENT_WINDOW_PATTERN.search(output)
    if match is None:
        return None
    raw_value = match.group(1)
    try:
        return int(raw_value, 0)
    except ValueError:
        return None


def parse_process_table(output: str) -> dict[int, int]:
    """Parse ``ps`` PID/PPID output into a child-to-parent mapping."""

    parent_by_pid: dict[int, int] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        try:
            pid, parent_pid = (int(field) for field in fields)
        except ValueError:
            continue
        parent_by_pid[pid] = parent_pid
    return parent_by_pid


def descendant_process_ids(root_pid: int, parent_by_pid: dict[int, int]) -> set[int]:
    """Return the root PID and every recursively discovered descendant PID."""

    family = {int(root_pid)}
    changed = True
    while changed:
        changed = False
        for pid, parent_pid in parent_by_pid.items():
            if parent_pid in family and pid not in family:
                family.add(pid)
                changed = True
    return family


class X11PanelRuntimeBackend:
    """Launch Linux applications and embed compatible windows through xdotool."""

    def __init__(
        self,
        launch_timeout: float = 8.0,
        poll_interval: float = 0.2,
        reparent_attempts: int = 4,
        stable_parent_checks: int = 3,
    ) -> None:
        self._launch_timeout = max(0.1, float(launch_timeout))
        self._poll_interval = max(0.01, float(poll_interval))
        self._reparent_attempts = max(1, int(reparent_attempts))
        self._stable_parent_checks = max(2, int(stable_parent_checks))

    @staticmethod
    def _xdotool_command() -> str | None:
        return shutil.which("xdotool")

    @staticmethod
    def _xwininfo_command() -> str | None:
        return shutil.which("xwininfo")

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
                "O programa pode abrir externamente, mas xdotool não está "
                "disponível para incorporação.",
                executable=resolved[0],
            )

        xwininfo = self._xwininfo_command()
        if xwininfo is None:
            return PanelRuntimeAvailability(
                True,
                False,
                "O programa pode abrir externamente, mas xwininfo não está "
                "disponível para confirmar a incorporação.",
                executable=resolved[0],
                xdotool_command=xdotool,
            )

        return PanelRuntimeAvailability(
            True,
            True,
            "Backend X11 pronto para executar e incorporar aplicações compatíveis.",
            executable=resolved[0],
            xdotool_command=xdotool,
            xwininfo_command=xwininfo,
        )

    @_serialized_x11_launch
    def launch(
        self,
        request: PanelRuntimeLaunchRequest,
        parent_window_id: int,
    ) -> PanelRuntimeSession:
        availability = self.availability(request.command)
        if not availability.available:
            raise PanelBackendUnavailable(availability.reason)

        command = resolve_command(request.command)
        known_window_ids: set[str] = set()
        if availability.xdotool_command is not None:
            known_window_ids = self._visible_window_ids(availability.xdotool_command)

        try:
            process = subprocess.Popen(  # noqa: S603
                list(command),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise PanelLaunchError(f"Não foi possível iniciar a aplicação: {exc}.") from exc

        LOGGER.info(
            "Panel %s launched PID %s; %s visible X11 windows existed before launch.",
            request.panel_id,
            process.pid,
            len(known_window_ids),
        )

        if (
            not availability.can_embed
            or availability.xdotool_command is None
            or availability.xwininfo_command is None
        ):
            return self._external_session(request, command, process)

        try:
            window_id = self._wait_for_window(
                availability.xdotool_command,
                availability.xwininfo_command,
                process,
                request.window_hints,
                known_window_ids,
            )
            if window_id is None:
                if request.allow_external_fallback:
                    LOGGER.warning(
                        "Panel %s did not expose a unique new X11 window; using external fallback.",
                        request.panel_id,
                    )
                    return self._external_session(request, command, process)
                raise PanelLaunchError(
                    "A aplicação abriu, mas sua nova janela X11 não pôde ser identificada."
                )

            if not self._embed_window(
                availability.xdotool_command,
                availability.xwininfo_command,
                window_id,
                parent_window_id,
                request.panel_id,
            ):
                if request.allow_external_fallback:
                    LOGGER.warning(
                        "Panel %s did not remain inside X11 parent %s after %s attempts; "
                        "using external fallback.",
                        request.panel_id,
                        parent_window_id,
                        self._reparent_attempts,
                    )
                    return self._external_session(request, command, process)
                raise PanelLaunchError(
                    "A aplicação abriu, mas o gerenciador de janelas não manteve "
                    "sua janela incorporada."
                )
        except Exception:
            if request.allow_external_fallback and process.poll() is None:
                LOGGER.exception(
                    "Panel %s could not be embedded; keeping external fallback.",
                    request.panel_id,
                )
                return self._external_session(request, command, process)
            self._terminate_process(process)
            raise

        LOGGER.info(
            "Panel %s embedded X11 window %s into parent %s.",
            request.panel_id,
            window_id,
            parent_window_id,
        )
        return PanelRuntimeSession(
            panel_id=request.panel_id,
            command=command,
            process=process if process.poll() is None else None,
            window_id=window_id,
            embedded=True,
            external=False,
        )

    @staticmethod
    def _external_session(
        request: PanelRuntimeLaunchRequest,
        command: tuple[str, ...],
        process: subprocess.Popen[bytes],
    ) -> PanelRuntimeSession:
        return PanelRuntimeSession(
            panel_id=request.panel_id,
            command=command,
            process=process if process.poll() is None else None,
            window_id=None,
            embedded=False,
            external=True,
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
        xwininfo: str,
        process: subprocess.Popen[bytes],
        hints: Sequence[str],
        known_window_ids: set[str],
    ) -> str | None:
        deadline = time.monotonic() + self._launch_timeout
        normalized_hints = tuple(dict.fromkeys(hint.strip() for hint in hints if hint.strip()))
        consecutive_candidate: str | None = None
        consecutive_count = 0
        process_exit_seen_at: float | None = None
        observed_family_pids = {int(process.pid)}

        while time.monotonic() < deadline:
            observed_family_pids.update(self._process_family(process.pid))
            candidates = self._candidate_window_ids(
                xdotool,
                observed_family_pids,
                normalized_hints,
                known_window_ids,
            )
            candidate = next(
                (
                    window_id
                    for window_id in candidates
                    if self._window_is_viewable(xwininfo, window_id)
                ),
                None,
            )

            if candidate is not None:
                if candidate == consecutive_candidate:
                    consecutive_count += 1
                else:
                    consecutive_candidate = candidate
                    consecutive_count = 1
                if consecutive_count >= 2:
                    LOGGER.info(
                        "Selected new X11 window %s for PID family %s.",
                        candidate,
                        sorted(observed_family_pids),
                    )
                    return candidate
            else:
                consecutive_candidate = None
                consecutive_count = 0

            if process.poll() is not None:
                if process_exit_seen_at is None:
                    process_exit_seen_at = time.monotonic()
                elif time.monotonic() - process_exit_seen_at >= 1.0:
                    break
            time.sleep(self._poll_interval)

        return None

    def _candidate_window_ids(
        self,
        xdotool: str,
        family_pids: set[int],
        hints: Sequence[str],
        known_window_ids: set[str],
    ) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()

        def add(window_ids: Sequence[str]) -> None:
            for window_id in window_ids:
                if window_id in known_window_ids or window_id in seen:
                    continue
                seen.add(window_id)
                ordered.append(window_id)

        for pid in sorted(family_pids):
            add(self._search_windows(xdotool, "--pid", str(pid)))

        hinted: list[str] = []
        for hint in hints:
            for selector in ("--class", "--classname", "--name"):
                hinted.extend(self._search_windows(xdotool, selector, hint))

        family_hinted: list[str] = []
        unowned_hinted: list[str] = []
        for window_id in hinted:
            window_pid = self._window_pid(xdotool, window_id)
            if window_pid in family_pids:
                family_hinted.append(window_id)
            elif window_pid is None:
                unowned_hinted.append(window_id)

        add(family_hinted)
        if ordered:
            return ordered

        unique_unowned = list(dict.fromkeys(unowned_hinted))
        if len(unique_unowned) == 1:
            add(unique_unowned)
        elif len(unique_unowned) > 1:
            LOGGER.warning(
                "Ignoring %s ambiguous new X11 windows without PID metadata.",
                len(unique_unowned),
            )
        return ordered

    def _embed_window(
        self,
        xdotool: str,
        xwininfo: str,
        window_id: str,
        parent_window_id: int,
        panel_id: str,
    ) -> bool:
        for attempt in range(1, self._reparent_attempts + 1):
            LOGGER.info(
                "Embedding panel %s window %s into parent %s: attempt %s/%s.",
                panel_id,
                window_id,
                parent_window_id,
                attempt,
                self._reparent_attempts,
            )
            try:
                self._run_xdotool(
                    xdotool,
                    "windowreparent",
                    window_id,
                    str(parent_window_id),
                )
                self._run_xdotool(xdotool, "windowmap", window_id)
            except PanelLaunchError:
                LOGGER.warning(
                    "Reparent attempt %s failed for panel %s.",
                    attempt,
                    panel_id,
                    exc_info=True,
                )
            else:
                if self._confirm_window_parent(
                    xwininfo,
                    window_id,
                    parent_window_id,
                ):
                    return True
            time.sleep(self._poll_interval)
        return False

    def _visible_window_ids(self, xdotool: str) -> set[str]:
        # Snapshot all existing windows, including hidden ones that could become visible later.
        return set(self._search_windows(xdotool, "--name", ".*", only_visible=False))

    def _process_family(self, root_pid: int) -> set[int]:
        result = subprocess.run(  # noqa: S603
            ["ps", "-eo", "pid=,ppid="],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
        if result.returncode != 0:
            return {int(root_pid)}
        return descendant_process_ids(root_pid, parse_process_table(result.stdout))

    def _search_windows(
        self,
        xdotool: str,
        selector: str,
        value: str,
        *,
        only_visible: bool = True,
    ) -> list[str]:
        arguments = [xdotool, "search"]
        if only_visible:
            arguments.append("--onlyvisible")
        arguments.extend((selector, value))
        result = subprocess.run(  # noqa: S603
            arguments,
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        if result.returncode not in (0, 1):
            LOGGER.debug(
                "xdotool search failed for %s %r: %s",
                selector,
                value,
                result.stderr.strip(),
            )
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    @staticmethod
    def _window_pid(xdotool: str, window_id: str) -> int | None:
        result = subprocess.run(  # noqa: S603
            [xdotool, "getwindowpid", window_id],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        if result.returncode != 0:
            return None
        try:
            return int(result.stdout.strip())
        except ValueError:
            return None

    @staticmethod
    def _window_is_viewable(xwininfo: str, window_id: str) -> bool:
        result = subprocess.run(  # noqa: S603
            [xwininfo, "-id", window_id],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
        if result.returncode != 0:
            return False
        match = _MAP_STATE_PATTERN.search(result.stdout)
        return match is not None and match.group(1).strip().casefold() == "isviewable"

    def _confirm_window_parent(
        self,
        xwininfo: str,
        window_id: str,
        expected_parent_window_id: int,
    ) -> bool:
        consecutive_matches = 0
        max_checks = self._stable_parent_checks + 4
        for _attempt in range(max_checks):
            time.sleep(self._poll_interval)
            parent_window_id = self._read_parent_window_id(xwininfo, window_id)
            if parent_window_id == int(expected_parent_window_id):
                consecutive_matches += 1
                if consecutive_matches >= self._stable_parent_checks:
                    return True
            else:
                consecutive_matches = 0
        return False

    @staticmethod
    def _read_parent_window_id(xwininfo: str, window_id: str) -> int | None:
        result = subprocess.run(  # noqa: S603
            [xwininfo, "-id", window_id, "-tree"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
        if result.returncode != 0:
            return None
        return parse_parent_window_id(result.stdout)

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
