"""Nested X11 browser backend that prevents host-desktop exposure.

Each Browser Panel receives a dedicated Xephyr server embedded directly in the
Tk host window. Chromium is launched inside that nested display, so its first
map can never become a top-level window on the user's desktop.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from triview_workspace.engines.browser import (
    BrowserBackendAvailability,
    BrowserBackendUnavailable,
    BrowserLaunchError,
    BrowserLaunchRequest,
    BrowserSession,
    X11BraveBrowserBackend,
)
from triview_workspace.engines.browser_embedded import terminate_process_group
from triview_workspace.runtime_observability import record_runtime_event


XEPHYR_BROWSER_BACKEND_NAME = "XephyrEmbeddedBraveBrowserBackend"
_DEFAULT_SIZE = (800, 600)
_DISPLAY_MIN = 120
_DISPLAY_MAX = 220


@dataclass(slots=True)
class NestedX11Runtime:
    panel_id: str
    display_number: int
    display_name: str
    lock_path: Path
    xephyr_process: subprocess.Popen[bytes]
    xephyr_window_id: str
    browser_process: subprocess.Popen[bytes]
    nested_browser_window_id: str


def _safe_exact_pattern(value: str) -> str:
    return rf"^{re.escape(value)}$"


class XephyrEmbeddedBraveBrowserBackend(X11BraveBrowserBackend):
    """Launch Chromium in a nested X server already embedded in the panel."""

    def __init__(self, launch_timeout: float = 20.0) -> None:
        super().__init__(launch_timeout=launch_timeout)
        self._runtimes: dict[str, NestedX11Runtime] = {}

    @staticmethod
    def _xephyr_command() -> str | None:
        return shutil.which("Xephyr")

    def availability(self) -> BrowserBackendAvailability:
        report = super().availability()
        if not report.available:
            return report
        xephyr = self._xephyr_command()
        if xephyr is None:
            return BrowserBackendAvailability(
                False,
                "O pacote xserver-xephyr é necessário para criar navegadores "
                "que já nascem incorporados ao TriView.",
                browser_command=report.browser_command,
                xdotool_command=report.xdotool_command,
            )
        return BrowserBackendAvailability(
            True,
            "Backend Xephyr pronto: o navegador nasce dentro do painel sem "
            "mapear uma janela no desktop principal.",
            browser_command=report.browser_command,
            xdotool_command=report.xdotool_command,
        )

    def launch(
        self,
        request: BrowserLaunchRequest,
        parent_window_id: int,
    ) -> BrowserSession:
        availability = self.availability()
        if not availability.available:
            raise BrowserBackendUnavailable(availability.reason)
        assert availability.browser_command is not None
        assert availability.xdotool_command is not None
        xephyr = self._xephyr_command()
        assert xephyr is not None

        request.profile_dir.mkdir(parents=True, exist_ok=True)
        display_number, display_name, lock_path = self._allocate_display()
        width, height = _DEFAULT_SIZE
        xephyr_command = [
            xephyr,
            display_name,
            "-parent",
            str(int(parent_window_id)),
            "-screen",
            f"{width}x{height}",
            "-resizeable",
            "-noreset",
            "-nolisten",
            "tcp",
            "-ac",
            "-br",
        ]
        record_runtime_event(
            "browser_launch_requested",
            backend=XEPHYR_BROWSER_BACKEND_NAME,
            panel_id=request.panel_id,
            url=request.url,
            profile_dir=str(request.profile_dir),
            window_class=request.window_class,
            host_window_id=int(parent_window_id),
            containment="nested_xephyr",
            external_root_mapping_possible=False,
        )
        xephyr_process = subprocess.Popen(  # noqa: S603
            xephyr_command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        browser_process: subprocess.Popen[bytes] | None = None
        try:
            self._wait_for_display(display_name, xephyr_process)
            xephyr_window_id = self._wait_for_host_window(
                availability.xdotool_command,
                xephyr_process,
                int(parent_window_id),
            )
            nested_env = os.environ.copy()
            nested_env["DISPLAY"] = display_name
            nested_env.pop("WAYLAND_DISPLAY", None)
            browser_command = [
                availability.browser_command,
                f"--app={request.url}",
                f"--user-data-dir={request.profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "--ozone-platform=x11",
                "--disable-session-crashed-bubble",
                f"--class={request.window_class}",
                f"--name={request.window_class}",
                "--window-position=0,0",
                f"--window-size={width},{height}",
            ]
            browser_process = subprocess.Popen(  # noqa: S603
                browser_command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=nested_env,
                start_new_session=True,
            )
            nested_browser_window_id = self._wait_for_nested_browser_window(
                availability.xdotool_command,
                display_name,
                request.window_class,
                browser_process,
            )
            runtime = NestedX11Runtime(
                panel_id=request.panel_id,
                display_number=display_number,
                display_name=display_name,
                lock_path=lock_path,
                xephyr_process=xephyr_process,
                xephyr_window_id=xephyr_window_id,
                browser_process=browser_process,
                nested_browser_window_id=nested_browser_window_id,
            )
            self._runtimes[request.panel_id] = runtime
        except Exception:
            if browser_process is not None:
                terminate_process_group(browser_process)
            terminate_process_group(xephyr_process)
            self._release_display(lock_path)
            raise

        record_runtime_event(
            "browser_nested_window_ready",
            panel_id=request.panel_id,
            runtime_id=request.panel_id,
            browser_pid=browser_process.pid,
            xephyr_pid=xephyr_process.pid,
            host_window_id=int(parent_window_id),
            browser_window_id=xephyr_window_id,
            nested_browser_window_id=nested_browser_window_id,
            nested_display=display_name,
            containment="nested_xephyr",
            external_root_mapping_possible=False,
        )
        record_runtime_event(
            "browser_launch_embedded",
            panel_id=request.panel_id,
            runtime_id=request.panel_id,
            browser_pid=browser_process.pid,
            browser_window_id=xephyr_window_id,
            nested_browser_window_id=nested_browser_window_id,
            host_window_id=int(parent_window_id),
            embedded=True,
            containment="nested_xephyr",
            external_root_mapping_possible=False,
        )
        return BrowserSession(
            panel_id=request.panel_id,
            url=request.url,
            process=browser_process,
            window_id=xephyr_window_id,
            embedded=True,
        )

    def resize(self, session: BrowserSession, width: int, height: int) -> None:
        runtime = self._runtimes.get(session.panel_id)
        if runtime is None:
            return
        safe_width = max(64, int(width))
        safe_height = max(64, int(height))
        xdotool = self._xdotool_command()
        if xdotool is None:
            raise BrowserBackendUnavailable("O xdotool deixou de estar disponível.")
        self._run_host_xdotool(
            xdotool,
            "windowsize",
            runtime.xephyr_window_id,
            str(safe_width),
            str(safe_height),
        )
        nested_env = os.environ.copy()
        nested_env["DISPLAY"] = runtime.display_name
        self._run_nested(
            [xdotool, "windowmove", runtime.nested_browser_window_id, "0", "0"],
            nested_env,
            required=False,
        )
        self._run_nested(
            [
                xdotool,
                "windowsize",
                runtime.nested_browser_window_id,
                str(safe_width),
                str(safe_height),
            ],
            nested_env,
            required=False,
        )
        xrandr = shutil.which("xrandr")
        if xrandr is not None:
            self._run_nested(
                [xrandr, "--fb", f"{safe_width}x{safe_height}"],
                nested_env,
                required=False,
            )

    def close(self, session: BrowserSession) -> None:
        runtime = self._runtimes.pop(session.panel_id, None)
        if runtime is None:
            if session.process is not None:
                terminate_process_group(session.process)
            return
        record_runtime_event(
            "browser_nested_session_closing",
            panel_id=session.panel_id,
            browser_pid=runtime.browser_process.pid,
            xephyr_pid=runtime.xephyr_process.pid,
            nested_display=runtime.display_name,
        )
        terminate_process_group(runtime.browser_process)
        terminate_process_group(runtime.xephyr_process)
        self._release_display(runtime.lock_path)

    def focus(self, session: BrowserSession) -> bool:
        runtime = self._runtimes.get(session.panel_id)
        xdotool = self._xdotool_command()
        if runtime is None or xdotool is None:
            return False
        try:
            self._run_host_xdotool(xdotool, "windowfocus", runtime.xephyr_window_id)
        except BrowserLaunchError:
            return False
        return True

    def scroll(self, session: BrowserSession, steps: int) -> bool:
        runtime = self._runtimes.get(session.panel_id)
        xdotool = self._xdotool_command()
        if runtime is None or xdotool is None or steps == 0:
            return False
        button = "4" if steps > 0 else "5"
        repeat = min(12, max(1, abs(int(steps))))
        try:
            self._run_host_xdotool(
                xdotool,
                "click",
                "--window",
                runtime.xephyr_window_id,
                "--repeat",
                str(repeat),
                button,
            )
        except BrowserLaunchError:
            return False
        return True

    @staticmethod
    def _allocate_display() -> tuple[int, str, Path]:
        lock_root = Path(tempfile.gettempdir()) / "triview-xephyr-locks"
        lock_root.mkdir(parents=True, exist_ok=True)
        for display_number in range(_DISPLAY_MIN, _DISPLAY_MAX + 1):
            socket_path = Path("/tmp/.X11-unix") / f"X{display_number}"
            lock_path = lock_root / f"display-{display_number}.lock"
            if socket_path.exists():
                continue
            try:
                descriptor = os.open(
                    lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
            except FileExistsError:
                try:
                    owner_pid = int(lock_path.read_text(encoding="utf-8").strip())
                except (OSError, ValueError):
                    owner_pid = 0
                if owner_pid and Path(f"/proc/{owner_pid}").exists():
                    continue
                try:
                    lock_path.unlink()
                except OSError:
                    continue
                continue
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(f"{os.getpid()}\n")
            return display_number, f":{display_number}", lock_path
        raise BrowserLaunchError("Não há número de display Xephyr livre para o painel.")

    @staticmethod
    def _release_display(lock_path: Path) -> None:
        try:
            lock_path.unlink()
        except OSError:
            pass

    def _wait_for_display(
        self,
        display_name: str,
        process: subprocess.Popen[bytes],
    ) -> None:
        xdotool = self._xdotool_command()
        assert xdotool is not None
        env = os.environ.copy()
        env["DISPLAY"] = display_name
        deadline = time.monotonic() + self._launch_timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            result = subprocess.run(
                [xdotool, "getdisplaygeometry"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                env=env,
                timeout=2,
            )
            if result.returncode == 0:
                return
            time.sleep(0.04)
        raise BrowserLaunchError("O display Xephyr incorporado não ficou disponível.")

    def _wait_for_host_window(
        self,
        xdotool: str,
        process: subprocess.Popen[bytes],
        parent_window_id: int,
    ) -> str:
        deadline = time.monotonic() + self._launch_timeout
        xwininfo = shutil.which("xwininfo")
        while time.monotonic() < deadline:
            result = subprocess.run(
                [xdotool, "search", "--pid", str(process.pid)],
                capture_output=True,
                text=True,
                check=False,
                timeout=2,
            )
            candidates = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            for window_id in reversed(candidates):
                if xwininfo is None or self._is_descendant_of(
                    xwininfo,
                    window_id,
                    parent_window_id,
                ):
                    return window_id
            if process.poll() is not None:
                break
            time.sleep(0.04)
        raise BrowserLaunchError("A janela hospedeira do Xephyr não foi localizada no painel.")

    def _wait_for_nested_browser_window(
        self,
        xdotool: str,
        display_name: str,
        window_class: str,
        process: subprocess.Popen[bytes],
    ) -> str:
        env = os.environ.copy()
        env["DISPLAY"] = display_name
        pattern = _safe_exact_pattern(window_class)
        deadline = time.monotonic() + self._launch_timeout
        while time.monotonic() < deadline:
            for selector in ("--class", "--classname", "--name"):
                result = subprocess.run(
                    [xdotool, "search", "--onlyvisible", selector, pattern],
                    capture_output=True,
                    text=True,
                    check=False,
                    env=env,
                    timeout=2,
                )
                candidates = [
                    line.strip()
                    for line in result.stdout.splitlines()
                    if line.strip()
                ]
                if candidates:
                    return candidates[-1]
            if process.poll() is not None:
                break
            time.sleep(0.05)
        raise BrowserLaunchError(
            "O Brave iniciou no Xephyr, mas a janela interna não foi localizada."
        )

    @staticmethod
    def _run_nested(
        command: list[str],
        env: dict[str, str],
        *,
        required: bool,
    ) -> bool:
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                env=env,
                timeout=3,
            )
        except (OSError, subprocess.SubprocessError):
            if required:
                raise
            return False
        if required and result.returncode != 0:
            raise BrowserLaunchError(f"Comando no display aninhado falhou: {command[0]}")
        return result.returncode == 0

    def _run_host_xdotool(self, xdotool: str, *arguments: str) -> None:
        result = subprocess.run(
            [xdotool, *arguments],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
        if result.returncode != 0:
            raise BrowserLaunchError(
                result.stderr.strip() or f"Falha no xdotool: {' '.join(arguments)}"
            )

    @staticmethod
    def _window_parent(xwininfo: str, window_id: str) -> int | None:
        result = subprocess.run(
            [xwininfo, "-id", window_id, "-tree"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
        if result.returncode != 0:
            return None
        match = re.search(r"Parent window id:\s*(0x[0-9a-fA-F]+|\d+)", result.stdout)
        if match is None:
            return None
        try:
            return int(match.group(1), 0)
        except ValueError:
            return None

    @classmethod
    def _is_descendant_of(
        cls,
        xwininfo: str,
        candidate_window_id: str,
        ancestor_window_id: int,
    ) -> bool:
        try:
            current = int(candidate_window_id, 0)
        except ValueError:
            return False
        for _depth in range(16):
            if current == int(ancestor_window_id):
                return True
            parent = cls._window_parent(xwininfo, str(current))
            if parent is None or parent <= 0 or parent == current:
                return False
            current = parent
        return False


__all__ = [
    "NestedX11Runtime",
    "XEPHYR_BROWSER_BACKEND_NAME",
    "XephyrEmbeddedBraveBrowserBackend",
]
