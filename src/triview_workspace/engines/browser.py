"""Browser panel contracts and an X11 backend for Brave/Chromium browsers."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from triview_workspace.domain import PanelKind, PanelSpec

LOGGER = logging.getLogger(__name__)
_SUPPORTED_SCHEMES = {"http", "https"}
_BROWSER_CANDIDATES = (
    "brave-browser",
    "brave",
    "brave-browser-stable",
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
)


class BrowserEngineError(RuntimeError):
    """Base error raised by browser panel operations."""


class BrowserBackendUnavailable(BrowserEngineError):
    """Raised when the current Linux session cannot embed a browser window."""


class BrowserLaunchError(BrowserEngineError):
    """Raised when the browser starts but cannot be embedded safely."""


@dataclass(frozen=True, slots=True)
class BrowserBackendAvailability:
    """Availability report displayed by the GUI without launching a process."""

    available: bool
    reason: str
    browser_command: str | None = None
    xdotool_command: str | None = None


@dataclass(frozen=True, slots=True)
class BrowserLaunchRequest:
    """Validated request sent to a concrete browser backend."""

    panel_id: str
    url: str
    profile_dir: Path
    window_class: str


@dataclass(slots=True)
class BrowserSession:
    """Runtime handle for one embedded browser process and its X11 window."""

    panel_id: str
    url: str
    process: subprocess.Popen[bytes] | None
    window_id: str | None
    embedded: bool


class BrowserBackend(Protocol):
    """Contract implemented by concrete browser embedding backends."""

    def availability(self) -> BrowserBackendAvailability:
        """Return whether the backend can be used in the current session."""

    def launch(self, request: BrowserLaunchRequest, parent_window_id: int) -> BrowserSession:
        """Start and embed a browser into the supplied native parent window."""

    def resize(self, session: BrowserSession, width: int, height: int) -> None:
        """Resize an embedded browser to the current panel area."""

    def close(self, session: BrowserSession) -> None:
        """Close one browser session without affecting other panels."""


def normalize_browser_url(value: str) -> str:
    """Normalize an HTTP(S) target and reject unsafe or malformed schemes."""

    raw = value.strip()
    if not raw:
        raise ValueError("A URL do painel navegador não pode ficar vazia.")
    if any(character.isspace() for character in raw):
        raise ValueError("A URL do painel navegador não pode conter espaços.")

    if raw.startswith("//"):
        raw = f"https:{raw}"
    elif "://" not in raw:
        raw = f"https://{raw}"

    parsed = urlsplit(raw)
    scheme = parsed.scheme.lower()
    if scheme not in _SUPPORTED_SCHEMES:
        raise ValueError("Somente URLs HTTP e HTTPS são permitidas em painéis navegador.")
    if not parsed.hostname:
        raise ValueError("A URL do painel navegador precisa informar um endereço válido.")

    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("A porta informada na URL do painel navegador é inválida.") from exc

    return urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment))


def _safe_panel_token(panel_id: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", panel_id).strip(".-")
    return token or "panel"


class BrowserPanelAdapter:
    """Workspace adapter that prepares validated browser launch metadata."""

    name = "browser"

    def supports(self, kind: PanelKind) -> bool:
        return kind is PanelKind.BROWSER

    def build_launch_request(self, panel: PanelSpec) -> dict[str, str]:
        return {
            "mode": "browser",
            "panel_id": panel.id,
            "url": normalize_browser_url(panel.target),
        }


class BrowserEngine:
    """Manage browser sessions independently from Tkinter and workspace layout logic."""

    def __init__(self, backend: BrowserBackend, profile_root: Path | None = None) -> None:
        self._backend = backend
        self._profile_root = profile_root or self._default_profile_root()
        self._sessions: dict[str, BrowserSession] = {}
        self._lock = RLock()

    @staticmethod
    def _default_profile_root() -> Path:
        state_root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        return state_root / "triview-workspace" / "browser-profiles"

    def availability(self) -> BrowserBackendAvailability:
        return self._backend.availability()

    def has_session(self, panel_id: str) -> bool:
        with self._lock:
            return panel_id in self._sessions

    def open(
        self,
        panel_id: str,
        target: str,
        parent_window_id: int,
        width: int,
        height: int,
    ) -> BrowserSession:
        availability = self._backend.availability()
        if not availability.available:
            raise BrowserBackendUnavailable(availability.reason)

        token = _safe_panel_token(panel_id)
        request = BrowserLaunchRequest(
            panel_id=panel_id,
            url=normalize_browser_url(target),
            profile_dir=self._profile_root / token,
            window_class=f"TriView-{token}",
        )

        with self._lock:
            previous = self._sessions.pop(panel_id, None)
        if previous is not None:
            self._backend.close(previous)

        session = self._backend.launch(request, parent_window_id)
        self._backend.resize(session, width, height)
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
                LOGGER.exception("Unable to close browser panel %s", session.panel_id)


class X11BraveBrowserBackend:
    """Embed Brave/Chromium app windows into Tk frames through X11 and xdotool."""

    def __init__(self, launch_timeout: float = 15.0) -> None:
        self._launch_timeout = launch_timeout

    def availability(self) -> BrowserBackendAvailability:
        if not os.environ.get("DISPLAY"):
            return BrowserBackendAvailability(
                False,
                "A incorporação do navegador exige uma sessão gráfica X11 com DISPLAY disponível.",
            )

        configured = os.environ.get("TRIVIEW_BROWSER")
        browser = shutil.which(configured) if configured else None
        if browser is None:
            browser = next(
                (resolved for candidate in _BROWSER_CANDIDATES if (resolved := shutil.which(candidate))),
                None,
            )
        if browser is None:
            return BrowserBackendAvailability(
                False,
                "Brave ou outro navegador Chromium compatível não foi encontrado no sistema.",
            )

        xdotool = shutil.which("xdotool")
        if xdotool is None:
            return BrowserBackendAvailability(
                False,
                "O utilitário xdotool não foi encontrado. Ele é necessário para incorporar a janela no painel.",
                browser_command=browser,
            )

        return BrowserBackendAvailability(
            True,
            "Backend X11 pronto para incorporar o navegador.",
            browser_command=browser,
            xdotool_command=xdotool,
        )

    def launch(self, request: BrowserLaunchRequest, parent_window_id: int) -> BrowserSession:
        availability = self.availability()
        if not availability.available:
            raise BrowserBackendUnavailable(availability.reason)
        assert availability.browser_command is not None
        assert availability.xdotool_command is not None

        request.profile_dir.mkdir(parents=True, exist_ok=True)
        command = [
            availability.browser_command,
            f"--app={request.url}",
            f"--user-data-dir={request.profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--class={request.window_class}",
            f"--name={request.window_class}",
        ]

        process = subprocess.Popen(  # noqa: S603
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        try:
            window_id = self._wait_for_window(
                availability.xdotool_command,
                request.window_class,
                process,
            )
            self._run_xdotool(
                availability.xdotool_command,
                "windowreparent",
                window_id,
                str(parent_window_id),
            )
            self._run_xdotool(availability.xdotool_command, "windowmap", window_id)
        except Exception:
            process.terminate()
            raise

        return BrowserSession(
            panel_id=request.panel_id,
            url=request.url,
            process=process,
            window_id=window_id,
            embedded=True,
        )

    def resize(self, session: BrowserSession, width: int, height: int) -> None:
        if not session.window_id:
            return
        availability = self.availability()
        if not availability.xdotool_command:
            return
        safe_width = max(1, int(width))
        safe_height = max(1, int(height))
        self._run_xdotool(
            availability.xdotool_command,
            "windowmove",
            session.window_id,
            "0",
            "0",
        )
        self._run_xdotool(
            availability.xdotool_command,
            "windowsize",
            session.window_id,
            str(safe_width),
            str(safe_height),
        )

    def close(self, session: BrowserSession) -> None:
        availability = self.availability()
        if session.window_id and availability.xdotool_command:
            try:
                self._run_xdotool(
                    availability.xdotool_command,
                    "windowclose",
                    session.window_id,
                )
            except BrowserLaunchError:
                LOGGER.warning("Unable to request X11 close for panel %s", session.panel_id)

        process = session.process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()

    def _wait_for_window(
        self,
        xdotool: str,
        window_class: str,
        process: subprocess.Popen[bytes],
    ) -> str:
        deadline = time.monotonic() + self._launch_timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise BrowserLaunchError(
                    "O navegador encerrou antes que sua janela pudesse ser incorporada."
                )

            for selector in ("--classname", "--name"):
                result = subprocess.run(  # noqa: S603
                    [xdotool, "search", "--onlyvisible", selector, window_class],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=2,
                )
                window_ids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
                if window_ids:
                    return window_ids[-1]
            time.sleep(0.2)

        raise BrowserLaunchError(
            "O navegador abriu, mas a janela X11 não foi localizada para incorporação no painel."
        )

    @staticmethod
    def _run_xdotool(xdotool: str, *arguments: str) -> None:
        result = subprocess.run(  # noqa: S603
            [xdotool, *arguments],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "falha desconhecida"
            raise BrowserLaunchError(f"Falha ao controlar a janela do navegador: {detail}")
